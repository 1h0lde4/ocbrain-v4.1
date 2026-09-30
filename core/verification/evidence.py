"""
Evidence contracts, including the circular-evidence structural check
(architecture v2 Part 2 §17): evidence that is merely an unsupported
restatement of its own claim must be structurally rejected -- this is
a property of the claim/evidence graph, checked mechanically, not an
LLM judgment call.

Extended with Phase 4 contracts (v2 §13, §14, §44) -- WORK IN PROGRESS,
reconciled but NOT complete (see "Enforcement boundary" below):
  - ProvenanceCompleteness: COMPLETE / PARTIAL / UNKNOWN / BROKEN
  - EvidenceReference: exact source + locator + claim/criterion binding
  - EvidenceObservation: binds evidence to an existing Observation by id
  - EvidenceTransformation: reconstructable lineage + categorical safety rules
  - EvidenceBundle: immutable collection that preserves every EvidenceItem
  - MinimumSufficientEvidence: declarative retention/auditability requirement

Enforcement boundary
--------------------
These contracts enforce only what their own fields can observe. They do
NOT enforce, and no comment in this module should be read as enforcing:

  * authority, integrity or certainty of evidence (no such fields here;
    authority lives on Observation, integrity/certainty are assessment-layer);
  * scope, validity window, relevance, specificity, correlation_group,
    independence_level, sensitivity classification (v1 §15 metadata with no
    vocabulary in the frozen architecture; NOT carried by these contracts --
    an open decision, see the implementation report);
  * observation absence (NOT_OBSERVED / OBSERVED_ABSENT / ...) -- a later
    coverage-batch contract; nothing here models "no evidence" as evidence;
  * that a locator is genuinely *exact* -- only that it is non-empty.

EvidenceDirectness is categorical, never ordinal: no comparison below asks
whether one value is "stronger" than another.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from .identity import ClaimId, CriterionId, EvidenceId, ObservationId
from .observation import Observation


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


class EvidenceBindingError(ValueError):
    """Raised when a binding record disagrees with the concrete object it
    claims to describe (mismatched id, source, locator, directness, ...)."""


def _require_text(value: str, what: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")


def _require_binding(
    claim_id: Optional[ClaimId], criterion_id: Optional[CriterionId], owner: str
) -> None:
    if claim_id is None and criterion_id is None:
        raise ValueError(
            f"{owner} must be bound to a claim_id and/or a criterion_id -- "
            f"evidence that is not bound to anything is a citation, not a binding"
        )
    if claim_id is not None:
        _require_text(claim_id, f"{owner}.claim_id")
    if criterion_id is not None:
        _require_text(criterion_id, f"{owner}.criterion_id")


def _require_unique_tuple(values: object, what: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(
            f"{what} must be a tuple (immutable); got {type(values).__name__}"
        )
    if not values:
        raise ValueError(f"{what} must not be empty")


@dataclass(frozen=True)
class EvidenceReference:
    """Binds a claim and/or criterion to one piece of evidence with the
    exact source and locator (v1 §16: ``Claim -> Evidence -> Source ->
    Locator``, never ``Claim -> Source``).

    It reuses EvidenceSource rather than re-declaring it, and carries NO
    content/summary field, so it cannot become a channel for raw payloads.
    The evidence's own metadata (directness, status, timestamps, summary)
    stays on EvidenceItem, the single source of truth; call
    ``verify_against(item)`` to prove this record does not drift from it.

    Enforced: non-empty locator and source identity; a claim and/or
    criterion binding.  NOT enforced (cannot be, structurally): that the
    locator is *exact* -- 'somewhere in the output' is a non-empty string.
    Exactness is the producer's obligation; this record makes the missing
    binding, not a vague one, the thing that is rejected.

    Not independently addressable -- no EvidenceReferenceId."""
    evidence_id: EvidenceId
    source: EvidenceSource
    locator: str
    provenance: ProvenanceCompleteness
    claim_id: Optional[ClaimId] = None
    criterion_id: Optional[CriterionId] = None

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "EvidenceReference.evidence_id")
        _require_text(self.locator, "EvidenceReference.locator")
        _require_text(self.source.source_type, "EvidenceReference.source.source_type")
        _require_text(self.source.source_id, "EvidenceReference.source.source_id")
        _require_text(self.source.producer, "EvidenceReference.source.producer")
        _require_binding(self.claim_id, self.criterion_id, "EvidenceReference")

    def verify_against(self, item: EvidenceItem) -> None:
        """Raise EvidenceBindingError unless ``item`` is the evidence this
        reference points at (same id, source and locator), and, for a
        claim-bound reference, CircularEvidenceError if the item is a
        restatement of that very claim (``check_not_circular``).  Pure: no
        registry, the caller supplies the item.  Says nothing about
        whether the item supports or refutes anything.  A criterion-only
        reference has no claim to test, so the claim-scoped guard cannot
        apply to it."""
        if item.evidence_id != self.evidence_id:
            raise EvidenceBindingError(
                f"reference points at evidence {self.evidence_id!r}, "
                f"got item {item.evidence_id!r}"
            )
        if item.source != self.source:
            raise EvidenceBindingError(
                f"reference source {self.source!r} does not match "
                f"evidence {item.evidence_id!r} source {item.source!r}"
            )
        if item.locator != self.locator:
            raise EvidenceBindingError(
                f"reference locator {self.locator!r} does not match "
                f"evidence {item.evidence_id!r} locator {item.locator!r}"
            )
        if self.claim_id is not None:
            # Binding a claim to its own restatement is the circular route
            # check_not_circular exists to close; this record must not be a
            # way around it.
            check_not_circular(self.claim_id, item)


@dataclass(frozen=True)
class EvidenceObservation:
    """Binds evidence to an existing Observation by id
    (``Evidence -> ... -> Observation``, v1 §16).

    Deliberately carries NO authority, timestamp or directness of its
    own: the Observation's ObservationAuthority stays the single
    authority model, and the evidence's directness/timestamps stay on
    EvidenceItem.  This record only says *which* observation the
    evidence rests on and how completely that link is traceable.

    Only an Observation can be bound.  An Interpretation is a semantic
    reading of an Observation, not evidence (Observation -> Interpretation
    -> Claim vs Observation -> Evidence): ``verify_against`` rejects it.

    Not independently addressable -- no EvidenceObservationId."""
    evidence_id: EvidenceId
    observation_id: ObservationId
    provenance: ProvenanceCompleteness

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "EvidenceObservation.evidence_id")
        _require_text(self.observation_id, "EvidenceObservation.observation_id")

    def verify_against(self, observation: Observation) -> None:
        """Raise unless ``observation`` is the Observation this record
        binds.  Pure: no registry, the caller supplies the object."""
        if not isinstance(observation, Observation):
            raise TypeError(
                f"only an Observation can be bound as evidence provenance; "
                f"got {type(observation).__name__} (an Interpretation is "
                f"not evidence)"
            )
        if observation.observation_id != self.observation_id:
            raise EvidenceBindingError(
                f"record binds observation {self.observation_id!r}, "
                f"got {observation.observation_id!r}"
            )


class TransformationType(str, Enum):
    """Categories of evidence transformation (IMPLEMENTATION JUDGMENT).
    The architecture names examples (summarized, translated, normalized,
    OCR'd, extracted, parsed, redacted) but does not prescribe a closed
    vocabulary.  MODEL_INTERPRETATION is added because v1 §16 names model
    summaries explicitly."""
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
    """Reconstructable lineage for derived evidence (v2 §14):
    ``source evidence -> type -> version -> producer -> derived evidence``.

    Enforced, using only categorical rules (no ordering of
    EvidenceDirectness is assumed anywhere):

      1. Lineage is complete: non-empty version and producer; source and
         derived evidence are distinct.
      2. Directness is never upgraded *into* DIRECT (v1 §16, v2 §14): a
         non-DIRECT source cannot yield a DIRECT result.
      3. MODEL_INTERPRETATION is permanent (v1 §16: "permanently reads
         MODEL_INTERPRETATION, never silently upgraded"): a
         MODEL_INTERPRETATION source, or a MODEL_INTERPRETATION-type
         transformation, can only yield a MODEL_INTERPRETATION result.
      4. Provenance is never silently completed: a source whose
         provenance is not COMPLETE cannot yield a COMPLETE result.

    Deliberately NOT enforced -- left to evidence construction /
    assessment, because the frozen architecture gives no categorical
    table for it:
      * DIRECT -> DIRECT through a non-model transformation is accepted.
        Whether a given redaction/normalization "justifies" keeping DIRECT
        (v2 §14) is a judgment this record cannot make from its fields.
      * Transitions among INDIRECT / DERIVED / MODEL_INTERPRETATION other
        than rule 3 are not compared (that would require an ordering).
      * Authority, integrity and certainty: no such fields exist here.

    ``verify_against`` additionally proves the recorded directness and ids
    match the two concrete EvidenceItems, so the rules above apply to the
    real evidence and not merely to what the record says about it.

    Not independently addressable -- no TransformationId."""
    source_evidence_id: EvidenceId
    source_directness: EvidenceDirectness
    source_provenance: ProvenanceCompleteness
    transformation_type: TransformationType
    transformation_version: str
    transformation_producer: str
    result_evidence_id: EvidenceId
    result_directness: EvidenceDirectness
    result_provenance: ProvenanceCompleteness

    def __post_init__(self) -> None:
        _require_text(self.source_evidence_id, "EvidenceTransformation.source_evidence_id")
        _require_text(self.result_evidence_id, "EvidenceTransformation.result_evidence_id")
        _require_text(
            self.transformation_version,
            "EvidenceTransformation.transformation_version",
        )
        _require_text(
            self.transformation_producer,
            "EvidenceTransformation.transformation_producer",
        )
        if self.source_evidence_id == self.result_evidence_id:
            raise ValueError(
                "EvidenceTransformation source and result must be distinct "
                "evidence objects -- a transformation that maps evidence to "
                "itself is not a transformation"
            )
        if (self.source_directness != EvidenceDirectness.DIRECT
                and self.result_directness == EvidenceDirectness.DIRECT):
            raise ValueError(
                f"transformation safety violation: source evidence has "
                f"directness={self.source_directness.value!r}, so derived "
                f"evidence cannot be DIRECT"
            )
        model = EvidenceDirectness.MODEL_INTERPRETATION
        if ((self.source_directness == model
                or self.transformation_type == TransformationType.MODEL_INTERPRETATION)
                and self.result_directness != model):
            raise ValueError(
                f"transformation safety violation: a model interpretation is "
                f"permanent -- result directness must stay "
                f"{model.value!r}, got {self.result_directness.value!r}"
            )
        if (self.source_provenance != ProvenanceCompleteness.COMPLETE
                and self.result_provenance == ProvenanceCompleteness.COMPLETE):
            raise ValueError(
                f"transformation safety violation: source provenance is "
                f"{self.source_provenance.value!r}; derived evidence cannot "
                f"claim COMPLETE provenance"
            )

    def verify_against(self, source: EvidenceItem, result: EvidenceItem) -> None:
        """Raise EvidenceBindingError unless the two items are the ones
        this record describes (ids and recorded directness match)."""
        if source.evidence_id != self.source_evidence_id:
            raise EvidenceBindingError(
                f"record source is {self.source_evidence_id!r}, "
                f"got item {source.evidence_id!r}"
            )
        if result.evidence_id != self.result_evidence_id:
            raise EvidenceBindingError(
                f"record result is {self.result_evidence_id!r}, "
                f"got item {result.evidence_id!r}"
            )
        if source.directness != self.source_directness:
            raise EvidenceBindingError(
                f"record says source directness is "
                f"{self.source_directness.value!r} but the item is "
                f"{source.directness.value!r}"
            )
        if result.directness != self.result_directness:
            raise EvidenceBindingError(
                f"record says result directness is "
                f"{self.result_directness.value!r} but the item is "
                f"{result.directness.value!r}"
            )


@dataclass(frozen=True)
class EvidenceBundle:
    """The evidence actually bound to one assessment (v2 §13), held as the
    EvidenceItems themselves so each item's own EvidenceStatus
    (UNAVAILABLE / INVALID / IRRELEVANT / INSUFFICIENT / SUFFICIENT /
    CONTRADICTORY), directness and source stay attached.  Nothing is
    filtered, resolved, averaged or overridden here, and order is kept.

    Bundle membership implies NOTHING: not truth, support, refutation,
    verification, whole-verification sufficiency, or a verdict.  An item
    need not even list the bound claim in ``supports_claim_ids``.
    Assessment and aggregation are later-layer responsibilities, and this
    type deliberately offers no method that decides any of them.

    Structural rules: immutable tuple; at least one item (an empty bundle
    is indistinguishable from missing evidence, and missing evidence is
    never proof of absence); unique evidence_ids; a claim and/or criterion
    binding; and, for a bound claim, the existing ``check_not_circular``
    guard is applied to every member, so this type cannot be a route
    around it.  A criterion-only bundle has no claim to test, so the
    claim-scoped guard cannot apply to it.

    Not independently addressable in this phase -- no bundle id."""
    items: Tuple[EvidenceItem, ...]
    claim_id: Optional[ClaimId] = None
    criterion_id: Optional[CriterionId] = None

    def __post_init__(self) -> None:
        _require_unique_tuple(self.items, "EvidenceBundle.items")
        _require_binding(self.claim_id, self.criterion_id, "EvidenceBundle")
        for item in self.items:
            if not isinstance(item, EvidenceItem):
                raise TypeError(
                    f"EvidenceBundle.items must contain EvidenceItem; "
                    f"got {type(item).__name__}"
                )
        ids = [item.evidence_id for item in self.items]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(
                f"EvidenceBundle contains duplicate evidence_ids: {dupes!r}"
            )
        if self.claim_id is not None:
            for item in self.items:
                check_not_circular(self.claim_id, item)

    @property
    def evidence_ids(self) -> Tuple[EvidenceId, ...]:
        return tuple(item.evidence_id for item in self.items)


@dataclass(frozen=True)
class MinimumSufficientEvidence:
    """Declarative retention/auditability requirement (v2 §44): the
    evidence that must remain retrievable so the decision on a claim
    and/or criterion can be reconstructed and audited -- "retain enough
    to reconstruct the decision, not everything that was ever touched".

    A REQUIREMENT, not a result.  It is not a count floor (that is
    rubric.CriterionEvidenceRequirement, which this type does not
    duplicate), not an EvidenceStatus, not a score, and never promotes a
    bundle to verified.  It is status-blind on purpose: reconstructing a
    decision may require CONTRADICTORY or INSUFFICIENT evidence, so being
    "required for audit" says nothing about being "sufficient".

    Field layout is IMPLEMENTATION JUDGMENT: v2 §44 names the concept and
    its purpose only.  NOT represented yet (needs metadata this batch does
    not carry): privacy exposure, storage/replay cost.  Pruning lifetime
    stays with EvidenceRetention (retention.py).

    Not independently addressable -- no MinimumSufficientEvidenceId."""
    required_evidence_ids: Tuple[EvidenceId, ...]
    claim_id: Optional[ClaimId] = None
    criterion_id: Optional[CriterionId] = None

    def __post_init__(self) -> None:
        _require_unique_tuple(
            self.required_evidence_ids, "MinimumSufficientEvidence.required_evidence_ids"
        )
        _require_binding(self.claim_id, self.criterion_id, "MinimumSufficientEvidence")
        for eid in self.required_evidence_ids:
            _require_text(eid, "MinimumSufficientEvidence.required_evidence_ids entry")
        if len(self.required_evidence_ids) != len(set(self.required_evidence_ids)):
            raise ValueError(
                "MinimumSufficientEvidence.required_evidence_ids contains duplicates"
            )

    def verify_against(self, bundle: EvidenceBundle) -> None:
        """Raise EvidenceBindingError unless ``bundle`` is bound to the
        same claim/criterion and actually contains every required item.
        Pure containment check -- no scoring, no sufficiency judgment."""
        if self.claim_id is not None and bundle.claim_id != self.claim_id:
            raise EvidenceBindingError(
                f"requirement is for claim {self.claim_id!r}, bundle is bound "
                f"to {bundle.claim_id!r}"
            )
        if self.criterion_id is not None and bundle.criterion_id != self.criterion_id:
            raise EvidenceBindingError(
                f"requirement is for criterion {self.criterion_id!r}, bundle "
                f"is bound to {bundle.criterion_id!r}"
            )
        missing = [e for e in self.required_evidence_ids if e not in bundle.evidence_ids]
        if missing:
            raise EvidenceBindingError(
                f"bundle lacks required evidence {missing!r} -- the decision "
                f"could not be reconstructed from it"
            )
