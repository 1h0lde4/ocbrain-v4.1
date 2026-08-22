"""
scripts/check_drift.py — K4.2 D10 Architecture Drift Verification (DRIFT-01..15).

Source of truth for DRIFT-01..09: `docs/architecture/implementation_plan -
K42 v1-0 FINAL PRE-FREEZE ARCHITECTURE SPECIFICATION frozen.md`, section
"Final Drift Verification Contract (Corrected)" and its "DRIFT-08 Canonical
Ownership Declarations" / "DRIFT-07 Exception" subsections. Read that section
before changing any of those nine checks below — they are a direct
implementation of it, not an independent design.

Source of truth for DRIFT-10..15: `docs/architecture/h2_packets/
D10_ARCHITECTURE_DRIFT_ENFORCEMENT.md` (the full D10 enforcement-area list,
D10-A through D10-J). Not every D10-lettered area gets a new numbered check
below — D10-D (Capability/Adapter boundary) is already DRIFT-02, and D10-F
(diagnostic emission) is already DRIFT-07; both are confirmed, not
reimplemented. D10-H (deep semantic equivalence of frozen contracts) is
explicitly out of scope for a static checker — construction-confinement
(DRIFT-04/08/10/14) is what a tool like this can honestly claim, and that
limitation is documented rather than papered over with a fragile heuristic.
D10-I (packet ownership) is CI-integration, not a new drift rule — see
.github/workflows/ci.yml, which calls scripts/check_packet_ownership.py
directly rather than reimplementing its logic here.

  DRIFT-10  Governance boundary, broadened: Intent Interpretation and
            Planner must not call GovernanceKernel.evaluate_action()
            directly (DRIFT-05's existing check, unmodified, still covers
            SupervisorWorker only — this is a new, separate check, not a
            rewrite of it).
  DRIFT-11  Frozen entrypoints: interpret_request()/plan()/compile() are
            importable as *callables* only from core/orchestrator.py in
            production code (the one confirmed caller — repository-wide
            search performed before writing this check, not assumed).
  DRIFT-12  Recovery authority: no class outside core/cognitive/recovery.py
            (other than OperationRecoveryBudget itself) may define all
            three of consume()/remaining/exhausted — that exact trio is
            OperationRecoveryBudget's real public surface, confirmed by
            reading core/cognitive/recovery.py directly. Verified this
            does not collide with RetryPolicy (core/workflow/definition.py),
            a legitimate, differently-shaped config dataclass with no such
            methods.
  DRIFT-13  Architecture markers: the RECONCILE-PENDING marker in
            OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md
            must not silently disappear without KNOWN_ISSUES.md's DEBT-011
            being recorded as resolved.
  DRIFT-14  Multi-site canonical construction: PlannerRequest (confirmed by
            direct search to be a real class with two genuine production
            construction sites, core/cognitive/planner.py and
            core/orchestrator.py — not the single-owner shape DRIFT-08
            assumes) may not be constructed anywhere else.
  DRIFT-15  Forbidden diagnostic transport: core/event_bus.py's EventBus is
            a genuinely separate, pre-existing, non-overlapping pub/sub
            mechanism (module.*/learning.*/kb.*/brain.* events; confirmed
            by reading its full event catalogue and every call site, zero
            cognitive.* usage found) — this check exists to keep it that
            way, not because it is currently violated. Any bus.emit(...)
            call passing a cognitive.*-prefixed string is a violation.

Status: DRIFT-01..09 were the MINIMUM D10 baseline capability authorized
ahead of full H2 implementation (K4.2-H2 readiness plan, `docs/Bugs Hunt &
fix reports/K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md`, section 3 / D10
packet); DRIFT-10..15 are the full D10 enforcement layer, added once D3/D7/
D11/D12 were all integrated onto main and could be verified against
directly rather than assumed. This file is now wired into CI (see
.github/workflows/ci.yml) and IS the default architecture-verification
gate for pushes/PRs — no longer "not wired into CI yet."

Run with:
    python3 scripts/check_drift.py                    # JSON to stdout
    python3 scripts/check_drift.py --out FILE.json     # also write to FILE.json
    python3 scripts/check_drift.py --quiet             # suppress the stderr summary

Exit code: 0 if every check is PASS (a documented architectural exception
counts as PASS — see DRIFT-07 below); 1 if any check reports a VIOLATION.

Known limitations (not solved here on purpose):
  - DRIFT-06 (no hard-coded capability-type strings) and DRIFT-09 (no
    unauthorized shared-contract producer) are the two DRIFT-01..09 checks
    the frozen spec itself only describes loosely ("literal string
    analysis", "producer source analysis"). Both are implemented below as
    documented, conservative heuristics. A VIOLATION from either is a
    prompt for a human read, not proof of an actual architecture break.
  - All checks are AST-name-based static analysis, not a type checker:
    a call routed through an aliased import or an intermediate variable
    of the same runtime type but a different static name will not be
    caught. This is the deliberate, inspectable trade-off LAW 4
    (Determinism Over Magic) implies over a heavier, less legible tool.
  - DRIFT-10..15 are new, narrowly-scoped structural rules, not proof of
    semantic correctness — see each check's own docstring for exactly
    what it does and doesn't catch, and D10-H's note above for why deep
    semantic equivalence is deliberately not attempted.
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
    # D10-A (K4.2-H2 D10): CapabilityDiscoveryRequest has two production
    # construction sites (build_capability_discovery_request()'s own
    # definition, and a per-step construction inside _decompose()) --
    # both confirmed to be inside core/cognitive/planner.py itself, so
    # this fits the existing single-owner-file shape exactly and simply
    # extends this dict, rather than needing PlannerRequest's separate
    # multi-site treatment below (see MULTI_SITE_CANONICAL_OWNERS).
    "CapabilityDiscoveryRequest": "core/cognitive/planner.py",
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
        f"Interpreted as: none of the {len(CANONICAL_OWNERS)} canonical contract dataclasses ("
        + ", ".join(CANONICAL_OWNERS)
        + ") may be directly constructed in production code (tests/*.py exempt) outside their "
        "declared owner file. Test doubles and compatibility adapters are exempt via the tests/ "
        "exclusion, per the spec's explicit note. (K4.2-H2 D10: grown from 6 to "
        f"{len(CANONICAL_OWNERS)} entries — see CANONICAL_OWNERS' own inline comment for what "
        "was added and why; the count here is computed, not hand-copied, specifically so it "
        "cannot go stale again the way the original 'six' description would have the moment "
        "this dict grew.)"
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


# ---------------------------------------------------------------------------
# DRIFT-10 — Governance boundary broadened: Intent Interpretation and
# Planner must not call GovernanceKernel.evaluate_action() directly.
# (K4.2-H2 D10-C. DRIFT-05 above is unmodified and still independently
# covers SupervisorWorker — this is additive, not a replacement.)
# ---------------------------------------------------------------------------


GOVERNANCE_BOUNDARY_FILES: tuple[str, ...] = (
    "core/cognitive/intent.py",
    "core/cognitive/planner.py",
)


def check_drift_10() -> CheckResult:
    violations: list[Violation] = []
    for rel in GOVERNANCE_BOUNDARY_FILES:
        path = REPO_ROOT / rel
        tree = _parse(path) if path.exists() else None
        if tree is not None:
            violations.extend(_evaluate_action_violations(tree, rel))
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-10",
        "Intent Interpretation and Planner must not call "
        "GovernanceKernel.evaluate_action() directly (Governance sits at the "
        "compilation boundary only — extends DRIFT-05's same check, which "
        "independently still covers SupervisorWorker, to these two files)",
        status,
        violations,
    )


# ---------------------------------------------------------------------------
# DRIFT-11 — Frozen entrypoints: interpret_request()/plan()/compile() are
# importable as callables only from their one confirmed production caller.
# (K4.2-H2 D10-B. Generalizes DRIFT-03's exact pattern, which only ever
# checked supervisor.py against plan/compile, to all three entrypoints and
# to production code generally.)
# ---------------------------------------------------------------------------

# entrypoint function name -> (defining module, sole authorized-caller file).
# Established by direct repository search before writing this check: every
# production import of these three names *as callables* (not as the data
# types ExecutionPlan/CompilationResult/CompilationStatus/Goal, which are
# legitimately imported much more widely) goes through core/orchestrator.py.
FROZEN_ENTRYPOINTS: dict[str, tuple[str, str]] = {
    "interpret_request": ("core.cognitive.intent", "core/orchestrator.py"),
    "plan": ("core.cognitive.planner", "core/orchestrator.py"),
    "compile": ("core.cognitive.compiler", "core/orchestrator.py"),
}


def _frozen_entrypoint_violations(name: str, module: str, authorized_rel: str) -> list[Violation]:
    violations: list[Violation] = []
    authorized_path = REPO_ROOT / authorized_rel
    for path in _iter_core_py_files(exclude_tests=True):
        if path == authorized_path:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for imported_name, lineno in _imported_names_from(tree, module):
            if imported_name == name:
                violations.append(
                    Violation(
                        _rel(path), lineno,
                        f"imports {name}() from {module} — only {authorized_rel} is an "
                        f"authorized caller of this cognitive entrypoint",
                    )
                )
    return violations


def check_drift_11() -> CheckResult:
    violations: list[Violation] = []
    for name, (module, authorized_rel) in FROZEN_ENTRYPOINTS.items():
        violations.extend(_frozen_entrypoint_violations(name, module, authorized_rel))
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-11",
        "interpret_request()/plan()/compile() importable as callables only "
        "from core/orchestrator.py in production code (importing the data "
        "types they return — Goal/ExecutionPlan/CompilationResult/"
        "CompilationStatus — is unrestricted; this checks the callables only)",
        status,
        violations,
    )


# ---------------------------------------------------------------------------
# DRIFT-12 — Recovery authority: no shadow OperationRecoveryBudget.
# (K4.2-H2 D10-E.)
# ---------------------------------------------------------------------------

# OperationRecoveryBudget's real public surface (core/cognitive/recovery.py):
# two properties and one method. Confirmed by direct reading, not assumed.
RECOVERY_BUDGET_OWNER = "core/cognitive/recovery.py"
RECOVERY_BUDGET_SURFACE = {"consume", "remaining", "exhausted"}


def _recovery_authority_violations(tree: ast.Module, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name == "OperationRecoveryBudget":
            continue
        member_names = {
            item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if RECOVERY_BUDGET_SURFACE <= member_names:
            violations.append(
                Violation(
                    rel, node.lineno,
                    f"class '{node.name}' defines all of consume()/remaining/exhausted — "
                    f"the exact OperationRecoveryBudget surface — outside its declared owner "
                    f"{RECOVERY_BUDGET_OWNER}. This is either a second recovery authority or a "
                    f"legitimate wrapper/adapter that should delegate to the real "
                    f"OperationRecoveryBudget rather than re-implementing its shape.",
                )
            )
    return violations


def check_drift_12() -> CheckResult:
    violations: list[Violation] = []
    owner_path = REPO_ROOT / RECOVERY_BUDGET_OWNER
    for path in _iter_core_py_files(exclude_tests=True):
        if path == owner_path:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        violations.extend(_recovery_authority_violations(tree, _rel(path)))
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-12",
        "No class outside core/cognitive/recovery.py (other than "
        "OperationRecoveryBudget itself) may define all three of "
        "consume()/remaining/exhausted — that exact trio is a strong, narrow "
        "signal of a shadow recovery authority. Does not flag RetryPolicy "
        "(core/workflow/definition.py) or any other config-only dataclass, "
        "since neither defines this method/property trio.",
        status,
        violations,
    )


# ---------------------------------------------------------------------------
# DRIFT-13 — Architecture markers must not silently disappear.
# (K4.2-H2 D10-J.)
# ---------------------------------------------------------------------------

ARCHITECTURE_MARKER = "RECONCILE-PENDING"
ARCHITECTURE_MARKER_FILE = "docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md"
ARCHITECTURE_MARKER_RESOLUTION_FILE = "KNOWN_ISSUES.md"
ARCHITECTURE_MARKER_RESOLUTION_TOKEN = "DEBT-011"


def check_drift_13() -> CheckResult:
    marker_path = REPO_ROOT / ARCHITECTURE_MARKER_FILE
    marker_present = marker_path.exists() and ARCHITECTURE_MARKER in marker_path.read_text(encoding="utf-8")
    if marker_present:
        return CheckResult(
            "DRIFT-13",
            f"'{ARCHITECTURE_MARKER}' marker in {ARCHITECTURE_MARKER_FILE} must not silently "
            f"disappear without a recorded resolution",
            "PASS",
            [],
            notes=f"Marker still present in {ARCHITECTURE_MARKER_FILE} — open, as expected.",
        )
    resolution_path = REPO_ROOT / ARCHITECTURE_MARKER_RESOLUTION_FILE
    resolution_text = resolution_path.read_text(encoding="utf-8") if resolution_path.exists() else ""
    # A resolved DEBT entry in this codebase's own established convention is
    # struck through, e.g. "~~DEBT-011 — ...~~ **Resolved (date):**" — look
    # for the token appearing at all near strikethrough/Resolved language,
    # rather than requiring one exact phrasing.
    resolved = ARCHITECTURE_MARKER_RESOLUTION_TOKEN in resolution_text and (
        f"~~{ARCHITECTURE_MARKER_RESOLUTION_TOKEN}" in resolution_text
        or "Resolved" in resolution_text
    )
    if resolved:
        return CheckResult(
            "DRIFT-13",
            f"'{ARCHITECTURE_MARKER}' marker in {ARCHITECTURE_MARKER_FILE} must not silently "
            f"disappear without a recorded resolution",
            "PASS",
            [],
            notes=(
                f"Marker absent from {ARCHITECTURE_MARKER_FILE}, but "
                f"{ARCHITECTURE_MARKER_RESOLUTION_FILE} records {ARCHITECTURE_MARKER_RESOLUTION_TOKEN} "
                f"as resolved — treated as a deliberate, documented resolution, not a silent deletion."
            ),
        )
    return CheckResult(
        "DRIFT-13",
        f"'{ARCHITECTURE_MARKER}' marker in {ARCHITECTURE_MARKER_FILE} must not silently "
        f"disappear without a recorded resolution",
        "VIOLATION",
        [Violation(
            ARCHITECTURE_MARKER_FILE, 0,
            f"marker is absent and {ARCHITECTURE_MARKER_RESOLUTION_FILE} does not record "
            f"{ARCHITECTURE_MARKER_RESOLUTION_TOKEN} as resolved — looks like a silent deletion",
        )],
    )


# ---------------------------------------------------------------------------
# DRIFT-14 — Multi-site canonical construction: PlannerRequest.
# (K4.2-H2 D10-A. PlannerRequest has two genuine production construction
# sites in different files — core/cognitive/planner.py's own internal
# builder, and core/orchestrator.py preparing its call into plan() — so it
# does not fit CANONICAL_OWNERS' single-owner-file shape. Confirmed by
# direct repository search before writing this check, not assumed.)
# ---------------------------------------------------------------------------

MULTI_SITE_CANONICAL_OWNERS: dict[str, set[str]] = {
    "PlannerRequest": {"core/cognitive/planner.py", "core/orchestrator.py"},
}


def _ownership_violations_for_multi(contract: str, owner_rels: set[str]) -> list[Violation]:
    violations: list[Violation] = []
    owner_paths = {REPO_ROOT / o for o in owner_rels}
    for path in _iter_core_py_files(exclude_tests=True):
        if path in owner_paths:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for lineno in _call_sites_for_name(tree, contract):
            violations.append(
                Violation(
                    _rel(path), lineno,
                    f"constructs {contract}(...) outside its declared owner files "
                    f"({', '.join(sorted(owner_rels))})",
                )
            )
    return violations


def check_drift_14() -> CheckResult:
    all_violations: list[Violation] = []
    for contract, owners in MULTI_SITE_CANONICAL_OWNERS.items():
        all_violations.extend(_ownership_violations_for_multi(contract, owners))
    status = "VIOLATION" if all_violations else "PASS"
    return CheckResult(
        "DRIFT-14",
        "PlannerRequest constructed only in core/cognitive/planner.py or "
        "core/orchestrator.py (its two genuine production sites — an "
        "internal builder and the entrypoint's caller preparing its own "
        "call; complementary to DRIFT-08's single-owner-file checks, for "
        "the one canonical contract that doesn't fit that shape)",
        status,
        all_violations,
    )


# ---------------------------------------------------------------------------
# DRIFT-15 — Forbidden diagnostic transport: cognitive.* events must never
# be routed through core/event_bus.py's EventBus.
# (K4.2-H2 D10-G. EventBus is a genuinely separate, legitimate mechanism
# for module/learning/kb/brain lifecycle events — confirmed by reading its
# full event catalogue and every call site before writing this check; this
# exists to keep it that way, not because it is currently violated.)
# ---------------------------------------------------------------------------


def _forbidden_transport_violations(tree: ast.Module, rel: str) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "emit"):
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.startswith("cognitive."):
            violations.append(
                Violation(rel, node.lineno, f"emits '{first.value}' via a .emit(...) call — "
                                             f"EventStream's own emission path uses .append(...)/"
                                             f"_emit_event(...), not .emit(...); this looks like "
                                             f"EventBus, the wrong transport for a cognitive.* event")
            )
    return violations


def check_drift_15() -> CheckResult:
    violations: list[Violation] = []
    for path in _iter_py_files(REPO_ROOT / "core", recursive=True):
        if "tests" in path.relative_to(REPO_ROOT).parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        violations.extend(_forbidden_transport_violations(tree, _rel(path)))
    status = "VIOLATION" if violations else "PASS"
    return CheckResult(
        "DRIFT-15",
        "No cognitive.* event is ever passed to a .emit(...) call (EventBus's "
        "method — the legitimate cognitive.* transport, EventStream, is "
        "reached via .append(...)/_emit_event(...) only)",
        status,
        violations,
    )


CHECKS += [
    check_drift_10,
    check_drift_11,
    check_drift_12,
    check_drift_13,
    check_drift_14,
    check_drift_15,
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
        "purpose": "K4.2-H2 D10 full architecture drift enforcement (post-H2-integration)",
        "source_spec": (
            "DRIFT-01..09: docs/architecture/implementation_plan - K42 v1-0 FINAL PRE-FREEZE "
            "ARCHITECTURE SPECIFICATION frozen.md, section 9 (Final Drift Verification Contract). "
            "DRIFT-10..15: docs/architecture/h2_packets/D10_ARCHITECTURE_DRIFT_ENFORCEMENT.md."
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
