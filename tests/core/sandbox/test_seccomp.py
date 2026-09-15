"""tests/core/sandbox/test_seccomp.py — Sandbox Fabric, _seccomp module unit tests.

Architecture Sources:
    core/sandbox/backends/_seccomp.py (closes KNOWN_ISSUES.md DEBT-022;
    also covers the CVE-2026-31431 AF_ALG/AF_VSOCK addition, Sept 13 2026)

Coverage:
    - apply_denylist() resolves and blocks a non-trivial number of
      syscalls on this architecture, run in a throwaway subprocess (a
      loaded seccomp filter is irreversible and inherited by children --
      never call this in the main test process itself)
    - a blocked syscall (ptrace) returns EPERM after apply_denylist()
    - an unrelated, non-denied syscall (getpid) is unaffected
    - DENIED_SOCKET_FAMILIES contains AF_ALG/AF_VSOCK (CVE-2026-31431)
    - ordinary sockets (AF_INET, AF_UNIX) still work after apply_denylist()
      -- socket() itself stays allowed, only specific families are blocked
    - documents, in a real test rather than only a comment, why the CVE
      scenario can't be exercised directly on this host (AF_ALG already
      returns EAFNOSUPPORT here with no filter at all)
    - proves the underlying argument-filtering mechanism using a stand-in
      family (AF_INET) that does exist on this host, since AF_ALG itself
      doesn't: selective blocking by address-family value, not a blanket
      socket() block

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


def test_denied_socket_families_is_non_trivial():
    """CVE-2026-31431 ('Copy Fail') addition: AF_ALG and AF_VSOCK are
    blocked by argument, not by blocking socket() outright."""
    from core.sandbox.backends._seccomp import AF_ALG, AF_VSOCK, DENIED_SOCKET_FAMILIES

    families = [f for f, _rationale in DENIED_SOCKET_FAMILIES]
    assert AF_ALG in families
    assert AF_VSOCK in families
    assert AF_ALG == 38 and AF_VSOCK == 40  # standard Linux socket.h values


def test_ordinary_sockets_still_work_after_apply():
    """socket() itself must stay usable -- this sandbox's own
    network-allowlist proxy (DEBT-023) depends on ordinary AF_INET
    sockets working through the seccomp filter."""
    code = (
        "import socket\n"
        "from core.sandbox.backends._seccomp import apply_denylist\n"
        "apply_denylist()\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.close()\n"
        "u = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
        "u.close()\n"
        "print('OK')\n"
    )
    result = _run_in_subprocess(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_af_alg_is_unreachable_on_this_host_regardless_of_seccomp():
    """Documents, in the test suite itself rather than only in a comment,
    why the CVE-2026-31431 scenario can't be exercised directly here:
    this host's kernel already refuses AF_ALG (EAFNOSUPPORT) with no
    filter loaded at all. The mechanism is proven instead by
    test_argument_filtering_selectively_blocks_a_stand_in_family below,
    using a family that does exist on this host."""
    code = "import socket\ntry:\n    socket.socket(38, socket.SOCK_SEQPACKET, 0)\n    print('CREATED')\nexcept OSError as e:\n    print('BLOCKED', e.errno)\n"
    result = _run_in_subprocess(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("BLOCKED"), (
        "AF_ALG is reachable on this host with no seccomp filter at all -- "
        "re-run test_argument_filtering_selectively_blocks_a_stand_in_family's "
        "logic against AF_ALG directly instead of relying on the stand-in"
    )


def test_argument_filtering_selectively_blocks_a_stand_in_family():
    """Proves the seccomp_rule_add_array-based argument filtering
    mechanism itself: block AF_INET specifically (a family that DOES
    exist on this host, unlike AF_ALG) and confirm AF_UNIX is
    unaffected -- selective blocking by address-family value, not a
    blanket socket() block. The same mechanism, with AF_ALG's value
    instead of AF_INET's, is what production DENIED_SOCKET_FAMILIES
    relies on."""
    code = (
        "import socket\n"
        "from core.sandbox.backends._seccomp import apply_denylist\n"
        "apply_denylist(deny=(), deny_socket_families=((socket.AF_INET, 'test'),))\n"
        "try:\n"
        "    socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "    print('AF_INET_NOT_BLOCKED')\n"
        "except OSError:\n"
        "    print('AF_INET_BLOCKED', end=' ')\n"
        "    try:\n"
        "        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
        "        s.close()\n"
        "        print('AF_UNIX_STILL_WORKS')\n"
        "    except OSError:\n"
        "        print('AF_UNIX_ALSO_BLOCKED')\n"
    )
    result = _run_in_subprocess(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "AF_INET_BLOCKED AF_UNIX_STILL_WORKS", result.stdout
