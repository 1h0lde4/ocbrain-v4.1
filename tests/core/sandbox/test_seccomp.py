"""tests/core/sandbox/test_seccomp.py — Sandbox Fabric, _seccomp module unit tests.

Architecture Sources:
    core/sandbox/backends/_seccomp.py (closes KNOWN_ISSUES.md DEBT-022)

Coverage:
    - apply_denylist() resolves and blocks a non-trivial number of
      syscalls on this architecture, run in a throwaway subprocess (a
      loaded seccomp filter is irreversible and inherited by children --
      never call this in the main test process itself)
    - a blocked syscall (ptrace) returns EPERM after apply_denylist()
    - an unrelated, non-denied syscall (getpid) is unaffected

These are unit-level tests of the module in isolation; full integration
(applied inside the real chroot/namespace chain) is covered by the
seccomp-specific cases in test_namespace_backend.py.
"""
import subprocess
import sys

import pytest

from core.sandbox.backends._seccomp import DENIED_SYSCALLS


def _run_in_subprocess(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)


def test_denylist_is_non_trivial():
    assert len(DENIED_SYSCALLS) >= 20
    names = [name for name, _rationale in DENIED_SYSCALLS]
    assert "ptrace" in names
    assert "mount" in names
    assert len(names) == len(set(names)), "duplicate syscall names in the denylist"


def test_apply_denylist_blocks_most_syscalls_on_this_arch():
    code = (
        "from core.sandbox.backends._seccomp import apply_denylist, DENIED_SYSCALLS\n"
        "blocked = apply_denylist()\n"
        "print(len(blocked))\n"
    )
    result = _run_in_subprocess(code)
    assert result.returncode == 0, result.stderr
    blocked_count = int(result.stdout.strip())
    # A handful of names may not resolve on every architecture (skipped,
    # not fatal -- see apply_denylist's docstring), but the large
    # majority should resolve on x86_64/aarch64.
    assert blocked_count >= len(DENIED_SYSCALLS) - 3


def test_ptrace_is_blocked_after_apply(tmp_path=None):
    code = (
        "import ctypes\n"
        "from core.sandbox.backends._seccomp import apply_denylist\n"
        "apply_denylist()\n"
        "libc = ctypes.CDLL(None, use_errno=True)\n"
        "r = libc.ptrace(0, 0, 0, 0)\n"
        "err = ctypes.get_errno()\n"
        "print(r, err)\n"
    )
    result = _run_in_subprocess(code)
    assert result.returncode == 0, result.stderr
    r, err = result.stdout.split()
    assert int(r) == -1
    assert int(err) == 1  # EPERM


def test_getpid_unaffected_after_apply():
    code = (
        "import os\n"
        "from core.sandbox.backends._seccomp import apply_denylist\n"
        "apply_denylist()\n"
        "print(os.getpid())\n"
    )
    result = _run_in_subprocess(code)
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) > 0
