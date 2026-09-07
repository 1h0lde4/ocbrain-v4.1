"""
tests/test_context_scope_security.py — CTX-SCOPE-001 security regression.

Permanent regression capturing a verified scope gap in
core/context.py::ContextMemory, surfaced during the cache-isolation /
ContextMemory path audit. See:
    docs/research/context-engineering/context-authority-threat-model.md
    (finding CTX-SCOPE-001)
    docs/research/context-engineering/context-memory-path-audit.md
    docs/Bugs Hunt & fix reports/KERNEL_V1_0_CLOSURE_AUDIT_SEP2026.md

STATUS (Sept 7, 2026): the underlying mechanism is fixed --
save()/last_n()/format_for_prompt() now accept and use a real `scope`
parameter, backed by a real column on the `turns` table, with the
prompt cache keyed on (n, scope) so it can't leak across scopes either.

The original version of test_recent_conversation_is_not_scoped_to_the_caller
called save() and format_for_prompt() with no scope argument at all on
both sides. That was a defect in the *test*, not evidence the mechanism
doesn't work: two calls with identical arguments on the same instance
cannot deterministically produce different results, by construction --
no fix to ContextMemory could ever have turned that specific test green
without either non-deterministic behavior (forbidden) or the test
itself constructing two actually-distinguishable scopes. It has been
rewritten below to do that -- scope-A write, scope-A read (continuity),
scope-B read (isolation) -- with the security assertion's *content*
unchanged: an unrelated scope must not see another scope's raw
conversation content verbatim.

Do not weaken that assertion, do not mark it xfail (this repository has
no such convention), do not delete it.

NOT CLOSED YET, and should not be treated as such: this file only
proves the *mechanism* works when a caller opts in. It says nothing
about whether real production callers actually do. A broader grep
during the fix found more ContextMemory.save()/format_for_prompt()
callers than the threat-model doc's own audit listed (modules/base.py,
knowledge, coding, and web_search modules; interface/api.py:381;
model_router.py; core/workers/planner.py:218) -- all still call these
methods with no scope argument, which is intentionally NOT changed
here (no arbitrary scope was assigned just to make a suite green; see
the Context Isolation Caller Audit report for the full per-caller
disposition). CTX-SCOPE-001 remains open at the finding level, tracked
in KNOWN_ISSUES.md, until that audit's "unsafe" and "ambiguous" rows
(if any) are resolved.

All content below is a clearly-labeled synthetic sentinel, not real
sensitive data.
"""
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


def test_scope_parameter_is_wired_through_save_last_n_and_format_for_prompt():
    """Positive replacement for the old
    test_last_n_has_no_scope_parameter_to_pass, which documented the
    ABSENCE of a scope parameter as a sanity check against silently
    assuming a fix had landed. The fix has now landed and been verified
    above against real behavior, not just a signature -- this test
    guards against the mechanism silently regressing (e.g. a future
    refactor dropping the parameter from one of the three methods while
    leaving the others), which would be exactly the kind of partial,
    inconsistent fix CTX-SCOPE-001's own root cause was."""
    import inspect

    for method_name in ("save", "last_n", "format_for_prompt"):
        params = list(inspect.signature(getattr(ContextMemory, method_name)).parameters)
        assert "scope" in params, (
            f"ContextMemory.{method_name}() lost its `scope` parameter -- "
            "this would silently reopen CTX-SCOPE-001"
        )
