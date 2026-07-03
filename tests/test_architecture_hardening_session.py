"""
tests/test_architecture_hardening_session.py — Architecture Hardening Session

Covers three categories of change made during this session:

  1. Graph-as-index architectural decision: the graph is an orthogonal
     index over UnifiedMemory's canonical entries (comparable to the
     vector/BM25/FTS5 indexes), gated purely by
     KnowledgeEntry.is_graph_eligible() -- never by entry.layer. Entities
     stay in their appropriate memory layer (L2); LAYERS["l3"] was
     corrected to describe Procedural Memory, matching
     OCBRAIN_FUTURE_ARCHITECTURE.md's own definition of the existing
     5-layer system, not "Graph Memory" as the code previously (and
     inconsistently with that authoritative document) claimed.

  2. A newly-discovered L0 cache-coherence bug: graph indexing was
     previously gated to layer=="l3", a write target nothing in
     production ever actually used -- so the graph-indexing block's own
     self._storage.update() call (setting graph_node_id) had never
     actually executed against a real L0-cached entry. Removing the
     layer gate made this reachable for the first time, immediately
     exposing that L0 was being populated BEFORE that update ran, so
     read() could return an entry missing graph_node_id even though it
     was correctly persisted and the graph node genuinely existed. Fixed
     by moving L0 population to after every write()-time storage
     mutation completes.

  3. Legacy runtime removal, informed by the composition root review:
     - HealthMonitor._check_memory() and SelfModel._detect_memory() both
       replaced MemoryVault() with real UnifiedMemory-based checks
       (health_monitor's path is LIVE -- confirmed via the composition
       root review that _start_background_engines() does call
       health_monitor.start() -- so this was not dead code, unlike the
       self_model.py path, which remains unreachable but was fixed for
       consistency and correctness).
     - SelfModel._detect_retrieval() replaced a find_spec() check against
       the orphaned hybrid_retrieval.py file with a check against
       UnifiedMemory.search, the capability's real, live home since
       Session 3B.
     - IterationBudget's dead invocation (constructed and .check()'d
       exactly once per handle() call, which can never exceed any
       max_iterations >= 1 since nothing loops) was removed from
       Orchestrator; the class itself was left intact since it has its
       own legitimate, passing, independent test coverage.
     - The legacy MemoryConsolidator background loop (operating hourly on
       cognitive_vault, a singleton fully disconnected from UnifiedMemory
       since Session 4) was stopped rather than migrated -- migrating it
       would mean building MemoryCuratorWorker's v4.3.6 active-memory-
       improvement logic prematurely, explicitly out of scope.
"""
import ast
import asyncio
import inspect
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from core.memory.unified_memory import UnifiedMemory, LayerRouter
from core.memory.knowledge_entry import LAYERS
from core.memory.backends.sqlite_graph import SQLiteGraphBackend

ORCHESTRATOR_SRC = Path(__file__).parent.parent / "core" / "orchestrator.py"
UNIFIED_MEMORY_SRC = Path(__file__).parent.parent / "core" / "memory" / "unified_memory.py"


def _mem(tmp_path, name: str) -> UnifiedMemory:
    return UnifiedMemory(db_prefix=str(tmp_path / name))


# ──────────────────────────────────────────────────────────────────────────
# 1. GRAPH-AS-INDEX ARCHITECTURAL DECISION
# ──────────────────────────────────────────────────────────────────────────

class TestGraphAsIndexDecision:

    def test_l3_no_longer_described_as_graph_memory(self):
        """LAYERS["l3"] must match OCBRAIN_FUTURE_ARCHITECTURE.md's own
        description of the existing (already-built) 5-layer system:
        'L0 LRU -> L1 SQLite+FTS5 -> L2 BM25+embeddings -> L3 procedural
        -> L4 archive' -- L3 is procedural, not graph."""
        assert "graph" not in LAYERS["l3"].lower()
        assert "procedural" in LAYERS["l3"].lower()

    def test_entity_still_routes_to_l2_not_l3(self):
        """Entities belong in their appropriate memory layer (semantic
        memory, L2) -- NOT a special graph layer. This is unchanged by
        the graph-as-index decision; only the reasoning/comment changed."""
        assert LayerRouter.CONTENT_TYPE_ROUTES["entity"] == "l2"

    def test_graph_indexing_gate_has_no_layer_dependency(self):
        """AST check: the graph-indexing block inside write() must not
        reference entry.layer or a "l3" comparison anywhere in its
        condition -- graph eligibility is the only gate."""
        tree = ast.parse(UNIFIED_MEMORY_SRC.read_text())
        write_def = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "write"
        )
        src = ast.get_source_segment(UNIFIED_MEMORY_SRC.read_text(), write_def)
        # Locate the graph-indexing if-block specifically (contains add_node)
        assert "self._graph.add_node" in src
        graph_block_start = src.index("if self._graph and entry.is_graph_eligible()")
        # The condition itself (up to the colon) must not mention layer/l3
        condition_end = src.index(":", graph_block_start)
        condition = src[graph_block_start:condition_end]
        assert "layer" not in condition
        assert '"l3"' not in condition

    @pytest.mark.asyncio
    async def test_l1_entry_can_now_be_graph_indexed(self, tmp_path):
        """The core behavioral proof: an L1 (episodic) entry that is
        graph-eligible now gets indexed into the graph -- something that
        was structurally impossible before this session (graph indexing
        required layer=="l3", and nothing routes to l3 in production)."""
        memory = _mem(tmp_path, "gai_a")
        graph = SQLiteGraphBackend(str(tmp_path / "gai_a_graph.db"))
        memory.register_graph_backend(graph)

        with patch("core.memory.knowledge_entry.GRAPH_ELIGIBLE_STATUSES",
                   {"unknown", "verified", "candidate"}):
            entry_id = await memory.write(
                content="an L1 entry that should be graph-indexed",
                content_type="interaction",   # routes to l1, not l3
            )
        entry = await memory.read(entry_id)
        assert entry.layer == "l1"
        assert entry.graph_node_id is not None
        assert entry.graph_node_id.startswith("mem:")

    @pytest.mark.asyncio
    async def test_l2_entry_can_be_graph_indexed(self, tmp_path):
        """Same proof for L2 (semantic memory, e.g. entities/facts) --
        confirming this is genuinely layer-independent, not a special
        case for l1 alone."""
        memory = _mem(tmp_path, "gai_b")
        graph = SQLiteGraphBackend(str(tmp_path / "gai_b_graph.db"))
        memory.register_graph_backend(graph)

        with patch("core.memory.knowledge_entry.GRAPH_ELIGIBLE_STATUSES",
                   {"unknown", "verified", "candidate"}):
            entry_id = await memory.write(
                content="Alice works at Acme Corp",
                content_type="entity",   # routes to l2
            )
        entry = await memory.read(entry_id)
        assert entry.layer == "l2"
        assert entry.graph_node_id is not None

    @pytest.mark.asyncio
    async def test_non_eligible_entry_is_not_graph_indexed_regardless_of_layer(self, tmp_path):
        """The gate is is_graph_eligible(), which is real and still
        enforced -- this isn't "index everything unconditionally"."""
        memory = _mem(tmp_path, "gai_c")
        graph = SQLiteGraphBackend(str(tmp_path / "gai_c_graph.db"))
        memory.register_graph_backend(graph)

        # truth_status defaults to "unknown", NOT in GRAPH_ELIGIBLE_STATUSES
        # by default ({"verified", "candidate"}) -- no patching this time.
        entry_id = await memory.write(content="not graph eligible by default",
                                       content_type="interaction")
        entry = await memory.read(entry_id)
        assert entry.graph_node_id is None

    def test_no_graphlayer_or_graph_backend_class_introduced(self):
        """Explicit constraint from the architectural decision: do NOT
        introduce GraphLayer, L3 storage backend, GraphMemory backend, or
        GraphRepository classes. The graph remains only an index."""
        import core.memory.unified_memory as um_mod
        forbidden_names = {"GraphLayer", "GraphMemory", "GraphRepository",
                            "L3StorageBackend"}
        defined_names = {name for name, obj in vars(um_mod).items()
                          if inspect.isclass(obj)}
        assert not (forbidden_names & defined_names)


# ──────────────────────────────────────────────────────────────────────────
# 2. L0 CACHE COHERENCE FOR graph_node_id (newly discovered this session)
# ──────────────────────────────────────────────────────────────────────────

class TestL0CoherenceForGraphNodeId:

    @pytest.mark.asyncio
    async def test_l0_cached_read_matches_storage_after_graph_indexing(self, tmp_path):
        """The exact bug found this session: read() (which checks L0
        first) must return the same graph_node_id as
        memory._storage.read() (which bypasses L0) -- both must reflect
        the fully-completed write(), including the graph-indexing block's
        own separate storage.update() call."""
        memory = _mem(tmp_path, "l0gni_a")
        graph = SQLiteGraphBackend(str(tmp_path / "l0gni_a_graph.db"))
        memory.register_graph_backend(graph)

        with patch("core.memory.knowledge_entry.GRAPH_ELIGIBLE_STATUSES",
                   {"unknown", "verified", "candidate"}):
            entry_id = await memory.write(content="coherence check content",
                                           content_type="interaction")

        via_cache = await memory.read(entry_id)     # L0 first
        via_storage = await memory._storage.read(entry_id)  # bypasses L0

        assert via_cache.graph_node_id == via_storage.graph_node_id
        assert via_cache.graph_node_id is not None

    @pytest.mark.asyncio
    async def test_l0_population_happens_after_all_storage_mutations(self, tmp_path):
        """Structural proof via call-order: L0 must not be populated until
        after the graph-indexing block's storage.update() call, for any
        entry that actually goes through graph indexing."""
        memory = _mem(tmp_path, "l0gni_b")
        graph = SQLiteGraphBackend(str(tmp_path / "l0gni_b_graph.db"))
        memory.register_graph_backend(graph)

        call_order = []
        real_l0_put = memory._l0.put
        real_storage_update = memory._storage.update

        def tracking_put(entry_id, entry):
            call_order.append("l0_put")
            return real_l0_put(entry_id, entry)

        async def tracking_update(entry_id, delta):
            call_order.append("storage_update")
            return await real_storage_update(entry_id, delta)

        memory._l0.put = tracking_put
        memory._storage.update = tracking_update

        with patch("core.memory.knowledge_entry.GRAPH_ELIGIBLE_STATUSES",
                   {"unknown", "verified", "candidate"}):
            await memory.write(content="call order check", content_type="interaction")

        assert "storage_update" in call_order
        assert "l0_put" in call_order
        assert call_order.index("storage_update") < call_order.index("l0_put"), \
            "L0 must be populated AFTER the graph-indexing storage.update(), not before"

    @pytest.mark.asyncio
    async def test_regression_created_at_coherence_still_holds(self, tmp_path):
        """Session 4C's original created_at coherence fix must still hold
        after this session's reordering -- confirms the reorder didn't
        silently reintroduce that bug while fixing the graph_node_id one."""
        memory = _mem(tmp_path, "l0gni_c")
        iid = "interaction:l0gni_c_fixed_id"
        await memory.write(content="first answer", content_type="interaction", entry_id=iid)
        await asyncio.sleep(0.05)
        await memory.write(content="second answer", content_type="interaction", entry_id=iid)

        via_cache = await memory.read(iid)
        via_storage = await memory._storage.read(iid)
        assert via_cache.created_at == via_storage.created_at

    @pytest.mark.asyncio
    async def test_phantom_l0_entry_still_prevented_on_storage_failure(self, tmp_path):
        """Session 4C's original phantom-entry-on-failure fix must also
        still hold after this session's reordering."""
        class _FailingStorage:
            def __init__(self, real):
                self._real = real
            async def write(self, entry):
                raise RuntimeError("simulated failure")
            def __getattr__(self, name):
                return getattr(self._real, name)

        from core.memory.backends.sqlite_storage import SQLiteStorageBackend
        real_storage = SQLiteStorageBackend(str(tmp_path / "l0gni_d" / "unified.db"))
        memory = UnifiedMemory(storage=_FailingStorage(real_storage))

        with pytest.raises(RuntimeError):
            await memory.write(content="never persisted", content_type="interaction",
                                entry_id="interaction:l0gni_d")
        assert memory._l0.get("interaction:l0gni_d") is None


# ──────────────────────────────────────────────────────────────────────────
# 3. LEGACY RUNTIME REMOVAL
# ──────────────────────────────────────────────────────────────────────────

class TestLegacyRuntimeRemoval:

    def test_health_monitor_no_longer_references_memory_vault(self):
        import core.meta.health_monitor as hm_mod
        src = inspect.getsource(hm_mod)
        assert "MemoryVault()" not in src
        assert "from core.memory.mem_vault import MemoryVault" not in src

    def test_self_model_no_longer_references_memory_vault(self):
        import core.meta.self_model as sm_mod
        src = inspect.getsource(sm_mod)
        assert "MemoryVault()" not in src
        assert "from core.memory.mem_vault import MemoryVault" not in src

    def test_health_monitor_check_memory_uses_real_unified_memory_stats(self):
        from core.meta.health_monitor import HealthMonitor
        src = inspect.getsource(HealthMonitor._check_memory)
        assert "get_unified_memory" in src
        assert "stats()" in src

    def test_health_monitor_check_is_not_hardcoded(self):
        """Confirm the fix isn't just a different hardcoded constant --
        the source must branch on a real condition, not always write 1.0
        unconditionally."""
        from core.meta.health_monitor import HealthMonitor
        src = inspect.getsource(HealthMonitor._check_memory)
        assert "if healthy" in src or "1.0 if" in src

    @pytest.mark.asyncio
    async def test_health_monitor_check_memory_runs_without_error(self):
        """End-to-end: the rewritten method must actually work against the
        real production UnifiedMemory singleton."""
        from core.meta.health_monitor import HealthMonitor
        from core.meta.self_model import SELF_MODEL
        hm = HealthMonitor()
        hm._check_memory()  # synchronous, must not raise
        assert "memory_integrity" in SELF_MODEL["health"]
        assert SELF_MODEL["health"]["memory_integrity"] in (0.0, 1.0)

    def test_self_model_capability_detection_no_longer_tautological(self):
        """The original bug: len(vault.entries) >= 0 is always True, and
        the health value was an explicitly-labeled placeholder. Checked
        against the AST body (not raw source text), so a docstring that
        legitimately explains the old bug in prose can't produce a false
        failure."""
        from core.meta.self_model import CapabilityDetector
        func = CapabilityDetector._detect_memory
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
        func_def = tree.body[0]
        body_without_docstring = func_def.body[1:] if (
            func_def.body and isinstance(func_def.body[0], ast.Expr)
            and isinstance(func_def.body[0].value, ast.Constant)
        ) else func_def.body
        body_src = "\n".join(ast.unparse(stmt) for stmt in body_without_docstring)
        assert "vault.entries" not in body_src
        assert "Placeholder" not in body_src

    def test_self_model_retrieval_detection_checks_real_capability(self):
        """The original bug: find_spec() on the orphaned hybrid_retrieval.py
        file, not the real live capability. Fix checks UnifiedMemory.
        Confirmed structurally (no import of find_spec anywhere in the
        module) rather than by substring-matching one method's source,
        since the fix's own docstring legitimately mentions "find_spec()"
        in prose explaining what was wrong."""
        import core.meta.self_model as sm_mod
        from core.meta.self_model import CapabilityDetector
        assert "from importlib.util import find_spec" not in inspect.getsource(sm_mod)
        assert "UnifiedMemory" in inspect.getsource(CapabilityDetector._detect_retrieval)

    def test_self_model_detection_runs_without_error(self):
        """End-to-end: both rewritten detectors must actually work."""
        from core.meta.self_model import CapabilityDetector, SELF_MODEL
        CapabilityDetector._detect_memory()
        CapabilityDetector._detect_retrieval()
        assert isinstance(SELF_MODEL["capabilities"]["memory_system"], bool)
        assert isinstance(SELF_MODEL["capabilities"]["hybrid_retrieval"], bool)
        assert SELF_MODEL["capabilities"]["hybrid_retrieval"] is True  # UnifiedMemory.search exists

    def test_iteration_budget_no_longer_constructed_in_orchestrator(self):
        tree = ast.parse(ORCHESTRATOR_SRC.read_text())
        called_names = {
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "IterationBudget" not in called_names

    def test_iteration_budget_import_removed_but_backpressure_guard_kept(self):
        tree = ast.parse(ORCHESTRATOR_SRC.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
        assert "IterationBudget" not in imported
        assert "BackpressureGuard" in imported

    def test_iteration_budget_class_itself_still_exists_and_is_tested_elsewhere(self):
        """We removed the dead USAGE, not the class -- it has its own
        legitimate, independent test coverage (test_runtime_limits.py)
        and may still be useful as a primitive for future orchestration
        integration."""
        from core.runtime.limits import IterationBudget
        budget = IterationBudget(max_steps=2)
        budget.check()
        budget.check()
        with pytest.raises(RuntimeError):
            budget.check()

    def test_max_iterations_parameter_preserved_for_api_compatibility(self):
        """Public API preserved even though the parameter is currently
        unenforced -- multiple existing call sites pass it by name.
        Checked via AST rather than inspect.signature(), since
        async_trace_function's wrapper doesn't use functools.wraps and
        inspect.signature() on the decorated method would only see
        (*args, **kwargs)."""
        tree = ast.parse(ORCHESTRATOR_SRC.read_text())
        handle_def = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle"
        )
        arg_names = [a.arg for a in handle_def.args.args]
        assert "max_iterations" in arg_names
        defaults = handle_def.args.defaults
        # max_iterations is the last positional arg with a default of 5
        assert ast.unparse(defaults[-1]) == "5"

    def test_consolidator_no_longer_imported_by_orchestrator(self):
        tree = ast.parse(ORCHESTRATOR_SRC.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
        assert "consolidator" not in imported

    def test_consolidator_not_started_by_orchestrator_lifecycle(self):
        src = ORCHESTRATOR_SRC.read_text()
        assert "consolidator.start()" not in src
        assert "consolidator.stop()" not in src

    @pytest.mark.asyncio
    async def test_orchestrator_construction_no_longer_touches_cognitive_vault_file(self, tmp_path):
        """End-to-end proof: constructing and closing an Orchestrator must
        not mutate cognitive_vault's on-disk file anymore -- this is the
        exact incidental side effect that required repeated git checkout
        cleanup throughout Sessions 4/4B/4C."""
        from unittest.mock import AsyncMock, MagicMock
        from core.context import ContextMemory
        from core.model_router import RouteResult
        from core.orchestrator import Orchestrator
        import core.memory.cognitive_vault as cv_mod

        vault_path = Path(cv_mod.cognitive_vault._get_path())
        before = vault_path.read_bytes() if vault_path.exists() else None

        memory = _mem(tmp_path, "no_cv_touch")
        router = MagicMock()
        router.route = AsyncMock(return_value=RouteResult(answer="ans", source="mock"))
        orch = Orchestrator(modules={}, context=MagicMock(spec=ContextMemory),
                             router=router, memory=memory)
        await asyncio.sleep(0.05)   # let any background task get a chance to run
        try:
            await orch.handle("does this touch cognitive_vault")
        finally:
            await orch.close()
        await asyncio.sleep(0.05)

        after = vault_path.read_bytes() if vault_path.exists() else None
        assert before == after, "cognitive_vault file must not be touched by Orchestrator anymore"

    def test_health_monitor_still_starts_and_stops_normally(self):
        """We stopped consolidator specifically -- health_monitor itself
        (which now does something real) must be unaffected."""
        src = ORCHESTRATOR_SRC.read_text()
        assert "health_monitor.start()" in src
        assert "health_monitor.stop()" in src
