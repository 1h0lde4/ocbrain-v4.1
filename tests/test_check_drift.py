"""Tests for scripts/check_drift.py (K4.2 D10 minimum baseline capability).

These deliberately test the pure, tree-level helper functions against
synthetic `ast.parse()` fixtures rather than writing temp files to disk —
`check_drift.py`'s file-walking functions are tied to module-level
REPO_ROOT/CORE constants computed from `__file__`, so unit-testing the
underlying detection logic directly (which is where a real bug was found
during manual verification — see test_cognitive_event_violations_catches_
wrapper_method_not_just_append below) is both simpler and more precise
than faking a mini-repo on disk.

One integration-level test (test_run_all_against_real_repo) does exercise
run_all() against the actual repository.
"""

import ast
import errno
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_drift  # noqa: E402  (import after sys.path manipulation, by necessity)


def _tree(source: str) -> ast.Module:
    return ast.parse(source)


def _skip_if_symlink_creation_is_unsupported(exc: OSError) -> None:
    unsupported_errnos = {
        value
        for value in (
            getattr(errno, "ENOSYS", None),
            getattr(errno, "EOPNOTSUPP", None),
            getattr(errno, "ENOTSUP", None),
        )
        if value is not None
    }
    if exc.errno in unsupported_errnos:
        pytest.skip(f"Filesystem/platform does not support symlinks: {exc}")
    if sys.platform == "win32" and getattr(exc, "winerror", None) == 1314:
        pytest.skip(f"Windows symlink privilege is unavailable: {exc}")
    raise exc


# ---------------------------------------------------------------------------
# _imported_modules / _imported_names_from
# ---------------------------------------------------------------------------


def test_imported_modules_captures_plain_and_from_import():
    tree = _tree("import a.b.c\nfrom x.y import z\n")
    modules = check_drift._imported_modules(tree)
    assert ("a.b.c", 1) in modules
    assert ("x.y", 2) in modules


def test_imported_names_from_reports_original_name_not_alias():
    tree = _tree("from core.cognitive.planner import plan as p, other\n")
    names = check_drift._imported_names_from(tree, "core.cognitive.planner")
    # Must report the *original* symbol "plan", not the local alias "p" --
    # DRIFT-03 cares whether plan() was imported at all, regardless of
    # what it was renamed to locally.
    assert ("plan", 1) in names
    assert ("other", 1) in names
    assert not any(name == "p" for name, _ in names)


def test_imported_names_from_ignores_unrelated_module():
    tree = _tree("from core.cognitive.compiler import compile\n")
    assert check_drift._imported_names_from(tree, "core.cognitive.planner") == []


# ---------------------------------------------------------------------------
# _call_sites_for_name (DRIFT-04 / DRIFT-08 basis)
# ---------------------------------------------------------------------------


def test_call_sites_for_name_catches_bare_and_attribute_calls():
    tree = _tree("RawRequest(text='x')\nmod.RawRequest(text='y')\nOther(text='z')\n")
    lines = check_drift._call_sites_for_name(tree, "RawRequest")
    assert lines == [1, 2]


def test_ownership_violations_for_excludes_owner_file_only(tmp_path, monkeypatch):
    # _ownership_violations_for walks real files via _iter_core_py_files,
    # so this one test does touch disk -- confirming the "skip the
    # declared owner file itself" logic, which the pure-AST helpers above
    # can't exercise on their own.
    fake_core = tmp_path / "core"
    (fake_core / "cognitive").mkdir(parents=True)
    owner = fake_core / "cognitive" / "intent.py"
    owner.write_text("RawRequest(text='owner site, must not self-flag')\n")
    other = fake_core / "cognitive" / "other.py"
    other.write_text("RawRequest(text='violation site')\n")

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_drift, "CORE", fake_core)

    violations = check_drift._ownership_violations_for("RawRequest", "core/cognitive/intent.py")
    assert len(violations) == 1
    assert violations[0].file == "core/cognitive/other.py"


# ---------------------------------------------------------------------------
# DRIFT-05 — evaluate_action
# ---------------------------------------------------------------------------


def test_evaluate_action_violations_ignores_docstring_mentions():
    tree = _tree('"""This module must never call evaluate_action() directly."""\n')
    assert check_drift._evaluate_action_violations(tree, "core/workers/supervisor.py") == []


def test_evaluate_action_violations_catches_real_call():
    tree = _tree("gov.evaluate_action(action)\n")
    violations = check_drift._evaluate_action_violations(tree, "core/workers/supervisor.py")
    assert len(violations) == 1
    assert violations[0].line == 1


# ---------------------------------------------------------------------------
# DRIFT-06 — hard-coded capability type strings
# ---------------------------------------------------------------------------


def test_hardcoded_type_string_violations_catches_equality_check():
    tree = _tree('if capability.capability_type == "llm_completion":\n    pass\n')
    violations = check_drift._hardcoded_type_string_violations(tree, "core/cognitive/planner.py")
    assert len(violations) == 1


def test_hardcoded_type_string_violations_ignores_unrelated_comparison():
    tree = _tree('if score == 0.5:\n    pass\n')
    assert check_drift._hardcoded_type_string_violations(tree, "core/cognitive/planner.py") == []


# ---------------------------------------------------------------------------
# DRIFT-07 — cognitive.* event emission (the check that found a real bug)
# ---------------------------------------------------------------------------


def test_cognitive_event_violations_catches_wrapper_method_not_just_append():
    """Regression test.

    The first version of this check matched only `.append("cognitive....",
    ...)` calls. The real codebase emits cognitive.* events through a
    wrapper (`self._emit_event("cognitive....", {...})` in
    core/orchestrator.py), which that version silently missed --
    discovered only by running the checker against a known-positive case,
    not by reading the code. This test pins that fix in place.
    """
    tree = _tree('self._emit_event("cognitive.something_happened", {})\n')
    violations, exceptions = check_drift._cognitive_event_violations(
        tree, "core/some_other_module.py", in_allowed_dir=False
    )
    assert len(violations) == 1
    assert exceptions == []


def test_cognitive_event_violations_respects_declared_exception():
    tree = _tree('self._emit_event("cognitive.planner_impasse_terminal", {})\n')
    violations, exceptions = check_drift._cognitive_event_violations(
        tree, "core/orchestrator.py", in_allowed_dir=False
    )
    assert violations == []
    assert len(exceptions) == 1


def test_cognitive_event_violations_allows_emission_from_allowed_dir():
    tree = _tree('self._emit_event("cognitive.intent_interpreted", {})\n')
    violations, exceptions = check_drift._cognitive_event_violations(
        tree, "core/cognitive/intent.py", in_allowed_dir=True
    )
    assert violations == []
    assert exceptions == []


def test_cognitive_event_violations_ignores_non_cognitive_strings():
    tree = _tree('log.info("something unrelated")\n')
    violations, exceptions = check_drift._cognitive_event_violations(
        tree, "core/some_other_module.py", in_allowed_dir=False
    )
    assert violations == [] and exceptions == []


# ---------------------------------------------------------------------------
# DRIFT-09 — unauthorized shared-contract producer
# ---------------------------------------------------------------------------


def test_unauthorized_producer_violations_catches_foreign_return_type():
    tree = _tree("def build() -> ExecutionPlan:\n    ...\n")
    violations = check_drift._unauthorized_producer_violations(tree, "core/some_other_module.py", owner_here=set())
    assert len(violations) == 1


def test_unauthorized_producer_violations_allows_owner_file():
    tree = _tree("def plan() -> ExecutionPlan:\n    ...\n")
    violations = check_drift._unauthorized_producer_violations(
        tree, "core/cognitive/planner.py", owner_here={"ExecutionPlan", "CapabilityDiscoveryResult"}
    )
    assert violations == []


def test_unauthorized_producer_violations_ignores_unrelated_return_type():
    tree = _tree("def helper() -> int:\n    ...\n")
    assert check_drift._unauthorized_producer_violations(tree, "core/some_other_module.py", owner_here=set()) == []


# ---------------------------------------------------------------------------
# Integration: run_all() against the real repository
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DRIFT-10 — Governance boundary (Intent, Planner, and Learning)
# ---------------------------------------------------------------------------

VALID_LEARNING_PY = (
    "from core.events.event_stream import get_event_stream\n"
    "from core.governance.governance_kernel import EvolutionGovernor, GovernanceAction, GovernanceKernel, GovernanceVerdict, get_governance_kernel\n"
    "from core.memory.unified_memory import get_unified_memory\n"
    "async def validation_gate(*, tier, governance, action_type, hitl_approved=False, memory=None, event_stream=None):\n"
    "    memory = memory or get_unified_memory()\n"
    "    governance = governance or get_governance_kernel()\n"
    "    event_stream = event_stream or get_event_stream()\n"
    "    if action_type not in EvolutionGovernor.SELF_MODIFYING_ACTIONS:\n"
    "        return None\n"
    "    action = GovernanceAction(action_type=action_type, requires_approval=not hitl_approved)\n"
    "    result = governance.evaluate_action(action)\n"
    "    if result.verdict == GovernanceVerdict.ESCALATE:\n"
    "        return result\n"
    "    if result.verdict == GovernanceVerdict.REJECT:\n"
    "        return result\n"
    "    if result.verdict != GovernanceVerdict.APPROVE:\n"
    "        return result\n"
    "    entry_id = await memory.write(candidate)\n"
    "    await event_stream.append('done', {})\n"
    "    return result\n"
)


def _setup_clean_governance_files(tmp_path):
    fake_core = tmp_path / "core" / "cognitive"
    fake_core.mkdir(parents=True, exist_ok=True)
    (fake_core / "intent.py").write_text("# clean\n", encoding="utf-8")
    (fake_core / "planner.py").write_text("# clean\n", encoding="utf-8")
    (fake_core / "learning.py").write_text(VALID_LEARNING_PY, encoding="utf-8")
    return fake_core


def test_drift_10_canonical_scope_pinned():
    assert check_drift.GOVERNANCE_BOUNDARY_FILES == (
        "core/cognitive/intent.py",
        "core/cognitive/planner.py",
        "core/cognitive/learning.py",
    )


def test_drift_10_exception_scope_pinned():
    assert check_drift.DRIFT_10_EXCEPTION_SCOPES == {
        ("core/cognitive/learning.py", "validation_gate"): (
            "ValidationGate's EVOLUTION-tier promotion must pass through "
            "GovernanceKernel before writing a promoted entry."
        )
    }


def test_drift_10_trusted_governance_imports_pinned():
    assert check_drift.GOVERNANCE_TRUSTED_IMPORTS == (
        ("EvolutionGovernor", "core.governance.governance_kernel"),
        ("GovernanceAction", "core.governance.governance_kernel"),
        ("GovernanceKernel", "core.governance.governance_kernel"),
        ("GovernanceVerdict", "core.governance.governance_kernel"),
        ("get_governance_kernel", "core.governance.governance_kernel"),
        ("get_event_stream", "core.events.event_stream"),
        ("get_unified_memory", "core.memory.unified_memory"),
    )


@pytest.mark.parametrize("unsafe_module_statement", [
    "GovernanceKernel.evaluate_action = fake_evaluate\n",
    "EvolutionGovernor.SELF_MODIFYING_ACTIONS.clear()\n",
    "get_governance_kernel = lambda: FakeGovernance()\n",
])
def test_check_drift_10_rejects_module_level_governance_monkeypatches(
    tmp_path, monkeypatch, unsafe_module_statement
):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        VALID_LEARNING_PY + "\n" + unsafe_module_statement,
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert result.notes == ""
    assert any(
        "trusted governance" in v.detail
        or "EvolutionGovernor allowlist is mutated" in v.detail
        or "module-scope binding" in v.detail
        for v in result.violations
    )


def test_check_drift_10_exception_configuration_drives_enforcement_and_notes(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    custom_name = "configured_gate"
    custom_reason = "Configured exception reason used by enforcement and notes."
    (tmp_path / "core/cognitive/learning.py").write_text(
        VALID_LEARNING_PY.replace("validation_gate", custom_name),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        check_drift,
        "DRIFT_10_EXCEPTION_SCOPES",
        {("core/cognitive/learning.py", custom_name): custom_reason},
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"
    assert custom_reason in result.notes


def test_check_drift_10_passes_clean_repository(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"
    assert "ValidationGate" in result.notes


@pytest.mark.parametrize("target_file", [
    "core/cognitive/intent.py",
    "core/cognitive/planner.py",
])
def test_check_drift_10_detects_unauthorized_call_in_intent_or_planner(tmp_path, monkeypatch, target_file):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / target_file).write_text("gov.evaluate_action(action)\n", encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert len(result.violations) == 1
    assert result.violations[0].file == target_file


def test_check_drift_10_ignores_comments_and_docstrings(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/intent.py").write_text(
        '"""Docstring mentioning evaluate_action() directly."""\n# Comment calling evaluate_action()\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


# --- File Validation & Robustness Tests ---

def test_check_drift_10_fails_on_missing_file(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/intent.py").unlink()
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("does not exist" in v.detail for v in result.violations)


def test_check_drift_10_fails_on_non_regular_file(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/intent.py").unlink()
    (tmp_path / "core/cognitive/intent.py").mkdir()
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("not a regular file" in v.detail for v in result.violations)


@pytest.mark.parametrize(
    "error",
    [
        PermissionError(errno.EACCES, "permission denied"),
        OSError("unexpected error without errno"),
    ],
)
def test_symlink_creation_errors_are_not_silently_skipped(error):
    with pytest.raises(type(error)):
        _skip_if_symlink_creation_is_unsupported(error)


def test_check_drift_10_fails_on_symlink_file(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    real_file = tmp_path / "real_intent.py"
    real_file.write_text("# clean\n", encoding="utf-8")
    (tmp_path / "core/cognitive/intent.py").unlink()
    try:
        (tmp_path / "core/cognitive/intent.py").symlink_to(real_file)
    except NotImplementedError:
        pytest.skip("Platform does not implement symlink creation")
    except OSError as exc:
        _skip_if_symlink_creation_is_unsupported(exc)

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("contains symbolic link" in v.detail for v in result.violations)


def test_check_drift_10_fails_on_symlink_in_path_component(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    real_dir = tmp_path / "real_cognitive"
    real_dir.mkdir(parents=True)
    (real_dir / "intent.py").write_text("# clean\n", encoding="utf-8")

    # Replace core/cognitive directory with a symlink to real_dir
    for f in (tmp_path / "core/cognitive").iterdir():
        f.unlink()
    (tmp_path / "core/cognitive").rmdir()
    try:
        (tmp_path / "core/cognitive").symlink_to(real_dir)
    except NotImplementedError:
        pytest.skip("Platform does not implement symlink creation")
    except OSError as exc:
        _skip_if_symlink_creation_is_unsupported(exc)

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("contains symbolic link" in v.detail for v in result.violations)


def test_check_drift_10_fails_on_compile_time_scope_error(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/planner.py").write_text(
        "def invalid():\n"
        "    nonlocal missing_name\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("syntax error" in v.detail for v in result.violations)


def test_check_drift_10_rejects_tier_rebinding_before_non_evolution_write_exception(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        "    tier = LearningTier.LEARNING\n"
        "    if tier == LearningTier.LEARNING:\n"
        "        entry_id = await memory.write(candidate)\n"
        "        return result\n"
        "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("ValidationGate tier selector 'tier' is rebound or deleted" in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_rejects_global_result_binding(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    gate = VALID_LEARNING_PY.replace(
        "async def validation_gate(*, tier, governance, action_type, hitl_approved=False, memory=None, event_stream=None):\n",
        "async def validation_gate(*, tier, governance, action_type, hitl_approved=False, memory=None, event_stream=None):\n    global result\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(gate, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("governance result 'result' is rebound or deleted after/beside the approved call" in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_fails_on_syntax_error(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/planner.py").write_text("def invalid_syntax(\n", encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("syntax error" in v.detail for v in result.violations)


def test_check_drift_10_fails_on_decoding_error(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/planner.py").write_bytes(b"\x80\x81\x82\xff")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("decoding" in v.detail for v in result.violations)


def test_check_drift_10_fails_on_read_os_error(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)

    def fake_read_text(*args, **kwargs):
        raise OSError("Permission denied / disk I/O error")

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("failed to read" in v.detail for v in result.violations)


# --- ValidationGate & Exception Hardening Tests ---

def test_check_drift_10_fails_if_governance_call_removed_completely(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        "async def validation_gate(governance, action):\n"
        "    return None\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("missing or invalid required" in v.detail for v in result.violations)


def test_check_drift_10_fails_if_validation_gate_renamed_or_missing(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        "async def other_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    return result\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("missing required top-level 'validation_gate'" in v.detail for v in result.violations)


def test_check_drift_10_rejects_synchronous_validation_gate(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        "def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    return result\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("async function definition" in v.detail for v in result.violations)


def test_check_drift_10_rejects_decorated_validation_gate(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        "@some_decorator\n"
        "async def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    return result\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("must be undecorated" in v.detail for v in result.violations)


@pytest.mark.parametrize("rebind_code, expected_snippet", [
    ("validation_gate = None\n", "competing or duplicate module-scope binding"),
    ("validation_gate: int = 1\n", "competing or duplicate module-scope binding"),
    ("del validation_gate\n", "competing or duplicate module-scope binding"),
    ("from math import sin as validation_gate\n", "competing or duplicate module-scope binding"),
    ("class validation_gate: pass\n", "competing or duplicate module-scope binding"),
    ("def validation_gate(): pass\n", "competing or duplicate module-scope binding"),
    ("if True:\n    validation_gate = 123\n", "competing or duplicate module-scope binding"),
    ("try:\n    pass\nexcept Exception:\n    del validation_gate\n", "competing or duplicate module-scope binding"),
    ("for validation_gate in candidates:\n    pass\n", "competing or duplicate module-scope binding"),
    ("with provider() as validation_gate:\n    pass\n", "competing or duplicate module-scope binding"),
    ("try:\n    pass\nexcept Exception as validation_gate:\n    pass\n", "competing or duplicate module-scope binding"),
    ("if (validation_gate := None):\n    pass\n", "competing or duplicate module-scope binding"),
    ("match subject:\n    case validation_gate:\n        pass\n", "competing or duplicate module-scope binding"),
    ("import validation_gate.child\n", "competing or duplicate module-scope binding"),
    ("from some_module import *\n", "competing or duplicate module-scope binding"),
    ("validation_gate, other = (None, None)\n", "competing or duplicate module-scope binding"),
])
def test_check_drift_10_rejects_module_scope_rebinding(tmp_path, monkeypatch, rebind_code, expected_snippet):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY + "\n" + rebind_code
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    matching_binding = next(
        v for v in result.violations if expected_snippet in v.detail
    )
    assert matching_binding.line > 0


@pytest.mark.parametrize("rebind_code", [
    "def mutate():\n    global validation_gate\n    validation_gate = None\n",
    "def mutate():\n    global validation_gate\n    del validation_gate\n",
    "class Mutator:\n    global validation_gate\n    validation_gate = None\n",
    "def mutate():\n    if ready:\n        global validation_gate\n        validation_gate = replacement\n",
    "def mutate():\n    global validation_gate\n    import validation_gate.child\n",
    "def mutate():\n    global validation_gate\n    try:\n        pass\n    except Exception as validation_gate:\n        pass\n",
])
def test_check_drift_10_rejects_global_rebinding_from_nested_scope(tmp_path, monkeypatch, rebind_code):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        VALID_LEARNING_PY + "\n" + rebind_code,
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("global rebinding of 'validation_gate'" in v.detail for v in result.violations)


@pytest.mark.parametrize("nested_code", [
    "def read_gate():\n    global validation_gate\n    return validation_gate\n",
    "def use_comprehension():\n    global validation_gate\n    return [validation_gate for validation_gate in values]\n",
])
def test_check_drift_10_allows_read_only_global_and_comprehension_local_name(tmp_path, monkeypatch, nested_code):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        VALID_LEARNING_PY + "\n" + nested_code,
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


def test_check_drift_10_allows_annotation_only_without_rebinding_validation_gate(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(
        VALID_LEARNING_PY + "\nvalidation_gate: object\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


def test_check_drift_10_does_not_treat_attribute_or_subscript_targets_as_rebindings(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = (
        VALID_LEARNING_PY
        + "\nvalidation_gate.status = state\n"
        + "container[validation_gate] = item\n"
        + "del validation_gate.status\n"
        + "del container[validation_gate]\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


def test_check_drift_10_does_not_treat_async_for_inside_async_function_as_module_binding(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = (
        VALID_LEARNING_PY
        + "\nasync def unrelated():\n"
        + "    async for validation_gate in stream:\n"
        + "        pass\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


def test_check_drift_10_allows_function_local_assignments_named_validation_gate(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = (
        VALID_LEARNING_PY
        + "\ndef other_func():\n"
        + "    validation_gate = 42\n"
        + "    return validation_gate\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


# --- Call Shape & Placement Tests ---

@pytest.mark.parametrize("call_code, expected_snippet", [
    ("result = other_gov.evaluate_action(action)", "missing or invalid required"),
    ("result = governance.other_method(action)", "missing or invalid required"),
    ("result = governance.evaluate_action(action, extra)", "missing or invalid required"),
    ("result = governance.evaluate_action(action, kw=1)", "missing or invalid required"),
    ("other_target = governance.evaluate_action(action)", "missing or invalid required"),
    ("governance.evaluate_action(action)", "missing or invalid required"),
])
def test_check_drift_10_rejects_altered_call_shape(tmp_path, monkeypatch, call_code, expected_snippet):
    _setup_clean_governance_files(tmp_path)
    code = (
        "async def validation_gate(governance, action):\n"
        f"    {call_code}\n"
        "    return None\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any(expected_snippet in v.detail for v in result.violations)


def test_check_drift_10_rejects_nested_statement_placement(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = (
        "async def validation_gate(governance, action):\n"
        "    if True:\n"
        "        result = governance.evaluate_action(action)\n"
        "    return result\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("missing or invalid required" in v.detail for v in result.violations)


def test_check_drift_10_rejects_wrapped_or_lambda_call(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = (
        "async def validation_gate(governance, action):\n"
        "    fn = lambda: governance.evaluate_action(action)\n"
        "    return fn()\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("missing or invalid required" in v.detail for v in result.violations)


@pytest.mark.parametrize("early_exit_stmt", [
    "return None",
    "raise ValueError('early exit')",
    "if True:\n        return None",
    "if True:\n        raise ValueError('constant-condition early exit')",
    "if False:\n        pass\n    else:\n        return None",
])
def test_check_drift_10_rejects_early_exit_paths_before_call(tmp_path, monkeypatch, early_exit_stmt):
    _setup_clean_governance_files(tmp_path)
    code = (
        "async def validation_gate(governance, action):\n"
        f"    {early_exit_stmt}\n"
        "    result = governance.evaluate_action(action)\n"
        "    return result\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("can be bypassed by an earlier return/raise path" in v.detail for v in result.violations)


@pytest.mark.parametrize("unsafe_code", [
    (
        "async def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    return True\n"
    ),
    (
        "async def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    if result.verdict == GovernanceVerdict.ESCALATE:\n"
        "        return result\n"
        "    if result.verdict == GovernanceVerdict.REJECT:\n"
        "        return result\n"
        "    if result.verdict != GovernanceVerdict.APPROVE:\n"
        "        return result\n"
        "    result = FakeApproval()\n"
        "    return result\n"
    ),
    (
        "async def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    if result.verdict == GovernanceVerdict.ESCALATE:\n"
        "        return result\n"
        "    if result.verdict == GovernanceVerdict.REJECT:\n"
        "        return result\n"
        "    return result\n"
    ),
    (
        "async def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    result = FakeApproval()\n"
        "    if result.verdict == GovernanceVerdict.ESCALATE:\n"
        "        return result\n"
        "    if result.verdict == GovernanceVerdict.REJECT:\n"
        "        return result\n"
        "    return result\n"
    ),
    (
        "async def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    if result.verdict == GovernanceVerdict.ESCALATE:\n"
        "        pass\n"
        "    if result.verdict == GovernanceVerdict.REJECT:\n"
        "        return result\n"
        "    return result\n"
    ),
    (
        "async def validation_gate(governance, action):\n"
        "    result = governance.evaluate_action(action)\n"
        "    if result.verdict == GovernanceVerdict.ESCALATE:\n"
        "        return memory.write(candidate)\n"
        "    if result.verdict == GovernanceVerdict.REJECT:\n"
        "        return result\n"
        "    return result\n"
    ),
])
def test_check_drift_10_rejects_governance_result_bypass_shapes(tmp_path, monkeypatch, unsafe_code):
    _setup_clean_governance_files(tmp_path)
    (tmp_path / "core/cognitive/learning.py").write_text(unsafe_code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("governance result must immediately drive terminal ESCALATE/REJECT guards, reject every non-APPROVE verdict, preserve the evaluated result, and constrain memory writes to the authorized paths" in v.detail for v in result.violations)
    assert result.notes == ""  # A failed result-flow contract must not claim the exception applied.


@pytest.mark.parametrize("inserted_statement, expected_detail", [
    (
        "    await memory.write(candidate)\n",
        "memory.write(...) occurs before the required GovernanceKernel evaluation",
    ),
    (
        "    if enabled:\n        await memory.write(candidate)\n",
        "memory.write(...) occurs before the required GovernanceKernel evaluation",
    ),
])
def test_check_drift_10_rejects_pre_governance_memory_writes(
    tmp_path, monkeypatch, inserted_statement, expected_detail
):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        inserted_statement + "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any(expected_detail in v.detail for v in result.violations)


def test_check_drift_10_allows_terminal_adaptation_write_before_evolution_governance(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        "    if tier == LearningTier.ADAPTATION:\n"
        "        entry_id = await memory.write(candidate)\n"
        "        return result\n"
        "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


def test_check_drift_10_allows_terminal_learning_write_before_evolution_governance(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        "    if tier == LearningTier.LEARNING:\n"
        "        entry_id = await memory.write(candidate)\n"
        "        await event_stream.append('cognitive.pattern_learned', {})\n"
        "        return result\n"
        "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


@pytest.mark.parametrize("inserted_statement", [
    "    mutate_memory(memory)\n",
    "    store = memory\n    mutate_memory(store)\n",
    "    store = (memory,)\n    mutate_memory(store[0])\n",
])
def test_check_drift_10_rejects_unapproved_memory_object_escape(
    tmp_path, monkeypatch, inserted_statement
):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        inserted_statement + "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("memory object is passed to an unapproved helper" in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_rejects_memory_alias_inside_call_containing_rhs(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        "    store = [memory for _ in factory()]\n"
        "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("memory object is passed to an unapproved helper" in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_allows_exact_contradiction_reader_memory_argument(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        "    contradiction = await _find_contradiction(content_domain, candidate_content, memory)\n"
        "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


@pytest.mark.parametrize("inserted_statement", [
    "    writer = memory.write\n    await writer(candidate)\n",
    "    store = memory\n    await store.write(candidate)\n",
    "    writer = getattr(memory, 'write')\n    await writer(candidate)\n",
    "    writer = memory.__getattribute__('write')\n    await writer(candidate)\n",
    "    writer = memory.__dict__['write']\n    await writer(candidate)\n",
    "    writer = vars(memory)['write']\n    await writer(candidate)\n",
    "    writer = memory.__dict__.get('write')\n    await writer(candidate)\n",
    "    writer = vars(memory).get('write')\n    await writer(candidate)\n",
    "    writer = memory.__dict__.setdefault('write', None)\n    await writer(candidate)\n",
])
def test_check_drift_10_rejects_write_aliases_before_governance(tmp_path, monkeypatch, inserted_statement):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        inserted_statement + "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("memory.write(...) occurs before the required GovernanceKernel evaluation" in v.detail for v in result.violations)


@pytest.mark.parametrize("unsafe_tail", [
    "    result.verdict = GovernanceVerdict.APPROVE\n",
    "    result.__dict__[\"verdict\"] = GovernanceVerdict.APPROVE\n",
    "    setattr(result, \"verdict\", GovernanceVerdict.APPROVE)\n",
    "    alias = result\n    alias.verdict = GovernanceVerdict.APPROVE\n",
    "    alias = (result,)\n    alias[0].verdict = GovernanceVerdict.APPROVE\n",
    "    mutate_result(result)\n",
    "    def get_result():\n        return result\n    alias = get_result()\n    alias.verdict = GovernanceVerdict.APPROVE\n",
])
def test_check_drift_10_rejects_governance_result_mutation_and_escape(
    tmp_path, monkeypatch, unsafe_tail
):
    _setup_clean_governance_files(tmp_path)
    valid_prefix = VALID_LEARNING_PY.rsplit("    return result\n", 1)[0]
    code = (
        valid_prefix
        + unsafe_tail
        + "    entry_id = await memory.write(candidate)\n"
        + "    return result\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any(
        "governance result object is mutated or escapes its verified scope" in v.detail
        for v in result.violations
    )
    assert result.notes == ""


def test_check_drift_10_allows_nested_read_only_scalar_result_access(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    await event_stream.append('done', {})\n",
        "    def read_reason():\n"
        "        return result.reason\n"
        "    await event_stream.append('done', {})\n",
        1,
    ).replace("    return result\n", "    return None\n", 1)
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


@pytest.mark.parametrize("unsafe_statement", [
    "    memory = FakeMemory()\n",
    "    governance = FakeGovernance()\n",
    "    event_stream = FakeEventStream()\n",
    "    hitl_approved = True\n",
])
@pytest.mark.parametrize("unsafe_statement, expected_detail", [
    (
        "    def alter_tier():\n"
        "        nonlocal tier\n"
        "        tier = LearningTier.LEARNING\n"
        "    alter_tier()\n",
        "tier selector 'tier' is rebound",
    ),
    (
        "    def forge_approval():\n"
        "        nonlocal hitl_approved\n"
        "        hitl_approved = True\n"
        "    forge_approval()\n",
        "caller-supplied 'hitl_approved' input is rebound",
    ),
    (
        "    def replace_kernel():\n"
        "        nonlocal governance\n"
        "        governance = FakeGovernance()\n"
        "    replace_kernel()\n",
        "dependency 'governance' is rebound",
    ),
    (
        "    def change_action_type():\n"
        "        nonlocal action_type\n"
        "        action_type = 'unregistered'\n"
        "    change_action_type()\n",
        "action_type is rebound",
    ),
])
def test_check_drift_10_rejects_nested_nonlocal_control_rebinding(
    tmp_path, monkeypatch, unsafe_statement, expected_detail
):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        unsafe_statement + "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any(expected_detail in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_rejects_dependency_or_approval_input_rebinding(
    tmp_path, monkeypatch, unsafe_statement
):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        unsafe_statement + "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any(
        "is rebound or deleted" in v.detail
        or "caller-supplied 'hitl_approved' input" in v.detail
        for v in result.violations
    )
    assert result.notes == ""


@pytest.mark.parametrize("unsafe_statement", [
    "    action.requires_approval = False\n",
    "    alias = action\n    alias.requires_approval = False\n",
    "    mutate_action(action)\n",
])
def test_check_drift_10_rejects_governance_action_mutation_or_escape(
    tmp_path, monkeypatch, unsafe_statement
):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        unsafe_statement + "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("GovernanceAction is mutated, aliased, or passed to unapproved code" in v.detail for v in result.violations)
    assert result.notes == ""


@pytest.mark.parametrize("unsafe_statement", [
    "    governance.evaluate_action = fake_evaluate\n",
    "    alias = governance\n    mutate_governance(alias)\n",
    "    mutate_governance(governance)\n",
])
def test_check_drift_10_rejects_governance_dependency_mutation_or_escape(
    tmp_path, monkeypatch, unsafe_statement
):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        unsafe_statement + "    result = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any(
        "GovernanceKernel dependency is mutated, aliased, or passed to unapproved code"
        in v.detail for v in result.violations
    )
    assert result.notes == ""


def test_check_drift_10_rejects_false_action_requires_approval(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "requires_approval=not hitl_approved",
        "requires_approval=False",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("requires_approval=not hitl_approved" in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_rejects_action_type_rebinding_after_allowlist(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    action = GovernanceAction(",
        "    action_type = 'unregistered_action'\n"
        "    action = GovernanceAction(",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("action_type is rebound after its EvolutionGovernor allowlist check" in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_requires_hitl_approval_default_false(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace("hitl_approved=False", "hitl_approved=True", 1)
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("hitl_approved' must default to False" in v.detail for v in result.violations)
    assert result.notes == ""


def test_check_drift_10_rejects_result_rebinding_after_approval_guards(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.rsplit("    return result\n", 1)[0] + (
        "    result = FakeApproval()\n"
        "    return result\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("governance result 'result' is rebound" in v.detail for v in result.violations)


def test_check_drift_10_rejects_unapproved_memory_write_after_guards(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    entry_id = await memory.write(candidate)\n",
        "    await memory.write(candidate)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("post-approval memory.write(...) must be the direct" in v.detail for v in result.violations)


def test_check_drift_10_rejects_multiple_memory_writes_after_guards(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.rsplit("    return result\n", 1)[0] + (
        "    entry_id = await memory.write(candidate)\n"
        "    second_entry = await memory.write(unsafe_candidate)\n"
        "    return result\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("more than one memory.write(...)" in v.detail for v in result.violations)


def test_check_drift_10_rejects_additional_call_elsewhere_in_learning(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = (
        VALID_LEARNING_PY +
        "\ndef unauthorized_helper(governance, action):\n"
        "    return governance.evaluate_action(action)\n"
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert len(result.violations) == 1
    assert result.violations[0].file == "core/cognitive/learning.py"


def test_check_drift_10_rejects_duplicate_call_inside_validation_gate(tmp_path, monkeypatch):
    _setup_clean_governance_files(tmp_path)
    code = VALID_LEARNING_PY.replace(
        "    result = governance.evaluate_action(action)\n",
        "    result = governance.evaluate_action(action)\n"
        "    dup = governance.evaluate_action(action)\n",
        1,
    )
    (tmp_path / "core/cognitive/learning.py").write_text(code, encoding="utf-8")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert any("calls .evaluate_action(...) directly" in v.detail for v in result.violations)
    assert result.notes == ""


# ---------------------------------------------------------------------------
# DRIFT-11 — Frozen entrypoints (interpret_request/plan/compile)
# ---------------------------------------------------------------------------


def test_frozen_entrypoint_violations_catches_unauthorized_importer(tmp_path, monkeypatch):
    fake_core = tmp_path / "core" / "workers"
    fake_core.mkdir(parents=True)
    (fake_core / "rogue.py").write_text("from core.cognitive.planner import plan\n")

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_drift, "CORE", tmp_path / "core")

    violations = check_drift._frozen_entrypoint_violations("plan", "core.cognitive.planner", "core/orchestrator.py")
    assert len(violations) == 1
    assert violations[0].file == "core/workers/rogue.py"


def test_frozen_entrypoint_violations_allows_the_authorized_caller(tmp_path, monkeypatch):
    fake_core = tmp_path / "core"
    fake_core.mkdir(parents=True)
    (fake_core / "orchestrator.py").write_text("from core.cognitive.planner import plan\n")

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_drift, "CORE", fake_core)

    violations = check_drift._frozen_entrypoint_violations("plan", "core.cognitive.planner", "core/orchestrator.py")
    assert violations == []


def test_frozen_entrypoint_violations_ignores_unrelated_imports_from_same_module():
    # Importing the *data types* (not the callable) from the same module
    # must never be flagged -- this is what makes DRIFT-11 not blanket-
    # forbid every import from core.cognitive.planner.
    tree = _tree("from core.cognitive.planner import ExecutionPlan\n")
    names = check_drift._imported_names_from(tree, "core.cognitive.planner")
    assert not any(name == "plan" for name, _ in names)


# ---------------------------------------------------------------------------
# DRIFT-12 — Recovery authority (shadow OperationRecoveryBudget)
# ---------------------------------------------------------------------------


def test_recovery_authority_violations_catches_full_shadow_surface():
    tree = _tree(
        "class SneakyBudget:\n"
        "    def consume(self): ...\n"
        "    @property\n"
        "    def remaining(self): ...\n"
        "    @property\n"
        "    def exhausted(self): ...\n"
    )
    violations = check_drift._recovery_authority_violations(tree, "core/workers/rogue.py")
    assert len(violations) == 1
    assert "SneakyBudget" in violations[0].detail


def test_recovery_authority_violations_ignores_partial_surface():
    # Only 2 of the 3 members -- not a confident enough signal to flag.
    tree = _tree(
        "class RetryPolicy:\n"
        "    def consume(self): ...\n"
        "    @property\n"
        "    def remaining(self): ...\n"
    )
    assert check_drift._recovery_authority_violations(tree, "core/workflow/definition.py") == []


def test_recovery_authority_violations_exempts_operation_recovery_budget_by_name():
    tree = _tree(
        "class OperationRecoveryBudget:\n"
        "    def consume(self): ...\n"
        "    @property\n"
        "    def remaining(self): ...\n"
        "    @property\n"
        "    def exhausted(self): ...\n"
    )
    # Even called from a file other than its declared owner, the class
    # named OperationRecoveryBudget itself is never the shadow -- DRIFT-08
    # already covers *construction* elsewhere; this check is about a
    # *different-named* class re-implementing the same shape.
    assert check_drift._recovery_authority_violations(tree, "core/some_other_module.py") == []


# ---------------------------------------------------------------------------
# DRIFT-13 — Architecture markers (RECONCILE-PENDING)
# ---------------------------------------------------------------------------


def _write_marker_fixture(tmp_path, *, marker_present: bool, known_issues_text: str = ""):
    arch_dir = tmp_path / "docs" / "architecture"
    arch_dir.mkdir(parents=True)
    content = "# Architecture\n" + ("[RECONCILE-PENDING] still open\n" if marker_present else "# resolved\n")
    (arch_dir / "OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md").write_text(content)
    (tmp_path / "KNOWN_ISSUES.md").write_text(known_issues_text)


def test_check_drift_13_passes_when_marker_still_present(tmp_path, monkeypatch):
    _write_marker_fixture(tmp_path, marker_present=True)
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_13()
    assert result.status == "PASS"


def test_check_drift_13_passes_when_marker_removed_with_recorded_resolution(tmp_path, monkeypatch):
    _write_marker_fixture(
        tmp_path, marker_present=False,
        known_issues_text="~~DEBT-011 — reconciled~~ **Resolved (date):** done.\n",
    )
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_13()
    assert result.status == "PASS"


def test_check_drift_13_fails_when_marker_silently_removed(tmp_path, monkeypatch):
    """The dangerous case this check exists for: the marker is just gone,
    with no corresponding record of a deliberate resolution."""
    _write_marker_fixture(tmp_path, marker_present=False, known_issues_text="unrelated content\n")
    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    result = check_drift.check_drift_13()
    assert result.status == "VIOLATION"
    assert len(result.violations) == 1


# ---------------------------------------------------------------------------
# DRIFT-14 — Multi-site canonical construction (PlannerRequest)
# ---------------------------------------------------------------------------


def test_ownership_violations_for_multi_allows_both_declared_sites(tmp_path, monkeypatch):
    fake_core = tmp_path / "core"
    (fake_core / "cognitive").mkdir(parents=True)
    (fake_core / "cognitive" / "planner.py").write_text("PlannerRequest(goal_id='x')\n")
    (fake_core / "orchestrator.py").write_text("PlannerRequest(goal_id='y')\n")

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_drift, "CORE", fake_core)

    violations = check_drift._ownership_violations_for_multi(
        "PlannerRequest", {"core/cognitive/planner.py", "core/orchestrator.py"}
    )
    assert violations == []


def test_ownership_violations_for_multi_catches_a_third_site(tmp_path, monkeypatch):
    fake_core = tmp_path / "core"
    (fake_core / "cognitive").mkdir(parents=True)
    (fake_core / "cognitive" / "planner.py").write_text("PlannerRequest(goal_id='x')\n")
    (fake_core / "orchestrator.py").write_text("PlannerRequest(goal_id='y')\n")
    (fake_core / "cognitive" / "rogue.py").write_text("PlannerRequest(goal_id='z')\n")

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_drift, "CORE", fake_core)

    violations = check_drift._ownership_violations_for_multi(
        "PlannerRequest", {"core/cognitive/planner.py", "core/orchestrator.py"}
    )
    assert len(violations) == 1
    assert violations[0].file == "core/cognitive/rogue.py"


# ---------------------------------------------------------------------------
# DRIFT-15 — Forbidden diagnostic transport (EventBus vs. EventStream)
# ---------------------------------------------------------------------------


def test_forbidden_transport_violations_catches_cognitive_event_via_emit():
    tree = _tree('bus.emit("cognitive.something_happened", {})\n')
    violations = check_drift._forbidden_transport_violations(tree, "core/some_module.py")
    assert len(violations) == 1


def test_forbidden_transport_violations_ignores_legitimate_eventbus_usage():
    # A non-cognitive.*-prefixed .emit(...) call is exactly what EventBus is
    # for (module.*/learning.*/kb.*/brain.* events) -- must not be flagged.
    tree = _tree('bus.emit("module.promoted", {})\n')
    assert check_drift._forbidden_transport_violations(tree, "core/model_router.py") == []


def test_forbidden_transport_violations_ignores_correct_transport_method():
    # The real EventStream path (.append(...)/._emit_event(...)) is a
    # different method name entirely -- not this check's concern (DRIFT-07
    # already covers where those calls may legitimately originate from).
    tree = _tree('self._emit_event("cognitive.something_happened", {})\n')
    assert check_drift._forbidden_transport_violations(tree, "core/orchestrator.py") == []


# ---------------------------------------------------------------------------
# Integration: run_all() against the real repository (updated for DRIFT-15)
# ---------------------------------------------------------------------------


def test_run_all_returns_all_fifteen_checks_in_order():
    results = check_drift.run_all()
    expected_ids = [f"DRIFT-0{i}" for i in range(1, 10)] + [f"DRIFT-{i}" for i in range(10, 16)]
    assert [r.check_id for r in results] == expected_ids
    assert all(r.status in ("PASS", "VIOLATION") for r in results)


def test_run_all_against_real_repo_mechanically_certain_checks_pass():
    # DRIFT-01/02/03/04/05 are precise AST-name checks the frozen spec
    # pins down exactly (no "literal string analysis"-style heuristic
    # involved) -- these are the ones worth hard-asserting as a genuine
    # regression guard. 06/08/09 involve a documented heuristic and are
    # deliberately not hard-asserted here; 07 currently passes too but is
    # left to the JSON baseline report rather than a hard assertion,
    # since a future legitimate D7 change could plausibly need a second
    # declared exception added to DRIFT_07_EXCEPTIONS. DRIFT-10..15 (K4.2-H2
    # D10) are equally precise/mechanical (no documented heuristic caveat)
    # and are hard-asserted here for the same reason 01-05 are.
    results = {r.check_id: r for r in check_drift.run_all()}
    for check_id in (
        "DRIFT-01", "DRIFT-02", "DRIFT-03", "DRIFT-04", "DRIFT-05",
        "DRIFT-10", "DRIFT-11", "DRIFT-12", "DRIFT-13", "DRIFT-14", "DRIFT-15",
    ):
        assert results[check_id].status == "PASS", (
            f"{check_id} unexpectedly failing against the current repo: "
            f"{results[check_id].violations}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
