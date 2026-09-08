"""
Inspection plan contracts (architecture v1 §14, mission §14): the bridge
between a compiled Criterion and the actual observations, queries,
tests, or retrieval calls that will be run to check it.

method_reference is a plain string, not a VerificationMethod object --
VerificationMethod does not exist yet (Phase 5). This follows the exact
precedent policy.py already established for the same forward-reference
problem (VerificationRequirements.required_dimensions,
VerificationStrategy.selected_methods), not a new pattern invented here.

Nothing in this module requires an LLM call to construct or validate --
v1 §14's own example ("an InspectionPlan for 'artifact X exists' is a
filesystem check") stays true in code, not just in the docstring.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .identity import CriterionId, InspectionPlanId, InspectionStepId, ObligationId


@dataclass(frozen=True)
class InspectionStep:
    step_id: InspectionStepId
    plan_id: InspectionPlanId
    method_reference: str
    description: str

    def __post_init__(self) -> None:
        if not self.method_reference or not self.method_reference.strip():
            raise ValueError("InspectionStep requires a non-empty method_reference")
        if not self.description or not self.description.strip():
            raise ValueError("InspectionStep requires a non-empty description")


@dataclass(frozen=True)
class InspectionPlan:
    plan_id: InspectionPlanId
    obligation_id: ObligationId
    criterion_id: CriterionId
    steps: Tuple[InspectionStepId, ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError(
                "InspectionPlan requires at least one step -- an obligation "
                "with no inspection path is a rubric-satisfiability failure "
                "(mission §16), not a valid empty plan"
            )
