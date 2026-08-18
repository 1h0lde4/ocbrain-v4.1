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
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_drift  # noqa: E402  (import after sys.path manipulation, by necessity)


def _tree(source: str) -> ast.Module:
    return ast.parse(source)


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


def test_run_all_returns_all_nine_checks_in_order():
    results = check_drift.run_all()
    assert [r.check_id for r in results] == [f"DRIFT-0{i}" for i in range(1, 10)]
    assert all(r.status in ("PASS", "VIOLATION") for r in results)


def test_run_all_against_real_repo_mechanically_certain_checks_pass():
    # DRIFT-01/02/03/04/05 are precise AST-name checks the frozen spec
    # pins down exactly (no "literal string analysis"-style heuristic
    # involved) -- these are the ones worth hard-asserting as a genuine
    # regression guard. 06/08/09 involve a documented heuristic and are
    # deliberately not hard-asserted here; 07 currently passes too but is
    # left to the JSON baseline report rather than a hard assertion,
    # since a future legitimate D7 change could plausibly need a second
    # declared exception added to DRIFT_07_EXCEPTIONS.
    results = {r.check_id: r for r in check_drift.run_all()}
    for check_id in ("DRIFT-01", "DRIFT-02", "DRIFT-03", "DRIFT-04", "DRIFT-05"):
        assert results[check_id].status == "PASS", (
            f"{check_id} unexpectedly failing against the current repo: "
            f"{results[check_id].violations}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
