"""
core/capabilities/descriptors.py — machine-readable capability vocabulary.

ADR-CAP-01 / ADR-CAP-02 (Status: DRAFT — this branch has not been reviewed
or merged; see docs/architecture/decisions/ADR_CAP_01_CAPABILITY_FOUNDATION.md).

Purpose
-------
K2.3's CapabilityContract carried a capability_type, a prose description, and
two flags. Discovery (core/cognitive/planner.py) scores that prose lexically.
This module adds the *structured* metadata a future selector (C-MoE), a UX, a
Verification consumer or a conformance suite can reason about without
parsing prose -- and nothing else. Every type here is plain data:

    * No behavior beyond validation and structural compatibility checks.
    * No selection, ranking or scoring (selection stays with the Planner today
      and with C-MoE later -- see ADR-K4.2-H-02/-04 and K4.2 §1).
    * Descriptive, never enforcing: ``side_effects`` and ``repeatability``
      describe an operation. Enforcement lives in GovernanceKernel and the
      sandbox. Metadata is not a permission.

Vocabulary and the identity ladder (kept separate on purpose)
-------------------------------------------------------------
    capability_type      stable semantic identity ("file_reading")
    operation            named mode of one capability ("read_document").
                         NOT ``operation_id``: ADR-K4.2-H-08 and ADR-KERNEL-01
                         already use *operation_id* / *root_operation_id* for
                         the identity of one logical plan()/compile() lineage.
                         A capability operation is a different concept
                         (Workspace §G.5's "Operation" in the grant tuple) and
                         is therefore carried in a field named ``operation``.
    contract version     CapabilityContract.version -- semver of the *contract*;
                         a major bump means the semantics changed
    adapter identity     adapter_name (+ optional adapter_version)
    model / provider     reported per call in result provenance; never part of
                         capability identity

Not a type ontology. The semantic types below are the closed set the three
foundation capabilities actually exchange; adding one is an ADR-level change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_SCHEMA_RE = re.compile(r"^[a-z][a-z0-9_.]*/\d+$")


# ── Descriptive classifications ─────────────────────────────────────────────

class SideEffect:
    """Descriptive side-effect classification (NOT enforcement).

    Only the values the foundation needs exist. Capabilities with external
    side effects (writes, network calls, tool invocation) will need a richer
    classification *and* stronger idempotency semantics; that is deliberately
    not pre-built here (ADR-CAP-01 "Deferred").
    """
    NONE = "none"                # pure computation; no observable external effect
    READ_ONLY = "read_only"      # reads an artifact; never mutates anything
    UNSPECIFIED = "unspecified"  # legacy contracts that predate this field


class Repeatability:
    """How safely an operation can be retried / replayed (descriptive)."""
    REPEATABLE = "repeatable"          # same input -> same output
    MODEL_VARIABLE = "model_variable"  # same input -> output may vary with model/runtime
    UNSPECIFIED = "unspecified"


class CapabilityLifecycle:
    """Runtime lifecycle of a capability *type* (held by CapabilityRegistry).

    Implementation-level replacement does not use this: replacing an adapter
    is register_adapter()/deregister_adapter() under an unchanged capability
    identity.
    """
    ACTIVE = "active"
    DEPRECATED = "deprecated"   # still discoverable and invocable; flagged
    DISABLED = "disabled"       # not discoverable, not invocable (reversible)
    RETIRED = "retired"         # not discoverable, not invocable (terminal)


DISCOVERABLE_LIFECYCLES: FrozenSet[str] = frozenset(
    {CapabilityLifecycle.ACTIVE, CapabilityLifecycle.DEPRECATED})
INVOCABLE_LIFECYCLES: FrozenSet[str] = DISCOVERABLE_LIFECYCLES

SIDE_EFFECT_VALUES: FrozenSet[str] = frozenset(
    {SideEffect.NONE, SideEffect.READ_ONLY, SideEffect.UNSPECIFIED})
REPEATABILITY_VALUES: FrozenSet[str] = frozenset(
    {Repeatability.REPEATABLE, Repeatability.MODEL_VARIABLE,
     Repeatability.UNSPECIFIED})
LIFECYCLE_VALUES: FrozenSet[str] = frozenset(
    {CapabilityLifecycle.ACTIVE, CapabilityLifecycle.DEPRECATED,
     CapabilityLifecycle.DISABLED, CapabilityLifecycle.RETIRED})


# ── Result status vocabulary ────────────────────────────────────────────────

class CapabilityStatus:
    """Machine-readable outcome of one capability invocation.

    Maps onto -- does not replace -- core/runtime/execution_outcome.py's
    FailureType at the worker layer (see core/capabilities/foundation/
    step_workers.py). The vocabulary exists because FailureType has no way to
    say "unsupported", "malformed" or "legitimately empty", and because
    CapabilityResult.success alone cannot distinguish an *adapter fault* (which
    should degrade the adapter's health) from a *request that cannot be
    fulfilled* (which must not).

    success == True  : OK, PARTIAL, DEGRADED, EMPTY
    success == False : everything else
    """
    OK = "ok"                    # complete result
    PARTIAL = "partial"          # usable but incomplete (truncated / some inputs failed)
    DEGRADED = "degraded"        # complete-ish but lower fidelity (fallback path, warnings)
    EMPTY = "empty"              # read/executed correctly; there is legitimately nothing

    UNSUPPORTED = "unsupported"                    # this implementation cannot handle the input
    MALFORMED = "malformed"                        # input invalid for its (declared/detected) form
    UNREADABLE = "unreadable"                      # artifact content could not be obtained
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"  # required library/runtime missing
    INVALID_REQUEST = "invalid_request"            # caller violated the operation contract
    LIMIT_EXCEEDED = "limit_exceeded"              # rejected by a hard resource limit
    UNAVAILABLE = "unavailable"                    # capability disabled/retired/no adapter
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    FAILED = "failed"            # adapter/provider fault (health-affecting)


SUCCESS_STATUSES: FrozenSet[str] = frozenset({
    CapabilityStatus.OK, CapabilityStatus.PARTIAL,
    CapabilityStatus.DEGRADED, CapabilityStatus.EMPTY,
})

# Statuses that describe *the request*, not a fault of the adapter that
# answered. AdapterRuntime never applies a health penalty for these.
REQUEST_LEVEL_STATUSES: FrozenSet[str] = frozenset({
    CapabilityStatus.UNSUPPORTED, CapabilityStatus.MALFORMED,
    CapabilityStatus.UNREADABLE, CapabilityStatus.DEPENDENCY_UNAVAILABLE,
    CapabilityStatus.INVALID_REQUEST, CapabilityStatus.LIMIT_EXCEEDED,
})

# Of those, the ones another implementation might still fulfil. AdapterRuntime
# tries the next adapter (still without penalty) for these; every other
# request-level status is returned immediately.
FALLTHROUGH_STATUSES: FrozenSet[str] = frozenset({
    CapabilityStatus.UNSUPPORTED, CapabilityStatus.DEPENDENCY_UNAVAILABLE,
})

ALL_STATUSES: FrozenSet[str] = frozenset(
    {v for k, v in vars(CapabilityStatus).items()
     if not k.startswith("_") and isinstance(v, str)})


# ── Semantic types exchanged by the foundation capabilities ─────────────────

class SemanticType:
    """The closed set of value kinds the foundation capabilities exchange.

    Not an ontology: it names exactly what crosses a capability boundary
    today. A semantic type is *what the value is*; a media type says how it is
    serialized; a schema id says which versioned structure it has.
    """
    ARTIFACTS = "artifacts"    # one or more input artifacts (identity + bytes/text)
    DOCUMENT = "document_set"  # structured reading of one or more artifacts
    ANALYSIS = "analysis"      # structured analytical result
    TEXT = "text"              # generated or supplied prose


@dataclass(frozen=True)
class TypeSpec:
    """Machine-readable description of one value crossing a capability boundary.

    semantic_type  what it is (SemanticType.*)
    media_types    IANA media types it may arrive/leave as; empty = any
                   (RFC 6838; ``type/*`` wildcards allowed)
    schema_id      versioned structure, ``"<name>/<major>"``; empty = unversioned
                   free-form. Only the major is compared for compatibility.
    """
    semantic_type: str
    media_types: Tuple[str, ...] = ()
    schema_id: str = ""

    def __post_init__(self) -> None:
        if not self.semantic_type:
            raise ValueError("TypeSpec.semantic_type must not be empty")
        if self.schema_id and not _SCHEMA_RE.match(self.schema_id):
            raise ValueError(
                f"TypeSpec.schema_id must look like '<name>/<major>', "
                f"got {self.schema_id!r}")

    def accepts(self, produced: "TypeSpec") -> bool:
        """True iff a consumer declaring ``self`` as an input can take a value
        a producer declared as ``produced``.

        Pure structural check: same semantic type, overlapping media types
        (empty on either side = unconstrained), same schema name+major when
        both declare one. It does not judge quality, relevance or trust.
        """
        if self.semantic_type != produced.semantic_type:
            return False
        if self.media_types and produced.media_types:
            if not any(_media_overlap(a, b)
                       for a in self.media_types for b in produced.media_types):
                return False
        if self.schema_id and produced.schema_id:
            if self.schema_id != produced.schema_id:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {"semantic_type": self.semantic_type,
                "media_types": list(self.media_types),
                "schema_id": self.schema_id}


def _media_overlap(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    at, _, asub = a.partition("/")
    bt, _, bsub = b.partition("/")
    if at != bt:
        return False
    return asub == "*" or bsub == "*"


@dataclass(frozen=True)
class OperationSpec:
    """One named mode of a capability, with its own input/output contract.

    A distinct operation is justified only when its *contract* differs (inputs,
    outputs or required keys). Variations that only change a parameter are
    parameters, not operations.

    requires   payload keys the operation needs (lightweight precondition,
               checked by AdapterRuntime -> INVALID_REQUEST when absent)
    produces   keys a non-failure output dict contains (lightweight
               postcondition, checked by the conformance suite)
    """
    name: str
    description: str
    inputs: Tuple[TypeSpec, ...] = ()
    outputs: Tuple[TypeSpec, ...] = ()
    requires: Tuple[str, ...] = ()
    produces: Tuple[str, ...] = ()
    side_effects: str = ""  # "" = inherit the contract's
    repeatability: str = Repeatability.UNSPECIFIED

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name or ""):
            raise ValueError(
                f"OperationSpec.name must match {_NAME_RE.pattern}, "
                f"got {self.name!r}")
        if self.side_effects and self.side_effects not in SIDE_EFFECT_VALUES:
            raise ValueError(f"unknown side_effects {self.side_effects!r}")
        if self.repeatability not in REPEATABILITY_VALUES:
            raise ValueError(f"unknown repeatability {self.repeatability!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputs": [t.to_dict() for t in self.inputs],
            "outputs": [t.to_dict() for t in self.outputs],
            "requires": list(self.requires),
            "produces": list(self.produces),
            "side_effects": self.side_effects,
            "repeatability": self.repeatability,
        }


# ── Versions ────────────────────────────────────────────────────────────────

def parse_version(version: str) -> Optional[Tuple[int, int, int]]:
    """Parse ``major.minor.patch`` (pre-release/build suffix ignored)."""
    m = _SEMVER_RE.match((version or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def contract_major(version: str) -> Optional[int]:
    parsed = parse_version(version)
    return parsed[0] if parsed else None


def implements_contract_major(declared: str) -> Optional[int]:
    """An adapter declares the contract it implements as ``"1"`` or ``"1.2"``
    (or a full semver). Only the major participates in compatibility."""
    text = (declared or "").strip()
    if not text:
        return None
    head = text.split(".", 1)[0]
    return int(head) if head.isdigit() else None


def validate_operations(capability_type: str,
                        operations: Tuple[OperationSpec, ...],
                        default_operation: str) -> List[str]:
    """Structural problems in a declared operation set (empty list = valid)."""
    problems: List[str] = []
    seen = set()
    for op in operations:
        if op.name in seen:
            problems.append(
                f"{capability_type}: duplicate operation '{op.name}'")
        seen.add(op.name)
    if default_operation and default_operation not in seen:
        problems.append(
            f"{capability_type}: default_operation '{default_operation}' "
            f"is not a declared operation")
    return problems


# ── Lifecycle record & structured operation references ──────────────────────

@dataclass(frozen=True)
class LifecycleRecord:
    """Registry-held lifecycle state for one capability type.

    Kept in CapabilityRegistry (runtime state), not on the CapabilityContract
    (declarative metadata), so a contract object other code already holds is
    never mutated behind its back (registry.register_capability's rule).
    """
    state: str = CapabilityLifecycle.ACTIVE
    reason: str = ""
    replaced_by: str = ""  # capability_type that supersedes this one, if any

    def to_dict(self) -> Dict[str, Any]:
        return {"state": self.state, "reason": self.reason,
                "replaced_by": self.replaced_by}


@dataclass(frozen=True)
class OperationRef:
    """Pointer to one operation of one capability (a structured match)."""
    capability_type: str
    operation: str

    def to_dict(self) -> Dict[str, str]:
        return {"capability_type": self.capability_type,
                "operation": self.operation}


def operations_composable(producer: OperationSpec,
                          consumer: OperationSpec) -> bool:
    """True iff *some* output of ``producer`` is structurally acceptable to
    *some* input of ``consumer``. Structural only -- see TypeSpec.accepts()."""
    return any(i.accepts(o) for o in producer.outputs for i in consumer.inputs)
