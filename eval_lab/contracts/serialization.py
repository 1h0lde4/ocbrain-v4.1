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
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ContractValidationError(Exception):
    """Raised by a contract's `__post_init__` when constructed in an
    invalid state. First argument is a short, stable, machine-readable
    reason code (matching the `NormalizationRejected("empty_or_whitespace_only")`
    convention in core/cognitive/intent.py), not a prose message -- so
    calling code can branch on the reason without string-matching."""


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
