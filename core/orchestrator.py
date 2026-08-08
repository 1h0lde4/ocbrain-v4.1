"""
core/orchestrator.py — Parallel Orchestrator (Converged V3).
Coordinates the query flow using parallel execution and safety limits.
"""
import asyncio
import hashlib
import logging
import time
from typing import Dict, Any, Optional

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
from .governance.governance_kernel import (
    GovernanceAction,
    GovernanceKernel,
    GovernanceVerdict,
    get_governance_kernel,
)
from .events.event_stream import EventStream, get_event_stream

logger = logging.getLogger("ocbrain.orchestrator")

# Session 5 — Production Runtime Integration.
#
# Orchestrator.handle() is the production request path, so it is governed
# using the exact same contract AbstractCognitiveWorker.execute() already
# uses, and that GovernanceKernel/EventStream are already tested against
# (core/workers/base.py). This is deliberately NOT a new mechanism: same
# GovernanceAction shape, same evaluate_action() call, same non-fatal
# event-emission wrapper. See the governance block and _emit_event() in
# handle() below.
ORCHESTRATOR_ACTION_TYPE = "orchestrator_handle"


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
                 memory: UnifiedMemory, *,
                 governance: Optional[GovernanceKernel] = None,
                 event_stream: Optional[EventStream] = None,
                 execution_runtime: Optional["ExecutionRuntime"] = None,
                 workflow_runtime: Optional["WorkflowRuntime"] = None,
                 capability_registry: Optional["CapabilityRegistry"] = None,
                 use_k42_frontend: bool = False):
        """
        governance/event_stream: Optional[...] = None, defaulting to the
        shared singleton via get_governance_kernel()/get_event_stream().

        execution_runtime: K2.1 — The canonical execution service.
        workflow_runtime: K2.2 — The canonical workflow coordinator.
        capability_registry: Runtime Integration Task 3 — required only when
            use_k42_frontend is True (plan() needs it); None is safe
            otherwise, matching every other Optional[...] dependency here.
        use_k42_frontend: Runtime Integration Task 2/3 — feature flag,
            default False. See config/settings.toml's [runtime] section
            and handle()'s own new branch for the exact behavior; when
            False, handle() is byte-for-byte identical to before this
            parameter existed.

        When workflow_runtime is provided, handle() delegates through:
            WorkflowRuntime → PlannerWorker → ExecutionRuntime
        When None (backward compatibility for tests), handle() uses
        the legacy classify→dispatch→merge flow.
        """
        self.modules = modules
        self.context = context
        self.router  = router
        self.memory: UnifiedMemory = memory
        self._governance: GovernanceKernel = governance or get_governance_kernel()
        self._event_stream: EventStream = event_stream or get_event_stream()
        self._execution_runtime = execution_runtime
        self._workflow_runtime = workflow_runtime
        self._capability_registry = capability_registry
        self._use_k42_frontend = use_k42_frontend
        self._id: str = "Orchestrator"
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

    async def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit a lifecycle event to the EventStream.

        Mirrors AbstractCognitiveWorker._emit_event() (core/workers/base.py)
        exactly: event emission failure must NEVER break query handling.
        """
        try:
            await self._event_stream.append(
                event_type=event_type,
                source=self._id,
                payload=payload,
            )
        except Exception as e:
            logger.warning("[Orchestrator] Event emission failed for %s: %s",
                            event_type, e)

    @async_trace_function(name="orchestrator_v3")
    async def handle(self, query: str, max_iterations: int = 5) -> str:
        """
        Main entry point for query processing.
        Uses semantic classification and parallel module dispatching.

        max_iterations: accepted for API compatibility but not currently
        enforced. handle() is a single-pass classify->dispatch->merge flow
        with no internal loop to bound -- the prior IterationBudget check
        here was dead code (constructed and checked exactly once per call,
        which can never exceed any max_iterations >= 1). RecursionGovernor
        (below) is keyed off recursion_depth, not max_iterations; this
        parameter itself remains accepted-but-unenforced.

        Session 5 — Production Runtime Integration: GovernanceKernel and
        EventStream are now wired here, using the exact same GovernanceAction
        contract and evaluate_action() call that AbstractCognitiveWorker.
        execute() already uses (core/workers/base.py) -- no new governance
        mechanism was introduced, per PI LAW 4. With today's default
        governors (RecursionGovernor, BudgetGovernor, EvolutionGovernor),
        action_type=ORCHESTRATOR_ACTION_TYPE (not in EvolutionGovernor's
        SELF_MODIFYING_ACTIONS), recursion_depth=0 (handle() has no actual
        recursion today), and no step_count/token_spend supplied (BudgetGovernor
        approves by design when absent -- see its docstring), every
        currently-passing call is APPROVEd: this closes the PI LAW 1
        structural gap ("no autonomous capability may bypass governance")
        without changing behavior for any existing caller or test.
        Recursion/budget enforcement across nested or chained calls, and
        wiring the remaining PI §6.1 governors (OrchestrationGovernor,
        MemoryGovernor, AgentGovernor, ConversationGuardrails -- none of
        which exist yet except the disconnected MemoryGovernor), remain
        future work; see the Session 5 Technical Debt Report.
        """
        interaction_id = _interaction_id(query)

        # ── Governance evaluation (PI LAW 1) — BEFORE any work, BEFORE the
        # backpressure guard, so a rejected/escalated request never consumes
        # a concurrency slot. Same REJECT/ESCALATE handling as
        # AbstractCognitiveWorker.execute(). ──────────────────────────────
        action = GovernanceAction(
            action_type=ORCHESTRATOR_ACTION_TYPE,
            worker_id=self._id,
            description=f"orchestrator_handle: {query[:120]}",
            recursion_depth=0,
            metadata={
                "interaction_id": interaction_id,
                # K3.5: Budget context for BudgetGovernor activation.
                # Values are 0 at orchestrator level (first evaluation in chain).
                # Accumulated budget propagates at worker level via ExecutionContext.
                "step_count": 0,
                "token_spend": 0.0,
            },
        )
        gov_result = self._governance.evaluate_action(action)

        if gov_result.verdict == GovernanceVerdict.REJECT:
            await self._emit_event("orchestrator.rejected", {
                "interaction_id": interaction_id,
                "reason": gov_result.reason,
                "governor": gov_result.governor,
            })
            logger.warning("[Orchestrator] Query rejected by %s: %s",
                            gov_result.governor, gov_result.reason)
            return (f"This request was blocked by governance "
                    f"({gov_result.governor}): {gov_result.reason}")

        if gov_result.verdict == GovernanceVerdict.ESCALATE:
            await self._emit_event("orchestrator.escalated", {
                "interaction_id": interaction_id,
                "reason": gov_result.reason,
                "governor": gov_result.governor,
            })
            logger.info("[Orchestrator] Query escalated by %s: %s",
                        gov_result.governor, gov_result.reason)
            return (f"This request requires human approval "
                    f"({gov_result.governor}): {gov_result.reason}")

        async with BackpressureGuard():
            await self._emit_event("orchestrator.query_started", {
                "interaction_id": interaction_id,
                "query_preview": query[:120],
            })

            # ── Runtime Integration — K4.2 Cognitive Front-End (feature-flagged) ──
            # Config: [runtime] use_k42_frontend in config/settings.toml, default
            # false. Additive only -- when the flag is False (the default),
            # execution falls through unchanged to the existing K2.2 branch
            # immediately below; this block is not entered at all, and no line
            # in that branch or the legacy branch beneath it was modified to
            # add this one. See docs/architecture/K4_2_RUNTIME_INTEGRATION_PLAN.md
            # and the follow-up Runtime Integration Report for the analysis
            # this branch implements, including the worker_type <->
            # capability_type bridge (core/workers/capability_executor.py)
            # this branch relies on to make the compiled WorkflowDefinition
            # executable at all.
            #
            # Compound requests (interpret_request() returning more than one
            # Goal) are handled narrowly: only the first Goal is planned,
            # compiled, and executed here. Multi-goal merge/aggregation
            # through the K4.2 pipeline is not specified anywhere in the K4.2
            # architecture and is not invented here -- deferred, documented
            # future work (see the Runtime Integration Report's Final Notes).
            if self._use_k42_frontend and self._workflow_runtime is not None:
                try:
                    from core.cognitive.compiler import CompilationStatus
                    from core.cognitive.compiler import compile as compile_plan
                    from core.cognitive.intent import interpret_request
                    from core.cognitive.planner import (
                        PlannerRequest, PlannerStatus, plan as plan_fn,
                    )
                    from core.workers.evaluator import EvaluationRecord

                    goals = await interpret_request(
                        query, memory=self.memory, event_stream=self._event_stream)
                    goal = goals[0]

                    planner_request = PlannerRequest(goal_id=goal.resource_id, goal=goal)
                    planner_result = await plan_fn(
                        planner_request, self._capability_registry,
                        event_stream=self._event_stream)

                    if planner_result.status != PlannerStatus.READY_FOR_COMPILATION:
                        await self._emit_event("orchestrator.query_failed", {
                            "interaction_id": interaction_id,
                            "error": str(planner_result.impasse_detail),
                            "error_type": "PlannerImpasse",
                        })
                        return ("Sorry, I could not form a plan for this "
                                f"request: {planner_result.status}")

                    execution_plan = planner_result.execution_plan
                    compilation_result = await compile_plan(
                        execution_plan, event_stream=self._event_stream,
                        governance=self._governance)

                    if compilation_result.status != CompilationStatus.COMPILED:
                        # K4 §16 invariant 9: never retried here or anywhere
                        # -- SupervisorWorker only surfaces this outcome.
                        if self._execution_runtime is not None:
                            await self._execution_runtime.invoke(
                                "SupervisorWorker",
                                query=query,
                                workflow_id=execution_plan.resource_id,
                                metadata={"parameters": {
                                    "compilation_result": compilation_result}},
                            )
                        await self._emit_event("orchestrator.query_failed", {
                            "interaction_id": interaction_id,
                            "error": compilation_result.status,
                            "error_type": "CompilationRejected",
                        })
                        return ("Sorry, this request could not be compiled "
                                f"into a runnable plan ({compilation_result.status}).")

                    workflow_definition = compilation_result.workflow_definition
                    wf_result = await self._workflow_runtime.execute(
                        workflow_definition,
                        query=query,
                        session_id=interaction_id,
                        metadata={"interaction_id": interaction_id},
                    )
                    answer = wf_result.output or ""

                    # Task 5 — post-execution hooks. Same governed
                    # ExecutionRuntime.invoke() path as the SupervisorWorker
                    # call above and PlannerWorker's own invocation in the
                    # existing branch below.
                    if self._execution_runtime is not None:
                        eval_result = await self._execution_runtime.invoke(
                            "EvaluatorWorker",
                            query=query,
                            workflow_id=execution_plan.resource_id,
                            metadata={"parameters": {"execution_plan": execution_plan}},
                        )
                        if (eval_result.success
                                and "evaluation_record" in eval_result.artifacts):
                            record = EvaluationRecord(
                                **eval_result.artifacts["evaluation_record"])
                            await self._execution_runtime.invoke(
                                "ReflectionWorker",
                                query=query,
                                workflow_id=execution_plan.resource_id,
                                metadata={"parameters": {
                                    "evaluation_record": record,
                                    "execution_plan": execution_plan,
                                }},
                            )

                    capability_types = ", ".join(
                        step.capability_type for step in execution_plan.steps)
                    shadow_learner.record_interaction(
                        query=query,
                        answer=answer,
                        module_name=capability_types,
                        confidence=execution_plan.confidence,
                    )

                    await self._emit_event("orchestrator.query_completed", {
                        "interaction_id": interaction_id,
                        "outcome": "success",
                        "execution_path": "k42_cognitive_frontend",
                    })
                    return answer

                except Exception as e:
                    # Mirrors the existing workflow-runtime branch's own
                    # containment immediately below -- WorkflowRuntime.
                    # execute() itself never raises (Failure Containment),
                    # but interpret_request()/plan()/compile() are new call
                    # sites this branch introduces, so containment here is
                    # not merely defensive the way it is in the K2.2 branch.
                    logger.error("[Orchestrator] Unexpected error in "
                                 "K4.2 cognitive-frontend path: %s", e, exc_info=True)
                    await self._emit_event("orchestrator.query_failed", {
                        "interaction_id": interaction_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    })
                    return (f"Sorry, I encountered an internal error: "
                            f"{type(e).__name__}")

            # ── K2.2 — Production Runtime Migration ────────────────────────
            # When a WorkflowRuntime was supplied at construction (main.py,
            # composition root), query handling delegates through:
            #     WorkflowRuntime -> ExecutionRuntime -> PlannerWorker
            # PlannerWorker (core/workers/planner.py) runs the identical
            # classify->dispatch->merge pipeline that used to live inline
            # below, but now governed per-worker (AbstractCognitiveWorker.
            # execute()'s template method, PI LAW 1) and event-sourced at
            # node granularity (WorkflowRuntime's workflow.started/completed
            # + ExecutionRuntime's execution.completed), on top of the
            # orchestrator-level governance/event pair already emitted
            # above. Both governance evaluations are safe to run in
            # sequence: RecursionGovernor and BudgetGovernor are stateless
            # per-call (state lives in the caller-supplied GovernanceAction,
            # not the governor -- see BudgetGovernor's BUG-03 fix note in
            # core/governance/governance_kernel.py), so this is strictly
            # additional visibility, not double-counting.
            #
            # When workflow_runtime is None (existing tests that construct
            # Orchestrator without it, per TestBackwardCompatibility in
            # tests/test_execution_runtime.py), handle() falls through to
            # the untouched legacy flow below. This is the "legacy
            # compatibility bridge" the K2.2 migration calls for -- kept
            # only because it's still test-reachable, not because anything
            # in main.py's composition root constructs Orchestrator without
            # a workflow_runtime today.
            if self._workflow_runtime is not None:
                try:
                    from core.workflow.definition import build_planner_workflow

                    definition = build_planner_workflow()
                    wf_result = await self._workflow_runtime.execute(
                        definition,
                        query=query,
                        session_id=interaction_id,
                        metadata={"interaction_id": interaction_id},
                    )

                    if not wf_result.success:
                        logger.error("[Orchestrator] Workflow execution "
                                     "failed: %s", wf_result.error)
                        await self._emit_event("orchestrator.query_failed", {
                            "interaction_id": interaction_id,
                            "error": wf_result.error,
                            "error_type": "WorkflowFailure",
                        })
                        return (f"Sorry, I encountered an internal error: "
                                f"{wf_result.error}")

                    answer = wf_result.output or ""
                    planner_result = wf_result.node_results.get(
                        definition.entry_node)
                    modules_used = (
                        planner_result.metadata.get("modules_used", [])
                        if planner_result else []
                    )

                    # Shadow learning (Phase 3) is not replicated inside
                    # PlannerWorker -- it is an orchestrator-level maturity
                    # tracking concern, not part of the governed worker
                    # contract, so it stays here for both paths.
                    shadow_learner.record_interaction(
                        query=query,
                        answer=answer,
                        module_name=", ".join(modules_used),
                        confidence=1.0,
                    )

                    await self._emit_event("orchestrator.query_completed", {
                        "interaction_id": interaction_id,
                        "outcome": "success",
                        "modules_used": modules_used,
                        "execution_path": "workflow_runtime",
                    })
                    return answer

                except Exception as e:
                    # Should not happen -- WorkflowRuntime.execute() never
                    # raises (Failure Containment principle). Contained here
                    # anyway, consistent with the legacy path's own
                    # top-level except block below.
                    logger.error("[Orchestrator] Unexpected error in "
                                 "workflow-runtime path: %s", e, exc_info=True)
                    await self._emit_event("orchestrator.query_failed", {
                        "interaction_id": interaction_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    })
                    return (f"Sorry, I encountered an internal error: "
                            f"{type(e).__name__}")

            # ── Legacy Compatibility Bridge ─────────────────────────────────
            # Reached only when workflow_runtime is None. main.py's
            # composition root always supplies one (K2.2), so this path is
            # exercised in production only if that wiring is ever removed;
            # it remains live today solely to keep tests that construct
            # Orchestrator directly (without ExecutionRuntime/WorkflowRuntime)
            # passing unmodified. Scheduled for removal once K2.3's
            # CapabilityRegistry work confirms nothing else still relies on
            # constructing a workflow_runtime-less Orchestrator -- see the
            # K2.2 Cutover Report's Legacy Runtime Audit.
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
                    await self._emit_event("orchestrator.query_completed", {
                        "interaction_id": interaction_id,
                        "outcome": "unclassified",
                    })
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
                # interaction_id computed once at the top of handle() (Session 5:
                # reused here rather than recomputed -- same deterministic value).
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

                await self._emit_event("orchestrator.query_completed", {
                    "interaction_id": interaction_id,
                    "outcome": "success",
                    "modules_used": modules_used,
                })
                return answer

            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)
                await self._emit_event("orchestrator.query_failed", {
                    "interaction_id": interaction_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                })
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
