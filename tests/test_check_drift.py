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


# ---------------------------------------------------------------------------
# DRIFT-10 — Governance boundary broadened (Intent + Planner)
# ---------------------------------------------------------------------------


def test_check_drift_10_catches_violation_in_either_governed_file(tmp_path, monkeypatch):
    fake_core = tmp_path / "core" / "cognitive"
    fake_core.mkdir(parents=True)
    (fake_core / "intent.py").write_text("gov.evaluate_action(action)\n")
    (fake_core / "planner.py").write_text("# clean\n")

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_drift, "GOVERNANCE_BOUNDARY_FILES",
        ("core/cognitive/intent.py", "core/cognitive/planner.py"),
    )
    result = check_drift.check_drift_10()
    assert result.status == "VIOLATION"
    assert len(result.violations) == 1
    assert result.violations[0].file == "core/cognitive/intent.py"


def test_check_drift_10_passes_when_neither_file_calls_evaluate_action(tmp_path, monkeypatch):
    fake_core = tmp_path / "core" / "cognitive"
    fake_core.mkdir(parents=True)
    (fake_core / "intent.py").write_text("# no governance calls here\n")
    (fake_core / "planner.py").write_text('"""mentions evaluate_action() only in a docstring."""\n')

    monkeypatch.setattr(check_drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_drift, "GOVERNANCE_BOUNDARY_FILES",
        ("core/cognitive/intent.py", "core/cognitive/planner.py"),
    )
    result = check_drift.check_drift_10()
    assert result.status == "PASS"


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
