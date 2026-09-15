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

Added Sept 13, 2026: argument-conditioned blocking of AF_ALG and
AF_VSOCK socket creation (DENIED_SOCKET_FAMILIES), on top of the by-name
denylist above. `socket()` itself stays allowed by default -- this
sandbox's own network-allowlist path (_net_proxy.py) needs ordinary
sockets to work -- but the specific address-family argument is checked
via libseccomp's `seccomp_rule_add_array()` (the non-variadic array form
of `seccomp_rule_add()`, which is far more ctypes-friendly than binding
a true C varargs call). Prompted by CVE-2026-31431 ("Copy Fail",
CVSS 7.8, CERT-EU advisory 2026-005): a logic flaw in the kernel's
algif_aead module reachable via AF_ALG sockets that allows a controlled
page-cache write, exploitable to escalate to root by corrupting a
setuid binary such as `su` in memory -- explicitly documented as working
*inside* containers/namespaces, since it's a kernel-level page-cache
issue rather than something namespace isolation stops on its own. Fixed
upstream (mainline commit merged 1 April 2026) but still rolling out
across distributions as of this writing; Docker/Moby's own default
seccomp profile was independently patched for the same CVE (moby/moby
PR #52501), blocking the identical pair of address families this module
now also blocks. Verified via a stand-in test rather than the literal
CVE scenario: this host's kernel (6.18.44) does not expose AF_ALG at
all (`socket(AF_ALG, ...)` fails with EAFNOSUPPORT regardless of any
seccomp rule), so the argument-filtering *mechanism* was proven instead
by conditionally blocking AF_INET specifically while confirming AF_UNIX
remained unaffected -- selective blocking by address-family argument
value, not a blanket socket() block, verified directly rather than
assumed to generalize correctly to AF_ALG untested.
"""
import ctypes
import ctypes.util
import sys

_SCMP_ACT_ALLOW = 0x7FFF0000
_EPERM = 1
_SCMP_CMP_EQ = 4  # libseccomp's scmp_compare enum; verified empirically (see module docstring)

# AF_ALG=38, AF_VSOCK=40 -- standard Linux socket.h values, not
# libseccomp-specific.
AF_ALG = 38
AF_VSOCK = 40


class _ScmpArgCmp(ctypes.Structure):
    """Mirrors libseccomp's struct scmp_arg_cmp exactly (arg index, compare
    op, and up to two u64 operands) -- passed via seccomp_rule_add_array's
    array-pointer form rather than binding true C varargs through ctypes.
    """

    _fields_ = [
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_int),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


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
    ("socketcall", "legacy socket-syscall multiplexer (32-bit/compat ABIs). Resolves to -1 and is "
                    "skipped on this build host's native x86_64 syscall table -- kept for hosts where "
                    "it DOES resolve. Empirically confirmed on this host that an int-0x80 compat-mode "
                    "attempt to reach it independently gets SIGSYS-killed by libseccomp's own "
                    "unrecognized-architecture safety net (this filter never adds x86/x32 "
                    "architectures) -- this entry is defense-in-depth for that already-covered case, "
                    "not a fix for an open gap; matches Docker/Moby's PR #52501 explicit denial of "
                    "the same syscall for the same underlying CVE-2026-31431 concern."),
)

# socket() itself stays allowed (this sandbox's own network-allowlist
# proxy needs ordinary sockets); these specific address families are
# blocked by argument, not the syscall as a whole. Each entry: (AF_*
# value, rationale).
DENIED_SOCKET_FAMILIES: tuple[tuple[int, str], ...] = (
    (AF_ALG, "CVE-2026-31431 'Copy Fail' (CVSS 7.8, CERT-EU 2026-005): page-cache privilege "
             "escalation via algif_aead, reachable inside containers/namespaces since it's a "
             "kernel-level issue; matches Docker/Moby's own default-profile fix (PR #52501)"),
    (AF_VSOCK, "blocked alongside AF_ALG, matching Docker/Moby's own fix for the same CVE -- "
               "VM-socket family with no legitimate use inside this sandbox"),
)


class SeccompError(RuntimeError):
    pass


def apply_denylist(
    deny: tuple[tuple[str, str], ...] = DENIED_SYSCALLS,
    deny_socket_families: tuple[tuple[int, str], ...] = DENIED_SOCKET_FAMILIES,
) -> list[str]:
    """Load a default-ALLOW seccomp-bpf filter denying `deny`'s syscalls
    outright, plus `deny_socket_families`'s address families for socket()
    specifically (socket() itself stays allowed).

    Returns the syscall names and "socket(AF_*)" labels actually applied
    on this architecture (a name that fails to resolve is skipped, not
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
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    lib.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(_ScmpArgCmp),
    ]
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

        socket_num = lib.seccomp_syscall_resolve_name(b"socket")
        if socket_num >= 0 and deny_socket_families:
            for family, _rationale in deny_socket_families:
                arg_cmp = _ScmpArgCmp(arg=0, op=_SCMP_CMP_EQ, datum_a=family, datum_b=0)
                rc = lib.seccomp_rule_add_array(
                    ctx, errno_action, socket_num, 1, ctypes.byref(arg_cmp)
                )
                if rc != 0:
                    raise SeccompError(f"seccomp_rule_add_array(socket, family={family}) failed: rc={rc}")
                blocked.append(f"socket(family={family})")

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
