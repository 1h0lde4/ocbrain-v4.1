import os
import sys
import unittest
import ast
import importlib
import inspect
import json
import pkgutil
from dataclasses import FrozenInstanceError, fields as dataclass_fields, replace as dataclass_replace
from itertools import product
from datetime import datetime, timezone
from enum import Enum
from typing import get_type_hints

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
    ProvenanceCompleteness, EvidenceReference, EvidenceObservation,
    TransformationType, EvidenceTransformation, EvidenceBundle,
    MinimumSufficientEvidence, EvidenceBindingError,
)
from core.verification.coverage import (
    TaskCoverage, VerificationCoverage, CriterionCoverage, EvidenceCoverage,
    ObservationCoverage,
)
from core.verification.absence import ObservationAbsenceState, ObservationAbsence
import core.verification as _cv_pkg
import core.verification.criterion_result as _cr_module
from core.verification.criterion_result import CriterionAttemptState, CriterionResult
from core.verification.construct import (
    VerificationConstruct, ConstructValidityStatus, ConstructValidity,
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
from core.verification.dimension import VerificationDimension, StateVerification, TransitionVerification, InvariantVerification
from core.verification.retention import RetentionRule, EvidenceRetention, ReceiptRetention, SourceRetention
from core.verification.control import ControlType, ControlCase
from core.verification.obligation import DerivationSource, VerificationObligation
from core.verification.rubric import (
    RubricLockState, RubricValidationError, CriterionDependencyCycleError,
    CriterionDependencyType, CriterionDependency, CriterionApplicability,
    CriterionEvidenceRequirement, Criterion, Rubric, validate_dependency_graph,
)
from core.verification.inspection import InspectionStep, InspectionPlan
from core.verification.observation import ObservationForm, Observation, Interpretation
from core.verification.claim import ClaimOrigin, Claim, ClaimDependencyType, ClaimDependency
from core.verification.assumption import Assumption, AssumptionSourceKind, AssumptionSource, AssumptionStatus
from core.verification.reference import ReferenceKind, Reference, GroundTruth, ReferenceQuality
from core.verification.oracle import Oracle
from core.verification.method import (
    InspectionClass, CostLatencyClass, MethodExecutionState, MethodDisposition,
    VerificationCapability, VerificationMethod, VerificationMethodRequest,
    VerificationMethodResult, BaseVerifierAdapter,
)
from core.verification.compiled_specification import (
    compile as compile_spec, CompiledVerificationSpecification, CompilationFailure,
)
from core.verification.finding import FindingDisposition, VerificationFinding
from core.verification.critique import CritiqueFindingType, Contradiction, CounterArgument, Critique


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

    def test_requirements_id_auto_generated_and_unique(self):
        r1, r2 = self._requirements(), self._requirements()
        self.assertTrue(r1.requirements_id and r2.requirements_id)
        self.assertNotEqual(r1.requirements_id, r2.requirements_id)

    def test_explicit_empty_requirements_id_rejected(self):
        with self.assertRaises(ValueError):
            self._requirements(requirements_id="")

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


# --- Phase 2: Obligation / Rubric / Criterion / InspectionPlan -------------


class TestVerificationObligation(unittest.TestCase):
    def test_valid_construction(self):
        ob = VerificationObligation(
            obligation_id=new_id(),
            derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="the output must be a valid JSON document",
            source_reference="user message #3",
        )
        self.assertIsNone(ob.rubric_id)

    def test_empty_obligation_id_rejected(self):
        with self.assertRaises(ValueError):
            VerificationObligation(
                obligation_id="", derivation_source=DerivationSource.CONSTRAINT,
                description="x", source_reference="y",
            )

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            VerificationObligation(
                obligation_id=new_id(), derivation_source=DerivationSource.CONSTRAINT,
                description="", source_reference="y",
            )

    def test_empty_source_reference_rejected(self):
        with self.assertRaises(ValueError):
            VerificationObligation(
                obligation_id=new_id(), derivation_source=DerivationSource.CONSTRAINT,
                description="x", source_reference="",
            )

    def test_explicit_user_requirement_carries_authority(self):
        ob = VerificationObligation(
            obligation_id=new_id(), derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="x", source_reference="y",
        )
        self.assertTrue(ob.carries_explicit_user_authority)

    def test_no_non_explicit_source_carries_authority(self):
        non_explicit = [s for s in DerivationSource if s is not DerivationSource.EXPLICIT_USER_REQUIREMENT]
        for source in non_explicit:
            ob = VerificationObligation(
                obligation_id=new_id(), derivation_source=source,
                description="x", source_reference="y",
            )
            self.assertFalse(ob.carries_explicit_user_authority, f"{source} incorrectly carries explicit authority")


class TestCriterionDependency(unittest.TestCase):
    def test_valid_construction(self):
        dep = CriterionDependency(
            criterion_id="c2", depends_on_criterion_id="c1",
            dependency_type=CriterionDependencyType.REQUIRES,
        )
        self.assertEqual(dep.dependency_type, CriterionDependencyType.REQUIRES)

    def test_self_dependency_rejected(self):
        with self.assertRaises(RubricValidationError):
            CriterionDependency(
                criterion_id="c1", depends_on_criterion_id="c1",
                dependency_type=CriterionDependencyType.REQUIRES,
            )


class TestCriterionApplicability(unittest.TestCase):
    def test_unconditional_valid(self):
        ca = CriterionApplicability(applies_unconditionally=True)
        self.assertIsNone(ca.condition_description)

    def test_conditional_with_description_valid(self):
        ca = CriterionApplicability(applies_unconditionally=False, condition_description="only when a database migration ran")
        self.assertTrue(ca.condition_description)

    def test_conditional_without_description_rejected(self):
        with self.assertRaises(ValueError):
            CriterionApplicability(applies_unconditionally=False)


class TestCriterionEvidenceRequirement(unittest.TestCase):
    def test_valid_construction(self):
        req = CriterionEvidenceRequirement(minimum_evidence_items=2, required_directness=EvidenceDirectness.DIRECT)
        self.assertEqual(req.minimum_evidence_items, 2)

    def test_negative_minimum_rejected(self):
        with self.assertRaises(ValueError):
            CriterionEvidenceRequirement(minimum_evidence_items=-1)


class TestCriterion(unittest.TestCase):
    def test_valid_construction(self):
        c = Criterion(
            criterion_id="c1", rubric_id="r1", description="output is valid JSON",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        self.assertTrue(c.description)

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            Criterion(
                criterion_id="c1", rubric_id="r1", description="",
                applicability=CriterionApplicability(applies_unconditionally=True),
                evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
            )


class TestRubric(unittest.TestCase):
    def test_valid_construction(self):
        r = Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="abc123",
            created_from="obligation o1", created_by="phase-c-session",
            derived_from="user requirement", source_requirements=("req1",),
            context_basis="task target snapshot t1", criteria=("c1", "c2"),
            construct=VerificationConstruct(description="test construct"),
        )
        self.assertEqual(r.lock_state, RubricLockState.DRAFT)

    def test_empty_version_rejected(self):
        with self.assertRaises(ValueError):
            Rubric(
                rubric_id="r1", version="", fingerprint="abc123",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=("c1",),
                construct=VerificationConstruct(description="test construct"),
            )

    def test_empty_fingerprint_rejected(self):
        with self.assertRaises(ValueError):
            Rubric(
                rubric_id="r1", version="1.0.0", fingerprint="",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=("c1",),
                construct=VerificationConstruct(description="test construct"),
            )

    def test_empty_criteria_rejected(self):
        with self.assertRaises(ValueError):
            Rubric(
                rubric_id="r1", version="1.0.0", fingerprint="abc",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=(),
                construct=VerificationConstruct(description="test construct"),
            )

    def test_duplicate_criterion_id_rejected(self):
        with self.assertRaises(RubricValidationError):
            Rubric(
                rubric_id="r1", version="1.0.0", fingerprint="abc",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=("c1", "c1"),
                construct=VerificationConstruct(description="test construct"),
            )


class TestRubricLockStateProgression(unittest.TestCase):
    def _draft_rubric(self):
        return Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="abc",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
            construct=VerificationConstruct(description="test construct"),
        )

    def _matching_criteria(self):
        # Matches _draft_rubric()'s criteria=("c1",) -- advance_to(VALIDATED)
        # requires the actual Criterion objects, not just their ids (Phase 1
        # finding, 22 Sept 2026: it used to accept lock-state ordering alone
        # as proof validation ran).
        return [
            Criterion(
                criterion_id="c1", rubric_id="r1", description="criterion c1",
                applicability=CriterionApplicability(applies_unconditionally=True),
                evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
            )
        ]

    def test_draft_to_validated_allowed(self):
        r = self._draft_rubric().advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria())
        self.assertEqual(r.lock_state, RubricLockState.VALIDATED)

    def test_validated_to_compiled_allowed(self):
        r = self._draft_rubric().advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria()).advance_to(RubricLockState.COMPILED)
        self.assertEqual(r.lock_state, RubricLockState.COMPILED)

    def test_compiled_to_locked_allowed(self):
        r = (self._draft_rubric()
             .advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria())
             .advance_to(RubricLockState.COMPILED)
             .advance_to(RubricLockState.LOCKED))
        self.assertEqual(r.lock_state, RubricLockState.LOCKED)

    def test_draft_to_compiled_rejected(self):
        with self.assertRaises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.COMPILED)

    def test_draft_to_locked_rejected(self):
        with self.assertRaises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.LOCKED)

    def test_locked_is_terminal(self):
        locked = (self._draft_rubric()
                  .advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria())
                  .advance_to(RubricLockState.COMPILED)
                  .advance_to(RubricLockState.LOCKED))
        with self.assertRaises(RubricValidationError):
            locked.advance_to(RubricLockState.DRAFT)

    def test_advance_to_does_not_mutate_original(self):
        draft = self._draft_rubric()
        validated = draft.advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria())
        self.assertEqual(draft.lock_state, RubricLockState.DRAFT)
        self.assertEqual(validated.lock_state, RubricLockState.VALIDATED)
        self.assertIsNot(draft, validated)

    def test_validated_without_criteria_rejected(self):
        with self.assertRaises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.VALIDATED)

    def test_validated_criteria_mismatch_rejected(self):
        wrong_criteria = [
            Criterion(
                criterion_id="not-c1", rubric_id="r1", description="wrong criterion",
                applicability=CriterionApplicability(applies_unconditionally=True),
                evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
            )
        ]
        with self.assertRaises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.VALIDATED, criteria=wrong_criteria)

    def test_validated_runs_real_dependency_validation(self):
        two_criterion_rubric = Rubric(
            rubric_id="r2", version="1.0.0", fingerprint="abc",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1", "c2"),
            construct=VerificationConstruct(description="test construct"),
        )
        two_criteria = [
            Criterion(
                criterion_id=cid, rubric_id="r2", description=f"criterion {cid}",
                applicability=CriterionApplicability(applies_unconditionally=True),
                evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
            )
            for cid in ("c1", "c2")
        ]
        cyclic_deps = [
            CriterionDependency(criterion_id="c1", depends_on_criterion_id="c2", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="c2", depends_on_criterion_id="c1", dependency_type=CriterionDependencyType.REQUIRES),
        ]
        with self.assertRaises(CriterionDependencyCycleError):
            two_criterion_rubric.advance_to(RubricLockState.VALIDATED, criteria=two_criteria, dependencies=cyclic_deps)


class TestValidateDependencyGraph(unittest.TestCase):
    def _criteria(self, ids):
        return [
            Criterion(
                criterion_id=cid, rubric_id="r1", description=f"criterion {cid}",
                applicability=CriterionApplicability(applies_unconditionally=True),
                evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
            )
            for cid in ids
        ]

    def test_no_dependencies_passes(self):
        validate_dependency_graph(self._criteria(["c1", "c2"]), [])

    def test_valid_dependency_passes(self):
        deps = [CriterionDependency(criterion_id="c2", depends_on_criterion_id="c1", dependency_type=CriterionDependencyType.REQUIRES)]
        validate_dependency_graph(self._criteria(["c1", "c2"]), deps)

    def test_phantom_criterion_reference_rejected(self):
        deps = [CriterionDependency(criterion_id="ghost", depends_on_criterion_id="c1", dependency_type=CriterionDependencyType.REQUIRES)]
        with self.assertRaises(RubricValidationError):
            validate_dependency_graph(self._criteria(["c1"]), deps)

    def test_phantom_depends_on_rejected(self):
        deps = [CriterionDependency(criterion_id="c1", depends_on_criterion_id="ghost", dependency_type=CriterionDependencyType.REQUIRES)]
        with self.assertRaises(RubricValidationError):
            validate_dependency_graph(self._criteria(["c1"]), deps)

    def test_two_node_cycle_detected(self):
        deps = [
            CriterionDependency(criterion_id="c1", depends_on_criterion_id="c2", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="c2", depends_on_criterion_id="c1", dependency_type=CriterionDependencyType.REQUIRES),
        ]
        with self.assertRaises(CriterionDependencyCycleError):
            validate_dependency_graph(self._criteria(["c1", "c2"]), deps)

    def test_three_node_cycle_detected(self):
        # A > B > C > A -- mission's own pairwise-cycle example, applied here to criterion dependencies
        deps = [
            CriterionDependency(criterion_id="a", depends_on_criterion_id="b", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="b", depends_on_criterion_id="c", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="c", depends_on_criterion_id="a", dependency_type=CriterionDependencyType.REQUIRES),
        ]
        with self.assertRaises(CriterionDependencyCycleError):
            validate_dependency_graph(self._criteria(["a", "b", "c"]), deps)


class TestInspectionStep(unittest.TestCase):
    def test_valid_construction(self):
        step = InspectionStep(step_id="s1", plan_id="p1", method_reference="filesystem_exists_check", description="check artifact exists on disk")
        self.assertEqual(step.method_reference, "filesystem_exists_check")

    def test_empty_method_reference_rejected(self):
        with self.assertRaises(ValueError):
            InspectionStep(step_id="s1", plan_id="p1", method_reference="", description="x")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            InspectionStep(step_id="s1", plan_id="p1", method_reference="x", description="")


class TestInspectionPlan(unittest.TestCase):
    def test_valid_construction(self):
        plan = InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=("s1", "s2"))
        self.assertEqual(len(plan.steps), 2)

    def test_empty_steps_rejected(self):
        with self.assertRaises(ValueError):
            InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=())


class TestObservation(unittest.TestCase):
    def _obs(self, **overrides):
        defaults = dict(
            observation_id="obs1", authority=ObservationAuthority.FILESYSTEM,
            form=ObservationForm.BINARY_PRESENCE, content_summary="file present",
            observed_at=datetime.now(timezone.utc), locator="/repo/core/verification/rubric.py",
        )
        defaults.update(overrides)
        return Observation(**defaults)

    def test_valid_construction(self):
        obs = self._obs()
        self.assertEqual(obs.form, ObservationForm.BINARY_PRESENCE)

    def test_empty_content_summary_rejected(self):
        with self.assertRaises(ValueError):
            self._obs(content_summary="")

    def test_empty_locator_rejected(self):
        with self.assertRaises(ValueError):
            self._obs(locator="")


class TestInterpretation(unittest.TestCase):
    def test_valid_construction(self):
        interp = Interpretation(observation_id="obs1", meaning="the file exists", interpreted_by="deterministic_rule")
        self.assertEqual(interp.meaning, "the file exists")

    def test_empty_meaning_rejected(self):
        with self.assertRaises(ValueError):
            Interpretation(observation_id="obs1", meaning="", interpreted_by="deterministic_rule")

    def test_empty_interpreted_by_rejected(self):
        with self.assertRaises(ValueError):
            Interpretation(observation_id="obs1", meaning="x", interpreted_by="")


class TestClaim(unittest.TestCase):
    def test_direct_assertion_valid(self):
        c = Claim(claim_id="c1", content="the API returns 200 on success", origin=ClaimOrigin.DIRECT_ASSERTION)
        self.assertIsNone(c.source_observation_id)

    def test_interpreted_observation_valid(self):
        c = Claim(claim_id="c1", content="the file exists", origin=ClaimOrigin.INTERPRETED_OBSERVATION, source_observation_id="obs1")
        self.assertEqual(c.source_observation_id, "obs1")

    def test_derived_valid(self):
        c = Claim(claim_id="c1", content="therefore the pipeline is idle", origin=ClaimOrigin.DERIVED)
        self.assertEqual(c.origin, ClaimOrigin.DERIVED)

    def test_empty_content_rejected(self):
        with self.assertRaises(ValueError):
            Claim(claim_id="c1", content="", origin=ClaimOrigin.DIRECT_ASSERTION)

    def test_interpreted_observation_without_source_rejected(self):
        with self.assertRaises(ValueError):
            Claim(claim_id="c1", content="x", origin=ClaimOrigin.INTERPRETED_OBSERVATION)

    def test_direct_assertion_with_source_rejected(self):
        with self.assertRaises(ValueError):
            Claim(claim_id="c1", content="x", origin=ClaimOrigin.DIRECT_ASSERTION, source_observation_id="obs1")

    def test_derived_with_source_rejected(self):
        with self.assertRaises(ValueError):
            Claim(claim_id="c1", content="x", origin=ClaimOrigin.DERIVED, source_observation_id="obs1")


class TestAssumption(unittest.TestCase):
    def test_valid_construction(self):
        a = Assumption(assumption_id="a1", description="the database replica is current", relied_upon_for="freshness of the queried target state")
        self.assertEqual(a.assumption_id, "a1")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            Assumption(assumption_id="a1", description="", relied_upon_for="x")

    def test_empty_relied_upon_for_rejected(self):
        with self.assertRaises(ValueError):
            Assumption(assumption_id="a1", description="x", relied_upon_for="")


class TestReference(unittest.TestCase):
    def test_valid_construction(self):
        r = Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE, content_summary="expected HTTP 200", source="API spec v2")
        self.assertEqual(r.kind, ReferenceKind.EXPECTED_VALUE)

    def test_empty_content_summary_rejected(self):
        with self.assertRaises(ValueError):
            Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE, content_summary="", source="x")

    def test_empty_source_rejected(self):
        with self.assertRaises(ValueError):
            Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE, content_summary="x", source="")


class TestGroundTruth(unittest.TestCase):
    def test_valid_construction(self):
        gt = GroundTruth(ground_truth_id="gt1", reference_id="r1", established_by="human:moncif", established_via="human_review")
        self.assertEqual(gt.established_via, "human_review")

    def test_empty_established_by_rejected(self):
        with self.assertRaises(ValueError):
            GroundTruth(ground_truth_id="gt1", reference_id="r1", established_by="", established_via="human_review")

    def test_empty_established_via_rejected(self):
        with self.assertRaises(ValueError):
            GroundTruth(ground_truth_id="gt1", reference_id="r1", established_by="human:moncif", established_via="")


class TestOracle(unittest.TestCase):
    def test_valid_construction(self):
        o = Oracle(oracle_id="o1", description="reference implementation diff", is_executable=True, is_reproducible=True, is_validated=False)
        self.assertFalse(o.is_authoritative)

    def test_authoritative_without_validated_rejected(self):
        with self.assertRaises(ValueError):
            Oracle(oracle_id="o1", description="x", is_executable=True, is_reproducible=True, is_validated=False, is_authoritative=True)

    def test_authoritative_with_validated_allowed(self):
        o = Oracle(oracle_id="o1", description="x", is_executable=True, is_reproducible=True, is_validated=True, is_authoritative=True)
        self.assertTrue(o.is_authoritative)

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            Oracle(oracle_id="o1", description="", is_executable=True, is_reproducible=True, is_validated=True)


class TestVerificationCapability(unittest.TestCase):
    def test_valid_construction(self):
        cap = VerificationCapability(
            capability_id="cap1", name="filesystem_observation",
            inspection_class=InspectionClass.READ_ONLY_INSPECTION,
            typical_evidence_directness=EvidenceDirectness.DIRECT,
        )
        self.assertEqual(cap.underlying_capability_types, ())

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            VerificationCapability(capability_id="cap1", name="", inspection_class=InspectionClass.READ_ONLY_INSPECTION, typical_evidence_directness=EvidenceDirectness.DIRECT)

    def test_with_underlying_capability_types(self):
        cap = VerificationCapability(
            capability_id="cap1", name="filesystem_observation",
            inspection_class=InspectionClass.READ_ONLY_INSPECTION,
            typical_evidence_directness=EvidenceDirectness.DIRECT,
            underlying_capability_types=("FILE_ACCESS",),
        )
        self.assertEqual(cap.underlying_capability_types, ("FILE_ACCESS",))


class TestVerificationMethod(unittest.TestCase):
    def _method(self, **overrides):
        defaults = dict(
            method_id="m1", method_type="deterministic_file_existence",
            description="checks whether a file exists", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=False, is_deterministic=True,
            cost_latency_class=CostLatencyClass.INSTANT,
        )
        defaults.update(overrides)
        return VerificationMethod(**defaults)

    def test_valid_construction(self):
        m = self._method()
        self.assertTrue(m.is_deterministic)
        self.assertEqual(m.required_capabilities, ())

    def test_empty_method_type_rejected(self):
        with self.assertRaises(ValueError):
            self._method(method_type="")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            self._method(description="")

    def test_empty_version_rejected(self):
        with self.assertRaises(ValueError):
            self._method(version="")

    def test_external_access_without_capabilities_rejected(self):
        with self.assertRaises(ValueError):
            self._method(external_access_needed=True, required_capabilities=())

    def test_external_access_with_capabilities_allowed(self):
        m = self._method(external_access_needed=True, required_capabilities=("cap1",))
        self.assertEqual(m.required_capabilities, ("cap1",))


class TestVerificationMethodRequest(unittest.TestCase):
    def _target(self):
        fp = VerificationTargetFingerprint(content_hash="abc123", version="1")
        return VerificationTargetSnapshot(target_id="t1", fingerprint=fp, captured_at=datetime.now(timezone.utc))

    def test_valid_construction(self):
        req = VerificationMethodRequest(method_id="m1", target=self._target(), criterion_id="c1")
        self.assertEqual(req.payload, {})

    def test_empty_method_id_rejected(self):
        with self.assertRaises(ValueError):
            VerificationMethodRequest(method_id="", target=self._target(), criterion_id="c1")


class TestVerificationMethodResult(unittest.TestCase):
    def test_executed_requires_disposition(self):
        with self.assertRaises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=None)

    def test_executed_conclusive_requires_observations(self):
        with self.assertRaises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=MethodDisposition.CONCLUSIVE, observations=())

    def test_executed_conclusive_with_observations_valid(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=MethodDisposition.CONCLUSIVE, observations=("obs1",))
        self.assertEqual(r.disposition, MethodDisposition.CONCLUSIVE)

    def test_executed_insufficient_without_observations_valid(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=MethodDisposition.INSUFFICIENT, observations=())
        self.assertEqual(r.observations, ())

    def test_not_run_with_disposition_rejected(self):
        with self.assertRaises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.NOT_RUN, disposition=MethodDisposition.CONCLUSIVE)

    def test_not_run_with_observations_rejected(self):
        with self.assertRaises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.NOT_RUN, observations=("obs1",))

    def test_execution_failed_is_clean(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.EXECUTION_FAILED)
        self.assertIsNone(r.disposition)
        self.assertEqual(r.observations, ())

    def test_unavailable_is_clean(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.UNAVAILABLE)
        self.assertEqual(r.execution_state, MethodExecutionState.UNAVAILABLE)


class TestBaseVerifierAdapter(unittest.TestCase):
    def test_initial_state_available(self):
        a = BaseVerifierAdapter()
        self.assertTrue(a.is_available())
        self.assertEqual(a.health_score, 100)

    def test_mark_failure_triggers_cooldown(self):
        a = BaseVerifierAdapter()
        a.mark_failure()
        self.assertFalse(a.is_available())
        self.assertEqual(a.health_score, 80)

    def test_mark_success_resets_failures_and_raises_health(self):
        a = BaseVerifierAdapter()
        a.mark_failure()
        a.mark_success()
        self.assertEqual(a.consecutive_failures, 0)
        self.assertEqual(a.health_score, 85)

    def test_repeated_failures_extend_cooldown(self):
        a = BaseVerifierAdapter()
        a.mark_failure()
        first_cooldown = a.cooldown_until
        a.mark_failure()
        self.assertGreater(a.cooldown_until, first_cooldown)


class TestCompileVerificationSpecification(unittest.TestCase):
    def _scenario(self, **overrides):
        criterion = Criterion(
            criterion_id="c1", rubric_id="r1", description="criterion c1",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        rubric = (Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
            construct=VerificationConstruct(description="test construct"),
        ).advance_to(RubricLockState.VALIDATED, criteria=[criterion])
          .advance_to(RubricLockState.COMPILED))
        obligation = VerificationObligation(
            obligation_id="o1", derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="obligation desc", source_reference="req-1", rubric_id="r1",
        )
        method = VerificationMethod(
            method_id="m1", method_type="deterministic_file_existence",
            description="checks file existence", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=False, is_deterministic=True,
            cost_latency_class=CostLatencyClass.INSTANT,
        )
        step = InspectionStep(step_id="s1", plan_id="p1", method_reference="m1", description="step desc")
        plan = InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=("s1",))
        requirements = VerificationRequirements(target_description="check the file", required_dimensions=frozenset({"correctness"}))
        strategy = VerificationStrategy(
            selected_shape=VerificationShape.POINTWISE, selected_methods=frozenset({"m1"}),
            verifier_count=1, derived_from_requirements=requirements.requirements_id,
        )
        fp = VerificationTargetFingerprint(content_hash="abc", version="1")
        target = VerificationTargetSnapshot(target_id="t1", fingerprint=fp, captured_at=datetime.now(timezone.utc))

        defaults = dict(
            requirements=requirements, strategy=strategy, rubric=rubric, criteria=[criterion],
            dependencies=[], obligations=[obligation], inspection_plans=[plan], inspection_steps=[step],
            target=target, method_registry={"m1": method}, capability_registry={},
            authorization_registry={}, assurance_scope="unit test scope",
        )
        defaults.update(overrides)
        return defaults

    def test_successful_compilation(self):
        result = compile_spec(**self._scenario())
        self.assertIsInstance(result, CompiledVerificationSpecification)
        self.assertEqual(result.method_ids, ("m1",))
        self.assertEqual(result.criterion_ids, ("c1",))
        self.assertEqual(result.rubric_id, "r1")

    def test_wrong_lock_state_rejected(self):
        scenario = self._scenario()
        draft_rubric = Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
            construct=VerificationConstruct(description="test construct"),
        )
        scenario["rubric"] = draft_rubric
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("lock_state" in r for r in result.reasons))

    def test_criterion_mismatch_rejected(self):
        scenario = self._scenario()
        other_criterion = Criterion(
            criterion_id="not-c1", rubric_id="r1", description="wrong",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        scenario["criteria"] = [other_criterion]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("must match exactly" in r for r in result.reasons))

    def test_dependency_cycle_rejected(self):
        scenario = self._scenario()
        c2 = Criterion(
            criterion_id="c2", rubric_id="r1", description="c2",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        rubric_with_c2 = Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1", "c2"),
            construct=VerificationConstruct(description="test construct"),
        ).advance_to(RubricLockState.VALIDATED, criteria=[scenario["criteria"][0], c2]).advance_to(RubricLockState.COMPILED)
        cyclic_deps = [
            CriterionDependency(criterion_id="c1", depends_on_criterion_id="c2", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="c2", depends_on_criterion_id="c1", dependency_type=CriterionDependencyType.REQUIRES),
        ]
        scenario["rubric"] = rubric_with_c2
        scenario["criteria"] = [scenario["criteria"][0], c2]
        scenario["dependencies"] = cyclic_deps
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("dependency graph invalid" in r for r in result.reasons))

    def test_obligation_wrong_rubric_rejected(self):
        scenario = self._scenario()
        scenario["obligations"] = [VerificationObligation(
            obligation_id="o1", derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="d", source_reference="r", rubric_id="different-rubric",
        )]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("not the rubric being compiled" in r for r in result.reasons))

    def test_obligation_with_no_rubric_allowed(self):
        scenario = self._scenario()
        scenario["obligations"] = [VerificationObligation(
            obligation_id="o1", derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="d", source_reference="r", rubric_id=None,
        )]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompiledVerificationSpecification)

    def test_unresolvable_method_reference_rejected(self):
        scenario = self._scenario()
        scenario["method_registry"] = {}
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("not in the method registry" in r for r in result.reasons))

    def test_missing_inspection_step_rejected(self):
        scenario = self._scenario()
        scenario["inspection_steps"] = []
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("was not supplied" in r for r in result.reasons))

    def test_missing_capability_rejected(self):
        scenario = self._scenario()
        method_needing_cap = VerificationMethod(
            method_id="m1", method_type="tool_backed_filesystem",
            description="needs filesystem access", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=True, is_deterministic=True,
            cost_latency_class=CostLatencyClass.FAST,
            required_capabilities=("cap1",),
        )
        scenario["method_registry"] = {"m1": method_needing_cap}
        scenario["capability_registry"] = {}
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("capability" in r and "cap1" in r for r in result.reasons))

    def test_capability_registered_but_not_authorized_rejected(self):
        scenario = self._scenario()
        method_needing_cap = VerificationMethod(
            method_id="m1", method_type="tool_backed_filesystem",
            description="needs filesystem access", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=True, is_deterministic=True,
            cost_latency_class=CostLatencyClass.FAST,
            required_capabilities=("cap1",),
        )
        capability = VerificationCapability(
            capability_id="cap1", name="filesystem_observation",
            inspection_class=InspectionClass.READ_ONLY_INSPECTION,
            typical_evidence_directness=EvidenceDirectness.DIRECT,
        )
        scenario["method_registry"] = {"m1": method_needing_cap}
        scenario["capability_registry"] = {"cap1": capability}
        scenario["authorization_registry"] = {}
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("no authorized InspectionAuthorization" in r for r in result.reasons))

    def test_capability_explicitly_unauthorized_rejected(self):
        scenario = self._scenario()
        method_needing_cap = VerificationMethod(
            method_id="m1", method_type="tool_backed_filesystem",
            description="needs filesystem access", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=True, is_deterministic=True,
            cost_latency_class=CostLatencyClass.FAST,
            required_capabilities=("cap1",),
        )
        capability = VerificationCapability(
            capability_id="cap1", name="filesystem_observation",
            inspection_class=InspectionClass.READ_ONLY_INSPECTION,
            typical_evidence_directness=EvidenceDirectness.DIRECT,
        )
        scenario["method_registry"] = {"m1": method_needing_cap}
        scenario["capability_registry"] = {"cap1": capability}
        scenario["authorization_registry"] = {
            "filesystem_observation": InspectionAuthorization(surface="filesystem_observation", authorized=False, reason="pending review"),
        }
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("no authorized InspectionAuthorization" in r for r in result.reasons))

    def test_capability_satisfied_allowed(self):
        scenario = self._scenario()
        method_needing_cap = VerificationMethod(
            method_id="m1", method_type="tool_backed_filesystem",
            description="needs filesystem access", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=True, is_deterministic=True,
            cost_latency_class=CostLatencyClass.FAST,
            required_capabilities=("cap1",),
        )
        capability = VerificationCapability(
            capability_id="cap1", name="filesystem_observation",
            inspection_class=InspectionClass.READ_ONLY_INSPECTION,
            typical_evidence_directness=EvidenceDirectness.DIRECT,
        )
        scenario["method_registry"] = {"m1": method_needing_cap}
        scenario["capability_registry"] = {"cap1": capability}
        scenario["authorization_registry"] = {
            "filesystem_observation": InspectionAuthorization(surface="filesystem_observation", authorized=True, authorized_by="governance"),
        }
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompiledVerificationSpecification)

    def test_orphaned_criterion_rejected(self):
        scenario = self._scenario()
        scenario["inspection_plans"] = []
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("no inspection plan targeting them" in r for r in result.reasons))

    def test_plan_references_unknown_obligation_rejected(self):
        scenario = self._scenario()
        scenario["inspection_plans"] = [InspectionPlan(plan_id="p1", obligation_id="not-o1", criterion_id="c1", steps=("s1",))]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("not supplied to compile()" in r and "not-o1" in r for r in result.reasons))

    def test_plan_references_unknown_criterion_rejected(self):
        scenario = self._scenario()
        scenario["inspection_plans"] = [InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="not-c1", steps=("s1",))]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("not among the criteria being compiled" in r for r in result.reasons))

    def test_evidence_directness_mismatch_rejected(self):
        scenario = self._scenario()
        strict_criterion = Criterion(
            criterion_id="c1", rubric_id="r1", description="criterion c1",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1, required_directness=EvidenceDirectness.DIRECT),
        )
        scenario["criteria"] = [strict_criterion]
        indirect_method = VerificationMethod(
            method_id="m1", method_type="evidence_backed_semantic",
            description="produces indirect evidence", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.INDIRECT,
            external_access_needed=False, is_deterministic=False,
            cost_latency_class=CostLatencyClass.MODERATE,
        )
        scenario["method_registry"] = {"m1": indirect_method}
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("requires evidence directness" in r for r in result.reasons))

    def test_evidence_directness_match_allowed(self):
        scenario = self._scenario()
        strict_criterion = Criterion(
            criterion_id="c1", rubric_id="r1", description="criterion c1",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1, required_directness=EvidenceDirectness.DIRECT),
        )
        scenario["criteria"] = [strict_criterion]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompiledVerificationSpecification)

    def test_policy_shape_violation_rejected(self):
        scenario = self._scenario()
        scenario["policy"] = VerificationPolicy(
            policy_id="pol1",
            minimum_shape_for={"correctness": VerificationShape.PAIRWISE},
        )
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("policy requires shape" in r for r in result.reasons))

    def test_policy_forbidden_method_rejected(self):
        scenario = self._scenario()
        scenario["policy"] = VerificationPolicy(policy_id="pol1", forbidden_methods=frozenset({"m1"}))
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("forbidden methods" in r for r in result.reasons))

    def test_critical_criterion_not_in_set_rejected(self):
        scenario = self._scenario()
        scenario["critical_criterion_ids"] = frozenset({"not-a-real-criterion"})
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("not among the criteria being compiled" in r for r in result.reasons))

    def test_critical_criterion_in_set_allowed(self):
        scenario = self._scenario()
        scenario["critical_criterion_ids"] = frozenset({"c1"})
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompiledVerificationSpecification)
        self.assertEqual(result.critical_criterion_ids, frozenset({"c1"}))

    def test_multiple_failures_collected_together(self):
        scenario = self._scenario()
        draft_rubric = Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
            construct=VerificationConstruct(description="test construct"),
        )
        scenario["rubric"] = draft_rubric
        scenario["method_registry"] = {}
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertGreaterEqual(len(result.reasons), 2)

    def test_empty_spec_id_rejected_on_direct_construction(self):
        with self.assertRaises(ValueError):
            CompiledVerificationSpecification(
                spec_id="", compiled_at=datetime.now(timezone.utc), target_id="t1",
                target_fingerprint=VerificationTargetFingerprint(content_hash="a", version="1"),
                requirements=VerificationRequirements(target_description="x", required_dimensions=frozenset({"d"})),
                strategy=VerificationStrategy(selected_shape=VerificationShape.POINTWISE, selected_methods=frozenset({"m1"}), verifier_count=1, derived_from_requirements="req1"),
                rubric_id="r1", rubric_version="1.0.0", rubric_fingerprint="fp1",
                obligation_ids=(), criterion_ids=("c1",), critical_criterion_ids=frozenset(),
                inspection_plan_ids=(), method_ids=(), assurance_scope="scope",
            )

    def test_empty_assurance_scope_rejected(self):
        with self.assertRaises(ValueError):
            CompiledVerificationSpecification(
                spec_id="spec1", compiled_at=datetime.now(timezone.utc), target_id="t1",
                target_fingerprint=VerificationTargetFingerprint(content_hash="a", version="1"),
                requirements=VerificationRequirements(target_description="x", required_dimensions=frozenset({"d"})),
                strategy=VerificationStrategy(selected_shape=VerificationShape.POINTWISE, selected_methods=frozenset({"m1"}), verifier_count=1, derived_from_requirements="req1"),
                rubric_id="r1", rubric_version="1.0.0", rubric_fingerprint="fp1",
                obligation_ids=(), criterion_ids=("c1",), critical_criterion_ids=frozenset(),
                inspection_plan_ids=(), method_ids=(), assurance_scope="",
            )

    def test_critical_superset_rejected_on_direct_construction(self):
        with self.assertRaises(ValueError):
            CompiledVerificationSpecification(
                spec_id="spec1", compiled_at=datetime.now(timezone.utc), target_id="t1",
                target_fingerprint=VerificationTargetFingerprint(content_hash="a", version="1"),
                requirements=VerificationRequirements(target_description="x", required_dimensions=frozenset({"d"})),
                strategy=VerificationStrategy(selected_shape=VerificationShape.POINTWISE, selected_methods=frozenset({"m1"}), verifier_count=1, derived_from_requirements="req1"),
                rubric_id="r1", rubric_version="1.0.0", rubric_fingerprint="fp1",
                obligation_ids=(), criterion_ids=("c1",), critical_criterion_ids=frozenset({"not-c1"}),
                inspection_plan_ids=(), method_ids=(), assurance_scope="scope",
            )


class TestCompilationFailure(unittest.TestCase):
    def test_empty_reasons_rejected(self):
        with self.assertRaises(ValueError):
            CompilationFailure(reasons=())

    def test_valid_construction(self):
        f = CompilationFailure(reasons=("something went wrong",))
        self.assertEqual(len(f.reasons), 1)


class TestCompiledSpecificationHardening(unittest.TestCase):
    def _scenario(self, **overrides):
        criterion = Criterion(
            criterion_id="c1", rubric_id="r1", description="criterion c1",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        rubric = (Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
            construct=VerificationConstruct(description="test construct"),
        ).advance_to(RubricLockState.VALIDATED, criteria=[criterion])
          .advance_to(RubricLockState.COMPILED))
        obligation = VerificationObligation(
            obligation_id="o1", derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="obligation desc", source_reference="req-1", rubric_id="r1",
        )
        method = VerificationMethod(
            method_id="m1", method_type="deterministic_file_existence",
            description="checks file existence", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=False, is_deterministic=True,
            cost_latency_class=CostLatencyClass.INSTANT,
        )
        step = InspectionStep(step_id="s1", plan_id="p1", method_reference="m1", description="step desc")
        plan = InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=("s1",))
        requirements = VerificationRequirements(target_description="check the file", required_dimensions=frozenset({"correctness"}))
        strategy = VerificationStrategy(
            selected_shape=VerificationShape.POINTWISE, selected_methods=frozenset({"m1"}),
            verifier_count=1, derived_from_requirements=requirements.requirements_id,
        )
        fp = VerificationTargetFingerprint(content_hash="abc", version="1")
        target = VerificationTargetSnapshot(target_id="t1", fingerprint=fp, captured_at=datetime.now(timezone.utc))
        defaults = dict(
            requirements=requirements, strategy=strategy, rubric=rubric, criteria=[criterion],
            dependencies=[], obligations=[obligation], inspection_plans=[plan], inspection_steps=[step],
            target=target, method_registry={"m1": method}, capability_registry={},
            authorization_registry={}, assurance_scope="unit test scope",
        )
        defaults.update(overrides)
        return defaults

    def test_duplicate_criterion_ids_rejected(self):
        scenario = self._scenario()
        dup = Criterion(criterion_id="c1", rubric_id="r1", description="dup",
                        applicability=CriterionApplicability(applies_unconditionally=True),
                        evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1))
        scenario["criteria"] = [scenario["criteria"][0], dup]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("duplicate criterion id" in r for r in result.reasons))

    def test_duplicate_obligation_ids_rejected(self):
        scenario = self._scenario()
        dup = VerificationObligation(obligation_id="o1", derivation_source=DerivationSource.CONSTRAINT,
                                     description="dup", source_reference="r2", rubric_id="r1")
        scenario["obligations"] = [scenario["obligations"][0], dup]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("duplicate obligation id" in r for r in result.reasons))

    def test_duplicate_inspection_plan_ids_rejected(self):
        scenario = self._scenario()
        dup = InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=("s1",))
        scenario["inspection_plans"] = [scenario["inspection_plans"][0], dup]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("duplicate inspection_plan id" in r for r in result.reasons))

    def test_duplicate_inspection_step_ids_rejected(self):
        scenario = self._scenario()
        dup = InspectionStep(step_id="s1", plan_id="p1", method_reference="m1", description="dup")
        scenario["inspection_steps"] = [scenario["inspection_steps"][0], dup]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("duplicate inspection_step id" in r for r in result.reasons))

    def test_step_plan_id_not_in_supplied_plans_rejected(self):
        scenario = self._scenario()
        orphan = InspectionStep(step_id="s1", plan_id="phantom", method_reference="m1", description="orphan")
        scenario["inspection_steps"] = [orphan]
        result = compile_spec(**scenario)
        self.assertIsInstance(result, CompilationFailure)
        self.assertTrue(any("plan_id=" in r and "'phantom'" in r for r in result.reasons))

    def test_step_plan_id_matching_supplied_plan_accepted(self):
        result = compile_spec(**self._scenario())
        self.assertIsInstance(result, CompiledVerificationSpecification)

    def _distinct_id_and_type_scenario(self, selected_methods):
        scenario = self._scenario()
        method = VerificationMethod(
            method_id="method-uuid-1", method_type="deterministic_file_existence",
            description="checks file existence", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=False, is_deterministic=True,
            cost_latency_class=CostLatencyClass.INSTANT,
        )
        self.assertNotEqual(method.method_id, method.method_type)
        scenario["inspection_steps"] = [InspectionStep(
            step_id="s1", plan_id="p1", method_reference="method-uuid-1",
            description="step desc",
        )]
        scenario["method_registry"] = {"method-uuid-1": method}
        scenario["strategy"] = VerificationStrategy(
            selected_shape=VerificationShape.POINTWISE,
            selected_methods=frozenset(selected_methods),
            verifier_count=1,
            derived_from_requirements=scenario["requirements"].requirements_id,
        )
        return scenario

    def test_compiles_when_selected_methods_holds_method_type_not_id(self):
        result = compile_spec(**self._distinct_id_and_type_scenario(
            {"deterministic_file_existence"}))
        self.assertIsInstance(result, CompiledVerificationSpecification)
        self.assertEqual(result.method_ids, ("method-uuid-1",))

    def test_compiles_when_selected_methods_holds_method_id(self):
        result = compile_spec(**self._distinct_id_and_type_scenario(
            {"method-uuid-1"}))
        self.assertIsInstance(result, CompiledVerificationSpecification)

    def test_compile_imposes_no_strategy_to_step_method_relation(self):
        result = compile_spec(**self._distinct_id_and_type_scenario(
            {"deterministic_file_existence", "never_used_method"}))
        self.assertIsInstance(result, CompiledVerificationSpecification)

    def test_compile_creates_different_ids_each_call(self):
        scenario = self._scenario()
        r1 = compile_spec(**scenario)
        r2 = compile_spec(**scenario)
        self.assertIsInstance(r1, CompiledVerificationSpecification)
        self.assertIsInstance(r2, CompiledVerificationSpecification)
        self.assertNotEqual(r1.spec_id, r2.spec_id)

    def test_compile_creates_timestamps(self):
        result = compile_spec(**self._scenario())
        self.assertIsInstance(result, CompiledVerificationSpecification)
        self.assertIsNotNone(result.compiled_at)
        self.assertEqual(result.compiled_at.tzinfo, timezone.utc)


class TestVerificationDimension(unittest.TestCase):
    def test_has_exactly_the_ten_mission_sec16_values(self):
        expected = {
            "process", "outcome", "correctness", "completeness", "groundedness",
            "compliance", "safety", "state", "transition", "invariant",
        }
        self.assertEqual({d.value for d in VerificationDimension}, expected)

    def test_is_a_closed_enum_not_open_ended(self):
        with self.assertRaises(ValueError):
            VerificationDimension("not-a-real-dimension")


class TestVerificationFinding(unittest.TestCase):
    def _finding(self, **overrides):
        defaults = dict(
            finding_id="f1", criterion_id="c1", method_id="m1",
            dimension=VerificationDimension.CORRECTNESS,
            disposition=FindingDisposition.SUPPORTS,
            observation_ids=("obs1",),
        )
        defaults.update(overrides)
        return VerificationFinding(**defaults)

    def test_valid_construction(self):
        f = self._finding()
        self.assertEqual(f.disposition, FindingDisposition.SUPPORTS)

    def test_empty_observation_ids_rejected(self):
        with self.assertRaises(ValueError):
            self._finding(observation_ids=())

    def test_inconclusive_finding_still_requires_an_observation(self):
        with self.assertRaises(ValueError):
            self._finding(disposition=FindingDisposition.INCONCLUSIVE, observation_ids=())

    def test_method_and_dimension_are_independent_classifications(self):
        same_method_different_dimensions = [
            self._finding(method_id="m1", dimension=d)
            for d in (VerificationDimension.CORRECTNESS, VerificationDimension.SAFETY)
        ]
        same_dimension_different_methods = [
            self._finding(method_id=m, dimension=VerificationDimension.CORRECTNESS)
            for m in ("m1", "m2")
        ]
        self.assertEqual(len({f.dimension for f in same_method_different_dimensions}), 2)
        self.assertEqual(len({f.method_id for f in same_dimension_different_methods}), 2)

    def test_finding_disposition_distinct_from_method_disposition(self):
        self.assertEqual({d.value for d in FindingDisposition}, {"supports", "refutes", "inconclusive"})
        self.assertEqual({d.value for d in MethodDisposition}, {"conclusive", "inconclusive", "insufficient"})
        self.assertIsNot(FindingDisposition, MethodDisposition)


class TestContradiction(unittest.TestCase):
    def test_valid_construction(self):
        c = Contradiction(contradiction_id="ct1", first_claim_id="cl1", second_claim_id="cl2", description="cl1 says X, cl2 says not-X")
        self.assertNotEqual(c.first_claim_id, c.second_claim_id)

    def test_same_claim_on_both_sides_rejected(self):
        with self.assertRaises(ValueError):
            Contradiction(contradiction_id="ct1", first_claim_id="cl1", second_claim_id="cl1", description="self-contradiction")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            Contradiction(contradiction_id="ct1", first_claim_id="cl1", second_claim_id="cl2", description="")


class TestCounterArgument(unittest.TestCase):
    def test_valid_without_observations(self):
        ca = CounterArgument(counter_argument_id="ca1", target_claim_id="cl1", alternative_explanation="the test passed because of a cached result")
        self.assertEqual(ca.supporting_observation_ids, ())

    def test_valid_with_observations(self):
        ca = CounterArgument(
            counter_argument_id="ca1", target_claim_id="cl1",
            alternative_explanation="the test passed because of a cached result",
            supporting_observation_ids=("obs1", "obs2"),
        )
        self.assertEqual(len(ca.supporting_observation_ids), 2)

    def test_empty_alternative_explanation_rejected(self):
        with self.assertRaises(ValueError):
            CounterArgument(counter_argument_id="ca1", target_claim_id="cl1", alternative_explanation="")


class TestCritiqueFindingType(unittest.TestCase):
    def test_has_exactly_the_nine_v1_sec18_values(self):
        expected = {
            "unsupported_claim", "missing_evidence", "hidden_assumption", "logic_gap",
            "contradiction", "scope_violation", "false_completion", "wrong_attribution",
            "possible_counterexample",
        }
        self.assertEqual({t.value for t in CritiqueFindingType}, expected)


class TestCritique(unittest.TestCase):
    _PLAIN_TYPES = (
        CritiqueFindingType.UNSUPPORTED_CLAIM, CritiqueFindingType.MISSING_EVIDENCE,
        CritiqueFindingType.LOGIC_GAP, CritiqueFindingType.SCOPE_VIOLATION,
        CritiqueFindingType.FALSE_COMPLETION, CritiqueFindingType.WRONG_ATTRIBUTION,
    )

    def _critique(self, **overrides):
        defaults = dict(
            critique_id="cr1", finding_type=CritiqueFindingType.UNSUPPORTED_CLAIM,
            target_claim_id="cl1", description="no evidence offered for this claim",
        )
        defaults.update(overrides)
        return Critique(**defaults)

    def test_plain_types_valid_with_no_references(self):
        for finding_type in self._PLAIN_TYPES:
            c = self._critique(finding_type=finding_type)
            self.assertIsNone(c.contradiction_id)
            self.assertIsNone(c.counter_argument_id)
            self.assertIsNone(c.hidden_assumption_id)

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            self._critique(description="")

    def test_contradiction_type_requires_contradiction_id(self):
        with self.assertRaises(ValueError):
            self._critique(finding_type=CritiqueFindingType.CONTRADICTION)

    def test_contradiction_type_with_id_valid(self):
        c = self._critique(finding_type=CritiqueFindingType.CONTRADICTION, contradiction_id="ct1")
        self.assertEqual(c.contradiction_id, "ct1")

    def test_counterexample_type_requires_counter_argument_id(self):
        with self.assertRaises(ValueError):
            self._critique(finding_type=CritiqueFindingType.POSSIBLE_COUNTEREXAMPLE)

    def test_counterexample_type_with_id_valid(self):
        c = self._critique(finding_type=CritiqueFindingType.POSSIBLE_COUNTEREXAMPLE, counter_argument_id="ca1")
        self.assertEqual(c.counter_argument_id, "ca1")

    def test_hidden_assumption_type_requires_hidden_assumption_id(self):
        with self.assertRaises(ValueError):
            self._critique(finding_type=CritiqueFindingType.HIDDEN_ASSUMPTION)

    def test_hidden_assumption_type_with_id_valid(self):
        c = self._critique(finding_type=CritiqueFindingType.HIDDEN_ASSUMPTION, hidden_assumption_id="a1")
        self.assertEqual(c.hidden_assumption_id, "a1")

    def test_contradiction_id_rejected_for_wrong_type(self):
        with self.assertRaises(ValueError):
            self._critique(finding_type=CritiqueFindingType.LOGIC_GAP, contradiction_id="ct1")

    def test_counter_argument_id_rejected_for_wrong_type(self):
        with self.assertRaises(ValueError):
            self._critique(finding_type=CritiqueFindingType.LOGIC_GAP, counter_argument_id="ca1")

    def test_hidden_assumption_id_rejected_for_wrong_type(self):
        with self.assertRaises(ValueError):
            self._critique(finding_type=CritiqueFindingType.LOGIC_GAP, hidden_assumption_id="a1")

    def test_references_cannot_cross_between_types(self):
        with self.assertRaises(ValueError):
            self._critique(
                finding_type=CritiqueFindingType.HIDDEN_ASSUMPTION,
                hidden_assumption_id="a1", contradiction_id="ct1",
            )


# ---------------------------------------------------------------------------
# Batch 1 — Epistemic Spine: ClaimDependency, AssumptionSource,
#            AssumptionStatus, ReferenceQuality
# ---------------------------------------------------------------------------


class TestClaimDependency(unittest.TestCase):
    def test_valid_construction_relies_on(self):
        dep = ClaimDependency(
            claim_id="c2", depends_on_claim_id="c1",
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        self.assertEqual(dep.claim_id, "c2")
        self.assertEqual(dep.depends_on_claim_id, "c1")
        self.assertEqual(dep.dependency_type, ClaimDependencyType.RELIES_ON)

    def test_valid_construction_presupposes(self):
        dep = ClaimDependency(
            claim_id="c2", depends_on_claim_id="c1",
            dependency_type=ClaimDependencyType.PRESUPPOSES,
        )
        self.assertEqual(dep.dependency_type, ClaimDependencyType.PRESUPPOSES)

    def test_self_dependency_rejected(self):
        with self.assertRaises(ValueError):
            ClaimDependency(
                claim_id="c1", depends_on_claim_id="c1",
                dependency_type=ClaimDependencyType.RELIES_ON,
            )

    def test_dependent_and_depended_upon_are_distinct_fields(self):
        dep = ClaimDependency(
            claim_id="alpha", depends_on_claim_id="beta",
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        self.assertNotEqual(dep.claim_id, dep.depends_on_claim_id)

    def test_immutability(self):
        dep = ClaimDependency(
            claim_id="c2", depends_on_claim_id="c1",
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        with self.assertRaises(Exception):
            dep.claim_id = "tampered"

    def test_dependency_does_not_encode_support_or_refutation(self):
        dep_values = {t.value for t in ClaimDependencyType}
        for forbidden in ("supports", "refutes", "contradicts", "sufficient", "insufficient"):
            self.assertNotIn(forbidden, dep_values)

    def test_dependency_does_not_encode_authority(self):
        dep_values = {t.value for t in ClaimDependencyType}
        for forbidden in ("authoritative", "trusted", "verified", "proven"):
            self.assertNotIn(forbidden, dep_values)

    def test_no_accidental_equivalence_with_claim_origin_derived(self):
        origin_values = {o.value for o in ClaimOrigin}
        dep_values = {t.value for t in ClaimDependencyType}
        self.assertTrue(origin_values.isdisjoint(dep_values))

    def test_all_dependency_types_exist(self):
        self.assertEqual(
            {ClaimDependencyType.RELIES_ON, ClaimDependencyType.PRESUPPOSES},
            set(ClaimDependencyType),
        )

    def test_dependency_is_directional(self):
        dep_ab = ClaimDependency(claim_id="a", depends_on_claim_id="b",
                                 dependency_type=ClaimDependencyType.RELIES_ON)
        dep_ba = ClaimDependency(claim_id="b", depends_on_claim_id="a",
                                 dependency_type=ClaimDependencyType.RELIES_ON)
        self.assertNotEqual(dep_ab, dep_ba)

    def test_derived_claim_can_have_dependency(self):
        claim = Claim(claim_id="c2", content="therefore idle",
                      origin=ClaimOrigin.DERIVED)
        dep = ClaimDependency(claim_id=claim.claim_id,
                              depends_on_claim_id="c1",
                              dependency_type=ClaimDependencyType.RELIES_ON)
        self.assertEqual(dep.claim_id, claim.claim_id)


class TestAssumptionSource(unittest.TestCase):
    def test_valid_construction(self):
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.HUMAN,
            source_identifier="human:moncif",
        )
        self.assertEqual(src.source_kind, AssumptionSourceKind.HUMAN)
        self.assertEqual(src.source_identifier, "human:moncif")

    def test_empty_source_identifier_rejected(self):
        with self.assertRaises(ValueError):
            AssumptionSource(
                source_kind=AssumptionSourceKind.HUMAN,
                source_identifier="",
            )

    def test_whitespace_source_identifier_rejected(self):
        with self.assertRaises(ValueError):
            AssumptionSource(
                source_kind=AssumptionSourceKind.MODEL,
                source_identifier="   ",
            )

    def test_immutability(self):
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.SYSTEM,
            source_identifier="runtime_defaults",
        )
        with self.assertRaises(Exception):
            src.source_kind = AssumptionSourceKind.HUMAN

    def test_all_source_kinds_representable(self):
        expected = {"human", "model", "system", "policy", "documentation"}
        self.assertEqual({k.value for k in AssumptionSourceKind}, expected)

    def test_source_does_not_imply_authority(self):
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.HUMAN,
            source_identifier="human:moncif",
        )
        self.assertFalse(hasattr(src, "is_authoritative"))
        self.assertFalse(hasattr(src, "authority"))

    def test_source_is_not_observation_authority(self):
        from core.verification.epistemic import ObservationAuthority
        self.assertIsNot(AssumptionSourceKind, ObservationAuthority)

    def test_queryable_through_assumption(self):
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.DOCUMENTATION,
            source_identifier="api-spec-v2",
        )
        a = Assumption(
            assumption_id="a1",
            description="the API contract is stable",
            relied_upon_for="response schema validation",
            source=src,
        )
        self.assertIsNotNone(a.source)
        self.assertEqual(a.source.source_kind, AssumptionSourceKind.DOCUMENTATION)
        self.assertEqual(a.source.source_identifier, "api-spec-v2")


class TestAssumptionStatus(unittest.TestCase):
    def test_all_four_states_exist(self):
        expected = {"unexamined", "challenged", "confirmed", "rejected"}
        self.assertEqual({s.value for s in AssumptionStatus}, expected)

    def test_default_is_unexamined(self):
        a = Assumption(
            assumption_id="a1",
            description="db replica is current",
            relied_upon_for="freshness",
        )
        self.assertEqual(a.status, AssumptionStatus.UNEXAMINED)

    def test_unexamined_is_not_rejected(self):
        self.assertNotEqual(AssumptionStatus.UNEXAMINED, AssumptionStatus.REJECTED)

    def test_unexamined_is_not_confirmed(self):
        self.assertNotEqual(AssumptionStatus.UNEXAMINED, AssumptionStatus.CONFIRMED)

    def test_challenged_is_not_verified_failure(self):
        self.assertNotEqual(AssumptionStatus.CHALLENGED, AssumptionStatus.REJECTED)

    def test_not_interchangeable_with_verification_verdict(self):
        from core.verification.verdict import VerificationVerdict
        self.assertIsNot(AssumptionStatus, VerificationVerdict)
        self.assertNotEqual(AssumptionStatus.CONFIRMED.value, VerificationVerdict.VERIFIED.value)
        self.assertNotEqual(AssumptionStatus.REJECTED.value, VerificationVerdict.CONTRADICTED.value)

    def test_survives_round_trip(self):
        status = AssumptionStatus.UNEXAMINED
        serialized = status.value
        deserialized = AssumptionStatus(serialized)
        self.assertIs(deserialized, AssumptionStatus.UNEXAMINED)
        self.assertIsNot(deserialized, AssumptionStatus.REJECTED)

    def test_immutability_of_assumption_with_status(self):
        a = Assumption(
            assumption_id="a1",
            description="db replica is current",
            relied_upon_for="freshness",
            status=AssumptionStatus.CHALLENGED,
        )
        with self.assertRaises(Exception):
            a.status = AssumptionStatus.CONFIRMED

    def test_explicit_status_at_construction(self):
        a = Assumption(
            assumption_id="a1",
            description="API is idempotent",
            relied_upon_for="retry safety",
            status=AssumptionStatus.CONFIRMED,
        )
        self.assertEqual(a.status, AssumptionStatus.CONFIRMED)

    def test_changing_status_requires_new_instance(self):
        from dataclasses import replace
        a1 = Assumption(
            assumption_id="a1",
            description="db replica is current",
            relied_upon_for="freshness",
            status=AssumptionStatus.UNEXAMINED,
        )
        a2 = replace(a1, status=AssumptionStatus.CHALLENGED)
        self.assertEqual(a1.status, AssumptionStatus.UNEXAMINED)
        self.assertEqual(a2.status, AssumptionStatus.CHALLENGED)
        self.assertIsNot(a1, a2)


class TestReferenceQuality(unittest.TestCase):
    def test_all_four_quality_levels_exist(self):
        expected = {"unassessed", "low", "moderate", "high"}
        self.assertEqual({q.value for q in ReferenceQuality}, expected)

    def test_default_is_unassessed(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.EXPECTED_VALUE,
            content_summary="expected HTTP 200",
            source="API spec v2",
        )
        self.assertEqual(r.quality, ReferenceQuality.UNASSESSED)

    def test_explicit_quality_at_construction(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.SPECIFICATION,
            content_summary="OpenAPI schema v3",
            source="official documentation",
            quality=ReferenceQuality.HIGH,
        )
        self.assertEqual(r.quality, ReferenceQuality.HIGH)

    def test_quality_is_not_correctness(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.DOCUMENTATION,
            content_summary="outdated but well-formatted docs",
            source="wiki v1",
            quality=ReferenceQuality.HIGH,
        )
        self.assertIsInstance(r, Reference)
        self.assertNotIsInstance(r, GroundTruth)

    def test_quality_is_not_authority(self):
        self.assertFalse(hasattr(ReferenceQuality, "is_authoritative"))

    def test_high_quality_does_not_create_ground_truth(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.SPECIFICATION,
            content_summary="formal spec",
            source="standards body",
            quality=ReferenceQuality.HIGH,
        )
        self.assertIsInstance(r, Reference)
        self.assertNotIsInstance(r, GroundTruth)

    def test_existing_reference_construction_still_works(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.EXPECTED_VALUE,
            content_summary="expected 200",
            source="spec",
        )
        self.assertEqual(r.quality, ReferenceQuality.UNASSESSED)

    def test_quality_does_not_encode_freshness(self):
        for q in ReferenceQuality:
            self.assertNotIn("fresh", q.value)
            self.assertNotIn("stale", q.value)

    def test_immutability(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.PRIOR_RESULT,
            content_summary="prior run output",
            source="execution log",
            quality=ReferenceQuality.MODERATE,
        )
        with self.assertRaises(Exception):
            r.quality = ReferenceQuality.HIGH

    def test_high_quality_reference_remains_reference(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.SPECIFICATION,
            content_summary="fully validated spec",
            source="standards body official publication",
            quality=ReferenceQuality.HIGH,
        )
        self.assertIs(type(r), Reference)


class TestEpistemicSpineIntegration(unittest.TestCase):
    def test_what_claim_depends_on_what(self):
        claim_a = Claim(claim_id="ca", content="pipeline is idle",
                        origin=ClaimOrigin.DERIVED)
        claim_b = Claim(claim_id="cb", content="no jobs in queue",
                        origin=ClaimOrigin.DIRECT_ASSERTION)
        dep = ClaimDependency(
            claim_id=claim_a.claim_id,
            depends_on_claim_id=claim_b.claim_id,
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        self.assertEqual(dep.claim_id, "ca")
        self.assertEqual(dep.depends_on_claim_id, "cb")

    def test_where_assumption_came_from(self):
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.POLICY,
            source_identifier="policy:safety-critical-v1",
        )
        a = Assumption(
            assumption_id="a1",
            description="all inputs are sanitized",
            relied_upon_for="injection safety",
            source=src,
        )
        self.assertEqual(a.source.source_kind, AssumptionSourceKind.POLICY)

    def test_assumption_semantic_status(self):
        a = Assumption(
            assumption_id="a1",
            description="db replica is current",
            relied_upon_for="data freshness",
            source=AssumptionSource(
                source_kind=AssumptionSourceKind.SYSTEM,
                source_identifier="replication_monitor",
            ),
            status=AssumptionStatus.CHALLENGED,
        )
        self.assertEqual(a.status, AssumptionStatus.CHALLENGED)

    def test_reference_quality_characterization(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.DOCUMENTATION,
            content_summary="API reference v3.2",
            source="official documentation portal",
            quality=ReferenceQuality.HIGH,
        )
        self.assertEqual(r.quality, ReferenceQuality.HIGH)

    def test_existing_contracts_remain_valid(self):
        c = Claim(claim_id="c1", content="the API returns 200",
                  origin=ClaimOrigin.DIRECT_ASSERTION)
        self.assertIsNone(c.source_observation_id)

        a = Assumption(assumption_id="a1",
                       description="the database replica is current",
                       relied_upon_for="freshness of the queried target state")
        self.assertEqual(a.assumption_id, "a1")
        self.assertIsNone(a.source)
        self.assertEqual(a.status, AssumptionStatus.UNEXAMINED)

        r = Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE,
                      content_summary="expected HTTP 200", source="API spec v2")
        self.assertEqual(r.kind, ReferenceKind.EXPECTED_VALUE)
        self.assertEqual(r.quality, ReferenceQuality.UNASSESSED)

        gt = GroundTruth(ground_truth_id="gt1", reference_id="r1",
                         established_by="human:moncif",
                         established_via="human_review")
        self.assertEqual(gt.established_via, "human_review")

        o = Oracle(oracle_id="o1", description="reference implementation diff",
                   is_executable=True, is_reproducible=True, is_validated=False)
        self.assertFalse(o.is_authoritative)



# ---------------------------------------------------------------------------
# Phase 4 evidence contracts (WORK IN PROGRESS, not complete) -- tests only
# for behavior the contracts actually implement.  What they deliberately do
# NOT enforce is listed in core/verification/evidence.py "Enforcement
# boundary"; nothing below claims otherwise.
# ---------------------------------------------------------------------------

_EV_NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _ev_source():
    return EvidenceSource("tool_result", "s1", "runtime")


def _ev_item(eid="e1", directness=EvidenceDirectness.DIRECT,
             status=EvidenceStatus.SUFFICIENT, supports=(), restatement=False,
             locator="L10-L12", source=None):
    return EvidenceItem(
        evidence_id=eid, source=source or _ev_source(), locator=locator,
        directness=directness, status=status, observed_at=_EV_NOW,
        retrieved_at=_EV_NOW, content_summary="short summary",
        supports_claim_ids=supports, is_restatement_of_claim=restatement,
    )


def _ev_observation(oid="o1", authority=ObservationAuthority.RUNTIME):
    return Observation(
        observation_id=oid, authority=authority, form=ObservationForm.TEXTUAL,
        content_summary="captured output", observed_at=_EV_NOW, locator="L1",
    )


def _ev_reference(**over):
    kwargs = dict(evidence_id="e1", source=_ev_source(), locator="L10-L12",
                  provenance=ProvenanceCompleteness.COMPLETE, claim_id="c1")
    kwargs.update(over)
    return EvidenceReference(**kwargs)


def _ev_transformation(**over):
    kwargs = dict(
        source_evidence_id="e1", source_directness=EvidenceDirectness.DIRECT,
        source_provenance=ProvenanceCompleteness.COMPLETE,
        transformation_type=TransformationType.SUMMARY,
        transformation_version="1.0.0", transformation_producer="summarizer",
        result_evidence_id="e2", result_directness=EvidenceDirectness.DERIVED,
        result_provenance=ProvenanceCompleteness.COMPLETE,
    )
    kwargs.update(over)
    return EvidenceTransformation(**kwargs)


class TestEvidenceReference(unittest.TestCase):
    def test_preserves_exact_source_locator_and_binding(self):
        ref = _ev_reference(criterion_id="crit1")
        self.assertEqual(ref.evidence_id, "e1")
        self.assertEqual(ref.source, _ev_source())
        self.assertEqual(ref.locator, "L10-L12")
        self.assertEqual(ref.claim_id, "c1")
        self.assertEqual(ref.criterion_id, "crit1")

    def test_claim_only_and_criterion_only_bindings_are_valid(self):
        self.assertIsNone(_ev_reference(claim_id="c1", criterion_id=None).criterion_id)
        self.assertIsNone(_ev_reference(claim_id=None, criterion_id="crit1").claim_id)

    def test_is_immutable(self):
        ref = _ev_reference()
        with self.assertRaises(FrozenInstanceError):
            ref.locator = "elsewhere"

    def test_blank_locator_rejected(self):
        for bad in ("", "   "):
            with self.assertRaises(ValueError):
                _ev_reference(locator=bad)

    def test_blank_source_identity_rejected(self):
        for bad_source in (EvidenceSource("", "s1", "runtime"),
                           EvidenceSource("tool_result", " ", "runtime"),
                           EvidenceSource("tool_result", "s1", "")):
            with self.assertRaises(ValueError):
                _ev_reference(source=bad_source)

    def test_unbound_reference_rejected(self):
        # Claim -> Evidence chain needs a claim and/or criterion at one end.
        with self.assertRaises(ValueError):
            _ev_reference(claim_id=None, criterion_id=None)

    def test_has_no_payload_channel(self):
        # Content/directness/status stay on EvidenceItem (single source of truth).
        self.assertEqual({f.name for f in dataclass_fields(EvidenceReference)}, {"evidence_id", "source", "locator", "provenance", "claim_id", "criterion_id"})
        with self.assertRaises(TypeError):
            _ev_reference(content_summary="x" * 100000)

    def test_all_four_provenance_states_preserved(self):
        self.assertEqual(len(list(ProvenanceCompleteness)), 4)
        for state in ProvenanceCompleteness:
            self.assertEqual(_ev_reference(provenance=state).provenance, state)

    def test_verify_against_accepts_the_matching_item(self):
        self.assertIsNone(_ev_reference().verify_against(_ev_item()))

    def test_verify_against_rejects_drifted_id(self):
        with self.assertRaises(EvidenceBindingError):
            _ev_reference().verify_against(_ev_item(eid="e2"))

    def test_verify_against_rejects_drifted_source(self):
        other = EvidenceSource("tool_result", "OTHER", "runtime")
        with self.assertRaises(EvidenceBindingError):
            _ev_reference().verify_against(_ev_item(source=other))

    def test_verify_against_rejects_drifted_locator(self):
        with self.assertRaises(EvidenceBindingError):
            _ev_reference().verify_against(_ev_item(locator="L99"))

    def test_verify_against_says_nothing_about_support(self):
        item = _ev_item(status=EvidenceStatus.CONTRADICTORY, supports=())
        self.assertIsNone(_ev_reference(claim_id="c1").verify_against(item))

    def test_verify_against_is_status_blind(self):
        for state in EvidenceStatus:
            self.assertIsNone(_ev_reference().verify_against(_ev_item(status=state)))

    def test_claim_bound_reference_cannot_bind_a_claim_to_its_own_restatement(self):
        restatement = _ev_item("e1", supports=("c1",), restatement=True)
        with self.assertRaises(CircularEvidenceError):
            _ev_reference(claim_id="c1").verify_against(restatement)

    def test_restatement_of_a_different_claim_is_not_circular_for_this_reference(self):
        other = _ev_item("e1", supports=("c1",), restatement=True)
        self.assertIsNone(_ev_reference(claim_id="c2").verify_against(other))


class TestEvidenceObservation(unittest.TestCase):
    def _link(self, **over):
        kwargs = dict(evidence_id="e1", observation_id="o1",
                      provenance=ProvenanceCompleteness.COMPLETE)
        kwargs.update(over)
        return EvidenceObservation(**kwargs)

    def test_binds_evidence_to_observation_by_id(self):
        link = self._link(provenance=ProvenanceCompleteness.PARTIAL)
        self.assertEqual(link.evidence_id, "e1")
        self.assertEqual(link.observation_id, "o1")
        self.assertEqual(link.provenance, ProvenanceCompleteness.PARTIAL)

    def test_is_immutable(self):
        link = self._link()
        with self.assertRaises(FrozenInstanceError):
            link.observation_id = "o2"

    def test_blank_ids_rejected(self):
        for bad in ("", "  "):
            with self.assertRaises(ValueError):
                self._link(evidence_id=bad)
            with self.assertRaises(ValueError):
                self._link(observation_id=bad)

    def test_defines_no_authority_of_its_own(self):
        self.assertEqual({f.name for f in dataclass_fields(EvidenceObservation)}, {"evidence_id", "observation_id", "provenance"})
        with self.assertRaises(TypeError):
            self._link(authority=ObservationAuthority.RUNTIME)

    def test_verify_against_matching_observation_is_authority_independent(self):
        link = self._link()
        for authority in ObservationAuthority:
            self.assertIsNone(link.verify_against(_ev_observation(authority=authority)))

    def test_verify_against_rejects_another_observation(self):
        with self.assertRaises(EvidenceBindingError):
            self._link().verify_against(_ev_observation(oid="o2"))

    def test_an_interpretation_is_not_evidence_provenance(self):
        # Observation -> Interpretation -> Claim is not Observation -> Evidence.
        reading = Interpretation(observation_id="o1", meaning="file exists",
                                 interpreted_by="deterministic_rule")
        with self.assertRaises(TypeError):
            self._link().verify_against(reading)

    def test_all_four_provenance_states_preserved(self):
        for state in ProvenanceCompleteness:
            self.assertEqual(self._link(provenance=state).provenance, state)


class TestEvidenceTransformation(unittest.TestCase):
    def test_lineage_is_fully_reconstructable(self):
        tx = _ev_transformation(transformation_type=TransformationType.OCR)
        self.assertEqual(tx.source_evidence_id, "e1")
        self.assertEqual(tx.transformation_type, TransformationType.OCR)
        self.assertEqual(tx.transformation_version, "1.0.0")
        self.assertEqual(tx.transformation_producer, "summarizer")
        self.assertEqual(tx.result_evidence_id, "e2")

    def test_is_immutable(self):
        tx = _ev_transformation()
        with self.assertRaises(FrozenInstanceError):
            tx.result_directness = EvidenceDirectness.DIRECT

    def test_incomplete_lineage_rejected(self):
        for bad in ("", "  "):
            with self.assertRaises(ValueError):
                _ev_transformation(transformation_version=bad)
            with self.assertRaises(ValueError):
                _ev_transformation(transformation_producer=bad)

    def test_source_and_result_must_be_distinct(self):
        with self.assertRaises(ValueError):
            _ev_transformation(source_evidence_id="e1", result_evidence_id="e1")

    def test_non_direct_source_can_never_yield_direct(self):
        for source in (EvidenceDirectness.INDIRECT, EvidenceDirectness.DERIVED,
                       EvidenceDirectness.MODEL_INTERPRETATION):
            for ttype in TransformationType:
                with self.assertRaises(ValueError):
                    _ev_transformation(source_directness=source, transformation_type=ttype,
                                       result_directness=EvidenceDirectness.DIRECT)

    def test_model_interpretation_source_is_permanent(self):
        model = EvidenceDirectness.MODEL_INTERPRETATION
        for ttype in TransformationType:
            for result in EvidenceDirectness:
                if result == model:
                    tx = _ev_transformation(source_directness=model, transformation_type=ttype,
                                            result_directness=result)
                    self.assertEqual(tx.result_directness, model)
                else:
                    with self.assertRaises(ValueError):
                        _ev_transformation(source_directness=model, transformation_type=ttype,
                                           result_directness=result)

    def test_model_interpretation_transformation_of_direct_source_stays_model(self):
        model = EvidenceDirectness.MODEL_INTERPRETATION
        for result in EvidenceDirectness:
            if result == model:
                tx = _ev_transformation(transformation_type=TransformationType.MODEL_INTERPRETATION,
                                        result_directness=result)
                self.assertEqual(tx.result_directness, model)
            else:
                with self.assertRaises(ValueError):
                    _ev_transformation(transformation_type=TransformationType.MODEL_INTERPRETATION,
                                       result_directness=result)

    def test_incomplete_provenance_never_silently_becomes_complete(self):
        for source in (ProvenanceCompleteness.PARTIAL, ProvenanceCompleteness.UNKNOWN,
                       ProvenanceCompleteness.BROKEN):
            with self.assertRaises(ValueError):
                _ev_transformation(source_provenance=source,
                                   result_provenance=ProvenanceCompleteness.COMPLETE)
        kept = _ev_transformation(source_provenance=ProvenanceCompleteness.BROKEN,
                                  result_provenance=ProvenanceCompleteness.BROKEN)
        self.assertEqual(kept.result_provenance, ProvenanceCompleteness.BROKEN)
        weakened = _ev_transformation(result_provenance=ProvenanceCompleteness.UNKNOWN)
        self.assertEqual(weakened.result_provenance, ProvenanceCompleteness.UNKNOWN)

    def test_direct_to_direct_via_non_model_transformation_is_left_to_higher_layers(self):
        # Documented boundary, not a claim of enforcement: the frozen
        # architecture gives no categorical per-type table for what a
        # redaction/normalization "justifies", so this record accepts it.
        for ttype in TransformationType:
            if ttype == TransformationType.MODEL_INTERPRETATION:
                continue
            tx = _ev_transformation(transformation_type=ttype,
                                    result_directness=EvidenceDirectness.DIRECT)
            self.assertEqual(tx.result_directness, EvidenceDirectness.DIRECT)

    def test_verify_against_accepts_items_matching_the_record(self):
        tx = _ev_transformation()
        source = _ev_item("e1", directness=EvidenceDirectness.DIRECT)
        result = _ev_item("e2", directness=EvidenceDirectness.DERIVED)
        self.assertIsNone(tx.verify_against(source, result))

    def test_verify_against_catches_a_record_that_misstates_source_directness(self):
        # The record alone looks safe (DIRECT -> DERIVED); the real source
        # item is a model interpretation being laundered.
        tx = _ev_transformation(source_directness=EvidenceDirectness.DIRECT,
                                result_directness=EvidenceDirectness.DERIVED)
        real_source = _ev_item("e1", directness=EvidenceDirectness.MODEL_INTERPRETATION)
        result = _ev_item("e2", directness=EvidenceDirectness.DERIVED)
        with self.assertRaises(EvidenceBindingError):
            tx.verify_against(real_source, result)

    def test_verify_against_catches_a_record_that_misstates_result_directness(self):
        tx = _ev_transformation(result_directness=EvidenceDirectness.DERIVED)
        source = _ev_item("e1", directness=EvidenceDirectness.DIRECT)
        real_result = _ev_item("e2", directness=EvidenceDirectness.DIRECT)
        with self.assertRaises(EvidenceBindingError):
            tx.verify_against(source, real_result)

    def test_verify_against_rejects_wrong_ids(self):
        tx = _ev_transformation()
        good_source = _ev_item("e1", directness=EvidenceDirectness.DIRECT)
        good_result = _ev_item("e2", directness=EvidenceDirectness.DERIVED)
        with self.assertRaises(EvidenceBindingError):
            tx.verify_against(_ev_item("eX", directness=EvidenceDirectness.DIRECT), good_result)
        with self.assertRaises(EvidenceBindingError):
            tx.verify_against(good_source, _ev_item("eX", directness=EvidenceDirectness.DERIVED))

    def test_verify_against_blocks_laundering_circular_evidence_through_lineage(self):
        tx = _ev_transformation()
        restated = _ev_item("e1", directness=EvidenceDirectness.DIRECT, supports=("c1",), restatement=True)
        laundered = _ev_item("e2", directness=EvidenceDirectness.DERIVED, supports=("c1",), restatement=False)
        with self.assertRaises(CircularEvidenceError):
            tx.verify_against(restated, laundered)

    def test_restatement_flag_kept_through_lineage_is_still_caught_by_the_bundle(self):
        tx = _ev_transformation()
        restated = _ev_item("e1", directness=EvidenceDirectness.DIRECT, supports=("c1",), restatement=True)
        kept = _ev_item("e2", directness=EvidenceDirectness.DERIVED, supports=("c1",), restatement=True)
        self.assertIsNone(tx.verify_against(restated, kept))
        with self.assertRaises(CircularEvidenceError):
            EvidenceBundle(items=(kept,), claim_id="c1")

    def test_transformation_of_a_non_restatement_is_not_over_blocked(self):
        tx = _ev_transformation()
        plain = _ev_item("e1", directness=EvidenceDirectness.DIRECT, supports=("c1",), restatement=False)
        derived = _ev_item("e2", directness=EvidenceDirectness.DERIVED, supports=("c1",), restatement=False)
        self.assertIsNone(tx.verify_against(plain, derived))
        self.assertEqual(EvidenceBundle(items=(derived,), claim_id="c1").claim_id, "c1")


class TestEvidenceBundle(unittest.TestCase):
    def test_preserves_every_evidence_status_in_order_without_filtering(self):
        items = tuple(_ev_item("e%d" % n, status=state) for n, state in enumerate(EvidenceStatus))
        bundle = EvidenceBundle(items=items, claim_id="c1")
        self.assertEqual(len(bundle.items), 6)
        self.assertEqual(tuple(i.status for i in bundle.items), tuple(EvidenceStatus))
        self.assertEqual(bundle.evidence_ids, tuple(i.evidence_id for i in items))
        for kept, original in zip(bundle.items, items):
            self.assertIs(kept, original)

    def test_contradictory_only_bundle_is_not_resolved(self):
        bundle = EvidenceBundle(items=(_ev_item(status=EvidenceStatus.CONTRADICTORY),), claim_id="c1")
        self.assertEqual(bundle.items[0].status, EvidenceStatus.CONTRADICTORY)

    def test_membership_implies_no_support(self):
        unrelated = _ev_item("e1", supports=())
        elsewhere = _ev_item("e2", supports=("c9",))
        bundle = EvidenceBundle(items=(unrelated, elsewhere), claim_id="c1")
        self.assertNotIn("c1", bundle.items[0].supports_claim_ids)
        self.assertNotIn("c1", bundle.items[1].supports_claim_ids)

    def test_is_immutable(self):
        bundle = EvidenceBundle(items=(_ev_item(),), claim_id="c1")
        with self.assertRaises(FrozenInstanceError):
            bundle.claim_id = "c2"
        with self.assertRaises(AttributeError):
            bundle.items.append(_ev_item("e2"))

    def test_mutable_container_rejected(self):
        with self.assertRaises(TypeError):
            EvidenceBundle(items=[_ev_item()], claim_id="c1")

    def test_empty_bundle_rejected(self):
        # Missing evidence is not representable as an empty bundle.
        with self.assertRaises(ValueError):
            EvidenceBundle(items=(), claim_id="c1")

    def test_duplicate_evidence_ids_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceBundle(items=(_ev_item("e1"), _ev_item("e1")), claim_id="c1")

    def test_unbound_bundle_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceBundle(items=(_ev_item(),))

    def test_criterion_only_binding_is_valid(self):
        self.assertEqual(EvidenceBundle(items=(_ev_item(),), criterion_id="crit1").criterion_id, "crit1")

    def test_non_evidence_item_members_rejected(self):
        with self.assertRaises(TypeError):
            EvidenceBundle(items=(_ev_reference(),), claim_id="c1")

    def test_restatement_of_bound_claim_cannot_enter_the_bundle(self):
        circular = _ev_item("e1", supports=("c1",), restatement=True)
        with self.assertRaises(CircularEvidenceError):
            EvidenceBundle(items=(circular,), claim_id="c1")

    def test_restatement_of_a_different_claim_is_not_circular_for_this_claim(self):
        other = _ev_item("e1", supports=("c1",), restatement=True)
        self.assertEqual(EvidenceBundle(items=(other,), claim_id="c2").claim_id, "c2")


class TestMinimumSufficientEvidence(unittest.TestCase):
    def _bundle(self):
        return EvidenceBundle(items=(
            _ev_item("e1", status=EvidenceStatus.SUFFICIENT),
            _ev_item("e2", status=EvidenceStatus.CONTRADICTORY),
            _ev_item("e3", status=EvidenceStatus.INSUFFICIENT),
        ), claim_id="c1", criterion_id="crit1")

    def test_declares_required_evidence_for_a_decision(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1", "e2"), claim_id="c1")
        self.assertEqual(mse.required_evidence_ids, ("e1", "e2"))
        self.assertEqual(mse.claim_id, "c1")

    def test_is_immutable_and_rejects_mutable_container(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1",), claim_id="c1")
        with self.assertRaises(FrozenInstanceError):
            mse.claim_id = "c2"
        with self.assertRaises(TypeError):
            MinimumSufficientEvidence(required_evidence_ids=["e1"], claim_id="c1")

    def test_invalid_declarations_rejected(self):
        with self.assertRaises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=(), claim_id="c1")
        with self.assertRaises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=("e1", "e1"), claim_id="c1")
        with self.assertRaises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=("e1", " "), claim_id="c1")
        with self.assertRaises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=("e1",))

    def test_does_not_duplicate_the_criterion_evidence_floor(self):
        mse_fields = {f.name for f in dataclass_fields(MinimumSufficientEvidence)}
        self.assertEqual(mse_fields, {"required_evidence_ids", "claim_id", "criterion_id"})
        self.assertFalse((mse_fields & {f.name for f in dataclass_fields(CriterionEvidenceRequirement)}))

    def test_verify_against_accepts_a_bundle_that_retains_everything_required(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1", "e2"), claim_id="c1")
        self.assertIsNone(mse.verify_against(self._bundle()))

    def test_requirement_is_status_blind_and_not_a_sufficiency_judgment(self):
        # Reconstructing the decision needs the CONTRADICTORY and INSUFFICIENT
        # items too; "required for audit" is not EvidenceStatus.SUFFICIENT.
        mse = MinimumSufficientEvidence(required_evidence_ids=("e2", "e3"), claim_id="c1")
        self.assertIsNone(mse.verify_against(self._bundle()))
        statuses = tuple(i.status for i in self._bundle().items)
        self.assertEqual(statuses, (EvidenceStatus.SUFFICIENT, EvidenceStatus.CONTRADICTORY, EvidenceStatus.INSUFFICIENT))

    def test_verify_against_rejects_a_bundle_missing_required_evidence(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1", "e404"), claim_id="c1")
        with self.assertRaises(EvidenceBindingError):
            mse.verify_against(self._bundle())

    def test_verify_against_rejects_a_bundle_for_another_claim_or_criterion(self):
        with self.assertRaises(EvidenceBindingError):
            MinimumSufficientEvidence(required_evidence_ids=("e1",), claim_id="c2").verify_against(self._bundle())
        with self.assertRaises(EvidenceBindingError):
            MinimumSufficientEvidence(required_evidence_ids=("e1",), criterion_id="crit2").verify_against(self._bundle())


class TestEvidenceChainReconstruction(unittest.TestCase):
    def test_claim_to_observation_chain_is_reconstructable_from_structured_records(self):
        # Claim C7 -> Evidence E14 -> Source S2 -> Locator L9 -> Observation O4
        item = _ev_item("e14", locator="L9")
        reference = _ev_reference(evidence_id="e14", locator="L9", claim_id="c7")
        link = EvidenceObservation(evidence_id="e14", observation_id="o4",
                                   provenance=ProvenanceCompleteness.COMPLETE)
        observation = _ev_observation("o4", ObservationAuthority.RUNTIME)
        bundle = EvidenceBundle(items=(item,), claim_id="c7")

        self.assertIsNone(reference.verify_against(item))
        self.assertIsNone(link.verify_against(observation))
        self.assertEqual(reference.claim_id, "c7")
        self.assertIn(reference.evidence_id, bundle.evidence_ids)
        self.assertEqual(reference.source, item.source)
        self.assertEqual(reference.locator, item.locator)
        self.assertEqual(link.evidence_id, reference.evidence_id)
        self.assertEqual(link.observation_id, observation.observation_id)
        self.assertEqual(observation.authority, ObservationAuthority.RUNTIME)



# ---------------------------------------------------------------------------
# Batch 3A -- VerificationConstruct / ConstructValidity (core/verification/construct.py)
# ---------------------------------------------------------------------------

def _c3_criterion(cid):
    return Criterion(
        criterion_id=cid, rubric_id="r3a", description="d",
        applicability=CriterionApplicability(applies_unconditionally=True),
        evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
    )


def _c3_rubric(**over):
    kwargs = dict(
        rubric_id="r3a", version="1.0.0", fingerprint="fp-abc123",
        created_from="obligation o1", created_by="session", derived_from="requirement",
        source_requirements=("req1",), context_basis="target snapshot t1",
        criteria=("c1",), construct=VerificationConstruct(description="measures grounding"),
    )
    kwargs.update(over)
    return Rubric(**kwargs)


def _c3_result(verdict=VerificationVerdict.VERIFIED, confidence=0.95):
    assurance = VerificationAssurance(
        basis=VerificationBasis(frozenset({BasisComponent.DETERMINISTIC})),
        observation_authority=ObservationAuthority.FILESYSTEM,
        inspection_authorization=InspectionAuthorization(surface="fs:/tmp", authorized=True),
        assurance_scope="artifact_existence", coverage=1.0,
        independence_level="single_verifier", integrity_verified=True,
    )
    return VerificationResult(
        verification_id=new_id(), task_id=new_id(), execution_id=new_id(),
        attempt_id=new_id(), verdict=verdict, assurance=assurance, confidence=confidence,
    )


class TestVerificationConstruct(unittest.TestCase):
    def test_preserves_description(self):
        construct = VerificationConstruct(description="the answer cites only retrieved sources")
        self.assertEqual(construct.description, "the answer cites only retrieved sources")

    def test_is_immutable(self):
        construct = VerificationConstruct(description="d")
        with self.assertRaises(FrozenInstanceError):
            construct.description = "other"

    def test_blank_descriptions_rejected(self):
        for bad in ("", " ", "   ", "\n\t", "\u00a0\u2003"):
            with self.assertRaises(ValueError):
                VerificationConstruct(description=bad)

    def test_non_string_description_rejected(self):
        for bad in (None, 5, b"bytes", ["a"]):
            with self.assertRaises(ValueError):
                VerificationConstruct(description=bad)

    def test_description_with_content_inside_whitespace_is_valid(self):
        self.assertEqual(VerificationConstruct(description="  padded  ").description, "  padded  ")

    def test_has_no_independent_identity_or_speculative_fields(self):
        self.assertEqual({f.name for f in dataclass_fields(VerificationConstruct)}, {"description"})
        with self.assertRaises(TypeError):
            VerificationConstruct(description="d", construct_id="k1")

    def test_is_a_value_object_equal_by_content(self):
        self.assertEqual(VerificationConstruct(description="x"), VerificationConstruct(description="x"))
        self.assertNotEqual(VerificationConstruct(description="x"), VerificationConstruct(description="y"))
        self.assertEqual(hash(VerificationConstruct(description="x")), hash(VerificationConstruct(description="x")))


class TestRubricConstructIntegration(unittest.TestCase):
    def test_rubric_carries_its_construct(self):
        construct = VerificationConstruct(description="measures factual grounding")
        self.assertIs(_c3_rubric(construct=construct).construct, construct)

    def test_a_rubric_cannot_be_built_without_a_construct(self):
        # No construct-less state, DRAFT included.
        kwargs = dict(
            rubric_id="r3a", version="1.0.0", fingerprint="fp", created_from="o",
            created_by="s", derived_from="d", source_requirements=("req1",),
            context_basis="t", criteria=("c1",),
        )
        with self.assertRaises(TypeError):
            Rubric(**kwargs)

    def test_none_is_not_a_construct(self):
        with self.assertRaises(TypeError):
            _c3_rubric(construct=None)
        self.assertEqual(_c3_rubric().lock_state, RubricLockState.DRAFT)
        self.assertIsInstance(_c3_rubric().construct, VerificationConstruct)

    def test_a_non_construct_is_rejected_not_coerced(self):
        for bad in ("measures factual grounding", {"description": "d"}, 5):
            with self.assertRaises(TypeError):
                _c3_rubric(construct=bad)

    def test_construct_survives_every_lock_state_transition(self):
        construct = VerificationConstruct(description="measures factual grounding")
        rubric = _c3_rubric(construct=construct)
        validated = rubric.advance_to(RubricLockState.VALIDATED, criteria=[_c3_criterion("c1")])
        compiled = validated.advance_to(RubricLockState.COMPILED)
        locked = compiled.advance_to(RubricLockState.LOCKED)
        for stage in (validated, compiled, locked):
            self.assertIs(stage.construct, construct)

    def test_construct_does_not_weaken_existing_rubric_validation(self):
        construct = VerificationConstruct(description="d")
        with self.assertRaises(ValueError):
            _c3_rubric(construct=construct, criteria=())
        with self.assertRaises(RubricValidationError):
            _c3_rubric(construct=construct, criteria=("c1", "c1"))


class TestConstructValidityStatus(unittest.TestCase):
    def test_closed_four_state_vocabulary(self):
        self.assertEqual({m.name for m in ConstructValidityStatus}, {"NOT_EVALUATED", "SUPPORTED", "CONTESTED", "UNSUPPORTED"})
        with self.assertRaises(ValueError):
            ConstructValidityStatus("construct_bogus")

    def test_values_are_disjoint_from_neighbouring_vocabularies(self):
        # str enums with equal values compare equal and collide as dict keys,
        # so the values must not overlap any status-like enum in the package.
        mine = {m.value for m in ConstructValidityStatus}
        for other in (VerificationVerdict, AssumptionStatus, EvidenceStatus, ReferenceQuality, RubricLockState, ProvenanceCompleteness):
            self.assertFalse((mine & {m.value for m in other}))

    def test_unsupported_is_not_the_verdict_unsupported(self):
        # VerificationVerdict already has UNSUPPORTED; sharing its string value
        # would make these compare equal and collide as dict keys.
        self.assertNotEqual(ConstructValidityStatus.UNSUPPORTED, VerificationVerdict.UNSUPPORTED)
        self.assertIsNone({VerificationVerdict.UNSUPPORTED: "verdict"}.get(ConstructValidityStatus.UNSUPPORTED))

    def test_each_state_survives_serialization_without_collapsing(self):
        for state in ConstructValidityStatus:
            original = ConstructValidity(rubric_fingerprint="fp-abc123", status=state)
            wire = json.dumps({"rubric_fingerprint": original.rubric_fingerprint, "status": original.status.value})
            data = json.loads(wire)
            restored = ConstructValidity(rubric_fingerprint=data["rubric_fingerprint"], status=ConstructValidityStatus(data["status"]))
            self.assertEqual(restored, original)
            self.assertIs(restored.status, state)

    def test_not_evaluated_is_not_a_default_outcome_of_any_other_state(self):
        others = [s for s in ConstructValidityStatus if s != ConstructValidityStatus.NOT_EVALUATED]
        self.assertEqual(len(others), 3)
        for state in others:
            self.assertNotEqual(ConstructValidity("fp", state).status, ConstructValidityStatus.NOT_EVALUATED)


class TestConstructValidity(unittest.TestCase):
    def test_records_the_assessed_rubric_fingerprint_and_status(self):
        validity = ConstructValidity(rubric_fingerprint="fp-abc123", status=ConstructValidityStatus.SUPPORTED)
        self.assertEqual(validity.rubric_fingerprint, "fp-abc123")
        self.assertEqual(validity.status, ConstructValidityStatus.SUPPORTED)

    def test_is_immutable(self):
        validity = ConstructValidity("fp", ConstructValidityStatus.CONTESTED)
        with self.assertRaises(FrozenInstanceError):
            validity.status = ConstructValidityStatus.SUPPORTED

    def test_blank_fingerprint_rejected(self):
        for bad in ("", "  ", None, 7):
            with self.assertRaises(ValueError):
                ConstructValidity(rubric_fingerprint=bad, status=ConstructValidityStatus.SUPPORTED)

    def test_status_must_be_a_construct_validity_status(self):
        # Not a verdict, not a confidence value, not a bare string.
        for bad in (VerificationVerdict.VERIFIED, VerificationVerdict.UNSUPPORTED, AssumptionStatus.CONFIRMED,
                    "construct_supported", 0.9, None):
            with self.assertRaises(TypeError):
                ConstructValidity(rubric_fingerprint="fp", status=bad)

    def test_has_no_stability_confidence_verdict_consistency_or_score_field(self):
        self.assertEqual({f.name for f in dataclass_fields(ConstructValidity)}, {"rubric_fingerprint", "status"})
        for extra in ("stability", "confidence", "verdict", "consistency", "score"):
            with self.assertRaises(TypeError):
                ConstructValidity("fp", ConstructValidityStatus.SUPPORTED, **{extra: 1})

    def test_validity_and_verdict_are_independent_axes_with_no_implied_mapping(self):
        # No verdict forces, or is forced by, any validity status: every
        # combination is representable and neither side moves the other.
        for verdict in VerificationVerdict:
            result = _c3_result(verdict=verdict, confidence=0.5)
            for state in ConstructValidityStatus:
                validity = ConstructValidity("fp", state)
                self.assertEqual(result.verdict, verdict)
                self.assertEqual(result.confidence, 0.5)
                self.assertEqual(validity.status, state)

    def test_a_verified_verdict_does_not_imply_a_supported_construct(self):
        verified = _c3_result(verdict=VerificationVerdict.VERIFIED, confidence=0.99)
        unsupported = ConstructValidity("fp", ConstructValidityStatus.UNSUPPORTED)
        self.assertEqual(verified.verdict, VerificationVerdict.VERIFIED)
        self.assertEqual(unsupported.status, ConstructValidityStatus.UNSUPPORTED)

    def test_results_and_receipts_carry_no_construct_validity_state(self):
        for contract in (VerificationResult, VerificationAssurance, VerificationReceipt):
            self.assertFalse(any("construct" in f.name.lower() for f in dataclass_fields(contract)))


class TestConstructValidityAndRubricIdentity(unittest.TestCase):
    def test_validity_is_linked_to_the_rubric_only_by_fingerprint_value(self):
        rubric = _c3_rubric(construct=VerificationConstruct(description="measures grounding"))
        validity = ConstructValidity(rubric_fingerprint=rubric.fingerprint, status=ConstructValidityStatus.SUPPORTED)
        self.assertEqual(validity.rubric_fingerprint, rubric.fingerprint)
        self.assertEqual(rubric.construct.description, "measures grounding")

    def test_neither_type_holds_a_reference_to_the_other(self):
        rubric_hints = get_type_hints(Rubric)
        validity_hints = get_type_hints(ConstructValidity)
        self.assertFalse(any("ConstructValidity" in str(t) for t in rubric_hints.values()))
        self.assertFalse(any("Rubric" in str(t) for t in validity_hints.values()))

    def test_assessing_a_rubric_leaves_its_identity_unchanged(self):
        rubric = _c3_rubric(construct=VerificationConstruct(description="d"))
        snapshot = (rubric, hash(rubric), rubric.fingerprint, rubric.lock_state, rubric.construct)
        for state in ConstructValidityStatus:
            ConstructValidity(rubric_fingerprint=rubric.fingerprint, status=state)
        self.assertEqual((rubric, hash(rubric), rubric.fingerprint, rubric.lock_state, rubric.construct), snapshot)

    def test_a_changed_assessment_is_a_new_record_and_the_old_one_keeps_its_meaning(self):
        rubric = _c3_rubric()
        first = ConstructValidity(rubric.fingerprint, ConstructValidityStatus.NOT_EVALUATED)
        second = ConstructValidity(rubric.fingerprint, ConstructValidityStatus.CONTESTED)
        self.assertEqual(first.status, ConstructValidityStatus.NOT_EVALUATED)
        self.assertEqual(second.status, ConstructValidityStatus.CONTESTED)
        self.assertNotEqual(first, second)

    def test_a_locked_rubric_is_unaffected_by_any_validity_record(self):
        rubric = _c3_rubric(construct=VerificationConstruct(description="d"))
        locked = (rubric.advance_to(RubricLockState.VALIDATED, criteria=[_c3_criterion("c1")])
                  .advance_to(RubricLockState.COMPILED).advance_to(RubricLockState.LOCKED))
        before = locked
        ConstructValidity(locked.fingerprint, ConstructValidityStatus.UNSUPPORTED)
        self.assertEqual(locked, before)
        self.assertEqual(locked.lock_state, RubricLockState.LOCKED)



# ---------------------------------------------------------------------------
# Batch 3B -- five coverage types (coverage.py) and observation-absence states
# (absence.py).  VerificationObservation is deliberately NOT part of 3B.
# ---------------------------------------------------------------------------

_COVERAGE_TYPES = (TaskCoverage, VerificationCoverage, CriterionCoverage, EvidenceCoverage, ObservationCoverage)


class TestCoverageTypes(unittest.TestCase):
    def test_each_type_preserves_fraction_and_scope(self):
        for cls in _COVERAGE_TYPES:
            cov = cls(fraction=0.4, scope="requirements in the task statement")
            self.assertEqual(cov.fraction, 0.4)
            self.assertEqual(cov.scope, "requirements in the task statement")

    def test_zero_and_one_are_valid_boundaries(self):
        for cls in _COVERAGE_TYPES:
            self.assertEqual(cls(fraction=0.0, scope="s").fraction, 0.0)
            self.assertEqual(cls(fraction=1.0, scope="s").fraction, 1.0)
            self.assertEqual(cls(fraction=1, scope="s").fraction, 1)

    def test_out_of_range_and_non_finite_fractions_rejected(self):
        for cls in _COVERAGE_TYPES:
            for bad in (-0.0001, 1.0001, 2, -1, float("nan"), float("inf"), float("-inf")):
                with self.assertRaises(ValueError):
                    cls(fraction=bad, scope="s")

    def test_non_numeric_and_boolean_fractions_rejected(self):
        # bool is an int subclass: True would otherwise silently mean 1.0
        for cls in _COVERAGE_TYPES:
            for bad in ("0.5", True, False, [0.5], b"1"):
                with self.assertRaises(TypeError):
                    cls(fraction=bad, scope="s")

    def test_unknown_is_none_and_is_not_zero_or_one(self):
        for cls in _COVERAGE_TYPES:
            unknown = cls(fraction=None, scope="s")
            self.assertIsNone(unknown.fraction)
            self.assertNotEqual(unknown, cls(fraction=0.0, scope="s"))
            self.assertNotEqual(unknown, cls(fraction=1.0, scope="s"))

    def test_fraction_has_no_default_so_unknown_must_be_stated(self):
        for cls in _COVERAGE_TYPES:
            with self.assertRaises(TypeError):
                cls(scope="s")

    def test_scope_is_required_and_non_blank(self):
        for cls in _COVERAGE_TYPES:
            for bad in ("", "  ", "\n", None, 5):
                with self.assertRaises(ValueError):
                    cls(fraction=0.5, scope=bad)
            with self.assertRaises(TypeError):
                cls(fraction=0.5)

    def test_unknown_coverage_still_requires_a_scope(self):
        for cls in _COVERAGE_TYPES:
            with self.assertRaises(ValueError):
                cls(fraction=None, scope="")

    def test_is_immutable(self):
        for cls in _COVERAGE_TYPES:
            cov = cls(fraction=0.5, scope="s")
            with self.assertRaises(FrozenInstanceError):
                cov.fraction = 1.0
            with self.assertRaises(FrozenInstanceError):
                cov.scope = "other"

    def test_unknown_survives_serialization_without_becoming_a_number(self):
        for cls in _COVERAGE_TYPES:
            for fraction in (None, 0.0, 0.4, 1.0):
                original = cls(fraction=fraction, scope="s")
                data = json.loads(json.dumps({"fraction": original.fraction, "scope": original.scope}))
                restored = cls(fraction=data["fraction"], scope=data["scope"])
                self.assertEqual(restored, original)
                self.assertEqual((restored.fraction is None), (fraction is None))


class TestCoverageIndependence(unittest.TestCase):
    def test_five_distinct_types_with_no_shared_coverage_base(self):
        self.assertEqual(len(set(_COVERAGE_TYPES)), 5)
        for cls in _COVERAGE_TYPES:
            self.assertEqual(cls.__mro__, (cls, object))

    def test_equal_field_values_in_different_types_are_not_equal_or_interchangeable(self):
        for a in _COVERAGE_TYPES:
            for b in _COVERAGE_TYPES:
                if a is not b:
                    self.assertNotEqual(a(fraction=0.4, scope="s"), b(fraction=0.4, scope="s"))
                    self.assertFalse(isinstance(a(fraction=0.4, scope="s"), b))

    def test_task_complete_but_verification_partial_is_representable(self):
        task = TaskCoverage(fraction=1.0, scope="all 12 requirements implemented")
        verification = VerificationCoverage(fraction=0.4, scope="5 of 12 requirements verified")
        self.assertEqual(task.fraction, 1.0)
        self.assertEqual(verification.fraction, 0.4)

    def test_every_combination_of_known_and_unknown_values_is_representable(self):
        values = (None, 0.0, 0.4, 1.0)
        for combo in product(values, repeat=5):
            built = [cls(fraction=value, scope="s") for cls, value in zip(_COVERAGE_TYPES, combo)]
            self.assertEqual([c.fraction for c in built], list(combo))

    def test_verification_assurance_coverage_is_left_unchanged_and_unlinked(self):
        hints = get_type_hints(VerificationAssurance)
        self.assertIs(hints["coverage"], float)
        self.assertFalse(any("Coverage" in str(t) for t in hints.values()))
        self.assertEqual(dataclass_replace(_c3_result().assurance, coverage=0.4).coverage, 0.4)


_ABS_SURFACE = "fs:/data/out"


def _abs_auth(surface=_ABS_SURFACE, authorized=True):
    return InspectionAuthorization(surface=surface, authorized=authorized, authorized_by="governance")


def _abs(state=ObservationAbsenceState.OBSERVED_ABSENT, **over):
    kwargs = dict(state=state, surface=_ABS_SURFACE, inspected=True,
                  coverage_sufficient=True, inspection_authorization=_abs_auth())
    kwargs.update(over)
    return ObservationAbsence(**kwargs)


class TestObservationAbsenceState(unittest.TestCase):
    def test_closed_four_state_vocabulary(self):
        self.assertEqual({m.name for m in ObservationAbsenceState}, {"NOT_OBSERVED", "OBSERVED_ABSENT", "OBSERVATION_INCOMPLETE", "OBSERVATION_COVERAGE_UNKNOWN"})
        with self.assertRaises(ValueError):
            ObservationAbsenceState("absent")

    def test_values_are_disjoint_from_neighbouring_vocabularies(self):
        mine = {m.value for m in ObservationAbsenceState}
        for other in (VerificationVerdict, AssumptionStatus, EvidenceStatus, ReferenceQuality,
                      RubricLockState, ProvenanceCompleteness, ConstructValidityStatus):
            self.assertFalse((mine & {m.value for m in other}))

    def test_each_state_survives_serialization_distinctly(self):
        for state in ObservationAbsenceState:
            wire = json.dumps({"state": state.value})
            self.assertIs(ObservationAbsenceState(json.loads(wire)["state"]), state)


class TestObservationAbsence(unittest.TestCase):
    def test_observed_absent_is_constructible_with_all_three_prerequisites(self):
        absent = _abs()
        self.assertEqual(absent.state, ObservationAbsenceState.OBSERVED_ABSENT)
        self.assertIs(absent.inspected, True)
        self.assertIs(absent.inspection_authorization.authorized, True)
        self.assertIs(absent.coverage_sufficient, True)

    def test_observed_absent_requires_every_prerequisite(self):
        # all 2**3 truth assignments: only the all-true one may be constructed
        for inspected, authorized, sufficient in product((True, False), repeat=3):
            facts = dict(inspected=inspected, inspection_authorization=_abs_auth(authorized=authorized), coverage_sufficient=sufficient)
            if inspected and authorized and sufficient:
                self.assertEqual(_abs(**facts).state, ObservationAbsenceState.OBSERVED_ABSENT)
            else:
                with self.assertRaises(ValueError):
                    _abs(**facts)

    def test_observed_absent_without_any_authorization_record_is_rejected(self):
        with self.assertRaises(ValueError):
            _abs(inspection_authorization=None)

    def test_authorization_for_a_different_surface_does_not_count(self):
        with self.assertRaises(ValueError):
            _abs(inspection_authorization=_abs_auth(surface="fs:/data/OTHER"))

    def test_prerequisites_must_be_real_booleans_not_truthy_values(self):
        for bad in (1, "yes", "true", [True]):
            with self.assertRaises(TypeError):
                _abs(inspected=bad)
            with self.assertRaises(TypeError):
                _abs(coverage_sufficient=bad)
        with self.assertRaises(ValueError):
            _abs(inspection_authorization=InspectionAuthorization(surface=_ABS_SURFACE, authorized=1))

    def test_every_other_state_is_constructible_without_the_prerequisites(self):
        # The OBSERVED_ABSENT gate must not leak into the other three states.
        others = [s for s in ObservationAbsenceState if s != ObservationAbsenceState.OBSERVED_ABSENT]
        self.assertEqual(len(others), 3)
        for state in others:
            for inspected, authorized, sufficient in product((True, False), repeat=3):
                record = _abs(state, inspected=inspected, inspection_authorization=_abs_auth(authorized=authorized), coverage_sufficient=sufficient)
                self.assertEqual(record.state, state)
            bare = _abs(state, inspected=False, inspection_authorization=None, coverage_sufficient=False)
            self.assertEqual(bare.state, state)

    def test_observed_absent_is_the_only_gated_state(self):
        gated = []
        for state in ObservationAbsenceState:
            try:
                _abs(state, inspected=False, inspection_authorization=None, coverage_sufficient=False)
            except ValueError:
                gated.append(state)
        self.assertEqual(gated, [ObservationAbsenceState.OBSERVED_ABSENT])

    def test_absence_is_never_the_default_or_reached_by_omission(self):
        with self.assertRaises(TypeError):
            ObservationAbsence(surface=_ABS_SURFACE, inspected=False, coverage_sufficient=False)
        with self.assertRaises(TypeError):
            ObservationAbsence(state=ObservationAbsenceState.NOT_OBSERVED, surface=_ABS_SURFACE)
        with self.assertRaises(TypeError):
            ObservationAbsence(state=ObservationAbsenceState.OBSERVED_ABSENT, surface=_ABS_SURFACE, inspected=True)

    def test_state_must_be_an_observation_absence_state(self):
        for bad in ("observed_absent", EvidenceStatus.UNAVAILABLE, VerificationVerdict.VERIFIED, None):
            with self.assertRaises(TypeError):
                _abs(bad)

    def test_authorization_must_be_the_existing_inspection_authorization_contract(self):
        self.assertIn("InspectionAuthorization", str(get_type_hints(ObservationAbsence)["inspection_authorization"]))
        with self.assertRaises(TypeError):
            _abs(ObservationAbsenceState.NOT_OBSERVED, inspection_authorization={"surface": _ABS_SURFACE, "authorized": True})

    def test_blank_surface_rejected(self):
        for bad in ("", "  ", None, 5):
            with self.assertRaises(ValueError):
                _abs(ObservationAbsenceState.NOT_OBSERVED, surface=bad)

    def test_is_immutable(self):
        record = _abs()
        with self.assertRaises(FrozenInstanceError):
            record.state = ObservationAbsenceState.NOT_OBSERVED
        with self.assertRaises(FrozenInstanceError):
            record.coverage_sufficient = False

    def test_a_weaker_record_cannot_be_promoted_to_observed_absent_by_copying(self):
        for weak_state in (ObservationAbsenceState.NOT_OBSERVED, ObservationAbsenceState.OBSERVATION_INCOMPLETE,
                           ObservationAbsenceState.OBSERVATION_COVERAGE_UNKNOWN):
            weak = _abs(weak_state, inspected=True, coverage_sufficient=False)
            with self.assertRaises(ValueError):
                dataclass_replace(weak, state=ObservationAbsenceState.OBSERVED_ABSENT)

    def test_a_strong_record_can_be_restated_as_a_weaker_state(self):
        strong = _abs()
        weaker = dataclass_replace(strong, state=ObservationAbsenceState.OBSERVATION_INCOMPLETE)
        self.assertEqual(weaker.state, ObservationAbsenceState.OBSERVATION_INCOMPLETE)
        self.assertEqual(strong.state, ObservationAbsenceState.OBSERVED_ABSENT)

    def test_sufficiency_is_a_declared_boolean_not_a_threshold_or_a_coverage_value(self):
        self.assertEqual({f.name for f in dataclass_fields(ObservationAbsence)}, {"state", "surface", "inspected", "coverage_sufficient", "inspection_authorization"})
        with self.assertRaises(TypeError):
            _abs(coverage_sufficient=0.95)


# ---------------------------------------------------------------------------
# Batch 3C-A -- CriterionResult (criterion_result.py).  Process / outcome
# results and failure_control are deliberately NOT part of 3C-A (blocked
# pending architecture reconciliation).
# ---------------------------------------------------------------------------

_CR_FP = "fp-abc123"
_CR_ALL_FAILURES = tuple(VerificationExecutionFailure)
_CR_UNEVALUATED = (CriterionAttemptState.NOT_ATTEMPTED, CriterionAttemptState.BLOCKED)


def _cr(state=CriterionAttemptState.ATTEMPTED, verdict=VerificationVerdict.VERIFIED, **over):
    kwargs = dict(criterion_id="c1", rubric_fingerprint=_CR_FP, attempt_state=state, verdict=verdict)
    kwargs.update(over)
    return CriterionResult(**kwargs)


def _cr_other_str_enum_values(owner):
    found = {}
    for info in pkgutil.iter_modules(_cv_pkg.__path__):
        module = importlib.import_module("core.verification." + info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls is owner or cls.__module__ != module.__name__:
                continue
            if issubclass(cls, Enum) and issubclass(cls, str):
                for member in cls:
                    found.setdefault(member.value, []).append(cls.__name__ + "." + member.name)
    return found


class TestCriterionAttemptState(unittest.TestCase):
    def test_has_exactly_three_states_and_no_skipped(self):
        self.assertEqual({m.name for m in CriterionAttemptState}, {"NOT_ATTEMPTED", "BLOCKED", "ATTEMPTED"})
        self.assertFalse(hasattr(CriterionAttemptState, "SKIPPED"))

    def test_string_values_are_namespaced(self):
        for member in CriterionAttemptState:
            self.assertTrue(member.value.startswith("criterion_"))

    def test_values_collide_with_no_other_string_enum_in_the_package(self):
        others = _cr_other_str_enum_values(CriterionAttemptState)
        # The scan must actually see the neighbouring enums, or this proves nothing.
        self.assertIn("blocked", others)
        self.assertIn("not_run", others)
        self.assertIn("verified", others)
        for member in CriterionAttemptState:
            self.assertNotIn(member.value, others)

    def test_no_member_equals_a_method_execution_state_or_a_verdict(self):
        self.assertNotEqual(CriterionAttemptState.BLOCKED, MethodExecutionState.BLOCKED)
        self.assertNotEqual(CriterionAttemptState.NOT_ATTEMPTED, MethodExecutionState.NOT_RUN)
        self.assertNotEqual(CriterionAttemptState.ATTEMPTED, MethodExecutionState.EXECUTED)
        for member in CriterionAttemptState:
            for verdict in VerificationVerdict:
                self.assertNotEqual(member, verdict)

    def test_members_round_trip_by_value(self):
        for member in CriterionAttemptState:
            self.assertIs(CriterionAttemptState(json.loads(json.dumps(member.value))), member)


class TestCriterionResult(unittest.TestCase):
    def test_records_its_fields_and_defaults_optional_ones_to_nothing(self):
        record = _cr()
        self.assertEqual(record.criterion_id, "c1")
        self.assertEqual(record.rubric_fingerprint, _CR_FP)
        self.assertIs(record.attempt_state, CriterionAttemptState.ATTEMPTED)
        self.assertIs(record.verdict, VerificationVerdict.VERIFIED)
        self.assertIsNone(record.execution_failure)
        self.assertEqual(record.finding_ids, ())

    def test_is_immutable(self):
        record = _cr()
        with self.assertRaises(FrozenInstanceError):
            record.verdict = VerificationVerdict.CONTRADICTED
        with self.assertRaises(FrozenInstanceError):
            record.attempt_state = CriterionAttemptState.BLOCKED

    def test_blank_criterion_id_rejected(self):
        for bad in ("", "   ", None, 7):
            with self.assertRaises(ValueError):
                _cr(criterion_id=bad)

    def test_blank_rubric_fingerprint_rejected(self):
        for bad in ("", "   ", None, 7):
            with self.assertRaises(ValueError):
                _cr(rubric_fingerprint=bad)

    def test_attempt_state_must_be_a_criterion_attempt_state(self):
        # Not a verdict, not a method execution state, not a bare string.
        for bad in (VerificationVerdict.VERIFIED, MethodExecutionState.NOT_RUN, MethodExecutionState.EXECUTED,
                    ConstructValidityStatus.SUPPORTED, "criterion_attempted", None, 1):
            with self.assertRaises(TypeError):
                _cr(state=bad, verdict=None)

    def test_verdict_must_be_a_verification_verdict_or_none_in_every_state(self):
        for state in CriterionAttemptState:
            for bad in (FindingDisposition.SUPPORTS, MethodDisposition.CONCLUSIVE, ConstructValidityStatus.SUPPORTED,
                        "verified", 1.0, True):
                with self.assertRaises(TypeError):
                    _cr(state=state, verdict=bad)

    def test_an_attempted_criterion_accepts_every_verdict(self):
        for verdict in VerificationVerdict:
            self.assertIs(_cr(verdict=verdict).verdict, verdict)

    def test_an_attempted_criterion_without_a_verdict_is_rejected(self):
        with self.assertRaises(ValueError):
            _cr(verdict=None)

    def test_an_attempt_that_cannot_be_established_uses_a_fail_closed_verdict(self):
        for verdict in (VerificationVerdict.INSUFFICIENT_EVIDENCE, VerificationVerdict.UNVERIFIABLE):
            self.assertIs(_cr(verdict=verdict).attempt_state, CriterionAttemptState.ATTEMPTED)

    def test_unevaluated_states_accept_none_and_reject_every_verdict(self):
        for state in _CR_UNEVALUATED:
            self.assertIsNone(_cr(state=state, verdict=None).verdict)
            for verdict in VerificationVerdict:
                with self.assertRaises(ValueError):
                    _cr(state=state, verdict=verdict)

    def test_a_verdict_must_be_stated_never_reached_by_omission(self):
        for state in CriterionAttemptState:
            with self.assertRaises(TypeError):
                CriterionResult(criterion_id="c1", rubric_fingerprint=_CR_FP, attempt_state=state)

    def test_an_unevaluated_record_cannot_be_promoted_to_attempted_without_a_verdict(self):
        for state in _CR_UNEVALUATED:
            with self.assertRaises(ValueError):
                dataclass_replace(_cr(state=state, verdict=None), attempt_state=CriterionAttemptState.ATTEMPTED)

    def test_an_attempted_verdict_cannot_be_carried_into_an_unevaluated_state_by_copying(self):
        done = _cr(verdict=VerificationVerdict.VERIFIED)
        for state in _CR_UNEVALUATED:
            with self.assertRaises(ValueError):
                dataclass_replace(done, attempt_state=state)

    def test_a_blocked_criterion_can_be_restated_as_a_new_attempted_record(self):
        blocked = _cr(state=CriterionAttemptState.BLOCKED, verdict=None)
        done = dataclass_replace(blocked, attempt_state=CriterionAttemptState.ATTEMPTED, verdict=VerificationVerdict.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(blocked.verdict)
        self.assertIs(blocked.attempt_state, CriterionAttemptState.BLOCKED)
        self.assertIs(done.verdict, VerificationVerdict.INSUFFICIENT_EVIDENCE)

    def test_an_execution_failure_is_accepted_on_an_attempted_unverifiable_result(self):
        for failure in _CR_ALL_FAILURES:
            record = _cr(verdict=VerificationVerdict.UNVERIFIABLE, execution_failure=failure)
            self.assertIs(record.execution_failure, failure)

    def test_a_verifier_crash_can_never_become_a_positive_or_any_other_verdict(self):
        for failure in _CR_ALL_FAILURES:
            for verdict in VerificationVerdict:
                if verdict is VerificationVerdict.UNVERIFIABLE:
                    continue
                with self.assertRaises(ValueError):
                    _cr(verdict=verdict, execution_failure=failure)

    def test_an_execution_failure_cannot_sit_on_an_unevaluated_criterion(self):
        for state in _CR_UNEVALUATED:
            for failure in _CR_ALL_FAILURES:
                with self.assertRaises(ValueError):
                    _cr(state=state, verdict=None, execution_failure=failure)

    def test_unverifiable_without_an_execution_failure_is_valid(self):
        self.assertIsNone(_cr(verdict=VerificationVerdict.UNVERIFIABLE).execution_failure)

    def test_execution_failure_must_be_a_verification_execution_failure(self):
        for bad in ("timeout", MethodExecutionState.EXECUTION_FAILED, 1, True):
            with self.assertRaises(TypeError):
                _cr(verdict=VerificationVerdict.UNVERIFIABLE, execution_failure=bad)

    def test_finding_ids_are_optional_in_every_state_and_for_every_verdict(self):
        for verdict in VerificationVerdict:
            self.assertEqual(_cr(verdict=verdict).finding_ids, ())
            self.assertEqual(_cr(verdict=verdict, finding_ids=("f1", "f2")).finding_ids, ("f1", "f2"))
        for state in _CR_UNEVALUATED:
            self.assertEqual(_cr(state=state, verdict=None).finding_ids, ())
            self.assertEqual(_cr(state=state, verdict=None, finding_ids=("f1",)).finding_ids, ("f1",))

    def test_finding_ids_must_be_a_tuple_of_non_blank_strings(self):
        for bad in (["f1"], {"f1"}, "f1", None):
            with self.assertRaises(TypeError):
                _cr(finding_ids=bad)
        for bad in ((1,), (None,), ("f1", 2)):
            with self.assertRaises(TypeError):
                _cr(finding_ids=bad)
        for bad in (("",), ("f1", "   ")):
            with self.assertRaises(ValueError):
                _cr(finding_ids=bad)


class TestCriterionResultBoundaries(unittest.TestCase):
    def test_has_exactly_the_approved_fields(self):
        self.assertEqual({f.name for f in dataclass_fields(CriterionResult)}, {"criterion_id", "rubric_fingerprint", "attempt_state", "verdict", "execution_failure", "finding_ids"})

    def test_has_no_score_confidence_assurance_coverage_provenance_or_identity_field(self):
        for extra in ("score", "confidence", "uncertainty", "assurance", "coverage", "stability", "truth_status",
                      "decision", "aggregate", "weight", "produced_by", "derived_from", "receipt_id",
                      "supersedes_receipt_id", "execution_id", "attempt_id", "verification_id", "failure_control"):
            with self.assertRaises(TypeError):
                _cr(**{extra: 1})

    def test_field_types_reference_none_of_the_other_layers(self):
        hints = get_type_hints(CriterionResult)
        self.assertEqual(len(hints), 6)
        rendered = " ".join(str(t) for t in hints.values())
        for banned in ("Coverage", "VerificationAssurance", "VerificationReceipt", "VerificationResult", "Rubric",
                       "ConstructValidity", "Critique"):
            self.assertNotIn(banned, rendered)

    def test_module_depends_on_nothing_in_the_package_but_identity_and_verdict(self):
        tree = ast.parse(inspect.getsource(_cr_module))
        relative = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 1}
        absolute = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 0 and (n.module or "").startswith("core")]
        plain = [n for n in ast.walk(tree) if isinstance(n, ast.Import)]
        self.assertEqual(relative, {"identity", "verdict"})
        self.assertEqual(absolute, [])
        self.assertEqual(plain, [])

    def test_exposes_no_behaviour_that_could_aggregate_or_compute_a_verdict(self):
        public = [n for n in dir(CriterionResult) if not n.startswith("_") and callable(getattr(CriterionResult, n))]
        properties = [n for n, v in vars(CriterionResult).items() if isinstance(v, property)]
        self.assertEqual(public, [])
        self.assertEqual(properties, [])

    def test_each_verdict_is_stored_exactly_as_given_whatever_else_is_stored(self):
        records = [_cr(verdict=v, criterion_id="c" + str(i)) for i, v in enumerate(VerificationVerdict)]
        for record, verdict in zip(records, VerificationVerdict):
            self.assertIs(record.verdict, verdict)

    def test_a_task_level_verdict_and_criterion_verdicts_are_independent_axes(self):
        for task_verdict in VerificationVerdict:
            task_result = _c3_result(verdict=task_verdict, confidence=0.5)
            for criterion_verdict in VerificationVerdict:
                criterion = _cr(verdict=criterion_verdict)
                self.assertIs(task_result.verdict, task_verdict)
                self.assertIs(criterion.verdict, criterion_verdict)

    def test_the_existing_result_and_receipt_types_are_unchanged_and_carry_no_criterion_result(self):
        self.assertEqual({f.name for f in dataclass_fields(VerificationResult)}, {"verification_id", "task_id", "execution_id", "attempt_id", "verdict", "assurance", "confidence", "execution_failure"})
        for contract in (VerificationResult, VerificationAssurance, VerificationReceipt):
            self.assertFalse(any("criterion" in f.name.lower() for f in dataclass_fields(contract)))

    def test_results_compose_into_collections_without_collapsing_or_owning_them(self):
        verified = _cr(criterion_id="c1")
        blocked = _cr(criterion_id="c2", state=CriterionAttemptState.BLOCKED, verdict=None)
        crashed = _cr(criterion_id="c3", verdict=VerificationVerdict.UNVERIFIABLE, execution_failure=VerificationExecutionFailure.VERIFIER_CRASH)
        bag = frozenset({verified, blocked, crashed, _cr(criterion_id="c1")})
        by_id = {r.criterion_id: r for r in bag}
        self.assertEqual(len(bag), 3)
        self.assertIs(by_id["c1"].verdict, VerificationVerdict.VERIFIED)
        self.assertIsNone(by_id["c2"].verdict)
        self.assertIs(by_id["c3"].verdict, VerificationVerdict.UNVERIFIABLE)
        self.assertEqual({r.attempt_state for r in bag}, {CriterionAttemptState.ATTEMPTED, CriterionAttemptState.BLOCKED})

    def test_the_same_criterion_under_different_rubric_fingerprints_is_not_the_same_result(self):
        first = _cr(rubric_fingerprint="fp-1")
        second = _cr(rubric_fingerprint="fp-2")
        self.assertNotEqual(first, second)
        self.assertEqual(first, _cr(rubric_fingerprint="fp-1"))


class TestCriterionResultAndRubricIdentity(unittest.TestCase):
    def test_a_result_is_linked_to_a_rubric_only_by_fingerprint_value(self):
        rubric = _c3_rubric()
        record = _cr(rubric_fingerprint=rubric.fingerprint)
        self.assertEqual(record.rubric_fingerprint, rubric.fingerprint)
        self.assertFalse(any(isinstance(v, Rubric) for v in vars(record).values()))

    def test_neither_type_holds_a_reference_to_the_other(self):
        rubric_hints = get_type_hints(Rubric)
        result_hints = get_type_hints(CriterionResult)
        self.assertFalse(any("CriterionResult" in str(t) for t in rubric_hints.values()))
        self.assertFalse(any("Rubric" in str(t) for t in result_hints.values()))

    def test_recording_results_leaves_a_locked_rubric_and_its_identity_unchanged(self):
        rubric = _c3_rubric()
        locked = (rubric.advance_to(RubricLockState.VALIDATED, criteria=[_c3_criterion("c1")])
                  .advance_to(RubricLockState.COMPILED).advance_to(RubricLockState.LOCKED))
        snapshot = (locked, hash(locked), locked.fingerprint, locked.lock_state, locked.criteria)
        for state in CriterionAttemptState:
            verdict = VerificationVerdict.VERIFIED if state is CriterionAttemptState.ATTEMPTED else None
            _cr(state=state, verdict=verdict, rubric_fingerprint=locked.fingerprint)
        self.assertEqual((locked, hash(locked), locked.fingerprint, locked.lock_state, locked.criteria), snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)

