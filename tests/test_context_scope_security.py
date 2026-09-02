"""
tests/test_context_scope_security.py — CTX-SCOPE-001 security regression.

Permanent regression capturing a verified scope gap in
core/context.py::ContextMemory, surfaced during the cache-isolation /
ContextMemory path audit. See:
    docs/research/context-engineering/context-authority-threat-model.md
    (finding CTX-SCOPE-001)
    docs/research/context-engineering/context-memory-path-audit.md

STATUS: test_recent_conversation_is_not_scoped_to_the_caller is EXPECTED
TO FAIL (red). Do not weaken this assertion, do not mark it xfail (this
repository has no such convention), do not delete it. When a scope
parameter is added to save()/last_n()/format_for_prompt() as part of the
Context Engineering remediation, this test should turn green without
modification to the assertion itself.

Root cause: ContextMemory.save()/last_n()/format_for_prompt() have no
task/session/user/workflow parameter anywhere in their signatures. The
underlying `turns` table has no scope column (id, timestamp, query,
modules_used, answer only). format_for_prompt()'s "### RECENT
CONVERSATION" section is therefore the most recent N interactions
system-wide, unconditionally, regardless of who produced them --
verified against the real ContextMemory class, not a reimplementation.

Unlike CTX-AUTH-001, this requires no adversarial input and no model
susceptibility to injection -- it is a direct, mechanical read of
unscoped state. Currently confined to core/context.py::ContextMemory's
production callers, which per the ContextMemory path audit are: (a) the
K4.2 branch's write-only call (orchestrator.py:510, does not itself
read format_for_prompt() back), and (b) the Legacy Compatibility
Bridge's read/format_for_prompt() call, confirmed not exercised in
production today (main.py always supplies workflow_runtime). The gap
demonstrated here is real and reproducible against the live class either
way -- production exposure depends on which callers reach it, tracked
separately in the threat model, not on whether this test can reproduce
the underlying mechanism.

This test does NOT dispute that recent-conversation continuity is a
real, intended feature for a single ongoing session -- see the existing
tests/test_context.py::test_context_save_and_retrieve for that positive
case. The gap is specifically the absence of any way to say "only my own
recent turns," not the feature's existence.

All content below is a clearly-labeled synthetic sentinel, not real
sensitive data.
"""
from core.context import ContextMemory


def test_recent_conversation_is_not_scoped_to_the_caller(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx_scope.sqlite")
    ctx = ContextMemory()

    # "Scope A" interaction -- e.g. one task, session, or user.
    ctx.save(
        "what's the answer to my private question?",
        ["knowledge"],
        "CONTEXT_SENTINEL_SCOPE_A_ANSWER",
    )

    # "Scope B" request: a completely unrelated caller, using the exact
    # same API a genuinely different scope would have to use, because
    # there is no scope parameter anywhere to differentiate with.
    prompt_seen_by_scope_b = ctx.format_for_prompt(n=5)

    # DESIRED FUTURE INVARIANT (CTX-SCOPE-001) -- currently expected to fail:
    assert "CONTEXT_SENTINEL_SCOPE_A_ANSWER" not in prompt_seen_by_scope_b, (
        "an unrelated caller's format_for_prompt() included another "
        "scope's raw conversation content verbatim, with no parameter "
        "anywhere to exclude it (CTX-SCOPE-001)"
    )


def test_last_n_has_no_scope_parameter_to_pass():
    """Documents the API-surface fact directly: last_n()'s only
    parameter is a result-count limit, not a scope filter. Sanity check
    that this hasn't silently changed (which would mean the finding
    above needs re-verifying, not that the fix landed -- a real fix
    would also need save() and format_for_prompt() to accept and use a
    matching parameter, not just last_n())."""
    import inspect

    params = list(inspect.signature(ContextMemory.last_n).parameters)
    assert params == ["self", "n"], (
        f"last_n()'s signature changed to {params} -- re-verify "
        "CTX-SCOPE-001 against the current implementation before "
        "assuming this reflects a fix"
    )
