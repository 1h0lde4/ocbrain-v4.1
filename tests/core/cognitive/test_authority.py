"""
tests/core/cognitive/test_authority.py -- REM-004 / ADR-KERNEL-06 envelope unit
tests.

Scope: core/cognitive/authority.py in isolation (no Intent, no providers). The
end-to-end properties -- injection cases, mixed origin, cache, concurrency and
replay through real Intent/Goal objects, and Mechanism A against real context
blocks -- are in test_intent_authority_boundary.py.

The authority TAXONOMY is the repository's own ``AuthorityLevel``
(core/memory/retrieval/context/context.py); these tests pin that this module
adds no parallel taxonomy and only carries envelopes, provenance and lineage.

  AUTH-1  authority comes from trusted origin / a verified source, never content
  AUTH-2  authority / provenance / trust / taint are distinct
  AUTH-5  authority cannot increase implicitly
  AUTH-6  unknown authority/provenance fails closed
  AUTH-7  accepted security metadata is immutable
  AUTH-9/16 serialization is deterministic and cannot raise authority

Payload strings are clearly-labeled synthetic sentinels.
"""
import ast
import dataclasses
import inspect
import itertools
import json
import math

import pytest

import core.cognitive.authority as A
from core.cognitive.authority import (
    REQUEST_REF,
    AcceptedHypothesis,
    AuthorityEscalationError,
    AuthorityForgeryError,
    AuthorityIntegrityError,
    CategoryClass,
    CitableBlock,
    InferenceLineage,
    InferenceOutcome,
    LineageInput,
    Origin,
    ProposalRejection,
    ProvenanceStatus,
    ReasonCode,
    StaleAcceptanceError,
    VerifiedProvenance,
    assert_no_escalation,
    authority_for,
    content_digest,
    mint_model_proposal,
    mint_policy_default,
    may_instruct,
    outranks,
    request_citable_block,
)
from core.cognitive.intent_acceptance import POLICY_VERSION
from core.memory.retrieval.context.context import AuthorityLevel as AL

LOW = (AL.RETRIEVED, AL.EXTERNAL, AL.GENERATED)


RAW_REQUEST_TEXT = "summarize the notes"


def _blocks(*authorities):
    """Context-block entries, refs "[1]", "[2]", ... (the always-present
    "request" entry is added separately by _lineage)."""
    return tuple(
        CitableBlock(ref=f"[{i + 1}]", entry_id=f"entry-{i + 1}", authority=a,
                     digest=content_digest(f"block {i + 1}"))
        for i, a in enumerate(authorities))


def _lineage(scope="trace-A", with_context=True, blocks=None, with_request=True):
    """Mirrors the real invariant (ADR-KERNEL-06): the raw request is ALWAYS
    citable. with_request=False builds a lineage that violates that
    invariant, for the tests that specifically check what happens then."""
    inputs = [LineageInput.from_text("request", Origin.USER, RAW_REQUEST_TEXT)]
    if with_context:
        inputs.append(LineageInput.from_text("context", Origin.RETRIEVED_SOURCE, "CONTEXT_SENTINEL_X"))
    if blocks is None:
        blocks = _blocks(AL.RETRIEVED, AL.RETRIEVED) if with_context else ()
    citable = ((request_citable_block(RAW_REQUEST_TEXT),) if with_request else ()) + blocks
    return InferenceLineage(scope_id=scope, route="intent_interpreter",
                            template_version="t/4", prompt_digest="d" * 32,
                            inputs=tuple(inputs), citable=citable)


def _proposal(label="summarize notes", score=0.7, cls=CategoryClass.OPEN_CATEGORY,
              lineage=None, position=0, cite=None):
    """Mint a proposal; `cite` = a ref in the lineage's table ("request" or
    "[N]") -> verified provenance."""
    lineage = lineage or _lineage()
    if cite is None:
        status, prov = ProvenanceStatus.UNCITED, None
    else:
        status = ProvenanceStatus.VERIFIED
        prov = VerifiedProvenance.from_block(lineage.resolve(cite))
    return mint_model_proposal(label=label, score=score, category_class=cls,
                               provenance_status=status, provenance=prov,
                               lineage=lineage, policy_version=POLICY_VERSION,
                               position=position)


# ── the taxonomy is the repository's own ─────────────────────────────────────

class TestTheTaxonomyIsTheRepositorys:
    def test_no_parallel_authority_enum_exists(self):
        assert not hasattr(A, "InstructionAuthority")
        assert A.AuthorityLevel is AL                     # the one from context.py
        assert {m.name for m in AL} == {"SYSTEM", "USER", "RETRIEVED", "EXTERNAL", "GENERATED"}

    def test_only_system_and_user_can_instruct(self):
        assert {a for a in AL if may_instruct(a)} == {AL.SYSTEM, AL.USER}
        for a in LOW:
            assert not may_instruct(a)        # they inform or propose; they never bind

    def test_precedence_is_a_partial_order_with_no_invented_order_among_the_low_levels(self):
        assert outranks(AL.SYSTEM, AL.USER)
        for low in LOW:
            assert outranks(AL.SYSTEM, low) and outranks(AL.USER, low)
            assert not outranks(low, AL.USER) and not outranks(low, AL.SYSTEM)
        for a, b in itertools.permutations(LOW, 2):
            assert not outranks(a, b)         # AuthorityLevel defines no order among these
        for a in AL:
            assert not outranks(a, a)

    @pytest.mark.parametrize("source,derived",
                             [(s, d) for s in AL for d in AL if outranks(d, s)])
    def test_every_upward_transition_is_forbidden(self, source, derived):
        with pytest.raises(AuthorityEscalationError):
            assert_no_escalation(source, derived)

    @pytest.mark.parametrize("source,derived",
                             [(s, d) for s in AL for d in AL if not outranks(d, s)])
    def test_preserving_or_lowering_authority_is_allowed(self, source, derived):
        assert_no_escalation(source, derived)

    def test_no_promotion_api_exists(self):
        public = {n.lower() for n in dir(A) if not n.startswith("_")}
        assert not {n for n in public if "promote" in n or "elevate" in n or "grant" in n}


class TestAuthorityIsDerivedFromOrigin:
    EXPECTED = {
        Origin.SYSTEM: AL.SYSTEM, Origin.USER: AL.USER,
        Origin.INTENT_MODEL: AL.GENERATED, Origin.RETRIEVED_SOURCE: AL.RETRIEVED,
        Origin.RUNTIME_DEFAULT: AL.GENERATED,
    }

    def test_every_origin_has_exactly_the_trusted_mapping(self):
        assert set(self.EXPECTED) == set(Origin)      # a new Origin forces a decision here
        for origin, level in self.EXPECTED.items():
            assert authority_for(origin) is level

    def test_unknown_origin_fails_closed_instead_of_defaulting(self):
        for bogus in ("nonsense", "user", "USER ", "", None, 42, object(), []):
            with pytest.raises(AuthorityForgeryError):
                authority_for(bogus)
        assert authority_for("USER") is AL.USER       # the exact trusted token resolves

    def test_a_model_and_its_recovery_default_share_the_non_instructing_class(self):
        assert authority_for(Origin.INTENT_MODEL) is authority_for(Origin.RUNTIME_DEFAULT) is AL.GENERATED

    @pytest.mark.parametrize("bad", [Origin.USER, Origin.SYSTEM, Origin.RETRIEVED_SOURCE])
    def test_no_hypothesis_can_ever_carry_user_system_or_retrieved_origin(self, bad):
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis(
                label="x", score=0.5, origin=bad, authority=authority_for(bad),
                category_class=CategoryClass.OPEN_CATEGORY,
                provenance_status=ProvenanceStatus.UNCITED, provenance=None,
                lineage=_lineage(), policy_version=POLICY_VERSION, position=0,
                binding="b", _mint=A._MINT)


# ── envelope: mint guard + immutability (AUTH-7) ─────────────────────────────

class TestEnvelopeImmutabilityAndMint:
    def test_direct_construction_is_refused(self):
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis(label="x", score=0.5, origin=Origin.INTENT_MODEL,
                               authority=AL.GENERATED,
                               category_class=CategoryClass.OPEN_CATEGORY,
                               provenance_status=ProvenanceStatus.UNCITED, provenance=None,
                               lineage=_lineage(), policy_version=POLICY_VERSION,
                               position=0, binding="b")

    @pytest.mark.parametrize("claimed", [AL.USER, AL.SYSTEM, AL.RETRIEVED, AL.EXTERNAL])
    def test_claiming_a_different_authority_at_construction_is_refused(self, claimed):
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis(label="x", score=0.5, origin=Origin.INTENT_MODEL,
                               authority=claimed,
                               category_class=CategoryClass.OPEN_CATEGORY,
                               provenance_status=ProvenanceStatus.UNCITED, provenance=None,
                               lineage=_lineage(), policy_version=POLICY_VERSION,
                               position=0, binding="b", _mint=A._MINT)

    @pytest.mark.parametrize("label", ["system", "user instruction", "trusted", "authoritative",
                                       "override", "SYSTEM_POLICY", "USER", "generated"])
    def test_a_proposal_is_always_generated_whatever_it_is_labelled(self, label):
        p = _proposal(label=label)
        assert p.authority is AL.GENERATED and not may_instruct(p.authority)
        assert p.origin is Origin.INTENT_MODEL

    @pytest.mark.parametrize("field,value", [
        ("authority", AL.USER), ("origin", Origin.USER), ("score", 1.0), ("label", "create account"),
        ("policy_version", "x/9"), ("position", 9), ("lineage", None), ("binding", "0" * 32),
        ("provenance_status", ProvenanceStatus.VERIFIED), ("provenance", None),
    ])
    def test_no_field_can_be_assigned_after_acceptance(self, field, value):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(_proposal(), field, value)

    def test_dataclasses_replace_cannot_rebuild_an_accepted_proposal(self):
        p = _proposal()
        for change in ({"authority": AL.USER}, {"label": "something else"},
                       {"provenance_status": ProvenanceStatus.VERIFIED}):
            with pytest.raises(AuthorityForgeryError):
                dataclasses.replace(p, **change)

    def test_lineage_and_table_are_immutable_tuples(self):
        p = _proposal()
        assert isinstance(p.lineage.inputs, tuple) and isinstance(p.lineage.citable, tuple)
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.lineage.scope_id = "other"
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.lineage.citable[0].authority = AL.SYSTEM
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.lineage.inputs[0].authority = AL.SYSTEM

    def test_it_is_hashable_and_equal_by_value(self):
        assert _proposal() == _proposal() and len({_proposal(), _proposal()}) == 1
        assert _proposal() != _proposal(score=0.71)

    @pytest.mark.parametrize("bad_score", [-0.01, 1.01, math.nan, math.inf, -math.inf, True, "0.5", None])
    def test_scores_outside_the_contract_are_refused(self, bad_score):
        with pytest.raises(AuthorityIntegrityError):
            _proposal(score=bad_score)

    @pytest.mark.parametrize("bad_label", ["", "x" * 201, None, 5, b"x"])
    def test_labels_outside_the_bound_are_refused(self, bad_label):
        with pytest.raises(AuthorityIntegrityError):
            _proposal(label=bad_label)

    def test_any_label_shape_within_the_bound_is_representable(self):
        # ADR-KERNEL-06 rules out shape as an authority proxy: the envelope
        # imposes only a resource bound, never a form.
        for label in ("SYSTEM_POLICY", "novel:CONTEXT_SENTINEL_INJECTED", "Ünïcode \u200b label",
                      "**md** `code`", "a|b", "x" * 200):
            assert _proposal(label=label).authority is AL.GENERATED

    def test_policy_default_carries_only_the_fixed_token_and_inherits_authority(self):
        d = mint_policy_default(label="novel", score=0.1, lineage=_lineage(),
                                policy_version=POLICY_VERSION)
        assert d.origin is Origin.RUNTIME_DEFAULT and d.position == -1
        assert d.category_class is CategoryClass.POLICY_DEFAULT
        assert d.provenance_status is ProvenanceStatus.NOT_APPLICABLE and d.provenance is None
        assert d.authority is AL.GENERATED and not may_instruct(d.authority)

    def test_origin_and_category_class_must_agree(self):
        with pytest.raises(AuthorityForgeryError):
            mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.POLICY_DEFAULT,
                                provenance_status=ProvenanceStatus.UNCITED, provenance=None,
                                lineage=_lineage(), policy_version=POLICY_VERSION, position=0)


# ── verified provenance (ADR-KERNEL-06, Mechanism A) ─────────────────────────

class TestVerifiedProvenance:
    def test_a_verified_proposal_inherits_the_source_blocks_authority(self):
        p = _proposal(cite="[2]")
        assert p.provenance_status is ProvenanceStatus.VERIFIED and p.has_verified_provenance
        assert (p.provenance.ref, p.provenance.source_id) == ("[2]", "entry-2")
        assert p.provenance.authority is AL.RETRIEVED          # inherited from the block
        assert p.authority is AL.GENERATED                     # its OWN class is unchanged

    @pytest.mark.parametrize("block_authority", [AL.USER, AL.SYSTEM])
    def test_even_a_verified_source_that_can_instruct_does_not_make_the_proposal_instruct(self, block_authority):
        # If a trusted construction site ever assigned an instruction-bearing
        # authority to a block, the provenance records it faithfully -- but a
        # model-generated proposal never becomes instruction-bearing itself.
        lin = _lineage(blocks=_blocks(block_authority))
        p = _proposal(lineage=lin, cite="[1]")
        assert p.provenance.authority is block_authority
        assert p.authority is AL.GENERATED and not may_instruct(p.authority)

    def test_provenance_that_is_not_in_this_requests_table_is_a_forgery(self):
        lin = _lineage()
        for prov in (
            VerifiedProvenance(ref="[9]", source_id="entry-9", authority=AL.RETRIEVED, block_digest="d"),
            VerifiedProvenance(ref="[1]", source_id="entry-OTHER", authority=AL.RETRIEVED,
                               block_digest=content_digest("block 1")),
            VerifiedProvenance(ref="[1]", source_id="entry-1", authority=AL.SYSTEM,       # raised authority
                               block_digest=content_digest("block 1")),
            VerifiedProvenance(ref="[1]", source_id="entry-1", authority=AL.RETRIEVED,
                               block_digest="not-the-blocks-digest"),
        ):
            with pytest.raises(AuthorityForgeryError):
                mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.OPEN_CATEGORY,
                                    provenance_status=ProvenanceStatus.VERIFIED, provenance=prov,
                                    lineage=lin, policy_version=POLICY_VERSION, position=0)

    def test_status_and_provenance_must_agree(self):
        lin = _lineage()
        prov = VerifiedProvenance.from_block(lin.resolve("[1]"))
        with pytest.raises(AuthorityForgeryError):       # VERIFIED with nothing to show
            mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.OPEN_CATEGORY,
                                provenance_status=ProvenanceStatus.VERIFIED, provenance=None,
                                lineage=lin, policy_version=POLICY_VERSION, position=0)
        for status in (ProvenanceStatus.UNCITED, ProvenanceStatus.UNRESOLVED_CITATION,
                       ProvenanceStatus.MALFORMED_CITATION, ProvenanceStatus.AMBIGUOUS_CITATION):
            with pytest.raises(AuthorityForgeryError):   # provenance without VERIFIED
                mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.OPEN_CATEGORY,
                                    provenance_status=status, provenance=prov,
                                    lineage=lin, policy_version=POLICY_VERSION, position=0)

    def test_not_applicable_is_reserved_for_the_runtime_default(self):
        with pytest.raises(AuthorityForgeryError):
            mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.OPEN_CATEGORY,
                                provenance_status=ProvenanceStatus.NOT_APPLICABLE, provenance=None,
                                lineage=_lineage(), policy_version=POLICY_VERSION, position=0)

    def test_every_unverified_status_means_the_same_thing_no_provenance(self):
        for status in (ProvenanceStatus.UNCITED, ProvenanceStatus.MALFORMED_CITATION,
                       ProvenanceStatus.UNRESOLVED_CITATION, ProvenanceStatus.AMBIGUOUS_CITATION):
            p = mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.OPEN_CATEGORY,
                                    provenance_status=status, provenance=None, lineage=_lineage(),
                                    policy_version=POLICY_VERSION, position=0)
            assert p.provenance is None and not p.has_verified_provenance and p.authority is AL.GENERATED

    def test_the_citation_table_is_bound_into_the_proposal(self):
        a = _proposal(cite="[1]")
        b = _proposal(cite="[1]", lineage=_lineage(blocks=_blocks(AL.EXTERNAL, AL.RETRIEVED)))
        assert a.binding != b.binding


# ── the raw request as a citable source (ADR-KERNEL-06 Mechanism A) ─────────

class TestRequestCitation:
    """The one mechanism by which a model proposal can carry USER-authority
    provenance: citing "request", context.py's own definition of USER --
    "the current turn's actual human instruction". Always resolves (the
    request always exists); the residual self-report risk that follows from
    that is the documented, ADR-named trigger for evaluating Option C, not
    something this module can close (see live_citation_check.py)."""

    def test_the_helper_assigns_exactly_user_authority_and_nothing_else(self):
        b = request_citable_block("hello world")
        assert (b.ref, b.entry_id, b.authority) == (REQUEST_REF, REQUEST_REF, AL.USER)
        assert b.digest == content_digest("hello world")

    def test_it_is_not_parameterizable_to_any_other_authority(self):
        import inspect
        assert list(inspect.signature(request_citable_block).parameters) == ["request_text"]

    def test_citing_request_verifies_and_inherits_user_the_only_instruction_bearing_case_today(self):
        p = _proposal(cite="request")
        assert p.provenance_status is ProvenanceStatus.VERIFIED and p.provenance.authority is AL.USER
        assert may_instruct(p.provenance.authority)
        assert p.authority is AL.GENERATED                    # the envelope's OWN class never changes

    def test_the_digest_is_bound_to_the_actual_request_text_not_a_fixed_placeholder(self):
        a = request_citable_block("alpha"); b = request_citable_block("beta")
        assert a.digest != b.digest and a.ref == b.ref == REQUEST_REF

    def test_a_payload_cannot_repoint_a_request_citation_at_a_block_or_vice_versa(self):
        lin = _lineage(blocks=_blocks(AL.RETRIEVED))
        d = _proposal(lineage=lin, cite="request").to_dict()
        d["provenance"] = VerifiedProvenance.from_block(lin.resolve("[1]")).to_dict()
        with pytest.raises(AuthorityIntegrityError):           # binding no longer matches
            AcceptedHypothesis.from_dict(d)
        d = _proposal(lineage=lin, cite="[1]").to_dict()
        d["provenance"] = VerifiedProvenance.from_block(lin.resolve("request")).to_dict()
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)

    def test_forging_a_higher_authority_onto_the_request_entry_itself_is_still_caught(self):
        # request is already USER (cannot go higher without becoming SYSTEM);
        # tampering the table to claim SYSTEM must still be detected -- the
        # proposal's OWN recorded provenance (USER) no longer matches the
        # (now-forged) table entry, so this is a forgery, not mere corruption.
        d = _proposal(cite="request").to_dict()
        d["lineage"]["citable"][0]["authority"] = "system"
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis.from_dict(d)

    def test_without_the_request_entry_citing_request_does_not_resolve(self):
        # authority.py itself does not inject request_citable_block(); that
        # invariant belongs to intent.py's construction code (tested in
        # test_intent_authority_boundary.py). Here: if it is missing, "request"
        # is simply an unresolved pointer like any other -- fails closed, not open.
        lin = _lineage(with_request=False)
        assert lin.resolve("request") is None
        p = mint_model_proposal(label="x", score=0.5, category_class=CategoryClass.OPEN_CATEGORY,
                                provenance_status=ProvenanceStatus.UNRESOLVED_CITATION, provenance=None,
                                lineage=lin, policy_version=POLICY_VERSION, position=0)
        assert p.provenance is None and p.authority is AL.GENERATED

    def test_a_context_block_never_verifies_as_user_even_if_a_construction_site_mislabels_it(self):
        # Distinguishes "the request itself" from "a block that merely claims
        # to be user-authored": only ref==REQUEST_REF is ever request-level;
        # a block's own ref (a bracketed index) never is, regardless of the
        # AuthorityLevel a (hypothetically mislabeled) construction site gave it.
        lin = _lineage(blocks=_blocks(AL.USER))
        p = _proposal(lineage=lin, cite="[1]")
        assert p.provenance.ref == "[1]" and p.provenance.authority is AL.USER
        # It DOES faithfully report AL.USER here (garbage in, faithfully out) --
        # but it is attributed to a BLOCK, never to request_citable_block()'s
        # own fixed, request-text-bound digest.
        assert p.provenance.source_id == "entry-1" != REQUEST_REF


# ── lineage: per-input authority, never an aggregate ─────────────────────────

class TestLineage:
    def test_each_input_keeps_its_own_authority(self):
        by_role = {i.role: i.authority for i in _lineage().inputs}
        assert by_role == {"request": AL.USER, "context": AL.RETRIEVED}

    def test_taint_is_retrieved_data_presence_and_not_an_authority(self):
        assert _lineage(with_context=True).retrieved_data_influence is True
        assert _lineage(with_context=False).retrieved_data_influence is False
        assert (_proposal(lineage=_lineage(with_context=True)).authority
                is _proposal(lineage=_lineage(with_context=False)).authority is AL.GENERATED)

    def test_a_lineage_input_cannot_claim_a_role_origin_it_may_not_have(self):
        with pytest.raises(AuthorityForgeryError):
            LineageInput.from_text("context", Origin.USER, "x")
        with pytest.raises(AuthorityForgeryError):
            LineageInput.from_text("request", Origin.RETRIEVED_SOURCE, "x")
        with pytest.raises(AuthorityForgeryError):
            LineageInput.from_text("nonsense", Origin.USER, "x")

    def test_authority_is_never_passed_by_the_caller_only_derived(self):
        with pytest.raises(AuthorityForgeryError):
            LineageInput(role="context", origin=Origin.RETRIEVED_SOURCE,
                         authority=AL.SYSTEM, digest="d", size=1)

    def test_citable_refs_are_unique_bounded_and_well_formed(self):
        block = _blocks(AL.RETRIEVED)[0]
        with pytest.raises(AuthorityIntegrityError):
            _lineage(blocks=(block, block))                     # duplicate ref
        # exactly two legitimate shapes: "request", or a bracketed positive int
        for good in ("request", "[1]", "[23]", "[999]"):
            CitableBlock(ref=good, entry_id="e", authority=AL.RETRIEVED, digest="d")
        for bad in ("[0]", "[01]", "[1000]", " [1]", "[1] ", "[1],[2]", "REQUEST",
                   "Request", " request", "request ", "s1", "S1", "1", "[]", "", "()"):
            with pytest.raises(AuthorityIntegrityError):
                CitableBlock(ref=bad, entry_id="e", authority=AL.RETRIEVED, digest="d")
        with pytest.raises(AuthorityIntegrityError):
            CitableBlock(ref="[1]", entry_id="e", authority="retrieved", digest="d")   # not an AuthorityLevel

    def test_request_is_a_bare_reserved_ref_never_collides_with_a_block_index(self):
        # A real block can never legitimately be numbered "request" -- the
        # shapes are disjoint by construction (digits-in-brackets vs. the bare
        # word), so a request_citable_block() can always be told apart from
        # any context block, however many blocks a request has.
        lin = InferenceLineage(scope_id="s", route="r", template_version="t",
                               prompt_digest="d" * 32, inputs=(),
                               citable=(request_citable_block("hi"),) + _blocks(*([AL.RETRIEVED] * 5)))
        assert lin.resolve("request").entry_id == REQUEST_REF
        assert [b.ref for b in lin.citable] == ["request"] + [f"[{i}]" for i in range(1, 6)]

    def test_resolve_is_an_exact_lookup(self):
        lin = _lineage()
        assert lin.resolve("[1]").entry_id == "entry-1" and lin.resolve("[2]").entry_id == "entry-2"
        for miss in ("[3]", "s1", " S1", "S1 ", "S01", "", "entry-1"):
            assert lin.resolve(miss) is None

    def test_trust_scores_are_not_part_of_the_contract(self):
        names = {f.name for cls in (AcceptedHypothesis, InferenceLineage, LineageInput,
                                     CitableBlock, VerifiedProvenance, ProposalRejection)
                 for f in dataclasses.fields(cls)}
        assert not {n for n in names if "trust" in n or "truth" in n}


# ── serialization / replay (AUTH-9, AUTH-16) ─────────────────────────────────

class TestSerializationAndReplay:
    @pytest.mark.parametrize("cite", [None, "[1]", "[2]"])
    def test_round_trip_through_json_preserves_everything(self, cite):
        p = _proposal(cite=cite)
        wire = json.dumps(p.to_dict())
        back = AcceptedHypothesis.from_dict(json.loads(wire), expected_policy_version=POLICY_VERSION)
        assert back == p and back.authority is AL.GENERATED
        assert back.provenance == p.provenance and back.lineage.citable == p.lineage.citable
        assert json.dumps(back.to_dict()) == wire                    # deterministic

    @pytest.mark.parametrize("claimed", ["user", "system", "retrieved", "external"])
    def test_a_payload_cannot_raise_authority_by_claiming_it(self, claimed):
        d = _proposal().to_dict()
        d["authority"] = claimed
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis.from_dict(d)

    def test_forging_authority_and_origin_together_still_cannot_make_a_hypothesis_user_authored(self):
        d = _proposal().to_dict()
        d["origin"], d["authority"] = "USER", "user"
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis.from_dict(d)

    @pytest.mark.parametrize("field,value", [
        ("label", "create account"), ("score", 1.0), ("position", 3),
        ("category_class", "KNOWN_CATEGORY"), ("policy_version", "intent-acceptance/2 "),
    ])
    def test_tampering_with_any_bound_field_is_detected(self, field, value):
        d = _proposal().to_dict()
        d[field] = value
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)

    def test_a_payload_cannot_grant_itself_verified_provenance(self):
        d = _proposal().to_dict()                                    # UNCITED
        d["provenance_status"] = "VERIFIED"
        d["provenance"] = VerifiedProvenance.from_block(_lineage().resolve("[1]")).to_dict()
        with pytest.raises(AuthorityIntegrityError):                 # binding no longer matches
            AcceptedHypothesis.from_dict(d)

    def test_a_payload_cannot_repoint_a_verified_citation_to_another_block_in_its_own_blocks(self):
        # S2 is a REAL block of the same request, so the table check alone would pass:
        # only the binding digest ties the proposal to the citation it actually made.
        d = _proposal(cite="[1]").to_dict()
        d["provenance"] = VerifiedProvenance.from_block(_lineage().resolve("[2]")).to_dict()
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)
        # ...and the repointing is detected even when the two blocks differ in authority.
        lin = _lineage(blocks=_blocks(AL.RETRIEVED, AL.EXTERNAL))
        d = _proposal(lineage=lin, cite="[1]").to_dict()
        d["provenance"] = VerifiedProvenance.from_block(lin.resolve("[2]")).to_dict()
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)

    def test_a_payload_cannot_raise_a_provenance_authority_or_point_outside_its_blocks(self):
        d = _proposal(cite="[1]").to_dict()
        d["provenance"]["authority"] = "system"                      # not the block's own authority
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis.from_dict(d)
        d = _proposal(cite="[1]").to_dict()
        d["provenance"]["ref"] = "[9]"                                # not in this request's table
        with pytest.raises(AuthorityForgeryError):
            AcceptedHypothesis.from_dict(d)

    def test_tampering_with_lineage_or_the_citation_table_is_detected(self):
        d = _proposal(cite="[1]").to_dict()
        d["lineage"]["inputs"][1]["digest"] = "forged-digest"
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)
        d = _proposal(cite="[1]").to_dict()
        d["lineage"]["scope_id"] = "trace-B"                         # cannot be re-attached to another request
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)
        # citable[0] is always the "request" entry (see _lineage); [1] is the
        # first real context block.
        d = _proposal(cite="[1]").to_dict()
        d["lineage"]["citable"][1]["authority"] = "user"              # forge the BLOCK's authority:
        with pytest.raises(AuthorityForgeryError):                    # the cited provenance no longer matches
            AcceptedHypothesis.from_dict(d)
        d = _proposal().to_dict()                                     # ...and for an UNCITED proposal the
        d["lineage"]["citable"][1]["authority"] = "user"               # forged table breaks the binding
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)
        d = _proposal(cite="[1]").to_dict()
        d["lineage"]["citable"].append(d["lineage"]["citable"][0])   # duplicate ref
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(d)

    def test_unknown_or_missing_metadata_fails_closed(self):
        d = _proposal().to_dict()
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict({**d, "extra_metadata": "x"})
        missing = dict(d); missing.pop("binding")
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(missing)
        for field, bad in (("origin", "GOD_MODE"), ("category_class", "TRUSTED"), ("authority", "root"),
                           ("provenance_status", "TRUSTED"), ("origin", 5), ("authority", None)):
            with pytest.raises(AuthorityIntegrityError):
                AcceptedHypothesis.from_dict({**d, field: bad})

    def test_a_different_policy_version_is_stale_not_silently_accepted(self):
        d = _proposal().to_dict()
        AcceptedHypothesis.from_dict(d, expected_policy_version=POLICY_VERSION)
        with pytest.raises(StaleAcceptanceError):
            AcceptedHypothesis.from_dict(d, expected_policy_version="intent-acceptance/9")

    def test_scope_binding_check(self):
        p = _proposal()
        p.assert_scope("trace-A")
        with pytest.raises(AuthorityIntegrityError):
            p.assert_scope("trace-B")

    @pytest.mark.parametrize("junk", [None, [], "x", 5])
    def test_non_mapping_payloads_are_rejected(self, junk):
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(junk)

    def test_a_non_serializable_field_fails_closed_as_an_integrity_error(self):
        with pytest.raises(AuthorityIntegrityError):
            _proposal(label=object(), score=object())


class TestRejectionRecords:
    def _r(self, **kw):
        base = dict(position=1, reason_code=ReasonCode.DUPLICATE_LABEL, origin=Origin.INTENT_MODEL,
                    authority=AL.GENERATED, label_digest=content_digest("SENTINEL"),
                    label_length=8, score_claim=1.0)
        base.update(kw)
        return ProposalRejection(**base)

    def test_records_hold_a_digest_and_a_length_never_label_text(self):
        r = self._r()
        assert "SENTINEL" not in json.dumps(r.to_dict()) and "SENTINEL" not in json.dumps(r.to_event_dict())
        assert set(r.to_event_dict()) == {"position", "reason_code", "label_digest",
                                          "label_length", "score_claim"}

    def test_a_rejection_can_only_describe_model_generated_input(self):
        for origin in (Origin.USER, Origin.SYSTEM, Origin.RETRIEVED_SOURCE):
            with pytest.raises(AuthorityForgeryError):
                self._r(origin=origin, authority=authority_for(origin))
        with pytest.raises(AuthorityForgeryError):
            self._r(authority=AL.USER)

    def test_round_trip_and_strictness(self):
        r = self._r()
        assert ProposalRejection.from_dict(json.loads(json.dumps(r.to_dict()))) == r
        bad = r.to_dict(); bad["authority"] = "user"
        with pytest.raises(AuthorityForgeryError):
            ProposalRejection.from_dict(bad)
        with pytest.raises(AuthorityIntegrityError):
            ProposalRejection.from_dict({**r.to_dict(), "x": 1})

    def test_an_event_record_is_evidence_not_an_authority_source(self):
        with pytest.raises(AuthorityIntegrityError):
            AcceptedHypothesis.from_dict(self._r().to_event_dict())


class TestHelpers:
    def test_digest_is_deterministic_bounded_and_total(self):
        assert content_digest("a") == content_digest("a") != content_digest("b")
        assert len(content_digest("a")) == 16 and len(content_digest("a", length=32)) == 32
        content_digest("lone surrogate \ud800 must not raise")

    def test_the_module_holds_no_mutable_global_state(self):
        tree = ast.parse(inspect.getsource(A))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                assert not isinstance(node.value, (ast.List, ast.Dict, ast.Set, ast.ListComp,
                                                   ast.DictComp, ast.SetComp)), ast.dump(node)[:120]

    def test_outcome_and_reason_vocabularies_are_closed(self):
        assert {o.name for o in InferenceOutcome} == {
            "ACCEPTED", "NO_OUTPUT", "PROVIDER_FAILURE", "PARSE_FAILURE", "ALL_REJECTED", "INTERNAL_ERROR"}
        assert {r.name for r in ReasonCode} == {
            "SCORE_INVALID", "DUPLICATE_LABEL", "CANDIDATE_LIMIT", "LABEL_INVALID"}
