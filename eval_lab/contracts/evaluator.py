"""eval_lab/contracts/evaluator.py — evaluator identity, evaluation definition, metrics.

Implements ADR-LAB-03 (layering, evidence, judge calibration, lifecycle,
classifier statistics, abstention) and §16-18, §58, §61-62 of this Slice.
`EvaluatorMetrics` is defined here and reused by oracle.py's docstring
reference -- oracles and evaluators are both "verdict-producers against a
possibly-incomplete ground truth" per ADR-LAB-06 §2, so one metrics shape
serves both rather than two near-identical ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eval_lab.contracts.enums import ConstructValidity, EvaluatorType, LifecycleState, EVALUATOR_LIFECYCLE
from eval_lab.contracts.identifiers import (
    ConfigurationHash,
    CURRENT_SCHEMA_VERSION,
    EvaluationDefinitionId,
    EvaluationDefinitionVersion,
    EvaluatorId,
    EvaluatorVersion,
    PromptTemplateHash,
    RubricVersion,
    SchemaVersion,
)
from eval_lab.contracts.serialization import ContractValidationError, frozen_mapping, nested


@dataclass(frozen=True)
class JudgeIdentity:
    """The approved judge identity model (this Slice's §62, ADR-LAB-03 §2):
    judge_model_id, rubric_version, prompt_template_hash, configuration_hash.
    Deliberately its own type rather than four loose fields on
    EvaluatorDefinition -- per §62's own emphasis ("Do not make judge model
    family the only identity field"), bundling all four together makes it
    structurally impossible to record a judge by model family alone."""

    judge_model_id: str
    rubric_version: RubricVersion
    prompt_template_hash: PromptTemplateHash
    configuration_hash: ConfigurationHash
    cross_family_from_subject: bool | None = None
    """None = not yet determined/not applicable. True/False per ADR-LAB-03
    §2's cross-family default policy; when False (same-family judging),
    ADR-LAB-03's amendment requires this to be an explicit, visible
    choice -- see `self_preference_risk_acknowledged` below, not silence."""
    self_preference_risk_acknowledged: bool = False
    """Per ADR-LAB-03 §5 (amendment alternatives considered): same-family
    judging is allowed but must not be the silent default. If
    cross_family_from_subject is False, this must be True -- enforced in
    __post_init__."""

    def __post_init__(self) -> None:
        if self.cross_family_from_subject is False and not self.self_preference_risk_acknowledged:
            raise ContractValidationError(
                "same_family_judging_not_acknowledged",
                "cross_family_from_subject=False (same-family judging) requires "
                "self_preference_risk_acknowledged=True (ADR-LAB-03 amendment).",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "judge_model_id": self.judge_model_id,
            "rubric_version": self.rubric_version,
            "prompt_template_hash": self.prompt_template_hash,
            "configuration_hash": self.configuration_hash,
            "cross_family_from_subject": self.cross_family_from_subject,
            "self_preference_risk_acknowledged": self.self_preference_risk_acknowledged,
        }


@dataclass(frozen=True)
class EvaluatorMetrics:
    """Per ADR-LAB-03 §4 / ADR-LAB-06 §2: both oracles and evaluators are
    verdict-producers whose own error rates matter, not just the subject's.
    All fields optional and default to None (not 0.0) -- an evaluator with
    no metrics recorded yet is "unmeasured," not "measured at zero error,"
    a distinction §7a.4 of the research report specifically warns about
    (a high-abstention/never-measured mechanism must not look reliable by
    default)."""

    true_positive: int | None = None
    true_negative: int | None = None
    false_positive: int | None = None
    false_negative: int | None = None
    abstention_count: int | None = None
    n_probes: int | None = None

    def __post_init__(self) -> None:
        counts = [self.true_positive, self.true_negative, self.false_positive,
                  self.false_negative, self.abstention_count]
        for c in counts:
            if c is not None and c < 0:
                raise ContractValidationError("negative_metric_count", "classifier counts cannot be negative.")

    @property
    def sensitivity(self) -> float | None:
        if self.true_positive is None or self.false_negative is None:
            return None
        denom = self.true_positive + self.false_negative
        return self.true_positive / denom if denom else None

    @property
    def specificity(self) -> float | None:
        if self.true_negative is None or self.false_positive is None:
            return None
        denom = self.true_negative + self.false_positive
        return self.true_negative / denom if denom else None

    @property
    def precision(self) -> float | None:
        if self.true_positive is None or self.false_positive is None:
            return None
        denom = self.true_positive + self.false_positive
        return self.true_positive / denom if denom else None

    @property
    def abstention_rate(self) -> float | None:
        if self.abstention_count is None or not self.n_probes:
            return None
        return self.abstention_count / self.n_probes

    def to_dict(self) -> dict[str, Any]:
        return {
            "true_positive": self.true_positive,
            "true_negative": self.true_negative,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "abstention_count": self.abstention_count,
            "n_probes": self.n_probes,
            "sensitivity": self.sensitivity,
            "specificity": self.specificity,
            "precision": self.precision,
            "abstention_rate": self.abstention_rate,
        }


@dataclass(frozen=True)
class EvaluatorDefinition:
    """Per §17/§18 of this Slice: evaluator identity and semantics,
    independent of individual results. `measurement_target` +
    `construct_validity` implement ADR-LAB-01's construct-validity
    requirement directly on the evaluator that will produce results
    against it -- default UNKNOWN, per §16's explicit "do not default to
    strong.\""""

    evaluator_id: EvaluatorId
    evaluator_version: EvaluatorVersion
    evaluator_type: EvaluatorType
    measurement_target: str
    configuration_hash: ConfigurationHash
    construct_validity: ConstructValidity = ConstructValidity.UNKNOWN
    rubric_version: RubricVersion | None = None
    judge_identity: JudgeIdentity | None = None
    metrics: EvaluatorMetrics | None = None
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.lifecycle_state not in EVALUATOR_LIFECYCLE:
            raise ContractValidationError(
                "invalid_evaluator_lifecycle_state",
                f"{self.lifecycle_state} is not a valid evaluator lifecycle state.",
            )
        if self.evaluator_type == EvaluatorType.JUDGE and self.judge_identity is None:
            # Cross-field invariant, §71: "judge result => judge identity/version exists"
            raise ContractValidationError(
                "judge_evaluator_requires_judge_identity",
                "evaluator_type=JUDGE requires judge_identity to be set.",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "evaluator_type": self.evaluator_type.value,
            "measurement_target": self.measurement_target,
            "configuration_hash": self.configuration_hash,
            "construct_validity": self.construct_validity.value,
            "rubric_version": self.rubric_version,
            "judge_identity": nested(self.judge_identity),
            "metrics": nested(self.metrics),
            "lifecycle_state": self.lifecycle_state.value,
            "schema_version": str(self.schema_version),
        }


@dataclass(frozen=True)
class EvaluationDefinition:
    """Per §16 of this Slice: describes the measurement being performed
    (distinct from EvaluatorDefinition, which describes the mechanism
    performing it -- one EvaluationDefinition could in principle be
    satisfied by more than one evaluator implementation, e.g. a
    deterministic check and a judge both claiming to measure "goal
    satisfaction"; keeping them separate makes that comparison
    representable rather than assuming a 1:1 mapping)."""

    evaluation_definition_id: EvaluationDefinitionId
    evaluation_definition_version: EvaluationDefinitionVersion
    measurement_target: str
    construct_definition: str
    construct_validity: ConstructValidity = ConstructValidity.UNKNOWN
    evaluator_id: EvaluatorId | None = None
    evaluator_version: EvaluatorVersion | None = None
    oracle_id: str | None = None
    oracle_version: int | None = None
    required_evidence_description: str = ""
    configuration: dict[str, Any] = field(default_factory=dict)
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        # Correction pass: see serialization.frozen_mapping's docstring.
        object.__setattr__(self, "configuration", frozen_mapping(self.configuration))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_definition_id": self.evaluation_definition_id,
            "evaluation_definition_version": self.evaluation_definition_version,
            "measurement_target": self.measurement_target,
            "construct_definition": self.construct_definition,
            "construct_validity": self.construct_validity.value,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "oracle_id": self.oracle_id,
            "oracle_version": self.oracle_version,
            "required_evidence_description": self.required_evidence_description,
            "configuration": dict(self.configuration),
            "schema_version": str(self.schema_version),
        }
