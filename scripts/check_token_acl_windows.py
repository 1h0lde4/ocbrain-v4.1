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
LOG: list[str] = []


def say(text: str = "") -> None:
    """Print, and keep for the annotation: the runner's log is not readable through the API."""
    print(text, flush=True)
    LOG.append(text)


def annotate(level: str, title: str, text: str) -> None:
    """GitHub workflow command; visible through the checks API (annotations), unlike the raw log."""
    esc = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{level} title={title}::{esc}", flush=True)


def check(name: str, ok: bool, detail: str = "") -> None:
    say(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def run(*args: str) -> str:
    res = subprocess.run(list(args), capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        say(f"  (command {args[0]} exited {res.returncode}: {(res.stderr or res.stdout).strip()[:200]})")
    return res.stdout


def aces(path: Path) -> list[str]:
    return [ln for ln in run("icacls", str(path)).splitlines() if ":(" in ln]


def main() -> int:
    if os.name != "nt":
        print("Not Windows: nothing to validate here (this check is Windows-only).")
        return 0

    from interface import auth

    say(f"python {sys.version.split()[0]} on {sys.platform}; cwd={os.getcwd()}")
    me = run("whoami").strip()
    say(f"current user: {me}")
    say(f"whoami /user: {run('whoami', '/user', '/fo', 'csv', '/nh').strip()}")
    work = Path(tempfile.mkdtemp(prefix="ocb-acl-"))
    try:
        # 1. a freshly created token file
        path = work / "api_token"
        os.environ.pop(auth.ENV_TOKEN, None)
        os.environ[auth.ENV_TOKEN_FILE] = str(path)
        token = auth.load_or_create_token()
        listing = run("icacls", str(path))
        say("icacls listing of the new file:")
        say(listing.strip())
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

    say()
    if FAILURES:
        say(f"{len(FAILURES)} check(s) failed")
        return 1
    say("all Windows token ACL checks passed")
    return 0


def entry() -> int:
    try:
        code = main()
    except BaseException as exc:  # report, never just die with a bare exit code
        import traceback
        say("UNCAUGHT " + "".join(traceback.format_exception_only(type(exc), exc)).strip())
        say("".join(traceback.format_exc()[-1500:]))
        code = 1
    if not LOG:  # not Windows: nothing ran
        return code
    annotate("error" if code else "notice", "Windows token ACL " + ("FAILED" if code else "passed"), "\n".join(LOG)[-6000:])
    for item in FAILURES:
        annotate("error", "Windows token ACL check", item)
    return code


if __name__ == "__main__":
    sys.exit(entry())
