"""core/sandbox/backends/_seccomp.py — seccomp-bpf syscall denylist for
NamespaceBackend (closes DEBT-022).

Binds directly to libseccomp.so.2's C API via ctypes rather than hand-
rolling raw BPF instructions: this is exactly the kind of security-
critical, easy-to-get-subtly-wrong code where leaning on a widely-used,
independently-audited library (the same one nsjail, Docker, and Podman
all sit on top of) is the right trade, not "clever." libseccomp.so.2 was
found already present in the build/test environment
(`ldconfig -p | grep seccomp`) — this module has no new runtime
dependency to install, only libseccomp-dev's *headers*, which are not
needed since ctypes talks to the shared library directly.

Design: default-ALLOW with an explicit denylist (SCMP_ACT_ERRNO(EPERM)
for each blocked syscall), matching Docker's own default seccomp profile
philosophy rather than a strict allowlist. A strict allowlist is more
secure in principle but is fragile against arbitrary Python/shell
workloads in ways that are hard to fully enumerate and test in one pass;
a curated denylist of syscalls with essentially no legitimate use inside
a sandboxed task is the safer choice to ship first. Tightening to a
default-DENY allowlist is a natural, tracked follow-up once there is
real operational experience about what sandboxed workloads actually
call.

Blocked action is SCMP_ACT_ERRNO(EPERM), not SCMP_ACT_KILL: a blocked
syscall should look like an ordinary permission failure a program can
report cleanly, not an unexplained crash.

Empirically verified before being relied on (see reconciliation and the
sandbox-fabric commit history for detail): `seccomp_load()` succeeds for
a process that is only *namespaced* root (mapped via
`unshare --map-root-user`, not genuinely privileged on the host) even
before PR_SET_NO_NEW_PRIVS is set -- user-namespace-local capabilities
cover this. no_new_privs is still set first in _ns_init.py regardless,
as unconditional defense-in-depth, not because seccomp_load requires it
in this specific configuration.
"""
import ctypes
import ctypes.util
import sys

_SCMP_ACT_ALLOW = 0x7FFF0000
_EPERM = 1


def _scmp_act_errno(errno: int) -> int:
    return 0x00050000 | (errno & 0x0000FFFF)


# Curated Phase 1 denylist. Each entry: (syscall name, one-line rationale).
# Not a claim of matching any specific reference profile (e.g. Docker's)
# exactly -- a deliberately-scoped starting set, easy to extend.
DENIED_SYSCALLS: tuple[tuple[str, str], ...] = (
    ("ptrace", "process introspection/debugging; common sandbox-escape and privilege-escalation vector"),
    ("process_vm_readv", "direct cross-process memory read; bypasses the point of blocking ptrace"),
    ("process_vm_writev", "direct cross-process memory write; same rationale as process_vm_readv"),
    ("mount", "filesystem mount manipulation; could reshape or escape the chroot jail"),
    ("umount2", "filesystem unmount; same concern as mount"),
    ("pivot_root", "root-filesystem switching; chroot-escape-adjacent"),
    ("reboot", "host-level power control, meaningless and dangerous inside a sandbox"),
    ("swapon", "host-level swap management"),
    ("swapoff", "host-level swap management"),
    ("kexec_load", "kernel replacement; extremely dangerous"),
    ("kexec_file_load", "kernel replacement; extremely dangerous"),
    ("init_module", "kernel module loading; extremely dangerous"),
    ("finit_module", "kernel module loading; extremely dangerous"),
    ("delete_module", "kernel module unloading; extremely dangerous"),
    ("iopl", "direct hardware I/O port access"),
    ("ioperm", "direct hardware I/O port access"),
    ("acct", "process-accounting control, host-level"),
    ("settimeofday", "system clock manipulation"),
    ("clock_settime", "system clock manipulation"),
    ("clock_adjtime", "system clock manipulation"),
    ("adjtimex", "system clock manipulation"),
    ("keyctl", "kernel keyring manipulation"),
    ("add_key", "kernel keyring manipulation"),
    ("request_key", "kernel keyring manipulation"),
    ("bpf", "loading BPF programs; could itself be used against this very filter"),
    ("perf_event_open", "performance-monitoring subsystem; repeated real-world kernel CVE source"),
    ("userfaultfd", "userspace page-fault handling; repeated real-world kernel-exploit vector"),
    ("unshare", "prevents the sandboxed payload from creating further nested namespaces itself"),
    ("setns", "prevents the sandboxed payload from joining a namespace it wasn't given"),
    ("syslog", "kernel log buffer access; information-disclosure risk"),
)


class SeccompError(RuntimeError):
    pass


def apply_denylist(deny: tuple[tuple[str, str], ...] = DENIED_SYSCALLS) -> list[str]:
    """Load a default-ALLOW seccomp-bpf filter denying `deny`'s syscalls.

    Returns the list of syscall names actually resolved and blocked on
    this architecture (a name that fails to resolve is skipped, not
    fatal -- keeps this portable across architectures where a given
    syscall may not exist, rather than hard-failing Phase 1 on anything
    but the exact platform this was built on).

    Raises SeccompError if the library can't be loaded or seccomp_load
    itself fails -- unlike a missing syscall name, that is not something
    to silently continue past (PI LAW 3: never silently degrade
    isolation).
    """
    try:
        lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise SeccompError(f"libseccomp.so.2 not available: {exc}") from exc

    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]

    ctx = lib.seccomp_init(_SCMP_ACT_ALLOW)
    if not ctx:
        raise SeccompError("seccomp_init returned NULL")

    blocked: list[str] = []
    try:
        errno_action = _scmp_act_errno(_EPERM)
        for name, _rationale in deny:
            syscall_num = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
            if syscall_num < 0:
                continue  # not present on this architecture; skip, don't fail
            rc = lib.seccomp_rule_add(ctx, errno_action, syscall_num, 0)
            if rc != 0:
                raise SeccompError(f"seccomp_rule_add({name}) failed: rc={rc}")
            blocked.append(name)

        rc = lib.seccomp_load(ctx)
        if rc != 0:
            err = ctypes.get_errno()
            raise SeccompError(f"seccomp_load failed: rc={rc} errno={err}")
    finally:
        lib.seccomp_release(ctx)

    return blocked


if __name__ == "__main__":  # pragma: no cover -- manual smoke check
    result = apply_denylist()
    print(f"seccomp: blocked {len(result)} syscalls", file=sys.stderr)
