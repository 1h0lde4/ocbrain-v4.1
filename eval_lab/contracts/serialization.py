"""eval_lab/contracts/serialization.py — minimal shared serialization helpers.

This repository has no central serialization framework to reuse (§66 of
the Slice 2 brief asks to check first): `to_dict` is implemented per-class
throughout core/ (core/cognitive/intent.py, core/events/event_stream.py,
core/memory/knowledge_event.py, etc. each define their own). This module
follows that same decentralized convention -- every Lab contract defines
its own `to_dict()`/`from_dict()` -- and provides only the handful of
genuinely repeated small pieces (enum-safe encoding, optional-nested-object
encoding, one shared validation exception) rather than a generic
serialize-any-dataclass engine, which would be exactly the kind of
"generic framework abstraction" PROJECT_INSTRUCTIONS.md §20.8 warns against.

Canonicalization policy (§66): dict keys are written in a fixed, explicit
order by each `to_dict()` (Python dicts already preserve insertion order,
so this is free); enums serialize as their `.value`; `None` is written
explicitly as `null` rather than the field being omitted, so "absent from
the JSON" and "explicitly None" stay distinguishable on the wire; floats
are written as-is (no float values exist in Slice 2's contracts that
require rounding/precision policy -- flagged in the final report as
deferred rather than silently decided).

Collection semantics (correction pass, §9): three shapes are used
throughout this package, and the choice is not accidental --

- `tuple[...]` for **ordered sequences** where the order is causally or
  temporally meaningful and validated (e.g. `Trajectory.events`,
  `BenchmarkDefinition.versions` -- both reject out-of-order construction).
- `tuple[...]` *also* for collections that are conceptually unordered
  but need deterministic serialization (e.g. `EvaluationResult.evidence`,
  `EvaluationRun.results`/`failures`, `OracleValidation.probe_cases`).
  Here the tuple's order is construction/insertion order, not a semantic
  claim -- documented per-field rather than switched to `frozenset`,
  because a `frozenset` would *lose* deterministic serialization (Python
  does not guarantee stable iteration order for sets across runs), which
  is the opposite of what canonicalization needs.
- `frozenset[...]` for genuine **unordered sets** where order has no
  meaning and no serialization-determinism need beyond sorting at
  serialization time (e.g. `CoverageProfile`'s tag sets,
  `EvaluationPopulation.included_cases`/`excluded_cases` -- these are
  sorted in `to_dict()` specifically because, unlike the tuple case
  above, there is no meaningful "construction order" to preserve instead).
- `types.MappingProxyType` (via `frozen_mapping` below) for genuine
  **keyed mappings** where lookup-by-key is the actual access pattern
  (e.g. `EvaluationAggregate.per_dimension`, `configuration` fields).
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class ContractValidationError(Exception):
    """Raised by a contract's `__post_init__` when constructed in an
    invalid state. First argument is a short, stable, machine-readable
    reason code (matching the `NormalizationRejected("empty_or_whitespace_only")`
    convention in core/cognitive/intent.py), not a prose message -- so
    calling code can branch on the reason without string-matching."""


def frozen_mapping(d: Mapping[str, Any] | None) -> MappingProxyType:
    """Wrap a mapping in an immutable read-only view.

    Correction pass finding: several `@dataclass(frozen=True)` contracts
    (EvaluationCase, OracleDefinition, UserSimulatorDefinition,
    EvaluationDefinition, and EvaluationAggregate's `per_dimension`) held a
    plain `dict` field. `frozen=True` prevents `obj.field = x` but does
    nothing to stop `obj.field["k"] = v` -- a real shallow-immutability
    gap on types that document themselves as immutable contract state.
    `types.MappingProxyType` is the minimal stdlib fix: a read-only view
    over a copy of the input, no third-party dependency, no generic
    immutability framework. Call this from `__post_init__` via
    `object.__setattr__(self, "field", frozen_mapping(self.field))`
    (the standard, only-option pattern for normalizing a field on an
    already-frozen dataclass instance)."""
    return MappingProxyType(dict(d) if d is not None else {})


def enum_value(e: Enum | None) -> Any:
    """Encode an enum member as its `.value`, passing None through
    unchanged. Centralized purely so every module's to_dict() doesn't
    repeat the `x.value if x is not None else None` ternary."""
    return e.value if e is not None else None


def nested(obj: Any) -> Any:
    """Encode a nested contract object via its own `to_dict()`, passing
    None through unchanged. Any object without a `to_dict()` is returned
    as-is (covers plain str/int/float/bool/None leaf fields)."""
    if obj is None:
        return None
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return obj


def nested_list(objs: Any) -> Any:
    """`nested()` applied element-wise; None passes through as None
    (distinct from an empty list -- §20's known/unknown/not_applicable
    distinction applies to collections too, not just scalar fields)."""
    if objs is None:
        return None
    return [nested(o) for o in objs]
