"""
core/verification/absence.py -- Batch 3B: observation-absence states.

v1 §21 / v2 §13: ``NOT_OBSERVED`` / ``OBSERVED_ABSENT`` /
``OBSERVATION_INCOMPLETE`` / ``OBSERVATION_COVERAGE_UNKNOWN``, kept distinct.
"Absence is never inferred from silence": ``OBSERVED_ABSENT`` "may only be
emitted when (1) the relevant surface was actually inspected, (2) the
observing mechanism was authorized for that surface (§16), and (3) coverage
was sufficient.  Otherwise: NOT_OBSERVED / OBSERVATION_INCOMPLETE /
OBSERVATION_COVERAGE_UNKNOWN."

What is architecture and what is judgment here:

* The four states and the three prerequisites are v2 §13 / v1 §21.
* ``coverage_sufficient`` is a boolean *declared by the producing layer*.
  The architecture says "sufficient" without defining it, and 3B adds no
  numeric threshold.  This contract therefore enforces consistency (an
  OBSERVED_ABSENT record cannot exist unless all three prerequisites are
  declared true); it cannot check that the declaration is honest.
* The names ``ObservationAbsenceState`` and ``ObservationAbsence`` are
  IMPLEMENTATION JUDGMENT.  The state enum is named apart from
  ``ObservationCoverage`` (a quantity, in coverage.py) because v1 §21 uses
  "Observation Coverage" for these states while v2 §13 uses
  ``ObservationCoverage`` for one of five quantities.

Not here: VerificationObservation (named in the architecture, never defined),
any link between these records and the coverage quantities, any state-specific
rule beyond the OBSERVED_ABSENT gate (the frozen text imposes none), scoring,
confidence, verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .epistemic import InspectionAuthorization


class ObservationAbsenceState(str, Enum):
    """Whether, and how well, something was looked for.

    Only OBSERVED_ABSENT asserts that the thing is not there; the other three
    are explicitly *not* assertions of absence.  There is no ordering and no
    default.
    """

    NOT_OBSERVED = "not_observed"
    OBSERVED_ABSENT = "observed_absent"
    OBSERVATION_INCOMPLETE = "observation_incomplete"
    OBSERVATION_COVERAGE_UNKNOWN = "observation_coverage_unknown"


@dataclass(frozen=True)
class ObservationAbsence:
    """One statement about looking at one surface.

    Invariant (v2 §13): ``state`` may be OBSERVED_ABSENT only if the surface
    was inspected (``inspected is True``), the mechanism was authorized for
    *this* surface (``inspection_authorization`` present, ``authorized is
    True``, same ``surface``), and the producer declared coverage sufficient
    (``coverage_sufficient is True``).  The check is strict identity with True,
    so a truthy non-bool never satisfies it.

    The other three states do not acquire any of these requirements: they are
    valid with every combination of the three facts, including no
    authorization information at all.  There are no defaults for ``state``,
    ``inspected`` or ``coverage_sufficient``, so absence can never be reached
    by omission.

    Authorization reuses the existing ``InspectionAuthorization`` contract
    (checked per surface, v2 §16); no second authorization model is introduced.
    """

    state: ObservationAbsenceState
    surface: str
    inspected: bool
    coverage_sufficient: bool
    inspection_authorization: Optional[InspectionAuthorization] = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ObservationAbsenceState):
            raise TypeError(
                f"ObservationAbsence.state must be an ObservationAbsenceState, "
                f"got {type(self.state).__name__}"
            )
        if not isinstance(self.surface, str) or not self.surface.strip():
            raise ValueError("ObservationAbsence.surface must be a non-empty string")
        if not isinstance(self.inspected, bool):
            raise TypeError(
                f"ObservationAbsence.inspected must be a bool, got "
                f"{type(self.inspected).__name__}"
            )
        if not isinstance(self.coverage_sufficient, bool):
            raise TypeError(
                f"ObservationAbsence.coverage_sufficient must be a bool, got "
                f"{type(self.coverage_sufficient).__name__}"
            )
        auth = self.inspection_authorization
        if auth is not None and not isinstance(auth, InspectionAuthorization):
            raise TypeError(
                f"ObservationAbsence.inspection_authorization must be an "
                f"InspectionAuthorization or None, got {type(auth).__name__}"
            )

        if self.state is ObservationAbsenceState.OBSERVED_ABSENT:
            missing: list[str] = []
            if self.inspected is not True:
                missing.append("the surface was not inspected")
            if auth is None:
                missing.append("no inspection authorization is recorded")
            elif auth.authorized is not True:
                missing.append("inspection was not authorized")
            elif auth.surface != self.surface:
                missing.append(
                    f"the authorization is for surface {auth.surface!r}, "
                    f"not {self.surface!r}"
                )
            if self.coverage_sufficient is not True:
                missing.append("coverage was not declared sufficient")
            if missing:
                raise ValueError(
                    "OBSERVED_ABSENT requires an inspected surface, authorized "
                    "inspection of that surface, and sufficient coverage "
                    "(absence is never inferred from silence): "
                    + "; ".join(missing)
                )
