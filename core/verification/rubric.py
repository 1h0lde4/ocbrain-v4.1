"""
Rubric / Criterion contracts (architecture v1 §13, v2 §9, mission §14-16):
what gets checked, structured so a Rubric can be validated before it is
ever executed against real evidence.

Lock-state progression is strict single-step and forward-only
(DRAFT -> VALIDATED -> COMPILED -> LOCKED). A Rubric that needs to change
after validation gets a new version/fingerprint, not a state reversal --
the same "create new, never mutate history" discipline as
VerificationReceipt's supersession lineage in receipt.py.

Scope boundary, stated plainly rather than left implicit: what this
module validates is what is actually checkable today -- structural
duplication, self-dependency, phantom references, and dependency
cycles. Mission §15's full list (contradictory criteria, impossible
criteria, no evaluation path, invalid target/method combinations) needs
VerificationMethod and the remaining Evidence family members (Phase
4-5) to check for real; claiming to enforce those now would be exactly
the unsupported trust claim mission §107 asks this project not to make.

Reference, don't embed: Rubric.criteria holds CriterionId references,
not embedded Criterion objects -- matching policy.py's own established
pattern (VerificationRequirements.required_dimensions and friends).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from .evidence import EvidenceDirectness
from .identity import CriterionId, RubricId


class RubricValidationError(ValueError):
    """Raised when a rubric or its criteria fail a structural check."""


class CriterionDependencyCycleError(RubricValidationError):
    """Raised when CriterionDependency edges form a cycle."""


class RubricLockState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    COMPILED = "compiled"
    LOCKED = "locked"


_LOCK_STATE_ORDER: Tuple[RubricLockState, ...] = (
    RubricLockState.DRAFT,
    RubricLockState.VALIDATED,
    RubricLockState.COMPILED,
    RubricLockState.LOCKED,
)


class CriterionDependencyType(str, Enum):
    REQUIRES = "requires"  # depends_on_criterion_id must be evaluated first
    BLOCKS = "blocks"      # if depends_on_criterion_id fails, this criterion cannot be meaningfully evaluated


@dataclass(frozen=True)
class CriterionDependency:
    criterion_id: CriterionId
    depends_on_criterion_id: CriterionId
    dependency_type: CriterionDependencyType

    def __post_init__(self) -> None:
        if self.criterion_id == self.depends_on_criterion_id:
            raise RubricValidationError(
                f"criterion {self.criterion_id!r} cannot depend on itself"
            )


@dataclass(frozen=True)
class CriterionApplicability:
    """
    Whether a criterion applies to a given target at all. V1 supports
    only unconditional applicability or a human-readable condition -- a
    real predicate language is deferred to whenever VerificationMethod
    exists to evaluate one.
    """
    applies_unconditionally: bool
    condition_description: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.applies_unconditionally and not (
            self.condition_description and self.condition_description.strip()
        ):
            raise ValueError(
                "a conditional CriterionApplicability must describe its condition"
            )


@dataclass(frozen=True)
class CriterionEvidenceRequirement:
    """
    What a criterion needs before it can be evaluated. Deliberately
    narrower than the future MinimumSufficientEvidence (mission §28) --
    this states a floor, not a sufficiency policy.
    """
    minimum_evidence_items: int
    required_directness: Optional[EvidenceDirectness] = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.minimum_evidence_items < 0:
            raise ValueError("minimum_evidence_items cannot be negative")


@dataclass(frozen=True)
class Criterion:
    criterion_id: CriterionId
    rubric_id: RubricId
    description: str
    applicability: CriterionApplicability
    evidence_requirement: CriterionEvidenceRequirement

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("Criterion requires a non-empty description")


@dataclass(frozen=True)
class Rubric:
    rubric_id: RubricId
    version: str
    fingerprint: str
    created_from: str
    created_by: str
    derived_from: str
    source_requirements: Tuple[str, ...]
    context_basis: str
    criteria: Tuple[CriterionId, ...]
    lock_state: RubricLockState = RubricLockState.DRAFT
    # Placeholder for the future VerificationConstruct/ConstructValidity
    # (mission row 47) -- a plain string until that type exists, matching
    # policy.py's own established precedent for forward references to
    # not-yet-built taxonomies.
    construct_note: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.version or not self.version.strip():
            raise ValueError("Rubric requires a non-empty version")
        if not self.fingerprint or not self.fingerprint.strip():
            raise ValueError("Rubric requires a non-empty fingerprint")
        if not self.criteria:
            raise ValueError("Rubric requires at least one criterion")
        if len(self.criteria) != len(set(self.criteria)):
            raise RubricValidationError("Rubric lists a duplicate criterion_id")

    def can_advance_to(self, target: RubricLockState) -> bool:
        current_index = _LOCK_STATE_ORDER.index(self.lock_state)
        target_index = _LOCK_STATE_ORDER.index(target)
        return target_index == current_index + 1

    def advance_to(self, target: RubricLockState) -> "Rubric":
        if not self.can_advance_to(target):
            raise RubricValidationError(
                f"cannot advance Rubric {self.rubric_id!r} from "
                f"{self.lock_state.value!r} to {target.value!r} -- lock state "
                f"progression is strict single-step "
                f"DRAFT->VALIDATED->COMPILED->LOCKED"
            )
        return dataclasses.replace(self, lock_state=target)


def validate_dependency_graph(
    criteria: Sequence[Criterion],
    dependencies: Sequence[CriterionDependency],
) -> None:
    """
    Structural checks only (mission §15): every dependency references a
    criterion that actually exists in this set (no phantom references),
    and the dependency graph contains no cycles. Does not and cannot
    check semantic contradiction or impossibility -- see module docstring.
    """
    known_ids: FrozenSet[CriterionId] = frozenset(c.criterion_id for c in criteria)
    graph: Dict[CriterionId, List[CriterionId]] = {cid: [] for cid in known_ids}

    for dep in dependencies:
        if dep.criterion_id not in known_ids:
            raise RubricValidationError(
                f"CriterionDependency references unknown criterion_id "
                f"{dep.criterion_id!r} -- not present in this rubric's criteria"
            )
        if dep.depends_on_criterion_id not in known_ids:
            raise RubricValidationError(
                f"CriterionDependency for {dep.criterion_id!r} depends on "
                f"unknown criterion_id {dep.depends_on_criterion_id!r} -- "
                f"phantom dependency"
            )
        graph[dep.criterion_id].append(dep.depends_on_criterion_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[CriterionId, int] = {cid: WHITE for cid in known_ids}

    def visit(node: CriterionId, path: List[CriterionId]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in graph[node]:
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                raise CriterionDependencyCycleError(
                    "criterion dependency cycle detected: "
                    + " -> ".join(str(c) for c in cycle)
                )
            if color[neighbor] == WHITE:
                visit(neighbor, path)
        path.pop()
        color[node] = BLACK

    for cid in known_ids:
        if color[cid] == WHITE:
            visit(cid, [])
