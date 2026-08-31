"""eval_lab/contracts/evaluation_input.py — the exact evaluator-visible view.

Implements §22, §28, §76 of this Slice's brief. This is one of the more
easily-skipped concepts in the whole model, and the brief calls that out
explicitly (§22: "This is important"): without it, there is no way to
later answer "what evidence did the judge actually see" as distinct from
"what actually happened" (the Trajectory) -- and per §76, different
evaluators legitimately see different views of the *same* run (a
deterministic evaluator sees raw state; a human sees redacted evidence).
Collapsing these would make it impossible to tell whether a disagreement
between two evaluators is a real disagreement or just two different
inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.enums import EvidenceCapturePolicy
from eval_lab.contracts.evidence import ArtifactReference, Evidence
from eval_lab.contracts.identifiers import (
    EvaluationDefinitionId,
    EvaluatorId,
    EvaluatorVersion,
    TrajectoryEventId,
    TrajectoryId,
)
from eval_lab.contracts.serialization import ContractValidationError, nested_list


@dataclass(frozen=True)
class EvaluationInputSnapshot:
    """Exactly what one evaluator saw when it produced one EvaluationResult.

    `trajectory_id` + `included_event_ids` (rather than embedding the
    Trajectory) represents *which slice* of the trajectory this evaluator
    was shown -- per §76's judge/human example, a judge might see curated
    evidence rather than the raw ordered trajectory a deterministic
    evaluator gets. `included_event_ids=None` means "the full trajectory,"
    distinct from an empty tuple ("none of it, deliberately") -- the same
    None-vs-empty distinction Evidence's freshness/collections already
    apply elsewhere in this package.
    """

    evaluator_id: EvaluatorId
    evaluator_version: EvaluatorVersion
    evaluation_definition_id: EvaluationDefinitionId
    trajectory_id: TrajectoryId
    included_event_ids: tuple[TrajectoryEventId, ...] | None
    """None = full trajectory; empty tuple = deliberately none; a
    populated tuple = exactly this subset."""
    capture_policy: EvidenceCapturePolicy
    evidence_shown: tuple[Evidence, ...] = ()
    artifacts_shown: tuple[ArtifactReference, ...] = ()
    curation_note: str | None = None
    """Free text explaining *how* this view was produced if it differs
    from the raw trajectory (e.g. "redacted per privacy policy X" or
    "summarized for judge context window") -- per §28's redaction-validity
    concern, this is where a future reader learns whether redaction may
    have affected evaluation validity, without this contract needing a
    structured redaction-impact model in Slice 2."""
    captured_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    def __post_init__(self) -> None:
        if self.included_event_ids is not None and len(self.included_event_ids) != len(set(self.included_event_ids)):
            raise ContractValidationError(
                "duplicate_included_event_ids", "included_event_ids must not contain duplicates."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "evaluation_definition_id": self.evaluation_definition_id,
            "trajectory_id": self.trajectory_id,
            "included_event_ids": list(self.included_event_ids) if self.included_event_ids is not None else None,
            "capture_policy": self.capture_policy.value,
            "evidence_shown": nested_list(list(self.evidence_shown)),
            "artifacts_shown": nested_list(list(self.artifacts_shown)),
            "curation_note": self.curation_note,
            "captured_at": self.captured_at.isoformat(),
        }
