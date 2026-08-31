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
