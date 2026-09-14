#!/usr/bin/env python3
"""core/sandbox/backends/_ns_init.py — runs as PID 1 inside the new
user+mount+pid+net+uts namespaces created by namespace_backend.py.

Deliberately a standalone script file, not an inline `-c` string: nested
shell/Python quoting for something this security-sensitive is exactly the
"clever hack" PI §20.8 asks us to avoid, and it is genuinely fragile in
practice (a mis-escaped quote silently changes which bytes reach exec()).

Responsibilities, in order -- order matters for two independent reasons,
both verified empirically, not assumed:
    1. Bind-mount a minimal base rootfs (host /bin,/lib,/lib64,/usr, plus
       any extra --ro paths from the policy) into the workspace, read-only,
       so ordinary interpreters/binaries resolve inside the jail. Must
       happen before the seccomp filter below, which blocks `mount`
       itself for everything downstream of it.
    2. chroot into the workspace and chdir to /. Verified that
       libseccomp.so.2 (needed for step 4) still resolves via the normal
       dynamic-linker search path after this, since /lib and /usr are
       already bind-mounted in by step 1.
    3. Set PR_SET_NO_NEW_PRIVS so a setuid binary inside the jail cannot
       regain privileges. Set before the seccomp filter as conventional
       defense-in-depth, even though seccomp_load() was empirically found
       to succeed either order for a namespace-mapped-root process
       specifically (see _seccomp.py's module docstring).
    4. Load a default-ALLOW seccomp-bpf denylist (core/sandbox/backends/
       _seccomp.py, closing DEBT-022) blocking ptrace, mount/umount2,
       kernel-module and kexec syscalls, clock manipulation, keyring
       syscalls, bpf(), perf_event_open, userfaultfd, and nested
       unshare/setns, among others.
    5. execvp the real command, replacing this process's image.

This process is intentionally still running as (namespaced) uid 0 at this
point -- `unshare --map-root-user` maps that to an unprivileged host uid,
so "root inside" has no meaningful privilege outside the new namespaces.
cgroup membership is joined by the PARENT (namespace_backend.py's
preexec_fn) *before* this script's namespaces even exist, specifically to
avoid any ambiguity about which PID a cgroup.procs write refers to once a
new PID namespace is in play.
"""
import ctypes
import ctypes.util
import os
import subprocess
import sys

# Sibling-module import, not package-qualified: this file runs as a
# standalone script (`python3 /path/to/_ns_init.py ...`) inside a fresh
# interpreter that does not inherit the parent process's sys.path or
# package context, so `from core.sandbox.backends import _seccomp` would
# fail here even though it works everywhere else in this package. Since
# _seccomp.py lives in the same directory, and a directly-invoked
# script's own directory is sys.path[0], a plain sibling import is what
# actually resolves.
import _seccomp

PR_SET_NO_NEW_PRIVS = 38
_BASE_ROOTFS = ("/bin", "/lib", "/lib64", "/usr")


def _bind_ro(host_path: str, workspace: str) -> None:
    if not os.path.isdir(host_path):
        return  # e.g. /lib64 doesn't exist on every distro
    target = os.path.join(workspace, host_path.lstrip("/"))
    os.makedirs(target, exist_ok=True)
    subprocess.run(["mount", "--bind", host_path, target], check=True)
    subprocess.run(
        ["mount", "-o", "remount,ro,bind", target], check=True
    )


def main() -> int:
    args = sys.argv[1:]
    sep = args.index("--")
    workspace = args[0]
    extra_ro = args[1:sep]
    command = args[sep + 1 :]

    for path in (*_BASE_ROOTFS, *extra_ro):
        _bind_ro(path, workspace)

    os.chroot(workspace)
    os.chdir("/")

    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        err = ctypes.get_errno()
        sys.stderr.write(f"_ns_init: prctl(NO_NEW_PRIVS) failed, errno={err}\n")
        return 126

    try:
        _seccomp.apply_denylist()
    except _seccomp.SeccompError as exc:
        sys.stderr.write(f"_ns_init: seccomp denylist failed to load: {exc}\n")
        return 125

    os.execvp(command[0], command)
    return 127  # unreachable unless execvp itself fails to raise


if __name__ == "__main__":
    sys.exit(main())
