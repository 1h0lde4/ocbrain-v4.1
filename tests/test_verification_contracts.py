"""
Contract tests for Phase C Verification System types.

These test the CONTRACTS -- validation rules and structural
invariants -- not verification behavior, per the Phase C scope
boundary (no strategy execution, no LLM calls, no runtime workers).
"""
from dataclasses import FrozenInstanceError, fields as dataclass_fields
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
    ProvenanceCompleteness, EvidenceReference, EvidenceObservation,
    TransformationType, EvidenceTransformation, EvidenceBundle,
    MinimumSufficientEvidence, EvidenceBindingError,
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

    def test_requirements_id_auto_generated_and_unique(self):
        r1, r2 = self._requirements(), self._requirements()
        assert r1.requirements_id and r2.requirements_id
        assert r1.requirements_id != r2.requirements_id

    def test_explicit_empty_requirements_id_rejected(self):
        with pytest.raises(ValueError):
            self._requirements(requirements_id="")

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


# --- Phase 2: Obligation / Rubric / Criterion / InspectionPlan -------------


class TestVerificationObligation:
    def test_valid_construction(self):
        ob = VerificationObligation(
            obligation_id=new_id(),
            derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="the output must be a valid JSON document",
            source_reference="user message #3",
        )
        assert ob.rubric_id is None

    def test_empty_obligation_id_rejected(self):
        with pytest.raises(ValueError):
            VerificationObligation(
                obligation_id="", derivation_source=DerivationSource.CONSTRAINT,
                description="x", source_reference="y",
            )

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            VerificationObligation(
                obligation_id=new_id(), derivation_source=DerivationSource.CONSTRAINT,
                description="", source_reference="y",
            )

    def test_empty_source_reference_rejected(self):
        with pytest.raises(ValueError):
            VerificationObligation(
                obligation_id=new_id(), derivation_source=DerivationSource.CONSTRAINT,
                description="x", source_reference="",
            )

    def test_explicit_user_requirement_carries_authority(self):
        ob = VerificationObligation(
            obligation_id=new_id(), derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="x", source_reference="y",
        )
        assert ob.carries_explicit_user_authority

    def test_no_non_explicit_source_carries_authority(self):
        non_explicit = [s for s in DerivationSource if s is not DerivationSource.EXPLICIT_USER_REQUIREMENT]
        for source in non_explicit:
            ob = VerificationObligation(
                obligation_id=new_id(), derivation_source=source,
                description="x", source_reference="y",
            )
            assert not ob.carries_explicit_user_authority, f"{source} incorrectly carries explicit authority"


class TestCriterionDependency:
    def test_valid_construction(self):
        dep = CriterionDependency(
            criterion_id="c2", depends_on_criterion_id="c1",
            dependency_type=CriterionDependencyType.REQUIRES,
        )
        assert dep.dependency_type == CriterionDependencyType.REQUIRES

    def test_self_dependency_rejected(self):
        with pytest.raises(RubricValidationError):
            CriterionDependency(
                criterion_id="c1", depends_on_criterion_id="c1",
                dependency_type=CriterionDependencyType.REQUIRES,
            )


class TestCriterionApplicability:
    def test_unconditional_valid(self):
        ca = CriterionApplicability(applies_unconditionally=True)
        assert ca.condition_description is None

    def test_conditional_with_description_valid(self):
        ca = CriterionApplicability(applies_unconditionally=False, condition_description="only when a database migration ran")
        assert ca.condition_description

    def test_conditional_without_description_rejected(self):
        with pytest.raises(ValueError):
            CriterionApplicability(applies_unconditionally=False)


class TestCriterionEvidenceRequirement:
    def test_valid_construction(self):
        req = CriterionEvidenceRequirement(minimum_evidence_items=2, required_directness=EvidenceDirectness.DIRECT)
        assert req.minimum_evidence_items == 2

    def test_negative_minimum_rejected(self):
        with pytest.raises(ValueError):
            CriterionEvidenceRequirement(minimum_evidence_items=-1)


class TestCriterion:
    def test_valid_construction(self):
        c = Criterion(
            criterion_id="c1", rubric_id="r1", description="output is valid JSON",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        assert c.description

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            Criterion(
                criterion_id="c1", rubric_id="r1", description="",
                applicability=CriterionApplicability(applies_unconditionally=True),
                evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
            )


class TestRubric:
    def test_valid_construction(self):
        r = Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="abc123",
            created_from="obligation o1", created_by="phase-c-session",
            derived_from="user requirement", source_requirements=("req1",),
            context_basis="task target snapshot t1", criteria=("c1", "c2"),
        )
        assert r.lock_state == RubricLockState.DRAFT

    def test_empty_version_rejected(self):
        with pytest.raises(ValueError):
            Rubric(
                rubric_id="r1", version="", fingerprint="abc123",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=("c1",),
            )

    def test_empty_fingerprint_rejected(self):
        with pytest.raises(ValueError):
            Rubric(
                rubric_id="r1", version="1.0.0", fingerprint="",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=("c1",),
            )

    def test_empty_criteria_rejected(self):
        with pytest.raises(ValueError):
            Rubric(
                rubric_id="r1", version="1.0.0", fingerprint="abc",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=(),
            )

    def test_duplicate_criterion_id_rejected(self):
        with pytest.raises(RubricValidationError):
            Rubric(
                rubric_id="r1", version="1.0.0", fingerprint="abc",
                created_from="x", created_by="y", derived_from="z",
                source_requirements=(), context_basis="w", criteria=("c1", "c1"),
            )


class TestRubricLockStateProgression:
    def _draft_rubric(self):
        return Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="abc",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
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
        assert r.lock_state == RubricLockState.VALIDATED

    def test_validated_to_compiled_allowed(self):
        r = self._draft_rubric().advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria()).advance_to(RubricLockState.COMPILED)
        assert r.lock_state == RubricLockState.COMPILED

    def test_compiled_to_locked_allowed(self):
        r = (self._draft_rubric()
             .advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria())
             .advance_to(RubricLockState.COMPILED)
             .advance_to(RubricLockState.LOCKED))
        assert r.lock_state == RubricLockState.LOCKED

    def test_draft_to_compiled_rejected(self):
        with pytest.raises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.COMPILED)

    def test_draft_to_locked_rejected(self):
        with pytest.raises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.LOCKED)

    def test_locked_is_terminal(self):
        locked = (self._draft_rubric()
                  .advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria())
                  .advance_to(RubricLockState.COMPILED)
                  .advance_to(RubricLockState.LOCKED))
        with pytest.raises(RubricValidationError):
            locked.advance_to(RubricLockState.DRAFT)

    def test_advance_to_does_not_mutate_original(self):
        draft = self._draft_rubric()
        validated = draft.advance_to(RubricLockState.VALIDATED, criteria=self._matching_criteria())
        assert draft.lock_state == RubricLockState.DRAFT
        assert validated.lock_state == RubricLockState.VALIDATED
        assert draft is not validated

    def test_validated_without_criteria_rejected(self):
        # The regression test for the Phase 1 F2 finding: VALIDATED must not
        # be reachable without actually validating something.
        with pytest.raises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.VALIDATED)

    def test_validated_criteria_mismatch_rejected(self):
        # A caller cannot certify VALIDATED against a criterion set that
        # doesn't match what this Rubric actually declares.
        wrong_criteria = [
            Criterion(
                criterion_id="not-c1", rubric_id="r1", description="wrong criterion",
                applicability=CriterionApplicability(applies_unconditionally=True),
                evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
            )
        ]
        with pytest.raises(RubricValidationError):
            self._draft_rubric().advance_to(RubricLockState.VALIDATED, criteria=wrong_criteria)

    def test_validated_runs_real_dependency_validation(self):
        # Proves the wiring is real, not just an argument being accepted:
        # a criterion set with a genuine cycle must still fail here, not
        # only when validate_dependency_graph() is called directly. Uses a
        # two-node cycle (c1<->c2), not a self-loop -- CriterionDependency's
        # own __post_init__ already rejects self-loops at construction, so
        # only a multi-node cycle actually exercises the graph-level check.
        # Declares both ids on the Rubric itself so the new id-match check
        # above passes and the cycle detector is what actually fires.
        two_criterion_rubric = Rubric(
            rubric_id="r2", version="1.0.0", fingerprint="abc",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1", "c2"),
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
        with pytest.raises(CriterionDependencyCycleError):
            two_criterion_rubric.advance_to(RubricLockState.VALIDATED, criteria=two_criteria, dependencies=cyclic_deps)


class TestValidateDependencyGraph:
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
        with pytest.raises(RubricValidationError):
            validate_dependency_graph(self._criteria(["c1"]), deps)

    def test_phantom_depends_on_rejected(self):
        deps = [CriterionDependency(criterion_id="c1", depends_on_criterion_id="ghost", dependency_type=CriterionDependencyType.REQUIRES)]
        with pytest.raises(RubricValidationError):
            validate_dependency_graph(self._criteria(["c1"]), deps)

    def test_two_node_cycle_detected(self):
        deps = [
            CriterionDependency(criterion_id="c1", depends_on_criterion_id="c2", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="c2", depends_on_criterion_id="c1", dependency_type=CriterionDependencyType.REQUIRES),
        ]
        with pytest.raises(CriterionDependencyCycleError):
            validate_dependency_graph(self._criteria(["c1", "c2"]), deps)

    def test_three_node_cycle_detected(self):
        # A > B > C > A -- mission's own pairwise-cycle example, applied here to criterion dependencies
        deps = [
            CriterionDependency(criterion_id="a", depends_on_criterion_id="b", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="b", depends_on_criterion_id="c", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="c", depends_on_criterion_id="a", dependency_type=CriterionDependencyType.REQUIRES),
        ]
        with pytest.raises(CriterionDependencyCycleError):
            validate_dependency_graph(self._criteria(["a", "b", "c"]), deps)


class TestInspectionStep:
    def test_valid_construction(self):
        step = InspectionStep(step_id="s1", plan_id="p1", method_reference="filesystem_exists_check", description="check artifact exists on disk")
        assert step.method_reference == "filesystem_exists_check"

    def test_empty_method_reference_rejected(self):
        with pytest.raises(ValueError):
            InspectionStep(step_id="s1", plan_id="p1", method_reference="", description="x")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            InspectionStep(step_id="s1", plan_id="p1", method_reference="x", description="")


class TestInspectionPlan:
    def test_valid_construction(self):
        plan = InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=("s1", "s2"))
        assert len(plan.steps) == 2

    def test_empty_steps_rejected(self):
        with pytest.raises(ValueError):
            InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=())


class TestObservation:
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
        assert obs.form == ObservationForm.BINARY_PRESENCE

    def test_empty_content_summary_rejected(self):
        with pytest.raises(ValueError):
            self._obs(content_summary="")

    def test_empty_locator_rejected(self):
        with pytest.raises(ValueError):
            self._obs(locator="")


class TestInterpretation:
    def test_valid_construction(self):
        interp = Interpretation(observation_id="obs1", meaning="the file exists", interpreted_by="deterministic_rule")
        assert interp.meaning == "the file exists"

    def test_empty_meaning_rejected(self):
        with pytest.raises(ValueError):
            Interpretation(observation_id="obs1", meaning="", interpreted_by="deterministic_rule")

    def test_empty_interpreted_by_rejected(self):
        with pytest.raises(ValueError):
            Interpretation(observation_id="obs1", meaning="x", interpreted_by="")


class TestClaim:
    def test_direct_assertion_valid(self):
        c = Claim(claim_id="c1", content="the API returns 200 on success", origin=ClaimOrigin.DIRECT_ASSERTION)
        assert c.source_observation_id is None

    def test_interpreted_observation_valid(self):
        c = Claim(claim_id="c1", content="the file exists", origin=ClaimOrigin.INTERPRETED_OBSERVATION, source_observation_id="obs1")
        assert c.source_observation_id == "obs1"

    def test_derived_valid(self):
        c = Claim(claim_id="c1", content="therefore the pipeline is idle", origin=ClaimOrigin.DERIVED)
        assert c.origin == ClaimOrigin.DERIVED

    def test_empty_content_rejected(self):
        with pytest.raises(ValueError):
            Claim(claim_id="c1", content="", origin=ClaimOrigin.DIRECT_ASSERTION)

    def test_interpreted_observation_without_source_rejected(self):
        with pytest.raises(ValueError):
            Claim(claim_id="c1", content="x", origin=ClaimOrigin.INTERPRETED_OBSERVATION)

    def test_direct_assertion_with_source_rejected(self):
        with pytest.raises(ValueError):
            Claim(claim_id="c1", content="x", origin=ClaimOrigin.DIRECT_ASSERTION, source_observation_id="obs1")

    def test_derived_with_source_rejected(self):
        with pytest.raises(ValueError):
            Claim(claim_id="c1", content="x", origin=ClaimOrigin.DERIVED, source_observation_id="obs1")


class TestAssumption:
    def test_valid_construction(self):
        a = Assumption(assumption_id="a1", description="the database replica is current", relied_upon_for="freshness of the queried target state")
        assert a.assumption_id == "a1"

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            Assumption(assumption_id="a1", description="", relied_upon_for="x")

    def test_empty_relied_upon_for_rejected(self):
        with pytest.raises(ValueError):
            Assumption(assumption_id="a1", description="x", relied_upon_for="")


class TestReference:
    def test_valid_construction(self):
        r = Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE, content_summary="expected HTTP 200", source="API spec v2")
        assert r.kind == ReferenceKind.EXPECTED_VALUE

    def test_empty_content_summary_rejected(self):
        with pytest.raises(ValueError):
            Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE, content_summary="", source="x")

    def test_empty_source_rejected(self):
        with pytest.raises(ValueError):
            Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE, content_summary="x", source="")


class TestGroundTruth:
    def test_valid_construction(self):
        gt = GroundTruth(ground_truth_id="gt1", reference_id="r1", established_by="human:moncif", established_via="human_review")
        assert gt.established_via == "human_review"

    def test_empty_established_by_rejected(self):
        with pytest.raises(ValueError):
            GroundTruth(ground_truth_id="gt1", reference_id="r1", established_by="", established_via="human_review")

    def test_empty_established_via_rejected(self):
        with pytest.raises(ValueError):
            GroundTruth(ground_truth_id="gt1", reference_id="r1", established_by="human:moncif", established_via="")


class TestOracle:
    def test_valid_construction(self):
        o = Oracle(oracle_id="o1", description="reference implementation diff", is_executable=True, is_reproducible=True, is_validated=False)
        assert o.is_authoritative is False

    def test_authoritative_without_validated_rejected(self):
        with pytest.raises(ValueError):
            Oracle(oracle_id="o1", description="x", is_executable=True, is_reproducible=True, is_validated=False, is_authoritative=True)

    def test_authoritative_with_validated_allowed(self):
        o = Oracle(oracle_id="o1", description="x", is_executable=True, is_reproducible=True, is_validated=True, is_authoritative=True)
        assert o.is_authoritative is True

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            Oracle(oracle_id="o1", description="", is_executable=True, is_reproducible=True, is_validated=True)


class TestVerificationCapability:
    def test_valid_construction(self):
        cap = VerificationCapability(
            capability_id="cap1", name="filesystem_observation",
            inspection_class=InspectionClass.READ_ONLY_INSPECTION,
            typical_evidence_directness=EvidenceDirectness.DIRECT,
        )
        assert cap.underlying_capability_types == ()

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            VerificationCapability(capability_id="cap1", name="", inspection_class=InspectionClass.READ_ONLY_INSPECTION, typical_evidence_directness=EvidenceDirectness.DIRECT)

    def test_with_underlying_capability_types(self):
        cap = VerificationCapability(
            capability_id="cap1", name="filesystem_observation",
            inspection_class=InspectionClass.READ_ONLY_INSPECTION,
            typical_evidence_directness=EvidenceDirectness.DIRECT,
            underlying_capability_types=("FILE_ACCESS",),
        )
        assert cap.underlying_capability_types == ("FILE_ACCESS",)


class TestVerificationMethod:
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
        assert m.is_deterministic is True
        assert m.required_capabilities == ()

    def test_empty_method_type_rejected(self):
        with pytest.raises(ValueError):
            self._method(method_type="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            self._method(description="")

    def test_empty_version_rejected(self):
        with pytest.raises(ValueError):
            self._method(version="")

    def test_external_access_without_capabilities_rejected(self):
        with pytest.raises(ValueError):
            self._method(external_access_needed=True, required_capabilities=())

    def test_external_access_with_capabilities_allowed(self):
        m = self._method(external_access_needed=True, required_capabilities=("cap1",))
        assert m.required_capabilities == ("cap1",)


class TestVerificationMethodRequest:
    def _target(self):
        fp = VerificationTargetFingerprint(content_hash="abc123", version="1")
        return VerificationTargetSnapshot(target_id="t1", fingerprint=fp, captured_at=datetime.now(timezone.utc))

    def test_valid_construction(self):
        req = VerificationMethodRequest(method_id="m1", target=self._target(), criterion_id="c1")
        assert req.payload == {}

    def test_empty_method_id_rejected(self):
        with pytest.raises(ValueError):
            VerificationMethodRequest(method_id="", target=self._target(), criterion_id="c1")


class TestVerificationMethodResult:
    def test_executed_requires_disposition(self):
        with pytest.raises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=None)

    def test_executed_conclusive_requires_observations(self):
        with pytest.raises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=MethodDisposition.CONCLUSIVE, observations=())

    def test_executed_conclusive_with_observations_valid(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=MethodDisposition.CONCLUSIVE, observations=("obs1",))
        assert r.disposition == MethodDisposition.CONCLUSIVE

    def test_executed_insufficient_without_observations_valid(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.EXECUTED, disposition=MethodDisposition.INSUFFICIENT, observations=())
        assert r.observations == ()

    def test_not_run_with_disposition_rejected(self):
        with pytest.raises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.NOT_RUN, disposition=MethodDisposition.CONCLUSIVE)

    def test_not_run_with_observations_rejected(self):
        with pytest.raises(ValueError):
            VerificationMethodResult(execution_state=MethodExecutionState.NOT_RUN, observations=("obs1",))

    def test_execution_failed_is_clean(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.EXECUTION_FAILED)
        assert r.disposition is None
        assert r.observations == ()

    def test_unavailable_is_clean(self):
        r = VerificationMethodResult(execution_state=MethodExecutionState.UNAVAILABLE)
        assert r.execution_state == MethodExecutionState.UNAVAILABLE


class TestBaseVerifierAdapter:
    def test_initial_state_available(self):
        a = BaseVerifierAdapter()
        assert a.is_available() is True
        assert a.health_score == 100

    def test_mark_failure_triggers_cooldown(self):
        a = BaseVerifierAdapter()
        a.mark_failure()
        assert a.is_available() is False
        assert a.health_score == 80

    def test_mark_success_resets_failures_and_raises_health(self):
        a = BaseVerifierAdapter()
        a.mark_failure()
        a.mark_success()
        assert a.consecutive_failures == 0
        assert a.health_score == 85

    def test_repeated_failures_extend_cooldown(self):
        a = BaseVerifierAdapter()
        a.mark_failure()
        first_cooldown = a.cooldown_until
        a.mark_failure()
        assert a.cooldown_until > first_cooldown


class TestCompileVerificationSpecification:
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
        assert isinstance(result, CompiledVerificationSpecification)
        assert result.method_ids == ("m1",)
        assert result.criterion_ids == ("c1",)
        assert result.rubric_id == "r1"

    def test_wrong_lock_state_rejected(self):
        scenario = self._scenario()
        draft_rubric = Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
        )
        scenario["rubric"] = draft_rubric
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("lock_state" in r for r in result.reasons)

    def test_criterion_mismatch_rejected(self):
        scenario = self._scenario()
        other_criterion = Criterion(
            criterion_id="not-c1", rubric_id="r1", description="wrong",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        scenario["criteria"] = [other_criterion]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("must match exactly" in r for r in result.reasons)

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
        ).advance_to(RubricLockState.VALIDATED, criteria=[scenario["criteria"][0], c2]).advance_to(RubricLockState.COMPILED)
        cyclic_deps = [
            CriterionDependency(criterion_id="c1", depends_on_criterion_id="c2", dependency_type=CriterionDependencyType.REQUIRES),
            CriterionDependency(criterion_id="c2", depends_on_criterion_id="c1", dependency_type=CriterionDependencyType.REQUIRES),
        ]
        scenario["rubric"] = rubric_with_c2
        scenario["criteria"] = [scenario["criteria"][0], c2]
        scenario["dependencies"] = cyclic_deps
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("dependency graph invalid" in r for r in result.reasons)

    def test_obligation_wrong_rubric_rejected(self):
        scenario = self._scenario()
        scenario["obligations"] = [VerificationObligation(
            obligation_id="o1", derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="d", source_reference="r", rubric_id="different-rubric",
        )]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("not the rubric being compiled" in r for r in result.reasons)

    def test_obligation_with_no_rubric_allowed(self):
        scenario = self._scenario()
        scenario["obligations"] = [VerificationObligation(
            obligation_id="o1", derivation_source=DerivationSource.EXPLICIT_USER_REQUIREMENT,
            description="d", source_reference="r", rubric_id=None,
        )]
        result = compile_spec(**scenario)
        assert isinstance(result, CompiledVerificationSpecification)

    def test_unresolvable_method_reference_rejected(self):
        scenario = self._scenario()
        scenario["method_registry"] = {}
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("not in the method registry" in r for r in result.reasons)

    def test_missing_inspection_step_rejected(self):
        scenario = self._scenario()
        scenario["inspection_steps"] = []
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("was not supplied" in r for r in result.reasons)

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
        assert isinstance(result, CompilationFailure)
        assert any("capability" in r and "cap1" in r for r in result.reasons)

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
        assert isinstance(result, CompilationFailure)
        assert any("no authorized InspectionAuthorization" in r for r in result.reasons)

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
        assert isinstance(result, CompilationFailure)
        assert any("no authorized InspectionAuthorization" in r for r in result.reasons)

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
        assert isinstance(result, CompiledVerificationSpecification)

    def test_orphaned_criterion_rejected(self):
        scenario = self._scenario()
        scenario["inspection_plans"] = []
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("no inspection plan targeting them" in r for r in result.reasons)

    def test_plan_references_unknown_obligation_rejected(self):
        scenario = self._scenario()
        scenario["inspection_plans"] = [InspectionPlan(plan_id="p1", obligation_id="not-o1", criterion_id="c1", steps=("s1",))]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("not supplied to compile()" in r and "not-o1" in r for r in result.reasons)

    def test_plan_references_unknown_criterion_rejected(self):
        scenario = self._scenario()
        scenario["inspection_plans"] = [InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="not-c1", steps=("s1",))]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("not among the criteria being compiled" in r for r in result.reasons)

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
        assert isinstance(result, CompilationFailure)
        assert any("requires evidence directness" in r for r in result.reasons)

    def test_evidence_directness_match_allowed(self):
        scenario = self._scenario()
        strict_criterion = Criterion(
            criterion_id="c1", rubric_id="r1", description="criterion c1",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1, required_directness=EvidenceDirectness.DIRECT),
        )
        scenario["criteria"] = [strict_criterion]
        result = compile_spec(**scenario)
        assert isinstance(result, CompiledVerificationSpecification)

    def test_policy_shape_violation_rejected(self):
        scenario = self._scenario()
        scenario["policy"] = VerificationPolicy(
            policy_id="pol1",
            minimum_shape_for={"correctness": VerificationShape.PAIRWISE},
        )
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("policy requires shape" in r for r in result.reasons)

    def test_policy_forbidden_method_rejected(self):
        scenario = self._scenario()
        scenario["policy"] = VerificationPolicy(policy_id="pol1", forbidden_methods=frozenset({"m1"}))
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("forbidden methods" in r for r in result.reasons)

    def test_critical_criterion_not_in_set_rejected(self):
        scenario = self._scenario()
        scenario["critical_criterion_ids"] = frozenset({"not-a-real-criterion"})
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("not among the criteria being compiled" in r for r in result.reasons)

    def test_critical_criterion_in_set_allowed(self):
        scenario = self._scenario()
        scenario["critical_criterion_ids"] = frozenset({"c1"})
        result = compile_spec(**scenario)
        assert isinstance(result, CompiledVerificationSpecification)
        assert result.critical_criterion_ids == frozenset({"c1"})

    def test_multiple_failures_collected_together(self):
        scenario = self._scenario()
        draft_rubric = Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
        )
        scenario["rubric"] = draft_rubric
        scenario["method_registry"] = {}
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert len(result.reasons) >= 2

    def test_empty_spec_id_rejected_on_direct_construction(self):
        with pytest.raises(ValueError):
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
        with pytest.raises(ValueError):
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
        with pytest.raises(ValueError):
            CompiledVerificationSpecification(
                spec_id="spec1", compiled_at=datetime.now(timezone.utc), target_id="t1",
                target_fingerprint=VerificationTargetFingerprint(content_hash="a", version="1"),
                requirements=VerificationRequirements(target_description="x", required_dimensions=frozenset({"d"})),
                strategy=VerificationStrategy(selected_shape=VerificationShape.POINTWISE, selected_methods=frozenset({"m1"}), verifier_count=1, derived_from_requirements="req1"),
                rubric_id="r1", rubric_version="1.0.0", rubric_fingerprint="fp1",
                obligation_ids=(), criterion_ids=("c1",), critical_criterion_ids=frozenset({"not-c1"}),
                inspection_plan_ids=(), method_ids=(), assurance_scope="scope",
            )


class TestCompilationFailure:
    def test_empty_reasons_rejected(self):
        with pytest.raises(ValueError):
            CompilationFailure(reasons=())

    def test_valid_construction(self):
        f = CompilationFailure(reasons=("something went wrong",))
        assert len(f.reasons) == 1


class TestCompiledSpecificationHardening:
    """Hardening fixes for CompiledVerificationSpecification: duplicate
    ID detection, step.plan_id validation, and compile() non-purity
    acknowledgment.  (A strategy<->method consistency check added in
    c09f924 was removed: selected_methods and method_reference are not the
    same vocabulary -- see the method_id != method_type regression tests.)"""

    def _scenario(self, **overrides):
        """Reusable valid scenario — same as TestCompileVerificationSpecification."""
        criterion = Criterion(
            criterion_id="c1", rubric_id="r1", description="criterion c1",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        rubric = (Rubric(
            rubric_id="r1", version="1.0.0", fingerprint="fp1",
            created_from="x", created_by="y", derived_from="z",
            source_requirements=(), context_basis="w", criteria=("c1",),
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

    # ---- Fix 1: Duplicate ID detection --------------------------------

    def test_duplicate_criterion_ids_rejected(self):
        scenario = self._scenario()
        dup_criterion = Criterion(
            criterion_id="c1", rubric_id="r1", description="duplicate c1",
            applicability=CriterionApplicability(applies_unconditionally=True),
            evidence_requirement=CriterionEvidenceRequirement(minimum_evidence_items=1),
        )
        scenario["criteria"] = [scenario["criteria"][0], dup_criterion]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("duplicate criterion id" in r and "'c1'" in r for r in result.reasons)

    def test_duplicate_obligation_ids_rejected(self):
        scenario = self._scenario()
        dup_obligation = VerificationObligation(
            obligation_id="o1", derivation_source=DerivationSource.CONSTRAINT,
            description="duplicate obligation", source_reference="req-2", rubric_id="r1",
        )
        scenario["obligations"] = [scenario["obligations"][0], dup_obligation]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("duplicate obligation id" in r and "'o1'" in r for r in result.reasons)

    def test_duplicate_inspection_plan_ids_rejected(self):
        scenario = self._scenario()
        dup_plan = InspectionPlan(plan_id="p1", obligation_id="o1", criterion_id="c1", steps=("s1",))
        scenario["inspection_plans"] = [scenario["inspection_plans"][0], dup_plan]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("duplicate inspection_plan id" in r and "'p1'" in r for r in result.reasons)

    def test_duplicate_inspection_step_ids_rejected(self):
        scenario = self._scenario()
        dup_step = InspectionStep(step_id="s1", plan_id="p1", method_reference="m1", description="duplicate step")
        scenario["inspection_steps"] = [scenario["inspection_steps"][0], dup_step]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any("duplicate inspection_step id" in r and "'s1'" in r for r in result.reasons)

    # ---- Fix 2: InspectionStep.plan_id validation ---------------------

    def test_step_plan_id_not_in_supplied_plans_rejected(self):
        """A step that claims to belong to a plan not supplied to compile()
        must be rejected — the forward (plan→step) traversal would not
        catch this because it traverses plan.steps, not step.plan_id."""
        scenario = self._scenario()
        orphan_step = InspectionStep(
            step_id="s1", plan_id="phantom-plan",
            method_reference="m1", description="step claiming wrong plan",
        )
        scenario["inspection_steps"] = [orphan_step]
        result = compile_spec(**scenario)
        assert isinstance(result, CompilationFailure)
        assert any(
            "plan_id=" in r and "'phantom-plan'" in r
            and "not among the supplied" in r
            for r in result.reasons
        )

    def test_step_plan_id_matching_supplied_plan_accepted(self):
        """When step.plan_id matches a supplied plan, no plan_id error."""
        result = compile_spec(**self._scenario())
        assert isinstance(result, CompiledVerificationSpecification)

    # ---- Regression: method_id != method_type ---------------------------
    # c09f924 briefly compared strategy.selected_methods (method names /
    # types, per policy.py) against InspectionStep.method_reference (a
    # registry key, i.e. a method identifier).  Those are different
    # vocabularies; the fixtures used "m1" for both, which hid it.  The
    # representation is deliberately still open (compile design proposal),
    # so compile() must NOT enforce any relation between them.

    def _distinct_id_and_type_scenario(self, selected_methods):
        scenario = self._scenario()
        method = VerificationMethod(
            method_id="method-uuid-1", method_type="deterministic_file_existence",
            description="checks file existence", version="1.0.0",
            produces_evidence_directness=EvidenceDirectness.DIRECT,
            external_access_needed=False, is_deterministic=True,
            cost_latency_class=CostLatencyClass.INSTANT,
        )
        assert method.method_id != method.method_type
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
        # policy.py documents selected_methods as method names/types.
        result = compile_spec(**self._distinct_id_and_type_scenario(
            {"deterministic_file_existence"}))
        assert isinstance(result, CompiledVerificationSpecification)
        assert result.method_ids == ("method-uuid-1",)

    def test_compiles_when_selected_methods_holds_method_id(self):
        # The representation is open: neither choice is rejected here.
        result = compile_spec(**self._distinct_id_and_type_scenario(
            {"method-uuid-1"}))
        assert isinstance(result, CompiledVerificationSpecification)

    def test_compile_imposes_no_strategy_to_step_method_relation(self):
        # Unused selected method and unselected used method: still no
        # strategy<->step consistency rule at this layer.
        result = compile_spec(**self._distinct_id_and_type_scenario(
            {"deterministic_file_existence", "never_used_method"}))
        assert isinstance(result, CompiledVerificationSpecification)

    # ---- Fix 4: compile() non-purity ---------------------------------

    def test_compile_creates_different_ids_each_call(self):
        """compile() is NOT pure: each successful call creates a fresh
        UUID, so two calls with identical inputs produce different spec_ids."""
        scenario = self._scenario()
        result1 = compile_spec(**scenario)
        result2 = compile_spec(**scenario)
        assert isinstance(result1, CompiledVerificationSpecification)
        assert isinstance(result2, CompiledVerificationSpecification)
        assert result1.spec_id != result2.spec_id

    def test_compile_creates_timestamps(self):
        """compile() captures compiled_at timestamps — these are runtime
        side effects, confirming non-purity."""
        result = compile_spec(**self._scenario())
        assert isinstance(result, CompiledVerificationSpecification)
        assert result.compiled_at is not None
        # It should be a recent UTC timestamp
        from datetime import timezone
        assert result.compiled_at.tzinfo == timezone.utc


class TestVerificationDimension:
    def test_has_exactly_the_ten_mission_sec16_values(self):
        expected = {
            "process", "outcome", "correctness", "completeness", "groundedness",
            "compliance", "safety", "state", "transition", "invariant",
        }
        assert {d.value for d in VerificationDimension} == expected

    def test_is_a_closed_enum_not_open_ended(self):
        # Unlike VerificationMethodType (plain string constants, open by
        # design), dimensions are a fixed taxonomy -- an unknown value
        # must be rejected, not silently accepted.
        with pytest.raises(ValueError):
            VerificationDimension("not-a-real-dimension")


class TestVerificationFinding:
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
        assert f.disposition == FindingDisposition.SUPPORTS

    def test_empty_observation_ids_rejected(self):
        with pytest.raises(ValueError):
            self._finding(observation_ids=())

    def test_inconclusive_finding_still_requires_an_observation(self):
        # INCONCLUSIVE means "observed something, doesn't resolve either
        # way" -- not "observed nothing", which is a method-execution
        # state (NOT_RUN/BLOCKED/...) upstream of this type entirely.
        with pytest.raises(ValueError):
            self._finding(disposition=FindingDisposition.INCONCLUSIVE, observation_ids=())

    def test_method_and_dimension_are_independent_classifications(self):
        # v2-frozen.md Sec11: "a single dimension can be checked by
        # multiple methods, and a single method can serve multiple
        # dimensions" -- two independent axes, not a hierarchy.
        same_method_different_dimensions = [
            self._finding(method_id="m1", dimension=d)
            for d in (VerificationDimension.CORRECTNESS, VerificationDimension.SAFETY)
        ]
        same_dimension_different_methods = [
            self._finding(method_id=m, dimension=VerificationDimension.CORRECTNESS)
            for m in ("m1", "m2")
        ]
        assert len({f.dimension for f in same_method_different_dimensions}) == 2
        assert len({f.method_id for f in same_dimension_different_methods}) == 2

    def test_finding_disposition_distinct_from_method_disposition(self):
        # The exact conflation VerificationMethod Revision 1 got wrong
        # and Revision 2 fixed -- kept as two separate enums on purpose.
        assert {d.value for d in FindingDisposition} == {"supports", "refutes", "inconclusive"}
        assert {d.value for d in MethodDisposition} == {"conclusive", "inconclusive", "insufficient"}
        assert FindingDisposition is not MethodDisposition


class TestContradiction:
    def test_valid_construction(self):
        c = Contradiction(contradiction_id="ct1", first_claim_id="cl1", second_claim_id="cl2", description="cl1 says X, cl2 says not-X")
        assert c.first_claim_id != c.second_claim_id

    def test_same_claim_on_both_sides_rejected(self):
        with pytest.raises(ValueError):
            Contradiction(contradiction_id="ct1", first_claim_id="cl1", second_claim_id="cl1", description="self-contradiction")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            Contradiction(contradiction_id="ct1", first_claim_id="cl1", second_claim_id="cl2", description="")


class TestCounterArgument:
    def test_valid_without_observations(self):
        ca = CounterArgument(counter_argument_id="ca1", target_claim_id="cl1", alternative_explanation="the test passed because of a cached result")
        assert ca.supporting_observation_ids == ()

    def test_valid_with_observations(self):
        ca = CounterArgument(
            counter_argument_id="ca1", target_claim_id="cl1",
            alternative_explanation="the test passed because of a cached result",
            supporting_observation_ids=("obs1", "obs2"),
        )
        assert len(ca.supporting_observation_ids) == 2

    def test_empty_alternative_explanation_rejected(self):
        with pytest.raises(ValueError):
            CounterArgument(counter_argument_id="ca1", target_claim_id="cl1", alternative_explanation="")


class TestCritiqueFindingType:
    def test_has_exactly_the_nine_v1_sec18_values(self):
        expected = {
            "unsupported_claim", "missing_evidence", "hidden_assumption", "logic_gap",
            "contradiction", "scope_violation", "false_completion", "wrong_attribution",
            "possible_counterexample",
        }
        assert {t.value for t in CritiqueFindingType} == expected


class TestCritique:
    # The six finding types with no dedicated structured reference.
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
            assert c.contradiction_id is None
            assert c.counter_argument_id is None
            assert c.hidden_assumption_id is None

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            self._critique(description="")

    def test_contradiction_type_requires_contradiction_id(self):
        with pytest.raises(ValueError):
            self._critique(finding_type=CritiqueFindingType.CONTRADICTION)

    def test_contradiction_type_with_id_valid(self):
        c = self._critique(finding_type=CritiqueFindingType.CONTRADICTION, contradiction_id="ct1")
        assert c.contradiction_id == "ct1"

    def test_counterexample_type_requires_counter_argument_id(self):
        with pytest.raises(ValueError):
            self._critique(finding_type=CritiqueFindingType.POSSIBLE_COUNTEREXAMPLE)

    def test_counterexample_type_with_id_valid(self):
        c = self._critique(finding_type=CritiqueFindingType.POSSIBLE_COUNTEREXAMPLE, counter_argument_id="ca1")
        assert c.counter_argument_id == "ca1"

    def test_hidden_assumption_type_requires_hidden_assumption_id(self):
        with pytest.raises(ValueError):
            self._critique(finding_type=CritiqueFindingType.HIDDEN_ASSUMPTION)

    def test_hidden_assumption_type_with_id_valid(self):
        c = self._critique(finding_type=CritiqueFindingType.HIDDEN_ASSUMPTION, hidden_assumption_id="a1")
        assert c.hidden_assumption_id == "a1"

    def test_contradiction_id_rejected_for_wrong_type(self):
        with pytest.raises(ValueError):
            self._critique(finding_type=CritiqueFindingType.LOGIC_GAP, contradiction_id="ct1")

    def test_counter_argument_id_rejected_for_wrong_type(self):
        with pytest.raises(ValueError):
            self._critique(finding_type=CritiqueFindingType.LOGIC_GAP, counter_argument_id="ca1")

    def test_hidden_assumption_id_rejected_for_wrong_type(self):
        with pytest.raises(ValueError):
            self._critique(finding_type=CritiqueFindingType.LOGIC_GAP, hidden_assumption_id="a1")

    def test_references_cannot_cross_between_types(self):
        # A HIDDEN_ASSUMPTION critique may not also carry a contradiction_id.
        with pytest.raises(ValueError):
            self._critique(
                finding_type=CritiqueFindingType.HIDDEN_ASSUMPTION,
                hidden_assumption_id="a1", contradiction_id="ct1",
            )


# ---------------------------------------------------------------------------
# Batch 1 — Epistemic Spine: ClaimDependency, AssumptionSource,
#            AssumptionStatus, ReferenceQuality
# ---------------------------------------------------------------------------


class TestClaimDependency:
    """ClaimDependency: an immutable dependency edge between two claims.
    Structural parallel to CriterionDependency (rubric.py)."""

    def test_valid_construction_relies_on(self):
        dep = ClaimDependency(
            claim_id="c2", depends_on_claim_id="c1",
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        assert dep.claim_id == "c2"
        assert dep.depends_on_claim_id == "c1"
        assert dep.dependency_type == ClaimDependencyType.RELIES_ON

    def test_valid_construction_presupposes(self):
        dep = ClaimDependency(
            claim_id="c2", depends_on_claim_id="c1",
            dependency_type=ClaimDependencyType.PRESUPPOSES,
        )
        assert dep.dependency_type == ClaimDependencyType.PRESUPPOSES

    def test_self_dependency_rejected(self):
        with pytest.raises(ValueError, match="cannot depend on itself"):
            ClaimDependency(
                claim_id="c1", depends_on_claim_id="c1",
                dependency_type=ClaimDependencyType.RELIES_ON,
            )

    def test_dependent_and_depended_upon_are_distinct_fields(self):
        dep = ClaimDependency(
            claim_id="alpha", depends_on_claim_id="beta",
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        assert dep.claim_id != dep.depends_on_claim_id

    def test_immutability(self):
        dep = ClaimDependency(
            claim_id="c2", depends_on_claim_id="c1",
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        with pytest.raises(Exception):
            dep.claim_id = "tampered"

    def test_dependency_does_not_encode_support_or_refutation(self):
        """ClaimDependencyType values must not overlap with evidence
        support/refutation concepts."""
        dep_values = {t.value for t in ClaimDependencyType}
        # These are evidence-layer concepts that dependency must not encode
        for forbidden in ("supports", "refutes", "contradicts", "sufficient", "insufficient"):
            assert forbidden not in dep_values

    def test_dependency_does_not_encode_authority(self):
        """ClaimDependencyType values must not imply authority."""
        dep_values = {t.value for t in ClaimDependencyType}
        for forbidden in ("authoritative", "trusted", "verified", "proven"):
            assert forbidden not in dep_values

    def test_no_accidental_equivalence_with_claim_origin_derived(self):
        """ClaimOrigin.DERIVED means 'how a claim came to exist';
        ClaimDependencyType means 'what this claim relies on'.
        They must have no shared values."""
        origin_values = {o.value for o in ClaimOrigin}
        dep_values = {t.value for t in ClaimDependencyType}
        assert origin_values.isdisjoint(dep_values), (
            f"ClaimOrigin and ClaimDependencyType share values: "
            f"{origin_values & dep_values}"
        )

    def test_all_dependency_types_exist(self):
        assert {ClaimDependencyType.RELIES_ON, ClaimDependencyType.PRESUPPOSES} == set(ClaimDependencyType)

    def test_dependency_is_directional(self):
        """A depends_on B is not the same as B depends_on A."""
        dep_ab = ClaimDependency(claim_id="a", depends_on_claim_id="b",
                                 dependency_type=ClaimDependencyType.RELIES_ON)
        dep_ba = ClaimDependency(claim_id="b", depends_on_claim_id="a",
                                 dependency_type=ClaimDependencyType.RELIES_ON)
        assert dep_ab != dep_ba

    def test_derived_claim_can_have_dependency(self):
        """A DERIVED claim may also have a dependency edge --
        ClaimOrigin and ClaimDependency are orthogonal."""
        claim = Claim(claim_id="c2", content="therefore idle",
                      origin=ClaimOrigin.DERIVED)
        dep = ClaimDependency(claim_id=claim.claim_id,
                              depends_on_claim_id="c1",
                              dependency_type=ClaimDependencyType.RELIES_ON)
        assert dep.claim_id == claim.claim_id


class TestAssumptionSource:
    """AssumptionSource: structured provenance for assumptions,
    separate from authority."""

    def test_valid_construction(self):
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.HUMAN,
            source_identifier="human:moncif",
        )
        assert src.source_kind == AssumptionSourceKind.HUMAN
        assert src.source_identifier == "human:moncif"

    def test_empty_source_identifier_rejected(self):
        with pytest.raises(ValueError, match="non-empty source_identifier"):
            AssumptionSource(
                source_kind=AssumptionSourceKind.HUMAN,
                source_identifier="",
            )

    def test_whitespace_source_identifier_rejected(self):
        with pytest.raises(ValueError):
            AssumptionSource(
                source_kind=AssumptionSourceKind.MODEL,
                source_identifier="   ",
            )

    def test_immutability(self):
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.SYSTEM,
            source_identifier="runtime_defaults",
        )
        with pytest.raises(Exception):
            src.source_kind = AssumptionSourceKind.HUMAN

    def test_all_source_kinds_representable(self):
        expected = {"human", "model", "system", "policy", "documentation"}
        assert {k.value for k in AssumptionSourceKind} == expected

    def test_source_does_not_imply_authority(self):
        """AssumptionSource has no authority field -- provenance and
        authority are structurally separate."""
        src = AssumptionSource(
            source_kind=AssumptionSourceKind.HUMAN,
            source_identifier="human:moncif",
        )
        assert not hasattr(src, "is_authoritative")
        assert not hasattr(src, "authority")

    def test_source_is_not_observation_authority(self):
        """AssumptionSourceKind must not share values with
        ObservationAuthority -- they answer different questions."""
        from core.verification.epistemic import ObservationAuthority
        source_values = {k.value for k in AssumptionSourceKind}
        authority_values = {a.value for a in ObservationAuthority}
        # They CAN share some string values (e.g. "human", "model") but
        # are different enum types -- verify type distinctness
        assert AssumptionSourceKind is not ObservationAuthority

    def test_queryable_through_assumption(self):
        """An Assumption with a source must allow querying the source
        kind and identifier without reverse-engineering from prose."""
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
        assert a.source is not None
        assert a.source.source_kind == AssumptionSourceKind.DOCUMENTATION
        assert a.source.source_identifier == "api-spec-v2"


class TestAssumptionStatus:
    """AssumptionStatus: semantic status axis for assumptions,
    distinct from VerificationVerdict."""

    def test_all_four_states_exist(self):
        expected = {"unexamined", "challenged", "confirmed", "rejected"}
        assert {s.value for s in AssumptionStatus} == expected

    def test_default_is_unexamined(self):
        a = Assumption(
            assumption_id="a1",
            description="db replica is current",
            relied_upon_for="freshness",
        )
        assert a.status == AssumptionStatus.UNEXAMINED

    def test_unexamined_is_not_rejected(self):
        assert AssumptionStatus.UNEXAMINED != AssumptionStatus.REJECTED
        assert AssumptionStatus.UNEXAMINED.value != AssumptionStatus.REJECTED.value

    def test_unexamined_is_not_confirmed(self):
        assert AssumptionStatus.UNEXAMINED != AssumptionStatus.CONFIRMED

    def test_challenged_is_not_verified_failure(self):
        """CHALLENGED is under scrutiny, not found false."""
        assert AssumptionStatus.CHALLENGED != AssumptionStatus.REJECTED

    def test_not_interchangeable_with_verification_verdict(self):
        """AssumptionStatus and VerificationVerdict are different types."""
        from core.verification.verdict import VerificationVerdict
        assert AssumptionStatus is not VerificationVerdict
        # No value-level overlap for the critical confusion pairs
        assert AssumptionStatus.CONFIRMED.value != VerificationVerdict.VERIFIED.value
        assert AssumptionStatus.REJECTED.value != VerificationVerdict.CONTRADICTED.value

    def test_survives_round_trip(self):
        """UNEXAMINED survives serialization without becoming
        rejected/confirmed/false."""
        status = AssumptionStatus.UNEXAMINED
        serialized = status.value
        deserialized = AssumptionStatus(serialized)
        assert deserialized is AssumptionStatus.UNEXAMINED
        assert deserialized is not AssumptionStatus.REJECTED
        assert deserialized is not AssumptionStatus.CONFIRMED

    def test_immutability_of_assumption_with_status(self):
        a = Assumption(
            assumption_id="a1",
            description="db replica is current",
            relied_upon_for="freshness",
            status=AssumptionStatus.CHALLENGED,
        )
        with pytest.raises(Exception):
            a.status = AssumptionStatus.CONFIRMED

    def test_explicit_status_at_construction(self):
        a = Assumption(
            assumption_id="a1",
            description="API is idempotent",
            relied_upon_for="retry safety",
            status=AssumptionStatus.CONFIRMED,
        )
        assert a.status == AssumptionStatus.CONFIRMED

    def test_changing_status_requires_new_instance(self):
        """Historical semantics: changing status must not mutate an
        existing Assumption -- a new instance is required, compatible
        with the immutable receipt/supersession model."""
        a1 = Assumption(
            assumption_id="a1",
            description="db replica is current",
            relied_upon_for="freshness",
            status=AssumptionStatus.UNEXAMINED,
        )
        # The only way to "change" status is to construct a new Assumption
        from dataclasses import replace
        a2 = replace(a1, status=AssumptionStatus.CHALLENGED)
        assert a1.status == AssumptionStatus.UNEXAMINED  # original untouched
        assert a2.status == AssumptionStatus.CHALLENGED
        assert a1 is not a2


class TestReferenceQuality:
    """ReferenceQuality: quality characterization distinct from
    correctness, authority, freshness, and GroundTruth."""

    def test_all_four_quality_levels_exist(self):
        expected = {"unassessed", "low", "moderate", "high"}
        assert {q.value for q in ReferenceQuality} == expected

    def test_default_is_unassessed(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.EXPECTED_VALUE,
            content_summary="expected HTTP 200",
            source="API spec v2",
        )
        assert r.quality == ReferenceQuality.UNASSESSED

    def test_explicit_quality_at_construction(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.SPECIFICATION,
            content_summary="OpenAPI schema v3",
            source="official documentation",
            quality=ReferenceQuality.HIGH,
        )
        assert r.quality == ReferenceQuality.HIGH

    def test_quality_is_not_correctness(self):
        """HIGH quality does not mean the reference is correct/true."""
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.DOCUMENTATION,
            content_summary="outdated but well-formatted docs",
            source="wiki v1",
            quality=ReferenceQuality.HIGH,
        )
        # The reference is still just a Reference, regardless of quality
        assert isinstance(r, Reference)
        assert not isinstance(r, GroundTruth)

    def test_quality_is_not_authority(self):
        """ReferenceQuality has no authority field."""
        assert not hasattr(ReferenceQuality, "is_authoritative")
        # A high-quality reference carries no authority marker
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.HUMAN_JUDGMENT,
            content_summary="expert opinion",
            source="domain expert",
            quality=ReferenceQuality.HIGH,
        )
        assert not hasattr(r, "is_authoritative")

    def test_high_quality_does_not_create_ground_truth(self):
        """Attack D: quality=HIGH must not promote a Reference to
        GroundTruth. GroundTruth requires explicit elevation."""
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.SPECIFICATION,
            content_summary="formal spec",
            source="standards body",
            quality=ReferenceQuality.HIGH,
        )
        assert isinstance(r, Reference)
        assert not isinstance(r, GroundTruth)
        # GroundTruth still requires explicit established_by/established_via
        gt = GroundTruth(
            ground_truth_id="gt1",
            reference_id=r.reference_id,
            established_by="human:moncif",
            established_via="human_review",
        )
        assert isinstance(gt, GroundTruth)

    def test_existing_reference_construction_still_works(self):
        """Backward compatibility: Reference without quality still works."""
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.EXPECTED_VALUE,
            content_summary="expected 200",
            source="spec",
        )
        assert r.quality == ReferenceQuality.UNASSESSED

    def test_quality_does_not_encode_freshness(self):
        """Quality and freshness are distinct -- ReferenceQuality has no
        temporal/validity fields."""
        for q in ReferenceQuality:
            assert "fresh" not in q.value
            assert "stale" not in q.value
            assert "expired" not in q.value

    def test_immutability(self):
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.PRIOR_RESULT,
            content_summary="prior run output",
            source="execution log",
            quality=ReferenceQuality.MODERATE,
        )
        with pytest.raises(Exception):
            r.quality = ReferenceQuality.HIGH

    def test_high_quality_reference_remains_reference(self):
        """A representative high-quality Reference is still a Reference,
        not silently promoted."""
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.SPECIFICATION,
            content_summary="fully validated spec",
            source="standards body official publication",
            quality=ReferenceQuality.HIGH,
        )
        assert type(r) is Reference


class TestEpistemicSpineIntegration:
    """Integration tests proving the Batch 1 contracts can answer their
    intended questions without inference from free-form strings."""

    def test_what_claim_depends_on_what(self):
        """Can answer: 'What claim depends on what other claim?'"""
        claim_a = Claim(claim_id="ca", content="pipeline is idle",
                        origin=ClaimOrigin.DERIVED)
        claim_b = Claim(claim_id="cb", content="no jobs in queue",
                        origin=ClaimOrigin.DIRECT_ASSERTION)
        dep = ClaimDependency(
            claim_id=claim_a.claim_id,
            depends_on_claim_id=claim_b.claim_id,
            dependency_type=ClaimDependencyType.RELIES_ON,
        )
        assert dep.claim_id == "ca"
        assert dep.depends_on_claim_id == "cb"
        assert dep.dependency_type == ClaimDependencyType.RELIES_ON

    def test_where_assumption_came_from(self):
        """Can answer: 'Where did this assumption come from?'"""
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
        assert a.source.source_kind == AssumptionSourceKind.POLICY
        assert a.source.source_identifier == "policy:safety-critical-v1"

    def test_assumption_semantic_status(self):
        """Can answer: 'What is the assumption's current semantic status?'"""
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
        assert a.status == AssumptionStatus.CHALLENGED

    def test_reference_quality_characterization(self):
        """Can answer: 'What quality characterization applies to this reference?'"""
        r = Reference(
            reference_id="r1",
            kind=ReferenceKind.DOCUMENTATION,
            content_summary="API reference v3.2",
            source="official documentation portal",
            quality=ReferenceQuality.HIGH,
        )
        assert r.quality == ReferenceQuality.HIGH

    def test_existing_contracts_remain_valid(self):
        """Existing Claim/Assumption/Reference/GroundTruth/Oracle
        construction still works unchanged."""
        # Claim (existing test pattern)
        c = Claim(claim_id="c1", content="the API returns 200",
                  origin=ClaimOrigin.DIRECT_ASSERTION)
        assert c.source_observation_id is None

        # Assumption (existing test pattern -- no source/status args)
        a = Assumption(assumption_id="a1",
                       description="the database replica is current",
                       relied_upon_for="freshness of the queried target state")
        assert a.assumption_id == "a1"
        assert a.source is None
        assert a.status == AssumptionStatus.UNEXAMINED

        # Reference (existing test pattern -- no quality arg)
        r = Reference(reference_id="r1", kind=ReferenceKind.EXPECTED_VALUE,
                      content_summary="expected HTTP 200", source="API spec v2")
        assert r.kind == ReferenceKind.EXPECTED_VALUE
        assert r.quality == ReferenceQuality.UNASSESSED

        # GroundTruth (unchanged)
        gt = GroundTruth(ground_truth_id="gt1", reference_id="r1",
                         established_by="human:moncif",
                         established_via="human_review")
        assert gt.established_via == "human_review"

        # Oracle (unchanged)
        o = Oracle(oracle_id="o1", description="reference implementation diff",
                   is_executable=True, is_reproducible=True, is_validated=False)
        assert o.is_authoritative is False


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


class TestEvidenceReference:
    def test_preserves_exact_source_locator_and_binding(self):
        ref = _ev_reference(criterion_id="crit1")
        assert ref.evidence_id == "e1"
        assert ref.source == _ev_source()
        assert ref.locator == "L10-L12"
        assert ref.claim_id == "c1"
        assert ref.criterion_id == "crit1"

    def test_claim_only_and_criterion_only_bindings_are_valid(self):
        assert _ev_reference(claim_id="c1", criterion_id=None).criterion_id is None
        assert _ev_reference(claim_id=None, criterion_id="crit1").claim_id is None

    def test_is_immutable(self):
        ref = _ev_reference()
        with pytest.raises(FrozenInstanceError):
            ref.locator = "elsewhere"

    def test_blank_locator_rejected(self):
        for bad in ("", "   "):
            with pytest.raises(ValueError):
                _ev_reference(locator=bad)

    def test_blank_source_identity_rejected(self):
        for bad_source in (EvidenceSource("", "s1", "runtime"),
                           EvidenceSource("tool_result", " ", "runtime"),
                           EvidenceSource("tool_result", "s1", "")):
            with pytest.raises(ValueError):
                _ev_reference(source=bad_source)

    def test_unbound_reference_rejected(self):
        # Claim -> Evidence chain needs a claim and/or criterion at one end.
        with pytest.raises(ValueError):
            _ev_reference(claim_id=None, criterion_id=None)

    def test_has_no_payload_channel(self):
        # Content/directness/status stay on EvidenceItem (single source of truth).
        assert {f.name for f in dataclass_fields(EvidenceReference)} == {"evidence_id", "source", "locator", "provenance", "claim_id", "criterion_id"}
        with pytest.raises(TypeError):
            _ev_reference(content_summary="x" * 100000)

    def test_all_four_provenance_states_preserved(self):
        assert len(list(ProvenanceCompleteness)) == 4
        for state in ProvenanceCompleteness:
            assert _ev_reference(provenance=state).provenance == state

    def test_verify_against_accepts_the_matching_item(self):
        assert _ev_reference().verify_against(_ev_item()) is None

    def test_verify_against_rejects_drifted_id(self):
        with pytest.raises(EvidenceBindingError):
            _ev_reference().verify_against(_ev_item(eid="e2"))

    def test_verify_against_rejects_drifted_source(self):
        other = EvidenceSource("tool_result", "OTHER", "runtime")
        with pytest.raises(EvidenceBindingError):
            _ev_reference().verify_against(_ev_item(source=other))

    def test_verify_against_rejects_drifted_locator(self):
        with pytest.raises(EvidenceBindingError):
            _ev_reference().verify_against(_ev_item(locator="L99"))

    def test_verify_against_says_nothing_about_support(self):
        item = _ev_item(status=EvidenceStatus.CONTRADICTORY, supports=())
        assert _ev_reference(claim_id="c1").verify_against(item) is None

    def test_verify_against_is_status_blind(self):
        # A link check is not a sufficiency judgment: every one of the six
        # evidence states binds identically.
        for state in EvidenceStatus:
            assert _ev_reference().verify_against(_ev_item(status=state)) is None

    def test_claim_bound_reference_cannot_bind_a_claim_to_its_own_restatement(self):
        restatement = _ev_item("e1", supports=("c1",), restatement=True)
        with pytest.raises(CircularEvidenceError):
            _ev_reference(claim_id="c1").verify_against(restatement)

    def test_restatement_of_a_different_claim_is_not_circular_for_this_reference(self):
        other = _ev_item("e1", supports=("c1",), restatement=True)
        assert _ev_reference(claim_id="c2").verify_against(other) is None


class TestEvidenceObservation:
    def _link(self, **over):
        kwargs = dict(evidence_id="e1", observation_id="o1",
                      provenance=ProvenanceCompleteness.COMPLETE)
        kwargs.update(over)
        return EvidenceObservation(**kwargs)

    def test_binds_evidence_to_observation_by_id(self):
        link = self._link(provenance=ProvenanceCompleteness.PARTIAL)
        assert link.evidence_id == "e1"
        assert link.observation_id == "o1"
        assert link.provenance == ProvenanceCompleteness.PARTIAL

    def test_is_immutable(self):
        link = self._link()
        with pytest.raises(FrozenInstanceError):
            link.observation_id = "o2"

    def test_blank_ids_rejected(self):
        for bad in ("", "  "):
            with pytest.raises(ValueError):
                self._link(evidence_id=bad)
            with pytest.raises(ValueError):
                self._link(observation_id=bad)

    def test_defines_no_authority_of_its_own(self):
        assert {f.name for f in dataclass_fields(EvidenceObservation)} == {"evidence_id", "observation_id", "provenance"}
        with pytest.raises(TypeError):
            self._link(authority=ObservationAuthority.RUNTIME)

    def test_verify_against_matching_observation_is_authority_independent(self):
        link = self._link()
        for authority in ObservationAuthority:
            assert link.verify_against(_ev_observation(authority=authority)) is None

    def test_verify_against_rejects_another_observation(self):
        with pytest.raises(EvidenceBindingError):
            self._link().verify_against(_ev_observation(oid="o2"))

    def test_an_interpretation_is_not_evidence_provenance(self):
        # Observation -> Interpretation -> Claim is not Observation -> Evidence.
        reading = Interpretation(observation_id="o1", meaning="file exists",
                                 interpreted_by="deterministic_rule")
        with pytest.raises(TypeError):
            self._link().verify_against(reading)

    def test_all_four_provenance_states_preserved(self):
        for state in ProvenanceCompleteness:
            assert self._link(provenance=state).provenance == state


class TestEvidenceTransformation:
    def test_lineage_is_fully_reconstructable(self):
        tx = _ev_transformation(transformation_type=TransformationType.OCR)
        assert tx.source_evidence_id == "e1"
        assert tx.transformation_type == TransformationType.OCR
        assert tx.transformation_version == "1.0.0"
        assert tx.transformation_producer == "summarizer"
        assert tx.result_evidence_id == "e2"

    def test_is_immutable(self):
        tx = _ev_transformation()
        with pytest.raises(FrozenInstanceError):
            tx.result_directness = EvidenceDirectness.DIRECT

    def test_incomplete_lineage_rejected(self):
        for bad in ("", "  "):
            with pytest.raises(ValueError):
                _ev_transformation(transformation_version=bad)
            with pytest.raises(ValueError):
                _ev_transformation(transformation_producer=bad)

    def test_source_and_result_must_be_distinct(self):
        with pytest.raises(ValueError):
            _ev_transformation(source_evidence_id="e1", result_evidence_id="e1")

    def test_non_direct_source_can_never_yield_direct(self):
        for source in (EvidenceDirectness.INDIRECT, EvidenceDirectness.DERIVED,
                       EvidenceDirectness.MODEL_INTERPRETATION):
            for ttype in TransformationType:
                with pytest.raises(ValueError):
                    _ev_transformation(source_directness=source, transformation_type=ttype,
                                       result_directness=EvidenceDirectness.DIRECT)

    def test_model_interpretation_source_is_permanent(self):
        model = EvidenceDirectness.MODEL_INTERPRETATION
        for ttype in TransformationType:
            for result in EvidenceDirectness:
                if result == model:
                    tx = _ev_transformation(source_directness=model, transformation_type=ttype,
                                            result_directness=result)
                    assert tx.result_directness == model
                else:
                    with pytest.raises(ValueError):
                        _ev_transformation(source_directness=model, transformation_type=ttype,
                                           result_directness=result)

    def test_model_interpretation_transformation_of_direct_source_stays_model(self):
        model = EvidenceDirectness.MODEL_INTERPRETATION
        for result in EvidenceDirectness:
            if result == model:
                tx = _ev_transformation(transformation_type=TransformationType.MODEL_INTERPRETATION,
                                        result_directness=result)
                assert tx.result_directness == model
            else:
                with pytest.raises(ValueError):
                    _ev_transformation(transformation_type=TransformationType.MODEL_INTERPRETATION,
                                       result_directness=result)

    def test_incomplete_provenance_never_silently_becomes_complete(self):
        for source in (ProvenanceCompleteness.PARTIAL, ProvenanceCompleteness.UNKNOWN,
                       ProvenanceCompleteness.BROKEN):
            with pytest.raises(ValueError):
                _ev_transformation(source_provenance=source,
                                   result_provenance=ProvenanceCompleteness.COMPLETE)
        kept = _ev_transformation(source_provenance=ProvenanceCompleteness.BROKEN,
                                  result_provenance=ProvenanceCompleteness.BROKEN)
        assert kept.result_provenance == ProvenanceCompleteness.BROKEN
        weakened = _ev_transformation(result_provenance=ProvenanceCompleteness.UNKNOWN)
        assert weakened.result_provenance == ProvenanceCompleteness.UNKNOWN

    def test_direct_to_direct_via_non_model_transformation_is_left_to_higher_layers(self):
        # Documented boundary, not a claim of enforcement: the frozen
        # architecture gives no categorical per-type table for what a
        # redaction/normalization "justifies", so this record accepts it.
        for ttype in TransformationType:
            if ttype == TransformationType.MODEL_INTERPRETATION:
                continue
            tx = _ev_transformation(transformation_type=ttype,
                                    result_directness=EvidenceDirectness.DIRECT)
            assert tx.result_directness == EvidenceDirectness.DIRECT

    def test_verify_against_accepts_items_matching_the_record(self):
        tx = _ev_transformation()
        source = _ev_item("e1", directness=EvidenceDirectness.DIRECT)
        result = _ev_item("e2", directness=EvidenceDirectness.DERIVED)
        assert tx.verify_against(source, result) is None

    def test_verify_against_catches_a_record_that_misstates_source_directness(self):
        # The record alone looks safe (DIRECT -> DERIVED); the real source
        # item is a model interpretation being laundered.
        tx = _ev_transformation(source_directness=EvidenceDirectness.DIRECT,
                                result_directness=EvidenceDirectness.DERIVED)
        real_source = _ev_item("e1", directness=EvidenceDirectness.MODEL_INTERPRETATION)
        result = _ev_item("e2", directness=EvidenceDirectness.DERIVED)
        with pytest.raises(EvidenceBindingError):
            tx.verify_against(real_source, result)

    def test_verify_against_catches_a_record_that_misstates_result_directness(self):
        tx = _ev_transformation(result_directness=EvidenceDirectness.DERIVED)
        source = _ev_item("e1", directness=EvidenceDirectness.DIRECT)
        real_result = _ev_item("e2", directness=EvidenceDirectness.DIRECT)
        with pytest.raises(EvidenceBindingError):
            tx.verify_against(source, real_result)

    def test_verify_against_rejects_wrong_ids(self):
        tx = _ev_transformation()
        good_source = _ev_item("e1", directness=EvidenceDirectness.DIRECT)
        good_result = _ev_item("e2", directness=EvidenceDirectness.DERIVED)
        with pytest.raises(EvidenceBindingError):
            tx.verify_against(_ev_item("eX", directness=EvidenceDirectness.DIRECT), good_result)
        with pytest.raises(EvidenceBindingError):
            tx.verify_against(good_source, _ev_item("eX", directness=EvidenceDirectness.DERIVED))

    def test_verify_against_blocks_laundering_circular_evidence_through_lineage(self):
        # restatement of c1 -> "summary" -> derived copy with the flag dropped
        tx = _ev_transformation()
        restated = _ev_item("e1", directness=EvidenceDirectness.DIRECT, supports=("c1",), restatement=True)
        laundered = _ev_item("e2", directness=EvidenceDirectness.DERIVED, supports=("c1",), restatement=False)
        with pytest.raises(CircularEvidenceError):
            tx.verify_against(restated, laundered)

    def test_restatement_flag_kept_through_lineage_is_still_caught_by_the_bundle(self):
        tx = _ev_transformation()
        restated = _ev_item("e1", directness=EvidenceDirectness.DIRECT, supports=("c1",), restatement=True)
        kept = _ev_item("e2", directness=EvidenceDirectness.DERIVED, supports=("c1",), restatement=True)
        assert tx.verify_against(restated, kept) is None
        with pytest.raises(CircularEvidenceError):
            EvidenceBundle(items=(kept,), claim_id="c1")

    def test_transformation_of_a_non_restatement_is_not_over_blocked(self):
        tx = _ev_transformation()
        plain = _ev_item("e1", directness=EvidenceDirectness.DIRECT, supports=("c1",), restatement=False)
        derived = _ev_item("e2", directness=EvidenceDirectness.DERIVED, supports=("c1",), restatement=False)
        assert tx.verify_against(plain, derived) is None
        assert EvidenceBundle(items=(derived,), claim_id="c1").claim_id == "c1"


class TestEvidenceBundle:
    def test_preserves_every_evidence_status_in_order_without_filtering(self):
        items = tuple(_ev_item("e%d" % n, status=state) for n, state in enumerate(EvidenceStatus))
        bundle = EvidenceBundle(items=items, claim_id="c1")
        assert len(bundle.items) == 6
        assert tuple(i.status for i in bundle.items) == tuple(EvidenceStatus)
        assert bundle.evidence_ids == tuple(i.evidence_id for i in items)
        for kept, original in zip(bundle.items, items):
            assert kept is original

    def test_contradictory_only_bundle_is_not_resolved(self):
        bundle = EvidenceBundle(items=(_ev_item(status=EvidenceStatus.CONTRADICTORY),), claim_id="c1")
        assert bundle.items[0].status == EvidenceStatus.CONTRADICTORY

    def test_membership_implies_no_support(self):
        unrelated = _ev_item("e1", supports=())
        elsewhere = _ev_item("e2", supports=("c9",))
        bundle = EvidenceBundle(items=(unrelated, elsewhere), claim_id="c1")
        assert "c1" not in bundle.items[0].supports_claim_ids
        assert "c1" not in bundle.items[1].supports_claim_ids

    def test_is_immutable(self):
        bundle = EvidenceBundle(items=(_ev_item(),), claim_id="c1")
        with pytest.raises(FrozenInstanceError):
            bundle.claim_id = "c2"
        with pytest.raises(AttributeError):
            bundle.items.append(_ev_item("e2"))

    def test_mutable_container_rejected(self):
        with pytest.raises(TypeError):
            EvidenceBundle(items=[_ev_item()], claim_id="c1")

    def test_empty_bundle_rejected(self):
        # Missing evidence is not representable as an empty bundle.
        with pytest.raises(ValueError):
            EvidenceBundle(items=(), claim_id="c1")

    def test_duplicate_evidence_ids_rejected(self):
        with pytest.raises(ValueError):
            EvidenceBundle(items=(_ev_item("e1"), _ev_item("e1")), claim_id="c1")

    def test_unbound_bundle_rejected(self):
        with pytest.raises(ValueError):
            EvidenceBundle(items=(_ev_item(),))

    def test_criterion_only_binding_is_valid(self):
        assert EvidenceBundle(items=(_ev_item(),), criterion_id="crit1").criterion_id == "crit1"

    def test_non_evidence_item_members_rejected(self):
        with pytest.raises(TypeError):
            EvidenceBundle(items=(_ev_reference(),), claim_id="c1")

    def test_restatement_of_bound_claim_cannot_enter_the_bundle(self):
        circular = _ev_item("e1", supports=("c1",), restatement=True)
        with pytest.raises(CircularEvidenceError):
            EvidenceBundle(items=(circular,), claim_id="c1")

    def test_restatement_of_a_different_claim_is_not_circular_for_this_claim(self):
        other = _ev_item("e1", supports=("c1",), restatement=True)
        assert EvidenceBundle(items=(other,), claim_id="c2").claim_id == "c2"


class TestMinimumSufficientEvidence:
    def _bundle(self):
        return EvidenceBundle(items=(
            _ev_item("e1", status=EvidenceStatus.SUFFICIENT),
            _ev_item("e2", status=EvidenceStatus.CONTRADICTORY),
            _ev_item("e3", status=EvidenceStatus.INSUFFICIENT),
        ), claim_id="c1", criterion_id="crit1")

    def test_declares_required_evidence_for_a_decision(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1", "e2"), claim_id="c1")
        assert mse.required_evidence_ids == ("e1", "e2")
        assert mse.claim_id == "c1"

    def test_is_immutable_and_rejects_mutable_container(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1",), claim_id="c1")
        with pytest.raises(FrozenInstanceError):
            mse.claim_id = "c2"
        with pytest.raises(TypeError):
            MinimumSufficientEvidence(required_evidence_ids=["e1"], claim_id="c1")

    def test_invalid_declarations_rejected(self):
        with pytest.raises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=(), claim_id="c1")
        with pytest.raises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=("e1", "e1"), claim_id="c1")
        with pytest.raises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=("e1", " "), claim_id="c1")
        with pytest.raises(ValueError):
            MinimumSufficientEvidence(required_evidence_ids=("e1",))

    def test_does_not_duplicate_the_criterion_evidence_floor(self):
        mse_fields = {f.name for f in dataclass_fields(MinimumSufficientEvidence)}
        assert mse_fields == {"required_evidence_ids", "claim_id", "criterion_id"}
        assert not (mse_fields & {f.name for f in dataclass_fields(CriterionEvidenceRequirement)})

    def test_verify_against_accepts_a_bundle_that_retains_everything_required(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1", "e2"), claim_id="c1")
        assert mse.verify_against(self._bundle()) is None

    def test_requirement_is_status_blind_and_not_a_sufficiency_judgment(self):
        # Reconstructing the decision needs the CONTRADICTORY and INSUFFICIENT
        # items too; "required for audit" is not EvidenceStatus.SUFFICIENT.
        mse = MinimumSufficientEvidence(required_evidence_ids=("e2", "e3"), claim_id="c1")
        assert mse.verify_against(self._bundle()) is None
        statuses = tuple(i.status for i in self._bundle().items)
        assert statuses == (EvidenceStatus.SUFFICIENT, EvidenceStatus.CONTRADICTORY, EvidenceStatus.INSUFFICIENT)

    def test_verify_against_rejects_a_bundle_missing_required_evidence(self):
        mse = MinimumSufficientEvidence(required_evidence_ids=("e1", "e404"), claim_id="c1")
        with pytest.raises(EvidenceBindingError):
            mse.verify_against(self._bundle())

    def test_verify_against_rejects_a_bundle_for_another_claim_or_criterion(self):
        with pytest.raises(EvidenceBindingError):
            MinimumSufficientEvidence(required_evidence_ids=("e1",), claim_id="c2").verify_against(self._bundle())
        with pytest.raises(EvidenceBindingError):
            MinimumSufficientEvidence(required_evidence_ids=("e1",), criterion_id="crit2").verify_against(self._bundle())


class TestEvidenceChainReconstruction:
    def test_claim_to_observation_chain_is_reconstructable_from_structured_records(self):
        # Claim C7 -> Evidence E14 -> Source S2 -> Locator L9 -> Observation O4
        item = _ev_item("e14", locator="L9")
        reference = _ev_reference(evidence_id="e14", locator="L9", claim_id="c7")
        link = EvidenceObservation(evidence_id="e14", observation_id="o4",
                                   provenance=ProvenanceCompleteness.COMPLETE)
        observation = _ev_observation("o4", ObservationAuthority.RUNTIME)
        bundle = EvidenceBundle(items=(item,), claim_id="c7")

        assert reference.verify_against(item) is None
        assert link.verify_against(observation) is None
        assert reference.claim_id == "c7"
        assert reference.evidence_id in bundle.evidence_ids
        assert reference.source == item.source
        assert reference.locator == item.locator
        assert link.evidence_id == reference.evidence_id
        assert link.observation_id == observation.observation_id
        assert observation.authority == ObservationAuthority.RUNTIME
