"""
tests/test_context_scope_security.py — CTX-SCOPE-001 security regression.

Permanent regression capturing a verified scope gap in
core/context.py::ContextMemory, surfaced during the cache-isolation /
ContextMemory path audit. See:
    docs/research/context-engineering/context-authority-threat-model.md
    (finding CTX-SCOPE-001)
    docs/research/context-engineering/context-memory-path-audit.md
    docs/Bugs Hunt & fix reports/CONTEXT_ISOLATION_CALLER_AUDIT_SEP2026.md
    docs/reports/context-compiler-remediation-register.md (REM-006)

STATUS: the mechanism (save()/last_n()/format_for_prompt(), backed by a
real `scope` column on `turns`, prompt cache keyed on (n, scope)) landed
first. PR #14 (`fix/ctx-scope-001-caller-wiring`, merged into `main`
Sept 13, 2026) then wired every call site the Sept 7 Context Isolation
Caller Audit named live: core/workers/planner.py:218 (write) and its
_dispatch_module() payload/fallback, the interface/api.py:381
_save_context_background() write, and interface/api.py's direct
stream_route() call in the single-module streaming path -- proven by
that PR's own tests in tests/test_planner_worker.py::
TestCtxScope001PlannerCallerWiring, tests/test_model_router.py, and
tests/test_api_context_scope.py, not duplicated here.

This session found and closed two further live gaps outside that
audit's scope, folded into CTX-SCOPE-001 rather than given separate
IDs (both proven below, since neither is covered by PR #14's tests):

  - boost_module() had no scope parameter at all; its live caller is
    core/classifier.py:45's label(), reached from interface/api.py:304.
  - set_long_term_memories_string()/set_long_term_memories() wrote to a
    single process-global field injected into EVERY caller's prompt
    unconditionally, regardless of what scope (if any) that caller
    passed to format_for_prompt() -- live via core/workers/planner.py's
    PlannerWorker (the same canonical K4.2 worker PR #14 already
    confirmed live for the :218 write). Both now store per-scope,
    mirroring save()'s own convention. See
    docs/architecture/decisions/ADR_CTX_01_LONG_TERM_MEMORY_SCOPE_STORAGE.md.

`entities`/get_entity() is deliberately untouched: its only caller is
the confirmed-dead modules/*.py hierarchy (audit row 8) -- tracked, not
fixed, per explicit decision not to add schema/API surface for a
subsystem nothing live reaches. core/workers/capability_executor.py's
context="" payload is also deliberately untouched, matching PR #14's
own explicit reasoning for the same call site (audit row 6: safe today
by accident, not by design; not one of the confirmed live sites).

NOT CLOSED YET, and should not be read as such despite KNOWN_ISSUES.md
having said so before this session found the two gaps above: this file
proves the mechanism is real and every known live path uses it. It does
not yet prove concurrency-race safety, cross-process behavior, retry/
checkpoint/resume/replay semantics, or resistance to adversarial
confused-deputy scope substitution -- tracked separately, not silently
assumed here.

All content below is a clearly-labeled synthetic sentinel, not real
sensitive data.
"""
import pytest
from unittest.mock import AsyncMock

from core.capabilities import BaseAdapter, CapabilityResult
from core.context import ContextMemory


def test_recent_conversation_is_scoped_to_the_caller(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx_scope.sqlite")
    ctx = ContextMemory()

    # Scope A: write, then read back its own history.
    ctx.save(
        "what's the answer to my private question?",
        ["knowledge"],
        "CONTEXT_SENTINEL_SCOPE_A_ANSWER",
        scope="scope-A",
    )
    prompt_seen_by_scope_a = ctx.format_for_prompt(n=5, scope="scope-A")
    assert "CONTEXT_SENTINEL_SCOPE_A_ANSWER" in prompt_seen_by_scope_a, (
        "a caller reading its own scope must still see its own recent "
        "conversation -- scoping must not break same-scope continuity "
        "(see tests/test_context.py::test_context_save_and_retrieve for "
        "the equivalent no-scope-supplied case)"
    )

    # Scope B: an unrelated caller, reading its own (empty) scope.
    prompt_seen_by_scope_b = ctx.format_for_prompt(n=5, scope="scope-B")

    # CTX-SCOPE-001 invariant, now backed by two genuinely distinguishable
    # scopes rather than two identical no-argument calls:
    assert "CONTEXT_SENTINEL_SCOPE_A_ANSWER" not in prompt_seen_by_scope_b, (
        "an unrelated scope's format_for_prompt() included another "
        "scope's raw conversation content verbatim (CTX-SCOPE-001)"
    )


def test_no_scope_supplied_preserves_legacy_shared_behavior(tmp_path, monkeypatch):
    """Differential control: a caller that does not opt into scoping at
    all (scope left at its default) must see exactly what it always
    saw -- unfiltered, most-recent-N-system-wide. Isolation is opt-in
    per caller, not automatic, because ContextMemory has no way to know
    whether the caller wants a single ongoing shared session (the
    positive case) or genuine isolation (CTX-SCOPE-001's concern)
    without being told which."""
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx_scope_legacy.sqlite")
    ctx = ContextMemory()

    ctx.save("q1", ["knowledge"], "CONTEXT_SENTINEL_LEGACY_UNSCOPED")
    prompt = ctx.format_for_prompt(n=5)  # no scope argument, exactly as before

    assert "CONTEXT_SENTINEL_LEGACY_UNSCOPED" in prompt, (
        "omitting scope entirely must preserve the exact pre-fix "
        "behavior (unfiltered) -- this is not a security boundary on "
        "its own and must not silently start filtering"
    )


def test_boost_module_is_scoped_to_the_caller(tmp_path, monkeypatch):
    """CTX-SCOPE-001: boost_module() had no scope parameter at all. Its
    live caller is core/classifier.py:45's label(), reached from
    interface/api.py:304 -- see
    test_classifier_label_boost_is_scoped_to_the_caller below for the
    end-to-end proof through that real entry point. This test isolates
    ContextMemory's own half of the fix."""
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_boost_scope.sqlite")
    ctx = ContextMemory()
    ctx.save("q", ["coding"], "a", scope="scope-A")

    assert ctx.boost_module("coding", scope="scope-A") == 0.1, (
        "a scope must see its own recent module usage"
    )
    assert ctx.boost_module("coding", scope="scope-B") == 0.0, (
        "an unrelated scope's classification confidence must not be "
        "boosted by another scope's recent module usage (CTX-SCOPE-001)"
    )
    # Differential control, matching test_no_scope_supplied_preserves_
    # legacy_shared_behavior above: omitting scope entirely (the default)
    # must preserve the old, fully-unfiltered behavior.
    assert ctx.boost_module("coding", scope=None) == 0.1


def test_long_term_memory_string_is_scoped_to_the_caller(tmp_path, monkeypatch):
    """CTX-SCOPE-001, the more severe of the two findings this session
    added: this was a single process-global string injected into EVERY
    caller's prompt unconditionally -- worse than the turns-table gap
    this finding was originally opened for, since even a caller passing
    a real scope to format_for_prompt() still inherited whichever
    execution last called set_long_term_memories_string(). Live via
    core/workers/planner.py's PlannerWorker (see
    test_planner_worker_scopes_long_term_memory_save_and_dispatch below
    for the end-to-end proof)."""
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ltm_string_scope.sqlite")
    ctx = ContextMemory()

    ctx.set_long_term_memories_string("CONTEXT_SENTINEL_LTM_SCOPE_A", scope="scope-A")
    ctx.set_long_term_memories_string("CONTEXT_SENTINEL_LTM_SCOPE_B", scope="scope-B")

    prompt_a = ctx.format_for_prompt(scope="scope-A")
    prompt_b = ctx.format_for_prompt(scope="scope-B")
    prompt_c = ctx.format_for_prompt(scope="scope-C")  # never called the setter

    assert "CONTEXT_SENTINEL_LTM_SCOPE_A" in prompt_a
    assert "CONTEXT_SENTINEL_LTM_SCOPE_B" not in prompt_a, (
        "scope A's format_for_prompt() included scope B's long-term-memory "
        "string (CTX-SCOPE-001)"
    )
    assert "CONTEXT_SENTINEL_LTM_SCOPE_B" in prompt_b
    assert "CONTEXT_SENTINEL_LTM_SCOPE_A" not in prompt_b, (
        "scope B's format_for_prompt() included scope A's long-term-memory "
        "string (CTX-SCOPE-001) -- this is the exact leak: a caller doing "
        "everything right (passing a real scope) still received another "
        "execution's long-term-memory content"
    )
    assert "CONTEXT_SENTINEL_LTM_SCOPE_A" not in prompt_c
    assert "CONTEXT_SENTINEL_LTM_SCOPE_B" not in prompt_c


def test_long_term_memory_string_cache_invalidates_on_write(tmp_path, monkeypatch):
    """Incidental correctness bug found while redesigning this method for
    scoping, fixed alongside it since it shares the same cache: the
    original set_long_term_memories_string() never invalidated
    _prompt_cache (unlike its list-based sibling, which always did) --
    a second call with new content under an already-cached (n, scope)
    key would have been silently masked by the stale cached result."""
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ltm_cache_invalidate.sqlite")
    ctx = ContextMemory()

    ctx.set_long_term_memories_string("first value", scope="scope-A")
    first = ctx.format_for_prompt(scope="scope-A")  # populates the (5, 'scope-A') cache entry
    assert "first value" in first

    ctx.set_long_term_memories_string("second value", scope="scope-A")
    second = ctx.format_for_prompt(scope="scope-A")
    assert "second value" in second
    assert "first value" not in second, (
        "format_for_prompt() returned a stale cached long-term-memory "
        "value after a write to the same scope"
    )


def test_long_term_memories_list_is_scoped_to_the_caller(tmp_path, monkeypatch):
    """set_long_term_memories() (the list-based sibling of
    set_long_term_memories_string()) has no live caller today -- but it
    writes into the exact same injection point in format_for_prompt(),
    which no longer reads the old flat self.long_term_memories field at
    all after this session's redesign. Leaving this setter unscoped
    would not have left it merely dormant-and-correct; it would have
    made it silently write to storage nothing reads, a latent
    reintroduction risk the moment a caller is ever added. Fixed
    alongside its sibling for that reason, distinct from the entities/
    get_entity() decision (a genuinely separate table/method with no
    shared code path)."""
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ltm_list_scope.sqlite")
    ctx = ContextMemory()

    ctx.set_long_term_memories([{"summary": "CONTEXT_SENTINEL_FACT_A"}], scope="scope-A")
    ctx.set_long_term_memories([{"summary": "CONTEXT_SENTINEL_FACT_B"}], scope="scope-B")

    prompt_a = ctx.format_for_prompt(scope="scope-A")
    prompt_b = ctx.format_for_prompt(scope="scope-B")
    assert "CONTEXT_SENTINEL_FACT_A" in prompt_a and "CONTEXT_SENTINEL_FACT_B" not in prompt_a
    assert "CONTEXT_SENTINEL_FACT_B" in prompt_b and "CONTEXT_SENTINEL_FACT_A" not in prompt_b


def test_scope_parameter_is_wired_through_save_last_n_and_format_for_prompt():
    """Positive replacement for the old
    test_last_n_has_no_scope_parameter_to_pass, which documented the
    ABSENCE of a scope parameter as a sanity check against silently
    assuming a fix had landed. The fix has now landed and been verified
    above against real behavior, not just a signature -- this test
    guards against the mechanism silently regressing (e.g. a future
    refactor dropping the parameter from one of these methods while
    leaving the others), which would be exactly the kind of partial,
    inconsistent fix CTX-SCOPE-001's own root cause was. Extended this
    session to cover the two methods added to the mechanism."""
    import inspect

    for method_name in ("save", "last_n", "format_for_prompt", "boost_module",
                        "set_long_term_memories_string", "set_long_term_memories"):
        params = list(inspect.signature(getattr(ContextMemory, method_name)).parameters)
        assert "scope" in params, (
            f"ContextMemory.{method_name}() lost its `scope` parameter -- "
            "this would silently reopen CTX-SCOPE-001"
        )


# ─────────────────────────────────────────────────────────────────────
# Production-path tests for this session's two findings specifically.
# PR #14's own test files (test_planner_worker.py::
# TestCtxScope001PlannerCallerWiring, test_model_router.py,
# test_api_context_scope.py) already prove the :218/dispatch/:381/
# stream_route wiring end-to-end; not duplicated here. These two prove
# the long-term-memory and classifier findings, which nothing else
# covers.
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_classifier_label_boost_is_scoped_to_the_caller(tmp_path, monkeypatch):
    """CTX-SCOPE-001 correction, proven through the real entry point:
    core/classifier.py:45's boost_module() call is live -- reached from
    interface/api.py:304's _stream_response(), not the dormant
    classifier_v3.classify() the original Context Isolation Caller
    Audit's row 9 actually traced (a different function in a different
    module). The query below is chosen so the keyword-match stage alone
    clears FAST_PATH_THRESHOLD (0.75), keeping this test off the
    LLM-disambiguation path -- no model/network dependency."""
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_classifier_prod_scope.sqlite")
    from core.classifier import label
    from core.parser import parse

    ctx = ContextMemory()
    ctx.save("prior query", ["coding"], "prior answer", scope="scope-A")

    parsed = parse("write a function to fix this code")
    labels_a = await label(parsed, ctx, scope="scope-A")
    labels_b = await label(parsed, ctx, scope="scope-B")

    conf_a = next(l.confidence for l in labels_a if l.module == "coding")
    conf_b = next(l.confidence for l in labels_b if l.module == "coding")

    assert conf_a == 0.95, "base 0.85 (keyword-hit cap) + boost_module()'s 0.1 for scope A's own usage"
    assert conf_b == 0.85, (
        "scope B's classifier confidence was boosted by scope A's recent "
        f"module usage (CTX-SCOPE-001) -- got {conf_b}, expected the unboosted base"
    )


class _ScopeCapturingAdapter(BaseAdapter):
    """Minimal capability adapter that just records the scope it
    received -- proves _dispatch_module()'s payload construction reaches
    the adapter with the real execution scope (PR #14's wiring), so this
    session's long-term-memory fix can be proven in the same realistic
    end-to-end run rather than isolation."""
    adapter_name = "scope_capturing_fake"

    def __init__(self, capability_type):
        super().__init__()
        self.capability_type = capability_type
        self.received_payloads: list[dict] = []

    async def execute(self, request, resources):
        self.received_payloads.append(dict(request.payload))
        return CapabilityResult(success=True, output="captured")


@pytest.mark.asyncio
async def test_planner_worker_scopes_long_term_memory_save_and_dispatch(tmp_path, monkeypatch):
    """CTX-SCOPE-001, end-to-end through the real production path: two
    executions through the same PlannerWorker instance sharing the same
    ContextMemory object (the exact singleton-sharing pattern production
    uses) must not observe or influence each other's context. Exercises
    all three of this worker's live ContextMemory touchpoints in one
    pass -- set_long_term_memories_string() (this session's fix, the
    decisive check below), .save(), and _dispatch_module()'s payload
    (both already wired by PR #14, re-verified here in the same run
    rather than assumed) -- via the real execute()/ExecutionContext
    path, not the deprecated WorkerContext compatibility shim other
    PlannerWorker tests use for unrelated (non-scoping) purposes."""
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_planner_prod_scope.sqlite")
    # context_assembler is imported LOCALLY inside PlannerWorker._run()
    # (from core.memory.assembly, not a core.workers.planner module-level
    # name) -- patched here at its real source so the patch reaches that
    # local import too, without depending on the real retrieval subsystem
    # (a different concern from CTX-SCOPE-001, covered by its own tests).
    import core.memory.assembly as assembly_module
    monkeypatch.setattr(
        assembly_module.context_assembler, "assemble_context",
        AsyncMock(return_value="CONTEXT_SENTINEL_PLANNER_LTM"),
    )

    from core.capabilities import (
        AdapterRuntime, CapabilityContract, CapabilityRegistry,
        CapabilityType, ResourceManager,
    )
    from core.runtime.execution_context import ExecutionContext
    from core.workers.planner import PlannerWorker

    real_context_memory = ContextMemory()

    reg = CapabilityRegistry()
    reg.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION, description="d"))
    adapter = _ScopeCapturingAdapter(CapabilityType.LLM_COMPLETION)
    reg.register_adapter(CapabilityType.LLM_COMPLETION, adapter)
    runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())

    worker = PlannerWorker(
        modules={"knowledge": object()},
        context_memory=real_context_memory,
        adapter_runtime=runtime,
    )

    exec_ctx_a = ExecutionContext(metadata={
        "query": "CONTEXT_SENTINEL_QUERY_A", "execution_id": "scope-A"})
    exec_ctx_b = ExecutionContext(metadata={
        "query": "CONTEXT_SENTINEL_QUERY_B", "execution_id": "scope-B"})

    await worker.execute(exec_ctx_a)
    await worker.execute(exec_ctx_b)

    # 1. _dispatch_module()'s payload reached the adapter with the real
    #    execution scope (PR #14's wiring, re-verified here).
    scopes_seen = [p.get("scope") for p in adapter.received_payloads]
    assert "scope-A" in scopes_seen and "scope-B" in scopes_seen, (
        f"expected both real execution scopes in the adapter payloads, got {scopes_seen}"
    )

    # 2. save() -- scope A's saved turn is invisible to scope B and vice versa.
    prompt_a = real_context_memory.format_for_prompt(scope="scope-A")
    prompt_b = real_context_memory.format_for_prompt(scope="scope-B")
    assert "CONTEXT_SENTINEL_QUERY_A" in prompt_a
    assert "CONTEXT_SENTINEL_QUERY_A" not in prompt_b, (
        "scope B observed scope A's saved conversation turn (CTX-SCOPE-001)"
    )
    assert "CONTEXT_SENTINEL_QUERY_B" in prompt_b
    assert "CONTEXT_SENTINEL_QUERY_B" not in prompt_a

    # 3. The decisive set_long_term_memories_string() proof (this
    #    session's fix): a THIRD scope that never ran at all must see
    #    neither execution's long-term-memory content. (Both A and B
    #    legitimately see the same mocked sentinel under their OWN
    #    scope -- that alone wouldn't distinguish scoped from unscoped
    #    storage. Scope C never wrote anything; pre-fix, it shared one
    #    process-global field with A and B and would have seen it anyway.)
    prompt_c = real_context_memory.format_for_prompt(scope="scope-C")
    assert "CONTEXT_SENTINEL_PLANNER_LTM" not in prompt_c, (
        "an execution that never ran saw long-term-memory content set by "
        "another execution -- the exact pre-fix single-singleton-field bug"
    )
