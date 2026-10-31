#!/usr/bin/env python3
"""
scripts/check_token_acl_windows.py -- validate the REAL owner-only ACL on the API token file.

Run by the `token-acl-windows` CI job on a Windows runner (DEBT-025).  It is the only
place Windows evidence for interface/auth.py comes from: the unit tests stub icacls and
prove logic only, and everything POSIX proves nothing about NTFS.

It uses stdlib + interface.auth only (no third-party install) and drives the real
`icacls` and `whoami`.  What it establishes, and what it does not:

  establishes  the ACL that `icacls` reports for a token file created by
               load_or_create_token(), rotate_token() and the frozen-build default
               path is exactly one entry, for the current user, not inherited; and a
               deliberately loosened ACL (Everyone: read) is repaired on the next load.
  does NOT     attempt a read as a second user: the ACL listing is the evidence, not a
               cross-account access test.

On failure it prints GitHub `::error::` annotations (readable through the checks API)
and exits 1.  Outside Windows it prints a notice and exits 0.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def run(*args: str) -> str:
    return subprocess.run(list(args), capture_output=True, text=True, timeout=30).stdout


def aces(path: Path) -> list[str]:
    return [ln for ln in run("icacls", str(path)).splitlines() if ":(" in ln]


def main() -> int:
    if os.name != "nt":
        print("Not Windows: nothing to validate here (this check is Windows-only).")
        return 0

    from interface import auth

    me = run("whoami").strip()
    print(f"current user: {me}")
    work = Path(tempfile.mkdtemp(prefix="ocb-acl-"))
    try:
        # 1. a freshly created token file
        path = work / "api_token"
        os.environ.pop(auth.ENV_TOKEN, None)
        os.environ[auth.ENV_TOKEN_FILE] = str(path)
        token = auth.load_or_create_token()
        listing = run("icacls", str(path))
        print(listing)
        entries = aces(path)
        check("new file: exactly one access entry", len(entries) == 1, f"{len(entries)} entries")
        check("new file: the entry is the current user", len(entries) == 1 and me.split("\\")[-1].lower() in entries[0].lower(), entries[0] if entries else "")
        check("new file: nothing inherited", not any("(I)" in e for e in entries), "; ".join(entries))
        check("new file: full control for the owner", len(entries) == 1 and "(F)" in entries[0])

        # 2. a loosened ACL is repaired on the next load, and the token is unchanged
        run("icacls", str(path), "/grant", "*S-1-1-0:(R)")  # Everyone: read
        check("precondition: the ACL really was loosened", len(aces(path)) >= 2, f"{len(aces(path))} entries")
        auth.reset_cache_for_tests()
        again = auth.load_or_create_token()
        check("loosened ACL repaired on load", len(aces(path)) == 1, f"{len(aces(path))} entries")
        check("token unchanged by the repair", again == token)

        # 3. rotation keeps the restriction
        new, _ = auth.rotate_token()
        check("rotation: new token differs", new != token)
        check("rotation: file still owner-only", len(aces(path)) == 1, f"{len(aces(path))} entries")
        check("rotation: no temp files left", [p.name for p in work.iterdir()] == ["api_token"], str([p.name for p in work.iterdir()]))

        # 4. the frozen-build default location (per-user LOCALAPPDATA directory)
        os.environ.pop(auth.ENV_TOKEN_FILE, None)
        frozen = auth.default_token_path(frozen=True)
        local = os.environ.get("LOCALAPPDATA", "")
        check("frozen default is under LOCALAPPDATA\\OCBrain", bool(local) and str(frozen).lower().startswith(os.path.join(local, "OCBrain").lower()), str(frozen))
        if frozen.exists():
            check("frozen default path was free for the test", False, f"{frozen} already exists; not touching it")
        else:
            sys.frozen = True  # type: ignore[attr-defined]
            try:
                created_dir = not frozen.parent.exists()
                auth.reset_cache_for_tests()
                auth.load_or_create_token()
                check("frozen default: file created", frozen.exists(), str(frozen))
                check("frozen default: owner-only ACL", len(aces(frozen)) == 1, f"{len(aces(frozen))} entries")
            finally:
                del sys.frozen  # type: ignore[attr-defined]
                if frozen.exists():
                    frozen.unlink()
                if created_dir:
                    shutil.rmtree(frozen.parent, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if FAILURES:
        for item in FAILURES:
            print(f"::error title=Windows token ACL::{item}")
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all Windows token ACL checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
