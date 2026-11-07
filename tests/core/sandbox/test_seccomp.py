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
    - proves the underlying argument-filtering mechanism using a stand-in
      family (AF_INET) that exists on every kernel: selective blocking by
      address-family argument value, not a blanket socket() block
    - tests the PRODUCTION filter (apply_denylist() with its default
      DENIED_SOCKET_FAMILIES) against AF_ALG and AF_VSOCK directly, in an
      isolated subprocess, each with an unfiltered control and a
      filter-installed check. What is asserted is a property of the filter,
      never of the host kernel: see "THE INVARIANT" below.
    - the int-0x80/socketcall bypass Docker's own CVE-2026-31431 fix also
      covers: compiles a tiny C helper (int $0x80 + MAP_32BIT, the same
      technique moby/moby's own test suite uses) and confirms a filter
      built for native x86_64 only gets libseccomp's unrecognized-
      architecture SIGSYS kill the moment a 32-bit-compat syscall arrives
      -- skipped, not failed, on a host without gcc/32-bit compat support

These are unit-level tests of the module in isolation; full integration
(applied inside the real chroot/namespace chain) is covered by the
seccomp-specific cases in test_namespace_backend.py.
"""
import json
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

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

    families = [f for f, _errno, _rationale in DENIED_SOCKET_FAMILIES]
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


# --------------------------------------------------------------------------------------
# THE INVARIANT (what the AF_ALG / AF_VSOCK tests below do and do not assert)
#
#   The invariant is SECCOMP-ENFORCED, not host-level: "once apply_denylist() has
#   loaded the production filter, socket(AF_ALG, ...) fails with EAFNOSUPPORT and
#   socket(AF_VSOCK, ...) fails with EPERM, and ordinary families are unaffected".
#
#   A kernel without AF_ALG already answers EAFNOSUPPORT (97) with no filter at all,
#   and the production errno for AF_ALG is also 97. On such a kernel a "filtered
#   socket() returned 97" check cannot tell the filter apart from the kernel. A test
#   that asserted "AF_ALG is unreachable on this host" (the test this replaces) was
#   therefore a claim about the kernel, not about the filter, and it failed on every
#   kernel that DOES provide AF_ALG (the GitHub-hosted runner) although the filter
#   was working. So every probe below runs an unfiltered CONTROL first, in the same
#   subprocess, and only claims enforcement where the control makes it discriminating.
# --------------------------------------------------------------------------------------

_EPERM = 1
_EACCES = 13
_EAFNOSUPPORT = 97
_SOCK_STREAM = socket.SOCK_STREAM
_SOCK_SEQPACKET = socket.SOCK_SEQPACKET
_REPO_ROOT = Path(__file__).resolve().parents[3]

_PROBE_TEMPLATE = textwrap.dedent(
    """
    import json, socket
    from core.sandbox.backends import _seccomp

    def seccomp_status():
        out = {{}}
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith(("Seccomp:", "Seccomp_filters:")):
                    key, value = line.split(":", 1)
                    out[key] = int(value)
        return out

    def attempt(family, sock_type):
        try:
            s = socket.socket(family, sock_type, 0)
        except OSError as exc:
            return exc.errno
        s.close()
        return 0

    result = {{"before": {{"status": seccomp_status(), "errno": attempt({family}, {sock_type})}}}}
    result["applied"] = {apply_call}
    result["after"] = {{
        "status": seccomp_status(),
        "errno": attempt({family}, {sock_type}),
        "af_unix_errno": attempt(socket.AF_UNIX, socket.SOCK_STREAM),
        "af_inet_errno": attempt(socket.AF_INET, socket.SOCK_STREAM),
    }}
    print(json.dumps(result))
    """
)


def _probe(family: int, sock_type: int, apply_call: str = "_seccomp.apply_denylist()") -> dict:
    """Run, in a throwaway subprocess (a loaded filter is irreversible): an unfiltered attempt
    to create a `family` socket, then `apply_call`, then the same attempt again plus controls."""
    code = _PROBE_TEMPLATE.format(family=family, sock_type=sock_type, apply_call=apply_call)
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30, cwd=_REPO_ROOT
    )
    assert result.returncode == 0, f"probe subprocess failed: rc={result.returncode} stderr={result.stderr!r}"
    return json.loads(result.stdout)


def _verdict(probe: dict, expected_errno: int, *, denied_family_is_inet: bool = False) -> str:
    """Interpret one probe. Raises AssertionError when the filter is shown NOT to enforce the
    invariant (or the probe cannot be trusted); returns "enforced" when the unfiltered control
    makes the filtered result discriminating, or "non-discriminating" when the control already
    returned `expected_errno` (the kernel alone explains the filtered result)."""
    before, after = probe["before"], probe["after"]

    # Filter-installed check: the seccomp state really changed in this process.
    assert after["status"]["Seccomp"] == 2, f"seccomp filter mode not active after apply: {after['status']}"
    if "Seccomp_filters" in before["status"] and "Seccomp_filters" in after["status"]:
        assert after["status"]["Seccomp_filters"] == before["status"]["Seccomp_filters"] + 1, (
            f"apply_denylist() did not add exactly one filter: {before['status']} -> {after['status']}"
        )

    # Control cases: the filter is selective, not a blanket socket() block.
    assert after["af_unix_errno"] == 0, f"AF_UNIX socket() broke after the filter: errno {after['af_unix_errno']}"
    if not denied_family_is_inet:
        assert after["af_inet_errno"] == 0, f"AF_INET socket() broke after the filter: errno {after['af_inet_errno']}"

    # The enforced behaviour itself.
    assert after["errno"] == expected_errno, (
        f"filtered socket() returned errno {after['errno']}, expected {expected_errno} "
        f"(unfiltered control returned {before['errno']})"
    )

    # Unfiltered control: is the filtered result distinguishable from what the kernel does alone?
    if before["errno"] == expected_errno:
        return "non-discriminating"
    assert before["errno"] in (0, _EAFNOSUPPORT), (
        f"unfiltered control returned errno {before['errno']}: this environment adds a refusal of its "
        f"own, so the probe cannot be interpreted; investigate rather than skip"
    )
    return "enforced"


def test_production_table_pins_the_errno_of_each_denied_socket_family():
    from core.sandbox.backends._seccomp import AF_ALG, AF_VSOCK, DENIED_SOCKET_FAMILIES

    assert {family: errno_ for family, errno_, _why in DENIED_SOCKET_FAMILIES} == {
        AF_ALG: _EAFNOSUPPORT,
        AF_VSOCK: _EPERM,
    }


def test_argument_filter_matches_the_af_alg_family_value_on_any_kernel():
    """Host-independent proof that the filter fires on AF_ALG's value (38): the stand-in errno
    (EACCES) is one this kernel never returns for socket(AF_ALG) -- unfiltered it succeeds
    (AF_ALG present) or gives EAFNOSUPPORT (absent) -- so seeing it proves the rule matched.
    Everything else is the production code path (apply_denylist -> libseccomp -> kernel)."""
    from core.sandbox.backends._seccomp import AF_ALG

    probe = _probe(
        AF_ALG, _SOCK_SEQPACKET,
        f"_seccomp.apply_denylist(deny=(), deny_socket_families=(({AF_ALG}, {_EACCES}, 'stand-in errno'),))",
    )
    assert probe["before"]["errno"] in (0, _EAFNOSUPPORT), probe["before"]
    assert _verdict(probe, _EACCES) == "enforced"


def test_production_filter_blocks_af_alg_socket_creation():
    """The CVE-2026-31431 invariant, against the real production filter. The filtered result
    (EAFNOSUPPORT) is only evidence of enforcement on a kernel that provides AF_ALG; on one that
    does not, the kernel alone returns the same errno, so the outcome is reported as a SKIP with
    that reason rather than a pass. The control that justifies the skip is the unfiltered attempt
    in the same subprocess, which must itself have returned EAFNOSUPPORT, and every other
    assertion (filter installed, controls, errno) is made before the skip is raised.
    The AF_ALG argument match itself is proven on every kernel by
    test_argument_filter_matches_the_af_alg_family_value_on_any_kernel."""
    from core.sandbox.backends._seccomp import AF_ALG

    probe = _probe(AF_ALG, _SOCK_SEQPACKET)
    if _verdict(probe, _EAFNOSUPPORT) == "non-discriminating":
        pytest.skip(
            "this kernel has no AF_ALG (the unfiltered control already returned EAFNOSUPPORT), so the "
            "production errno cannot be told apart from the kernel's own refusal; enforcement on this "
            "host is covered by test_argument_filter_matches_the_af_alg_family_value_on_any_kernel"
        )


def test_production_filter_blocks_af_vsock_socket_creation():
    """AF_VSOCK's production errno is EPERM, which a kernel does not return for socket(AF_VSOCK)
    on its own (success, or EAFNOSUPPORT when the module is absent), so this is discriminating
    on every kernel. It skips only if the unfiltered control itself already returns EPERM."""
    from core.sandbox.backends._seccomp import AF_VSOCK

    probe = _probe(AF_VSOCK, _SOCK_STREAM)
    if _verdict(probe, _EPERM) == "non-discriminating":
        pytest.skip(
            "the unfiltered control already returned EPERM (an outer sandbox refuses AF_VSOCK), so "
            "the filter's own EPERM is not distinguishable here"
        )


def test_a_supported_family_exercises_the_discriminating_path_of_the_production_probe():
    """The branch of the AF_ALG test that runs on a kernel WITH AF_ALG (control succeeds, filtered
    attempt returns the production errno) is run here, on every kernel, with AF_INET -- a family
    every kernel supports -- denied with EAFNOSUPPORT through the same apply_denylist() call."""
    probe = _probe(
        socket.AF_INET, _SOCK_STREAM,
        f"_seccomp.apply_denylist(deny=(), deny_socket_families=(({socket.AF_INET}, {_EAFNOSUPPORT}, 'stand-in'),))",
    )
    assert probe["before"]["errno"] == 0
    # AF_INET is the family denied here, so it cannot also serve as the "still works" control.
    assert _verdict(probe, _EAFNOSUPPORT, denied_family_is_inet=True) == "enforced"


def _synthetic_probe(*, before=0, after=_EAFNOSUPPORT, mode=2, before_filters=0, after_filters=1, unix=0, inet=0) -> dict:
    return {
        "before": {"status": {"Seccomp": 0, "Seccomp_filters": before_filters}, "errno": before},
        "applied": [],
        "after": {"status": {"Seccomp": mode, "Seccomp_filters": after_filters},
                  "errno": after, "af_unix_errno": unix, "af_inet_errno": inet},
    }


class TestProbeInterpretation:
    """The interpreter is what decides pass / skip / fail, so each decision is pinned against
    synthetic probe results (including the ones a broken filter would produce)."""

    def test_control_succeeds_and_filtered_attempt_is_refused_is_enforced(self):
        assert _verdict(_synthetic_probe(before=0), _EAFNOSUPPORT) == "enforced"

    def test_control_already_refused_is_non_discriminating_not_enforced(self):
        assert _verdict(_synthetic_probe(before=_EAFNOSUPPORT), _EAFNOSUPPORT) == "non-discriminating"

    def test_a_filter_that_does_not_block_is_a_failure(self):
        with pytest.raises(AssertionError, match="expected 97"):
            _verdict(_synthetic_probe(before=0, after=0), _EAFNOSUPPORT)

    def test_a_filter_returning_the_wrong_errno_is_a_failure(self):
        with pytest.raises(AssertionError, match="expected 97"):
            _verdict(_synthetic_probe(before=0, after=_EPERM), _EAFNOSUPPORT)

    def test_a_filter_that_was_never_installed_is_a_failure(self):
        with pytest.raises(AssertionError, match="not active"):
            _verdict(_synthetic_probe(mode=0), _EAFNOSUPPORT)
        with pytest.raises(AssertionError, match="exactly one filter"):
            _verdict(_synthetic_probe(before_filters=1, after_filters=1), _EAFNOSUPPORT)

    def test_a_blanket_socket_block_is_a_failure(self):
        with pytest.raises(AssertionError, match="AF_UNIX"):
            _verdict(_synthetic_probe(unix=_EPERM), _EAFNOSUPPORT)
        with pytest.raises(AssertionError, match="AF_INET"):
            _verdict(_synthetic_probe(inet=_EPERM), _EAFNOSUPPORT)

    def test_an_unexplained_control_errno_is_a_failure_not_a_skip(self):
        with pytest.raises(AssertionError, match="cannot be interpreted"):
            _verdict(_synthetic_probe(before=_EPERM), _EAFNOSUPPORT)


def test_argument_filtering_selectively_blocks_a_stand_in_family():
    """Proves the seccomp_rule_add_array-based argument filtering
    mechanism itself: block AF_INET specifically (a family every kernel
    provides) and confirm AF_UNIX is
    unaffected -- selective blocking by address-family value, not a
    blanket socket() block. The same mechanism, with AF_ALG's value
    instead of AF_INET's, is what production DENIED_SOCKET_FAMILIES
    relies on."""
    code = (
        "import socket\n"
        "from core.sandbox.backends._seccomp import apply_denylist\n"
        "apply_denylist(deny=(), deny_socket_families=((socket.AF_INET, 1, 'test'),))\n"
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


_SOCKETCALL_INT80_PROBE_C = textwrap.dedent(
    """
    #include <stdio.h>
    #include <sys/mman.h>

    #define AF_INET 2
    #define SOCK_STREAM 1
    #define SYS_SOCKET 1

    int main() {
        unsigned long *args = mmap(NULL, 4096, PROT_READ|PROT_WRITE,
                                    MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT, -1, 0);
        if (args == MAP_FAILED) { perror("mmap"); return 2; }
        args[0] = AF_INET;
        args[1] = SOCK_STREAM;
        args[2] = 0;

        long ret;
        asm volatile(
            "int $0x80"
            : "=a"(ret)
            : "a"(102), "b"(SYS_SOCKET), "c"(args)
            : "memory"
        );
        printf("RESULT=%ld\\n", ret);
        return 0;
    }
    """
)


def _compile_socketcall_probe(tmp_path) -> str | None:
    """Compiles the int-0x80 socketcall probe on the fly. Returns the
    binary path, or None if gcc / 32-bit compat headers aren't available
    (skip, don't fail -- this is testing an optional hardening layer on
    top of coverage that's already proven by the stand-in-family tests
    above, not the primary guarantee)."""
    src = tmp_path / "probe.c"
    src.write_text(_SOCKETCALL_INT80_PROBE_C)
    binary = tmp_path / "probe"
    try:
        r = subprocess.run(
            ["gcc", "-o", str(binary), str(src)], capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    return str(binary)


def test_socketcall_int80_bypass_is_stopped_by_architecture_mismatch(tmp_path):
    """Docker/Moby's PR #52501 (the same CVE-2026-31431 fix) additionally
    denies socketcall(2) because a filter conditioning only the native
    `socket` syscall can be bypassed via the 32-bit compat multiplexer.
    This filter never adds the x86/x32 architectures at all -- so rather
    than needing an explicit rule, libseccomp's own "syscall arrived
    tagged with an architecture I was never told about" safety net kills
    the process outright the moment the int-0x80 syscall lands. Different
    mechanism than Docker's explicit multi-arch denial; same outcome,
    confirmed directly rather than assumed to generalize from the
    native-syscall tests above."""
    probe = _compile_socketcall_probe(tmp_path)
    if probe is None:
        pytest.skip("gcc / 32-bit compat headers not available in this environment")

    baseline = subprocess.run([probe], capture_output=True, text=True, timeout=10)
    if baseline.returncode != 0 or "RESULT=" not in baseline.stdout:
        pytest.skip("int $0x80 32-bit compat syscall path is not reachable on this kernel")

    code = (
        "import os, socket\n"
        "from core.sandbox.backends._seccomp import apply_denylist\n"
        "apply_denylist(deny=(), deny_socket_families=((socket.AF_INET, 1, 'test'),))\n"
        f"os.execv({probe!r}, [{probe!r}])\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == -31, (  # SIGSYS
        f"expected the process to be SIGSYS-killed by libseccomp's unrecognized-architecture "
        f"safety net; got returncode={result.returncode} stdout={result.stdout!r} "
        f"stderr={result.stderr!r} -- if this ever returns 0 with RESULT= in stdout, the "
        f"socketcall bypass is working and this is a real, open gap, not a documented one"
    )
