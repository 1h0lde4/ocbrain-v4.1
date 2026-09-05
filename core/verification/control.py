"""
Golden-corpus control cases -- extends G-0001 (v2 section 38), per
architecture v3 Part 1 section 8.

Adds control_type to the corpus: positive / negative / ambiguous /
partial / adversarial. The load-bearing invariant this file enforces
structurally, not just documents: abstention (an UNVERIFIABLE-shaped
verdict) on an AMBIGUOUS or PARTIAL control case is the CORRECT expected
outcome, not a defect. Without ambiguous/partial controls in the corpus,
a verifier that never abstains can look artificially better than one
that abstains appropriately -- this is v3's own stated reason this
taxonomy exists at all, and G-0001 (KNOWN_ISSUES.md's August 12 false-
verification incident) is exactly the failure mode a well-populated
corpus of this shape is meant to catch in the other direction: a
verifier that should have abstained but instead asserted PASS.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ControlType(str, Enum):
    POSITIVE = "positive"          # correct behavior: verify TRUE/PASS
    NEGATIVE = "negative"          # correct behavior: verify FALSE/FAIL
    AMBIGUOUS = "ambiguous"        # correct behavior: abstain
    PARTIAL = "partial"            # correct behavior: a partial/incomplete verdict
    ADVERSARIAL = "adversarial"    # designed to probe a specific failure mode (e.g. injection)


@dataclass(frozen=True)
class ControlCase:
    """One golden-corpus case, extending G-0001 (v2 section 38) with control_type.

    expected_abstention: for AMBIGUOUS/PARTIAL cases, True means abstaining
    IS the case passing, not failing. A scoring harness that doesn't check
    this will mark an appropriately-cautious verifier wrong for behaving
    correctly -- see this module's docstring.
    """
    case_id: str
    control_type: ControlType
    description: str
    expected_abstention: bool = False

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("ControlCase.case_id must be non-empty")
        if not self.description:
            raise ValueError("ControlCase.description must be non-empty")
        if self.control_type in (ControlType.POSITIVE, ControlType.NEGATIVE) and self.expected_abstention:
            raise ValueError(
                f"ControlCase {self.case_id}: control_type={self.control_type.value} "
                "should have a determinate expected verdict, not expected_abstention=True -- "
                "only AMBIGUOUS/PARTIAL cases legitimately expect abstention"
            )
