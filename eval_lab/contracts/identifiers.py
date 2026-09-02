"""eval_lab/contracts/identifiers.py — identity, version, and hash primitives.

ADR-LAB-01 requires the Lab's identity model to keep adjacent-but-distinct
concepts (task definition vs. instance vs. execution vs. evaluation run;
object identity vs. content hash vs. configuration hash) from ever being
collapsed into one field for convenience. This repository already shows
what that collapse costs at runtime: KNOWN_ISSUES.md DEBT-015 exists
because a single `trace_id` is asked to mean both "this HTTP request" and
"this logical operation," and can't distinguish a retry from a new
operation as a result.

Every ID below is a `typing.NewType` over `str` (or `int` for monotonic
version counters): zero runtime cost, but a static type checker will
reject passing a `TaskId` where an `EvaluationCaseId` is expected. This is
deliberately the lightest mechanism that satisfies ADR-LAB-01/§25's
requirement -- a bespoke ID-wrapper class hierarchy was considered and
rejected as exactly the "generic framework abstraction" PROJECT_INSTRUCTIONS.md
warns against (§20.8) for a distinction `NewType` already gets for free.

Content/configuration hashes get their own NewTypes, distinct from IDs:
per ADR-LAB-01/§25, an id is *assigned* identity; a hash is *derived* from
content. `evaluator_version_id != evaluator_configuration_hash` must hold
even though both are plain strings underneath.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import NewType

# ---------------------------------------------------------------------------
# Object identifiers (assigned identity -- distinct per §8 of the Slice 2 brief)
# ---------------------------------------------------------------------------

EvaluationRunId = NewType("EvaluationRunId", str)
ExperimentId = NewType("ExperimentId", str)

BenchmarkId = NewType("BenchmarkId", str)
TaskId = NewType("TaskId", str)
TaskInstanceId = NewType("TaskInstanceId", str)
EvaluationCaseId = NewType("EvaluationCaseId", str)

EnvironmentId = NewType("EnvironmentId", str)
EnvironmentInstanceId = NewType("EnvironmentInstanceId", str)

ExecutionInstanceId = NewType("ExecutionInstanceId", str)
"""Lab-minted. Per ADR-LAB-01 §4 / this Slice's §9: never derived from the
runtime's own `trace_id`, never a stand-in for DEBT-015's unimplemented
Operation/ExecutionAttempt identity. See `FutureRuntimeOperationRef` below
for the documented mapping seam."""

AgentId = NewType("AgentId", str)

EvaluationDefinitionId = NewType("EvaluationDefinitionId", str)
EvaluatorId = NewType("EvaluatorId", str)
OracleId = NewType("OracleId", str)
SimulatorId = NewType("SimulatorId", str)

TrajectoryId = NewType("TrajectoryId", str)
TrajectoryEventId = NewType("TrajectoryEventId", str)
CheckpointId = NewType("CheckpointId", str)
BranchId = NewType("BranchId", str)
SnapshotId = NewType("SnapshotId", str)

EvidenceId = NewType("EvidenceId", str)
ArtifactId = NewType("ArtifactId", str)
ExperimentResultId = NewType("ExperimentResultId", str)
AnnotationId = NewType("AnnotationId", str)
AnnotatorId = NewType("AnnotatorId", str)
FailureRecordId = NewType("FailureRecordId", str)
InterventionId = NewType("InterventionId", str)
CounterfactualEvaluationId = NewType("CounterfactualEvaluationId", str)
PopulationId = NewType("PopulationId", str)

# ---------------------------------------------------------------------------
# Version counters (monotonic per published artifact; ADR-LAB-04 §2:
# "a semantic change to a published benchmark must produce a new version")
# ---------------------------------------------------------------------------

BenchmarkVersion = NewType("BenchmarkVersion", int)
TaskVersion = NewType("TaskVersion", int)
EnvironmentVersion = NewType("EnvironmentVersion", int)
AgentVersion = NewType("AgentVersion", str)
"""Agent/runtime versions are external (e.g. a git SHA or semver string
OCBrain itself is tagged with) -- unlike benchmark/task versions, the Lab
does not mint these, so this stays a free-form string rather than a
Lab-controlled monotonic counter."""
RuntimeVersion = NewType("RuntimeVersion", str)
EvaluationDefinitionVersion = NewType("EvaluationDefinitionVersion", int)
EvaluatorVersion = NewType("EvaluatorVersion", int)
OracleVersion = NewType("OracleVersion", int)
SimulatorVersion = NewType("SimulatorVersion", int)

# ---------------------------------------------------------------------------
# Hashes (derived from content -- distinct from the above; ADR-LAB-01 §25)
# ---------------------------------------------------------------------------

ContentHash = NewType("ContentHash", str)
ConfigurationHash = NewType("ConfigurationHash", str)
RubricVersion = NewType("RubricVersion", str)
PromptTemplateHash = NewType("PromptTemplateHash", str)


def new_object_id(prefix: str) -> str:
    """Mint a new object id. Prefixed (e.g. ``run_...``) purely for human
    legibility in logs/fixtures -- the prefix carries no semantic meaning
    and callers must not parse it. Uses uuid4, matching the convention
    already used for identity generation elsewhere in this repository
    (core/cognitive/intent.py imports `uuid` for the same purpose)."""
    return f"{prefix}_{uuid.uuid4().hex}"


def content_hash(canonical_bytes: bytes) -> ContentHash:
    """Deterministic content hash for artifacts/evidence/trajectories.
    SHA-256 over already-canonicalized bytes -- canonicalization itself
    (stable key ordering, no floats-as-repr ambiguity) is the caller's
    responsibility; see `serialization.py`."""
    return ContentHash(hashlib.sha256(canonical_bytes).hexdigest())


@dataclass(frozen=True)
class SchemaVersion:
    """Major/minor schema version for serialized Lab contracts (§68 of the
    Slice 2 brief). Distinct from `BenchmarkVersion`/`TaskVersion`/etc.
    above: those version a *domain object* (a benchmark's content changed);
    this versions the *wire format* a contract type is serialized as.

    Compatibility policy (§68/§69): same major = compatible; different
    major = incompatible, must not be silently reinterpreted. There is no
    "unknown future version" special case here beyond major-mismatch
    detection -- a reader encountering a higher, unknown major version
    should raise `UnsupportedSchemaVersion` rather than guess.

    Correction pass clarification: `is_compatible_with` reports a
    *declared versioning policy* -- the same convention semantic
    versioning uses, where a maintainer commits to keeping same-major
    changes additive/non-breaking. It is not, and cannot be, an
    empirically-verified guarantee that any two same-major-versioned
    instances are actually interoperable in every respect; a version
    number is a promise about how changes will be made, not a proof about
    the artifacts themselves. Nothing in Slice 2 checks or enforces that
    the promise was kept -- there is no migration engine and none is
    implemented here (§69 of the correction pass: "do not build
    migrations... ensure the contract/documentation does not overclaim").
    """

    major: int
    minor: int = 0

    def is_compatible_with(self, other: "SchemaVersion") -> bool:
        """Declared-policy compatibility check (see class docstring) --
        not an empirical interoperability test."""
        return self.major == other.major

    def __str__(self) -> str:  # canonical string form, used in serialized output
        return f"{self.major}.{self.minor}"

    @classmethod
    def parse(cls, s: str) -> "SchemaVersion":
        major_s, _, minor_s = s.partition(".")
        return cls(major=int(major_s), minor=int(minor_s) if minor_s else 0)


class UnsupportedSchemaVersion(Exception):
    """Raised on deserialization when a contract's recorded schema_version
    has a major version this code does not know how to read. Per §69:
    never silently reinterpret an old schema under a new semantic meaning
    -- refuse instead."""


# Slice 2 introduces every contract at once, so a single current schema
# version is correct for now. Per ADR-LAB-04/§68, individual contract
# families are free to diverge and bump independently once any one of
# them actually changes shape after this slice ships.
CURRENT_SCHEMA_VERSION = SchemaVersion(major=1, minor=0)


@dataclass(frozen=True)
class FutureRuntimeOperationRef:
    """Documented mapping seam for DEBT-015 (Execution Reliability Track),
    per ADR-LAB-01 §4 and this Slice's §9. Deliberately empty of real
    behavior: DEBT-015's `Operation`/`ExecutionAttempt` model is proposed,
    not implemented, and this Lab must not implement it, depend on it, or
    simulate it. This type exists solely so that `ExecutionReference`
    (run.py) has a well-typed, always-optional field to populate *if and
    when* that runtime identity exists, without a breaking migration.

    `runtime_operation_id` / `runtime_attempt_number` are opaque strings/
    ints from whatever DEBT-015 eventually produces -- this module makes
    no assumption about their shape beyond "identifier" and "ordinal."

    Correction pass (§11, boundary protection): this class defines no
    methods beyond `to_dict` and the dataclass-generated ones -- no retry
    logic, no identity resolution, nothing that could function as a
    parallel implementation of DEBT-015. See
    test_future_runtime_operation_ref_has_no_behavior_beyond_data_holding
    in test_identifiers.py, which asserts this structurally rather than
    just by convention.
    """

    runtime_operation_id: str | None = None
    runtime_attempt_number: int | None = None

    def to_dict(self) -> dict[str, "int | str | None"]:
        return {"runtime_operation_id": self.runtime_operation_id, "runtime_attempt_number": self.runtime_attempt_number}
