"""
VerificationFinding (v1.md Sec42; v2-frozen.md Sec11; Phase 5). Implements
the design confirmed in
docs/architecture/verification-critic-evidence-system-finding-critique-design-proposal.md.
See that document for the reasoning; this module doesn't re-derive it.

v2-frozen.md Sec11, verbatim: "DeterministicVerifier is a method.
ProcessVerification is a dimension... a single dimension can be checked
by multiple methods, and a single method can serve multiple dimensions.
Phase C contracts should model these as two independent classifications
on a VerificationFinding, not a nested hierarchy." That sentence is this
module's entire design for the method/dimension field pair.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from .dimension import VerificationDimension
from .identity import CriterionId, ObservationId, VerificationFindingId, VerificationMethodId


class FindingDisposition(str, Enum):
    """Whether a finding, once produced, supports or refutes the
    criterion it bears on. Deliberately separate from method.py's
    MethodDisposition (CONCLUSIVE/INCONCLUSIVE/INSUFFICIENT), which
    answers a different question (was the method's execution clean) --
    conflating the two was VerificationMethod Revision 1's core mistake,
    caught and fixed before implementation; this module doesn't repeat
    it. This is the "support/refute is derived later from the produced
    observation/evidence against the criterion" step that mistake's fix
    deferred to -- this is that later point."""
    SUPPORTS = "supports"
    REFUTES = "refutes"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class VerificationFinding:
    finding_id: VerificationFindingId
    criterion_id: CriterionId
    method_id: VerificationMethodId
    dimension: VerificationDimension
    disposition: FindingDisposition
    observation_ids: Tuple[ObservationId, ...]

    def __post_init__(self) -> None:
        if not self.observation_ids:
            raise ValueError(
                "VerificationFinding requires at least one observation_id "
                "-- a finding with no observation behind it is an "
                "unsupported assertion, not a finding"
            )
