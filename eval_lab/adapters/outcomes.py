"""eval_lab/adapters/outcomes.py — adapter-level outcome, disposition, terminality.

These types are deliberately NOT eval_lab/contracts/ additions. Slice 2's
Trajectory/TrajectoryEvent describe *what happened at runtime*; the types
here describe *how normalization of that evidence went* -- a different,
adapter-scoped concern, analogous to a compiler's diagnostics being
separate from the language it compiles. This keeps Slice 2's contracts
frozen (per this Slice's own instruction) while still satisfying §9's
"every event needs an explicit disposition" and §12's terminality
requirements, which Slice 2 genuinely has no field for (EvaluationRun's
status/fault_domain describe the Lab's evaluation outcome, not the raw
subject trajectory's own observed terminal state -- these are
independent, the same way ADR-LAB-01 keeps subject/trajectory/evaluator
independent).

Reuses Slice 2's FailureRecord/ErrorEnvelope/FaultDomain for adapter-level
errors per this Slice's §11 instruction ("reuse existing Slice 2
failure/error contracts where appropriate... do not create a parallel
failure taxonomy").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from eval_lab.contracts.failure import ErrorEnvelope
from eval_lab.contracts.identifiers import ExecutionInstanceId, TrajectoryId
from eval_lab.contracts.trajectory import Trajectory


class EventDispositionType(str, Enum):
    """Per §9: every source event the adapter encounters gets exactly one
    of these, recorded -- never silently dropped."""

    NORMALIZED = "normalized"
    """Became canonical TrajectoryEvent evidence, fully representable."""
    RETAINED_RAW = "retained_raw"
    """Normalized, but canonical fields couldn't represent everything --
    the raw source payload is retained alongside (see EventDisposition.raw_payload)."""
    UNSUPPORTED = "unsupported"
    """A recognized-but-not-yet-handled event shape; recorded, not normalized into a TrajectoryEvent."""
    MALFORMED = "malformed"
    """Structurally invalid source event (e.g. missing required StreamEvent fields)."""
    REJECTED = "rejected"
    """Structurally valid but fails an explicit adapter boundary rule (documented per-rule at the call site)."""
    DUPLICATE_IGNORED = "duplicate_ignored"
    """Same event_id seen before with an identical payload -- idempotent skip, not silent (recorded here)."""
    CONFLICTING_DUPLICATE = "conflicting_duplicate"
    """Same event_id seen before with a DIFFERING payload -- a genuine
    integrity concern (§6). Neither occurrence is silently preferred;
    both are recorded, and this pushes the overall outcome toward
    PARTIAL at minimum."""


class AdapterOutcomeStatus(str, Enum):
    """Per §11 of this Slice, verbatim: successful, partial, source-event
    rejection, unsupported evidence, incomplete source trace, fatal
    adapter failure."""

    SUCCESSFUL = "successful"
    PARTIAL = "partial"
    SOURCE_EVENT_REJECTED = "source_event_rejected"
    UNSUPPORTED_EVIDENCE = "unsupported_evidence"
    INCOMPLETE_SOURCE_TRACE = "incomplete_source_trace"
    FATAL_ADAPTER_FAILURE = "fatal_adapter_failure"


class TrajectoryTerminality(str, Enum):
    """Per §12: the adapter must distinguish these from actual runtime
    evidence, never infer completion merely because ingestion stopped.

    This is independent of AdapterOutcomeStatus above: a trace can be
    fully, successfully normalized (AdapterOutcomeStatus.SUCCESSFUL) while
    its terminality is TERMINALITY_UNKNOWN, because the *subject's*
    execution simply never produced a terminal event -- normalization
    succeeded at faithfully representing that absence, which is a
    different fact than normalization itself failing."""

    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED_OBSERVED = "completed_observed"
    FAILED_OBSERVED = "failed_observed"
    CANCELLED_OBSERVED = "cancelled_observed"
    TERMINALITY_UNKNOWN = "terminality_unknown"
    """No terminal event was observed, and the adapter has no basis to
    assume one implicitly occurred -- per §8, absence of evidence is not
    evidence of success (and, symmetrically, not evidence of failure
    either). Worker event emission is confirmed best-effort
    (core/workers/base.py's try/except around EventStream.append swallows
    failures) -- a missing terminal event does not mean the subject
    didn't finish, only that no terminal evidence reached this adapter."""
    INCOMPLETE_TRACE = "incomplete_trace"
    """Distinct from TERMINALITY_UNKNOWN: this means the adapter has
    positive reason to believe evidence is missing (e.g. a gap in
    monotonic_sequence, or the caller explicitly flagged a truncated
    ingestion window), not just the absence of a terminal event."""


@dataclass(frozen=True)
class EventDisposition:
    """One source event's disposition record. `source_event_id` is the
    runtime StreamEvent.event_id (not a Lab identifier) -- deliberately
    typed as a plain str rather than a Lab NewType, since this is raw
    runtime evidence being tracked, not a Lab-minted identity."""

    source_event_id: str
    disposition: EventDispositionType
    reason: str
    raw_payload: dict[str, Any] | None = None
    """Populated for RETAINED_RAW (and optionally CONFLICTING_DUPLICATE)
    -- the original StreamEvent.payload, preserved verbatim so nothing is
    silently lost even where canonical TrajectoryEvent fields couldn't
    hold it (§9)."""
    canonical_trajectory_event_id: str | None = None
    """Set when disposition is NORMALIZED/RETAINED_RAW -- links back to
    the TrajectoryEvent this source event became, for audit (§14)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_event_id": self.source_event_id,
            "disposition": self.disposition.value,
            "reason": self.reason,
            "raw_payload": self.raw_payload,
            "canonical_trajectory_event_id": self.canonical_trajectory_event_id,
        }


@dataclass(frozen=True)
class NormalizationResult:
    """The adapter's complete output for one normalization call. `trajectory`
    is None only when outcome_status is FATAL_ADAPTER_FAILURE (nothing
    usable was produced); otherwise it is always present, even if empty
    or partial -- per §10, one malformed event must not crash the whole
    ingestion unless architecture requires fail-closed behavior, which
    discovery found no evidence of here.

    Finding 3 (raw evidence accessibility): `Trajectory` alone does not
    carry raw source payload for events where canonical fields couldn't
    represent everything -- that lives in `event_dispositions[i].raw_payload`,
    linked back via `canonical_trajectory_event_id`. **This
    `NormalizationResult`, not `Trajectory` in isolation, is the durable
    unit of output.** A caller (a future persistence Slice) that discards
    `event_dispositions` and keeps only `.trajectory` will lose raw
    evidence permanently for any event that needed RETAINED_RAW or
    CONFLICTING_DUPLICATE handling -- e.g. worker.failed's error/error_type,
    worker.rejected's reason/governor. If a later evaluator needs to
    reconstruct exactly what the runtime emitted (per Slice 2's
    EvaluationInputSnapshot design), it needs this whole object retained,
    not just the Trajectory it wraps.
    """

    execution_instance_id: ExecutionInstanceId
    trajectory_id: TrajectoryId
    trajectory: Trajectory | None
    outcome_status: AdapterOutcomeStatus
    terminality: TrajectoryTerminality
    event_dispositions: tuple[EventDisposition, ...]
    errors: tuple[ErrorEnvelope, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_instance_id": self.execution_instance_id,
            "trajectory_id": self.trajectory_id,
            "trajectory": self.trajectory.to_dict() if self.trajectory is not None else None,
            "outcome_status": self.outcome_status.value,
            "terminality": self.terminality.value,
            "event_dispositions": [d.to_dict() for d in self.event_dispositions],
            "errors": [e.to_dict() for e in self.errors],
        }
