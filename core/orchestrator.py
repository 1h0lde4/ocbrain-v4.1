"""
core/orchestrator.py — Parallel Orchestrator (Converged V3).
Coordinates the query flow using parallel execution and safety limits.
"""
import asyncio
import hashlib
import logging
import time
from typing import Dict, Any

from . import parser, merger
from .context import ContextMemory
from .model_router import ModelRouter, RouteResult
from .classifier_v3 import classify
from .observability.tracer import async_trace_function, span
from .runtime.limits import BackpressureGuard
from .memory.unified_memory import UnifiedMemory
from .memory.assembly import context_assembler
from .shadow.shadow_learner import shadow_learner
from .meta.health_monitor import health_monitor

logger = logging.getLogger("ocbrain.orchestrator")


def _interaction_id(query: str) -> str:
    """
    Deterministic identity for an Orchestrator interaction, based on the
    query text alone.

    Interaction identity (the question/topic) and response identity (a
    specific answer) are separate concerns:
    - L1 storage = current knowledge state: one row per unique query, kept
      current via ON CONFLICT(entry_id) DO UPDATE. A regenerated or improved
      answer to the same question updates this row in place.
    - L4 archive = full response history: a new immutable event is appended
      on every write(), so every answer ever produced is preserved regardless
      of L1 deduplication.

    Using SHA256(query) instead of SHA256(query+answer) ensures that a
    re-run of the same query improves the existing L1 entry rather than
    accumulating parallel entries that would dilute retrieval quality.

    Pure function: no singletons, no counters, no global state.
    """
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return f"interaction:{digest[:32]}"


class Orchestrator:
    def __init__(self, modules: dict, context: ContextMemory, router: ModelRouter,
                 memory: UnifiedMemory):
        self.modules = modules
        self.context = context
        self.router  = router
        self.memory: UnifiedMemory = memory
        self._background_tasks: list[asyncio.Task] = []
        # Start Phase 4/5 Cognitive Memory Engines
        self._start_background_engines()

    def _start_background_engines(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("[Orchestrator] Background engines deferred: no running event loop")
            return

        # Note (Architecture Hardening Session): MemoryConsolidator previously
        # ran here too, hourly, operating on the legacy `cognitive_vault`
        # singleton (core/memory/consolidation/consolidator.py) -- a data
        # store fully disconnected from UnifiedMemory since Session 4's
        # migration. It provided zero benefit to the live memory system
        # (its two other methods, _merge_duplicates and
        # _distill_episodic_to_semantic, are no-ops; only the cognitive_vault
        # decay/prune logic did real work, against data nothing reads).
        # Stopped rather than migrated: active memory improvement for
        # UnifiedMemory is MemoryCuratorWorker's job (v4.3.6), explicitly
        # out of scope to build here. The capability is honestly absent
        # until then, not silently running against the wrong store.
        self._background_tasks.extend([
            loop.create_task(health_monitor.start(), name="health-monitor-start"),
        ])

    async def close(self):
        """Stop background services owned by this orchestrator."""
        health_monitor.stop()
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

        max_iterations: accepted for API compatibility but not currently
        enforced. handle() is a single-pass classify->dispatch->merge flow
        with no internal loop to bound -- the prior IterationBudget check
        here was dead code (constructed and checked exactly once per call,
        which can never exceed any max_iterations >= 1). Real iteration/
        recursion limiting belongs in GovernanceKernel.RecursionGovernor
        (core/governance/governance_kernel.py), which already exists,
        is already tested, and is already used by EventStream/workers/
        graph -- but is not yet wired into Orchestrator.handle(). See the
        Architecture Hardening Session report for why that wiring is
        deliberately not implemented here.
        """
        async with BackpressureGuard():
            try:
                logger.info(f"[Orchestrator] Handling query: {query[:80]}")

                # 1. Parse (Extract entities)
                parsed = parser.parse(query)

                # 2. Cognitive Memory Context Assembly (Phase 5 Evolution)
                with span("cognitive_memory_assembly"):
                    # Assemble optimized context from L1, L2, L3 tiers
                    memory_context = await context_assembler.assemble_context(query)
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

                # 6b. Persist interaction to UnifiedMemory.
                #
                # Session 4:  activated UnifiedMemory as production memory owner.
                # Session 4B: structured payload, stable identity, enriched metadata.
                # Session 4C: fixed identity semantics (query-only hash, not Q+A hash)
                #             and removed summary=query (summary is reserved for
                #             LLM-generated summaries by MemoryCuratorWorker at v4.3.6).
                #             The query is fully preserved in metadata["query"] for
                #             analytics, replay, and future metadata-aware retrieval
                #             (v4.3.8 Cognitive Retrieval Engine).
                interaction_id = _interaction_id(query)
                try:
                    await self.memory.write(
                        content=answer,
                        content_type="interaction",
                        source="orchestrator",
                        importance=0.5,
                        entry_id=interaction_id,
                        metadata={
                            "interaction_id":        interaction_id,
                            "query":                  query,
                            "modules_used":           modules_used,
                            "entities":               entities,
                            "classification_scores":  labels,
                            "timestamp":              time.time(),
                            "response_length":        len(answer),
                        },
                    )
                except Exception as e:
                    logger.warning(f"[Orchestrator] Memory write failed (non-blocking): {e}")

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
