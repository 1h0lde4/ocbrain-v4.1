"""
main.py — OCBrain v4.1 — Composition Root

Canonical entry point for the OCBrain runtime.
Constructs and wires all production singletons:
  - UnifiedMemory (L0-L4)
  - GovernanceKernel (7 governors — K2.4 complete: PI §6.1 canonical set)
  - EventStream (SQLite WAL)
  - CapabilityRegistry (LLM_COMPLETION capability, 3 registered adapters)
  - ResourceManager (HTTPClientResource, ModelResource binding)
  - AdapterRuntime (capability execution: selection, fallback, isolation)
  - WorkerRegistry (worker type index: MemoryCuratorWorker, PlannerWorker)
  - ExecutionRuntime (worker invocation service)
  - WorkflowRuntime (DAG coordinator, wraps ExecutionRuntime)
  - MemoryCuratorWorker (registered, wired to memory)
  - Orchestrator (query handler, delegates through WorkflowRuntime)

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §7 — Execution Model.
    KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.
    K2.1 — ExecutionRuntime constructed and worker-invocation-capable.
    K2.2 — WorkflowRuntime becomes the production execution path:
           Orchestrator.handle() -> WorkflowRuntime -> ExecutionRuntime ->
           PlannerWorker. See K2.2 Cutover Report for the full chain and
           the reachability audit that verifies this is actually live
           (K2.1 alone constructed ExecutionRuntime and passed it to
           Orchestrator, but nothing in Orchestrator.handle() ever called
           it — that gap is what this session's wiring closes, for both
           K2.1 and K2.2 together).
    K2.3 — Capability Runtime: PlannerWorker's module dispatch no longer
           calls ModelRouter directly. It goes through AdapterRuntime,
           which resolves CapabilityType.LLM_COMPLETION to a registered
           Adapter (ModelRouterAdapter by default, wrapping the same
           ModelRouter unmodified -- a documented compatibility wrapper,
           not a replacement; see K2_3_CAPABILITY_RUNTIME_REPORT.md).
           OllamaAdapter/OpenAICompatAdapter register alongside it as the
           "pure" capability path with no maturity-tracking layer.
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn
from core.runtime.state import state_store

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ocbrain")


async def check_ollama() -> bool:
    import httpx
    from core.config import config
    host = config.get("global.ollama_host") or "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{host}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def prewarm_models(modules: dict):
    """
    V2.1 FIX: send a silent no-op to each unique model.
    Ollama loads the model into VRAM once — first real query is instant.
    All pre-warms run in parallel.
    """
    import httpx
    from core.config import config

    host   = config.get("global.ollama_host") or "http://localhost:11434"
    models = set()
    for name in modules:
        state = config.get_module_state(name)
        m = state.get("bootstrap_model") or "mistral"
        models.add(m)

    log.info(f"Pre-warming {len(models)} model(s): {models}")

    async def _warm(model: str):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": " ", "stream": False,
                          "options": {"num_predict": 1}},
                )
            log.info(f"  ✓ {model} warm")
        except Exception as e:
            log.warning(f"  ✗ {model} pre-warm failed: {e}")

    await asyncio.gather(*[_warm(m) for m in models])


async def main():
    print("=" * 55)
    
    # Step 0: State Store
    await state_store.start()

    # Step 1: Migrations
    log.info("Running schema migrations...")
    try:
        from core.migrator import run_migrations
        run_migrations()
    except Exception as e:
        log.error(f"Migration failed: {e}")
        sys.exit(1)

    # Step 2: Config + version
    from core.config import config
    from core.brain_version import brain_version_manager
    log.info(f"Brain: {brain_version_manager.brain_version} | "
             f"App: {brain_version_manager.app_version} | "
             f"Schema: v{brain_version_manager.schema_version}")

    # Step 3: Ollama check
    log.info("Checking Ollama...")
    ollama_ok = await check_ollama()
    if not ollama_ok:
        log.warning("Ollama not reachable — bootstrap/shadow stages will fail")
    else:
        log.info("Ollama OK")

    # Step 4: Load modules
    log.info("Loading modules...")
    from core.module_registry import load_all
    modules = load_all()
    if not modules:
        log.error("No modules loaded.")
        sys.exit(1)
    log.info(f"Loaded {len(modules)} module(s): {list(modules.keys())}")

    # Step 4b: Health check each module
    for name, mod in modules.items():
        try:
            h = mod.health()
            if not h.get("db_ok", True):
                log.warning(f"  Module '{name}': ChromaDB not OK — queries may fail")
            else:
                log.info(f"  Module '{name}': OK (stage={h.get('stage','?')}, "
                         f"kb_chunks={h.get('kb_chunks',0)})")
        except Exception as e:
            log.error(f"  Module '{name}': health check failed — {e}")

    # Step 5: Pre-warm Ollama models (V2.1)
    if ollama_ok:
        log.info("Pre-warming Ollama models...")
        await prewarm_models(modules)

    # Step 6: Orchestrator
    from core.context import context_memory
    from core.model_router import model_router
    from core.orchestrator import Orchestrator
    from core.memory.unified_memory import get_unified_memory
    from core.memory.backends.sqlite_graph import SQLiteGraphBackend
    from core.memory.graph.entity_extractor import RegexEntityExtractor
    from core.governance.governance_kernel import get_governance_kernel
    from core.events.event_stream import get_event_stream

    memory = get_unified_memory()

    # Session 5 — Graph Backend Wiring. Session 5.25 — Graph Index Foundation.
    # Reality-audit finding: register_graph_backend() was never called
    # anywhere in production before Session 5; SQLiteGraphBackend was
    # constructed only in tests, so memory.stats()["graph_active"] was
    # permanently False. Wiring it here is additive/best-effort: UnifiedMemory
    # already treats a missing or failing graph backend as a clean no-op
    # (tests/test_session4b_memory_hardening.py::
    # test_graph_backend_unregistered_in_production_is_a_clean_noop), so a
    # failure to construct/register it must never block startup.
    # Session 5.25 built GraphIndexer (core/memory/graph/graph_indexer.py):
    # eligibility/extraction/sync/removal now live there, and
    # UnifiedMemory.update() -- previously blind to the graph entirely --
    # now re-syncs too, so a truth_status change (e.g. MemoryCuratorWorker's
    # resolve_contradictions(), which already calls
    # update(loser_id, {"truth_status": "deprecated"})) correctly creates or
    # removes the corresponding graph node. This defaults to
    # NullEntityExtractor (no entities/edges, memory-node only) and
    # TruthStatusEligibilityPolicy (unchanged truth_status gate) — a
    # deliberately conservative default; see the Session 5.25 Integration
    # Report for how to opt into RegexEntityExtractor. Remaining gap: the
    # graph still stays empty in a default run today, because nothing in
    # the *reachable* production path calls update() with a truth_status
    # change yet -- MemoryCuratorWorker has that logic but is not
    # instantiated/scheduled anywhere (Session 5's Technical Debt Report;
    # unchanged by this session, deliberately out of scope here too).
    # Session 5.5 — Graph Population Strategy (see Session 5.5 Architecture
    # Decision report). RegexEntityExtractor is enabled explicitly here,
    # at the composition root -- not by changing GraphIndexer's own
    # library-level default (still NullEntityExtractor, still the safe
    # choice for anyone constructing GraphIndexer directly). Population
    # additionally requires an entry to be graph-eligible in the first
    # place: write() now accepts an optional truth_status kwarg for
    # exactly this (see UnifiedMemory.write()) -- nothing calls it
    # automatically; a caller must opt in per entry.
    try:
        graph_backend = SQLiteGraphBackend()
        memory.register_graph_backend(graph_backend,
                                       entity_extractor=RegexEntityExtractor())
        log.info("GraphBackend registered (L3 index active via GraphIndexer, "
                 "RegexEntityExtractor enabled — see Session 5.5 report)")
    except Exception as e:
        log.warning(f"GraphBackend registration failed (non-fatal, graph index inactive): {e}")

    # Session 5 — Governance / EventStream Wiring.
    # Reality-audit finding: get_governance_kernel()/get_event_stream() were
    # previously only called from AbstractCognitiveWorker.__init__, and no
    # AbstractCognitiveWorker subclass is ever constructed from main.py — so
    # neither singleton was ever instantiated in the running process, and
    # Orchestrator.handle() never consulted governance or emitted events.
    # Constructing them explicitly here (rather than relying on
    # Orchestrator's default-via-getter fallback) makes that construction
    # visible in the composition root, per PI LAW 4.
    governance_kernel = get_governance_kernel()
    event_stream = get_event_stream()
    log.info(f"GovernanceKernel ready ({governance_kernel.stats()['governors']})")
    log.info("EventStream ready")

    # Step 6b: K2.1 — ExecutionRuntime (canonical execution path)
    # WorkerRegistry: static index of constructable Worker types.
    # ExecutionRuntime: constructs and invokes one Worker per unit of work.
    # MemoryCuratorWorker: first production worker, registered and wired.
    from core.runtime.worker_registry import WorkerRegistry
    from core.runtime.execution_runtime import ExecutionRuntime
    from core.workers.curator import MemoryCuratorWorker
    from core.workers.planner import PlannerWorker
    from core.workflow.runtime import WorkflowRuntime

    # Step 6a-2: K2.3 — Capability Runtime (capability/adapter/resource layer)
    # CapabilityRegistry: metadata only (what capabilities exist, which
    # adapters fulfill them) -- does not execute.
    # ResourceManager: owns Resource lifetime (K1.6 Resource Model,
    # extended). No global state, no singleton lookups (K2.3 prompt).
    # AdapterRuntime: execution -- adapter selection, fallback, failure
    # isolation, diagnostics. See K2_3_CAPABILITY_RUNTIME_REPORT.md for
    # the full design (why only LLM_COMPLETION is registered, and why
    # ModelRouterAdapter wraps rather than replaces ModelRouter).
    from core.capabilities import CapabilityRegistry, ResourceManager, AdapterRuntime, CapabilityContract, CapabilityType
    from core.capabilities.adapters.model_router_adapter import ModelRouterAdapter
    from core.capabilities.adapters.ollama_adapter import OllamaAdapter
    from core.capabilities.adapters.openai_compat_adapter import OpenAICompatAdapter

    resource_manager = ResourceManager()
    capability_registry = CapabilityRegistry()
    capability_registry.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION,
        description="Generate text from a prompt via a language model.",
        required_resources=["http-client-shared"],
    ))
    # Adapter order = attempt order (subject to health-based re-ranking).
    # ModelRouterAdapter first: preserves the bootstrap/shadow/native
    # maturity pipeline PlannerWorker's production behavior already
    # depends on (documented compatibility wrapper -- see its own
    # docstring). OllamaAdapter/OpenAICompatAdapter are the "pure"
    # capability path, tried only if the maturity-tracked path is
    # unavailable.
    capability_registry.register_adapter(
        CapabilityType.LLM_COMPLETION, ModelRouterAdapter(model_router))
    capability_registry.register_adapter(
        CapabilityType.LLM_COMPLETION, OllamaAdapter())
    capability_registry.register_adapter(
        CapabilityType.LLM_COMPLETION, OpenAICompatAdapter())

    adapter_runtime = AdapterRuntime(
        registry=capability_registry,
        resource_manager=resource_manager,
        event_stream=event_stream,
    )
    log.info(f"CapabilityRegistry ready ({capability_registry.list_capabilities()}); "
             f"AdapterRuntime ready ({capability_registry.stats()})")

    worker_registry = WorkerRegistry()

    # Register all known worker types — composition root is the only
    # place workers are registered (no auto-discovery, no magic).
    worker_registry.register(MemoryCuratorWorker)

    # K2.2 — PlannerWorker needs domain dependencies (modules, context,
    # memory) beyond the governance/event_stream every worker gets by
    # default. WorkerRegistry.register()'s constructor_kwargs parameter
    # exists specifically for this case (see its own docstring, which
    # already names PlannerWorker as the example). context_memory is the
    # same module-level singleton Orchestrator itself is constructed with
    # below, so PlannerWorker's context.save() and Orchestrator.context
    # stay the same object, not two divergent ContextMemory instances.
    #
    # K2.3 — adapter_runtime replaces model_router here: PlannerWorker no
    # longer depends on the concrete ModelRouter class directly ("Workers
    # must never know concrete providers. Workers only know
    # Capabilities." -- K2.3 prompt). ModelRouter still runs underneath,
    # wrapped inside ModelRouterAdapter above -- nothing about its
    # bootstrap/shadow/native behavior changed, only who calls it.
    worker_registry.register(PlannerWorker, constructor_kwargs={
        "modules": modules,
        "context_memory": context_memory,
        "adapter_runtime": adapter_runtime,
        "memory": memory,
    })
    log.info(f"WorkerRegistry ready ({worker_registry.list_types()})")

    execution_runtime = ExecutionRuntime(
        worker_registry=worker_registry,
        governance=governance_kernel,
        event_stream=event_stream,
    )
    log.info("ExecutionRuntime ready")

    # Step 6c: K2.2 — WorkflowRuntime (canonical workflow coordinator)
    # Coordinates a DAG of ExecutionRuntime invocations. Orchestrator.handle()
    # wraps every query in the single-node "planner" workflow
    # (core/workflow/definition.py::build_planner_workflow) and delegates
    # through this, replacing the inline classify->dispatch->merge flow as
    # the primary production path. See K2.2 Cutover Report for the full
    # before/after chain and the reachability audit that verifies this.
    workflow_runtime = WorkflowRuntime(
        execution_runtime=execution_runtime,
        event_stream=event_stream,
    )
    log.info("WorkflowRuntime ready")

    # Wire MemoryCuratorWorker to UnifiedMemory for hook integration.
    # K2.1: this instance is used for hook registration only.
    # ExecutionRuntime creates fresh ephemeral instances for each invoke().
    # The hook-registered instance and the ephemeral instances are separate
    # — hooks are wired via HookRegistry at the UnifiedMemory level.
    try:
        curator_for_hooks = MemoryCuratorWorker(
            governance=governance_kernel,
            event_stream=event_stream,
        )
        curator_for_hooks.register(memory)
        log.info("MemoryCuratorWorker hooks registered with UnifiedMemory")
    except Exception as e:
        log.warning(f"MemoryCuratorWorker hook registration failed (non-fatal): {e}")

    orchestrator = Orchestrator(modules, context_memory, model_router,
                                 memory=memory,
                                 governance=governance_kernel,
                                 event_stream=event_stream,
                                 execution_runtime=execution_runtime,
                                 workflow_runtime=workflow_runtime)
    log.info("Orchestrator ready (WorkflowRuntime: production execution owner)")

    # Step 7: Scheduler
    from learning.scheduler import Scheduler
    scheduler = Scheduler(modules)

    # Step 8: Wire API
    from interface.api import app, setup as api_setup
    api_setup(orchestrator, scheduler)

    # Step 9: Emit brain.ready
    from core.event_bus import bus
    await bus.emit("brain.ready", {
        "modules": list(modules.keys()),
        "version": brain_version_manager.brain_version,
    })

    # Step 10: System tray
    try:
        from interface.tray import start as tray_start
        tray_start(orchestrator)
    except Exception as e:
        log.debug(f"Tray: {e}")

    # Step 11: Voice
    if config.get("global.voice_enabled", False):
        try:
            from interface.voice import start as voice_start
            def _handle_voice(q):
                asyncio.create_task(orchestrator.handle(q))
            voice_start(_handle_voice)
        except Exception as e:
            log.debug(f"Voice: {e}")

    # Step 12: Run
    port = int(config.get("global.web_ui_port") or 7437)
    log.info(f"Web UI  → http://localhost:{port}")
    log.info(f"API     → http://localhost:{port}/docs")
    log.info(f"Stream  → POST http://localhost:{port}/query  {{stream: true}}")
    log.info(f"Events  → GET  http://localhost:{port}/events")
    log.info("OCBrain v4.1 is ready (K2.3: CapabilityRuntime LIVE).\n")

    uv_config = uvicorn.Config(
        app, host="127.0.0.1", port=port,
        log_level=str(config.get("global.log_level") or "info").lower(),
        loop="asyncio",
    )
    server = uvicorn.Server(uv_config)
    try:
        await asyncio.gather(server.serve(), scheduler.start())
    finally:
        # Session 5 — Shutdown Validation.
        # Reality-audit finding: orchestrator.close() (stops health_monitor,
        # cancels Orchestrator's own background tasks) was never called from
        # anywhere; asyncio.run() tearing down the loop on exit cancelled
        # those tasks abruptly instead of gracefully. This runs on every exit
        # path from main(): normal return, exception, or a
        # KeyboardInterrupt/SystemExit propagating up through
        # asyncio.gather() above.
        log.info("Shutting down Orchestrator...")
        await orchestrator.close()


def _handle_sigterm(sig, frame):
    log.info("Shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
    finally:
        asyncio.run(state_store.stop())
