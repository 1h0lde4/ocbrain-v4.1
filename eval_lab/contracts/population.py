"""eval_lab/contracts/population.py — sampling population and experiment design.

Implements ADR-LAB-05 and §48-50 of this Slice. `EvaluationPopulation` is
the concrete implementation of ADR-LAB-05 §2's central claim: "82% of
selected cases passed" must never silently become "82% overall capability"
-- because the population that produced the number is recorded as a first-
class object, not left implicit in whichever run IDs happened to get
queried later.

Correction pass: a request to type `MetricObservation.population_id` as a
dedicated `PopulationId` (result.py) surfaced that this module's own
`EvaluationPopulation.population_id` and `Experiment.population_id` were
still plain `str` -- the type that *owns* the population concept was
untyped while a *reference* to it was about to become typed, which is
backwards and would have left a fresh instance of the exact inconsistency
class fixed elsewhere in this branch's history. Both fixed here too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eval_lab.contracts.identifiers import EvaluationCaseId, ExperimentId, PopulationId
from eval_lab.contracts.serialization import ContractValidationError


@dataclass(frozen=True)
class EvaluationPopulation:
    """Per ADR-LAB-05 §2: sampling_frame, selection_method,
    selection_reason, included_cases, excluded_cases. `included_cases` and
    `excluded_cases` are disjoint by construction (validated below) --
    together with `sampling_frame`, a reader can reconstruct "what could
    have been selected" vs. "what was," per §50 of this Slice."""

    population_id: PopulationId
    sampling_frame_description: str
    """What the population was drawn from, e.g. "all VALIDATED cases in
    benchmark-v3" or "cases tagged 'planning' in the dev set.\""""
    selection_method: str
    selection_reason: str
    included_cases: frozenset[EvaluationCaseId]
    excluded_cases: frozenset[EvaluationCaseId] = field(default_factory=frozenset)
    risk_weighted: bool = False

    def __post_init__(self) -> None:
        overlap = self.included_cases & self.excluded_cases
        if overlap:
            raise ContractValidationError(
                "included_excluded_overlap",
                f"included_cases and excluded_cases must be disjoint; overlap: {sorted(overlap)}.",
            )
        if not self.included_cases:
            raise ContractValidationError(
                "population_requires_included_cases", "included_cases cannot be empty."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_id": self.population_id,
            "sampling_frame_description": self.sampling_frame_description,
            "selection_method": self.selection_method,
            "selection_reason": self.selection_reason,
            "included_cases": sorted(self.included_cases),
            "excluded_cases": sorted(self.excluded_cases),
            "risk_weighted": self.risk_weighted,
            "n_included": len(self.included_cases),
            "n_excluded": len(self.excluded_cases),
        }


@dataclass(frozen=True)
class Experiment:
    """Per ADR-LAB-05 §2/§49 of this Slice: metadata only, no statistics
    implemented. `stopping_rule` is required (not optional with a None
    default) -- deliberately, because ADR-LAB-05 §2 treats an
    undeclared stopping rule as *itself* the "run, look, run again, look,
    stop when favorable" failure mode, not a neutral default. Callers
    that genuinely have no stopping rule yet must say so explicitly
    (e.g. "none declared") rather than the field silently being absent."""

    experiment_id: ExperimentId
    hypothesis: str
    population_id: PopulationId
    comparison_family: str
    """Which other comparisons share this experiment's multiple-comparison
    budget -- per ADR-LAB-05 §2, this has to exist *before* any statistics
    are computed, not be added retroactively once someone wants a p-value."""
    stopping_rule: str
    variables: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    statistical_test: str | None = None
    confidence_level: float | None = None
    planned_n: int | None = None
    minimum_n: int | None = None
    maximum_n: int | None = None

    def __post_init__(self) -> None:
        if self.confidence_level is not None and not (0.0 < self.confidence_level < 1.0):
            raise ContractValidationError(
                "confidence_level_out_of_range", f"confidence_level must be in (0.0, 1.0), got {self.confidence_level}."
            )
        for name, val in (("planned_n", self.planned_n), ("minimum_n", self.minimum_n), ("maximum_n", self.maximum_n)):
            if val is not None and val < 0:
                raise ContractValidationError(f"negative_{name}", f"{name} cannot be negative.")
        if self.minimum_n is not None and self.maximum_n is not None and self.minimum_n > self.maximum_n:
            raise ContractValidationError(
                "minimum_n_exceeds_maximum_n", f"minimum_n ({self.minimum_n}) cannot exceed maximum_n ({self.maximum_n})."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis": self.hypothesis,
            "population_id": self.population_id,
            "comparison_family": self.comparison_family,
            "stopping_rule": self.stopping_rule,
            "variables": list(self.variables),
            "controls": list(self.controls),
            "statistical_test": self.statistical_test,
            "confidence_level": self.confidence_level,
            "planned_n": self.planned_n,
            "minimum_n": self.minimum_n,
            "maximum_n": self.maximum_n,
        }
