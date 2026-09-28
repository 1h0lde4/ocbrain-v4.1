"""
Evidence contracts, including the circular-evidence structural check
(architecture v2 Part 2 §17): evidence that is merely an unsupported
restatement of its own claim must be structurally rejected -- this is
a property of the claim/evidence graph, checked mechanically, not an
LLM judgment call.

Extended with Phase 4 contracts (v2 §13, §14, §44):
  - ProvenanceCompleteness: COMPLETE / PARTIAL / UNKNOWN / BROKEN
  - EvidenceReference: exact source + locator binding for evidence
  - EvidenceObservation: binds evidence to an existing Observation
  - EvidenceTransformation: reconstructable lineage with safety rule
  - EvidenceBundle: immutable collection preserving all evidence states
  - MinimumSufficientEvidence: declarative retention requirement
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from .identity import ClaimId, CriterionId, EvidenceId, ObservationId


class EvidenceDirectness(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    DERIVED = "derived"
    MODEL_INTERPRETATION = "model_interpretation"


class EvidenceStatus(str, Enum):
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    IRRELEVANT = "irrelevant"
    INSUFFICIENT = "insufficient"
    SUFFICIENT = "sufficient"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True)
class EvidenceSource:
    source_type: str  # e.g. "retrieval", "tool_result", "runtime_state", "citation", "agent_assertion"
    source_id: str
    producer: str


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: EvidenceId
    source: EvidenceSource
    locator: str  # exact locator: span / line-range / JSON-path / event-id / etc.
    directness: EvidenceDirectness
    status: EvidenceStatus
    observed_at: datetime
    retrieved_at: datetime
    content_summary: str  # short summary only -- raw payloads don't belong in the contract layer
    supports_claim_ids: Tuple[ClaimId, ...] = ()
    is_restatement_of_claim: bool = False


class CircularEvidenceError(ValueError):
    """Raised when evidence for a claim is structurally circular."""


def check_not_circular(claim_id: ClaimId, evidence: EvidenceItem) -> None:
    """Structural graph check. NOT a heuristic -- a piece of evidence
    flagged as a restatement of the very claim it's offered to support
    is rejected outright, unless the target under verification is the
    narrower fact that the statement was made (a different claim)."""
    if claim_id in evidence.supports_claim_ids and evidence.is_restatement_of_claim:
        raise CircularEvidenceError(
            f"evidence {evidence.evidence_id} for claim {claim_id} is flagged as "
            f"a restatement of the claim itself -- cannot be its own evidence "
            f"unless the verification target is the fact that the statement was made"
        )


# ---------------------------------------------------------------------------
# Phase 4 — Evidence Architecture (v2 §13, §14, §44)
# ---------------------------------------------------------------------------


class ProvenanceCompleteness(str, Enum):
    """Provenance completeness status (v2 §14).  A verification resting
    on incomplete provenance discloses that limitation rather than
    presenting itself as fully traceable.  Incomplete/unknown/broken
    provenance must remain explicitly represented and must never
    silently become COMPLETE."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    BROKEN = "broken"


@dataclass(frozen=True)
class EvidenceReference:
    """Exact source + locator binding for a piece of evidence (v2 §13,
    §14).  Provides the link from evidence back to its source and the
    exact location within that source.  Vague citation strings or
    'somewhere in the output' references are invalid.

    Preserves criterion binding when the evidence is used for a
    specific criterion.  Does NOT carry raw payloads -- follows the
    existing EvidenceItem boundary (content_summary, not raw content).

    Not independently addressable -- no EvidenceReferenceId.  This is
    a binding record, not a registry entity."""
    evidence_id: EvidenceId
    source: EvidenceSource
    locator: str
    content_summary: str
    provenance: ProvenanceCompleteness
    criterion_id: Optional[CriterionId] = None
    claim_id: Optional[ClaimId] = None
    scope: str = ""
    correlation_group: str = ""
    independence_level: str = ""
    sensitivity_classification: str = ""

    def __post_init__(self) -> None:
        if not self.locator or not self.locator.strip():
            raise ValueError(
                "EvidenceReference requires a non-empty locator -- exact "
                "source + locator binding is required; vague citations or "
                "'somewhere in the output' references are invalid"
            )
        if not self.content_summary or not self.content_summary.strip():
            raise ValueError(
                "EvidenceReference requires a non-empty content_summary -- "
                "raw payloads don't belong here, but an empty summary is "
                "indistinguishable from missing evidence"
            )


@dataclass(frozen=True)
class EvidenceObservation:
    """Binds evidence to an existing Observation (v2 §13).  Preserves
    the observation's existing authority/provenance -- does NOT create a
    second ObservationAuthority model or duplicate Observation semantics.

    The observation_id must reference a real Observation; validation of
    that reference depends on a later execution/registry layer.  This
    contract records the binding explicitly rather than inventing
    registry infrastructure.

    Not independently addressable -- no EvidenceObservationId.  This is
    a binding record."""
    evidence_id: EvidenceId
    observation_id: ObservationId
    observed_at: datetime
    retrieved_at: datetime
    directness: EvidenceDirectness
    relevance: str
    provenance: ProvenanceCompleteness

    def __post_init__(self) -> None:
        if not self.relevance or not self.relevance.strip():
            raise ValueError(
                "EvidenceObservation requires a non-empty relevance -- "
                "the relationship between the observation and the evidence "
                "must be stated, not left implicit"
            )


class TransformationType(str, Enum):
    """Categories of evidence transformation (IMPLEMENTATION JUDGMENT).
    The architecture names examples (summarized, translated, normalized,
    OCR'd, extracted, parsed, redacted) but does not prescribe a closed
    vocabulary.  These are the minimal categories needed to represent
    the architecture's named examples."""
    SUMMARY = "summary"
    TRANSLATION = "translation"
    NORMALIZATION = "normalization"
    OCR = "ocr"
    EXTRACTION = "extraction"
    PARSING = "parsing"
    REDACTION = "redaction"
    MODEL_INTERPRETATION = "model_interpretation"


@dataclass(frozen=True)
class EvidenceTransformation:
    """Reconstructable lineage for derived evidence (v2 §14).

    Every derived evidence object retains its source evidence,
    transformation type, transformation version, and transformation
    producer.  The resulting directness must not be stronger than the
    source directness -- a normalization step doesn't get to make
    derived evidence look more direct than it is.

    NOT independently addressable -- no TransformationId.  This is a
    lineage record, not a registry entity.

    IMPORTANT: EvidenceDirectness values are CATEGORICAL, not ordinal.
    There is no generic DIRECT > INDIRECT > DERIVED comparator.  The
    safety check implemented here is narrow and structural: a
    transformation whose source is not DIRECT cannot produce DIRECT
    output.  This is the minimum safety rule the architecture demands
    without inventing an ordering the type itself doesn't assert."""
    source_evidence_id: EvidenceId
    source_directness: EvidenceDirectness
    transformation_type: TransformationType
    transformation_version: str
    transformation_producer: str
    result_evidence_id: EvidenceId
    result_directness: EvidenceDirectness
    provenance: ProvenanceCompleteness

    def __post_init__(self) -> None:
        if not self.transformation_version or not self.transformation_version.strip():
            raise ValueError(
                "EvidenceTransformation requires a non-empty "
                "transformation_version -- reconstructable lineage "
                "requires knowing what version of the transformation "
                "was applied"
            )
        if not self.transformation_producer or not self.transformation_producer.strip():
            raise ValueError(
                "EvidenceTransformation requires a non-empty "
                "transformation_producer -- reconstructable lineage "
                "requires knowing what produced the transformation"
            )
        if self.source_evidence_id == self.result_evidence_id:
            raise ValueError(
                "EvidenceTransformation source and result must be "
                "distinct evidence objects -- a transformation that "
                "maps evidence to itself is not a transformation"
            )
        # Transformation safety rule (v2 §14): derived evidence must
        # not inherit stronger directness than the transformation
        # justifies.  Since EvidenceDirectness is CATEGORICAL (not
        # ordinal), the only structural safety check we can make without
        # inventing an ordering is: if the source is not DIRECT, the
        # result cannot be DIRECT.  This prevents summaries,
        # translations, normalizations, OCR, extractions, parsing,
        # redaction, and model interpretations from silently becoming
        # DIRECT.
        if (self.source_directness != EvidenceDirectness.DIRECT
                and self.result_directness == EvidenceDirectness.DIRECT):
            raise ValueError(
                f"transformation safety violation (v2 §14): source "
                f"evidence has directness={self.source_directness.value!r}, "
                f"so derived evidence cannot be DIRECT -- a "
                f"{self.transformation_type.value} does not make "
                f"evidence more direct than its source"
            )


@dataclass(frozen=True)
class EvidenceBundle:
    """Immutable collection of evidence actually bound to an assessment
    (v2 §13).  Preserves ALL evidence including contradictory,
    irrelevant, insufficient, or otherwise non-supporting evidence
    without silently filtering, resolving, averaging, or overriding.

    Bundle membership does NOT imply truth, support, refutation,
    verification, whole-verification sufficiency, or a verdict.
    Assessment and aggregation remain later-layer responsibilities.

    Not independently addressable in this phase -- the bundle is always
    scoped to a specific assessment context."""
    bundle_id: str
    evidence_ids: Tuple[EvidenceId, ...]
    criterion_id: Optional[CriterionId] = None
    claim_id: Optional[ClaimId] = None
    provenance: ProvenanceCompleteness = ProvenanceCompleteness.UNKNOWN

    def __post_init__(self) -> None:
        if not self.bundle_id or not self.bundle_id.strip():
            raise ValueError(
                "EvidenceBundle requires a non-empty bundle_id"
            )
        if not self.evidence_ids:
            raise ValueError(
                "EvidenceBundle requires at least one evidence_id -- "
                "an empty bundle is indistinguishable from missing evidence"
            )
        # Check for duplicate evidence IDs within the bundle
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            seen: set = set()
            duplicates: list = []
            for eid in self.evidence_ids:
                if eid in seen:
                    duplicates.append(eid)
                seen.add(eid)
            raise ValueError(
                f"EvidenceBundle contains duplicate evidence_ids: "
                f"{duplicates!r} -- each piece of evidence should "
                f"appear at most once in a bundle"
            )


@dataclass(frozen=True)
class MinimumSufficientEvidence:
    """Declarative retention requirement (v2 §44).  Describes the
    minimum evidence necessary to reconstruct and audit a decision
    while minimizing unnecessary storage, context size, privacy
    exposure, and replay cost.

    This is a REQUIREMENT, not a result.  It is distinct from
    EvidenceStatus.SUFFICIENT and must never be turned into a verdict,
    a truth claim, a numeric evidence score, an aggregation algorithm,
    or automatic promotion of an evidence bundle to verified.

    Fields are IMPLEMENTATION JUDGMENT -- the architecture (v2 §44)
    names the concept and its purpose but does not prescribe a field
    layout."""
    criterion_id: CriterionId
    minimum_items: int
    required_directness: Optional[EvidenceDirectness] = None
    required_provenance: ProvenanceCompleteness = ProvenanceCompleteness.COMPLETE
    description: str = ""

    def __post_init__(self) -> None:
        if self.minimum_items < 0:
            raise ValueError(
                "minimum_items cannot be negative"
            )
