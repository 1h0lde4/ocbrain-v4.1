"""
Contract tests for Phase C Verification System types.

These test the CONTRACTS -- validation rules and structural
invariants -- not verification behavior, per the Phase C scope
boundary (no strategy execution, no LLM calls, no runtime workers).
"""
from datetime import datetime, timezone

import pytest

from core.verification.identity import new_id
from core.verification.epistemic import (
    BasisComponent, VerificationBasis, ObservationAuthority,
    InspectionAuthorization, VerificationAssurance,
)
from core.verification.evidence import (
    EvidenceSource, EvidenceItem, EvidenceDirectness, EvidenceStatus,
    CircularEvidenceError, check_not_circular,
)
from core.verification.verdict import (
    VerificationVerdict, VerificationExecutionFailure, VerificationResult,
)
from core.verification.receipt import VerificationReceipt, Replayability
from core.verification.shape import (
    VerificationShape, ComparisonOutcome, ComparisonRelation,
    ConsistencyStatus, PairwiseConsistency,
)
from core.verification.policy import (
    VerificationProfileName, VerificationRequirements, VerificationPolicy,
    VerificationStrategy, VerificationProfile,
)
from core.verification.target import VerificationTargetFingerprint, VerificationTargetSnapshot
from core.verification.dimension import StateVerification, TransitionVerification, InvariantVerification
from core.verification.retention import RetentionRule, EvidenceRetention, ReceiptRetention, SourceRetention
from core.verification.control import ControlType, ControlCase


def _basis(*components):
    return VerificationBasis(frozenset(components))


def _assurance(**overrides):
    defaults = dict(
        basis=_basis(BasisComponent.DETERMINISTIC),
        observation_authority=ObservationAuthority.FILESYSTEM,
        inspection_authorization=InspectionAuthorization(surface="fs:/tmp", authorized=True),
        assurance_scope="artifact_existence",
        coverage=1.0,
        independence_level="single_verifier",
        integrity_verified=True,
    )
    defaults.update(overrides)
    return VerificationAssurance(**defaults)


class TestVerificationBasisIsCompositional:
    """This is the exact bug the v1->v2 architecture correction fixed:
    v1 modeled Basis as a single exclusive enum, which cannot
    represent a verification that is simultaneously deterministic AND
    runtime-observed."""

    def test_single_component_allowed(self):
        b = _basis(BasisComponent.DETERMINISTIC)
        assert b.is_deterministic_only

    def test_multiple_components_allowed(self):
        b = _basis(BasisComponent.DETERMINISTIC, BasisComponent.RUNTIME_OBSERVATION)
        assert b.has(BasisComponent.DETERMINISTIC)
        assert b.has(BasisComponent.RUNTIME_OBSERVATION)
        assert not b.is_deterministic_only

    def test_empty_basis_rejected(self):
        with pytest.raises(ValueError):
            VerificationBasis(frozenset())


class TestAssuranceMustBeScoped:
    def test_missing_scope_rejected(self):
        with pytest.raises(ValueError):
            _assurance(assurance_scope="")

    def test_coverage_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            _assurance(coverage=1.5)

    def test_unauthorized_surface_rejected(self):
        with pytest.raises(ValueError):
            _assurance(inspection_authorization=InspectionAuthorization(surface="fs:/etc/shadow", authorized=False))


class TestCircularEvidenceRejected:
    """Architecture v2 Part 2 §17 -- new this round, not redundant
    with 'self-report != proof': this is about the STRUCTURE of the
    claim/evidence graph being circular, checked mechanically."""

    def test_restatement_of_claim_rejected(self):
        claim_id = new_id()
        ev = EvidenceItem(
            evidence_id=new_id(),
            source=EvidenceSource(source_type="agent_assertion", source_id="agent-1", producer="agent"),
            locator="chat:turn-4",
            directness=EvidenceDirectness.MODEL_INTERPRETATION,
            status=EvidenceStatus.SUFFICIENT,
            observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc),
            content_summary='agent says "X is true"',
            supports_claim_ids=(claim_id,),
            is_restatement_of_claim=True,
        )
        with pytest.raises(CircularEvidenceError):
            check_not_circular(claim_id, ev)

    def test_genuine_evidence_accepted(self):
        claim_id = new_id()
        ev = EvidenceItem(
            evidence_id=new_id(),
            source=EvidenceSource(source_type="filesystem", source_id="fs", producer="runtime"),
            locator="/repo/output.txt",
            directness=EvidenceDirectness.DIRECT,
            status=EvidenceStatus.SUFFICIENT,
            observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc),
            content_summary="file exists, 1024 bytes",
            supports_claim_ids=(claim_id,),
            is_restatement_of_claim=False,
        )
        check_not_circular(claim_id, ev)  # must not raise


class TestVerifierCrashCannotBecomePass:
    def test_execution_failure_with_positive_verdict_rejected(self):
        with pytest.raises(ValueError):
            VerificationResult(
                verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
                attempt_id=new_id(), verdict=VerificationVerdict.VERIFIED,
                assurance=_assurance(), confidence=0.9,
                execution_failure=VerificationExecutionFailure.VERIFIER_CRASH,
            )

    def test_execution_failure_with_unverifiable_accepted(self):
        r = VerificationResult(
            verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
            attempt_id=new_id(), verdict=VerificationVerdict.UNVERIFIABLE,
            assurance=_assurance(), confidence=0.0,
            execution_failure=VerificationExecutionFailure.VERIFIER_CRASH,
        )
        assert r.verdict == VerificationVerdict.UNVERIFIABLE


class TestReceiptImmutability:
    def _make_result(self):
        return VerificationResult(
            verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
            attempt_id=new_id(), verdict=VerificationVerdict.VERIFIED,
            assurance=_assurance(), confidence=0.95,
        )

    def test_supersession_returns_new_object_original_untouched(self):
        result = self._make_result()
        r1 = VerificationReceipt(
            receipt_id=new_id(), verification_id=result.verification_id,
            result=result, issued_at=datetime.now(timezone.utc),
            replayability=Replayability.FULLY_REPLAYABLE,
        )
        new_receipt_id = new_id()
        r2 = r1.superseded_by(new_receipt_id)
        assert r1.superseded_by_receipt_id is None       # original is untouched
        assert r2.superseded_by_receipt_id == new_receipt_id
        assert r1 is not r2

    def test_receipt_fields_cannot_be_reassigned(self):
        result = self._make_result()
        r = VerificationReceipt(
            receipt_id=new_id(), verification_id=result.verification_id,
            result=result, issued_at=datetime.now(timezone.utc),
            replayability=Replayability.FULLY_REPLAYABLE,
        )
        with pytest.raises(Exception):
            r.receipt_id = "tampered"


class TestVerificationShapeIsOrthogonal:
    """VerificationShape is independent of method/dimension -- an enum with a sensible default."""

    def test_all_three_shapes_exist(self):
        assert {VerificationShape.POINTWISE, VerificationShape.PAIRWISE, VerificationShape.SET_LEVEL} == set(VerificationShape)


class TestComparisonRelation:
    def test_decisive_outcomes(self):
        for outcome in (ComparisonOutcome.A_PREFERRED, ComparisonOutcome.B_PREFERRED):
            c = ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="b", outcome=outcome)
            assert c.is_decisive

    def test_non_decisive_outcomes(self):
        for outcome in (ComparisonOutcome.TIE, ComparisonOutcome.INCOMPARABLE):
            c = ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="b", outcome=outcome)
            assert not c.is_decisive

    def test_empty_comparison_id_rejected(self):
        with pytest.raises(ValueError):
            ComparisonRelation(comparison_id="", target_a_id="a", target_b_id="b", outcome=ComparisonOutcome.TIE)

    def test_missing_target_rejected(self):
        with pytest.raises(ValueError):
            ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="", outcome=ComparisonOutcome.TIE)

    def test_self_comparison_rejected(self):
        with pytest.raises(ValueError):
            ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="a", outcome=ComparisonOutcome.TIE)


class TestPairwiseConsistency:
    """v3 Part 1 §2: this is about a SET of comparisons jointly cohering, not any single one."""

    def test_consistent_requires_no_cycle_members(self):
        pc = PairwiseConsistency(status=ConsistencyStatus.CONSISTENT, comparisons_checked=("c1", "c2", "c3"))
        assert pc.cycle_members == frozenset()

    def test_cycle_detected_requires_cycle_members(self):
        with pytest.raises(ValueError):
            PairwiseConsistency(status=ConsistencyStatus.CYCLE_DETECTED, comparisons_checked=("c1", "c2", "c3"))

    def test_cycle_detected_with_members_is_valid(self):
        pc = PairwiseConsistency(
            status=ConsistencyStatus.CYCLE_DETECTED,
            comparisons_checked=("c1", "c2", "c3"),
            cycle_members=frozenset({"a", "b", "c"}),
        )
        assert pc.status == ConsistencyStatus.CYCLE_DETECTED

    def test_consistent_with_cycle_members_rejected(self):
        """A CONSISTENT result naming a cycle is contradictory."""
        with pytest.raises(ValueError):
            PairwiseConsistency(
                status=ConsistencyStatus.CONSISTENT,
                comparisons_checked=("c1",),
                cycle_members=frozenset({"a", "b"}),
            )

    def test_empty_comparisons_rejected(self):
        with pytest.raises(ValueError):
            PairwiseConsistency(status=ConsistencyStatus.CONSISTENT, comparisons_checked=())


class TestRequirementsPolicyStrategyProfile:
    """v3 Part 1 §3: four distinct concepts, kept separate -- the "real gap" v3 itself names."""

    def _requirements(self, **overrides):
        defaults = dict(target_description="artifact X exists", required_dimensions=frozenset({"outcome"}))
        defaults.update(overrides)
        return VerificationRequirements(**defaults)

    def test_valid_requirements_default_to_pointwise(self):
        assert self._requirements().shape == VerificationShape.POINTWISE

    def test_empty_target_description_rejected(self):
        with pytest.raises(ValueError):
            self._requirements(target_description="")

    def test_empty_dimensions_rejected(self):
        with pytest.raises(ValueError):
            self._requirements(required_dimensions=frozenset())

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            self._requirements(minimum_confidence=1.5)

    def test_policy_requires_id(self):
        with pytest.raises(ValueError):
            VerificationPolicy(policy_id="")

    def test_policy_defaults_are_empty(self):
        p = VerificationPolicy(policy_id="safety-critical-policy")
        assert p.mandatory_multi_verifier_dimensions == frozenset()
        assert p.forbidden_methods == frozenset()

    def test_strategy_requires_at_least_one_verifier(self):
        with pytest.raises(ValueError):
            VerificationStrategy(
                selected_shape=VerificationShape.POINTWISE,
                selected_methods=frozenset({"deterministic_check"}),
                verifier_count=0,
                derived_from_requirements="req-1",
            )

    def test_strategy_requires_at_least_one_method(self):
        with pytest.raises(ValueError):
            VerificationStrategy(
                selected_shape=VerificationShape.POINTWISE,
                selected_methods=frozenset(),
                verifier_count=1,
                derived_from_requirements="req-1",
            )

    def test_valid_strategy_has_no_policy_by_default(self):
        s = VerificationStrategy(
            selected_shape=VerificationShape.POINTWISE,
            selected_methods=frozenset({"deterministic_check"}),
            verifier_count=1,
            derived_from_requirements="req-1",
        )
        assert s.derived_from_policy is None

    def test_profile_requires_description(self):
        with pytest.raises(ValueError):
            VerificationProfile(
                name=VerificationProfileName.LIGHT,
                default_requirements=self._requirements(),
                description="",
            )

    def test_valid_profile(self):
        p = VerificationProfile(
            name=VerificationProfileName.STANDARD,
            default_requirements=self._requirements(),
            description="Standard rigor: single deterministic check where available.",
        )
        assert p.name == VerificationProfileName.STANDARD

    def test_all_three_profile_names_exist(self):
        """Recovers the original mission document's LIGHT/STANDARD/HIGH_ASSURANCE classes."""
        assert {VerificationProfileName.LIGHT, VerificationProfileName.STANDARD, VerificationProfileName.HIGH_ASSURANCE} == set(VerificationProfileName)


class TestVerificationTargetSnapshotAndFingerprint:
    def _fp(self, content_hash="abc123", version="v1"):
        return VerificationTargetFingerprint(content_hash=content_hash, version=version)

    def test_matching_fingerprints(self):
        assert self._fp().matches(self._fp())

    def test_different_content_hash_does_not_match(self):
        assert not self._fp(content_hash="abc123").matches(self._fp(content_hash="xyz789"))

    def test_empty_content_hash_rejected(self):
        with pytest.raises(ValueError):
            self._fp(content_hash="")

    def test_empty_version_rejected(self):
        with pytest.raises(ValueError):
            self._fp(version="")

    def test_snapshot_not_stale_against_matching_fingerprint(self):
        snap = VerificationTargetSnapshot(target_id="t1", fingerprint=self._fp(), captured_at=datetime.now(timezone.utc))
        assert not snap.is_stale_against(self._fp())

    def test_snapshot_stale_against_different_fingerprint(self):
        snap = VerificationTargetSnapshot(target_id="t1", fingerprint=self._fp(), captured_at=datetime.now(timezone.utc))
        assert snap.is_stale_against(self._fp(content_hash="different"))

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            VerificationTargetSnapshot(target_id="", fingerprint=self._fp(), captured_at=datetime.now(timezone.utc))


class TestStateTransitionInvariantVerification:
    """v3 Part 1 §5: precision subtypes, not new top-level concepts."""

    def test_state_verification_requires_predicate(self):
        with pytest.raises(ValueError):
            StateVerification(predicate_description="", as_of=datetime.now(timezone.utc))

    def test_valid_state_verification(self):
        sv = StateVerification(predicate_description="file exists", as_of=datetime.now(timezone.utc))
        assert sv.predicate_description == "file exists"

    def test_transition_requires_different_states(self):
        with pytest.raises(ValueError):
            TransitionVerification(action_description="no-op", from_state_description="X", to_state_description="X")

    def test_transition_requires_both_states_nonempty(self):
        with pytest.raises(ValueError):
            TransitionVerification(action_description="write", from_state_description="", to_state_description="present")

    def test_valid_transition(self):
        tv = TransitionVerification(action_description="write file", from_state_description="absent", to_state_description="present")
        assert tv.from_state_description != tv.to_state_description

    def test_invariant_window_end_before_start_rejected(self):
        start = datetime(2026, 1, 2, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            InvariantVerification(invariant_description="no writes", window_start=start, window_end=end)

    def test_invariant_open_window_allowed(self):
        iv = InvariantVerification(invariant_description="no writes", window_start=datetime.now(timezone.utc))
        assert iv.window_end is None


class TestRetentionPoliciesAreIndependent:
    """v3 Part 1 §6: three separate types on purpose, not one shared parametrized class."""

    def test_retain_for_duration_requires_days(self):
        with pytest.raises(ValueError):
            EvidenceRetention(rule=RetentionRule.RETAIN_FOR_DURATION)

    def test_negative_retention_days_rejected(self):
        with pytest.raises(ValueError):
            ReceiptRetention(rule=RetentionRule.RETAIN_FOR_DURATION, retention_days=-5)

    def test_zero_retention_days_rejected(self):
        with pytest.raises(ValueError):
            SourceRetention(rule=RetentionRule.RETAIN_FOR_DURATION, retention_days=0)

    def test_valid_source_retention(self):
        sr = SourceRetention(rule=RetentionRule.PRUNE_ELIGIBLE_IMMEDIATELY)
        assert sr.retention_days is None

    def test_evidence_and_receipt_retention_are_distinct_types(self):
        """The whole point of the split: these must not be interchangeable."""
        er = EvidenceRetention(rule=RetentionRule.RETAIN_INDEFINITELY)
        rr = ReceiptRetention(rule=RetentionRule.RETAIN_INDEFINITELY)
        assert type(er) is not type(rr)
        assert not isinstance(er, type(rr))


class TestControlCase:
    """v3 Part 1 §8: abstention on AMBIGUOUS/PARTIAL is correct behavior, not a defect."""

    def test_positive_case_cannot_expect_abstention(self):
        with pytest.raises(ValueError):
            ControlCase(case_id="cc1", control_type=ControlType.POSITIVE, description="basic pass case", expected_abstention=True)

    def test_negative_case_cannot_expect_abstention(self):
        with pytest.raises(ValueError):
            ControlCase(case_id="cc1", control_type=ControlType.NEGATIVE, description="basic fail case", expected_abstention=True)

    def test_ambiguous_case_may_expect_abstention(self):
        cc = ControlCase(case_id="cc1", control_type=ControlType.AMBIGUOUS, description="insufficient evidence to decide", expected_abstention=True)
        assert cc.expected_abstention

    def test_partial_case_may_expect_abstention(self):
        cc = ControlCase(case_id="cc1", control_type=ControlType.PARTIAL, description="incomplete coverage", expected_abstention=True)
        assert cc.expected_abstention

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            ControlCase(case_id="", control_type=ControlType.POSITIVE, description="x")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            ControlCase(case_id="cc1", control_type=ControlType.POSITIVE, description="")
