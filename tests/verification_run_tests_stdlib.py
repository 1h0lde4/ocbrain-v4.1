import os
import sys
import unittest
from datetime import datetime, timezone

# Portable repo-root insertion, matching tests/conftest.py's own technique —
# needed here because running this file directly (not via pytest) skips
# conftest.py entirely.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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


def basis(*components):
    return VerificationBasis(frozenset(components))


def assurance(**overrides):
    defaults = dict(
        basis=basis(BasisComponent.DETERMINISTIC),
        observation_authority=ObservationAuthority.FILESYSTEM,
        inspection_authorization=InspectionAuthorization(surface="fs:/tmp", authorized=True),
        assurance_scope="artifact_existence", coverage=1.0,
        independence_level="single_verifier", integrity_verified=True,
    )
    defaults.update(overrides)
    return VerificationAssurance(**defaults)


class TestVerificationBasisIsCompositional(unittest.TestCase):
    def test_single_component_allowed(self):
        self.assertTrue(basis(BasisComponent.DETERMINISTIC).is_deterministic_only)

    def test_multiple_components_allowed(self):
        b = basis(BasisComponent.DETERMINISTIC, BasisComponent.RUNTIME_OBSERVATION)
        self.assertTrue(b.has(BasisComponent.DETERMINISTIC))
        self.assertTrue(b.has(BasisComponent.RUNTIME_OBSERVATION))
        self.assertFalse(b.is_deterministic_only)

    def test_empty_basis_rejected(self):
        with self.assertRaises(ValueError):
            VerificationBasis(frozenset())


class TestAssuranceMustBeScoped(unittest.TestCase):
    def test_missing_scope_rejected(self):
        with self.assertRaises(ValueError):
            assurance(assurance_scope="")

    def test_coverage_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            assurance(coverage=1.5)

    def test_unauthorized_surface_rejected(self):
        with self.assertRaises(ValueError):
            assurance(inspection_authorization=InspectionAuthorization(surface="fs:/etc/shadow", authorized=False))


class TestCircularEvidenceRejected(unittest.TestCase):
    def test_restatement_of_claim_rejected(self):
        claim_id = new_id()
        ev = EvidenceItem(
            evidence_id=new_id(),
            source=EvidenceSource(source_type="agent_assertion", source_id="agent-1", producer="agent"),
            locator="chat:turn-4", directness=EvidenceDirectness.MODEL_INTERPRETATION,
            status=EvidenceStatus.SUFFICIENT, observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc), content_summary='agent says "X is true"',
            supports_claim_ids=(claim_id,), is_restatement_of_claim=True,
        )
        with self.assertRaises(CircularEvidenceError):
            check_not_circular(claim_id, ev)

    def test_genuine_evidence_accepted(self):
        claim_id = new_id()
        ev = EvidenceItem(
            evidence_id=new_id(),
            source=EvidenceSource(source_type="filesystem", source_id="fs", producer="runtime"),
            locator="/repo/output.txt", directness=EvidenceDirectness.DIRECT,
            status=EvidenceStatus.SUFFICIENT, observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc), content_summary="file exists, 1024 bytes",
            supports_claim_ids=(claim_id,), is_restatement_of_claim=False,
        )
        check_not_circular(claim_id, ev)  # must not raise


class TestVerifierCrashCannotBecomePass(unittest.TestCase):
    def test_execution_failure_with_positive_verdict_rejected(self):
        with self.assertRaises(ValueError):
            VerificationResult(
                verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
                attempt_id=new_id(), verdict=VerificationVerdict.VERIFIED,
                assurance=assurance(), confidence=0.9,
                execution_failure=VerificationExecutionFailure.VERIFIER_CRASH,
            )

    def test_execution_failure_with_unverifiable_accepted(self):
        r = VerificationResult(
            verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
            attempt_id=new_id(), verdict=VerificationVerdict.UNVERIFIABLE,
            assurance=assurance(), confidence=0.0,
            execution_failure=VerificationExecutionFailure.VERIFIER_CRASH,
        )
        self.assertEqual(r.verdict, VerificationVerdict.UNVERIFIABLE)


class TestReceiptImmutability(unittest.TestCase):
    def _make_result(self):
        return VerificationResult(
            verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
            attempt_id=new_id(), verdict=VerificationVerdict.VERIFIED,
            assurance=assurance(), confidence=0.95,
        )

    def test_supersession_returns_new_object_original_untouched(self):
        result = self._make_result()
        r1 = VerificationReceipt(
            receipt_id=new_id(), verification_id=result.verification_id, result=result,
            issued_at=datetime.now(timezone.utc), replayability=Replayability.FULLY_REPLAYABLE,
        )
        new_receipt_id = new_id()
        r2 = r1.superseded_by(new_receipt_id)
        self.assertIsNone(r1.superseded_by_receipt_id)
        self.assertEqual(r2.superseded_by_receipt_id, new_receipt_id)
        self.assertIsNot(r1, r2)

    def test_receipt_fields_cannot_be_reassigned(self):
        result = self._make_result()
        r = VerificationReceipt(
            receipt_id=new_id(), verification_id=result.verification_id, result=result,
            issued_at=datetime.now(timezone.utc), replayability=Replayability.FULLY_REPLAYABLE,
        )
        with self.assertRaises(Exception):
            r.receipt_id = "tampered"


class TestVerificationShapeIsOrthogonal(unittest.TestCase):
    def test_all_three_shapes_exist(self):
        self.assertEqual(
            {VerificationShape.POINTWISE, VerificationShape.PAIRWISE, VerificationShape.SET_LEVEL},
            set(VerificationShape),
        )


class TestComparisonRelation(unittest.TestCase):
    def test_decisive_outcomes(self):
        for outcome in (ComparisonOutcome.A_PREFERRED, ComparisonOutcome.B_PREFERRED):
            c = ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="b", outcome=outcome)
            self.assertTrue(c.is_decisive)

    def test_non_decisive_outcomes(self):
        for outcome in (ComparisonOutcome.TIE, ComparisonOutcome.INCOMPARABLE):
            c = ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="b", outcome=outcome)
            self.assertFalse(c.is_decisive)

    def test_empty_comparison_id_rejected(self):
        with self.assertRaises(ValueError):
            ComparisonRelation(comparison_id="", target_a_id="a", target_b_id="b", outcome=ComparisonOutcome.TIE)

    def test_missing_target_rejected(self):
        with self.assertRaises(ValueError):
            ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="", outcome=ComparisonOutcome.TIE)

    def test_self_comparison_rejected(self):
        with self.assertRaises(ValueError):
            ComparisonRelation(comparison_id="c1", target_a_id="a", target_b_id="a", outcome=ComparisonOutcome.TIE)


class TestPairwiseConsistency(unittest.TestCase):
    def test_consistent_requires_no_cycle_members(self):
        pc = PairwiseConsistency(status=ConsistencyStatus.CONSISTENT, comparisons_checked=("c1", "c2", "c3"))
        self.assertEqual(pc.cycle_members, frozenset())

    def test_cycle_detected_requires_cycle_members(self):
        with self.assertRaises(ValueError):
            PairwiseConsistency(status=ConsistencyStatus.CYCLE_DETECTED, comparisons_checked=("c1", "c2", "c3"))

    def test_cycle_detected_with_members_is_valid(self):
        pc = PairwiseConsistency(
            status=ConsistencyStatus.CYCLE_DETECTED,
            comparisons_checked=("c1", "c2", "c3"),
            cycle_members=frozenset({"a", "b", "c"}),
        )
        self.assertEqual(pc.status, ConsistencyStatus.CYCLE_DETECTED)

    def test_consistent_with_cycle_members_rejected(self):
        with self.assertRaises(ValueError):
            PairwiseConsistency(
                status=ConsistencyStatus.CONSISTENT,
                comparisons_checked=("c1",),
                cycle_members=frozenset({"a", "b"}),
            )

    def test_empty_comparisons_rejected(self):
        with self.assertRaises(ValueError):
            PairwiseConsistency(status=ConsistencyStatus.CONSISTENT, comparisons_checked=())


class TestRequirementsPolicyStrategyProfile(unittest.TestCase):
    def _requirements(self, **overrides):
        defaults = dict(target_description="artifact X exists", required_dimensions=frozenset({"outcome"}))
        defaults.update(overrides)
        return VerificationRequirements(**defaults)

    def test_valid_requirements_default_to_pointwise(self):
        self.assertEqual(self._requirements().shape, VerificationShape.POINTWISE)

    def test_empty_target_description_rejected(self):
        with self.assertRaises(ValueError):
            self._requirements(target_description="")

    def test_empty_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            self._requirements(required_dimensions=frozenset())

    def test_confidence_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            self._requirements(minimum_confidence=1.5)

    def test_policy_requires_id(self):
        with self.assertRaises(ValueError):
            VerificationPolicy(policy_id="")

    def test_policy_defaults_are_empty(self):
        p = VerificationPolicy(policy_id="safety-critical-policy")
        self.assertEqual(p.mandatory_multi_verifier_dimensions, frozenset())
        self.assertEqual(p.forbidden_methods, frozenset())

    def test_strategy_requires_at_least_one_verifier(self):
        with self.assertRaises(ValueError):
            VerificationStrategy(
                selected_shape=VerificationShape.POINTWISE,
                selected_methods=frozenset({"deterministic_check"}),
                verifier_count=0, derived_from_requirements="req-1",
            )

    def test_strategy_requires_at_least_one_method(self):
        with self.assertRaises(ValueError):
            VerificationStrategy(
                selected_shape=VerificationShape.POINTWISE,
                selected_methods=frozenset(),
                verifier_count=1, derived_from_requirements="req-1",
            )

    def test_valid_strategy_has_no_policy_by_default(self):
        s = VerificationStrategy(
            selected_shape=VerificationShape.POINTWISE,
            selected_methods=frozenset({"deterministic_check"}),
            verifier_count=1, derived_from_requirements="req-1",
        )
        self.assertIsNone(s.derived_from_policy)

    def test_profile_requires_description(self):
        with self.assertRaises(ValueError):
            VerificationProfile(
                name=VerificationProfileName.LIGHT,
                default_requirements=self._requirements(), description="",
            )

    def test_valid_profile(self):
        p = VerificationProfile(
            name=VerificationProfileName.STANDARD,
            default_requirements=self._requirements(),
            description="Standard rigor: single deterministic check where available.",
        )
        self.assertEqual(p.name, VerificationProfileName.STANDARD)

    def test_all_three_profile_names_exist(self):
        self.assertEqual(
            {VerificationProfileName.LIGHT, VerificationProfileName.STANDARD, VerificationProfileName.HIGH_ASSURANCE},
            set(VerificationProfileName),
        )


class TestVerificationTargetSnapshotAndFingerprint(unittest.TestCase):
    def _fp(self, content_hash="abc123", version="v1"):
        return VerificationTargetFingerprint(content_hash=content_hash, version=version)

    def test_matching_fingerprints(self):
        self.assertTrue(self._fp().matches(self._fp()))

    def test_different_content_hash_does_not_match(self):
        self.assertFalse(self._fp(content_hash="abc123").matches(self._fp(content_hash="xyz789")))

    def test_empty_content_hash_rejected(self):
        with self.assertRaises(ValueError):
            self._fp(content_hash="")

    def test_empty_version_rejected(self):
        with self.assertRaises(ValueError):
            self._fp(version="")

    def test_snapshot_not_stale_against_matching_fingerprint(self):
        snap = VerificationTargetSnapshot(target_id="t1", fingerprint=self._fp(), captured_at=datetime.now(timezone.utc))
        self.assertFalse(snap.is_stale_against(self._fp()))

    def test_snapshot_stale_against_different_fingerprint(self):
        snap = VerificationTargetSnapshot(target_id="t1", fingerprint=self._fp(), captured_at=datetime.now(timezone.utc))
        self.assertTrue(snap.is_stale_against(self._fp(content_hash="different")))

    def test_empty_target_id_rejected(self):
        with self.assertRaises(ValueError):
            VerificationTargetSnapshot(target_id="", fingerprint=self._fp(), captured_at=datetime.now(timezone.utc))


class TestStateTransitionInvariantVerification(unittest.TestCase):
    def test_state_verification_requires_predicate(self):
        with self.assertRaises(ValueError):
            StateVerification(predicate_description="", as_of=datetime.now(timezone.utc))

    def test_valid_state_verification(self):
        sv = StateVerification(predicate_description="file exists", as_of=datetime.now(timezone.utc))
        self.assertEqual(sv.predicate_description, "file exists")

    def test_transition_requires_different_states(self):
        with self.assertRaises(ValueError):
            TransitionVerification(action_description="no-op", from_state_description="X", to_state_description="X")

    def test_transition_requires_both_states_nonempty(self):
        with self.assertRaises(ValueError):
            TransitionVerification(action_description="write", from_state_description="", to_state_description="present")

    def test_valid_transition(self):
        tv = TransitionVerification(action_description="write file", from_state_description="absent", to_state_description="present")
        self.assertNotEqual(tv.from_state_description, tv.to_state_description)

    def test_invariant_window_end_before_start_rejected(self):
        start = datetime(2026, 1, 2, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            InvariantVerification(invariant_description="no writes", window_start=start, window_end=end)

    def test_invariant_open_window_allowed(self):
        iv = InvariantVerification(invariant_description="no writes", window_start=datetime.now(timezone.utc))
        self.assertIsNone(iv.window_end)


class TestRetentionPoliciesAreIndependent(unittest.TestCase):
    def test_retain_for_duration_requires_days(self):
        with self.assertRaises(ValueError):
            EvidenceRetention(rule=RetentionRule.RETAIN_FOR_DURATION)

    def test_negative_retention_days_rejected(self):
        with self.assertRaises(ValueError):
            ReceiptRetention(rule=RetentionRule.RETAIN_FOR_DURATION, retention_days=-5)

    def test_zero_retention_days_rejected(self):
        with self.assertRaises(ValueError):
            SourceRetention(rule=RetentionRule.RETAIN_FOR_DURATION, retention_days=0)

    def test_valid_source_retention(self):
        sr = SourceRetention(rule=RetentionRule.PRUNE_ELIGIBLE_IMMEDIATELY)
        self.assertIsNone(sr.retention_days)

    def test_evidence_and_receipt_retention_are_distinct_types(self):
        er = EvidenceRetention(rule=RetentionRule.RETAIN_INDEFINITELY)
        rr = ReceiptRetention(rule=RetentionRule.RETAIN_INDEFINITELY)
        self.assertIsNot(type(er), type(rr))
        self.assertFalse(isinstance(er, type(rr)))


class TestControlCase(unittest.TestCase):
    def test_positive_case_cannot_expect_abstention(self):
        with self.assertRaises(ValueError):
            ControlCase(case_id="cc1", control_type=ControlType.POSITIVE, description="basic pass case", expected_abstention=True)

    def test_negative_case_cannot_expect_abstention(self):
        with self.assertRaises(ValueError):
            ControlCase(case_id="cc1", control_type=ControlType.NEGATIVE, description="basic fail case", expected_abstention=True)

    def test_ambiguous_case_may_expect_abstention(self):
        cc = ControlCase(case_id="cc1", control_type=ControlType.AMBIGUOUS, description="insufficient evidence to decide", expected_abstention=True)
        self.assertTrue(cc.expected_abstention)

    def test_partial_case_may_expect_abstention(self):
        cc = ControlCase(case_id="cc1", control_type=ControlType.PARTIAL, description="incomplete coverage", expected_abstention=True)
        self.assertTrue(cc.expected_abstention)

    def test_empty_case_id_rejected(self):
        with self.assertRaises(ValueError):
            ControlCase(case_id="", control_type=ControlType.POSITIVE, description="x")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            ControlCase(case_id="cc1", control_type=ControlType.POSITIVE, description="")


if __name__ == "__main__":
    unittest.main(verbosity=2)
