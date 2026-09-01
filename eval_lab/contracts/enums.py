"""eval_lab/contracts/enums.py — shared closed-set vocabularies.

`class X(str, Enum)` throughout, matching this repository's existing
convention (core/runtime/execution_outcome.py's `FailureType`) rather than
the newer stdlib `enum.StrEnum` -- picked for consistency with house style
over novelty, even though both are available on this repo's Python floor
(>=3.11).

Enums that belong to exactly one contract module (e.g. task-mutation
adaptation classes) are defined next to that module instead of here, to
keep this file a genuine "shared vocabulary" file rather than a dumping
ground -- see PROJECT_INSTRUCTIONS.md §17's warning against giant flat
files playing that role.
"""

from __future__ import annotations

from enum import Enum


class EvaluationStatus(str, Enum):
    """Per this Slice's §11 and the mission's repeated invariant (#20 in
    the amendment): never collapse "the agent failed the task" and "the
    evaluator crashed" into one boolean. This enum covers the *result*
    status of an EvaluationRun; see `FaultDomain` below for *which layer*
    an ERROR/FAILED/TIMEOUT actually originated in."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INCONCLUSIVE = "inconclusive"


class ConfidenceLevel(str, Enum):
    """Shared high/medium/low qualitative confidence vocabulary. Used by
    EvaluationResult.confidence, FlakinessClassification.confidence, and
    AnnotationConfidence.level (result.py, reliability.py, evidence.py).

    Slice 2's correction pass found this had been typed as a raw `str`
    with manual `__post_init__` membership checking in two places
    (EvaluationResult, FlakinessClassification), and left as an
    explicitly-justified free string in a third (AnnotationConfidence.level,
    on the reasoning that a human self-report is a different kind of thing
    than a system-computed confidence). That distinction doesn't actually
    hold up: a human, a judge, and a flakiness-diagnosis process are all
    answering the same question ("how sure is the reporting entity"), and
    there's no reason one should be allowed values outside {high, medium,
    low} while the others can't. All three now share this one enum."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvaluatorResultStatus(str, Enum):
    """Status of a single EvaluatorResult (finer-grained than
    EvaluationStatus, which is the run-level rollup). Includes
    INSUFFICIENT_EVIDENCE and NOT_EVALUATED, which EvaluationStatus does
    not need at the run level but an individual evaluator result does
    (§20-21 of the Slice 2 brief, ADR-LAB-03 §4's abstention requirement)."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    NOT_EVALUATED = "not_evaluated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class FaultDomain(str, Enum):
    """Which layer a failure/error actually originated in. Per the
    amendment's invariant list (#21-24): subject failure != environment
    failure != oracle failure != evaluator failure != judge failure, and
    per §73/§89 of this Slice, none of these may collapse into one FAIL.

    SUBJECT and INFRASTRUCTURE failures may additionally carry a more
    granular `core.runtime.execution_outcome.FailureType` when the
    failure trace actually originated from a runtime ExecutionOutcome --
    see failure.py. ORACLE/EVALUATOR/JUDGE/DATA/INTEGRITY have no runtime
    equivalent; those concepts don't exist in the runtime's vocabulary."""

    SUBJECT = "subject"
    ENVIRONMENT = "environment"
    ORACLE = "oracle"
    EVALUATOR = "evaluator"
    JUDGE = "judge"
    DATA = "data"
    INTEGRITY = "integrity"
    INFRASTRUCTURE = "infrastructure"


class LifecycleState(str, Enum):
    """Shared lifecycle vocabulary for benchmark cases (ADR-LAB-04 §2)
    and evaluators/oracles/simulators (ADR-LAB-03 §4, ADR-LAB-06 §2).
    Not every state applies to every kind of object -- e.g. benchmark
    cases don't use CALIBRATING or QUARANTINED, evaluators don't use
    BENCHMARK or PROTECTED. Each contract module documents which subset
    of states is valid for its own lifecycle field; validity is enforced
    there; a full lattice per object type was considered and rejected as
    overengineering for six object families that share most of one
    vocabulary already."""

    DRAFT = "draft"
    CANDIDATE = "candidate"
    CALIBRATING = "calibrating"
    VALIDATED = "validated"
    BENCHMARK = "benchmark"
    TRUSTED = "trusted"
    PROTECTED = "protected"
    QUARANTINED = "quarantined"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


# Which LifecycleState values are valid for which object family. Used by
# each module's own validation, not enforced generically here -- this is
# reference metadata, not a validator itself (avoids a generic "lifecycle
# framework" the way §80 warns against).
BENCHMARK_CASE_LIFECYCLE = frozenset({
    LifecycleState.DRAFT, LifecycleState.CANDIDATE, LifecycleState.VALIDATED,
    LifecycleState.BENCHMARK, LifecycleState.PROTECTED,
    LifecycleState.DEPRECATED, LifecycleState.REJECTED,
})
EVALUATOR_LIFECYCLE = frozenset({
    LifecycleState.DRAFT, LifecycleState.CANDIDATE, LifecycleState.CALIBRATING,
    LifecycleState.VALIDATED, LifecycleState.TRUSTED,
    LifecycleState.QUARANTINED, LifecycleState.DEPRECATED,
})
ORACLE_SIMULATOR_LIFECYCLE = EVALUATOR_LIFECYCLE  # ADR-LAB-06 §3: same states, same reasoning


class ConstructValidity(str, Enum):
    """Per ADR-LAB-01/§7a.2 of the research report and §16 of this Slice:
    default is UNKNOWN, never STRONG, unless a contract explicitly sets it
    with evidence behind that claim."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    UNKNOWN = "unknown"


class TrustClassification(str, Enum):
    """Per the amendment's §77 (human/simulator/oracle trust is not a
    permanent scalar): applies to oracles, simulators, evaluators, judges,
    and human annotation sources alike."""

    VALIDATED = "validated"
    UNTRUSTED = "untrusted"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"


class ReproducibilityLevel(str, Enum):
    """Per §64 of this Slice / §60 of the research report: never claim
    more determinism than actually holds."""

    FULLY_DETERMINISTIC = "fully_deterministic"
    DETERMINISTIC_ENV_NONDETERMINISTIC_MODEL = "deterministic_env_nondeterministic_model"
    PARTIALLY_REPRODUCIBLE = "partially_reproducible"
    NON_REPRODUCIBLE = "non_reproducible"


class EvidenceCapturePolicy(str, Enum):
    """Per §28 of this Slice (evaluation input and privacy): an explicit
    choice, never an accident of what happened to get logged."""

    FULL = "full"
    REDACTED = "redacted"
    HASH_ONLY = "hash_only"
    METADATA_ONLY = "metadata_only"
    ARTIFACT_OFFLOADED = "artifact_offloaded"
    UNAVAILABLE = "unavailable"


class EvidenceOrigin(str, Enum):
    """Per §29 of this Slice: not all evidence is equally trusted by
    default, and the origin is the first fact needed to judge that."""

    ENVIRONMENT_GENERATED = "environment_generated"
    ORACLE_GENERATED = "oracle_generated"
    AGENT_GENERATED = "agent_generated"
    TOOL_GENERATED = "tool_generated"
    HUMAN_REVIEWED = "human_reviewed"
    EXTERNAL = "external"
    DERIVED = "derived"


class EvaluatorType(str, Enum):
    """Per ADR-LAB-03 §2's four-layer hierarchy, plus PROPERTY_METAMORPHIC
    (research report §7a.6/mission §53) and HYBRID for evaluators that
    combine layers (already anticipated in the original brief's Layer 2
    description)."""

    DETERMINISTIC = "deterministic"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    JUDGE = "judge"
    HUMAN = "human"
    HYBRID = "hybrid"
    PROPERTY_METAMORPHIC = "property_metamorphic"


class CausalRelationType(str, Enum):
    """Per §38 of this Slice: `caused_by` and `derived_from` must not
    collapse into one generic parent reference."""

    CAUSED_BY = "caused_by"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"
    SUPERSEDES = "supersedes"
    SUPERSEDED_BY = "superseded_by"
    OCCURRED_BEFORE = "occurred_before"
    OCCURRED_AFTER = "occurred_after"


class OrderingRelation(str, Enum):
    """Per §37 of this Slice: a serialized sequence number is not
    permission to assume a true total order. ORDERED and CONCURRENT are
    both legitimate; a TrajectoryEvent records which one applies to its
    relationship with a sibling rather than the contract silently picking
    one."""

    ORDERED = "ordered"
    CONCURRENT = "concurrent"
    CAUSALLY_RELATED = "causally_related"
    UNKNOWN = "unknown"
