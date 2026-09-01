"""eval_lab/contracts/trajectory.py — normalized trajectory, branching, interventions.

Implements §19-20 (trajectory/hierarchy), §37-42 (temporal/causal/branching)
of the original architecture and §34-43 of this Slice's brief, plus the
research report's §7a.6 (counterfactual evaluation, branching -- explicitly
future-scope shape only, no execution engine per ADR-LAB-02 §4's amendment).

Per ADR-LAB-02: this is a *normalized* trajectory format, not
core.events.event_stream.StreamEvent reused directly. The trace adapter
that actually populates a Trajectory from EventStream/EventBus/KnowledgeEvent
is Slice 3, explicitly out of scope here (this Slice's §84: "Do not start
Trace Adapter... Do not normalize EventStream"). TrajectoryEvent's shape
is designed to be a plausible normalization target without importing
anything from core/events/ -- confirmed safe per the dependency audit in
the final report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from eval_lab.contracts.enums import CausalRelationType, OrderingRelation
from eval_lab.contracts.identifiers import (
    BranchId,
    CheckpointId,
    CounterfactualEvaluationId,
    ExecutionInstanceId,
    InterventionId,
    SnapshotId,
    TrajectoryEventId,
    TrajectoryId,
)
from eval_lab.contracts.serialization import ContractValidationError, nested, nested_list


class CheckpointStatus(str, Enum):
    """Correction pass: originally a raw `str` on `Checkpoint.status` with
    a manual membership check -- same gap as the other closed-vocabulary
    fields fixed in this pass."""

    PENDING = "pending"
    MET = "met"
    NOT_MET = "not_met"
    NOT_EVALUATED = "not_evaluated"


class TrajectoryEventType(str, Enum):
    """Known event categories per §34/§19. UNKNOWN is a legitimate value
    (not an error) -- see TrajectoryEvent.raw_type_name for why."""

    GOAL = "goal"
    INTERPRETATION = "interpretation"
    CONSTRAINTS = "constraints"
    PLAN = "plan"
    CAPABILITY = "capability"
    COMPILATION = "compilation"
    WORKER = "worker"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    OBSERVATION = "observation"
    STATE_TRANSITION = "state_transition"
    MEMORY_CONTEXT = "memory_context"
    VALIDATION = "validation"
    RETRY = "retry"
    FAILURE = "failure"
    RECOVERY = "recovery"
    REPLANNING = "replanning"
    MUTATION = "mutation"
    CANCELLATION = "cancellation"
    COMPLETION = "completion"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CausalReference:
    """One typed relationship to another event, per §38: caused_by,
    derived_from, related_to, supersedes, superseded_by must not collapse
    into one generic parent reference."""

    relation: CausalRelationType
    target_event_id: TrajectoryEventId

    def to_dict(self) -> dict[str, Any]:
        return {"relation": self.relation.value, "target_event_id": self.target_event_id}


@dataclass(frozen=True)
class TrajectoryEvent:
    """One normalized event. Per §35: `event_type` classifies into a known
    TrajectoryEventType bucket where possible, but `raw_type_name` always
    preserves the original (pre-normalization) type string -- so an event
    the enum doesn't yet recognize becomes UNKNOWN *without losing
    information*, rather than either being rejected outright or forced
    into a misleading known category. This is the "controlled
    extensibility boundary" §35 asks for.

    Temporal/causal fields per §36-38: `occurred_at` (wall clock),
    `monotonic_sequence` (a per-trajectory counter -- documented below as
    NOT a causal-order guarantee), `ordering_relation_to_previous`
    (explicit, not inferred), and `causal_references` (typed, plural --
    an event may have more than one caused_by/derived_from relationship).
    """

    trajectory_event_id: TrajectoryEventId
    event_type: TrajectoryEventType
    raw_type_name: str
    occurred_at: datetime
    monotonic_sequence: int
    """A per-trajectory counter assigned at normalization time. Per §37:
    this is a *serialization convenience*, not a causal-order claim --
    two events with adjacent monotonic_sequence values may still be
    ordering_relation_to_previous=CONCURRENT. Documented here rather than
    left to be assumed, per §37's explicit "if a sequence number is used,
    document its meaning.\""""
    ordering_relation_to_previous: OrderingRelation = OrderingRelation.UNKNOWN
    worker_id: str | None = None
    execution_instance_id: ExecutionInstanceId | None = None
    attempt_number: int | None = None
    causal_references: tuple[CausalReference, ...] = ()
    summary: str = ""
    duration_ms: float | None = None

    def __post_init__(self) -> None:
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ContractValidationError("negative_duration", "duration_ms cannot be negative (§73).")
        if self.monotonic_sequence < 0:
            raise ContractValidationError("negative_sequence", "monotonic_sequence cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory_event_id": self.trajectory_event_id,
            "event_type": self.event_type.value,
            "raw_type_name": self.raw_type_name,
            "occurred_at": self.occurred_at.isoformat(),
            "monotonic_sequence": self.monotonic_sequence,
            "ordering_relation_to_previous": self.ordering_relation_to_previous.value,
            "worker_id": self.worker_id,
            "execution_instance_id": self.execution_instance_id,
            "attempt_number": self.attempt_number,
            "causal_references": [c.to_dict() for c in self.causal_references],
            "summary": self.summary,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class Trajectory:
    """Normalized evaluation history for one execution instance. `events`
    is stored in `monotonic_sequence` order (validated below) -- per §37,
    this is a serialization order, not an assertion that every consecutive
    pair is causally ordered; see each event's own
    `ordering_relation_to_previous` for that."""

    trajectory_id: TrajectoryId
    execution_instance_id: ExecutionInstanceId
    events: tuple[TrajectoryEvent, ...]

    def __post_init__(self) -> None:
        sequences = [e.monotonic_sequence for e in self.events]
        if sequences != sorted(sequences):
            raise ContractValidationError(
                "events_not_in_sequence_order", "events must be stored in monotonic_sequence order."
            )

    def event_ids(self) -> frozenset[TrajectoryEventId]:
        return frozenset(e.trajectory_event_id for e in self.events)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "execution_instance_id": self.execution_instance_id,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass(frozen=True)
class TrajectorySnapshot:
    """Per §39/research report §7a.6: identifies a point in a trajectory
    with enough context to be restored into a branch later. No snapshot
    engine in Slice 2 -- this is the reference type a future engine would
    populate and read. `reproducibility_context` is a plain description
    rather than a structured field: per the research report's citation of
    "Hierarchical Experimentalist Agents," what actually needs to be true
    (same seed, same physics/tool configuration) is environment-specific
    and not something this contract layer can enumerate generically."""

    snapshot_id: SnapshotId
    trajectory_id: TrajectoryId
    event_boundary_id: TrajectoryEventId
    """The last event included in this snapshot's state."""
    state_reference: str
    reproducibility_context: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "trajectory_id": self.trajectory_id,
            "event_boundary_id": self.event_boundary_id,
            "state_reference": self.state_reference,
            "reproducibility_context": self.reproducibility_context,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class SharedPrefix:
    """Per §40: the common trajectory segment before a BranchPoint."""

    parent_trajectory_id: TrajectoryId
    shared_event_ids: tuple[TrajectoryEventId, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_trajectory_id": self.parent_trajectory_id,
            "shared_event_ids": list(self.shared_event_ids),
        }


@dataclass(frozen=True)
class BranchPoint:
    """Per §40: where a SharedPrefix ends and branches diverge. References
    a TrajectorySnapshot as the restorable state at the divergence point."""

    branch_point_id: str
    snapshot: TrajectorySnapshot
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_point_id": self.branch_point_id,
            "snapshot": nested(self.snapshot),
            "description": self.description,
        }


@dataclass(frozen=True)
class EvaluationBranch:
    """Per §40/§63: one branch descending from a BranchPoint. No branch
    *execution* engine (§2 scope boundary) -- `branch_trajectory_id` is
    populated once some future slice actually runs the branch; until
    then it is None, representing "defined, not yet executed.\""""

    branch_id: BranchId
    shared_prefix: SharedPrefix
    branch_point: BranchPoint
    branch_label: str
    branch_trajectory_id: TrajectoryId | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "shared_prefix": nested(self.shared_prefix),
            "branch_point": nested(self.branch_point),
            "branch_label": self.branch_label,
            "branch_trajectory_id": self.branch_trajectory_id,
        }


@dataclass(frozen=True)
class Checkpoint:
    """Per §42: checkpoint_id, trajectory/run reference, state predicate
    reference, expected progress, required evidence, status. Progress is
    a float in [0, 1] but explicitly documented as non-linear (§42/§43 of
    the research report: "do not assume progress is linearly additive") --
    i.e. checkpoint 3 of 5 does not mean "60% done," it means whatever this
    specific checkpoint's own expected_progress says."""

    checkpoint_id: CheckpointId
    trajectory_id: TrajectoryId
    state_predicate_description: str
    expected_progress: float
    required_evidence_description: str = ""
    status: CheckpointStatus = CheckpointStatus.PENDING

    def __post_init__(self) -> None:
        if not (0.0 <= self.expected_progress <= 1.0):
            raise ContractValidationError(
                "expected_progress_out_of_range", f"expected_progress must be in [0.0, 1.0], got {self.expected_progress}."
            )
        if not isinstance(self.status, CheckpointStatus):
            raise ContractValidationError(
                "status_not_enum_member", f"status must be a CheckpointStatus member, got {type(self.status).__name__}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "trajectory_id": self.trajectory_id,
            "state_predicate_description": self.state_predicate_description,
            "expected_progress": self.expected_progress,
            "required_evidence_description": self.required_evidence_description,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class Intervention:
    """Per §41/research report §7a.6: a structured description of a single
    change applied at a BranchPoint -- "remove one tool," "inject one
    failure," etc. Deliberately just a typed description, not an
    executable specification: Slice 2 does not implement intervention
    execution (§2 scope boundary)."""

    intervention_id: InterventionId
    branch_point: BranchPoint
    intervention_type: str
    """Free string (e.g. "remove_tool", "inject_failure", "change_model")
    -- per §41, "the contract records the experimental relationship," not
    a closed taxonomy of every possible intervention OCBrain might ever
    define."""
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "branch_point": nested(self.branch_point),
            "intervention_type": self.intervention_type,
            "description": self.description,
        }


@dataclass(frozen=True)
class CounterfactualEvaluation:
    """Per §41: structured references to baseline/intervention/
    counterfactual/comparison. `causal_confidence_note` exists specifically
    so that a filled-in comparison never implies more causal certainty
    than the evidence supports -- per the research report's citation of
    ~14% state-of-the-art step-level attribution accuracy (arXiv:2606.08275),
    this field defaults to a hedge, not a confident claim, and there is no
    field on this type that would let a caller assert "proven cause" --
    only a free-text note, matching §41's "do not encode causal certainty
    into the contract.\""""

    counterfactual_evaluation_id: CounterfactualEvaluationId
    baseline_trajectory_id: TrajectoryId
    intervention: Intervention
    counterfactual_trajectory_id: TrajectoryId | None = None
    """None until some future slice actually executes the branch."""
    observed_outcome_difference: str | None = None
    causal_confidence_note: str = "correlational only; no causal attribution mechanism exists in Slice 2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "counterfactual_evaluation_id": self.counterfactual_evaluation_id,
            "baseline_trajectory_id": self.baseline_trajectory_id,
            "intervention": nested(self.intervention),
            "counterfactual_trajectory_id": self.counterfactual_trajectory_id,
            "observed_outcome_difference": self.observed_outcome_difference,
            "causal_confidence_note": self.causal_confidence_note,
        }
