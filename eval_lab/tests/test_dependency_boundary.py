"""Dependency-boundary audit — §86 of the Slice 2 brief, made into an
actual automated test rather than a one-time manual claim in a report.

Per the memory principle "AST-based identifier checking is more reliable
than substring/text search for architecture compliance tests" (this
project's own established pattern from prior drift-enforcement work):
this uses Python's `ast` module to parse real import statements, not a
grep for the string "eval_lab" (which would false-positive on comments,
docstrings, or the word appearing inside an unrelated string literal).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
CONTRACTS_DIR = REPO_ROOT / "eval_lab" / "contracts"

# Every top-level module eval_lab/contracts/*.py is allowed to import.
# Anything OCBrain-internal beyond this explicit list should fail the
# audit below and require a documented decision (§6/§86), the same way
# core.runtime.execution_outcome was evaluated before being added here.
ALLOWED_INTERNAL_IMPORTS = {
    "core.runtime.execution_outcome",  # FailureType: stdlib-only, zero coupling, verified in failure.py's docstring
}

STDLIB_ALLOWED_PREFIXES = (
    "__future__", "dataclasses", "datetime", "enum", "typing", "hashlib", "uuid", "json", "pathlib",
)


def _iter_python_files(directory: Path):
    if not directory.exists():
        return
    for path in directory.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_core_never_imports_eval_lab():
    """The load-bearing invariant: OCBrain's runtime must be able to run
    with eval_lab/ deleted. If anything under core/ ever imports from
    eval_lab, that's a broken invariant, not a style nit."""
    offenders = []
    for path in _iter_python_files(CORE_DIR):
        for name in _imported_module_names(path):
            if name == "eval_lab" or name.startswith("eval_lab."):
                offenders.append((str(path.relative_to(REPO_ROOT)), name))
    assert not offenders, f"core/ must never import eval_lab/, but found: {offenders}"


def test_eval_lab_contracts_do_not_import_unapproved_ocbrain_internals():
    """Every OCBrain-internal import from eval_lab/contracts/*.py must be
    on the explicit ALLOWED_INTERNAL_IMPORTS list. This is deliberately
    strict (fails closed on an unrecognized import) so a future
    contributor adding a new `from core.x import y` to a contract module
    is forced to either justify it here or reconsider the dependency,
    rather than it slipping in silently."""
    offenders = []
    for path in _iter_python_files(CONTRACTS_DIR):
        for name in _imported_module_names(path):
            is_stdlib_or_thirdparty = not (name == "core" or name.startswith("core."))
            is_eval_lab_internal = name == "eval_lab" or name.startswith("eval_lab.")
            if is_stdlib_or_thirdparty or is_eval_lab_internal:
                continue
            # remaining: something under core.*
            if name not in ALLOWED_INTERNAL_IMPORTS and not any(
                name.startswith(allowed + ".") for allowed in ALLOWED_INTERNAL_IMPORTS
            ):
                offenders.append((str(path.relative_to(REPO_ROOT)), name))
    assert not offenders, (
        f"eval_lab/contracts imports an OCBrain-internal module not on the "
        f"approved allowlist: {offenders}. Add it to ALLOWED_INTERNAL_IMPORTS "
        f"only after confirming it's a plain value type with no OCBrain-internal "
        f"coupling (§6/§86), the way core.runtime.execution_outcome.FailureType was."
    )


def test_the_one_approved_internal_import_is_still_the_safe_one():
    """Guards against ALLOWED_INTERNAL_IMPORTS silently growing without
    re-justification -- if this test needs updating, that's the prompt to
    re-examine whether the new entry is actually safe, not just add it
    quietly."""
    assert ALLOWED_INTERNAL_IMPORTS == {"core.runtime.execution_outcome"}


def test_execution_outcome_module_itself_remains_stdlib_only():
    """Re-verifies the safety argument this audit depends on: if
    core/runtime/execution_outcome.py ever grows an OCBrain-internal
    import of its own, the transitive-safety argument in failure.py's
    docstring stops being true, and this test should start failing to
    flag that."""
    path = CORE_DIR / "runtime" / "execution_outcome.py"
    if not path.exists():
        pytest.skip("core/runtime/execution_outcome.py not present in this checkout")
    for name in _imported_module_names(path):
        assert not name.startswith("core.") and name != "core", (
            f"core/runtime/execution_outcome.py now imports {name!r}; the "
            f"stdlib-only safety argument for reusing FailureType in "
            f"eval_lab/contracts/failure.py no longer holds and needs re-review."
        )
