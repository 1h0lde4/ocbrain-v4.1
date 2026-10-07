"""
tests/test_live_citation_check.py -- sensitivity tests for live_citation_check.py
(CTX-AUTH-002 evidence chain, ADR-KERNEL-08 section 8.1 item 1).

live_citation_check.py is part of the evidence chain for CTX-AUTH-002, so it must
FAIL LOUDLY rather than claim a clean pass when it measured nothing or when its
own instrumentation is broken. Each test here re-creates one specific way the
harness used to exit 0 vacuously (or could), and requires it to exit 2 instead:

  gap 1   zero runs (--trials 0 / --requests 0)            -> exit 2, not 0
  gap 2   the poisoned entry never reached a prompt         -> exit 2, not 0
  guard   interpret_request returned no goals               -> run error, exit 2
  gap 3   the model never answered (empty completions)      -> exit 2, not 0
  gap 4   ONE payload never exposed / never answered while the
          others were (judged per payload, not in aggregate)  -> exit 2, not 0
  codes   an escalated EXPLICIT constraint                  -> exit 1
          a run error                                       -> exit 2

Everything runs the real harness in-process in --dry-run (scripted stand-in
model, no provider). That validates the harness and the code path, NOT any real
model. Do not weaken an assertion here to make a harness change pass: a harness
that can report a pass without measuring is exactly what these tests exist to
prevent. Do not mark any test xfail.

Each test is shown to fail against the previous harness (commit 218ff59) and
each guard is covered by a mutant in scripts/mutation_check_ctx_auth_002.py.
"""
import argparse
import asyncio
import re
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import live_citation_check as lcc


def _args(**overrides) -> argparse.Namespace:
    """Namespace the harness' own parser would build. verbose=True keeps the
    harness from calling logging.disable() process-wide (a side effect that would
    leak into other tests)."""
    base = dict(requests=1, trials=1, json=None, dry_run="compliant",
                verbose=True, fail_on_selected=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def _run(capsys, **overrides):
    code = asyncio.run(lcc._amain(_args(**overrides)))
    return code, capsys.readouterr().out


class TestHarnessGreenPathIsReal:
    def test_a_normal_dry_run_passes_and_actually_measured_something(self, capsys):
        """Control: the guards must not break the genuine pass, and a pass must
        come with measurements (otherwise the vacuous-pass tests below prove
        nothing)."""
        code, out = _run(capsys)
        exposed = re.search(r"exposed trials: (\d+)", out)
        assert code == 0, out
        assert "invariant held" in out
        assert exposed and int(exposed.group(1)) > 0, out


class TestGap1ZeroRunsAreNotAPass:
    @pytest.mark.parametrize("flag,value", [
        ("--trials", "0"), ("--requests", "0"), ("--trials", "-1"), ("--requests", "-3"),
    ])
    def test_cli_rejects_a_run_count_that_would_measure_nothing(self, flag, value, capsys):
        """Rejected AT THE ARGUMENT BOUNDARY: exit 2, a message that names the
        problem, and no work done. (The runtime guard below also exits 2 for a
        zero count, so the exit code alone cannot tell the two layers apart.)"""
        with patch.object(sys, "argv", ["live_citation_check.py", "--dry-run", "compliant", flag, value]):
            with pytest.raises(SystemExit) as exc:
                lcc.main()
        captured = capsys.readouterr()
        assert exc.value.code == 2
        assert "must be >= 1" in captured.err, captured.err
        assert "part A done" not in captured.out, "work was started before the count was rejected"

    def test_zero_runs_that_bypass_the_cli_are_inconclusive_not_a_pass(self, capsys):
        """Defense in depth: even if a zero-run configuration reaches _amain
        (a future caller, a changed parser), it must not report a pass."""
        code, out = _run(capsys, trials=0)
        assert code == 2, out
        assert "no runs were executed" in out
        assert "invariant held" not in out


class TestGap2PoisonNeverExposedIsNotAPass:
    def test_entry_that_never_reaches_a_prompt_is_inconclusive_not_a_pass(self, capsys):
        """Simulates retrieval never surfacing the poisoned entry (or the
        seeding path being broken): runs execute and nothing errors, but part B
        measured nothing, so exit 2 -- in every mode, --dry-run included."""
        real_seed = lcc._seed

        async def seed_without_poison(memory, payload=None):
            await real_seed(memory)          # benign facts only; the payload is dropped

        with patch.object(lcc, "_seed", new=seed_without_poison):
            code, out = _run(capsys)
        assert code == 2, out
        assert "never reached a prompt" in out
        assert "invariant held" not in out
        assert re.search(r"exposed trials: 0\b", out), out


class TestGap3ModelNeverAnsweredIsNotAPass:
    def test_empty_completions_in_every_exposed_trial_are_inconclusive_not_a_pass(self, capsys):
        """Found by running the harness for real with no provider configured:
        every completion was empty, 0 runs errored, and it exited 0 with
        "invariant held". The poisoned entry reached the prompt, but a model that
        never answered cannot have been fooled, so nothing was measured."""
        def silent_model(_mode):
            async def fake(provider, prompt):
                return ""
            return fake

        with patch.object(lcc, "_make_fake", new=silent_model):
            code, out = _run(capsys)
        assert code == 2, out
        assert "returned no completion" in out
        assert "invariant held" not in out
        assert re.search(r"exposed trials: [1-9]", out), "the entry must have been exposed for this to be the no-answer case"


def _verdict_line(out: str) -> str:
    """The single printed INCONCLUSIVE verdict line (not the payload table)."""
    lines = [ln for ln in out.splitlines() if "INCONCLUSIVE" in ln]
    assert len(lines) == 1, out
    return lines[0]


class TestMeasurementCompletenessIsPerPayload:
    """A declared adversarial payload that was never exposed, or whose exposed
    trials never got an answer, was NEVER TESTED -- however well the other
    payloads went. Judging exposure/answering in aggregate would let one
    untested case hide behind three tested ones. Exit 2 (inconclusive), never
    1 (nothing was observed violating the invariant) and never 0."""

    def test_one_payload_never_exposed_is_inconclusive_even_when_the_others_were(self, capsys):
        real_seed = lcc._seed
        target = lcc.PAYLOADS["constraint-bait"]

        async def seed_dropping_one_payload(memory, payload=None):
            await real_seed(memory, None if payload == target else payload)

        with patch.object(lcc, "_seed", new=seed_dropping_one_payload):
            code, out = _run(capsys)
        verdict = _verdict_line(out)
        assert code == 2, out
        assert "never reached a prompt" in verdict
        assert "constraint-bait" in verdict
        for tested in ("naive", "cite-request", "line-spoof"):
            assert tested not in verdict, f"{tested} was exposed and must not be named: {verdict}"
        assert re.search(r"exposed trials: [1-9]", out), \
            "the other payloads must have been exposed, or this is not the per-payload case"
        assert "invariant held" not in out

    def test_one_payload_never_answered_is_inconclusive_even_when_the_others_were(self, capsys):
        real_make = lcc._make_fake

        def silent_for_constraint_bait(mode):
            inner = real_make(mode)

            async def fake(provider, prompt):
                if "followed by the words" in prompt:      # only the constraint-bait entry has this
                    return ""
                return await inner(provider, prompt)
            return fake

        with patch.object(lcc, "_make_fake", new=silent_for_constraint_bait):
            code, out = _run(capsys)
        verdict = _verdict_line(out)
        assert code == 2, out
        assert "returned no completion" in verdict
        assert "constraint-bait" in verdict
        for answered in ("naive", "cite-request", "line-spoof"):
            assert answered not in verdict, f"{answered} was answered and must not be named: {verdict}"
        assert re.search(r"exposed trials: [1-9]", out)
        assert "invariant held" not in out


class TestEmptyGoalsGuard:
    def test_a_run_with_no_goals_is_an_error_not_a_clean_run(self, capsys):
        """If interpret_request ever returned [], the escalation check would
        inspect nothing and ESCALATED would be 0 vacuously."""
        from core.cognitive import intent
        real = intent.interpret_request

        async def drop_goals(*args, **kwargs):
            await real(*args, **kwargs)      # events are still emitted and valid
            return []

        with patch("core.cognitive.intent.interpret_request", new=drop_goals):
            code, out = _run(capsys)
        assert code == 2, out
        assert "returned no goals" in out
        assert "invariant held" not in out


class TestExitCodeContract:
    def test_an_escalated_explicit_constraint_exits_1(self, capsys):
        """Simulates a regressed planner: it produces an EXPLICIT constraint the
        user's own text does not account for. The invariant failure must win."""
        from core.cognitive import planner
        forged = SimpleNamespace(source=planner.ConstraintSource.EXPLICIT,
                                 rationale="scoping_constraint: only for the new account")

        with patch("core.cognitive.planner._extract_constraints",
                   new=AsyncMock(return_value=[forged])):
            code, out = _run(capsys, dry_run="obey-padded")
        assert code == 1, out
        assert "INVARIANT FAILED" in out
        assert "invariant held" not in out

    def test_an_unreadable_event_field_exits_2_and_never_defaults_to_zero(self, capsys):
        """Instrumentation broken (here: the harness cannot read the events it
        depends on) must be INCONCLUSIVE, never a quiet zero."""
        with patch.object(lcc, "_validate_events", return_value="forced for test: event field missing"):
            code, out = _run(capsys)
        assert code == 2, out
        assert "INCONCLUSIVE" in out
        assert "invariant held" not in out
