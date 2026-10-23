#!/usr/bin/env python3
"""Snapshot protected runtime trees before pytest and verify they stay byte-identical.

Unlike `git diff`, this also detects new/deleted ignored files, untracked files,
empty directories, symlinks, and generated ChromaDB files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTECTED_ROOTS = ("config", "modules", "data", "workspace")


def _entry(path: Path, relative: str) -> dict[str, Any]:
    if path.is_symlink():
        info = path.lstat()
        return {
            "kind": "symlink",
            "target": os.readlink(path),
            "mode": stat.S_IMODE(info.st_mode),
            "mtime_ns": info.st_mtime_ns,
            "ctime_ns": info.st_ctime_ns,
        }
    try:
        info = path.stat()
    except FileNotFoundError:
        return {"kind": "missing"}
    metadata = {
        "mode": stat.S_IMODE(info.st_mode),
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
    }
    if stat.S_ISDIR(info.st_mode):
        return {"kind": "directory", **metadata}
    if stat.S_ISREG(info.st_mode):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return {
            "kind": "file",
            "size": info.st_size,
            "sha256": digest.hexdigest(),
            **metadata,
        }
    return {"kind": "other", "mode": stat.S_IFMT(info.st_mode)}


def _raise_walk_error(exc: OSError) -> None:
    """Fail closed rather than silently skipping unreadable protected subtrees."""
    raise exc


def capture_state(root: Path) -> dict[str, dict[str, Any]]:
    """Record protected paths including ignored/untracked files and empty dirs."""
    root = Path(root).resolve()
    state: dict[str, dict[str, Any]] = {}
    for relative in PROTECTED_ROOTS:
        protected = root / relative
        root_entry = _entry(protected, relative)
        state[relative] = root_entry
        if root_entry["kind"] != "directory":
            continue

        for current, directory_names, file_names in os.walk(
            protected, followlinks=False, onerror=_raise_walk_error
        ):
            current_path = Path(current)
            for name in list(directory_names):
                child = current_path / name
                child_relative = child.relative_to(root).as_posix()
                child_entry = _entry(child, child_relative)
                state[child_relative] = child_entry
                # os.walk lists directory symlinks here; never traverse them.
                if child_entry["kind"] != "directory":
                    directory_names.remove(name)
            for name in file_names:
                child = current_path / name
                child_relative = child.relative_to(root).as_posix()
                state[child_relative] = _entry(child, child_relative)
    return dict(sorted(state.items()))


def _differences(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> list[str]:
    lines: list[str] = []
    for path in sorted(set(before) | set(after)):
        if path not in before:
            lines.append(f"ADDED    {path}: {after[path]}")
        elif path not in after:
            lines.append(f"REMOVED  {path}: {before[path]}")
        elif before[path] != after[path]:
            lines.append(f"CHANGED  {path}: before={before[path]} after={after[path]}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--snapshot", type=Path, help="write the pre-test snapshot")
    mode.add_argument("--verify", type=Path, help="compare the current tree to a snapshot")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    current = capture_state(args.root)
    if args.snapshot is not None:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(
            json.dumps(current, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Captured {len(current)} protected paths.")
        return 0

    try:
        before = json.loads(args.verify.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read protected-tree baseline: {exc}", file=sys.stderr)
        return 2
    differences = _differences(before, current)
    if differences:
        print("Protected runtime files changed during tests:", file=sys.stderr)
        for line in differences[:100]:
            print(f"  {line}", file=sys.stderr)
        if len(differences) > 100:
            print(f"  ... {len(differences) - 100} additional differences", file=sys.stderr)
        return 1
    print(f"Protected runtime state unchanged ({len(current)} paths).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
