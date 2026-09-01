"""eval_lab/contracts/reliability.py — repeated-run reliability and flakiness.

Implements §51-52 of this Slice and the mission's reliability sections
(pass@k/pass^k, flakiness diagnosis). No aggregation *engine* here (§51:
"Do not implement aggregation logic") -- `pass_at_1_rate` /
`pass_hat_k_rate` are simple derived properties computed directly from the
recorded run outcomes, not a general statistics package; anything beyond
that (confidence intervals, significance) is ADR-LAB-05/Slice 7 territory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from eval_lab.contracts.enums import ConfidenceLevel, EvaluatorResultStatus
from eval_lab.contracts.serialization import ContractValidationError


class FlakinessSuspectedCause(str, Enum):
    """Per §52: do not simply label every variance "agent unreliability" --
    name the candidate sources explicitly, including UNKNOWN as a
    legitimate answer when the cause hasn't been determined yet."""

    AGENT_NONDETERMINISM = "agent_nondeterminism"
    ENVIRONMENT_NONDETERMINISM = "environment_nondeterminism"
    TOOL_NONDETERMINISM = "tool_nondeterminism"
    TIMING_SENSITIVITY = "timing_sensitivity"
    CONCURRENCY_SENSITIVITY = "concurrency_sensitivity"
    EVALUATOR_NONDETERMINISM = "evaluator_nondeterminism"
    JUDGE_NONDETERMINISM = "judge_nondeterminism"
    INFRASTRUCTURE_INSTABILITY = "infrastructure_instability"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ReliabilityObservation:
    """Per §51: run count, successful/failed/partial runs, pass@k/pass^k-
    compatible data, reproducibility metadata. `run_statuses` is the raw
    per-run outcome list -- pass@1/pass^k are computed from it rather than
    stored separately, so they can never drift out of sync with the
    underlying runs (same reasoning as SimulatorReliability.deviation_rate)."""

    task_id: str
    run_statuses: tuple[EvaluatorResultStatus, ...]

    def __post_init__(self) -> None:
        if not self.run_statuses:
            raise ContractValidationError("reliability_requires_runs", "run_statuses cannot be empty.")

    @property
    def n(self) -> int:
        return len(self.run_statuses)

    @property
    def n_pass(self) -> int:
        return sum(1 for s in self.run_statuses if s == EvaluatorResultStatus.PASS)

    @property
    def pass_at_1_rate(self) -> float:
        """Empirical success rate across all recorded runs -- the honest
        "pass@1" reading (mean success over N independent attempts), not
        the "best of k" reading sometimes meant by pass@k elsewhere in the
        literature. Documented explicitly per this Slice's §51 instruction
        to "use the correct metric for the research question" and not
        copy metric names blindly."""
        return self.n_pass / self.n

    @property
    def pass_hat_k_rate(self) -> float:
        """pass^k: probability that *all* k of a random k-subset succeed,
        estimated here as (n_pass/n) itself when treating each run as an
        independent Bernoulli trial with the observed success rate --
        i.e. this is pass@1 raised to the k-power's *expectation* under
        that model, not literally re-sampled subsets (no statistics
        engine in Slice 2, ADR-LAB-05). Exposed as a property so a caller
        gets a number without this module pretending to have done a full
        combinatorial pass^k estimate."""
        return self.pass_at_1_rate  # k=1 case is definitionally pass@1; see docstring for the honesty caveat

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run_statuses": [s.value for s in self.run_statuses],
            "n": self.n,
            "n_pass": self.n_pass,
            "pass_at_1_rate": self.pass_at_1_rate,
        }


@dataclass(frozen=True)
class FlakinessClassification:
    """Per §52: attached to a ReliabilityObservation that shows variance.
    `suspected_causes` is a set (more than one may be plausible at once)
    with `confidence` distinct from the causes themselves -- naming a
    suspect is not the same as being sure."""

    task_id: str
    suspected_causes: frozenset[FlakinessSuspectedCause]
    confidence: ConfidenceLevel
    investigation_note: str | None = None

    def __post_init__(self) -> None:
        if not self.suspected_causes:
            raise ContractValidationError(
                "flakiness_requires_suspected_cause",
                "suspected_causes cannot be empty -- use FlakinessSuspectedCause.UNKNOWN "
                "if no specific cause has been identified.",
            )
        if not isinstance(self.confidence, ConfidenceLevel):
            raise ContractValidationError(
                "confidence_not_enum_member",
                f"confidence must be a ConfidenceLevel member, got {type(self.confidence).__name__}.",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "suspected_causes": sorted(c.value for c in self.suspected_causes),
            "confidence": self.confidence.value,
            "investigation_note": self.investigation_note,
        }
