"""Tests for core/cognitive/user_model.py — Packet 05, K4.2.7 User
Cognitive Model.

Architecture: OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md
§3, §11, §15.
"""
import ast
import inspect
from typing import Any, Dict, List

import pytest

from core.cognitive import user_model as user_model_module
from core.cognitive.user_model import (
    ALL_MODEL_FIELDS,
    BEHAVIORAL_PATTERNS,
    COMMUNICATION_STYLE,
    EXPERTISE,
    NAMESPACE_PREFIX,
    PREFERRED_ABSTRACTION_LEVEL,
    PREFERRED_OUTPUT_FORMATS,
    RECURRING_OBJECTIVES,
    TERMINOLOGY_PREFERENCES,
    UserCognitiveModelProjection,
    assemble_user_cognitive_model,
    cross_instance_excluded_metadata,
    delete_user_model_entry,
    list_user_model_entries,
    procedure_name_for,
)
from core.memory.knowledge_entry import KnowledgeEntry


# ─────────────────────────────────────────────────────────────────────────
# Test doubles
# ─────────────────────────────────────────────────────────────────────────

class MockMemory:
    """Minimal UnifiedMemory double: pre-configured per-layer entry lists,
    and a recording delete()."""

    def __init__(self, l1=None, l3=None):
        self._layers = {"l1": l1 or [], "l3": l3 or []}
        self.delete_calls: List[Dict[str, Any]] = []
        self.get_layer_calls: List[str] = []

    async def get_layer(self, layer, limit=100, min_importance=0.0):
        self.get_layer_calls.append(layer)
        return self._layers.get(layer, [])

    async def delete(self, entry_id, reason="", worker_id=""):
        self.delete_calls.append(
            {"entry_id": entry_id, "reason": reason, "worker_id": worker_id}
        )
        return True


def _entry(content, procedure_name=None, metadata=None, confidence=1.0,
           updated_at=0.0, entry_id=None):
    kwargs = dict(content=content, procedure_name=procedure_name,
                  metadata=metadata or {}, confidence=confidence,
                  updated_at=updated_at)
    if entry_id is not None:
        kwargs["entry_id"] = entry_id
    return KnowledgeEntry(**kwargs)


# ─────────────────────────────────────────────────────────────────────────
# Namespace convention
# ─────────────────────────────────────────────────────────────────────────

class TestProcedureNameConvention:
    @pytest.mark.parametrize("model_field", sorted(ALL_MODEL_FIELDS))
    def test_procedure_name_for_known_fields(self, model_field):
        assert procedure_name_for(model_field) == f"{NAMESPACE_PREFIX}{model_field}"

    def test_procedure_name_for_unknown_field_raises(self):
        with pytest.raises(ValueError):
            procedure_name_for("not_a_real_field")

    def test_all_seven_fields_are_recognized(self):
        # K4.2 §3's illustrative field list has exactly seven entries.
        assert ALL_MODEL_FIELDS == {
            EXPERTISE, TERMINOLOGY_PREFERENCES, PREFERRED_ABSTRACTION_LEVEL,
            COMMUNICATION_STYLE, PREFERRED_OUTPUT_FORMATS,
            RECURRING_OBJECTIVES, BEHAVIORAL_PATTERNS,
        }
        assert len(ALL_MODEL_FIELDS) == 7


# ─────────────────────────────────────────────────────────────────────────
# Projection dataclass
# ─────────────────────────────────────────────────────────────────────────

class TestUserCognitiveModelProjectionDataclass:
    def test_defaults(self):
        p = UserCognitiveModelProjection()
        assert p.expertise == {}
        assert p.terminology_preferences == {}
        assert p.preferred_abstraction_level is None
        assert p.communication_style is None
        assert p.preferred_output_formats == []
        assert p.recurring_objectives == []
        assert p.behavioral_patterns == []
        assert p.source_entry_ids == []
        assert p.average_confidence is None
        assert isinstance(p.assembled_at, float)

    def test_independent_default_factories(self):
        p1, p2 = UserCognitiveModelProjection(), UserCognitiveModelProjection()
        assert p1.expertise is not p2.expertise
        assert p1.preferred_output_formats is not p2.preferred_output_formats
        assert p1.source_entry_ids is not p2.source_entry_ids


# ─────────────────────────────────────────────────────────────────────────
# assemble_user_cognitive_model
# ─────────────────────────────────────────────────────────────────────────

class TestAssembleUserCognitiveModel:
    async def test_empty_memory_yields_empty_projection(self):
        memory = MockMemory()
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.expertise == {}
        assert p.preferred_output_formats == []
        assert p.source_entry_ids == []
        assert p.average_confidence is None

    async def test_queries_both_l1_and_l3(self):
        memory = MockMemory()
        await assemble_user_cognitive_model(memory=memory)
        assert set(memory.get_layer_calls) == {"l1", "l3"}

    async def test_ignores_entries_with_no_procedure_name(self):
        memory = MockMemory(l1=[_entry("irrelevant", procedure_name=None)])
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.source_entry_ids == []

    async def test_ignores_non_user_model_procedure_names(self):
        memory = MockMemory(l3=[_entry("irrelevant", procedure_name="skill:something")])
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.source_entry_ids == []

    async def test_ignores_unrecognized_user_model_field(self):
        memory = MockMemory(l3=[_entry("irrelevant", procedure_name="user_model:not_a_real_field")])
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.source_entry_ids == []

    async def test_dict_field_populated_via_model_key(self):
        memory = MockMemory(l3=[
            _entry("intermediate", procedure_name=procedure_name_for(EXPERTISE),
                   metadata={"model_key": "python"}),
            _entry("expert", procedure_name=procedure_name_for(EXPERTISE),
                   metadata={"model_key": "cooking"}),
        ])
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.expertise == {"python": "intermediate", "cooking": "expert"}

    async def test_dict_field_entry_without_model_key_is_skipped(self):
        memory = MockMemory(l3=[
            _entry("intermediate", procedure_name=procedure_name_for(EXPERTISE), metadata={}),
        ])
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.expertise == {}
        # Still counted for provenance/confidence even though it didn't
        # populate the dict -- it IS a real User Cognitive Model entry.
        assert len(p.source_entry_ids) == 1

    async def test_list_field_accumulates_and_deduplicates(self):
        memory = MockMemory(l1=[
            _entry("markdown", procedure_name=procedure_name_for(PREFERRED_OUTPUT_FORMATS)),
        ], l3=[
            _entry("bullet_points", procedure_name=procedure_name_for(PREFERRED_OUTPUT_FORMATS)),
            _entry("markdown", procedure_name=procedure_name_for(PREFERRED_OUTPUT_FORMATS)),
        ])
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.preferred_output_formats == ["markdown", "bullet_points"]

    async def test_scalar_field_most_recent_wins_within_a_layer(self):
        memory = MockMemory(l3=[
            _entry("terse", procedure_name=procedure_name_for(COMMUNICATION_STYLE), updated_at=1.0),
            _entry("verbose", procedure_name=procedure_name_for(COMMUNICATION_STYLE), updated_at=5.0),
        ])
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.communication_style == "verbose"

    async def test_l3_beats_l1_on_conflict_even_if_l1_is_newer(self):
        # Promoted (L3) always wins over raw (L1), regardless of recency
        # -- confirmed truth beats an unvetted signal.
        memory = MockMemory(
            l1=[_entry("terse", procedure_name=procedure_name_for(COMMUNICATION_STYLE), updated_at=100.0)],
            l3=[_entry("verbose", procedure_name=procedure_name_for(COMMUNICATION_STYLE), updated_at=1.0)],
        )
        p = await assemble_user_cognitive_model(memory=memory)
        assert p.communication_style == "verbose"

    async def test_source_entry_ids_and_average_confidence(self):
        memory = MockMemory(l3=[
            _entry("markdown", procedure_name=procedure_name_for(PREFERRED_OUTPUT_FORMATS),
                   confidence=0.8, entry_id="e1"),
            _entry("bullet_points", procedure_name=procedure_name_for(PREFERRED_OUTPUT_FORMATS),
                   confidence=0.4, entry_id="e2"),
        ])
        p = await assemble_user_cognitive_model(memory=memory)
        assert set(p.source_entry_ids) == {"e1", "e2"}
        assert p.average_confidence == pytest.approx(0.6)

    async def test_is_deterministic_given_the_same_inputs(self):
        entries_l3 = [_entry("expert", procedure_name=procedure_name_for(EXPERTISE),
                              metadata={"model_key": "python"})]
        p1 = await assemble_user_cognitive_model(memory=MockMemory(l3=list(entries_l3)))
        p2 = await assemble_user_cognitive_model(memory=MockMemory(l3=list(entries_l3)))
        assert p1.expertise == p2.expertise
        assert p1.preferred_output_formats == p2.preferred_output_formats


# ─────────────────────────────────────────────────────────────────────────
# Privacy invariants
# ─────────────────────────────────────────────────────────────────────────

class TestListUserModelEntries:
    async def test_returns_only_user_model_entries_across_both_layers(self):
        memory = MockMemory(
            l1=[_entry("a", procedure_name=procedure_name_for(BEHAVIORAL_PATTERNS)),
                _entry("b", procedure_name="skill:something")],
            l3=[_entry("c", procedure_name=procedure_name_for(EXPERTISE))],
        )
        entries = await list_user_model_entries(memory=memory)
        assert {e.content for e in entries} == {"a", "c"}

    async def test_empty_when_no_user_model_entries_exist(self):
        memory = MockMemory(l1=[_entry("irrelevant", procedure_name=None)])
        entries = await list_user_model_entries(memory=memory)
        assert entries == []


class TestDeleteUserModelEntry:
    async def test_delegates_to_memory_delete(self):
        memory = MockMemory()
        result = await delete_user_model_entry("entry-123", memory=memory, reason="test")
        assert result is True
        assert memory.delete_calls == [
            {"entry_id": "entry-123", "reason": "test", "worker_id": "UserCognitiveModel"}
        ]

    async def test_default_reason_is_provided(self):
        memory = MockMemory()
        await delete_user_model_entry("entry-123", memory=memory)
        assert memory.delete_calls[0]["reason"]  # non-empty default


class TestCrossInstanceExcludedMetadata:
    def test_returns_expected_marker(self):
        assert cross_instance_excluded_metadata() == {"cross_instance_excluded": True}


# ─────────────────────────────────────────────────────────────────────────
# Architecture compliance
# ─────────────────────────────────────────────────────────────────────────

def _real_code_identifiers(source: str) -> set:
    """See tests/core/cognitive/test_planner.py / test_learning.py for
    the precedent this mirrors: names in executable positions only, not
    comments/docstrings/strings."""
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        names.add(base.id)
    return names


class TestArchitectureCompliance:
    """K4.2 §3's boundaries: no separate write path, no new governor, no
    new memory layer, no coupling to a (nonexistent) cross-instance
    mechanism anywhere in the repository."""

    def test_no_direct_memory_write_call(self):
        # K4.2 §3: "governed by the same write-path as everything else --
        # no separate, ungoverned 'personalization' backdoor." This
        # module must never call memory.write()/UnifiedMemory.write()
        # itself; writes go through validation_gate() elsewhere.
        source = inspect.getsource(user_model_module)
        identifiers = _real_code_identifiers(source)
        assert "write" not in identifiers

    def test_does_not_import_validation_gate_writer_bypass(self):
        # Confirms this module doesn't import UnifiedMemory.write directly
        # or construct KnowledgeEntry objects to insert around the gate.
        source = inspect.getsource(user_model_module)
        assert "KnowledgeEntry(" not in source

    def test_no_new_governor_class_defined(self):
        source = inspect.getsource(user_model_module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "Governor" not in base_names

    def test_no_new_memory_layer_introduced(self):
        source = inspect.getsource(user_model_module)
        identifiers = _real_code_identifiers(source)
        assert "LAYERS" not in identifiers
        assert not any(name in identifiers for name in ("L5", "l5"))

    def test_does_not_import_worker_modules(self):
        # "Dependencies should remain one-directional" -- this module
        # must not import from core.workers (Reflection/Evaluation/
        # Supervisor workers), core.cognitive.planner, or
        # core.cognitive.intent, which would create a cycle once those
        # eventually consume this module's projection. Checked via real
        # import statements (AST), not raw text -- the module docstring
        # legitimately *discusses* core.cognitive.planner in prose
        # (explaining the pre-existing, unused HintSource.USER_MODEL
        # constant) without importing it.
        tree = ast.parse(inspect.getsource(user_model_module))
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        forbidden_prefixes = ("core.workers", "core.cognitive.planner", "core.cognitive.intent")
        offending = [m for m in imported_modules if m.startswith(forbidden_prefixes)]
        assert offending == []

    def test_no_cross_instance_coupling_anywhere_in_core(self):
        # K4.2 §3: excluded from any future cross-instance advisory
        # mechanism. No such mechanism exists yet, so this checks the
        # only thing checkable today: nothing in core/ *other than this
        # module's own docstring* (which legitimately discusses the
        # invariant in prose) couples "user_model" to anything
        # "cross_instance"-named. If a future module imports user_model
        # and also references "cross_instance", this test starts failing
        # for a genuine reason.
        import core
        import pathlib
        core_dir = pathlib.Path(core.__file__).parent
        this_file = pathlib.Path(inspect.getfile(user_model_module)).resolve()
        offending = []
        for py_file in core_dir.rglob("*.py"):
            if py_file.resolve() == this_file:
                continue
            text = py_file.read_text(errors="ignore")
            if "cross_instance" in text.lower() and (
                "user_model" in text.lower() or "usercognitivemodel" in text.lower()
            ):
                offending.append(str(py_file))
        assert offending == []
