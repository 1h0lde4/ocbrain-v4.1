"""
scripts/check_drift.py — K4.2 D10 Architecture Drift Verification (DRIFT-01..09).

Source of truth for these nine checks: `docs/architecture/implementation_plan -
K42 v1-0 FINAL PRE-FREEZE ARCHITECTURE SPECIFICATION frozen.md`, section
"Final Drift Verification Contract (Corrected)" and its "DRIFT-08 Canonical
Ownership Declarations" / "DRIFT-07 Exception" subsections. Read that section
before changing any check below — this file is a direct implementation of it,
not an independent design.

Status: this is the MINIMUM D10 baseline capability authorized ahead of full
H2 implementation (K4.2-H2 readiness plan, `docs/Bugs Hunt & fix reports/
K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md`, section 3 / D10 packet). It
exists so a "before H2" snapshot can be captured now and diffed against an
"after H2" snapshot once D3/D7/D11 land. It is deliberately NOT wired into
CI or the default pytest run yet, and does not attempt drift rules beyond
the nine the frozen spec defines — both are the D10 packet's own job.

Run with:
    python3 scripts/check_drift.py                    # JSON to stdout
    python3 scripts/check_drift.py --out FILE.json     # also write to FILE.json
    python3 scripts/check_drift.py --quiet             # suppress the stderr summary

Exit code: 0 if every check is PASS (a documented architectural exception
counts as PASS — see DRIFT-07 below); 1 if any check reports a VIOLATION.

Known limitations of this minimum baseline (not solved here on purpose):
  - DRIFT-06 (no hard-coded capability-type strings) and DRIFT-09 (no
    unauthorized shared-contract producer) are the two checks the frozen
    spec itself only describes loosely ("literal string analysis",
    "producer source analysis"). Both are implemented below as documented,
    conservative heuristics. A VIOLATION from either is a prompt for a
    human read, not proof of an actual architecture break — tighten them
    as part of the full D10 packet if they prove too noisy or too loose.
  - All checks are AST-name-based static analysis, not a type checker:
    a call routed through an aliased import or an intermediate variable
    of the same runtime type but a different static name will not be
    caught. This is the deliberate, inspectable trade-off LAW 4
    (Determinism Over Magic) implies over a heavier, less legible tool.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "core"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    file: str
    line: int
    detail: str


@dataclass
class CheckResult:
    check_id: str
    rule: str
    status: str  # "PASS" | "VIOLATION"
    violations: list[Violation] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _iter_py_files(directory: Path, *, recursive: bool) -> list[Path]:
    if not directory.exists():
        return []
    pattern = "**/*.py" if recursive else "*.py"
    return sorted(p for p in directory.glob(pattern) if p.is_file())


def _iter_core_py_files(*, exclude_tests: bool = True) -> list[Path]:
    files = _iter_py_files(CORE, recursive=True)
    if exclude_tests:
        files = [p for p in files if "tests" not in p.relative_to(REPO_ROOT).parts]
    return files


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _imported_modules(tree: ast.Module) -> list[tuple[str, int]]:
    """(dotted_module_name, lineno) for every `import x.y` / `from x.y import z`."""
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.module, node.lineno))
    return out


def _imported_names_from(tree: ast.Module, module: str) -> list[tuple[str, int]]:
    """(imported_name, lineno) for `from <module> import name [as alias]`.

    Reports the *original* name, not the local alias — DRIFT-03 cares
    whether `plan`/`compile` were imported at all, regardless of what
    they were renamed to locally.
    """
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            for alias in node.names:
                out.append((alias.name, node.lineno))
    return out


def _call_sites_for_name(tree: ast.Module, name: str) -> list[int]:
    """Line numbers of calls shaped like `name(...)` or `x.name(...)`."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == name:
            lines.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == name:
            lines.append(node.lineno)
    return lines


def _attribute_call_sites(tree: ast.Module, attr_name: str) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr_name
        ):
            lines.append(node.lineno)
    return lines


# ---------------------------------------------------------------------------
# DRIFT-01 / DRIFT-02 — forbidden imports from core/cognitive/*.py
# ---------------------------------------------------------------------------


def _forbidden_import_check(check_id: str, rule: str, forbidden_module: str) -> CheckResult:
    violations: list[Violation] = []
    for path in _iter_py_files(CORE / "cognitive", recursive=False):
        tree = _parse(path)
        if tree is None:
            continue
        for module, lineno in _imported_modules(tree):
            if module == forbidden_module or module.startswith(forbidden_module + "."):
                violations.append(Violation(_rel(path), lineno, f"imports '{module}'"))
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(check_id, rule, status, violations)


def check_drift_01() -> CheckResult:
    return _forbidden_import_check(
        "DRIFT-01",
        "core/cognitive/*.py must not import core.workflow.runtime",
        "core.workflow.runtime",
    )


def check_drift_02() -> CheckResult:
    return _forbidden_import_check(
        "DRIFT-02",
        "core/cognitive/*.py must not import core.capabilities.adapter_runtime",
        "core.capabilities.adapter_runtime",
    )


# ---------------------------------------------------------------------------
# DRIFT-03 — supervisor.py must not import plan()/compile() functions
# ---------------------------------------------------------------------------


def check_drift_03() -> CheckResult:
    path = CORE / "workers" / "supervisor.py"
    violations: list[Violation] = []
    tree = _parse(path) if path.exists() else None
    if tree is not None:
        for name, lineno in _imported_names_from(tree, "core.cognitive.planner"):
            if name == "plan":
                violations.append(
                    Violation(_rel(path), lineno, "imports plan() from core.cognitive.planner")
                )
        for name, lineno in _imported_names_from(tree, "core.cognitive.compiler"):
            if name == "compile":
                violations.append(
                    Violation(_rel(path), lineno, "imports compile() from core.cognitive.compiler")
                )
    status = "VIOLATION" if violations else "PASS"
    notes = "" if path.exists() else f"{_rel(path)} not found — check skipped, treated as PASS"
    return CheckResult(
        "DRIFT-03",
        "supervisor.py must not import plan() or compile() functions "
        "(importing CompilationResult/CompilationStatus is legitimate — a consumer, not a caller)",
        status,
        violations,
        notes,
    )


# ---------------------------------------------------------------------------
# DRIFT-04 / DRIFT-08 — canonical construction confined to declared owner
# ---------------------------------------------------------------------------

# contract class name -> declared owner file (relative to repo root)
CANONICAL_OWNERS: dict[str, str] = {
    "RawRequest": "core/cognitive/intent.py",
    "Goal": "core/cognitive/intent.py",
    "ExecutionPlan": "core/cognitive/planner.py",
    "CapabilityDiscoveryResult": "core/cognitive/planner.py",
    "CompilationResult": "core/cognitive/compiler.py",
    "OperationRecoveryBudget": "core/orchestrator.py",
}


def _ownership_violations_for(contract: str, owner_rel: str) -> list[Violation]:
    violations: list[Violation] = []
    owner_path = REPO_ROOT / owner_rel
    for path in _iter_core_py_files(exclude_tests=True):
        if path == owner_path:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for lineno in _call_sites_for_name(tree, contract):
            violations.append(
                Violation(_rel(path), lineno, f"constructs {contract}(...) outside declared owner {owner_rel}")
            )
    return violations


def check_drift_04() -> CheckResult:
    violations = _ownership_violations_for("RawRequest", CANONICAL_OWNERS["RawRequest"])
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-04", "RawRequest construction only in core/cognitive/intent.py", status, violations
    )


def check_drift_08() -> CheckResult:
    all_violations: list[Violation] = []
    for contract, owner in CANONICAL_OWNERS.items():
        all_violations.extend(_ownership_violations_for(contract, owner))
    status = "VIOLATION" if all_violations else "PASS"
    notes = (
        "Interpreted as: none of the six canonical contract dataclasses (" + ", ".join(CANONICAL_OWNERS)
        + ") may be directly constructed in production code (tests/*.py exempt) outside their "
        "declared owner file. Test doubles and compatibility adapters are exempt via the tests/ "
        "exclusion, per the spec's explicit note."
    )
    return CheckResult(
        "DRIFT-08",
        "[CORRECTED] Canonical builders not bypassed by production code outside declared owner",
        status,
        all_violations,
        notes,
    )


# ---------------------------------------------------------------------------
# DRIFT-05 — SupervisorWorker must not call GovernanceKernel.evaluate_action()
# ---------------------------------------------------------------------------


def _evaluate_action_violations(tree: ast.Module, rel: str) -> list[Violation]:
    return [
        Violation(rel, lineno, "calls .evaluate_action(...) directly")
        for lineno in _attribute_call_sites(tree, "evaluate_action")
    ]


def check_drift_05() -> CheckResult:
    path = CORE / "workers" / "supervisor.py"
    tree = _parse(path) if path.exists() else None
    violations = _evaluate_action_violations(tree, _rel(path)) if tree is not None else []
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-05",
        "SupervisorWorker must not call GovernanceKernel.evaluate_action() directly "
        "(docstring mentions are not violations — AST does not parse docstrings as calls)",
        status,
        violations,
    )


# ---------------------------------------------------------------------------
# DRIFT-06 — no hard-coded capability type strings in Planner routing
# ---------------------------------------------------------------------------


def _hardcoded_type_string_violations(tree: ast.Module, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        strings = [o for o in operands if isinstance(o, ast.Constant) and isinstance(o.value, str)]
        type_attrs = [o for o in operands if isinstance(o, ast.Attribute) and "type" in o.attr.lower()]
        if strings and type_attrs:
            violations.append(
                Violation(
                    rel,
                    node.lineno,
                    f"compares a *.{type_attrs[0].attr} attribute against string literal {strings[0].value!r}",
                )
            )
    return violations


def check_drift_06() -> CheckResult:
    path = CORE / "cognitive" / "planner.py"
    tree = _parse(path) if path.exists() else None
    violations = _hardcoded_type_string_violations(tree, _rel(path)) if tree is not None else []
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-06",
        "No hard-coded capability type strings in Planner routing",
        status,
        violations,
        notes="Heuristic (spec says only 'literal string analysis'): flags `<expr>.<...type...> == "
        "\"literal\"` comparisons in planner.py. A VIOLATION is worth a human read, not an "
        "automatic failure.",
    )


# ---------------------------------------------------------------------------
# DRIFT-07 — cognitive.* events only from core/cognitive/ or core/workers/
# ---------------------------------------------------------------------------

# (file relative to repo root, event type) pairs explicitly declared as
# architectural exceptions. Every entry here MUST be traceable to a
# specification section — see the tuple's inline comment. Never add an
# entry here to silence a violation without that justification existing.
DRIFT_07_EXCEPTIONS: set[tuple[str, str]] = {
    # D7: terminal impasse routes through Orchestrator, not Supervisor.
    # Frozen implementation plan §9 "DRIFT-07 Exception".
    ("core/orchestrator.py", "cognitive.planner_impasse_terminal"),
}


ALLOWED_COGNITIVE_EVENT_DIRS = ("core/cognitive", "core/workers")


def _cognitive_event_violations(
    tree: ast.Module, rel: str, in_allowed_dir: bool
) -> tuple[list[Violation], list[str]]:
    """Deliberately NOT keyed to a specific method name (e.g. `.append`):
    the real emission path in this codebase goes through wrapper helpers
    like `self._emit_event(...)`, not `EventStream.append(...)` directly.
    Keying off the cognitive.*-prefixed string-literal *argument* itself,
    on any call regardless of method name, is the robust signal — a first
    version of this check, keyed to `.append` alone, silently missed the
    known core/orchestrator.py cognitive.planner_impasse_terminal
    emission entirely. Caught by testing against a known-positive case,
    not by code review — see tests/test_check_drift.py.
    """
    violations: list[Violation] = []
    exceptions: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if not first.value.startswith("cognitive."):
            continue
        if in_allowed_dir:
            continue
        if (rel, first.value) in DRIFT_07_EXCEPTIONS:
            exceptions.append(f"{rel}:{node.lineno} emits {first.value!r}")
            continue
        violations.append(
            Violation(rel, node.lineno, f"emits '{first.value}' from outside core/cognitive/ or core/workers/")
        )
    return violations, exceptions


def check_drift_07() -> CheckResult:
    violations: list[Violation] = []
    exceptions_applied: list[str] = []
    for path in _iter_core_py_files(exclude_tests=True):
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        in_allowed_dir = any(rel.startswith(d + "/") for d in ALLOWED_COGNITIVE_EVENT_DIRS)
        v, e = _cognitive_event_violations(tree, rel, in_allowed_dir)
        violations.extend(v)
        exceptions_applied.extend(e)
    status = "VIOLATION" if violations else "PASS"
    notes = ""
    if exceptions_applied:
        notes = (
            "Declared architectural exception applied per D7 (frozen implementation plan "
            "\u00a79 'DRIFT-07 Exception'): " + "; ".join(exceptions_applied)
        )
    return CheckResult(
        "DRIFT-07",
        "cognitive.* events emitted only from core/cognitive/ or core/workers/ (exception: "
        "cognitive.planner_impasse_terminal from core/orchestrator.py, declared owner per D7)",
        status,
        violations,
        notes,
    )


# ---------------------------------------------------------------------------
# DRIFT-09 — no unauthorized shared-contract producer outside declared owners
# ---------------------------------------------------------------------------


def _unauthorized_producer_violations(tree: ast.Module, rel: str, owner_here: set[str]) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.returns is None:
            continue
        ret = node.returns
        ret_name = ret.id if isinstance(ret, ast.Name) else getattr(ret, "attr", None)
        if ret_name in CANONICAL_OWNERS and ret_name not in owner_here:
            violations.append(
                Violation(
                    rel,
                    node.lineno,
                    f"function '{node.name}' declares return type {ret_name}, whose canonical "
                    f"owner is {CANONICAL_OWNERS[ret_name]}",
                )
            )
    return violations


def check_drift_09() -> CheckResult:
    """Complementary to DRIFT-08.

    DRIFT-08 catches direct `ClassName(...)` construction outside the
    owner file. The frozen spec's one-line description of DRIFT-09 ("no
    unauthorized shared-contract producer") doesn't fully pin down what,
    beyond that, counts as "producing" a contract — so this is a
    documented interpretation, not a mechanical certainty: it flags a
    function defined *outside* a contract's owner file whose declared
    return-type annotation is that contract. A VIOLATION is a prompt to
    check whether the function actually constructs the object (in which
    case DRIFT-08 would independently catch it too) or only re-exports
    one it received as an argument (legitimate, and worth tightening
    this heuristic to exclude once the full D10 packet revisits it).
    """
    violations: list[Violation] = []
    for path in _iter_core_py_files(exclude_tests=True):
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        owner_here = {c for c, o in CANONICAL_OWNERS.items() if REPO_ROOT / o == path}
        violations.extend(_unauthorized_producer_violations(tree, rel, owner_here))
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-09",
        "No unauthorized shared-contract producer outside declared owners",
        status,
        violations,
        notes="Heuristic, narrower in confidence than DRIFT-08 — see this check's function "
        "docstring in scripts/check_drift.py for exactly what it does and doesn't catch.",
    )


CHECKS = [
    check_drift_01,
    check_drift_02,
    check_drift_03,
    check_drift_04,
    check_drift_05,
    check_drift_06,
    check_drift_07,
    check_drift_08,
    check_drift_09,
]


def run_all() -> list[CheckResult]:
    return [check() for check in CHECKS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=None, help="also write the JSON report to this path")
    parser.add_argument("--quiet", action="store_true", help="suppress the human-readable stderr summary")
    args = parser.parse_args(argv)

    results = run_all()
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "K4.2-H2 D10 pre-H2 architecture drift baseline",
        "source_spec": (
            "docs/architecture/implementation_plan - K42 v1-0 FINAL PRE-FREEZE ARCHITECTURE "
            "SPECIFICATION frozen.md, section 9 (Final Drift Verification Contract)"
        ),
        "checks": [r.to_dict() for r in results],
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r.status == "PASS"),
            "violation": sum(1 for r in results if r.status == "VIOLATION"),
        },
    }

    payload = json.dumps(report, indent=2)
    print(payload)

    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")

    if not args.quiet:
        for r in results:
            marker = "PASS" if r.status == "PASS" else f"VIOLATION ({len(r.violations)})"
            print(f"  {r.check_id}: {marker}", file=sys.stderr)
            if r.notes:
                print(f"      note: {r.notes}", file=sys.stderr)

    return 0 if report["summary"]["violation"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
