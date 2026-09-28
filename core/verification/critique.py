"""
Critique / Contradiction / CounterArgument (v1.md Sec18, unchanged into
v2-frozen.md Sec16 except one addition already covered by evidence.py's
existing circular-evidence check; v1.md Sec42; Phase 5). Implements the
design confirmed in
docs/architecture/verification-critic-evidence-system-finding-critique-design-proposal.md.
See that document for the reasoning; this module doesn't re-derive it.

v1.md Sec18, verbatim: "A disconfirmation engine, structurally separate
from both the generator and the verdict-maker... A critique is an input
to verification, not a verdict -- Critique != VerificationResult !=
Verdict, three different objects." The nine-value taxonomy below is
that section's literal output list, not re-derived.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .identity import (
    AssumptionId,
    ClaimId,
    ContradictionId,
    CounterArgumentId,
    CritiqueId,
    ObservationId,
)


class CritiqueFindingType(str, Enum):
    """v1.md Sec18's nine named disconfirmation-engine outputs, taken
    verbatim. Three of the nine reference a dedicated structured type
    (see Critique's __post_init__ below) rather than staying a bare
    label; the other six intentionally do not -- nothing in v1/v2 calls
    for more than a description on those six, and inventing structure
    for them here would be scope this design pass wasn't asked for."""
    UNSUPPORTED_CLAIM = "unsupported_claim"
    MISSING_EVIDENCE = "missing_evidence"
    HIDDEN_ASSUMPTION = "hidden_assumption"
    LOGIC_GAP = "logic_gap"
    CONTRADICTION = "contradiction"
    SCOPE_VIOLATION = "scope_violation"
    FALSE_COMPLETION = "false_completion"
    WRONG_ATTRIBUTION = "wrong_attribution"
    POSSIBLE_COUNTEREXAMPLE = "possible_counterexample"


@dataclass(frozen=True)
class Contradiction:
    """Claim-vs-claim, not claim-vs-evidence -- evidence conflicting
    with a claim is already expressible as "the evidence supports a
    different claim that conflicts with this one" via claim.py's
    existing ClaimOrigin.INTERPRETED_OBSERVATION chain, so this type
    keeps one comparison shape rather than two."""
    contradiction_id: ContradictionId
    first_claim_id: ClaimId
    second_claim_id: ClaimId
    description: str

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("Contradiction requires a non-empty description")
        if self.first_claim_id == self.second_claim_id:
            raise ValueError(
                "Contradiction requires two distinct claims -- a claim "
                "cannot contradict itself (that's evidence.py's existing "
                "circular-evidence check, a different problem)"
            )


@dataclass(frozen=True)
class CounterArgument:
    """Deliberately weaker than Contradiction: doesn't assert the
    target claim is false, only that a plausible alternative exists
    that would undermine it if true -- matching POSSIBLE_COUNTEREXAMPLE's
    own name (possible, not proven) against CONTRADICTION's flat
    assertion of conflict."""
    counter_argument_id: CounterArgumentId
    target_claim_id: ClaimId
    alternative_explanation: str
    supporting_observation_ids: Tuple[ObservationId, ...] = ()

    def __post_init__(self) -> None:
        if not self.alternative_explanation or not self.alternative_explanation.strip():
            raise ValueError("CounterArgument requires a non-empty alternative_explanation")


@dataclass(frozen=True)
class Critique:
    critique_id: CritiqueId
    finding_type: CritiqueFindingType
    target_claim_id: ClaimId
    description: str
    contradiction_id: Optional[ContradictionId] = None
    counter_argument_id: Optional[CounterArgumentId] = None
    hidden_assumption_id: Optional[AssumptionId] = None

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("Critique requires a non-empty description")
        self._require_iff(CritiqueFindingType.CONTRADICTION, self.contradiction_id, "contradiction_id")
        self._require_iff(CritiqueFindingType.POSSIBLE_COUNTEREXAMPLE, self.counter_argument_id, "counter_argument_id")
        self._require_iff(CritiqueFindingType.HIDDEN_ASSUMPTION, self.hidden_assumption_id, "hidden_assumption_id")

    def _require_iff(self, required_for: CritiqueFindingType, value: object, field_name: str) -> None:
        if self.finding_type is required_for and value is None:
            raise ValueError(
                f"Critique with finding_type={required_for.value!r} must "
                f"reference {field_name}"
            )
        if self.finding_type is not required_for and value is not None:
            raise ValueError(
                f"{field_name} is only meaningful for "
                f"finding_type={required_for.value!r}, not "
                f"{self.finding_type.value!r}"
            )
