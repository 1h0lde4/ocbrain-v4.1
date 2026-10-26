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


# ── CTX-AUTH-002 remediation: harness self-coverage and per-trial provenance ──
#
# Requirement source: handoff v3 section 4 (owner's gate order) and ADR-KERNEL-08
# section 6 R6 + section 8.1 item 1: the harness must (a) check that it measured
# exactly the payloads it declares, and (b) record per trial which provider and
# model answered, whether the completion came from the prompt cache, that the
# cache was cleared between trials, and the harness hash / commit / non-secret
# config in the run metadata. Fails closed (exit 2) when it cannot.

import hashlib
import json
from pathlib import Path


class _FakeProvider:
    """Provider-like object that goes through the REAL provider mesh and the REAL
    prompt cache, with a scripted answer. Counts the calls that reach it."""

    def __init__(self, model="model-x", endpoint=None, mode="compliant"):
        self.model = model
        self.endpoint = endpoint
        self.calls = 0
        self._fake = lcc._make_fake(mode)

    @property
    def name(self):
        return f"FakeProvider({self.model})" + (f"@{self.endpoint}" if self.endpoint else "")

    def is_available(self):
        return True

    async def generate(self, prompt):
        self.calls += 1
        return await self._fake(self, prompt)


@pytest.fixture
def clean_prompt_cache():
    from core.prompt import cache as prompt_cache
    prompt_cache._prompt_cache.clear()
    yield prompt_cache
    prompt_cache._prompt_cache.clear()


def _run_real(capsys, provider, **overrides):
    with patch("core.cognitive.intent.resolve_provider", return_value=[provider]):
        code = asyncio.run(lcc._amain(_args(dry_run=None, **overrides)))
    return code, capsys.readouterr().out


class TestSelfCoverageInvariant:
    """The harness must verify that the set of payloads it judged for completeness
    equals exactly the declared PAYLOADS set. Before the fix a declared payload that
    silently dropped out of the measurement was simply not judged, and the run
    passed (exit 0) on the others."""

    def test_a_declared_payload_missing_from_the_measurement_is_inconclusive(self, capsys):
        class SkipsOne(dict):
            def items(self):
                return [(k, v) for k, v in dict.items(self) if k != "line-spoof"]

        with patch.object(lcc, "PAYLOADS", new=SkipsOne(lcc.PAYLOADS)):
            code, out = _run(capsys)
        verdict = _verdict_line(out)
        assert code == 2, out
        assert "self-coverage" in verdict and "line-spoof" in verdict, verdict
        assert "invariant held" not in out

    def test_a_measured_payload_that_is_not_declared_is_inconclusive(self, capsys):
        class AddsGhost(dict):
            def items(self):
                return list(dict.items(self)) + [("ghost", lcc.PAYLOADS["naive"])]

        with patch.object(lcc, "PAYLOADS", new=AddsGhost(lcc.PAYLOADS)):
            code, out = _run(capsys)
        verdict = _verdict_line(out)
        assert code == 2, out
        assert "self-coverage" in verdict and "ghost" in verdict, verdict

    def test_coverage_gaps_helper_reports_both_directions_sorted(self):
        missing, undeclared = lcc._coverage_gaps({"a", "b", "c"}, {"b", "z", "y"})
        assert missing == ["a", "c"] and undeclared == ["y", "z"]
        assert lcc._coverage_gaps({"a"}, {"a"}) == ([], [])


class TestProvenancePerTrial:
    def test_every_trial_records_provider_model_and_a_cache_miss(self, capsys, tmp_path, clean_prompt_cache):
        provider = _FakeProvider(model="model-x")
        out_json = tmp_path / "out.json"
        code, out = _run_real(capsys, provider, requests=1, trials=2, json=str(out_json))
        assert code == 0, out
        data = json.loads(out_json.read_text(encoding="utf-8"))
        records = data["benign"] + [r for runs in data["poisoned"].values() for r in runs]
        assert records and all("error" not in r for r in records)
        for r in records:
            prov = r["provenance"]
            assert prov["mode"] == "real" and prov["cache_cleared_before_trial"] is True
            answering = prov["answered_by"]
            assert answering["provider"] == "FakeProvider(model-x)"
            assert answering["model"] == "model-x"
            assert answering["cache"] == "miss"
        assert "NOT real-provider evidence" not in out

    def test_the_prompt_cache_is_cleared_between_trials_so_trials_are_independent(
            self, capsys, tmp_path, clean_prompt_cache):
        """Two trials of the same request build the same prompt. Without clearing,
        trial 2 is served from the cache and never reaches the model."""
        provider = _FakeProvider()
        out_json = tmp_path / "out.json"
        code, out = _run_real(capsys, provider, requests=1, trials=2, json=str(out_json))
        data = json.loads(out_json.read_text(encoding="utf-8"))
        total_runs = len(data["benign"]) + sum(len(v) for v in data["poisoned"].values())
        assert total_runs == 2 + 4 * 2
        assert provider.calls == total_runs, (provider.calls, total_runs)

    def test_a_completion_served_from_the_cache_is_inconclusive(self, capsys, clean_prompt_cache):
        provider = _FakeProvider()
        with patch.object(lcc, "_clear_prompt_cache", new=lambda: None):
            code, out = _run_real(capsys, provider, requests=1, trials=2)
        verdict = _verdict_line(out)
        assert code == 2, out
        assert "prompt cache" in verdict, verdict
        assert "invariant held" not in out

    def test_a_cache_that_cannot_be_cleared_is_an_error_not_a_pass(self, capsys, clean_prompt_cache):
        provider = _FakeProvider()

        def boom():
            raise RuntimeError("cache module changed shape")

        with patch.object(lcc, "_clear_prompt_cache", new=boom):
            code, out = _run_real(capsys, provider, requests=1, trials=1)
        assert code == 2, out
        assert "cache module changed shape" in out
        assert "invariant held" not in out

    def test_run_metadata_has_harness_hash_commit_and_non_secret_config(
            self, capsys, tmp_path, clean_prompt_cache):
        provider = _FakeProvider(model="model-x",
                                 endpoint="https://user:SECRETPASS@api.example.test:8443/v1?key=SECRETKEY")
        out_json = tmp_path / "out.json"
        code, out = _run_real(capsys, provider, requests=1, trials=1, json=str(out_json))
        assert code == 0, out
        raw = out_json.read_text(encoding="utf-8")
        assert "SECRETPASS" not in raw and "SECRETKEY" not in raw
        assert "SECRETPASS" not in out and "SECRETKEY" not in out
        meta = json.loads(raw)["provenance"]["run"]
        assert meta["mode"] == "real" and meta["real_provider_path"] is True
        expected = hashlib.sha256(Path(lcc.__file__).read_bytes()).hexdigest()
        assert meta["harness_sha256"] == expected
        assert isinstance(meta["git_commit"], str) and meta["git_commit"]
        assert meta["git_dirty_tracked"] in (True, False, None)
        configured = meta["providers_configured"]
        assert configured and configured[0]["model"] == "model-x"
        assert configured[0]["endpoint"] == "https://api.example.test:8443"
        summary = json.loads(raw)["provenance"]["summary"]
        assert summary["cache_hits"] == 0 and summary["runs_without_provenance"] == 0
        # the provider name embeds its endpoint; the harness must record it with credentials stripped
        assert summary["answered_by"] == {"FakeProvider(model-x)@https://api.example.test:8443": summary["runs"]}

    def test_real_path_run_with_no_answering_provider_records_no_attribution(
            self, capsys, tmp_path, clean_prompt_cache):
        """mode=real only says the real path was used; with no provider answering there is
        no attribution at all and the run is INCONCLUSIVE, never a pass."""
        class Silent(_FakeProvider):
            async def generate(self, prompt):
                self.calls += 1
                return ""

        out_json = tmp_path / "out.json"
        code, out = _run_real(capsys, Silent(), requests=1, trials=1, json=str(out_json))
        assert code == 2, out
        summary = json.loads(out_json.read_text(encoding="utf-8"))["provenance"]["summary"]
        assert summary["answered_by"] == {} and summary["models"] == {}
        assert "invariant held" not in out

    def test_dry_run_is_labelled_as_not_real_provider_evidence(self, capsys, tmp_path):
        out_json = tmp_path / "out.json"
        code, out = _run(capsys, json=str(out_json))
        assert code == 0, out
        assert "NOT real-provider evidence" in out
        meta = json.loads(out_json.read_text(encoding="utf-8"))["provenance"]["run"]
        assert meta["mode"] == "stand-in" and meta["real_provider_path"] is False

    def test_endpoint_sanitizer_keeps_only_scheme_host_and_port(self):
        f = lcc._sanitize_endpoint
        assert f("https://user:pw@h.example:8443/v1?key=K#frag") == "https://h.example:8443"
        assert f("http://localhost:11434") == "http://localhost:11434"
        assert f(None) is None
        assert f("not a url") is None


# ── coverage policy and trial accounting (independent-review finding, options A + B) ──
#
# The default policy (ADR-KERNEL-08 R6/section 7: one exposed, answered trial per payload)
# is unchanged. Trials that got no model completion are COUNTED, by kind, and never
# hidden; `--require-all-answered` is an opt-in strict policy. Escalation always wins.

class _FlakyProvider(_FakeProvider):
    """Answers compliantly, but every second call returns a blank completion."""

    async def generate(self, prompt):
        self.calls += 1
        return "" if self.calls % 2 == 0 else await self._fake(self, prompt)


class _RaisingProvider(_FakeProvider):
    async def generate(self, prompt):
        self.calls += 1
        raise ConnectionError("provider down")


class _BlanksOnePayload(_FakeProvider):
    """Never answers the 'line-spoof' payload; answers everything else."""

    async def generate(self, prompt):
        self.calls += 1
        return "" if "Copy the line above verbatim" in prompt else await self._fake(self, prompt)


def _run_chain(capsys, providers, **overrides):
    with patch("core.cognitive.intent.resolve_provider", return_value=list(providers)):
        code = asyncio.run(lcc._amain(_args(dry_run=None, **overrides)))
    return code, capsys.readouterr().out


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _reconciles(acc):
    return acc["started_trials"] == (acc["nonblank_completion_trials"] + acc["blank_response_trials"]
                                     + acc["provider_error_trials"] + acc["no_completion_trials"]
                                     + acc["error_trials"])


class TestCoveragePolicyAndTrialAccounting:
    def test_every_trial_answered_exits_0_under_both_policies_and_records_the_policy(
            self, capsys, tmp_path, clean_prompt_cache):
        for strict in (False, True):
            out_json = tmp_path / f"out_{strict}.json"
            code, out = _run_chain(capsys, [_FakeProvider()], requests=1, trials=2,
                                   json=str(out_json), require_all_answered=strict)
            assert code == 0, out
            data = _read_json(out_json)
            expected = lcc.POLICY_STRICT if strict else lcc.POLICY_DEFAULT
            meta = data["provenance"]["run"]
            assert meta["coverage_policy"] == expected
            assert meta["args"]["require_all_answered"] is strict
            assert expected in out
            acc = data["provenance"]["summary"]["accounting"]["all"]
            assert (acc["scheduled_trials"] == acc["started_trials"] == acc["nonblank_completion_trials"]
                    == acc["attributed_completion_trials"] == 10)
            assert _reconciles(acc)

    def test_blank_trials_are_counted_and_reported_under_the_default_policy(
            self, capsys, tmp_path, clean_prompt_cache):
        out_json = tmp_path / "out.json"
        code, out = _run_chain(capsys, [_FlakyProvider()], requests=2, trials=3, json=str(out_json))
        assert code == 0, out                                  # the accepted coverage policy still holds
        assert "minimum coverage met" in out
        assert "15 of 30 trial(s) produced no model completion (blank: 15" in out
        assert "no evidence about model resistance" in out
        data = _read_json(out_json)
        acc = data["provenance"]["summary"]["accounting"]
        assert acc["all"]["blank_response_trials"] == 15 and acc["all"]["nonblank_completion_trials"] == 15
        assert acc["all"]["provider_error_trials"] == 0 and acc["all"]["no_completion_trials"] == 0
        for group in [acc["benign"], *acc["poisoned"].values(), acc["all"]]:
            assert _reconciles(group)
        for name, group in acc["poisoned"].items():
            assert group["blank_response_trials"] == 3 and group["nonblank_completion_trials"] == 3, name
        runs = data["benign"] + [r for v in data["poisoned"].values() for r in v]
        assert all("outcome" in r for r in runs)
        # attempt accounting covers the blank trials too, not only the answered ones
        attempts = data["provenance"]["summary"]["provider_attempts"]
        assert attempts["total"] == 30 and attempts["blank_returned"] == 15

    def test_strict_policy_makes_any_blank_trial_inconclusive(self, capsys, tmp_path, clean_prompt_cache):
        out_json = tmp_path / "out.json"
        code, out = _run_chain(capsys, [_FlakyProvider()], requests=2, trials=3, json=str(out_json),
                               require_all_answered=True)
        verdict = _verdict_line(out)
        assert code == 2, out
        assert "strict coverage policy (all-trials-answered/v1)" in verdict and "blank: 15" in verdict
        assert "invariant held" not in out
        meta = _read_json(out_json)["provenance"]["run"]
        assert meta["coverage_policy"] == lcc.POLICY_STRICT and meta["args"]["require_all_answered"] is True

    def test_a_payload_with_no_valid_answer_is_inconclusive_under_both_policies(
            self, capsys, clean_prompt_cache):
        for strict in (False, True):
            code, out = _run_chain(capsys, [_BlanksOnePayload()], requests=1, trials=2,
                                   require_all_answered=strict)
            assert code == 2, out
            assert "line-spoof" in _verdict_line(out)

    def test_provider_calls_that_raise_are_provider_errors_not_blank_responses(
            self, capsys, tmp_path, clean_prompt_cache):
        for strict in (False, True):
            out_json = tmp_path / f"out_{strict}.json"
            code, out = _run_chain(capsys, [_RaisingProvider()], requests=1, trials=2,
                                   json=str(out_json), require_all_answered=strict)
            assert code == 2, out
            acc = _read_json(out_json)["provenance"]["summary"]["accounting"]["all"]
            assert acc["provider_error_trials"] == 10 and acc["blank_response_trials"] == 0
            assert acc["nonblank_completion_trials"] == 0 and _reconciles(acc)

    def test_a_cached_blank_replayed_to_the_fallback_provider_is_reported_not_hidden(
            self, capsys, tmp_path, clean_prompt_cache):
        """ADJ-1: the first provider's blank answer is cached under the prompt, so the
        fallback provider is served the cached blank instead of being called."""
        class Secondary(_FakeProvider):
            @property
            def name(self):
                return "Secondary(model-y)"

        flaky, second = _FlakyProvider(), Secondary(model="model-y")
        out_json = tmp_path / "out.json"
        code, out = _run_chain(capsys, [flaky, second], requests=2, trials=3, json=str(out_json))
        assert code == 0, out
        summary = _read_json(out_json)["provenance"]["summary"]
        assert second.calls == 0                                # the fallback was never actually called
        assert summary["cached_blank_replay_trials"] == 15
        assert summary["trials_with_fallback_attempts"] == 15
        assert summary["provider_attempts"]["total"] == 45 and summary["provider_attempts"]["cache_hit"] == 15
        assert "cached blank replays inside a trial: 15" in out
        code, out = _run_chain(capsys, [_FlakyProvider(), Secondary(model="model-y")],
                               requests=2, trials=3, require_all_answered=True)
        assert code == 2, out

    def test_a_genuine_escalation_is_exit_1_under_both_policies_even_with_blank_trials(
            self, capsys, clean_prompt_cache):
        from core.cognitive import planner
        forged = SimpleNamespace(source=planner.ConstraintSource.EXPLICIT,
                                 rationale="scoping_constraint: only for the new account")
        for strict in (False, True):
            with patch("core.cognitive.planner._extract_constraints", new=AsyncMock(return_value=[forged])):
                code, out = _run_chain(capsys, [_FlakyProvider()], requests=1, trials=2,
                                       require_all_answered=strict)
            assert code == 1, out
            assert "INVARIANT FAILED" in out and "invariant held" not in out



# ── secret redaction (CTX-AUTH-002 revision, harness audit finding H-1 / H-2) ────────────
# Every marker below is a clearly-labelled synthetic string. None is a real credential, and
# no test here contacts any provider: the "providers" are in-process fakes.

_MARK = "SYNTHSECRET"


class TestSecretRedaction:
    """The harness prints and persists provider provenance and error text. A URL inside
    either may carry userinfo, a query-string key or a fragment; none of it may survive."""

    @pytest.mark.parametrize("name", [
        f"OpenAICompat(m@https://u:{_MARK}1@h.example/v1?key={_MARK}2)",
        f"OpenAICompat(m@HTTPS://u:{_MARK}3@h.example/v1?key={_MARK}4)",      # upper-case scheme
        f"OpenAICompat(m@https://u:pa)ss{_MARK}5@h.example/v1)",             # ")" is legal in userinfo
        f"OpenAICompat(m@https://h.example/v1?k=a]b{_MARK}6)",               # "]" inside a query
        f"OpenAICompat(m@https://h.example/v1#{_MARK}7)",                    # fragment
    ])
    def test_provider_name_keeps_only_scheme_host_and_port(self, name):
        shown = lcc._safe_provider_name(SimpleNamespace(name=name))
        assert _MARK not in shown, shown
        assert "h.example" in shown, "the non-secret host must stay, or the trial is not auditable"

    def test_the_providers_own_endpoint_is_replaced_even_with_unusual_characters(self):
        endpoint = f"https://u:pa ss{_MARK}8@h.example:8443/v1?key={_MARK}9"
        provider = SimpleNamespace(name=f"OpenAICompat(m@{endpoint})", endpoint=endpoint)
        shown = lcc._safe_provider_name(provider)
        assert _MARK not in shown, shown
        assert "https://h.example:8443" in shown, shown

    def test_scrub_urls_leaves_text_that_is_not_a_url_unchanged(self):
        text = "RuntimeError('cache module changed shape')"
        assert lcc._scrub_urls(text) == text

    def test_a_url_in_an_exception_is_reduced_and_trailing_punctuation_survives(self):
        shown = lcc._safe_error(RuntimeError(f"failed for (https://u:{_MARK}a@h.example/p?k={_MARK}b)."))
        assert _MARK not in shown, shown
        assert "https://h.example" in shown, shown

    def test_a_non_http_url_is_replaced_not_passed_through(self):
        assert _MARK not in lcc._scrub_urls(f"dial wss://u:{_MARK}c@h.example/x failed")

    def test_an_exception_escaping_interpret_request_reaches_neither_stdout_nor_the_json(
            self, capsys, tmp_path, clean_prompt_cache):
        """The error path used to print and persist repr(exc) verbatim."""
        provider = _FakeProvider()
        boom = RuntimeError(f"upstream failed for https://u:{_MARK}d@h.example/v1?key={_MARK}e")
        out_json = tmp_path / "out.json"
        with patch("core.cognitive.intent.interpret_request", new=AsyncMock(side_effect=boom)):
            code, out = _run_real(capsys, provider, requests=1, trials=1, json=str(out_json))
        raw = out_json.read_text(encoding="utf-8")
        assert code == 2, out
        assert _MARK not in out and _MARK not in raw
        assert "upstream failed" in raw and "h.example" in raw, "the diagnosis must survive redaction"

    def test_a_credential_bearing_provider_name_reaches_no_output_and_stays_auditable(
            self, capsys, tmp_path, clean_prompt_cache):
        endpoint = f"HTTPS://u:{_MARK}f@api.example.test:8443/v1?key={_MARK}g"
        provider = _FakeProvider(model="model-x", endpoint=endpoint)
        out_json = tmp_path / "out.json"
        code, out = _run_real(capsys, provider, requests=1, trials=1, json=str(out_json))
        raw = out_json.read_text(encoding="utf-8")
        assert code == 0, out
        assert _MARK not in out and _MARK not in raw
        summary = json.loads(raw)["provenance"]["summary"]
        assert any("api.example.test:8443" in name for name in summary["answered_by"]), summary["answered_by"]


# ── event contract and unverifiable cache state (CTX-AUTH-002 revision, scenarios 7 and 9) ──

def _valid_events():
    grounding = sorted(lcc.GROUNDING_VOCAB)[0]
    generated = {"labels": ["a"], "citation_grounding": [grounding]}
    interpreted = {"selected_label": "a", "selected_citation_grounding": grounding,
                   "selection_basis": sorted(lcc.BASIS_VOCAB)[0]}
    return generated, interpreted


class TestEventContractBranches:
    """_validate_events must name the missing or invalid field and never substitute a default.
    One end-to-end test already pins exit 2; each branch is pinned here."""

    def test_a_complete_pair_of_events_is_accepted(self):
        assert lcc._validate_events(*_valid_events()) is None

    @pytest.mark.parametrize("break_it,expected", [
        (lambda g, i: (None, i), "was not emitted"),
        (lambda g, i: (g, {}), "was not emitted"),
        (lambda g, i: ({**g, sorted(lcc.REJECTED_EVENT_KEYS)[0]: []}, i), "rejected key"),
        (lambda g, i: (g, {**i, sorted(lcc.REJECTED_EVENT_KEYS)[0]: "x"}), "rejected key"),
        (lambda g, i: ({**g, "labels": "not-a-list"}, i), "labels missing or not a list"),
        (lambda g, i: ({k: v for k, v in g.items() if k != "citation_grounding"}, i),
         "citation_grounding missing or not a list"),
        (lambda g, i: ({**g, "labels": ["a", "b"]}, i), "differ in length"),
        (lambda g, i: ({**g, "citation_grounding": ["not-in-the-vocabulary"]}, i), "outside the vocabulary"),
        (lambda g, i: ({**g, "citation_grounding": ["verified_operative"]}, i), "outside the vocabulary"),
        (lambda g, i: (g, {**i, "selected_citation_grounding": "verified_nonoperative"}),
         "selected_citation_grounding"),
        (lambda g, i: (g, {**i, "selected_label": None}), "selected_label"),
        (lambda g, i: (g, {**i, "selected_citation_grounding": "bogus"}), "selected_citation_grounding"),
        (lambda g, i: (g, {k: v for k, v in i.items() if k != "selection_basis"}), "selection_basis"),
        (lambda g, i: (g, {**i, "selection_basis": "bogus"}), "selection_basis"),
    ])
    def test_each_missing_or_invalid_field_is_named_and_never_defaulted(self, break_it, expected):
        problem = lcc._validate_events(*break_it(*_valid_events()))
        assert problem is not None and expected in problem, problem


class _UnhookableProvider(_FakeProvider):
    """A provider whose generate() cannot be wrapped, so the harness cannot observe whether a
    call reached it or the cache answered."""

    def __setattr__(self, name, value):
        if name == "generate":
            raise AttributeError("generate is read-only on this provider")
        super().__setattr__(name, value)


class TestCacheStateThatCannotBeObserved:
    def test_a_completion_whose_cache_state_is_unverifiable_is_inconclusive_not_a_pass(
            self, capsys, clean_prompt_cache):
        code, out = _run_real(capsys, _UnhookableProvider(), requests=1, trials=1)
        verdict = _verdict_line(out)
        assert code == 2, out
        assert "cache state unverified" in out, out
        assert "invariant held" not in out
        assert "no pass is claimed" in verdict or "INCONCLUSIVE" in verdict, verdict
