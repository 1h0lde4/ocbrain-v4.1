"""Dependency-boundary audit — §86 of the Slice 2 brief, extended in Slice 3
to also cover eval_lab/adapters/. Made into an actual automated test
rather than a one-time manual claim in a report.

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
LAB_SCAN_DIRS = (
    REPO_ROOT / "eval_lab" / "contracts",
    REPO_ROOT / "eval_lab" / "adapters",
)

# Every eval_lab/{contracts,adapters}/*.py module is allowed to import
# exactly these OCBrain-internal modules. Anything beyond this explicit
# list fails the audit below and requires a documented decision (§6/§86
# of Slice 2; §4 of Slice 3), the same way each entry here was evaluated
# before being added.
ALLOWED_INTERNAL_IMPORTS = {
    # FailureType: stdlib-only, zero coupling. Verified in failure.py's
    # docstring (Slice 2) and re-verified in test_execution_outcome_module_
    # itself_remains_stdlib_only below.
    "core.runtime.execution_outcome",
    # StreamEvent: pure dataclass, stdlib-only (asyncio/json/logging/os/
    # sqlite3/time/uuid/abc/collections/contextlib/dataclasses/typing --
    # no OCBrain-internal imports). The adapter imports only the dataclass,
    # never EventStream/EventStore (the stateful sqlite3/asyncio-coupled
    # service classes in the same module) -- verified in
    # trace_normalizer.py's docstring and re-verified in
    # test_event_stream_module_itself_remains_stdlib_only below.
    "core.events.event_stream",
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


def test_eval_lab_does_not_import_unapproved_ocbrain_internals():
    """Every OCBrain-internal import from eval_lab/{contracts,adapters}/*.py
    must be on the explicit ALLOWED_INTERNAL_IMPORTS list. Deliberately
    strict (fails closed on an unrecognized import) so a future
    contributor adding a new `from core.x import y` anywhere in eval_lab/
    is forced to either justify it here or reconsider the dependency,
    rather than it slipping in silently. Scans both contracts/ and
    adapters/ as of Slice 3 -- a single-directory scan would have missed
    the adapter's own import of core.events.event_stream entirely."""
    offenders = []
    for scan_dir in LAB_SCAN_DIRS:
        for path in _iter_python_files(scan_dir):
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
        f"eval_lab/ imports an OCBrain-internal module not on the "
        f"approved allowlist: {offenders}. Add it to ALLOWED_INTERNAL_IMPORTS "
        f"only after confirming it's a plain value type with no OCBrain-internal "
        f"coupling, the way core.runtime.execution_outcome.FailureType and "
        f"core.events.event_stream.StreamEvent were."
    )


def test_the_approved_internal_imports_are_still_exactly_the_verified_safe_set():
    """Guards against ALLOWED_INTERNAL_IMPORTS silently growing without
    re-justification -- if this test needs updating, that's the prompt to
    re-examine whether the new entry is actually safe, not just add it
    quietly."""
    assert ALLOWED_INTERNAL_IMPORTS == {
        "core.runtime.execution_outcome",
        "core.events.event_stream",
    }


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


def test_event_stream_module_itself_remains_stdlib_only():
    """Same re-verification as above, for the Slice 3 adapter's import of
    core.events.event_stream.StreamEvent. If EventStream's module ever
    grows an OCBrain-internal import, the safety argument in
    trace_normalizer.py's docstring needs re-review -- this doesn't check
    that the *class* StreamEvent stays free of coupling (a class can't
    selectively import), only that the *module* it lives in doesn't grow
    OCBrain-internal dependencies that would apply to every name in it."""
    path = CORE_DIR / "events" / "event_stream.py"
    if not path.exists():
        pytest.skip("core/events/event_stream.py not present in this checkout")
    for name in _imported_module_names(path):
        assert not name.startswith("core.") and name != "core", (
            f"core/events/event_stream.py now imports {name!r}; the "
            f"stdlib-only safety argument for reusing StreamEvent in "
            f"eval_lab/adapters/trace_normalizer.py no longer holds and needs re-review."
        )
