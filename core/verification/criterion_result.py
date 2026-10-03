"""
core/verification/criterion_result.py -- Batch 3C-A: CriterionResult.

What the frozen architecture says (and how little of it there is):

* ``CriterionResult`` is *named* in v1 §13 / v2 §9 and in the v1 §42 contract
  list.  No fields, no vocabulary and no invariants are given.
* v1 §13 says the rubric architecture mirrors a "category-level (not
  aggregate)" scoring precedent: a criterion result is per criterion.
* v2 §19 keeps criterion logic (AND / OR / conditional / dependency), evidence
  aggregation and verifier aggregation as three separate layers and forbids
  collapsing them into one weighted average.  v2 §21 requires that
  ``task_incomplete + some_criteria_verified`` and its relatives stay
  representable without collapsing into each other.
* v1 §25 / mission §50 / ``verdict.py``: a verifier crash can never become a
  positive verdict.

So this is a LOCAL result contract: what was concluded about ONE criterion, as
produced by some later layer.  It is not an aggregation engine, not an
execution-state accumulator and not a receipt.  It is built to be composable
into future coverage / aggregation / ``VerifiedState`` views, and it does not
perform or own any of them.

Everything below that is not stated in the sources above is IMPLEMENTATION
JUDGMENT, marked as such:

* the field set;
* ``CriterionAttemptState`` and its namespaced string values;
* what ATTEMPTED / NOT_ATTEMPTED / BLOCKED mean;
* binding a result to a rubric by ``rubric_fingerprint``;
* ``finding_ids`` as optional references.

Deliberately NOT here:

* any computation of a verdict: no AND / OR, no majority, no weighted average,
  no worst-of, no "overall".  A verdict stored here was declared by the layer
  that produced it; this type only refuses states that contradict themselves;
* scores, confidence, uncertainty, ``VerificationAssurance`` -- a criterion that
  was never inspected has no assurance to state, and forcing one is exactly the
  fabrication this design avoids;
* coverage of any kind -- ``CriterionCoverage`` is a rubric-level quantity;
* provenance / lineage / receipt / execution / attempt identity;
* truth or decision status (v1 §25 keeps those as separate fields);
* process / outcome results and ``failure_control`` (Batch 3C-B, blocked pending
  architecture reconciliation);
* ``SKIPPED`` -- no source defines it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .identity import CriterionId, VerificationFindingId
from .verdict import VerificationExecutionFailure, VerificationVerdict


class CriterionAttemptState(str, Enum):
    """Whether a criterion was evaluated at all.  IMPLEMENTATION JUDGMENT.

    This is the criterion-level axis the earlier planning notes asked for.  A
    method-level axis already exists (``MethodExecutionState``) and answers a
    different question -- what happened when one *method* was invoked.

    - NOT_ATTEMPTED: no evaluation of the criterion took place.  There is no
      verdict, and the absence of one must never be read as a positive result.
    - BLOCKED: evaluation could not begin.  No verdict.  What blocks it is not
      defined here, and ``CriterionDependencyType.BLOCKS`` is deliberately not
      wired to this state: the architecture does not say how the two relate.
    - ATTEMPTED: an evaluation took place and the producing layer states its
      verdict.  That includes ``NOT_APPLICABLE`` (deciding that a criterion does
      not apply is an evaluation), ``INSUFFICIENT_EVIDENCE`` and
      ``UNVERIFIABLE``.  An attempt that could not be established is stated as
      one of those fail-closed verdicts, never as "no verdict".

    No ordering is intended: ATTEMPTED is not "greater" than BLOCKED.  (As with
    every ``str`` enum, Python compares members as strings; that order carries
    no meaning.)

    The string values are namespaced (``criterion_*``) on purpose.  This is a
    ``str`` enum, so a member compares equal to any other ``str`` enum member
    with the same value: ``"blocked"`` and ``"not_run"`` are already taken by
    ``MethodExecutionState``, and sharing them would make the two enums compare
    equal and collide as dict keys or set members.

    There is deliberately no SKIPPED: no source defines it.
    """
    NOT_ATTEMPTED = "criterion_not_attempted"
    BLOCKED = "criterion_blocked"
    ATTEMPTED = "criterion_attempted"


@dataclass(frozen=True)
class CriterionResult:
    """What was concluded about one criterion.  Immutable.

    Invariants (each is enforced here, not just documented):

    1. ``attempt_state`` is a ``CriterionAttemptState``; ``verdict`` is a
       ``VerificationVerdict`` or ``None``.  Nothing else is accepted, and
       nothing is coerced (a finding disposition, a construct-validity status,
       a method disposition or a bare string is rejected).
    2. ATTEMPTED  -> ``verdict`` is required.  There is no "attempted but no
       verdict" state; an attempt that cannot be established carries a
       fail-closed verdict such as INSUFFICIENT_EVIDENCE or UNVERIFIABLE.
    3. NOT_ATTEMPTED / BLOCKED -> ``verdict`` is None.  An unevaluated
       criterion has no verdict to carry.
    4. ``execution_failure`` is only valid on an ATTEMPTED result whose verdict
       is UNVERIFIABLE (the rule ``VerificationResult`` already enforces): a
       verifier crash, timeout or exhausted budget can never become a pass.
       The reverse is not required -- UNVERIFIABLE without a failure is valid.

    ``verdict`` has no default, so "no verdict" must be stated
    (``verdict=None``), never reached by omission.

    ``rubric_fingerprint`` -- IMPLEMENTATION JUDGMENT, not an architectural
    requirement.  It refers to the rubric the criterion belongs to by *value*,
    exactly as ``ConstructValidity`` does, so a result cannot be silently
    re-attached to a different rubric version.  It holds no ``Rubric`` and takes
    no part in any rubric's identity.

    ``finding_ids`` -- IMPLEMENTATION JUDGMENT.  Optional references to the
    ``VerificationFinding`` records behind the result.  Not required: the
    architecture does not establish that every valid criterion result must
    have findings (an UNVERIFIABLE result after a crash has none), so an empty
    tuple is valid in every state and asserts nothing.  The ids are not checked
    against real findings here, and no relation between findings and
    ``attempt_state`` is imposed.

    There is deliberately no score, confidence, assurance, coverage,
    provenance, lineage, receipt or execution identity, and no behaviour: no
    method on this type computes anything from anything.
    """
    criterion_id: CriterionId
    rubric_fingerprint: str
    attempt_state: CriterionAttemptState
    verdict: Optional[VerificationVerdict]
    execution_failure: Optional[VerificationExecutionFailure] = None
    finding_ids: Tuple[VerificationFindingId, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.criterion_id, str) or not self.criterion_id.strip():
            raise ValueError("CriterionResult requires a non-empty criterion_id")
        if not isinstance(self.rubric_fingerprint, str) or not self.rubric_fingerprint.strip():
            raise ValueError("CriterionResult requires a non-empty rubric_fingerprint")
        if not isinstance(self.attempt_state, CriterionAttemptState):
            raise TypeError(
                f"CriterionResult.attempt_state must be a CriterionAttemptState, "
                f"got {type(self.attempt_state).__name__} -- a verdict, a method "
                f"execution state or a bare string is never coerced"
            )
        if self.verdict is not None and not isinstance(self.verdict, VerificationVerdict):
            raise TypeError(
                f"CriterionResult.verdict must be a VerificationVerdict or None, "
                f"got {type(self.verdict).__name__} -- a finding disposition, a "
                f"validity status or a bare string is never coerced"
            )
        if self.execution_failure is not None and not isinstance(
            self.execution_failure, VerificationExecutionFailure
        ):
            raise TypeError(
                f"CriterionResult.execution_failure must be a "
                f"VerificationExecutionFailure or None, "
                f"got {type(self.execution_failure).__name__}"
            )
        if self.attempt_state is CriterionAttemptState.ATTEMPTED:
            if self.verdict is None:
                raise ValueError(
                    "an ATTEMPTED criterion requires a verdict -- an attempt that "
                    "cannot be established is INSUFFICIENT_EVIDENCE or UNVERIFIABLE, "
                    "never 'no verdict'"
                )
        elif self.verdict is not None:
            raise ValueError(
                f"a {self.attempt_state.name} criterion cannot carry a verdict -- "
                f"a criterion that was not evaluated has nothing to conclude"
            )
        if self.execution_failure is not None and (
            self.attempt_state is not CriterionAttemptState.ATTEMPTED
            or self.verdict is not VerificationVerdict.UNVERIFIABLE
        ):
            raise ValueError(
                "an execution failure belongs to an ATTEMPTED criterion and must "
                "produce UNVERIFIABLE, never a positive verdict -- a verifier crash "
                "cannot become PASS"
            )
        if not isinstance(self.finding_ids, tuple):
            raise TypeError(
                f"CriterionResult.finding_ids must be a tuple, "
                f"got {type(self.finding_ids).__name__}"
            )
        for finding_id in self.finding_ids:
            if not isinstance(finding_id, str):
                raise TypeError(
                    f"CriterionResult.finding_ids entries must be strings, "
                    f"got {type(finding_id).__name__}"
                )
            if not finding_id.strip():
                raise ValueError("CriterionResult.finding_ids entries must be non-empty")
