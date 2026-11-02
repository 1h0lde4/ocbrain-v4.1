#!/usr/bin/env python3
"""
scripts/check_token_acl_windows.py -- validate the REAL owner-only ACL on the API token file.

Run by the `token-acl-windows` CI job on a Windows runner (DEBT-025).  It is the only
place Windows evidence for interface/auth.py comes from: the unit tests stub icacls and
prove logic only, and everything POSIX proves nothing about NTFS.

It uses stdlib + interface.auth only (no third-party install) and drives the real
`icacls` and `whoami`.  What it establishes, and what it does not:

  establishes  that a token file created by load_or_create_token(), rotate_token() and the
               frozen-build default path grants access to no principal other than the
               current user plus SYSTEM, Administrators and OWNER RIGHTS (which a file
               cannot be kept from; a first CI run showed a new file already carries
               them as explicit entries), seen two ways (icacls display names and SDDL
               SIDs); and that a deliberately loosened ACL (Everyone and Users: read) is
               repaired on the next load.
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


BROAD_NAMES = {"everyone", "builtin\\users", "nt authority\\authenticated users",
               "nt authority\\interactive", "nt authority\\network", "builtin\\guests"}


def principals(path: Path) -> list[str]:
    """Principals named in `icacls <file>` (display names: an English runner is assumed here)."""
    out = []
    for ln in run("icacls", str(path)).splitlines():
        if ":(" in ln:
            head = ln.split(":(")[0]
            out.append(head[len(str(path)):].strip() if head.startswith(str(path)) else head.strip())
    return out


def private(path: Path, sid: str, label: str) -> None:
    """Two independent views of the same file: names from the listing, SIDs from SDDL."""
    names = [p.lower() for p in principals(path)]
    broad = [n for n in names if n in BROAD_NAMES]
    check(f"{label}: no broad principal in the icacls listing", not broad, f"listing={names} broad={broad}")
    check(f"{label}: the current user is in the listing", any(os.environ.get("USERNAME", "").lower() in n for n in names), f"listing={names}")
    from interface import auth
    trustees = auth._sddl_trustees(auth._windows_acl_sddl(path))
    allowed = {"SY", "BA", "OW", sid} | ({"LA"} if sid.endswith("-500") else set())
    check(f"{label}: SDDL trustees are only SYSTEM/Administrators/OWNER RIGHTS/the user", set(trustees) <= allowed, f"trustees={trustees}")
    check(f"{label}: SDDL contains the current user", bool(set(trustees) & {sid, "LA"}), f"trustees={trustees}")


def main() -> int:
    if os.name != "nt":
        print("Not Windows: nothing to validate here (this check is Windows-only).")
        return 0

    from interface import auth

    say(f"python {sys.version.split()[0]} on {sys.platform}")
    me = run("whoami").strip()
    sid = auth._windows_current_sid()
    say(f"current user: {me}  sid: {sid}")
    work = Path(tempfile.mkdtemp(prefix="ocb-acl-"))
    try:
        # 1. a freshly created token file
        path = work / "api_token"
        os.environ.pop(auth.ENV_TOKEN, None)
        os.environ[auth.ENV_TOKEN_FILE] = str(path)
        token = auth.load_or_create_token()
        say("icacls listing of the new file:\n" + run("icacls", str(path)).strip())
        private(path, sid, "new file")

        # 2. a loosened ACL (Everyone + Users: read) is repaired on the next load; the token is unchanged
        run("icacls", str(path), "/grant", "*S-1-1-0:(R)", "*S-1-5-32-545:(R)")
        loosened = [p.lower() for p in principals(path)]
        check("precondition: the ACL really was loosened (Everyone and Users present)",
              "everyone" in loosened and "builtin\\users" in loosened, f"listing={loosened}")
        auth.reset_cache_for_tests()
        again = auth.load_or_create_token()
        say("after repair:\n" + run("icacls", str(path)).strip())
        private(path, sid, "after repair")
        check("token unchanged by the repair", again == token)

        # 3. rotation keeps it private and leaves nothing behind
        new, _ = auth.rotate_token()
        check("rotation: new token differs", new != token)
        private(path, sid, "after rotation")
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
            created_dir = not frozen.parent.exists()
            try:
                auth.reset_cache_for_tests()
                auth.load_or_create_token()
                check("frozen default: file created", frozen.exists(), str(frozen))
                private(frozen, sid, "frozen default")
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
    annotate("error" if code else "notice", "Windows token ACL " + ("FAILED" if code else "passed"), "\n".join(LOG)[-16000:])
    for item in FAILURES:
        annotate("error", "Windows token ACL check", item)
    return code


if __name__ == "__main__":
    sys.exit(entry())
