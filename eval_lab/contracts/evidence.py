"""eval_lab/contracts/evidence.py — evidence, provenance, artifacts, human annotation.

Implements §19-20, §23-29, §33, §64-66 of the research report's amendment
and §22-33 of this Slice's brief. `Evidence` is the load-bearing type here:
per ADR-LAB-01, a `Score` without `Evidence` is exactly the opaque number
the mission repeatedly forbids (original brief §27, amendment invariant
list). Human annotation (Annotator/Annotation/...) lives in this module
rather than its own file: an Annotation *is* a kind of Evidence (§33's own
framing -- "Human review must be able to represent PASS/FAIL/PARTIAL/
INCONCLUSIVE and confidence" is exactly Evidence's shape plus a human
source), and splitting it out would separate two things that share nearly
every field for no domain reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.enums import EvidenceCapturePolicy, EvidenceOrigin, TrustClassification
from eval_lab.contracts.identifiers import (
    AnnotationId,
    AnnotatorId,
    ArtifactId,
    ContentHash,
    EvidenceId,
)
from eval_lab.contracts.serialization import ContractValidationError, enum_value, nested


@dataclass(frozen=True)
class Provenance:
    """Per §27/§57: every derived object should retain source,
    transformation, creator/version, and timestamp -- without embedding
    the complete parent object (§27 explicit requirement)."""

    source_description: str
    transformation: str | None
    """What was done to produce this object from its source, if anything
    (e.g. "redacted", "hashed", "sampled from population"). None means
    "this is the source, not a derivation."""
    creator_id: str
    creator_version: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_description": self.source_description,
            "transformation": self.transformation,
            "creator_id": self.creator_id,
            "creator_version": self.creator_version,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Provenance":
        return cls(
            source_description=d["source_description"],
            transformation=d.get("transformation"),
            creator_id=d["creator_id"],
            creator_version=d["creator_version"],
            created_at=datetime.fromisoformat(d["created_at"]),
        )


@dataclass(frozen=True)
class ArtifactReference:
    """Per §24: distinguishes artifact identity from artifact content
    identity/hash, and never embeds the artifact itself (§24 explicit:
    "Do not embed large artifacts directly into evaluation contracts")."""

    artifact_id: ArtifactId
    artifact_type: str
    storage_location: str
    """Opaque reference string (path, URI, or backend-specific key) --
    Slice 2 does not implement a storage backend, so this is intentionally
    uninterpreted here."""
    content_hash: ContentHash | None
    provenance: Provenance | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "storage_location": self.storage_location,
            "content_hash": self.content_hash,
            "provenance": nested(self.provenance),
        }


@dataclass(frozen=True)
class IntegrityEvidence:
    """Per §36/§39/§55: tamper-evidence hashes, where the Lab has them.
    Every field is optional -- Slice 2 does not create new cryptographic
    infrastructure (§55/§39 explicit instruction), so this is a place to
    *record* hashes computed elsewhere (e.g. an existing OCBrain audit
    primitive, once identified -- see the research report's open question
    on this), not a mechanism that computes them itself."""

    event_hash: ContentHash | None = None
    trajectory_hash: ContentHash | None = None
    artifact_hash: ContentHash | None = None
    environment_hash: ContentHash | None = None
    benchmark_hash: ContentHash | None = None
    evaluation_definition_hash: ContentHash | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_hash": self.event_hash,
            "trajectory_hash": self.trajectory_hash,
            "artifact_hash": self.artifact_hash,
            "environment_hash": self.environment_hash,
            "benchmark_hash": self.benchmark_hash,
            "evaluation_definition_hash": self.evaluation_definition_hash,
        }


@dataclass(frozen=True)
class EvidenceFreshness:
    """Per §20 (research report amendment): was this evidence current when
    used, and has anything it refers to changed since. Kept to the fields
    that are answerable without executing anything (Slice 2 is
    contracts-only) -- `state_possibly_changed_since` and
    `produced_before_mutation` are facts the *caller* asserts when
    constructing this (e.g. the future trace adapter), not something this
    contract computes."""

    captured_at: datetime
    state_possibly_changed_since: bool = False
    produced_before_task_mutation: bool | None = None
    """None = not applicable (no mutation occurred / not yet known)."""
    staleness_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at.isoformat(),
            "state_possibly_changed_since": self.state_possibly_changed_since,
            "produced_before_task_mutation": self.produced_before_task_mutation,
            "staleness_note": self.staleness_note,
        }


@dataclass(frozen=True)
class Evidence:
    """The central evidence type referenced by EvaluationResult (result.py),
    OracleValidation (oracle.py), and SimulatorReliability (simulator.py).

    Per §23/§29: evidence identifies *what* it points to (exactly one of
    the reference fields below should normally be set -- multiple are
    allowed for composite evidence, but at least one is required, per
    §71's cross-field invariants) and carries its own origin/trust
    classification rather than being treated as uniformly authoritative.
    """

    evidence_id: EvidenceId
    origin: EvidenceOrigin
    trust_classification: TrustClassification
    capture_policy: EvidenceCapturePolicy
    freshness: EvidenceFreshness

    # Reference fields -- at least one must be set (§71 cross-field invariant)
    trajectory_event_id: str | None = None
    trajectory_span: tuple[str, str] | None = None
    """(start_event_id, end_event_id) inclusive span, for evidence that
    covers a range rather than one event."""
    state_predicate_description: str | None = None
    artifact: ArtifactReference | None = None
    oracle_output_description: str | None = None
    judge_output_description: str | None = None
    human_annotation_id: AnnotationId | None = None
    environment_state_description: str | None = None

    provenance: Provenance | None = None
    integrity: IntegrityEvidence | None = None

    def __post_init__(self) -> None:
        reference_fields = (
            self.trajectory_event_id,
            self.trajectory_span,
            self.state_predicate_description,
            self.artifact,
            self.oracle_output_description,
            self.judge_output_description,
            self.human_annotation_id,
            self.environment_state_description,
        )
        if all(f is None for f in reference_fields):
            raise ContractValidationError(
                "evidence_requires_at_least_one_reference",
                "Evidence must reference at least one of: trajectory_event_id, "
                "trajectory_span, state_predicate_description, artifact, "
                "oracle_output_description, judge_output_description, "
                "human_annotation_id, environment_state_description.",
            )
        if self.capture_policy == EvidenceCapturePolicy.UNAVAILABLE and (
            self.artifact is not None or self.state_predicate_description is not None
        ):
            raise ContractValidationError(
                "unavailable_capture_policy_with_content",
                "capture_policy=UNAVAILABLE means the underlying content was not "
                "captured; artifact/state_predicate_description should be None.",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "origin": enum_value(self.origin),
            "trust_classification": enum_value(self.trust_classification),
            "capture_policy": enum_value(self.capture_policy),
            "freshness": nested(self.freshness),
            "trajectory_event_id": self.trajectory_event_id,
            "trajectory_span": list(self.trajectory_span) if self.trajectory_span else None,
            "state_predicate_description": self.state_predicate_description,
            "artifact": nested(self.artifact),
            "oracle_output_description": self.oracle_output_description,
            "judge_output_description": self.judge_output_description,
            "human_annotation_id": self.human_annotation_id,
            "environment_state_description": self.environment_state_description,
            "provenance": nested(self.provenance),
            "integrity": nested(self.integrity),
        }


# ---------------------------------------------------------------------------
# Human annotation (§33, §64-65)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Annotator:
    """Per §65: human annotation is not an invisible absolute oracle --
    an Annotator is tracked identity, not an anonymous rubber stamp."""

    annotator_id: AnnotatorId
    display_name: str
    qualification_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotator_id": self.annotator_id,
            "display_name": self.display_name,
            "qualification_note": self.qualification_note,
        }


@dataclass(frozen=True)
class AnnotationConfidence:
    """Kept distinct from the annotation's verdict itself, same reasoning
    as judge confidence (evaluator.py) -- a low-confidence PASS is a
    different fact than a high-confidence PASS, even though both serialize
    to the same status."""

    level: str  # "high" | "medium" | "low" -- free string, not an enum:
    # unlike EvaluatorResultStatus this is a qualitative human self-report,
    # not a closed system vocabulary the contract layer reasons about.
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "note": self.note}


@dataclass(frozen=True)
class Annotation:
    """One human judgment. `AnnotationTask` (what was asked) is
    intentionally not a separate type in Slice 2 -- its only fields would
    be a prompt string and a reference to what's being annotated, both of
    which fit directly on Annotation without a wrapper that nothing else
    references; introducing it now would be exactly the "instantiate every
    noun as a class" §7 warns against."""

    annotation_id: AnnotationId
    annotator: Annotator
    task_description: str
    verdict: str  # "pass" | "fail" | "partial" | "inconclusive" -- see note below
    confidence: AnnotationConfidence
    created_at: datetime
    rationale: str | None = None

    def __post_init__(self) -> None:
        allowed = {"pass", "fail", "partial", "inconclusive"}
        if self.verdict not in allowed:
            raise ContractValidationError(
                "invalid_annotation_verdict",
                f"verdict must be one of {sorted(allowed)}, got {self.verdict!r}.",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "annotator": nested(self.annotator),
            "task_description": self.task_description,
            "verdict": self.verdict,
            "confidence": nested(self.confidence),
            "created_at": self.created_at.isoformat(),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class AnnotatorAgreement:
    """Per §30 (research report amendment, extended by this Slice's §79
    test requirements): agreement statistics between two annotation
    sources. Deliberately generic over *which* two sources (human-human,
    human-judge, judge-judge, simulator-human, etc. per the amendment's
    §30) rather than one type per pairing."""

    source_a_description: str
    source_b_description: str
    n_compared: int
    agreement_rate: float
    """0.0-1.0. Simple percent agreement; Cohen's kappa or another
    chance-corrected statistic is metadata a *future* statistics engine
    would compute (ADR-LAB-05 §2: no statistics engine in Slice 2) -- this
    field records raw agreement, not an inferential statistic."""

    def __post_init__(self) -> None:
        if not (0.0 <= self.agreement_rate <= 1.0):
            raise ContractValidationError(
                "agreement_rate_out_of_range",
                f"agreement_rate must be in [0.0, 1.0], got {self.agreement_rate}.",
            )
        if self.n_compared < 0:
            raise ContractValidationError("negative_n_compared", "n_compared cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_a_description": self.source_a_description,
            "source_b_description": self.source_b_description,
            "n_compared": self.n_compared,
            "agreement_rate": self.agreement_rate,
        }


@dataclass(frozen=True)
class AnnotatorCalibration:
    """Per §65: fatigue/drift/inconsistency are named risks, not assumed
    away. `calibrated_at` + `calibration_case_ids` let a future workflow
    answer "when was this annotator last checked, and against what,"
    without this Slice implementing the checking process itself."""

    annotator_id: AnnotatorId
    calibrated_at: datetime
    calibration_case_ids: tuple[str, ...]
    agreement_with_reference: AnnotatorAgreement | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotator_id": self.annotator_id,
            "calibrated_at": self.calibrated_at.isoformat(),
            "calibration_case_ids": list(self.calibration_case_ids),
            "agreement_with_reference": nested(self.agreement_with_reference),
        }
