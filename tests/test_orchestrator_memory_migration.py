"""
tests/test_orchestrator_memory_migration.py — Session 4 Test Suite

Verifies that UnifiedMemory has been activated as the production memory
owner of core.orchestrator.Orchestrator, replacing the legacy
MemoryVault / HybridRetriever construction that previously lived in
Orchestrator.__init__.

Reality-audit context (see Session 4 report "Files Modified" section):
MemoryVault/HybridRetriever were constructed in Orchestrator.__init__ but
were NEVER invoked anywhere inside Orchestrator.handle() — not in this
commit, not in the first commit of the repository. There was no live
".add_entry()" call to mechanically replace. This suite therefore verifies
the two things this session actually changed:

  1. The dead MemoryVault/HybridRetriever construction is gone, replaced
     by required constructor injection of UnifiedMemory.
  2. Orchestrator.handle() now performs exactly one production write to
     UnifiedMemory per request (the capability the prior wiring never
     provided), without altering the response returned to the caller.

Test categories (matching the Session 4 prompt's TESTS REQUIRED section):
  - Orchestrator   : constructor injection, no MemoryVault, write() called
                      exactly once, retrieval still works, responses
                      unchanged.
  - Runtime        : writes actually reach UnifiedMemory end-to-end
                      (LayerRouter, L1 storage, archive all exercised).
  - AST            : structural verification of core/orchestrator.py.
  - Out-of-scope   : confirms Session 4 did not touch systems explicitly
                      excluded by the prompt (web learning, UnifiedMemory
                      internals).
"""
import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.context import ContextMemory
from core.model_router import RouteResult
from core.orchestrator import Orchestrator
from core.memory.unified_memory import UnifiedMemory

ORCHESTRATOR_SRC_PATH = Path(__file__).parent.parent / "core" / "orchestrator.py"


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _make_router(answer: str = "mocked answer") -> MagicMock:
    """A router whose .route() is awaitable and returns a fixed RouteResult,
    so handle() exercises the real classify -> dispatch -> merge path
    without touching a real LLM provider."""
    router = MagicMock()
    router.route = AsyncMock(return_value=RouteResult(answer=answer, source="mock"))
    return router


def _make_context() -> MagicMock:
    """A spec'd mock so only real ContextMemory methods can be called,
    without touching the real on-disk context.sqlite."""
    return MagicMock(spec=ContextMemory)


# ──────────────────────────────────────────────────────────────────────────
# 1. ORCHESTRATOR — constructor injection / dead-code removal
# ──────────────────────────────────────────────────────────────────────────

class TestOrchestratorConstructorInjection:

    def test_constructor_requires_unified_memory(self):
        """Orchestrator.__init__ must accept a UnifiedMemory, with no
        internal default — it must be supplied by the caller (composition
        root), matching the injection pattern already established by
        ContextAssemblyEngine / RetrievalFusionEngine in Session 3A/3B."""
        sig = inspect.signature(Orchestrator.__init__)
        assert "memory" in sig.parameters
        assert sig.parameters["memory"].default is inspect.Parameter.empty

    def test_memory_vault_never_instantiated_by_orchestrator(self):
        """Constructing an Orchestrator must never touch MemoryVault.__init__."""
        with patch(
            "core.memory.mem_vault.MemoryVault.__init__",
            side_effect=AssertionError("MemoryVault must not be instantiated by Orchestrator"),
        ):
            mock_memory = AsyncMock(spec=UnifiedMemory)
            orch = Orchestrator(modules={}, context=_make_context(),
                                 router=_make_router(), memory=mock_memory)
            assert orch is not None

    def test_orchestrator_has_no_vault_or_retriever_attributes(self):
        mock_memory = AsyncMock(spec=UnifiedMemory)
        orch = Orchestrator(modules={}, context=_make_context(),
                             router=_make_router(), memory=mock_memory)
        assert not hasattr(orch, "vault")
        assert not hasattr(orch, "retriever")
        assert orch.memory is mock_memory


# ──────────────────────────────────────────────────────────────────────────
# 2. ORCHESTRATOR — write() called exactly once, retrieval still works,
#    responses unchanged, write failures never surface to the caller
# ──────────────────────────────────────────────────────────────────────────

class TestOrchestratorHandleWritesToUnifiedMemory:

    @pytest.mark.asyncio
    async def test_write_called_exactly_once_per_handle(self):
        mock_memory = AsyncMock(spec=UnifiedMemory)
        orch = Orchestrator(modules={}, context=_make_context(),
                             router=_make_router("the answer"), memory=mock_memory)
        try:
            answer = await orch.handle("what is OCBrain?")
        finally:
            await orch.close()

        mock_memory.write.assert_awaited_once()
        _, kwargs = mock_memory.write.call_args
        assert kwargs["content_type"] == "interaction"
        assert "what is OCBrain?" in kwargs["content"]
        assert "the answer" in kwargs["content"]
        # Response unchanged: single classified module -> merger pass-through.
        assert answer == "the answer"

    @pytest.mark.asyncio
    async def test_retrieval_still_goes_through_context_assembler(self):
        """Session 3B's UnifiedMemory-backed retrieval path is untouched by
        this session; Orchestrator must still call it exactly once."""
        mock_memory = AsyncMock(spec=UnifiedMemory)
        orch = Orchestrator(modules={}, context=_make_context(),
                             router=_make_router(), memory=mock_memory)
        with patch(
            "core.orchestrator.context_assembler.assemble_context",
            new=AsyncMock(return_value="some assembled context"),
        ) as mock_assemble:
            try:
                await orch.handle("explain the graph engine")
            finally:
                await orch.close()
            mock_assemble.assert_awaited_once_with("explain the graph engine")

    @pytest.mark.asyncio
    async def test_memory_write_failure_does_not_break_response(self):
        """A UnifiedMemory write failure must never turn a successful
        answer into the generic internal-error response — storage
        ownership changed, user-facing behaviour must not."""
        mock_memory = AsyncMock(spec=UnifiedMemory)
        mock_memory.write.side_effect = RuntimeError("disk full")
        orch = Orchestrator(modules={}, context=_make_context(),
                             router=_make_router("still the answer"), memory=mock_memory)
        try:
            answer = await orch.handle("does this survive a memory failure?")
        finally:
            await orch.close()

        assert answer == "still the answer"
        assert "Sorry, I encountered an internal error" not in answer
        mock_memory.write.assert_awaited_once()


# ──────────────────────────────────────────────────────────────────────────
# 3. RUNTIME — end-to-end with a real UnifiedMemory: LayerRouter, L1
#    storage and archive are actually exercised by a live request
# ──────────────────────────────────────────────────────────────────────────

class TestRuntimeMemoryOwnership:

    @pytest.mark.asyncio
    async def test_real_unified_memory_receives_and_persists_interaction(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "session4_memory"))
        orch = Orchestrator(modules={}, context=_make_context(),
                             router=_make_router("xqzPERSISTENCEtoken99"), memory=memory)
        try:
            answer = await orch.handle("a query about durable interaction persistence")
        finally:
            await orch.close()

        assert answer == "xqzPERSISTENCEtoken99"

        # LayerRouter must have routed content_type="interaction" -> L1 (episodic).
        l1_entries = await memory.get_layer("l1")
        assert len(l1_entries) == 1
        assert l1_entries[0].metadata.get("content_type") == "interaction"
        assert "xqzPERSISTENCEtoken99" in l1_entries[0].content
        assert l1_entries[0].source == "orchestrator"

        # Hybrid search (FTS5 over L1) must surface the freshly written entry.
        results = await memory.search("xqzPERSISTENCEtoken99", limit=5)
        assert any("xqzPERSISTENCEtoken99" in r.entry.content for r in results)

        # L4 archive event must have been created for the write (the
        # try/except inside UnifiedMemory.write around archive.append_event
        # is non-blocking — confirm it actually succeeded, not just that
        # it didn't crash).
        full_stats = await memory.full_stats()
        assert full_stats["writes"] == 1
        assert full_stats["l4"]["total_events"] >= 1

    @pytest.mark.asyncio
    async def test_production_runtime_never_creates_vault_json(self, tmp_path):
        """A live request must never create MemoryVault's vault.json —
        confirms MemoryVault no longer participates in production runtime."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "session4_memory2"))
        orch = Orchestrator(modules={}, context=_make_context(),
                             router=_make_router(), memory=memory)
        try:
            await orch.handle("a fresh query for a fresh vault check")
        finally:
            await orch.close()

        assert not (tmp_path / "vault.json").exists()
        assert not (tmp_path / "session4_memory2" / "vault.json").exists()


# ──────────────────────────────────────────────────────────────────────────
# 4. AST — structural verification of core/orchestrator.py
# ──────────────────────────────────────────────────────────────────────────

class TestOrchestratorAST:

    @classmethod
    def setup_class(cls):
        cls.source = ORCHESTRATOR_SRC_PATH.read_text()
        cls.tree = ast.parse(cls.source, filename=str(ORCHESTRATOR_SRC_PATH))

    def _all_imported_names(self):
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    names.add(alias.asname or alias.name)
                    names.add(f"{module}.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
        return names

    def test_no_memory_vault_import(self):
        imported = self._all_imported_names()
        assert "MemoryVault" not in imported
        assert not any("mem_vault" in name for name in imported)

    def test_no_hybrid_retriever_import(self):
        imported = self._all_imported_names()
        assert "HybridRetriever" not in imported
        assert not any("hybrid_retrieval" in name for name in imported)

    def test_no_memory_vault_or_hybrid_retriever_construction(self):
        called_names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called_names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called_names.add(func.attr)
        assert "MemoryVault" not in called_names
        assert "HybridRetriever" not in called_names

    def test_constructor_injection_structurally_present(self):
        init_def = next(
            node for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        arg_names = [a.arg for a in init_def.args.args]
        assert "memory" in arg_names

    def test_unified_memory_is_imported(self):
        imported = self._all_imported_names()
        assert "UnifiedMemory" in imported

    def test_no_get_unified_memory_call_inside_handle(self):
        """'No get_unified_memory() inside methods' — the per-request
        handle() method must use the injected self.memory, never fetch
        the singleton itself."""
        handle_def = next(
            node for node in ast.walk(self.tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle"
        )
        for node in ast.walk(handle_def):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "get_unified_memory"


# ──────────────────────────────────────────────────────────────────────────
# 5. OUT-OF-SCOPE SYSTEMS — confirm Session 4 stayed inside its boundary
# ──────────────────────────────────────────────────────────────────────────

class TestSession4StayedInScope:

    def test_web_learning_pipeline_still_uses_memory_vault(self):
        """Session 4 explicitly excludes web learning from migration; its
        MemoryVault usage is intentionally untouched until a future
        session. This is not a regression — it is the documented boundary."""
        from core.web_learning import pipeline
        src = inspect.getsource(pipeline)
        assert "MemoryVault" in src

    def test_unified_memory_public_api_unchanged_by_this_session(self):
        """Spot-check that UnifiedMemory's write/search signatures (the
        only surfaces this session depends on) are exactly what Session 3A
        left them as — this session must not have modified them."""
        write_sig = inspect.signature(UnifiedMemory.write)
        assert "content" in write_sig.parameters
        assert "content_type" in write_sig.parameters
        search_sig = inspect.signature(UnifiedMemory.search)
        assert "query" in search_sig.parameters
