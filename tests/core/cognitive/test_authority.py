"""
tests/core/cognitive/test_authority.py -- REM-004 taxonomy + envelope unit tests.

Scope: core/cognitive/authority.py in isolation (no Intent, no providers).
The end-to-end security properties -- injection cases, mixed origin, cache,
concurrency, replay through real Intent/Goal objects -- are in
test_intent_authority_boundary.py.

Everything here is a deterministic property of the trusted-runtime types:

  AUTH-1  authority comes from trusted origin, never from content
  AUTH-2  authority / provenance / trust / taint are distinct
  AUTH-5  authority cannot increase implicitly
  AUTH-6  unknown authority/provenance fails closed
  AUTH-7  accepted security metadata is immutable
  AUTH-9/16 serialization is deterministic and cannot raise authority

Payload strings are clearly-labeled synthetic sentinels.
"""
import dataclasses
import itertools
import json
import math

import pytest

from core.cognitive import authority as A
from core.cognitive.authority import (
    AcceptedHypothesis,
    AuthorityEscalationError,
    AuthorityForgeryError,
    AuthorityIntegrityError,
    CategoryClass,
    Disposition,
    InferenceLineage,
    InferenceOutcome,
    InstructionAuthority as IA,
    LineageInput,
    Origin,
    ProposalDisposition,
    ReasonCode,
    StaleAcceptanceError,
    assert_no_escalation,
    authority_for,
    content_digest,
    mint_model_proposal,
    mint_policy_default,
    may_influence_interpretation,
    may_instruct,
    outranks,
    resolve_conflict,
    safe_preview,
)
from core.cognitive.intent_acceptance import POLICY_VERSION, admit_label


def _lineage(scope="trace-A", with_context=True):
    inputs = [LineageInput.from_text("request", Origin.USER, "summarize the notes")]
    if with_context:
        inputs.append(LineageInput.from_text("context", Origin.RETRIEVED_SOURCE, "CONTEXT_SENTINEL_X"))
    return InferenceLineage(scope_id=scope, route="intent_interpreter",
                            template_version="t/1", prompt_digest="d" * 32,
                            inputs=tuple(inputs))


def _proposal(label="summarize notes", score=0.7, cls=CategoryClass.OPEN_CATEGORY,
              lineage=None, position=0):
    return mint_model_proposal(label=label, score=score, category_class=cls,
                               lineage=lineage or _lineage(),
                               policy_version=POLICY_VERSION, position=position)


# ── taxonomy, precedence, conflicts ─────────────────────────────────────────

class TestTaxonomy:
    def test_the_four_required_classes_exist_and_nothing_else_is_implied(self):
        assert {a.name for a in IA} == {
            "SYSTEM_POLICY", "USER_INSTRUCTION", "MODEL_PROPOSAL", "RETRIEVED_DATA"}

    def test_only_system_and_user_can_instruct(self):
        assert {a for a in IA if may_instruct(a)} == {IA.SYSTEM_POLICY, IA.USER_INSTRUCTION}
        assert not may_instruct(IA.MODEL_PROPOSAL)      # proposes, never binds
        assert not may_instruct(IA.RETRIEVED_DATA)      # informs, never instructs

    def test_precedence_is_a_strict_total_order(self):
        order = [IA.SYSTEM_POLICY, IA.USER_INSTRUCTION, IA.MODEL_PROPOSAL, IA.RETRIEVED_DATA]
        for hi, lo in itertools.combinations(order, 2):
            assert outranks(hi, lo) and not outranks(lo, hi)
        for a in IA:
            assert not outranks(a, a)

    @pytest.mark.parametrize("a,b", list(itertools.product(IA, IA)))
    def test_conflicts_resolve_to_the_higher_authority_symmetrically(self, a, b):
        winner = resolve_conflict(a, b)
        assert winner is resolve_conflict(b, a)                     # order-independent
        assert not outranks(a, winner) and not outranks(b, winner)  # nobody outranks the winner
        assert winner in (a, b)                                     # never an aggregate/average

    def test_lower_authority_cannot_reinterpret_higher_authority(self):
        assert not may_influence_interpretation(IA.RETRIEVED_DATA, IA.USER_INSTRUCTION)
        assert not may_influence_interpretation(IA.MODEL_PROPOSAL, IA.USER_INSTRUCTION)
        assert not may_influence_interpretation(IA.MODEL_PROPOSAL, IA.SYSTEM_POLICY)
        assert not may_influence_interpretation(IA.USER_INSTRUCTION, IA.SYSTEM_POLICY)
        assert may_influence_interpretation(IA.USER_INSTRUCTION, IA.MODEL_PROPOSAL)
        assert may_influence_interpretation(IA.SYSTEM_POLICY, IA.USER_INSTRUCTION)


class TestAuthorityConservation:
    @pytest.mark.parametrize("source,derived", [
        (IA.RETRIEVED_DATA, IA.USER_INSTRUCTION),
        (IA.RETRIEVED_DATA, IA.SYSTEM_POLICY),
        (IA.RETRIEVED_DATA, IA.MODEL_PROPOSAL),
        (IA.MODEL_PROPOSAL, IA.USER_INSTRUCTION),
        (IA.MODEL_PROPOSAL, IA.SYSTEM_POLICY),
        (IA.USER_INSTRUCTION, IA.SYSTEM_POLICY),
    ])
    def test_every_upward_transition_is_forbidden(self, source, derived):
        with pytest.raises(AuthorityEscalationError):
            assert_no_escalation(source, derived)

    @pytest.mark.parametrize("a,b", [(a, b) for a in IA for b in IA if not outranks(b, a)])
    def test_preserving_or_reducing_authority_is_allowed(self, a, b):
        assert_no_escalation(a, b)   # must not raise

    def test_no_promotion_api_exists(self):
        public = {n for n in dir(A) if not n.startswith("_")}
        assert not {n for n in public if "promote" in n.lower() or "elevate" in n.lower()
                    or "grant" in n.lower()}


class TestAuthorityIsDerivedFromOrigin:
    EXPECTED = {
        Origin.SYSTEM: IA.SYSTEM_POLICY,
        Origin.USER: IA.USER_INSTRUCTION,
        Origin.INTENT_MODEL: IA.MODEL_PROPOSAL,
        Origin.RETRIEVED_SOURCE: IA.RETRIEVED_DATA,
        Origin.RUNTIME_DEFAULT: IA.MODEL_PROPOSAL,
    }

    def test_every_origin_has_exactly_the_trusted_mapping(self):
        assert set(self.EXPECTED) == set(Origin)   # a new Origin forces a decision here
        for origin, authority in self.EXPECTED.items():
            assert authority_for(origin) is authority

    @pytest.mark.parametrize("bogus", ["nonsense", "user", "", None, 42, object(), ["USER"]])
    def test_unknown_origin_fails_closed_instead_of_defaulting(self, bogus):
        with pytest.raises(AuthorityForgeryError):
            authority_for(bogus)

    def test_runtime_default_never_exceeds_the_path_it_replaces(self):
        # Recovery preserves (never raises) authority.
        assert not outranks(authority_for(Origin.RUNTIME_DEFAULT),
                            authority_for(Origin.INTENT_MODEL))

    def test_no_hypothesis_can_ever_carry_user_system_or_retrieved_origin(self):
        for bad in (Origin.USER, Origin.SYSTEM, Origin.RETRIEVED_SOURCE):
            with pytest.raises(AuthorityForgeryError):
                AcceptedHypothesis(
                    label="x", score=0.5, origin=bad, authority=authority_for(bad),
                    category_class=CategoryClass.OPEN_CATEGORY, lineage=_lineage(),
                    policy_version=POLICY_VERSION, position=0,
                    binding="b", _mint=A._MINT)


# ── namespace disjointness: model strings can never equal a trusted token ────

class TestReservedNamespaceIsDisjoint:
    TRUSTED = sorted({m.value for enum in (IA, Origin, CategoryClass, Disposition,
                                           ReasonCode, InferenceOutcome) for m in enum})

    def test_every_serialized_trusted_token_is_upper_snake(self):
        for tok in self.TRUSTED:
            assert tok == tok.upper() and tok.replace("_", "").isalnum(), tok

    @pytest.mark.parametrize("token", TRUSTED)
    def test_a_model_label_equal_to_a_trusted_token_is_never_admitted(self, token):
        assert admit_label(token) is not None
        assert admit_label("novel:" + token) is not None

    @pytest.mark.parametrize("token", TRUSTED)
    def test_the_lowercase_form_is_admissible_but_can_never_equal_a_token(self, token):
        lowered = token.lower()
        assert admit_label(lowered) is None          # a legal label...
        assert lowered not in self.TRUSTED           # ...textually disjoint from every token


# ── envelope: mint guard + immutability (AUTH-7) ────────────────────────────

class TestEnvelopeImmutabilityAndMint:
    def test_direct_construction_is_refused(self):
        lin = _lineage()
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis(label="x", score=0.5, origin=Origin.INTENT_MODEL,
                               authority=IA.MODEL_PROPOSAL,
                               category_class=CategoryClass.OPEN_CATEGORY, lineage=lin,
                               policy_version=POLICY_VERSION, position=0, binding="b")

    def test_claiming_a_higher_authority_at_construction_is_refused(self):
        for claimed in (IA.USER_INSTRUCTION, IA.SYSTEM_POLICY, IA.RETRIEVED_DATA):
            with pytest.raises(AuthorityForgeryError):
                AcceptedHypothesis(label="x", score=0.5, origin=Origin.INTENT_MODEL,
                                   authority=claimed,
                                   category_class=CategoryClass.OPEN_CATEGORY,
                                   lineage=_lineage(), policy_version=POLICY_VERSION,
                                   position=0, binding="b", _mint=A._MINT)

    def test_a_model_proposal_is_always_model_proposal_whatever_it_is_labelled(self):
        for label in ("system policy", "user instruction", "trusted", "authoritative override"):
            assert _proposal(label=label).authority is IA.MODEL_PROPOSAL
            assert _proposal(label=label).origin is Origin.INTENT_MODEL

    @pytest.mark.parametrize("field,value", [
        ("authority", IA.USER_INSTRUCTION), ("origin", Origin.USER), ("score", 1.0),
        ("label", "create account"), ("policy_version", "x/9"), ("position", 9),
        ("lineage", None), ("binding", "0" * 32),
    ])
    def test_no_field_can_be_assigned_after_acceptance(self, field, value):
        p = _proposal()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(p, field, value)

    def test_dataclasses_replace_cannot_rebuild_an_accepted_proposal(self):
        p = _proposal()
        with pytest.raises(AuthorityForgeryError):
            dataclasses.replace(p, authority=IA.USER_INSTRUCTION)
        with pytest.raises(AuthorityForgeryError):
            dataclasses.replace(p, label="something else")

    def test_lineage_is_immutable_and_uses_tuples(self):
        p = _proposal()
        assert isinstance(p.lineage.inputs, tuple)
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.lineage.scope_id = "other"
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.lineage.inputs[0].authority = IA.SYSTEM_POLICY

    def test_it_is_hashable_and_equal_by_value(self):
        assert _proposal() == _proposal()
        assert len({_proposal(), _proposal()}) == 1
        assert _proposal() != _proposal(score=0.71)

    @pytest.mark.parametrize("bad_score", [-0.01, 1.01, math.nan, math.inf, -math.inf, True, "0.5", None])
    def test_scores_outside_the_contract_are_refused(self, bad_score):
        with pytest.raises(AuthorityIntegrityError):
            _proposal(score=bad_score)

    @pytest.mark.parametrize("bad_label", ["", "x" * 81, None, 5, b"x"])
    def test_labels_outside_the_bound_are_refused(self, bad_label):
        with pytest.raises(AuthorityIntegrityError):
            _proposal(label=bad_label)

    def test_policy_default_carries_only_the_fixed_token_and_inherits_authority(self):
        d = mint_policy_default(label="novel", score=0.1, lineage=_lineage(),
                                policy_version=POLICY_VERSION)
        assert d.origin is Origin.RUNTIME_DEFAULT
        assert d.category_class is CategoryClass.POLICY_DEFAULT
        assert d.authority is IA.MODEL_PROPOSAL and not may_instruct(d.authority)
        assert d.position == -1

    def test_origin_and_category_class_must_agree(self):
        with pytest.raises(AuthorityForgeryError):
            mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.POLICY_DEFAULT,
                                lineage=_lineage(), policy_version=POLICY_VERSION, position=0)


# ── lineage: per-input authority, never an aggregate ─────────────────────────

class TestLineage:
    def test_each_input_keeps_its_own_authority(self):
        lin = _lineage()
        by_role = {i.role: i.authority for i in lin.inputs}
        assert by_role == {"request": IA.USER_INSTRUCTION, "context": IA.RETRIEVED_DATA}

    def test_taint_is_retrieved_data_presence_and_not_an_authority(self):
        assert _lineage(with_context=True).retrieved_data_influence is True
        assert _lineage(with_context=False).retrieved_data_influence is False
        # tainted or not, the proposal's authority is identical: taint does not
        # convert a proposal into data, and its absence does not promote it.
        assert (_proposal(lineage=_lineage(with_context=True)).authority
                is _proposal(lineage=_lineage(with_context=False)).authority)

    def test_a_lineage_input_cannot_claim_a_role_origin_it_may_not_have(self):
        with pytest.raises(AuthorityForgeryError):
            LineageInput.from_text("context", Origin.USER, "x")          # context is never USER
        with pytest.raises(AuthorityForgeryError):
            LineageInput.from_text("request", Origin.RETRIEVED_SOURCE, "x")
        with pytest.raises(AuthorityForgeryError):
            LineageInput.from_text("nonsense", Origin.USER, "x")

    def test_authority_is_never_passed_by_the_caller_only_derived(self):
        with pytest.raises(AuthorityForgeryError):
            LineageInput(role="context", origin=Origin.RETRIEVED_SOURCE,
                         authority=IA.SYSTEM_POLICY, digest="d", size=1)

    def test_trust_scores_are_not_part_of_the_contract(self):
        names = {f.name for cls in (AcceptedHypothesis, InferenceLineage, LineageInput,
                                     ProposalDisposition) for f in dataclasses.fields(cls)}
        assert not {n for n in names if "trust" in n or "truth" in n}


# ── serialization / replay (AUTH-9, AUTH-16) ─────────────────────────────────

class TestSerializationAndReplay:
    def test_round_trip_through_json_preserves_everything(self):
        p = _proposal()
        wire = json.dumps(p.to_dict())
        back = AcceptedHypothesis.from_dict(json.loads(wire), expected_policy_version=POLICY_VERSION)
        assert back == p and back.authority is IA.MODEL_PROPOSAL
        assert back.lineage.scope_id == "trace-A" and back.retrieved_data_influence is True
        assert json.dumps(back.to_dict()) == wire                     # deterministic

    def test_serialization_is_deterministic_across_instances(self):
        assert json.dumps(_proposal().to_dict(), sort_keys=True) == \
               json.dumps(_proposal().to_dict(), sort_keys=True)

    @pytest.mark.parametrize("claimed", ["USER_INSTRUCTION", "SYSTEM_POLICY", "RETRIEVED_DATA"])
    def test_a_payload_cannot_raise_authority_by_claiming_it(self, claimed):
        d = _proposal().to_dict()
        d["authority"] = claimed
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis.from_dict(d)

    def test_forging_authority_and_origin_together_still_cannot_make_a_hypothesis_user_authored(self):
        d = _proposal().to_dict()
        d["origin"], d["authority"] = "USER", "USER_INSTRUCTION"
        with pytest.raises(AuthorityForgeryError):    # USER is not a permitted hypothesis origin
            AcceptedHypothesis.from_dict(d)

    @pytest.mark.parametrize("field,value", [
        ("label", "create account"), ("score", 1.0), ("position", 3),
        ("category_class", "KNOWN_CATEGORY"), ("policy_version", "intent-acceptance/1 "),
    ])
    def test_tampering_with_any_bound_field_is_detected(self, field, value):
        d = _proposal().to_dict()
        d[field] = value
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)

    def test_tampering_with_lineage_is_detected(self):
        d = _proposal().to_dict()
        d["lineage"]["inputs"][1]["digest"] = "forged-digest"
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)
        d = _proposal().to_dict()
        d["lineage"]["scope_id"] = "trace-B"          # cannot be re-attached to another request
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)

    def test_unknown_or_missing_metadata_fails_closed(self):
        d = _proposal().to_dict()
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict({**d, "extra_metadata": "x"})
        missing = dict(d); missing.pop("binding")
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(missing)
        for field, bad in (("origin", "GOD_MODE"), ("category_class", "TRUSTED"),
                           ("authority", "ROOT"), ("origin", 5), ("authority", None)):
            with pytest.raises(AuthorityIntegrityError):
                AcceptedHypothesis.from_dict({**d, field: bad})

    def test_a_different_policy_version_is_stale_not_silently_accepted(self):
        d = _proposal().to_dict()
        AcceptedHypothesis.from_dict(d, expected_policy_version=POLICY_VERSION)
        with pytest.raises(StaleAcceptanceError):
            AcceptedHypothesis.from_dict(d, expected_policy_version="intent-acceptance/2")

    def test_scope_binding_check(self):
        p = _proposal()
        p.assert_scope("trace-A")
        with pytest.raises(AuthorityIntegrityError):
            p.assert_scope("trace-B")

    def test_non_mapping_payloads_are_rejected(self):
        for junk in (None, [], "x", 5):
            with pytest.raises(AuthorityIntegrityError):
                AcceptedHypothesis.from_dict(junk)


class TestDispositionRecords:
    def _quarantined(self):
        return ProposalDisposition(
            position=1, disposition=Disposition.QUARANTINED,
            reason_code=ReasonCode.RESERVED_NAMESPACE, origin=Origin.INTENT_MODEL,
            authority=IA.MODEL_PROPOSAL, label_digest=content_digest("SENTINEL"),
            label_length=8, score_claim=1.0, label_preview=safe_preview("SENTINEL"))

    def test_event_view_carries_no_label_text_and_no_preview(self):
        ev = self._quarantined().to_event_dict()
        assert "label_preview" not in ev and "SENTINEL" not in json.dumps(ev)
        assert set(ev) == {"position", "disposition", "reason_code", "label_digest",
                           "label_length", "score_claim"}

    def test_only_quarantined_records_may_carry_a_preview(self):
        with pytest.raises(AuthorityIntegrityError):
            ProposalDisposition(position=0, disposition=Disposition.REJECTED,
                                reason_code=ReasonCode.LABEL_GRAMMAR, origin=Origin.INTENT_MODEL,
                                authority=IA.MODEL_PROPOSAL, label_digest="d", label_length=3,
                                score_claim=0.5, label_preview="abc")

    def test_a_disposition_can_only_describe_model_proposal_input(self):
        for origin in (Origin.USER, Origin.SYSTEM, Origin.RETRIEVED_SOURCE):
            with pytest.raises(AuthorityForgeryError):
                ProposalDisposition(position=0, disposition=Disposition.REJECTED,
                                    reason_code=ReasonCode.LABEL_GRAMMAR, origin=origin,
                                    authority=authority_for(origin), label_digest="d",
                                    label_length=3, score_claim=None)

    def test_a_disposition_is_never_an_accepted_state(self):
        with pytest.raises(AuthorityIntegrityError):
            ProposalDisposition(position=0, disposition=Disposition.ACCEPTED,
                                reason_code=ReasonCode.LABEL_GRAMMAR, origin=Origin.INTENT_MODEL,
                                authority=IA.MODEL_PROPOSAL, label_digest="d", label_length=1,
                                score_claim=None)

    def test_round_trip_and_strictness(self):
        d = self._quarantined()
        assert ProposalDisposition.from_dict(json.loads(json.dumps(d.to_dict()))) == d
        bad = d.to_dict(); bad["authority"] = "USER_INSTRUCTION"
        with pytest.raises(AuthorityForgeryError):
            ProposalDisposition.from_dict(bad)
        with pytest.raises(AuthorityIntegrityError):
            ProposalDisposition.from_dict({**d.to_dict(), "x": 1})

    def test_an_event_record_is_evidence_not_an_authority_source(self):
        # Feeding an event-shaped record to the envelope constructor must fail:
        # nothing can reconstruct an accepted proposal from evidence.
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(self._quarantined().to_event_dict())


class TestHelpers:
    def test_digest_is_deterministic_bounded_and_total(self):
        assert content_digest("a") == content_digest("a") != content_digest("b")
        assert len(content_digest("a")) == 16 and len(content_digest("a", length=32)) == 32
        content_digest("lone surrogate \ud800 must not raise")     # total on odd input

    def test_safe_preview_escapes_everything_but_printable_ascii_and_is_bounded(self):
        out = safe_preview("A\nB\x00C\u200bD\u202eE" + "x" * 100)
        assert len(out) <= 48 * 6
        assert all(32 <= ord(c) < 127 for c in out)
        assert "\\u000a" in out and "\\u200b" in out and "\\u202e" in out

    def test_the_module_holds_no_mutable_global_state(self):
        import ast, inspect
        tree = ast.parse(inspect.getsource(A))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                assert not isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp,
                                              ast.DictComp, ast.SetComp)), ast.dump(node)[:120]

    def test_safe_preview_is_hard_bounded_to_the_first_48_source_characters(self):
        # Tight, exact bounds -- a loose "<= N" would let an unbounded preview pass.
        assert safe_preview("A" * 500) == "A" * 48
        assert safe_preview("x" * 10, limit=3) == "xxx"
        assert len(safe_preview("\u2603" * 500)) == 48 * 6          # BMP escape: \uXXXX
        assert len(safe_preview("\U0001f600" * 500)) == 48 * 7      # astral: \uXXXXX
        assert len(safe_preview("\U0010ffff" * 500)) == 48 * 8      # worst case: \uXXXXXX

    def test_the_worst_case_escaped_preview_is_always_a_valid_quarantine_record(self):
        for ch in ("A", "\u2603", "\U0001f600", "\U0010ffff"):
            ProposalDisposition(
                position=0, disposition=Disposition.QUARANTINED,
                reason_code=ReasonCode.RESERVED_NAMESPACE, origin=Origin.INTENT_MODEL,
                authority=IA.MODEL_PROPOSAL, label_digest="d", label_length=500,
                score_claim=None, label_preview=safe_preview(ch * 500))

