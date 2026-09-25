"""
CompiledVerificationSpecification (mission Sec10; v1.md Sec42; Phase 3
-- specification/inspection binding). Implements the design confirmed in
docs/architecture/verification-critic-evidence-system-compiledverificationspecification-design-proposal.md
(Revision 2, after both prerequisites it named -- VerificationRequirements
identity and criterion criticality placement -- were resolved first).
See that document for the reasoning; this module doesn't re-derive it.

compile() is a pure function, matching mission Sec10's own test: "A
specification that cannot be compiled into a satisfiable verification
plan is not a valid executable verification. It is an unresolved
specification." It either returns a complete, internally-consistent
CompiledVerificationSpecification, or a CompilationFailure naming every
reason -- never a partial/degraded spec, and never a bare False.

Reference vs. embed is resolved per input, not by one blanket rule (see
the design doc's table): Rubric/Criterion/Obligation/InspectionPlan/
VerificationMethod are referenced by id (all have one); Requirements and
Strategy are embedded (neither has a registry to resolve a reference
against yet, though Requirements now at least carries its own
requirements_id for citation -- see policy.py).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, FrozenSet, Mapping, Optional, Sequence, Tuple, Union

from .identity import (
    AssumptionId,
    CompiledVerificationSpecificationId,
    CriterionId,
    InspectionPlanId,
    ObligationId,
    RubricId,
    VerificationCapabilityId,
    VerificationMethodId,
)
from .inspection import InspectionPlan, InspectionStep
from .method import VerificationCapability, VerificationMethod
from .obligation import VerificationObligation
from .policy import (
    VerificationPolicy,
    VerificationProfileName,
    VerificationRequirements,
    VerificationStrategy,
)
from .rubric import (
    Criterion,
    CriterionDependency,
    CriterionDependencyCycleError,
    Rubric,
    RubricLockState,
    RubricValidationError,
    validate_dependency_graph,
)
from .target import VerificationTargetFingerprint, VerificationTargetSnapshot


@dataclass(frozen=True)
class CompilationFailure:
    """Compilation did not produce a valid specification. reasons names
    every check that failed, not just the first -- mission Sec9's
    requirement-gap vocabulary (missing/ambiguous/unrepresentable/
    incorrectly modeled) applies to each entry, not to this object as a
    whole."""
    reasons: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise ValueError(
                "CompilationFailure requires at least one reason -- a "
                "failure with no stated cause is not distinguishable "
                "from success"
            )


@dataclass(frozen=True)
class CompiledVerificationSpecification:
    """A satisfiable, internally-consistent verification plan, or this
    object does not exist -- see compile(), below, which is the only
    intended constructor in normal use. __post_init__ here only checks
    what's determinable from this object's own fields (id non-empty,
    critical ids actually among the compiled criteria); everything
    needing external context (registries, the rubric's own lock state,
    policy constraints) is compile()'s job, not this dataclass's."""
    spec_id: CompiledVerificationSpecificationId
    compiled_at: datetime
    target_id: str
    target_fingerprint: VerificationTargetFingerprint
    requirements: VerificationRequirements
    strategy: VerificationStrategy
    rubric_id: RubricId
    rubric_version: str
    rubric_fingerprint: str
    obligation_ids: Tuple[ObligationId, ...]
    criterion_ids: Tuple[CriterionId, ...]
    critical_criterion_ids: FrozenSet[CriterionId]
    inspection_plan_ids: Tuple[InspectionPlanId, ...]
    method_ids: Tuple[VerificationMethodId, ...]
    assurance_scope: str
    policy_id: Optional[str] = None
    profile_name: Optional[VerificationProfileName] = None
    execution_identity: Optional[str] = None  # provisional -- no
        # execution/attempt-id binding exists anywhere in
        # core/verification/ yet; Phase 13's job to wire for real
    known_assumptions: Tuple[AssumptionId, ...] = ()

    def __post_init__(self) -> None:
        if not self.spec_id or not str(self.spec_id).strip():
            raise ValueError("CompiledVerificationSpecification requires a non-empty spec_id")
        if not self.assurance_scope or not self.assurance_scope.strip():
            raise ValueError(
                "CompiledVerificationSpecification requires a non-empty "
                "assurance_scope -- mission Sec7.4: assurance is always "
                "scoped, never left to be assumed as covering the whole task"
            )
        if not self.critical_criterion_ids <= frozenset(self.criterion_ids):
            invalid = self.critical_criterion_ids - frozenset(self.criterion_ids)
            raise ValueError(
                f"critical_criterion_ids contains {sorted(invalid)!r}, "
                f"which are not among this specification's own criterion_ids"
            )


def compile(
    *,
    requirements: VerificationRequirements,
    strategy: VerificationStrategy,
    rubric: Rubric,
    criteria: Sequence[Criterion],
    dependencies: Sequence[CriterionDependency],
    obligations: Sequence[VerificationObligation],
    inspection_plans: Sequence[InspectionPlan],
    inspection_steps: Sequence[InspectionStep],
    target: VerificationTargetSnapshot,
    method_registry: Mapping[VerificationMethodId, VerificationMethod],
    capability_registry: Mapping[VerificationCapabilityId, VerificationCapability],
    assurance_scope: str,
    policy: Optional[VerificationPolicy] = None,
    profile_name: Optional[VerificationProfileName] = None,
    critical_criterion_ids: FrozenSet[CriterionId] = frozenset(),
    known_assumptions: Tuple[AssumptionId, ...] = (),
    execution_identity: Optional[str] = None,
) -> Union[CompiledVerificationSpecification, CompilationFailure]:
    """Pure function: same inputs, same output, no hidden state. Collects
    every failing check rather than stopping at the first, so a caller
    gets the complete picture in one pass rather than one error at a time."""
    reasons: list = []

    # Rubric.lock_state -- matches this session's own Phase 1 fix:
    # VALIDATED is now only reachable with real validation behind it, and
    # COMPILED is the next state up from that, so gating here on
    # COMPILED-or-LOCKED reuses that guarantee rather than re-deriving it.
    if rubric.lock_state not in (RubricLockState.COMPILED, RubricLockState.LOCKED):
        reasons.append(
            f"rubric {rubric.rubric_id!r} is in lock_state="
            f"{rubric.lock_state.value!r}; only COMPILED or LOCKED "
            f"rubrics can be compiled into a specification"
        )

    # Criterion set must match the rubric's own declaration exactly --
    # the same consistency requirement already enforced on
    # Rubric.advance_to(VALIDATED) this session, applied here for the
    # same reason: compiling against the wrong criterion set would
    # silently compile the wrong specification.
    supplied_criterion_ids = frozenset(c.criterion_id for c in criteria)
    declared_criterion_ids = frozenset(rubric.criteria)
    if supplied_criterion_ids != declared_criterion_ids:
        reasons.append(
            f"rubric {rubric.rubric_id!r} declares criteria "
            f"{sorted(declared_criterion_ids)!r} but was compiled against "
            f"{sorted(supplied_criterion_ids)!r} -- these must match exactly"
        )

    # Reuse rubric.py's own dependency-graph validator rather than
    # reimplementing cycle detection here.
    try:
        validate_dependency_graph(criteria, dependencies)
    except (RubricValidationError, CriterionDependencyCycleError) as exc:
        reasons.append(f"criterion dependency graph invalid: {exc}")

    # Every obligation being compiled must actually belong to this rubric
    # (or declare no rubric at all) -- not silently accepted if it names
    # a different one.
    for obligation in obligations:
        if obligation.rubric_id is not None and obligation.rubric_id != rubric.rubric_id:
            reasons.append(
                f"obligation {obligation.obligation_id!r} declares "
                f"rubric_id={obligation.rubric_id!r}, not the rubric "
                f"being compiled ({rubric.rubric_id!r})"
            )

    # Every inspection step's method_reference must resolve, and every
    # capability that method requires must be registered (not that its
    # adapters are currently healthy -- that's runtime's question, not
    # compile-time's; see the design doc's compile-time/runtime split).
    step_by_id = {step.step_id: step for step in inspection_steps}
    method_ids_used: set = set()
    for plan in inspection_plans:
        for step_id in plan.steps:
            step = step_by_id.get(step_id)
            if step is None:
                reasons.append(
                    f"inspection plan {plan.plan_id!r} references step "
                    f"{step_id!r}, which was not supplied to compile()"
                )
                continue
            method = method_registry.get(step.method_reference)
            if method is None:
                reasons.append(
                    f"inspection step {step.step_id!r} references method "
                    f"{step.method_reference!r}, which is not in the "
                    f"method registry"
                )
                continue
            method_ids_used.add(method.method_id)
            for capability_id in method.required_capabilities:
                if capability_id not in capability_registry:
                    reasons.append(
                        f"method {method.method_id!r} requires capability "
                        f"{capability_id!r}, which is not in the "
                        f"capability registry"
                    )

    # Policy constraints -- never relaxed by what requirements/strategy
    # asked for, only tightened (v3 Part 1 Sec3).
    if policy is not None:
        for dimension in requirements.required_dimensions:
            minimum_shape = policy.minimum_shape_for.get(dimension)
            if minimum_shape is not None and strategy.selected_shape != minimum_shape:
                reasons.append(
                    f"policy requires shape={minimum_shape.value!r} for "
                    f"dimension {dimension!r}, but strategy selected "
                    f"{strategy.selected_shape.value!r}"
                )
        forbidden_used = frozenset(strategy.selected_methods) & policy.forbidden_methods
        if forbidden_used:
            reasons.append(
                f"strategy selects forbidden methods: {sorted(forbidden_used)!r}"
            )

    # critical_criterion_ids must be a subset of what's actually being
    # compiled -- re-checked here even though CompiledVerificationSpecification's
    # own __post_init__ checks it too, so compile() reports it as a named
    # reason alongside every other failure rather than raising separately.
    if not critical_criterion_ids <= supplied_criterion_ids:
        invalid = critical_criterion_ids - supplied_criterion_ids
        reasons.append(
            f"critical_criterion_ids contains {sorted(invalid)!r}, which "
            f"are not among the criteria being compiled"
        )

    # Target-kind compatibility: deliberately not checked. target.py has
    # no target-kind taxonomy yet (confirmed by direct read during the
    # VerificationMethod design pass) -- gating on one here would check
    # against a taxonomy that doesn't exist rather than leaving the
    # boundary honest, per that same design doc's Sec9.

    if reasons:
        return CompilationFailure(reasons=tuple(reasons))

    return CompiledVerificationSpecification(
        spec_id=CompiledVerificationSpecificationId(str(uuid.uuid4())),
        compiled_at=datetime.now(timezone.utc),
        target_id=target.target_id,
        target_fingerprint=target.fingerprint,
        requirements=requirements,
        strategy=strategy,
        rubric_id=rubric.rubric_id,
        rubric_version=rubric.version,
        rubric_fingerprint=rubric.fingerprint,
        obligation_ids=tuple(o.obligation_id for o in obligations),
        criterion_ids=tuple(sorted(supplied_criterion_ids)),
        critical_criterion_ids=critical_criterion_ids,
        inspection_plan_ids=tuple(p.plan_id for p in inspection_plans),
        method_ids=tuple(sorted(method_ids_used)),
        assurance_scope=assurance_scope,
        policy_id=(policy.policy_id if policy is not None else None),
        profile_name=profile_name,
        execution_identity=execution_identity,
        known_assumptions=known_assumptions,
    )
