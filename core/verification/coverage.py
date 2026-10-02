"""
core/verification/coverage.py -- Batch 3B: the five coverage types (v2 §13).

v2 §13: "Coverage is five separate fields, not one. TaskCoverage,
VerificationCoverage, CriterionCoverage, EvidenceCoverage, ObservationCoverage
coexist independently -- TaskCoverage=100% with VerificationCoverage=40% must
be representable without contradiction, and this is the concrete architectural
guard against ... task completeness silently becoming verification
completeness."

So this module deliberately does NOT provide:

* a shared Coverage base class or a generic "coverage" type (the five types
  share no base, so nothing can accept "any coverage" and quietly swap one for
  another);
* any container, aggregate, minimum, average or "overall" coverage;
* any validation of one coverage against another (a task at 1.0 with a
  verification at 0.4 is valid, and so is every other combination);
* any relationship to ``VerificationAssurance.coverage`` -- that field is a
  separate, already-built contract and no equivalence with
  ``VerificationCoverage`` is defined or implied here.

What the architecture does not define is left to the caller: it names the five
quantities but not their denominators.  Each value therefore carries a
required ``scope`` saying what the fraction is *of* (the same idea as
``VerificationAssurance.assurance_scope``).  The descriptions on each type
below are IMPLEMENTATION JUDGMENT, not frozen architecture.

Unknown is not zero: ``fraction=None`` means the coverage is unknown.  It has
no default, so "unknown" must be stated, never reached by omission, and it is
never coerced to 0.0 or 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def _validate_coverage(owner: str, fraction: Optional[float], scope: str) -> None:
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError(
            f"{owner}.scope must be a non-empty string -- a coverage fraction "
            f"is meaningless without saying what it is a fraction of"
        )
    if fraction is None:
        return  # unknown: deliberately valid, deliberately not a number
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
        raise TypeError(
            f"{owner}.fraction must be a number in [0, 1] or None (unknown), "
            f"got {type(fraction).__name__}"
        )
    if not (0.0 <= fraction <= 1.0):  # also rejects NaN
        raise ValueError(f"{owner}.fraction must be in [0.0, 1.0], got {fraction!r}")


@dataclass(frozen=True)
class TaskCoverage:
    """How much of the *task* is complete, by the task's own definition of
    completeness.  Not a statement about how much has been verified."""

    fraction: Optional[float]
    scope: str

    def __post_init__(self) -> None:
        _validate_coverage("TaskCoverage", self.fraction, self.scope)


@dataclass(frozen=True)
class VerificationCoverage:
    """How much of what needs verifying has actually been verified.  Not
    task completeness, and not (by any defined equivalence)
    ``VerificationAssurance.coverage``."""

    fraction: Optional[float]
    scope: str

    def __post_init__(self) -> None:
        _validate_coverage("VerificationCoverage", self.fraction, self.scope)


@dataclass(frozen=True)
class CriterionCoverage:
    """How much of the rubric's criteria have been evaluated."""

    fraction: Optional[float]
    scope: str

    def __post_init__(self) -> None:
        _validate_coverage("CriterionCoverage", self.fraction, self.scope)


@dataclass(frozen=True)
class EvidenceCoverage:
    """How much of the evidence that was needed has been obtained."""

    fraction: Optional[float]
    scope: str

    def __post_init__(self) -> None:
        _validate_coverage("EvidenceCoverage", self.fraction, self.scope)


@dataclass(frozen=True)
class ObservationCoverage:
    """How much of the relevant observation surface has actually been
    observed.  A quantity, like the other four -- distinct from
    ``ObservationAbsenceState`` (core/verification/absence.py), which is the
    four-state vocabulary v1 §21 headlines "Observation Coverage"."""

    fraction: Optional[float]
    scope: str

    def __post_init__(self) -> None:
        _validate_coverage("ObservationCoverage", self.fraction, self.scope)
