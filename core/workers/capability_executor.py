"""
core/workers/capability_executor.py — CapabilityExecutorWorker.

Runtime Integration Task 4 — the worker_type <-> capability_type bridge.

Not a K4.2 packet. This module exists solely to let WorkerRegistry /
ExecutionRuntime execute a WorkflowNode that core/cognitive/compiler.py
produced, without changing compile(), Planner, or WorkflowDefinition at
all -- exactly as this task's own constraints require.

The gap, confirmed by direct code reading (docs/architecture/
K4_2_RUNTIME_INTEGRATION_PLAN.md and the follow-up Runtime Integration
Report both document this the same way):

    core/cognitive/compiler.py's _compile_step() deliberately sets
    WorkflowNode.worker_type = PlanStep.capability_type (e.g.
    "llm_completion") -- a documented, deliberate Packet 06 choice, not
    a defect, and not something this task is permitted to change.

    core/runtime/execution_runtime.py's invoke() does
    self._registry.get(worker_type) against WorkerRegistry, which maps
    worker_type strings to *registered worker class names* only
    ("PlannerWorker", "MemoryCuratorWorker", ...) -- confirmed by
    reading core/runtime/worker_registry.py directly: register() always
    keys off worker_class.worker_type, with no way to register a class
    under a different name.

The bridge: a worker whose own `worker_type` class attribute IS the
literal capability_type string ("llm_completion") -- the only
capability_type registered anywhere in this repository today (confirmed
via CapabilityRegistry's contents in main.py). WorkerRegistry.get("llm_
completion") then resolves to this class exactly the way it resolves
"PlannerWorker" to PlannerWorker today. Nothing about WorkerRegistry,
ExecutionRuntime, or WorkflowRuntime needed to change to make this work.

Deliberately narrow, not a capability-selection mechanism: this worker
does not choose between capabilities or adapters -- CapabilityRegistry's
own ranking (AdapterRuntime._rank_adapters(), unchanged) still does
that. It exists only to answer "given a WorkflowNode whose worker_type
already IS a specific capability_type, how does execution actually
reach AdapterRuntime.invoke() for it" -- reusing the exact call pattern
core/workers/planner.py's own _dispatch_module() already uses for the
same capability, not a new invocation convention.

If a second capability_type is ever registered, this worker does not
automatically cover it -- per this task's own "as small and isolated as
possible... do not invent speculative infrastructure" instruction, this
is intentionally not solved for a hypothetical second capability that
does not exist in this repository today. Extending to more capabilities
(one worker per capability_type, or a single worker with an internal
dispatch table) is future work, not a redesign of this one.
"""
from __future__ import annotations

from typing import Any, Dict

from core.capabilities.adapter_runtime import AdapterRuntime
from core.capabilities.capability import CapabilityRequest, CapabilityType
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult


class CapabilityExecutorWorker(AbstractCognitiveWorker):
    """Bridges one compiled WorkflowNode to AdapterRuntime.invoke().

    worker_type is deliberately the literal capability_type string, not
    a descriptive class-style name -- see module docstring for why this
    is required for WorkerRegistry.get(node.worker_type) to resolve at
    all, given WorkflowNode.worker_type already equals capability_type
    coming out of compile() (Packet 06, unchanged, not modified by this
    task).
    """

    worker_type = CapabilityType.LLM_COMPLETION

    def __init__(self, *, adapter_runtime: AdapterRuntime, **kwargs: Any) -> None:
        """Args:
            adapter_runtime: required (no singleton getter exists for
                this, matching AdapterRuntime's own established
                composition-root-only construction pattern -- confirmed
                by reading main.py, which constructs exactly one
                instance and threads it explicitly to every caller that
                needs it, PlannerWorker included).
            **kwargs: forwarded to AbstractCognitiveWorker.__init__
                (governance, event_stream).
        """
        super().__init__(**kwargs)
        self._adapter_runtime = adapter_runtime

    async def _run(self, context: WorkerContext) -> WorkerResult:
        """Execute the one compiled step this invocation represents.

        node_config arrives under context.metadata["node_config"], not
        context.parameters -- confirmed by reading
        core/workflow/runtime.py's _execute_node_with_retry() directly:
        it builds ExecutionContext.metadata={"query":..., "node_id":...,
        "node_config": node.config, "attempt":..., **metadata}, with no
        "parameters" key set anywhere in that construction. (Contrast
        with core/workers/supervisor.py's own retry path, which builds
        its ExecutionContext with metadata={"parameters": {...}}
        directly and deliberately -- a different call site, not an
        inconsistency in this bridge.) node.config's shape
        ({"description":..., "capability_type":...}) is exactly what
        core/cognitive/compiler.py's _compile_step() puts there,
        unchanged.
        """
        node_config: Dict[str, Any] = context.metadata.get("node_config", {})
        description = node_config.get("description", context.query)
        capability_type = node_config.get("capability_type", self.worker_type)

        # Same CapabilityRequest shape core/workers/planner.py's own
        # _dispatch_module() already constructs for this exact
        # capability -- reused, not reinvented (this task's own
        # instruction: "If a better implementation already exists in
        # the repository, reuse it").
        request = CapabilityRequest(
            capability_type=capability_type,
            payload={
                "module_name": "k4.2_capability_step",
                "subtask": description,
                "context": "",
            },
        )
        result = await self._adapter_runtime.invoke(capability_type, request=request)

        if not result.success:
            return WorkerResult(
                success=False,
                error=result.error or f"capability invocation failed for '{capability_type}'",
            )
        return WorkerResult(
            success=True,
            output=result.output,
            artifacts={"adapter_used": result.adapter_used,
                       "capability_type": capability_type},
        )
