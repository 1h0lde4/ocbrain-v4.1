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

  DRIFT-10  Governance boundary: direct evaluate_action() calls in Intent
            Interpretation and Planner are forbidden; learning.py is also
            checked, with one structurally pinned ValidationGate exception
            for the required Evolution-tier approval check. DRIFT-05 remains
            unchanged and still independently covers SupervisorWorker.
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
# DRIFT-10 — Governance boundary: scan Intent, Planner, and Learning.
# (K4.2-H2 D10-C. DRIFT-05 remains unchanged and independently covers
# SupervisorWorker. The one legitimate Learning-tier approval call is
# structurally scoped below; it must not become a file-wide exemption.)
# ---------------------------------------------------------------------------


GOVERNANCE_BOUNDARY_FILES: tuple[str, ...] = (
    "core/cognitive/intent.py",
    "core/cognitive/planner.py",
    "core/cognitive/learning.py",
)

# The EVOLUTION-tier ValidationGate call is required by PROJECT_INSTRUCTIONS.md
# §13 ("no autonomous evolution may bypass approval"). This exception allows
# exactly one governance.evaluate_action(action) call in the top-level
# validation_gate() function; any additional call or different call shape is
# reported. The scope remains name-based so unrelated additions to learning.py
# are still checked.
DRIFT_10_EXCEPTION_SCOPES: dict[tuple[str, str], str] = {
    (
        "core/cognitive/learning.py",
        "validation_gate",
    ): (
        "ValidationGate's EVOLUTION-tier promotion must pass through "
        "GovernanceKernel before writing a promoted entry."
    ),
}

GOVERNANCE_TRUSTED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("EvolutionGovernor", "core.governance.governance_kernel"),
    ("GovernanceAction", "core.governance.governance_kernel"),
    ("GovernanceKernel", "core.governance.governance_kernel"),
    ("GovernanceVerdict", "core.governance.governance_kernel"),
    ("get_governance_kernel", "core.governance.governance_kernel"),
    ("get_event_stream", "core.events.event_stream"),
    ("get_unified_memory", "core.memory.unified_memory"),
)

TRUSTED_POLICY_CLASSES: tuple[str, ...] = ("LearningTier", "ContentDomain")
TRUSTED_POLICY_VALUES: dict[str, dict[str, object]] = {
    "LearningTier": {
        "LEARNING": "learning",
        "ADAPTATION": "adaptation",
        "EVOLUTION": "evolution",
        "ALL": ("LEARNING", "ADAPTATION", "EVOLUTION"),
    },
    "ContentDomain": {
        "SKILL": "skill",
        "INTENT_ONTOLOGY": "intent_ontology",
        "USER_MODEL": "user_model",
        "ALL": ("SKILL", "INTENT_ONTOLOGY", "USER_MODEL"),
    },
}


def _module_scope_named_exprs(node: ast.AST):
    """Yield assignment expressions evaluated in module scope, not nested bodies."""
    if isinstance(node, ast.NamedExpr):
        yield node

    # Definition bodies execute in their own namespaces. Their headers, however,
    # are evaluated in the containing scope and can contain assignment expressions.
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        header_nodes = [*node.decorator_list, node.args]
        if node.returns is not None:
            header_nodes.append(node.returns)
        header_nodes.extend(getattr(node, "type_params", ()))
        for child in header_nodes:
            yield from _module_scope_named_exprs(child)
        return
    if isinstance(node, ast.ClassDef):
        header_nodes = [*node.decorator_list, *node.bases, *node.keywords]
        header_nodes.extend(getattr(node, "type_params", ()))
        for child in header_nodes:
            yield from _module_scope_named_exprs(child)
        return
    if isinstance(node, ast.Lambda):
        # Lambda defaults execute in the containing scope; its body does not.
        yield from _module_scope_named_exprs(node.args)
        return

    for child in ast.iter_child_nodes(node):
        yield from _module_scope_named_exprs(child)


def _target_binds_name(
    target: ast.AST, name: str, *, deleting: bool = False
) -> bool:
    """Check actual Name targets, without mistaking attribute/index references for binds."""
    expected_context = ast.Del if deleting else ast.Store
    if isinstance(target, ast.Name):
        return target.id == name and isinstance(target.ctx, expected_context)
    if isinstance(target, ast.Starred):
        return _target_binds_name(target.value, name, deleting=deleting)
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(
            _target_binds_name(element, name, deleting=deleting)
            for element in target.elts
        )
    # Attribute and subscript targets can contain Names in Load context; those
    # Names are references, not bindings of the module-level name being checked.
    return False


def _pattern_binds_name(pattern: ast.AST, name: str) -> bool:
    """Find capture names in structural-pattern-matching patterns."""
    if isinstance(pattern, ast.MatchAs) and pattern.name == name:
        return True
    if isinstance(pattern, ast.MatchStar) and pattern.name == name:
        return True
    if isinstance(pattern, ast.MatchMapping) and pattern.rest == name:
        return True
    return any(
        _pattern_binds_name(child, name)
        for child in ast.iter_child_nodes(pattern)
    )


def _first_unconditional_return_or_raise(node: ast.AST) -> ast.Return | ast.Raise | None:
    """Find unconditional early exits, without misclassifying tier-dependent branches."""
    if isinstance(node, (ast.Return, ast.Raise)):
        return node
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return None
    # Only descend through an if-statement when a literal condition selects the
    # branch with certainty. Arbitrary conditions are domain control flow in
    # ValidationGate (including legitimate non-Evolution exits), not proof of a
    # governance bypass.
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Constant):
        return None
    selected_body = node.body if bool(node.test.value) else node.orelse
    for stmt in selected_body:
        found = _first_unconditional_return_or_raise(stmt)
        if found is not None:
            return found
    return None


def _global_scope_writes_for_name(scope: ast.AST, name: str) -> list[ast.AST]:
    """Find actual writes to a name declared global in this lexical scope.

    Nested function/class bodies are analyzed independently because each has
    its own symbol table. Definition headers are still visited in the enclosing
    scope because decorators, bases, and defaults execute where the definition
    statement appears. Read-only global declarations do not count as rebinding.
    """
    if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []

    class _ScopeVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.global_declared = False
            self.writes: list[ast.AST] = []

        def visit_Global(self, node: ast.Global) -> None:
            if name in node.names:
                self.global_declared = True

        def visit_Name(self, node: ast.Name) -> None:
            if node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)):
                self.writes.append(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            # Without a value, an annotation does not write the name. Still
            # visit the annotation expression, which is evaluated in this scope.
            self.visit(node.annotation)
            if node.value is not None:
                self.visit(node.target)
                self.visit(node.value)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == name:
                self.writes.append(node)
            # These expressions execute in the current scope. The function body
            # and its symbol declarations belong to the nested function scope.
            for expression in (
                *node.decorator_list,
                *node.args.defaults,
                *(x for x in node.args.kw_defaults if x is not None),
                *(arg.annotation for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs) if arg.annotation is not None),
            ):
                self.visit(expression)
            if node.args.vararg and node.args.vararg.annotation is not None:
                self.visit(node.args.vararg.annotation)
            if node.args.kwarg and node.args.kwarg.annotation is not None:
                self.visit(node.args.kwarg.annotation)
            if node.returns is not None:
                self.visit(node.returns)
            for type_param in getattr(node, "type_params", ()):
                self.visit(type_param)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == name:
                self.writes.append(node)
            # Evaluate these in the containing scope, but do not enter the
            # class body; it has its own namespace and is checked independently.
            for expression in (*node.decorator_list, *node.bases, *node.keywords):
                self.visit(expression)
            for type_param in getattr(node, "type_params", ()):
                self.visit(type_param)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            # Lambda defaults execute in this scope; the body has lambda-local
            # assignment-expression semantics and no global declaration syntax.
            for expression in (
                *node.args.defaults,
                *(x for x in node.args.kw_defaults if x is not None),
            ):
                self.visit(expression)

        def visit_ListComp(self, node: ast.ListComp) -> None:
            self.visit_comprehension_for_named_exprs(node)

        def visit_SetComp(self, node: ast.SetComp) -> None:
            self.visit_comprehension_for_named_exprs(node)

        def visit_DictComp(self, node: ast.DictComp) -> None:
            self.visit_comprehension_for_named_exprs(node)

        def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
            self.visit_comprehension_for_named_exprs(node)

        def visit_comprehension_for_named_exprs(self, node: ast.AST) -> None:
            # Comprehension iteration targets are local to the comprehension.
            # PEP 572 assignment expressions are the exception: their target is
            # bound in the containing scope, so inspect those specifically.
            for named_expr in _module_scope_named_exprs(node):
                if _target_binds_name(named_expr.target, name):
                    self.writes.append(named_expr)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if bound == name:
                    self.writes.append(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                if alias.name == "*" or (alias.asname or alias.name) == name:
                    self.writes.append(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name == name:
                self.writes.append(node)
            if node.type is not None:
                self.visit(node.type)
            for statement in node.body:
                self.visit(statement)

        def visit_Match(self, node: ast.Match) -> None:
            self.visit(node.subject)
            for case in node.cases:
                if _pattern_binds_name(case.pattern, name):
                    self.writes.append(case.pattern)
                if case.guard is not None:
                    self.visit(case.guard)
                for statement in case.body:
                    self.visit(statement)

    visitor = _ScopeVisitor()
    for statement in scope.body:
        visitor.visit(statement)
    if not visitor.global_declared:
        return []
    return visitor.writes


def _find_module_scope_bindings_for_name(
    tree: ast.Module, name: str
) -> list[tuple[ast.AST, str]]:
    """Return actual or potentially name-binding module-scope statements."""
    bindings: list[tuple[ast.AST, str]] = []
    type_alias_type = getattr(ast, "TypeAlias", None)

    def record(node: ast.AST, description: str) -> None:
        bindings.append((node, description))

    def _visit_stmts(body: list[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if stmt.name == name:
                    kind = (
                        "async function"
                        if isinstance(stmt, ast.AsyncFunctionDef)
                        else ("function" if isinstance(stmt, ast.FunctionDef) else "class")
                    )
                    record(stmt, f"{kind} definition '{name}'")
            elif isinstance(stmt, ast.Assign):
                if any(_target_binds_name(target, name) for target in stmt.targets):
                    record(stmt, f"assignment to '{name}'")
            elif isinstance(stmt, ast.AnnAssign):
                # An annotation without a value records metadata but does not
                # bind/replace the module-level name.
                if stmt.value is not None and _target_binds_name(stmt.target, name):
                    record(stmt, f"annotated assignment to '{name}'")
            elif isinstance(stmt, ast.AugAssign):
                if _target_binds_name(stmt.target, name):
                    record(stmt, f"augmented assignment to '{name}'")
            elif isinstance(stmt, ast.Delete):
                if any(_target_binds_name(target, name, deleting=True) for target in stmt.targets):
                    record(stmt, f"deletion of '{name}'")
            elif isinstance(stmt, ast.For):
                if _target_binds_name(stmt.target, name):
                    record(stmt, f"loop target binding '{name}'")
            elif isinstance(stmt, ast.AsyncFor):
                if _target_binds_name(stmt.target, name):
                    record(stmt, f"async loop target binding '{name}'")
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    if item.optional_vars is not None and _target_binds_name(item.optional_vars, name):
                        record(stmt, f"context-manager target binding '{name}'")
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    # An unaliased dotted import binds only its first component.
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    if bound == name:
                        record(stmt, f"import binding '{name}'")
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    if alias.name == "*":
                        # A star import could overwrite the protected name; fail closed.
                        record(stmt, f"star import may bind '{name}'")
                    else:
                        bound = alias.asname or alias.name
                        if bound == name:
                            record(stmt, f"import-from binding '{name}'")
            elif type_alias_type is not None and isinstance(stmt, type_alias_type):
                if _target_binds_name(stmt.name, name):
                    record(stmt, f"type-alias binding '{name}'")

            # These suites execute in the module namespace. Recurse into them,
            # while deliberately not traversing function or class bodies.
            if isinstance(stmt, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                _visit_stmts(stmt.body)
                _visit_stmts(stmt.orelse)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                _visit_stmts(stmt.body)
            elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                _visit_stmts(stmt.body)
                for handler in stmt.handlers:
                    if handler.name == name:
                        record(handler, f"exception-handler target binding '{name}'")
                    _visit_stmts(handler.body)
                _visit_stmts(stmt.orelse)
                _visit_stmts(stmt.finalbody)
            elif isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    if _pattern_binds_name(case.pattern, name):
                        record(case.pattern, f"pattern-capture binding '{name}'")
                    _visit_stmts(case.body)

    # Assignment expressions bind in the surrounding scope, including in module
    # conditions, loop headers, decorators/defaults, and comprehension expressions.
    for named_expr in _module_scope_named_exprs(tree):
        if _target_binds_name(named_expr.target, name):
            record(named_expr, f"assignment-expression binding '{name}'")

    _visit_stmts(tree.body)

    # A nested scope can mutate the module binding only when it explicitly
    # declares the name global and actually writes/deletes it. Read-only
    # globals and comprehension-local iteration targets remain permitted.
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        scope_kind = (
            "class" if isinstance(scope, ast.ClassDef)
            else "async function" if isinstance(scope, ast.AsyncFunctionDef)
            else "function"
        )
        for writer in _global_scope_writes_for_name(scope, name):
            bindings.append((
                writer,
                f"global rebinding of '{name}' from {scope_kind} scope",
            ))

    bindings.sort(key=lambda item: getattr(item[0], "lineno", 0))
    return bindings


def _scope_name_writes(scope: ast.AST, name: str) -> list[ast.AST]:
    """Find writes to a local name in one function scope, excluding nested bodies."""
    if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []

    class _ScopeVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.writes: list[ast.AST] = []

        def visit_Name(self, node: ast.Name) -> None:
            if node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)):
                self.writes.append(node)

        def visit_Global(self, node: ast.Global) -> None:
            if name in node.names:
                self.writes.append(node)

        def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
            if name in node.names:
                self.writes.append(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            self.visit(node.annotation)
            if node.value is not None:
                self.visit(node.target)
                self.visit(node.value)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == name:
                self.writes.append(node)
            # Headers execute in the containing scope; the body does not.
            for expr in (
                *node.decorator_list,
                node.args,
                *((node.returns,) if node.returns is not None else ()),
                *getattr(node, "type_params", ()),
            ):
                self.visit(expr)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == name:
                self.writes.append(node)
            for expr in (*node.decorator_list, *node.bases, *node.keywords, *getattr(node, "type_params", ())):
                self.visit(expr)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            # Lambda defaults execute here; its body has a distinct local scope.
            self.visit(node.args)

        def visit_ListComp(self, node: ast.ListComp) -> None:
            for gen in node.generators:
                self.visit(gen.iter)
                for condition in gen.ifs:
                    self.visit(condition)
            self.visit(node.elt)

        def visit_SetComp(self, node: ast.SetComp) -> None:
            for gen in node.generators:
                self.visit(gen.iter)
                for condition in gen.ifs:
                    self.visit(condition)
            self.visit(node.elt)

        def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
            for gen in node.generators:
                self.visit(gen.iter)
                for condition in gen.ifs:
                    self.visit(condition)
            self.visit(node.elt)

        def visit_DictComp(self, node: ast.DictComp) -> None:
            for gen in node.generators:
                self.visit(gen.iter)
                for condition in gen.ifs:
                    self.visit(condition)
            self.visit(node.key)
            self.visit(node.value)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                if (alias.asname or alias.name.split(".", 1)[0]) == name:
                    self.writes.append(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                if alias.name == "*" or (alias.asname or alias.name) == name:
                    self.writes.append(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name == name:
                self.writes.append(node)
            if node.type is not None:
                self.visit(node.type)
            for statement in node.body:
                self.visit(statement)

        def visit_Match(self, node: ast.Match) -> None:
            self.visit(node.subject)
            for case in node.cases:
                if _pattern_binds_name(case.pattern, name):
                    self.writes.append(case.pattern)
                if case.guard is not None:
                    self.visit(case.guard)
                for statement in case.body:
                    self.visit(statement)

    visitor = _ScopeVisitor()
    for statement in scope.body:
        visitor.visit(statement)

    # Nested closures/classes can explicitly target this scope's variables with
    # a nonlocal declaration. The visitor deliberately skips nested bodies for
    # ordinary local writes, so fail closed on any cross-scope declaration of
    # the protected name. The current ValidationGate has no legitimate need to
    # mutate its policy inputs/results from a nested lexical scope.
    for nested_node in ast.walk(scope):
        if (
            nested_node is not scope
            and isinstance(nested_node, ast.Nonlocal)
            and name in nested_node.names
        ):
            visitor.writes.append(nested_node)
    return visitor.writes


def _contains_name_reference(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(child, ast.Name) and child.id == name
        for child in ast.walk(node)
    )


def _is_approved_contradiction_read(call: ast.Call) -> bool:
    """Whitelist only the exact read-only contradiction helper call in this gate."""
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == "_find_contradiction"
        and len(call.args) == 3
        and not call.keywords
        and isinstance(call.args[2], ast.Name)
        and call.args[2].id == "memory"
        and not _contains_name_reference(call.args[0], "memory")
        and not _contains_name_reference(call.args[1], "memory")
    )


def _is_default_dependency_initialization(
    statement: ast.stmt, name: str, provider_name: str
) -> bool:
    """Recognize only the exact name = name or provider() initialization."""
    return (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == name
        and isinstance(statement.value, ast.BoolOp)
        and isinstance(statement.value.op, ast.Or)
        and len(statement.value.values) == 2
        and isinstance(statement.value.values[0], ast.Name)
        and statement.value.values[0].id == name
        and isinstance(statement.value.values[1], ast.Call)
        and isinstance(statement.value.values[1].func, ast.Name)
        and statement.value.values[1].func.id == provider_name
        and not statement.value.values[1].args
        and not statement.value.values[1].keywords
    )


def _is_approved_action_construction(statement: ast.stmt) -> bool:
    """Require the action approval bit to be derived from the caller's HITL flag."""
    if not (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == "action"
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "GovernanceAction"
        and not statement.value.args
    ):
        return False
    keywords = {kw.arg: kw.value for kw in statement.value.keywords if kw.arg is not None}
    required = keywords.get("requires_approval")
    return (
        isinstance(keywords.get("action_type"), ast.Name)
        and keywords["action_type"].id == "action_type"
        and isinstance(required, ast.UnaryOp)
        and isinstance(required.op, ast.Not)
        and isinstance(required.operand, ast.Name)
        and required.operand.id == "hitl_approved"
    )


def _is_action_type_allowlist_guard(statement: ast.stmt) -> bool:
    test = statement.test if isinstance(statement, ast.If) else None
    return (
        isinstance(statement, ast.If)
        and not statement.orelse
        and len(statement.body) == 1
        and isinstance(statement.body[0], ast.Return)
        and isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "action_type"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.NotIn)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Attribute)
        and isinstance(test.comparators[0].value, ast.Name)
        and test.comparators[0].value.id == "EvolutionGovernor"
        and test.comparators[0].attr == "SELF_MODIFYING_ACTIONS"
    )


def _argument_default_is_false(function: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    positional = [*function.args.posonlyargs, *function.args.args]
    positional_start = len(positional) - len(function.args.defaults)
    for index, argument in enumerate(positional):
        if argument.arg == name:
            default_index = index - positional_start
            return (
                0 <= default_index < len(function.args.defaults)
                and isinstance(function.args.defaults[default_index], ast.Constant)
                and function.args.defaults[default_index].value is False
            )
    for argument, default in zip(function.args.kwonlyargs, function.args.kw_defaults):
        if argument.arg == name:
            return isinstance(default, ast.Constant) and default.value is False
    return False


def _governance_mutation_escape_sites(
    scope: ast.AST,
    allowed_initializer: ast.stmt,
    approved_statement: ast.stmt,
    approved_call: ast.Call,
) -> list[ast.AST]:
    """Reject mutation, aliasing, or escape of the governance dependency."""
    sites: dict[int, ast.AST] = {}

    def record(node: ast.AST) -> None:
        sites.setdefault(id(node), node)

    for node in ast.walk(scope):
        if (
            isinstance(node, (ast.Attribute, ast.Subscript))
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and _rooted_in_name(node, "governance")
        ):
            record(node)
        elif (
            isinstance(node, ast.Assign)
            and node is not allowed_initializer
            and node is not approved_statement
        ):
            if _contains_name_reference(node.value, "governance"):
                record(node)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if _contains_name_reference(node.value, "governance"):
                record(node)
        elif isinstance(node, ast.NamedExpr):
            if _contains_name_reference(node.value, "governance"):
                record(node)
        elif isinstance(node, ast.Return) and node.value is not None:
            if _contains_name_reference(node.value, "governance"):
                record(node)
        elif isinstance(node, ast.Call) and node is not approved_call:
            if _rooted_in_name(node.func, "governance") or any(
                _contains_name_reference(arg, "governance") for arg in node.args
            ) or any(
                _contains_name_reference(keyword.value, "governance")
                for keyword in node.keywords
            ):
                record(node)

    return sorted(sites.values(), key=lambda node: getattr(node, "lineno", 0))


def _action_mutation_escape_sites(
    scope: ast.AST, name: str, approved_statement: ast.stmt, approved_call: ast.Call
) -> list[ast.AST]:
    """Reject writes, aliases, and unapproved calls that can alter a GovernanceAction."""
    sites: dict[int, ast.AST] = {}

    def record(node: ast.AST) -> None:
        sites.setdefault(id(node), node)

    for node in ast.walk(scope):
        if (
            isinstance(node, (ast.Attribute, ast.Subscript))
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and _rooted_in_name(node, name)
        ):
            record(node)
        elif isinstance(node, ast.Assign) and node is not approved_statement:
            if _contains_name_reference(node.value, name):
                record(node)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if _contains_name_reference(node.value, name):
                record(node)
        elif isinstance(node, ast.NamedExpr):
            if _contains_name_reference(node.value, name):
                record(node)
        elif isinstance(node, ast.Return) and node.value is not None:
            if _contains_name_reference(node.value, name):
                record(node)
        elif isinstance(node, ast.Call) and node is not approved_call:
            if _rooted_in_name(node.func, name) or any(
                _contains_name_reference(arg, name) for arg in node.args
            ) or any(
                _contains_name_reference(keyword.value, name)
                for keyword in node.keywords
            ):
                record(node)

    return sorted(sites.values(), key=lambda node: getattr(node, "lineno", 0))


def _memory_method_call_sites(scope: ast.AST) -> list[ast.Call]:
    """Reject direct memory methods other than the separately governed write."""
    calls: dict[int, ast.Call] = {}
    for node in ast.walk(scope):
        if not isinstance(node, ast.Call) or not _rooted_in_name(node.func, "memory"):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "memory"
            and node.func.attr == "write"
        ):
            continue
        calls.setdefault(id(node), node)
    return sorted(calls.values(), key=lambda node: getattr(node, "lineno", 0))

def _memory_object_escape_sites(scope: ast.AST) -> list[ast.AST]:
    """Find calls/aliases that hand the memory object to unapproved code."""
    sites: dict[int, ast.AST] = {}

    def record(node: ast.AST) -> None:
        sites.setdefault(id(node), node)

    for node in ast.walk(scope):
        if isinstance(node, ast.Call):
            passed_memory = any(
                _contains_name_reference(arg, "memory") for arg in node.args
            ) or any(
                _contains_name_reference(keyword.value, "memory")
                for keyword in node.keywords
            )
            if passed_memory and not _is_approved_contradiction_read(node):
                record(node)
        elif isinstance(node, ast.Assign):
            # Only the exact dependency-default expression is exempt. An alias
            # such as a comprehension containing helper() must still be detected
            # even though the RHS contains a different call. Direct memory writes
            # and the one approved read-only contradiction lookup are validated
            # separately by their dedicated structural checks.
            approved_read_assignment = (
                isinstance(node.value, ast.Await)
                and isinstance(node.value.value, ast.Call)
                and _is_approved_contradiction_read(node.value.value)
            )
            if (
                not _is_default_dependency_initialization(
                    node, "memory", "get_unified_memory"
                )
                and not _is_direct_entry_memory_write(node)
                and not approved_read_assignment
                and _contains_name_reference(node.value, "memory")
            ):
                record(node)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if _contains_name_reference(node.value, "memory"):
                record(node)
        elif isinstance(node, ast.Return) and node.value is not None:
            if _contains_name_reference(node.value, "memory"):
                record(node)

    return sorted(sites.values(), key=lambda node: getattr(node, "lineno", 0))


def _memory_write_calls(node: ast.AST) -> list[ast.AST]:
    """Find direct writes, bound-method extraction, and common literal reflection.

    Any receiver's .write method is treated as a persistence write inside
    ValidationGate. Bound-method extraction and common literal reflection forms
    are also detected so an alias cannot bypass the direct-call check.
    """
    descendants = list(ast.walk(node))
    calls = [
        child for child in descendants
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "write"
    ]
    direct_callee_ids = {id(call.func) for call in calls}
    extracted_references = [
        child for child in descendants
        if isinstance(child, ast.Attribute)
        and child.attr == "write"
        and id(child) not in direct_callee_ids
    ]

    def is_literal_write(value: ast.AST) -> bool:
        return isinstance(value, ast.Constant) and value.value == "write"

    reflective_references: list[ast.AST] = []
    for child in descendants:
        if isinstance(child, ast.Call):
            func = child.func
            if (
                isinstance(func, ast.Name)
                and func.id == "getattr"
                and len(child.args) >= 2
                and is_literal_write(child.args[1])
            ):
                reflective_references.append(child)
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in {"__getattribute__", "__getattr__"}
                and any(is_literal_write(arg) for arg in child.args)
            ):
                reflective_references.append(child)
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in {"get", "pop", "setdefault", "__getitem__"}
                and child.args
                and is_literal_write(child.args[0])
                and (
                    (isinstance(func.value, ast.Attribute) and func.value.attr == "__dict__")
                    or (
                        isinstance(func.value, ast.Call)
                        and isinstance(func.value.func, ast.Name)
                        and func.value.func.id == "vars"
                    )
                )
            ):
                reflective_references.append(child)
        elif isinstance(child, ast.Subscript) and is_literal_write(child.slice):
            value = child.value
            if (
                isinstance(value, ast.Attribute)
                and value.attr == "__dict__"
            ) or (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "vars"
            ):
                reflective_references.append(child)

    # A reflection node can also contain another recognized write node.
    # Deduplicate by identity while preserving source traversal order.
    unique: list[ast.AST] = []
    seen: set[int] = set()
    for candidate in (*calls, *extracted_references, *reflective_references):
        if id(candidate) not in seen:
            seen.add(id(candidate))
            unique.append(candidate)
    return unique


def _is_direct_entry_memory_write(statement: ast.stmt) -> bool:
    """Recognize the single expected promotion write after the approval guards."""
    return (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == "entry_id"
        and isinstance(statement.value, ast.Await)
        and isinstance(statement.value.value, ast.Call)
        and isinstance(statement.value.value.func, ast.Attribute)
        and isinstance(statement.value.value.func.value, ast.Name)
        and statement.value.value.func.value.id == "memory"
        and statement.value.value.func.attr == "write"
    )


def _is_terminal_non_evolution_write_branch(statement: ast.stmt) -> bool:
    """Allow pre-governance writes only in LEARNING/ADAPTATION branches that return."""
    if not isinstance(statement, ast.If) or statement.orelse or len(statement.body) < 2:
        return False
    test = statement.test
    if not (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "tier"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Attribute)
        and isinstance(test.comparators[0].value, ast.Name)
        and test.comparators[0].value.id == "LearningTier"
        and test.comparators[0].attr in {"LEARNING", "ADAPTATION"}
    ):
        return False

    # Both supported non-Evolution paths write directly to entry_id and
    # terminate the function; LEARNING also emits its routine event first.
    write_calls = _memory_write_calls(statement)
    return (
        len(write_calls) == 1
        and _is_direct_entry_memory_write(statement.body[0])
        and isinstance(statement.body[-1], ast.Return)
    )


def _is_terminal_governance_verdict_guard(
    statement: ast.stmt,
    expected_verdict: str,
    *,
    operator_type: type[ast.cmpop] = ast.Eq,
) -> bool:
    """Recognize a terminal verdict guard that cannot promote on its branch."""
    if not isinstance(statement, ast.If) or statement.orelse or not statement.body:
        return False
    test = statement.test
    if not (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Attribute)
        and isinstance(test.left.value, ast.Name)
        and test.left.value.id == "result"
        and test.left.attr == "verdict"
        and len(test.ops) == 1
        and isinstance(test.ops[0], operator_type)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Attribute)
        and isinstance(test.comparators[0].value, ast.Name)
        and test.comparators[0].value.id == "GovernanceVerdict"
        and test.comparators[0].attr == expected_verdict
    ):
        return False
    first = statement.body[0]
    if not isinstance(first, (ast.Return, ast.Raise)):
        return False
    return not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "memory"
        for node in ast.walk(first)
    )


def _rooted_in_name(node: ast.AST, name: str) -> bool:
    """Return whether an attribute/subscript expression is rooted at a Name."""
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        return _rooted_in_name(node.value, name)
    return False


def _contains_unsafe_result_reference(node: ast.AST, name: str) -> bool:
    """Detect an object reference that may escape or expose mutable result state."""
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.Attribute):
        if _rooted_in_name(node, name):
            # These are the only scalar fields read directly by the governance
            # guards/return construction. Any other attribute may be mutable.
            return not (
                isinstance(node.value, ast.Name)
                and node.value.id == name
                and node.attr in {"verdict", "reason"}
            )
        return any(
            _contains_unsafe_result_reference(child, name)
            for child in ast.iter_child_nodes(node)
        )
    if isinstance(node, ast.Subscript):
        if _rooted_in_name(node.value, name):
            return True
        return any(
            _contains_unsafe_result_reference(child, name)
            for child in ast.iter_child_nodes(node)
        )
    return any(
        _contains_unsafe_result_reference(child, name)
        for child in ast.iter_child_nodes(node)
    )


def _result_object_mutation_sites(
    scope: ast.AST, name: str, approved_statement: ast.stmt
) -> list[tuple[ast.AST, str]]:
    """Find result-object mutation, aliasing, or escape in the gate's AST.

    Direct writes/deletes through attributes or subscripts are rejected.
    Assigning the result object (or a mutable object reachable from it) to an
    alias, passing it to an arbitrary call, or calling a method on it is also
    rejected. Read-only access to the scalar 'verdict' and 'reason' fields is
    permitted. This is a bounded AST guard, not a general alias/type analysis.
    """
    sites: dict[int, tuple[ast.AST, str]] = {}

    def record(node: ast.AST, detail: str) -> None:
        sites.setdefault(id(node), (node, detail))

    # An annotation-only attribute target does not assign a new value.
    annotation_only_targets = [
        node.target
        for node in ast.walk(scope)
        if isinstance(node, ast.AnnAssign) and node.value is None
    ]

    for node in ast.walk(scope):
        if (
            node is not scope
            and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
            and _contains_unsafe_result_reference(node, name)
        ):
            # A nested scope can close over and return/pass the evaluated result,
            # allowing an alias to mutate it later without a direct result target.
            record(node, "governance result object is mutated or escapes its verified scope")

        if (
            isinstance(node, (ast.Attribute, ast.Subscript))
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and _rooted_in_name(node, name)
        ):
            if any(node is target or any(child is node for child in ast.walk(target))
                   for target in annotation_only_targets):
                continue
            record(node, "governance result object is mutated or escapes its verified scope")

        if isinstance(node, ast.Assign) and node is not approved_statement:
            if _contains_unsafe_result_reference(node.value, name):
                record(node, "governance result object is mutated or escapes its verified scope")
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if _contains_unsafe_result_reference(node.value, name):
                record(node, "governance result object is mutated or escapes its verified scope")
        elif isinstance(node, ast.NamedExpr):
            if _contains_unsafe_result_reference(node.value, name):
                record(node, "governance result object is mutated or escapes its verified scope")
        elif isinstance(node, ast.Call):
            if _rooted_in_name(node.func, name) or any(
                _contains_unsafe_result_reference(arg, name) for arg in node.args
            ) or any(
                _contains_unsafe_result_reference(keyword.value, name)
                for keyword in node.keywords
            ):
                record(node, "governance result object is mutated or escapes its verified scope")

    return sorted(
        sites.values(),
        key=lambda item: getattr(item[0], "lineno", 0),
    )


def _trusted_governance_mutation_sites(tree: ast.Module) -> list[ast.AST]:
    """Find direct mutations/aliases of imported governance classes and policy state."""
    governance_names = {
        "EvolutionGovernor",
        "GovernanceAction",
        "GovernanceKernel",
        "GovernanceVerdict",
    }
    policy_names = set(TRUSTED_POLICY_CLASSES)
    protected_names = governance_names | policy_names
    mutating_methods = {
        "add", "append", "clear", "discard", "extend", "insert", "pop",
        "remove", "setdefault", "update", "__delitem__", "__setitem__",
    }
    sites: dict[int, ast.AST] = {}

    def record(node: ast.AST) -> None:
        sites.setdefault(id(node), node)

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.Attribute, ast.Subscript))
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and any(_rooted_in_name(node, name) for name in protected_names)
        ):
            record(node)
        elif isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.Name) and value.id in protected_names:
                # A bare class-name alias can later be used to mutate or replace
                # the original policy authority, regardless of the local alias.
                record(node)
            elif isinstance(value, (ast.Attribute, ast.Subscript)) and any(
                _contains_name_reference(value, name) for name in governance_names
            ):
                # Governance method extraction (e.g. evaluate_action) is unsafe.
                record(node)
            elif (
                isinstance(value, ast.Attribute)
                and value.attr in {"__dict__", "__bases__", "__mro__"}
                and any(_rooted_in_name(value, name) for name in policy_names)
            ):
                record(node)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
            if isinstance(value, ast.Name) and value.id in protected_names:
                record(node)
            elif isinstance(value, (ast.Attribute, ast.Subscript)) and any(
                _contains_name_reference(value, name) for name in governance_names
            ):
                record(node)
            elif (
                isinstance(value, ast.Attribute)
                and value.attr in {"__dict__", "__bases__", "__mro__"}
                and any(_rooted_in_name(value, name) for name in policy_names)
            ):
                record(node)
        elif isinstance(node, ast.NamedExpr):
            value = node.value
            if isinstance(value, ast.Name) and value.id in protected_names:
                record(node)
            elif isinstance(value, (ast.Attribute, ast.Subscript)) and any(
                _contains_name_reference(value, name) for name in governance_names
            ):
                record(node)
            elif (
                isinstance(value, ast.Attribute)
                and value.attr in {"__dict__", "__bases__", "__mro__"}
                and any(_rooted_in_name(value, name) for name in policy_names)
            ):
                record(node)
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Name)
                and func.id in {"getattr", "setattr", "delattr"}
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in protected_names
            ):
                record(node)
            elif any(
                _contains_name_reference(arg, name)
                for name in protected_names
                for arg in node.args
            ) or any(
                _contains_name_reference(keyword.value, name)
                for name in protected_names
                for keyword in node.keywords
            ):
                # Passing a trusted class to another callable can expose it
                # to type.__setattr__ or a mutating helper; there is no such
                # legitimate use in the current ValidationGate module.
                record(node)
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in mutating_methods
                and (
                    (
                        _rooted_in_name(func.value, "EvolutionGovernor")
                        and any(
                            isinstance(part, ast.Attribute)
                            and part.attr == "SELF_MODIFYING_ACTIONS"
                            for part in ast.walk(func.value)
                        )
                    )
                    or any(_rooted_in_name(func.value, name) for name in policy_names)
                )
            ):
                record(node)

    return sorted(sites.values(), key=lambda node: getattr(node, "lineno", 0))


def _trusted_policy_class_violations(tree: ast.Module, rel: str) -> list[Violation]:
    """Require tier/domain policy classes to be unique top-level class definitions."""
    violations: list[Violation] = []
    for symbol in TRUSTED_POLICY_CLASSES:
        bindings = _find_module_scope_bindings_for_name(tree, symbol)
        if len(bindings) != 1:
            node = bindings[1][0] if len(bindings) > 1 else (
                bindings[0][0] if bindings else ast.Module(body=[], type_ignores=[])
            )
            violations.append(
                Violation(
                    rel, getattr(node, "lineno", 0),
                    f"policy class '{symbol}' has a competing or missing module-scope binding",
                )
            )
            continue
        node, description = bindings[0]
        if node not in tree.body or not isinstance(node, ast.ClassDef):
            violations.append(
                Violation(
                    rel, getattr(node, "lineno", 0),
                    f"policy symbol '{symbol}' must be one direct top-level class definition, found {description}",
                )
            )
            continue

        # These classes are intentionally plain policy namespaces. A custom
        # base, metaclass, or decorator could alter class-attribute resolution
        # without changing the visible assignments below.
        if node.bases or node.keywords or node.decorator_list:
            violations.append(
                Violation(
                    rel, node.lineno,
                    f"policy class '{symbol}' must remain an undecorated plain class without custom bases/metaclass",
                )
            )

        expected_values = TRUSTED_POLICY_VALUES[symbol]
        class_scope = ast.Module(body=node.body, type_ignores=[])
        for field_name, expected_value in expected_values.items():
            field_bindings = _find_module_scope_bindings_for_name(
                class_scope, field_name
            )
            if len(field_bindings) != 1:
                at = getattr(field_bindings[1][0], "lineno", node.lineno) if len(field_bindings) > 1 else node.lineno
                violations.append(
                    Violation(
                        rel, at,
                        f"policy constant '{symbol}.{field_name}' has a missing or competing class-body binding",
                    )
                )
                continue
            field_node, field_description = field_bindings[0]
            if (
                field_node not in node.body
                or not isinstance(field_node, ast.Assign)
                or len(field_node.targets) != 1
                or not isinstance(field_node.targets[0], ast.Name)
                or field_node.targets[0].id != field_name
            ):
                violations.append(
                    Violation(
                        rel, getattr(field_node, "lineno", node.lineno),
                        f"policy constant '{symbol}.{field_name}' must be one direct class-body assignment, found {field_description}",
                    )
                )
                continue

            value = field_node.value
            if isinstance(expected_value, str):
                value_is_exact = (
                    isinstance(value, ast.Constant)
                    and type(value.value) is str
                    and value.value == expected_value
                )
            else:
                expected_names = tuple(expected_value)
                value_is_exact = (
                    isinstance(value, ast.Tuple)
                    and len(value.elts) == len(expected_names)
                    and all(
                        isinstance(element, ast.Name) and element.id == expected_name
                        for element, expected_name in zip(value.elts, expected_names)
                    )
                )
            if not value_is_exact:
                violations.append(
                    Violation(
                        rel, field_node.lineno,
                        f"policy constant '{symbol}.{field_name}' must retain its frozen value {expected_value!r}",
                    )
                )
    return violations

def _trusted_governance_import_violations(tree: ast.Module, rel: str) -> list[Violation]:
    """Pin trusted imports and reject competing module-scope bindings."""
    violations: list[Violation] = []
    for symbol, module_name in GOVERNANCE_TRUSTED_IMPORTS:
        exact_imports = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.ImportFrom)
            and statement.module == module_name
            and any(
                alias.name == symbol and alias.asname in (None, symbol)
                for alias in statement.names
            )
        ]
        if len(exact_imports) != 1:
            violations.append(
                Violation(
                    rel, getattr(exact_imports[0], "lineno", 0) if exact_imports else 0,
                    f"missing or invalid required trusted import '{symbol}' from '{module_name}'",
                )
            )

        bindings = _find_module_scope_bindings_for_name(tree, symbol)
        if len(bindings) != 1:
            node = bindings[1][0] if len(bindings) > 1 else (
                bindings[0][0] if bindings else ast.Module(body=[], type_ignores=[])
            )
            violations.append(
                Violation(
                    rel, getattr(node, "lineno", 0),
                    f"trusted governance symbol '{symbol}' has a competing or missing module-scope binding",
                )
            )

    for node in _trusted_governance_mutation_sites(tree):
        violations.append(
            Violation(
                rel, getattr(node, "lineno", 0),
                "trusted governance/policy class or EvolutionGovernor allowlist is mutated, aliased, or passed to dynamic access code",
            )
        )
    return violations


def _contradiction_helper_violations(tree: ast.Module, rel: str) -> list[Violation]:
    """Require _find_contradiction to use only its canonical read-only search."""
    violations: list[Violation] = []
    bindings = _find_module_scope_bindings_for_name(tree, "_find_contradiction")
    if len(bindings) != 1:
        node = bindings[1][0] if len(bindings) > 1 else (bindings[0][0] if bindings else ast.Module(body=[], type_ignores=[]))
        violations.append(Violation(rel, getattr(node, "lineno", 0), "missing or competing module-scope binding for _find_contradiction"))
        return violations
    helper = bindings[0][0]
    if helper not in tree.body or not isinstance(helper, ast.AsyncFunctionDef) or helper.decorator_list:
        violations.append(Violation(rel, getattr(helper, "lineno", 0), "_find_contradiction must be one undecorated top-level async helper"))
        return violations

    def expected_search(call: ast.Call) -> bool:
        return (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "memory"
            and call.func.attr == "search"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "candidate_content"
            and len(call.keywords) == 1
            and call.keywords[0].arg == "limit"
            and isinstance(call.keywords[0].value, ast.Constant)
            and call.keywords[0].value.value == 5
        )

    search_statements = [
        node for node in ast.walk(helper)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "results"
        and isinstance(node.value, ast.Await)
        and isinstance(node.value.value, ast.Call)
        and expected_search(node.value.value)
    ]
    allowed_statement = search_statements[0] if len(search_statements) == 1 else None
    allowed_call = allowed_statement.value.value if allowed_statement is not None else None
    if len(search_statements) != 1:
        violations.append(Violation(rel, helper.lineno, "_find_contradiction must assign exactly one awaited memory.search(candidate_content, limit=5) call to results"))

    for node in ast.walk(helper):
        if isinstance(node, ast.Call):
            if _rooted_in_name(node.func, "memory") and node is not allowed_call:
                violations.append(Violation(rel, node.lineno, "_find_contradiction may only call memory.search through its canonical read path"))
            if node is not allowed_call and (
                any(_contains_name_reference(arg, "memory") for arg in node.args)
                or any(_contains_name_reference(keyword.value, "memory") for keyword in node.keywords)
            ):
                violations.append(Violation(rel, node.lineno, "_find_contradiction may not pass memory to another helper"))
        elif isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)) and _rooted_in_name(node, "memory"):
            violations.append(Violation(rel, getattr(node, "lineno", helper.lineno), "_find_contradiction may not mutate memory"))
        elif isinstance(node, ast.Assign) and node is not allowed_statement and _contains_name_reference(node.value, "memory"):
            violations.append(Violation(rel, node.lineno, "_find_contradiction may not alias memory"))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and _contains_name_reference(node.value, "memory"):
            violations.append(Violation(rel, node.lineno, "_find_contradiction may not alias memory"))
        elif isinstance(node, ast.NamedExpr) and _contains_name_reference(node.value, "memory"):
            violations.append(Violation(rel, node.lineno, "_find_contradiction may not alias memory"))
        elif isinstance(node, ast.Return) and node.value is not None and _contains_name_reference(node.value, "memory"):
            violations.append(Violation(rel, node.lineno, "_find_contradiction may not return memory"))
    return violations

def _returns_in_current_scope(node: ast.AST) -> list[ast.Return]:
    """Collect returns in a statement while not entering nested scopes."""
    returns: list[ast.Return] = []
    class _ReturnVisitor(ast.NodeVisitor):
        def visit_Return(self, item: ast.Return) -> None:
            returns.append(item)
            self.generic_visit(item)
        def visit_FunctionDef(self, item: ast.FunctionDef) -> None:
            return
        def visit_AsyncFunctionDef(self, item: ast.AsyncFunctionDef) -> None:
            return
        def visit_ClassDef(self, item: ast.ClassDef) -> None:
            return
        def visit_Lambda(self, item: ast.Lambda) -> None:
            return
    _ReturnVisitor().visit(node)
    return returns

def _is_canonical_rejected_helper(node: ast.AST) -> bool:
    """Recognize the gate-local helper whose only outcome is REJECTED."""
    if not (
        isinstance(node, ast.FunctionDef)
        and node.name == "_rejected"
        and not node.decorator_list
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Return)
        and isinstance(node.body[0].value, ast.Call)
        and isinstance(node.body[0].value.func, ast.Name)
        and node.body[0].value.func.id == "LearningRecord"
    ):
        return False
    lifecycle = next(
        (kw.value for kw in node.body[0].value.keywords if kw.arg == "lifecycle_state"),
        None,
    )
    return (
        isinstance(lifecycle, ast.Attribute)
        and lifecycle.attr == "REJECTED"
        and isinstance(lifecycle.value, ast.Name)
        and lifecycle.value.id == "LearningLifecycle"
    )

def _safe_pre_governance_return(
    node: ast.Return, canonical_rejected_helper: ast.FunctionDef | None
) -> bool:
    """Allow only a no-result exit or the gate's canonical REJECTED helper."""
    if node.value is None or (
        isinstance(node.value, ast.Constant) and node.value.value is None
    ):
        return True
    return (
        canonical_rejected_helper is not None
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_rejected"
    )

def _governance_boundary_violations(
    tree: ast.Module, rel: str
) -> tuple[list[Violation], tuple[str, str] | None]:
    """Find direct governance calls, allowing only configured, scoped exceptions."""
    violations: list[Violation] = []
    if rel == "core/cognitive/learning.py":
        violations.extend(_trusted_governance_import_violations(tree, rel))
        violations.extend(_trusted_policy_class_violations(tree, rel))
        violations.extend(_contradiction_helper_violations(tree, rel))
    approved_call_node: ast.Call | None = None
    approved_gate_node: ast.AsyncFunctionDef | None = None
    approved_call_stmt_idx: int | None = None
    applied_exception_key: tuple[str, str] | None = None

    # The exception configuration is the single source of truth for both the
    # required gate name and the rationale reported by check_drift_10().
    scope_key = next(
        (key for key in DRIFT_10_EXCEPTION_SCOPES if key[0] == rel),
        None,
    )
    if scope_key is not None:
        gate_name = scope_key[1]
        bindings = _find_module_scope_bindings_for_name(tree, gate_name)
        if len(bindings) == 0:
            violations.append(
                Violation(
                    rel, 0,
                    f"missing required top-level '{gate_name}' function definition in {rel}",
                )
            )
        elif len(bindings) > 1:
            second_node, desc = bindings[1]
            violations.append(
                Violation(
                    rel, getattr(second_node, "lineno", 0),
                    f"competing or duplicate module-scope binding for '{gate_name}': {desc}",
                )
            )
        else:
            gate_node, desc = bindings[0]
            if gate_node not in tree.body:
                violations.append(
                    Violation(
                        rel, getattr(gate_node, "lineno", 0),
                        f"'{gate_name}' must be a direct top-level definition, not nested in control flow",
                    )
                )
            elif not isinstance(gate_node, ast.AsyncFunctionDef):
                violations.append(
                    Violation(
                        rel, getattr(gate_node, "lineno", 0),
                        f"'{gate_name}' must be an async function definition, found {desc}",
                    )
                )
            elif gate_node.decorator_list:
                violations.append(
                    Violation(
                        rel, gate_node.lineno,
                        f"'{gate_name}' must be undecorated",
                    )
                )
            else:
                call_stmt_idx = None
                for idx, stmt in enumerate(gate_node.body):
                    if (
                        isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and stmt.targets[0].id == "result"
                        and isinstance(stmt.value, ast.Call)
                        and isinstance(stmt.value.func, ast.Attribute)
                        and isinstance(stmt.value.func.value, ast.Name)
                        and stmt.value.func.value.id == "governance"
                        and stmt.value.func.attr == "evaluate_action"
                        and len(stmt.value.args) == 1
                        and isinstance(stmt.value.args[0], ast.Name)
                        and stmt.value.args[0].id == "action"
                        and not stmt.value.keywords
                    ):
                        call_stmt_idx = idx
                        break

                if call_stmt_idx is None:
                    violations.append(
                        Violation(
                            rel, gate_node.lineno,
                            f"missing or invalid required 'result = governance.evaluate_action(action)' call in top-level '{gate_name}()' body",
                        )
                    )
                else:
                    early_exit = None
                    for stmt in gate_node.body[:call_stmt_idx]:
                        early_exit = _first_unconditional_return_or_raise(stmt)
                        if early_exit is not None:
                            break

                    if early_exit is not None:
                        violations.append(
                            Violation(
                                rel, early_exit.lineno,
                                f"required 'evaluate_action()' call in '{gate_name}()' can be bypassed by an earlier return/raise path",
                            )
                        )
                    else:
                        approved_call_node = gate_node.body[call_stmt_idx].value
                        approved_gate_node = gate_node
                        approved_call_stmt_idx = call_stmt_idx
                        result_target = gate_node.body[call_stmt_idx].targets[0]

                        # Caller-supplied values that define what was scored,
                        # checked for contradiction, and ultimately written
                        # must remain stable across the gate. Reassignment
                        # after validation could check benign content and write
                        # different content or attribute it to another domain.
                        protected_inputs = (
                            "content_domain",
                            "subject_ref",
                            "candidate_content",
                            "trigger_signals",
                            "held_out_score",
                            "baseline_score",
                            "importance",
                            "is_new_entry",
                            "procedure_name",
                            "metadata",
                        )
                        for input_name in protected_inputs:
                            for writer in _scope_name_writes(gate_node, input_name):
                                violations.append(
                                    Violation(
                                        rel, getattr(writer, "lineno", gate_node.lineno),
                                        f"caller-supplied ValidationGate input '{input_name}' is rebound or deleted",
                                    )
                                )


                        if not _argument_default_is_false(gate_node, "hitl_approved"):
                            violations.append(
                                Violation(
                                    rel, gate_node.lineno,
                                    "ValidationGate 'hitl_approved' must default to False",
                                )
                            )
                        for writer in _scope_name_writes(gate_node, "hitl_approved"):
                            violations.append(
                                Violation(
                                    rel, getattr(writer, "lineno", gate_node.lineno),
                                    "ValidationGate caller-supplied 'hitl_approved' input is rebound or deleted",
                                )
                            )

                        dependency_defaults = (
                            ("memory", "get_unified_memory"),
                            ("governance", "get_governance_kernel"),
                            ("event_stream", "get_event_stream"),
                        )
                        for dependency_name, provider_name in dependency_defaults:
                            allowed_initializers = [
                                stmt for stmt in gate_node.body
                                if _is_default_dependency_initialization(
                                    stmt, dependency_name, provider_name
                                )
                            ]
                            if len(allowed_initializers) != 1:
                                violations.append(
                                    Violation(
                                        rel, gate_node.lineno,
                                        f"ValidationGate must preserve exactly one default initialization for '{dependency_name}'",
                                    )
                                )
                            allowed_targets = {
                                id(stmt.targets[0]) for stmt in allowed_initializers
                            }
                            for writer in _scope_name_writes(gate_node, dependency_name):
                                if id(writer) not in allowed_targets:
                                    violations.append(
                                        Violation(
                                            rel, getattr(writer, "lineno", gate_node.lineno),
                                            f"ValidationGate dependency '{dependency_name}' is rebound or deleted",
                                        )
                                    )

                        action_parameters = [
                            arg.arg for arg in (
                                *gate_node.args.posonlyargs,
                                *gate_node.args.args,
                                *gate_node.args.kwonlyargs,
                            )
                        ]
                        if "action" in action_parameters:
                            violations.append(
                                Violation(
                                    rel, gate_node.lineno,
                                    "missing or invalid required internal GovernanceAction construction; accepting a prebuilt 'action' parameter bypasses the approval contract",
                                )
                            )

                        action_initializers = [
                            (index, stmt) for index, stmt in enumerate(gate_node.body)
                            if _is_approved_action_construction(stmt)
                        ]
                        if (
                            len(action_initializers) != 1
                            or action_initializers[0][0] >= call_stmt_idx
                        ):
                            violations.append(
                                Violation(
                                    rel, gate_node.lineno,
                                    "missing or invalid required 'action = GovernanceAction(..., requires_approval=not hitl_approved)' before governance evaluation",
                                )
                            )
                        allowed_action_targets = {
                            id(stmt.targets[0]) for _, stmt in action_initializers
                        }
                        for writer in _scope_name_writes(gate_node, "action"):
                            if id(writer) not in allowed_action_targets:
                                violations.append(
                                    Violation(
                                        rel, getattr(writer, "lineno", gate_node.lineno),
                                        "ValidationGate GovernanceAction binding is rebound or deleted",
                                    )
                                )

                        allowlist_guards = [
                            (index, stmt) for index, stmt in enumerate(gate_node.body)
                            if _is_action_type_allowlist_guard(stmt)
                        ]
                        if (
                            len(allowlist_guards) != 1
                            or (
                                len(action_initializers) == 1
                                and allowlist_guards[0][0] >= action_initializers[0][0]
                            )
                        ):
                            violations.append(
                                Violation(
                                    rel, gate_node.lineno,
                                    "missing or invalid required EvolutionGovernor.SELF_MODIFYING_ACTIONS allowlist guard before GovernanceAction construction",
                                )
                            )
                        elif len(allowlist_guards) == 1:
                            guard_stmt = allowlist_guards[0][1]
                            guard_end = (
                                getattr(guard_stmt, "end_lineno", guard_stmt.lineno),
                                getattr(guard_stmt, "end_col_offset", guard_stmt.col_offset),
                            )
                            for writer in _scope_name_writes(gate_node, "action_type"):
                                position = (
                                    getattr(writer, "lineno", 0),
                                    getattr(writer, "col_offset", 0),
                                )
                                if position > guard_end:
                                    violations.append(
                                        Violation(
                                            rel, getattr(writer, "lineno", gate_node.lineno),
                                            "ValidationGate action_type is rebound after its EvolutionGovernor allowlist check",
                                        )
                                    )

                        governance_initializers = [
                            stmt for stmt in gate_node.body
                            if _is_default_dependency_initialization(
                                stmt, "governance", "get_governance_kernel"
                            )
                        ]
                        if len(governance_initializers) == 1:
                            governance_escapes = _governance_mutation_escape_sites(
                                gate_node,
                                governance_initializers[0],
                                gate_node.body[call_stmt_idx],
                                approved_call_node,
                            )
                            for escape_node in governance_escapes:
                                violations.append(
                                    Violation(
                                        rel, getattr(escape_node, "lineno", gate_node.lineno),
                                        "GovernanceKernel dependency is mutated, aliased, or passed to unapproved code",
                                    )
                                )
                        else:
                            governance_escapes = []

                        if len(action_initializers) == 1:
                            action_mutations = _action_mutation_escape_sites(
                                gate_node,
                                "action",
                                gate_node.body[call_stmt_idx],
                                approved_call_node,
                            )
                            for mutation_node in action_mutations:
                                violations.append(
                                    Violation(
                                        rel, getattr(mutation_node, "lineno", gate_node.lineno),
                                        "GovernanceAction is mutated, aliased, or passed to unapproved code before/after evaluation",
                                    )
                                )
                        unexpected_result_writes = [
                            writer
                            for writer in _scope_name_writes(gate_node, "result")
                            if writer is not result_target
                        ]
                        for writer in unexpected_result_writes:
                            violations.append(
                                Violation(
                                    rel,
                                    getattr(writer, "lineno", gate_node.lineno),
                                    "governance result 'result' is rebound or deleted after/beside the approved call",
                                )
                            )

                        tier_selector_writes = _scope_name_writes(gate_node, "tier")
                        for writer in tier_selector_writes:
                            violations.append(
                                Violation(
                                    rel,
                                    getattr(writer, "lineno", gate_node.lineno),
                                    "ValidationGate tier selector 'tier' is rebound or deleted; non-Evolution write exceptions must depend on the original caller-supplied tier",
                                )
                            )

                        rejected_helpers = [
                            stmt for stmt in gate_node.body
                            if _is_canonical_rejected_helper(stmt)
                        ]
                        canonical_rejected_helper = rejected_helpers[0] if len(rejected_helpers) == 1 else None
                        rejected_helper_writes = _scope_name_writes(gate_node, "_rejected")
                        if rejected_helper_writes and (
                            len(rejected_helpers) != 1
                            or any(writer is not canonical_rejected_helper for writer in rejected_helper_writes)
                        ):
                            violations.append(
                                Violation(
                                    rel, gate_node.lineno,
                                    "ValidationGate rejection helper is missing, duplicated, or rebound",
                                )
                            )

                        for prior_stmt in gate_node.body[:call_stmt_idx]:
                            if not _is_terminal_non_evolution_write_branch(prior_stmt):
                                for return_node in _returns_in_current_scope(prior_stmt):
                                    if not _safe_pre_governance_return(return_node, canonical_rejected_helper):
                                        violations.append(
                                            Violation(
                                                rel, return_node.lineno,
                                                "pre-governance return can bypass the gate with an unapproved result; only a no-result exit or canonical REJECTED return is permitted outside terminal non-Evolution write branches",
                                            )
                                        )
                            writes = _memory_write_calls(prior_stmt)
                            if writes and not (
                                _is_terminal_non_evolution_write_branch(prior_stmt)
                                and len(writes) == 1
                            ):
                                for write_call in writes:
                                    violations.append(
                                        Violation(
                                            rel,
                                            write_call.lineno,
                                            "memory.write(...) occurs before the required GovernanceKernel evaluation outside a terminal LEARNING/ADAPTATION branch",
                                        )
                                    )



    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "evaluate_action"
        ):
            continue

        if approved_call_node is not None and node is approved_call_node:
            # Defer declaring the exception applied until result-flow validation
            # below also confirms the governance verdict cannot be bypassed.
            continue
        violations.append(Violation(rel, node.lineno, "calls .evaluate_action(...) directly"))

    # Structural call presence alone is insufficient: pin the governance
    # result to terminal ESCALATE/REJECT guards and an explicit non-APPROVE
    # rejection. This prevents an unknown/future verdict from falling through
    # to promotion. It deliberately verifies the current direct control-flow
    # shape; it is not a general semantic/type analysis.
    all_evaluate_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "evaluate_action"
    ]
    if (
        approved_call_node is not None
        and approved_gate_node is not None
        and approved_call_stmt_idx is not None
        and len(all_evaluate_calls) == 1
    ):
        following = approved_gate_node.body[approved_call_stmt_idx + 1:approved_call_stmt_idx + 4]
        result_flow_is_safe = (
            len(following) == 3
            and _is_terminal_governance_verdict_guard(following[0], "ESCALATE")
            and _is_terminal_governance_verdict_guard(following[1], "REJECT")
            and _is_terminal_governance_verdict_guard(
                following[2], "APPROVE", operator_type=ast.NotEq
            )
        )
        if any(_memory_write_calls(guard) for guard in following):
            violations.append(
                Violation(
                    rel,
                    approved_call_node.lineno,
                    "memory.write(...) is forbidden inside the governance verdict guards",
                )
            )
            result_flow_is_safe = False

        post_guard_write_sites = [
            (statement, _memory_write_calls(statement))
            for statement in approved_gate_node.body[approved_call_stmt_idx + 4:]
        ]
        post_guard_writes = [
            (statement, call)
            for statement, calls in post_guard_write_sites
            for call in calls
        ]
        if len(post_guard_writes) > 1:
            violations.append(
                Violation(
                    rel,
                    post_guard_writes[1][1].lineno,
                    "more than one memory.write(...) occurs after the governance approval guards",
                )
            )
            result_flow_is_safe = False
        elif post_guard_writes and not _is_direct_entry_memory_write(post_guard_writes[0][0]):
            violations.append(
                Violation(
                    rel,
                    post_guard_writes[0][1].lineno,
                    "post-approval memory.write(...) must be the direct 'entry_id = await memory.write(...)' statement",
                )
            )
            result_flow_is_safe = False

        result_object_mutations = _result_object_mutation_sites(
            approved_gate_node,
            "result",
            approved_gate_node.body[approved_call_stmt_idx],
        )
        for mutation_node, detail in result_object_mutations:
            violations.append(
                Violation(rel, getattr(mutation_node, "lineno", approved_call_node.lineno), detail)
            )

        memory_escape_sites = _memory_object_escape_sites(approved_gate_node)
        for escape_node in memory_escape_sites:
            violations.append(
                Violation(
                    rel,
                    getattr(escape_node, "lineno", approved_call_node.lineno),
                    "memory object is passed to an unapproved helper, aliased, or returned",
                )
            )
        memory_method_sites = _memory_method_call_sites(approved_gate_node)
        for method_call in memory_method_sites:
            violations.append(
                Violation(
                    rel,
                    getattr(method_call, "lineno", approved_call_node.lineno),
                    "unapproved direct memory method call; only the canonical post-approval memory.write(...) is permitted",
                )
            )

        result_flow_is_safe = result_flow_is_safe and not result_object_mutations and not memory_escape_sites and not memory_method_sites and not tier_selector_writes and not governance_escapes and not any(
            "governance result 'result' is rebound or deleted after/beside the approved call" in violation.detail
            for violation in violations
            if violation.file == rel
        ) and not any(
            "memory.write(...) occurs before the required GovernanceKernel evaluation" in violation.detail
            for violation in violations
            if violation.file == rel
        )
        if not result_flow_is_safe:
            violations.append(
                Violation(
                    rel,
                    approved_call_node.lineno,
                    "governance result must immediately drive terminal ESCALATE/REJECT guards, reject every non-APPROVE verdict, preserve the evaluated result, and constrain memory writes to the authorized paths",
                )
            )
        elif not any(violation.file == rel for violation in violations):
            # A structurally valid verdict sequence is not enough if any other
            # contract check failed (action construction, dependency identity,
            # approval input, or write path). Never report the exception applied
            # for a Learning file that has any DRIFT-10 violation.
            applied_exception_key = scope_key

    return violations, applied_exception_key


def _validate_and_parse_governed_file(rel: str) -> tuple[ast.Module | None, Violation | None]:
    path = REPO_ROOT / rel
    cur = REPO_ROOT
    for part in Path(rel).parts:
        cur = cur / part
        if not cur.exists() and not cur.is_symlink():
            return None, Violation(rel, 0, f"governed file '{rel}' does not exist")
        if cur.is_symlink():
            return None, Violation(rel, 0, f"governed path '{rel}' contains symbolic link '{part}'")

    if not path.is_file():
        return None, Violation(rel, 0, f"governed path '{rel}' is not a regular file")

    try:
        resolved = path.resolve()
        resolved.relative_to(REPO_ROOT)
    except (ValueError, OSError) as e:
        return None, Violation(rel, 0, f"governed file '{rel}' resolves outside repository root: {e}")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return None, Violation(rel, 0, f"governed file '{rel}' failed utf-8 decoding: {e}")
    except OSError as e:
        return None, Violation(rel, 0, f"governed file '{rel}' failed to read: {e}")

    try:
        tree = ast.parse(content, filename=str(path))
        # Parsing builds an AST but does not perform every compiler/symbol-table
        # check (for example, an unbound nonlocal declaration). Compile without
        # execution so malformed governed sources fail closed.
        compile(tree, filename=str(path), mode="exec")
        return tree, None
    except SyntaxError as e:
        lineno = e.lineno or 0
        return None, Violation(rel, lineno, f"governed file '{rel}' syntax error: {e.msg}")


def check_drift_10() -> CheckResult:
    violations: list[Violation] = []
    applied_exception_keys: list[tuple[str, str]] = []
    for rel in GOVERNANCE_BOUNDARY_FILES:
        tree, err = _validate_and_parse_governed_file(rel)
        if err is not None:
            violations.append(err)
            continue
        if tree is not None:
            found, used_exception_key = _governance_boundary_violations(tree, rel)
            violations.extend(found)
            if used_exception_key is not None:
                applied_exception_keys.append(used_exception_key)
    status = "VIOLATION" if violations else "PASS"
    unique_applied_keys = list(dict.fromkeys(applied_exception_keys))
    notes = (
        "Applied the documented exception(s): "
        + "; ".join(DRIFT_10_EXCEPTION_SCOPES[key] for key in unique_applied_keys)
        if unique_applied_keys else ""
    )
    return CheckResult(
        "DRIFT-10",
        "Unauthorized direct GovernanceKernel.evaluate_action() calls in "
        "Intent, Planner, and Learning are forbidden; the one exact "
        "ValidationGate approval call is allowed only when the result "
        "immediately drives terminal ESCALATE/REJECT guards and rejects "
        "every non-APPROVE verdict before promotion (DRIFT-05 remains "
        "unchanged and independently covers SupervisorWorker).",
        status,
        violations,
        notes,
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
