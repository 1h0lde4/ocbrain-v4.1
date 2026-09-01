"""Identity/version/hash primitive tests — §79 'Identity' category."""

from __future__ import annotations

import json

import pytest

from eval_lab.contracts import identifiers as ids


def test_new_object_id_uniqueness():
    generated = {ids.new_object_id("run") for _ in range(1000)}
    assert len(generated) == 1000, "1000 generated ids collided; uuid4-based minting should not collide at this scale"


def test_new_object_id_prefix_is_cosmetic_only():
    a = ids.new_object_id("run")
    b = ids.new_object_id("case")
    assert a.startswith("run_")
    assert b.startswith("case_")


def test_content_hash_deterministic():
    h1 = ids.content_hash(b"same content")
    h2 = ids.content_hash(b"same content")
    assert h1 == h2, "identical content must hash identically"


def test_content_hash_distinguishes_different_content():
    assert ids.content_hash(b"a") != ids.content_hash(b"b")


def test_schema_version_compatible_same_major():
    assert ids.SchemaVersion(1, 0).is_compatible_with(ids.SchemaVersion(1, 9))


def test_schema_version_incompatible_different_major():
    assert not ids.SchemaVersion(1, 0).is_compatible_with(ids.SchemaVersion(2, 0))


def test_schema_version_round_trip():
    v = ids.SchemaVersion(3, 7)
    assert ids.SchemaVersion.parse(str(v)) == v


def test_schema_version_str_format():
    assert str(ids.SchemaVersion(1, 0)) == "1.0"


def test_current_schema_version_is_json_serializable_as_string():
    assert json.loads(json.dumps(str(ids.CURRENT_SCHEMA_VERSION))) == "1.0"


def test_future_runtime_operation_ref_defaults_to_empty():
    ref = ids.FutureRuntimeOperationRef()
    assert ref.runtime_operation_id is None
    assert ref.runtime_attempt_number is None


def test_future_runtime_operation_ref_has_no_behavior_beyond_data_holding():
    """§11 (correction pass, boundary protection): this type must not
    become a parallel implementation of DEBT-015. Structurally verified,
    not just claimed in a docstring: the only methods it defines are
    dataclass-generated ones plus to_dict -- no retry logic, no identity
    resolution, nothing that could function as runtime operation-identity
    behavior."""
    allowed_methods = {
        "__init__", "__repr__", "__eq__", "__hash__", "__setattr__", "__delattr__",
        "__class__", "__dict__", "__module__", "__doc__", "__annotations__",
        "__dataclass_fields__", "__dataclass_params__", "__match_args__", "__weakref__",
        "to_dict",
    }
    own_methods = {
        name for name in vars(ids.FutureRuntimeOperationRef)
        if callable(getattr(ids.FutureRuntimeOperationRef, name, None)) or name.startswith("__")
    }
    unexpected = own_methods - allowed_methods
    assert not unexpected, (
        f"FutureRuntimeOperationRef defines unexpected method(s) {unexpected} -- "
        f"this type must remain a plain data holder, per ADR-LAB-01 §4's boundary "
        f"with DEBT-015. Adding behavior here risks it becoming a parallel, "
        f"competing implementation of runtime operation identity."
    )
