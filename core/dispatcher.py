"""
core/dispatcher.py — Async parallel + serial task executor.
Resolves the DAG from decomposer and fires tasks in correct order.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional

from .decomposer import Task
from .model_router import ModelRouter, RouteResult


@dataclass
class TaskResult:
    task_id: str
    module: str
    result: RouteResult


async def run(
    tasks: list[Task],
    router: ModelRouter,
    context,
    modules: dict,
) -> list[TaskResult]:
    """
    Execute tasks respecting dependency order.
    Independent tasks run in parallel via asyncio.gather().
    Sequential tasks receive the previous result injected into their subtask.
    """
    completed: dict[str, TaskResult] = {}

    while len(completed) < len(tasks):
        # Find all tasks whose deps are satisfied
        ready = [
            t for t in tasks
            if t.id not in completed
            and all(dep in completed for dep in t.deps)
        ]
        if not ready:
            # Circular dependency guard
            break

        # Inject upstream results into subtask strings for sequential tasks
        enriched = []
        for task in ready:
            subtask = task.subtask
            for dep_id in task.deps:
                dep_result = completed[dep_id].result.answer
                subtask = f"[Context from previous step: {dep_result[:500]}]\n\n{subtask}"
            enriched.append((task, subtask))

        # Dispatch all ready tasks in parallel
        async_tasks = [
            _dispatch_one(task, subtask, router, context, modules)
            for task, subtask in enriched
        ]
        results = await asyncio.gather(*async_tasks, return_exceptions=True)

        for (task, _), res in zip(enriched, results):
            if isinstance(res, Exception):
                # Wrap exception in a fallback result so pipeline continues
                from .model_router import RouteResult
                res = TaskResult(
                    task_id=task.id,
                    module=task.module,
                    result=RouteResult(
                        answer=f"[Module {task.module} error: {res}]",
                        source="error",
                    ),
                )
            completed[task.id] = res

    return list(completed.values())


async def _dispatch_one(
    task: Task,
    subtask: str,
    router: ModelRouter,
    context,
    modules: dict,
) -> TaskResult:
    module_obj = modules.get(task.module)
    if module_obj is None:
        from .model_router import RouteResult
        return TaskResult(
            task_id=task.id,
            module=task.module,
            result=RouteResult(
                answer=f"[Module '{task.module}' not found]",
                source="error",
            ),
        )

    # Let the module do its RAG retrieval, then route through the maturity gate
    route_result = await module_obj.run_routed(subtask, context, router)
    return TaskResult(task_id=task.id, module=task.module, result=route_result)
