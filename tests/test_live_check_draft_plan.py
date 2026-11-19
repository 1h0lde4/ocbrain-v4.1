"""tests/test_live_check_draft_plan.py -- the ADR-KERNEL-07 draft-plan live-check harness.

These test the INSTRUMENT (scripts/live_check_draft_plan.py), not any real model:
its word-level classification, its offline self-test profiles, and -- most
important -- that a run which could not reach a provider can never be presented
as evidence. They prove nothing about how a real model decomposes requests; that
is exactly what the live run is for (ADR-KERNEL-07 §10.4, [PENDING]).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "live_check_draft_plan.py"
_spec = importlib.util.spec_from_file_location("live_check_draft_plan", _PATH)
lc = importlib.util.module_from_spec(_spec)
sys.modules["live_check_draft_plan"] = lc
_spec.loader.exec_module(lc)

REQ = "write a 1000 words story"
INTERP = "Write a 1000 words story"


class TestClassification:
    def test_words_copied_from_request_or_interpretation_are_not_novel(self):
        assert lc.novel_content_tokens(INTERP, [REQ, INTERP]) == []

    def test_authoring_process_words_are_not_content(self):
        # Regression: the first version flagged 'revise'/'polish', which would
        # have labeled almost every multi-step plan "speculative".
        assert lc.novel_content_tokens(
            "Revise and polish the draft", [REQ, INTERP]) == []
        assert lc.novel_content_tokens(
            "Outline the piece, then finalize the draft", [REQ, INTERP]) == []

    def test_invented_premise_content_is_flagged(self):
        novel = lc.novel_content_tokens(
            "Invent a detective protagonist in a rain-soaked city", [REQ, INTERP])
        assert {"detective", "protagonist", "rain", "city"} <= set(novel)

    def test_step_labels(self):
        assert lc.classify_step(INTERP, REQ, INTERP)["label"] == "redundant"
        assert lc.classify_step("Draft the piece", REQ, INTERP)["label"] == "generic"
        assert lc.classify_step(
            "Write it as a noir mystery", REQ, INTERP)["label"] == "speculative"

    def test_plan_label_aggregation(self):
        assert lc.classify_plan([INTERP], REQ, INTERP) == "redundant"
        assert lc.classify_plan(
            ["Draft the piece", "Polish the draft"], REQ, INTERP) == "generic"
        assert lc.classify_plan(
            ["Draft the piece", "Add a betrayal twist"], REQ, INTERP) == "speculative"

    def test_one_speculative_step_outweighs_generic_ones(self):
        assert lc.classify_plan(
            ["Draft the piece"] * 4 + ["Set it on Mars"], REQ, INTERP) == "speculative"


class TestOfflineSelfTest:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("profile,expected", [
        ("single", "redundant"), ("generic", "generic"),
        ("speculative", "speculative")])
    async def test_profiles_land_where_designed(self, profile, expected):
        res = await lc.run(lc.SAMPLE, offline=profile)
        assert res["escalated"] == len(lc.SAMPLE)
        assert res["label_counts"] == {expected: len(lc.SAMPLE)}

    @pytest.mark.asyncio
    async def test_offline_output_is_always_marked_not_evidence(self):
        res = await lc.run(lc.SAMPLE[:2], offline="single")
        assert res["not_evidence"] is True
        assert "NOT EVIDENCE" in lc.render(res)
        assert res["mode"].startswith("OFFLINE-SYNTHETIC")

    @pytest.mark.asyncio
    async def test_well_specified_request_is_not_analysed(self):
        res = await lc.run(["write a poem about autumn"], offline="speculative")
        row = res["rows"][0]
        assert row["would_escalate"] is False
        assert "steps" not in row and res["escalated"] == 0

    @pytest.mark.asyncio
    async def test_shown_to_user_is_the_real_response_builder_output(self):
        res = await lc.run([REQ], offline="generic")
        shown = res["rows"][0]["shown_to_user"]
        assert "Here's how I read your request" in shown
        assert "1. Draft the piece; 2. Revise and polish the draft" in shown
        assert "surprise me" in shown


class TestLiveModeHonesty:
    @pytest.mark.asyncio
    async def test_all_degraded_live_run_is_never_evidence(self, monkeypatch):
        async def degraded(req):
            return {"interpretation": req, "steps": [req],
                    "degraded": ["decompose: RuntimeError"]}
        monkeypatch.setattr(lc, "_live_pair", degraded)
        res = await lc.run(["write a story"], offline="")
        assert res["mode"] == "LIVE" and res["not_evidence"] is True
        assert "NOT EVIDENCE" in lc.render(res)

    @pytest.mark.asyncio
    async def test_healthy_live_run_is_evidence(self, monkeypatch):
        async def healthy(req):
            return {"interpretation": "Write a story", "steps": ["Draft the piece"],
                    "degraded": []}
        monkeypatch.setattr(lc, "_live_pair", healthy)
        res = await lc.run(["write a story"], offline="")
        assert res["not_evidence"] is False

    def test_main_exits_2_when_live_run_is_not_evidence(self, monkeypatch, tmp_path):
        async def degraded(req):
            return {"interpretation": req, "steps": [req], "degraded": ["x"]}
        monkeypatch.setattr(lc, "_live_pair", degraded)
        f = tmp_path / "p.txt"
        f.write_text("write a story\n")
        assert lc.main(["--prompts", str(f)]) == 2

    def test_main_exits_0_offline(self):
        assert lc.main(["--offline", "single"]) == 0

    def test_sample_is_all_form_only_and_nonempty(self):
        # The built-in sample must all be requests the detector would escalate,
        # otherwise a live run silently analyses fewer cases than intended.
        assert len(lc.SAMPLE) >= 8
        for r in lc.SAMPLE:
            assert lc.ca.anchor_missing(lc.ca.detect_creative_content_anchors(r)), r
