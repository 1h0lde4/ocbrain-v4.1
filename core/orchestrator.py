"""
core/orchestrator.py — Parallel Orchestrator (Converged V3).
Coordinates the query flow using parallel execution and safety limits.
"""
import asyncio
import logging
from typing import Dict, Any

from . import parser, merger
from .context import ContextMemory
from .model_router import ModelRouter, RouteResult
from .classifier_v3 import classify
from .observability.tracer import async_trace_function, span
from .runtime.limits import IterationBudget, BackpressureGuard
from .memory.mem_vault import MemoryVault
from .memory.hybrid_retrieval import HybridRetriever
from .memory.assembly import context_assembler
from .memory.consolidation.consolidator import consolidator
from .shadow.shadow_learner import shadow_learner
from .meta.health_monitor import health_monitor

logger = logging.getLogger("ocbrain.orchestrator")


class Orchestrator:
    def __init__(self, modules: dict, context: ContextMemory, router: ModelRouter):
        self.modules = modules
        self.context = context
        self.router  = router
        self.vault   = MemoryVault()
        self.retriever = HybridRetriever(self.vault)
        self._background_tasks: list[asyncio.Task] = []
        # Start Phase 4/5 Cognitive Memory Engines
        self._start_background_engines()

    def _start_background_engines(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("[Orchestrator] Background engines deferred: no running event loop")
            return

        self._background_tasks.extend([
            loop.create_task(health_monitor.start(), name="health-monitor-start"),
            loop.create_task(consolidator.start(), name="memory-consolidator-start"),
        ])

    async def close(self):
        """Stop background services owned by this orchestrator."""
        health_monitor.stop()
        consolidator.stop()
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

    @async_trace_function(name="orchestrator_v3")
    async def handle(self, query: str, max_iterations: int = 5) -> str:
        """
        Main entry point for query processing.
        Uses semantic classification and parallel module dispatching.
        """
        async with BackpressureGuard():
            budget = IterationBudget(max_steps=max_iterations)
            try:
                budget.check()
                logger.info(f"[Orchestrator] Handling query: {query[:80]}")

                # 1. Parse (Extract entities)
                parsed = parser.parse(query)

                # 2. Cognitive Memory Context Assembly (Phase 5 Evolution)
                with span("cognitive_memory_assembly"):
                    # Assemble optimized context from L1, L2, L3 tiers
                    memory_context = context_assembler.assemble_context(query)
                    self.context.set_long_term_memories_string(memory_context)
                    
                    # Phase 4: Record retrieval health
                    # (Simplified check: if context has content, it's a hit)
                    health_monitor.record_retrieval(hit=len(memory_context) > 0)

                # 3. Classify (Identify target modules)
                labels = classify(query, top_k=2)
                if not labels:
                    return "I'm not sure which module should handle this. Could you rephrase?"

                # 4. Dispatch (Execute modules in parallel)
                tasks = [
                    self._run_module(label, query, parsed) 
                    for label in labels
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 5. Merge
                processed_results = []
                for i, res in enumerate(results):
                    mod_name = labels[i]["module"]
                    if isinstance(res, Exception):
                        logger.error(f"[Orchestrator] Module {mod_name} failed: {res}")
                        processed_results.append(RouteResult(
                            answer=f"[Error in {mod_name}: {res}]",
                            source="error"
                        ))
                    else:
                        processed_results.append(res)

                answer = await merger.merge(processed_results, query)

                # 6. Save to context memory (Short-Term)
                modules_used = [label_item["module"] for label_item in labels]
                entities = {
                    "urls":      parsed.entities.get("urls", []),
                    "languages": parsed.entities.get("languages", []),
                    "filenames": parsed.entities.get("filenames", []),
                }
                self.context.save(query, modules_used, answer, entities)

                # 7. Shadow Learning (Phase 3)
                shadow_learner.record_interaction(
                    query=query,
                    answer=answer,
                    module_name=", ".join(modules_used),
                    confidence=1.0 # Standard success confidence
                )

                return answer

            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)
                return f"Sorry, I encountered an internal error: {type(e).__name__}"

    @async_trace_function(name="module_execution")
    async def _run_module(self, label: Dict[str, Any], query: str, parsed: Any) -> RouteResult:
        """Execute a single module via the router."""
        mod_name = label["module"]
        # Use the router to handle shadow promotion / maturity
        return await self.router.route(mod_name, query, self.context)

    def status(self) -> dict:
        return {
            name: mod.health()
            for name, mod in self.modules.items()
        }
