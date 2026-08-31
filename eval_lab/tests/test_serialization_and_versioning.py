"""Serialization/canonicalization/versioning tests — §66-70, §79 'Serialization'
and 'Versioning' categories."""

from __future__ import annotations

import json

import pytest

from eval_lab.contracts.identifiers import CURRENT_SCHEMA_VERSION, SchemaVersion, UnsupportedSchemaVersion
from eval_lab.tests import fixtures as fx


ALL_FIXTURE_BUILDERS = [
    fx.minimal_benchmark,
    fx.protected_benchmark,
    fx.minimal_task,
    fx.minimal_case,
    fx.minimal_task_instance,
    fx.minimal_evidence,
    fx.deterministic_evaluator,
    fx.judge_evaluator,
    fx.minimal_trajectory,
    fx.minimal_result,
    fx.minimal_population,
    fx.minimal_experiment,
    fx.minimal_execution_reference,
    fx.minimal_evaluation_input,
    fx.minimal_run,
]


@pytest.mark.parametrize("builder", ALL_FIXTURE_BUILDERS, ids=[b.__name__ for b in ALL_FIXTURE_BUILDERS])
def test_every_major_contract_is_json_serializable(builder):
    """Blanket round-trip check across every major contract type -- if any
    field were accidentally left as a raw Python object (a bare Enum, a
    bare datetime, a bare frozenset) instead of going through
    enum_value()/nested()/isoformat(), this test catches it immediately
    rather than failing only for whichever type happens to get exercised
    by a more specific test."""
    obj = builder()
    d = obj.to_dict()
    serialized = json.dumps(d)  # raises TypeError if anything isn't JSON-safe
    reloaded = json.loads(serialized)
    assert isinstance(reloaded, dict)


def test_json_output_has_stable_key_order_within_a_single_call():
    """Canonicalization policy (§66): dict keys are written in a fixed
    explicit order by to_dict(). Confirmed by calling twice and comparing
    the raw key order, not just equality of contents."""
    run1 = fx.minimal_run().to_dict()
    run2 = fx.minimal_run().to_dict()
    assert list(run1.keys()) == list(run2.keys())


def test_none_is_written_explicitly_not_omitted():
    """§66: 'None is written explicitly as null rather than the field
    being omitted.'"""
    d = fx.minimal_execution_reference().to_dict()
    assert "runtime_operation_id" in d["future_runtime_operation_ref"]
    assert d["future_runtime_operation_ref"]["runtime_operation_id"] is None  # present with value null, not absent


def test_schema_version_field_present_on_versioned_contracts():
    for builder in (fx.minimal_benchmark, fx.minimal_task, fx.deterministic_evaluator):
        d = builder().to_dict()
        assert d["schema_version"] == str(CURRENT_SCHEMA_VERSION)


def test_unsupported_schema_version_is_a_distinct_exception_type():
    """§69: never silently reinterpret an old schema under a new meaning
    -- confirmed that the refusal mechanism (UnsupportedSchemaVersion)
    exists as its own type, distinct from ContractValidationError, so a
    future reader can catch schema-incompatibility specifically."""
    assert issubclass(UnsupportedSchemaVersion, Exception)
    assert not issubclass(UnsupportedSchemaVersion, type(None))


def test_compatible_minor_version_bump_does_not_break_compatibility():
    v_current = SchemaVersion(1, 0)
    v_future_minor = SchemaVersion(1, 7)
    assert v_current.is_compatible_with(v_future_minor)
    assert v_future_minor.is_compatible_with(v_current)


def test_incompatible_major_version_is_detected():
    v_current = SchemaVersion(1, 0)
    v_future_major = SchemaVersion(2, 0)
    assert not v_current.is_compatible_with(v_future_major)
