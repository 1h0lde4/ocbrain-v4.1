"""
Evidence contracts, including the circular-evidence structural check
(architecture v2 Part 2 §17): evidence that is merely an unsupported
restatement of its own claim must be structurally rejected -- this is
a property of the claim/evidence graph, checked mechanically, not an
LLM judgment call.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Tuple

from .identity import EvidenceId, ClaimId


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
