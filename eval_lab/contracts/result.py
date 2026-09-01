"""eval_lab/contracts/result.py — result, aggregate, metric, comparison.

Implements §19, §27, §56-58 of this Slice. §19 is explicit that
EvaluationResult must not be overloaded to also mean "aggregated run
result" or "multi-run metric" or "experiment comparison" -- so this module
defines four separate types rather than one with optional fields for
everything, per §19's own critical invariant: "individual evidence/result
!= aggregate statistic != experiment comparison."

§56-57's evaluator-disagreement requirement (oracle=PASS, judge=FAIL,
human=PARTIAL, all held simultaneously, none overwriting another) is why
an EvaluationRun (run.py) holds a *tuple* of EvaluationResults rather than
one -- this module doesn't enforce that itself (that's run.py's job), but
EvaluationResult's own identity (evaluator_id + evaluator_version)
alongside a `chronology` timestamp and no "supersedes" field by default
is what makes holding several of them meaningful rather than ambiguous
about which one is "current."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from eval_lab.contracts.enums import ConfidenceLevel, EvaluatorResultStatus
from eval_lab.contracts.evidence import Evidence
from eval_lab.contracts.identifiers import (
    EvaluationRunId,
    EvaluatorId,
    EvaluatorVersion,
    ExperimentId,
)
from eval_lab.contracts.serialization import ContractValidationError, frozen_mapping, nested_list
from enum import Enum


class EvaluatorRelationshipType(str, Enum):
    """Per §57's own closed list. Correction pass: originally a raw `str`
    with a manual `__post_init__` membership check -- weaker typing
    discipline than the rest of the package's closed vocabularies, with
    no extensibility justification (unlike e.g. OracleProbeCase.probe_type,
    which is deliberately left free-form and documented as such)."""

    SUPPORTING = "supporting"
    DEPENDENT_ON = "dependent_on"
    CONTRADICTORY = "contradictory"
    SUPERSEDES = "supersedes"


@dataclass(frozen=True)
class EvaluatorRelationship:
    """Per §57: where one evaluator result depends on or contradicts
    another, represent that explicitly rather than assuming "later
    evaluator = more authoritative." `relationship_type` is one of
    "supporting" | "dependent_on" | "contradictory" | "supersedes" per
    §57's own list."""

    related_evaluator_id: EvaluatorId
    related_evaluator_version: EvaluatorVersion
    relationship_type: EvaluatorRelationshipType

    def __post_init__(self) -> None:
        if not isinstance(self.relationship_type, EvaluatorRelationshipType):
            raise ContractValidationError(
                "relationship_type_not_enum_member",
                f"relationship_type must be an EvaluatorRelationshipType member, "
                f"got {type(self.relationship_type).__name__}.",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "related_evaluator_id": self.related_evaluator_id,
            "related_evaluator_version": self.related_evaluator_version,
            "relationship_type": self.relationship_type.value,
        }


@dataclass(frozen=True)
class EvaluationResult:
    """Per original brief §27/§30-32, ADR-LAB-03: score + status +
    evaluator + evaluator_version + confidence + evidence, always. A score
    without evidence is exactly the opaque number the mission repeatedly
    forbids -- enforced below: PASS/FAIL/PARTIAL require at least one
    Evidence; INSUFFICIENT_EVIDENCE/NOT_EVALUATED/ERROR do not (there may
    be nothing to point to yet)."""

    evaluator_id: EvaluatorId
    evaluator_version: EvaluatorVersion
    dimension: str
    """Which of the mission's evaluation dimensions this result measures
    (e.g. "goal_satisfaction", "tool_selection_quality", "groundedness") --
    free string rather than an enum, since the original brief's dimension
    list (§6/§26) is explicitly "at minimum," not exhaustive."""
    status: EvaluatorResultStatus
    score: float | None
    """None is legitimate for a non-numeric verdict (many deterministic
    checks are pass/fail with no meaningful score); 0.0 and None are not
    the same thing."""
    confidence: ConfidenceLevel
    evidence: tuple[Evidence, ...]
    relationships: tuple[EvaluatorRelationship, ...] = ()
    produced_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.confidence, ConfidenceLevel):
            raise ContractValidationError(
                "confidence_not_enum_member",
                f"confidence must be a ConfidenceLevel member, got {type(self.confidence).__name__}.",
            )
        if self.score is not None and not (0.0 <= self.score <= 1.0):
            raise ContractValidationError("score_out_of_range", f"score must be in [0.0, 1.0] or None, got {self.score}.")
        requires_evidence = self.status in (
            EvaluatorResultStatus.PASS, EvaluatorResultStatus.FAIL, EvaluatorResultStatus.PARTIAL,
        )
        if requires_evidence and not self.evidence:
            raise ContractValidationError(
                "result_requires_evidence",
                f"status={self.status.value} requires at least one Evidence entry.",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "dimension": self.dimension,
            "status": self.status.value,
            "score": self.score,
            "confidence": self.confidence.value,
            "evidence": nested_list(list(self.evidence)),
            "relationships": [r.to_dict() for r in self.relationships],
            "produced_at": self.produced_at.isoformat(),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class EvaluationAggregate:
    """Per §19: the run-level rollup across all of a run's
    EvaluationResults -- distinct from any one of them. `per_dimension`
    holds one EvaluationResult per dimension key for convenient lookup;
    `overall_status` is a rollup the *caller* computes and asserts (this
    contract does not compute an aggregate score itself -- per original
    brief §26/§30, "do not hard-code a single aggregate score unless there
    is a legitimate use case," and Slice 2 does not implement an
    aggregation engine).

    Correction pass: `per_dimension` was a plain mutable `dict` on a
    frozen dataclass -- `frozen=True` blocks `agg.per_dimension = x` but
    not `agg.per_dimension["x"] = y`. Now wrapped in a `MappingProxyType`
    (serialization.frozen_mapping) at construction time; the type hint is
    `Mapping` rather than `dict` to make the read-only contract visible to
    callers/type-checkers, not just enforced at runtime."""

    evaluation_run_id: EvaluationRunId
    per_dimension: Mapping[str, EvaluationResult]
    overall_status: EvaluatorResultStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_dimension", frozen_mapping(self.per_dimension))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_run_id": self.evaluation_run_id,
            "per_dimension": {k: v.to_dict() for k, v in self.per_dimension.items()},
            "overall_status": self.overall_status.value,
        }


@dataclass(frozen=True)
class MetricObservation:
    """One multi-run metric value (e.g. "pass_rate over 20 runs of task
    T"), per §19/§51. Distinct from EvaluationAggregate (one run) and from
    ComparisonResult (two populations) -- this is "one number, computed
    over one population, at one point in time."

    Correction pass (population lineage, ADR-LAB-05): originally had no
    reference back to which EvaluationPopulation it was computed over.
    When nested inside ComparisonResult, `experiment_id` on the enclosing
    object provided partial lineage -- but a standalone MetricObservation
    (e.g. a future single-sided reliability report with no baseline to
    compare against) had none at all, which is exactly the ambiguity
    ADR-LAB-05 exists to prevent ("82% of selected cases passed" must
    never be presentable without the population that produced it).
    `population_id` is added directly here rather than duplicating
    `experiment_id` too: a bare metric naturally references the population
    it was measured over, while an experiment context (which implies a
    comparison) is already available from ComparisonResult when relevant
    and would be redundant to repeat on every MetricObservation."""

    metric_name: str
    value: float
    n: int
    population_id: str | None = None
    """None only when genuinely not computed over a tracked population
    (e.g. a single ad hoc measurement) -- for anything meant to support a
    capability claim, a real population_id should be set."""
    unit: str = ""
    """E.g. "probability", "count", "ms" -- per §67's numeric/unit
    semantics requirement; free string since the set of possible units is
    open-ended."""

    def __post_init__(self) -> None:
        if self.n < 0:
            raise ContractValidationError("negative_n", "n cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name, "value": self.value, "n": self.n,
            "population_id": self.population_id, "unit": self.unit,
        }


@dataclass(frozen=True)
class ComparisonResult:
    """Baseline-vs-candidate comparison, per §19/original brief §47.
    `is_comparable` plus `comparability_caveats` implement §47's
    requirement directly: an incomparable pair must say so rather than
    silently printing a delta. No statistical test is computed here
    (ADR-LAB-05: no statistics engine in Slice 2) -- `raw_delta` is exactly
    that, raw, and `comparability_caveats` is where the honesty about
    whether the delta means anything lives."""

    baseline_metric: MetricObservation
    candidate_metric: MetricObservation
    experiment_id: ExperimentId | None = None
    is_comparable: bool = True
    comparability_caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.baseline_metric.metric_name != self.candidate_metric.metric_name:
            raise ContractValidationError(
                "mismatched_metric_names",
                "baseline_metric and candidate_metric must have the same metric_name to be comparable at all.",
            )
        if not self.is_comparable and not self.comparability_caveats:
            raise ContractValidationError(
                "incomparable_requires_caveats",
                "is_comparable=False requires at least one entry in comparability_caveats "
                "explaining why (§47).",
            )

    @property
    def raw_delta(self) -> float:
        return self.candidate_metric.value - self.baseline_metric.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_metric": self.baseline_metric.to_dict(),
            "candidate_metric": self.candidate_metric.to_dict(),
            "experiment_id": self.experiment_id,
            "is_comparable": self.is_comparable,
            "comparability_caveats": list(self.comparability_caveats),
            "raw_delta": self.raw_delta,
        }
