"""
core/workers/planner.py — PlannerWorker (K2.2)

Canonical bridge between incoming requests and the worker runtime.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §9.1 — PlannerWorker.
    K2.2 — Production Runtime Migration.

Design:
    - Receives incoming query through ExecutionContext.
    - Wraps the legacy classify→dispatch→merge pipeline as a single worker.
    - Returns the merged answer as WorkerResult.
    - This is intentionally lightweight — NOT an LLM planner.
    - The classify→dispatch→merge logic moves here from Orchestrator,
      making it governable and event-sourced.

Production path:
    Orchestrator.handle() → WorkflowRuntime → PlannerWorker → result
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from core.workers.base import (
    AbstractCognitiveWorker,
    WorkerContext,
    WorkerResult,
)

logger = logging.getLogger("ocbrain.workers.planner")


class PlannerWorker(AbstractCognitiveWorker):
    """Canonical workflow entry worker.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §9.1 — PlannerWorker.
        K2.2 — bridges legacy pipeline into the worker runtime.

    Responsibilities:
        - Receive query from ExecutionContext
        - Classify query to identify target modules
        - Dispatch to modules in parallel
        - Merge results
        - Return unified answer

    NOT responsible for:
        - LLM planning
        - Autonomous reasoning
        - Multi-step decomposition
        - Reflection

    Constructor kwargs (injected via WorkerRegistry):
        modules: Dict of loaded expert modules.
        context_memory: ContextMemory for conversation history.
        model_router: ModelRouter for module dispatch.
        memory: UnifiedMemory for interaction persistence.
    """

    worker_type: str = "PlannerWorker"

    def __init__(
        self,
        *,
        modules: Optional[dict] = None,
        context_memory: Optional[Any] = None,
        model_router: Optional[Any] = None,
        memory: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._modules = modules or {}
        self._context_memory = context_memory
        self._model_router = model_router
        self._memory = memory

    async def _run(self, context: WorkerContext) -> WorkerResult:
        """Execute the classify→dispatch→merge pipeline.

        This is the legacy Orchestrator.handle() logic, moved here to make
        it governable (template method) and event-sourced (lifecycle events).

        Args:
            context: WorkerContext with query in context.query or
                     context.metadata["query"].

        Returns:
            WorkerResult with the merged answer as output.
        """
        query = context.query or context.metadata.get("query", "")
        if not query:
            return WorkerResult(
                success=False,
                error="No query provided to PlannerWorker",
            )

        if not self._modules:
            return WorkerResult(
                success=False,
                error="PlannerWorker: no modules available",
            )

        try:
            # ── 1. Parse ─────────────────────────────────────────────────
            from core import parser
            parsed = parser.parse(query)

            # ── 2. Context Assembly ──────────────────────────────────────
            from core.memory.assembly import context_assembler
            memory_context = await context_assembler.assemble_context(query)
            if self._context_memory:
                self._context_memory.set_long_term_memories_string(memory_context)

            # ── 3. Classify ──────────────────────────────────────────────
            from core.classifier_v3 import classify
            labels = classify(query, top_k=2)
            if not labels:
                return WorkerResult(
                    success=True,
                    output="I'm not sure which module should handle this. "
                           "Could you rephrase?",
                    metadata={"outcome": "unclassified"},
                )

            await self.emit_progress(context, "Classified query",
                                     percent=30.0,
                                     data={"labels": [l["module"] for l in labels]})

            # ── 4. Dispatch (parallel module execution) ──────────────────
            tasks = []
            for label in labels:
                mod_name = label["module"]
                tasks.append(self._dispatch_module(mod_name, query, context))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            await self.emit_progress(context, "Modules executed",
                                     percent=70.0)

            # ── 5. Process results ───────────────────────────────────────
            from core.model_router import RouteResult
            processed_results = []
            for i, res in enumerate(results):
                mod_name = labels[i]["module"]
                if isinstance(res, Exception):
                    logger.error("[PlannerWorker] Module %s failed: %s",
                                 mod_name, res)
                    processed_results.append(RouteResult(
                        answer=f"[Error in {mod_name}: {res}]",
                        source="error",
                    ))
                else:
                    processed_results.append(res)

            # ── 6. Merge ─────────────────────────────────────────────────
            from core import merger
            answer = await merger.merge(processed_results, query)

            await self.emit_progress(context, "Results merged",
                                     percent=90.0)

            # ── 7. Persist to UnifiedMemory ──────────────────────────────
            modules_used = [label["module"] for label in labels]
            if self._memory:
                try:
                    import hashlib
                    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
                    interaction_id = f"interaction:{digest[:32]}"

                    entities = {
                        "urls": parsed.entities.get("urls", []),
                        "languages": parsed.entities.get("languages", []),
                        "filenames": parsed.entities.get("filenames", []),
                    }
                    await self._memory.write(
                        content=answer,
                        content_type="interaction",
                        source="planner_worker",
                        importance=0.5,
                        entry_id=interaction_id,
                        metadata={
                            "interaction_id": interaction_id,
                            "query": query,
                            "modules_used": modules_used,
                            "entities": entities,
                            "classification_scores": labels,
                            "timestamp": time.time(),
                            "response_length": len(answer),
                        },
                    )
                except Exception as e:
                    logger.warning("[PlannerWorker] Memory write failed "
                                   "(non-blocking): %s", e)

            # ── 8. Save to context memory ────────────────────────────────
            if self._context_memory:
                entities = {
                    "urls": parsed.entities.get("urls", []),
                    "languages": parsed.entities.get("languages", []),
                    "filenames": parsed.entities.get("filenames", []),
                }
                self._context_memory.save(query, modules_used, answer, entities)

            await self.emit_progress(context, "Complete", percent=100.0)

            return WorkerResult(
                success=True,
                output=answer,
                metadata={
                    "modules_used": modules_used,
                    "outcome": "success",
                },
            )

        except Exception as e:
            logger.error("[PlannerWorker] Pipeline failed: %s", e, exc_info=True)
            return WorkerResult(
                success=False,
                error=f"PlannerWorker pipeline error: {e}",
            )

    async def _dispatch_module(self, mod_name: str, query: str,
                                context: WorkerContext) -> Any:
        """Dispatch to a single module via the model router."""
        if self._model_router:
            return await self._model_router.route(
                mod_name, query, self._context_memory)
        else:
            return WorkerResult(
                success=False,
                error=f"No model_router available for module '{mod_name}'",
            )
