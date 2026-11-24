#!/usr/bin/env python3
"""scripts/ci_a9_verifier.py -- how the container's AF_VSOCK deny rule is verified (H-D13).

What this is
------------
A9 is the AF_VSOCK ``socketcall`` bypass: a 32-bit static probe using ``int $0x80`` creates
an AF_VSOCK socket although seccomp's argument filters never see the call.  Only an LSM hook
(``security_socket_create``) can refuse it.  This module is the *method* that decides, from
observed behaviour, whether an enforcing LSM refuses it in a container started the way the
product starts one.  It has three parts:

* a pure classifier (``classify``) -- a function of recorded observations only;
* a record builder and validator (``build_record``, ``validate_record``) for
  ``a9-observation.json``;
* a collector (``collect``) that performs the four probe runs through an injectable runner,
  so the whole method is testable with a scripted fake ``docker`` (no Docker host needed).

The method (spec section 4A of the B03 CI hardening specification)
-----------------------------------------------------------------
Runs, all with the same image, the same probe binary, the same kernel and daemon:

* S (subject)  -- the product's own ``docker create`` argv, probe args ``40 1`` (AF_VSOCK);
* C (control)  -- S's argv plus ONLY the removal of LSM confinement; the probe must succeed;
* B1, B2       -- as S with ``1 1`` (AF_UNIX) and ``2 1`` (AF_INET); both must succeed.

Every run prints its own ``CONFINEMENT`` line before the socket attempt, so the enforcement
evidence comes from the container that made the attempt, never from another one.

Classification (first match wins; see ``classify``): INFRASTRUCTURE_ERROR, BYPASS_REPRODUCED,
INVESTIGATION_REQUIRED, INCONCLUSIVE, and MITIGATION_VERIFIED only when every check passed.
Under the owner's decisions H-D1 and H-D12 every classification except MITIGATION_VERIFIED is
red.  MITIGATION_VERIFIED is never produced from an Engine version, a profile name, a
configuration file or the absence of a reproduced bypass; ``engine_floor_corroboration`` is
recorded and never read by the classifier.

What this does NOT establish: that every other route to AF_VSOCK is closed, that ``connect``
or ``bind`` are safe, or that the property holds on another host, at another time, or after
an Engine or profile change.  A verification is a measurement of one host at one time.

CLI
---
``python3 scripts/ci_a9_verifier.py check --record PATH``: validate the record and print its
classification; exit 0 only for a valid MITIGATION_VERIFIED record, 1 for any other valid
record, 2 when the record is missing or invalid (all red).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = "a9-observation/2"

# -- classifications -------------------------------------------------------------------------
INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
BYPASS_REPRODUCED = "BYPASS_REPRODUCED"
INVESTIGATION_REQUIRED = "INVESTIGATION_REQUIRED"
INCONCLUSIVE = "INCONCLUSIVE"
MITIGATION_VERIFIED = "MITIGATION_VERIFIED"
CLASSIFICATIONS = (
    INFRASTRUCTURE_ERROR,
    BYPASS_REPRODUCED,
    INVESTIGATION_REQUIRED,
    INCONCLUSIVE,
    MITIGATION_VERIFIED,
)

# -- constants of the method -------------------------------------------------------------------
AF_UNIX, AF_INET, AF_VSOCK, SOCK_STREAM = 1, 2, 40, 1
EPERM, EACCES = 1, 13
DENIAL_ERRNOS = frozenset({EPERM, EACCES})
RUN_NAMES = ("S", "C", "B1", "B2")
RUN_PROBE_ARGS: dict[str, tuple[int, int]] = {
    "S": (AF_VSOCK, SOCK_STREAM),
    "C": (AF_VSOCK, SOCK_STREAM),
    "B1": (AF_UNIX, SOCK_STREAM),
    "B2": (AF_INET, SOCK_STREAM),
}
# Route (1) of H-D13c: Docker owns the policy.  On AppArmor that is the daemon's own profile.
ROUTE = 1
EXPECTED_APPARMOR_PROFILE = "docker-default"
# SELinux domains a container process runs in under container-selinux.  Anything else
# (unconfined_t, spc_t -- what `label=disable` produces -- ...) is not a confined container.
CONFINED_SELINUX_TYPES = frozenset({"container_t", "container_init_t", "container_kvm_t"})
ENGINE_FLOOR = (29, 8, 0)  # corroboration only; never an input to classify()

# Exit statuses of `docker run`-style failures that mean "no verdict from this run".
_TRUSTED_RC = frozenset({0, 1})

# The probe.  Prints exactly two lines: CONFINEMENT ..., then SUCCEEDED ... or FAILED ...
# The socket attempt is the legacy 32-bit socketcall(2) entry point via `int $0x80`; the
# probe only creates a socket and exits (no connect, no bind).
PROBE_C = r"""
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SYS_SOCKET 1

static long int80_socketcall(int call, long a0, long a1, long a2) {
    long args[3] = {a0, a1, a2};
    long ret;
    __asm__ volatile ("int $0x80" : "=a" (ret) : "a" (102), "b" (call), "c" (args) : "memory");
    return ret;
}

static void read_attr(const char *path, char *out, size_t n) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) { snprintf(out, n, "UNREADABLE"); return; }
    ssize_t r = read(fd, out, n - 1);
    close(fd);
    if (r <= 0) { snprintf(out, n, "UNREADABLE"); return; }
    out[r] = '\0';
    for (ssize_t i = 0; i < r; i++) {
        if (out[i] == '\n' || out[i] == '\0') { out[i] = '\0'; break; }
        if (out[i] == ']') out[i] = '_';
    }
    if (out[0] == '\0') snprintf(out, n, "UNREADABLE");
}

int main(int argc, char **argv) {
    if (argc < 3) { printf("FAILED errno=22\n"); return 1; }
    char aa[256], se[256], at[256];
    read_attr("/proc/self/attr/apparmor/current", aa, sizeof(aa));
    read_attr("/proc/self/attr/selinux/current", se, sizeof(se));
    read_attr("/proc/self/attr/current", at, sizeof(at));
    printf("CONFINEMENT apparmor=[%s] selinux=[%s] attr=[%s]\n", aa, se, at);
    fflush(stdout);
    int domain = atoi(argv[1]);
    int type = atoi(argv[2]);
    long ret = int80_socketcall(SYS_SOCKET, domain, type, 0);
    if (ret < 0) {
        printf("FAILED errno=%ld\n", -ret);
        return 1;
    }
    char linkpath[64], target[256];
    snprintf(linkpath, sizeof(linkpath), "/proc/self/fd/%ld", ret);
    ssize_t n = readlink(linkpath, target, sizeof(target) - 1);
    if (n >= 0) {
        target[n] = '\0';
        printf("SUCCEEDED fd=%ld target=%s\n", ret, target);
        return 0;
    }
    printf("SUCCEEDED fd=%ld target=UNKNOWN\n", ret);
    return 0;
}
"""
PROBE_SOURCE_SHA256 = hashlib.sha256(PROBE_C.encode("utf-8")).hexdigest()

_CONFINEMENT_RE = re.compile(r"^CONFINEMENT apparmor=\[(.*)\] selinux=\[(.*)\] attr=\[(.*)\]$")
_FAILED_RE = re.compile(r"^FAILED errno=(\d+)$")
_SUCCEEDED_RE = re.compile(r"^SUCCEEDED fd=(\d+) target=(.*)$")
UNREADABLE = "UNREADABLE"


# =================================================================================================
# data model
# =================================================================================================


@dataclass(frozen=True)
class Confinement:
    """The three values the probe read from /proc/self/attr in its own container."""

    apparmor: str
    selinux: str
    attr: str


@dataclass(frozen=True)
class RunRecord:
    """Raw facts of one probe run.  Nothing here is interpreted."""

    name: str
    argv: tuple[str, ...]
    container_id: str | None
    rc: int | None
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    probe_sha256: str | None
    image_id: str | None
    inspect: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HostObservation:
    """O1/O2: host LSM state and daemon facts.  A failed query is UNKNOWN, never DISABLED."""

    apparmor: str  # ENABLED | DISABLED | UNKNOWN
    selinux: str  # ENFORCING | PERMISSIVE | DISABLED | UNKNOWN
    docker_security_options: tuple[str, ...] | None  # None = the query failed
    server_version: str | None
    kernel_release: str | None

    @property
    def lsm_backend(self) -> str:
        return lsm_backend(self.apparmor, self.selinux)


@dataclass(frozen=True)
class Observations:
    host: HostObservation
    runs: Mapping[str, RunRecord]
    expected_probe_sha256: str | None
    expected_image_id: str | None
    route: int = ROUTE
    expected_profile: str = EXPECTED_APPARMOR_PROFILE
    compile_error: str | None = None  # diagnostic only; never read by classify()


@dataclass(frozen=True)
class ParsedRun:
    """A run, interpreted.  ``kind`` is OPEN, DENIED, INDETERMINATE or BAD."""

    kind: str
    errno: int | None
    confinement: Confinement | None
    problem: str | None

    @property
    def trustworthy(self) -> bool:
        return self.kind in ("OPEN", "DENIED")


@dataclass(frozen=True)
class Enforcement:
    state: str  # ENFORCING | NON_ENFORCING | UNKNOWN
    scope: tuple[str, ...]  # the backends exercised: subset of ("apparmor", "selinux")
    profile: str | None
    detail: str


@dataclass(frozen=True)
class Classification:
    label: str
    reasons: tuple[str, ...]
    deny_rule: str  # OBSERVED_BEHAVIORAL | NOT_OBSERVED | UNKNOWN
    verified_scope: tuple[str, ...]


# =================================================================================================
# host LSM state
# =================================================================================================


def lsm_backend(apparmor: str, selinux: str) -> str:
    """apparmor | selinux | both | none | unknown.

    SELinux Permissive counts as an active backend (it stays distinct from Enforcing for the
    enforcement decision).  Any UNKNOWN that could change the answer makes the backend unknown.
    """
    aa_active = apparmor == "ENABLED"
    se_active = selinux in ("ENFORCING", "PERMISSIVE")
    if apparmor == "UNKNOWN" or selinux == "UNKNOWN":
        return "unknown"
    if aa_active and se_active:
        return "both"
    if aa_active:
        return "apparmor"
    if se_active:
        return "selinux"
    return "none"


def _version_tuple(version: str | None) -> tuple[int, ...] | None:
    if not version:
        return None
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", version.strip())
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def engine_floor_corroboration(server_version: str | None) -> bool:
    """True when the Engine is at or above the release that carries the upstream rule.

    Corroboration only.  ``classify`` never reads this, in either direction.
    """
    v = _version_tuple(server_version)
    return v is not None and v >= ENGINE_FLOOR


# =================================================================================================
# probe output
# =================================================================================================


def parse_run(run: RunRecord) -> ParsedRun:
    """Interpret one run.  Anything that is not exactly the probe protocol is BAD."""

    def bad(problem: str) -> ParsedRun:
        return ParsedRun("BAD", None, None, problem)

    if run.timed_out:
        return bad("timeout")
    if run.rc is None:
        return bad("no exit status")
    if run.rc not in _TRUSTED_RC:
        return bad(f"docker or container status {run.rc}")
    lines = [ln.rstrip("\r") for ln in run.stdout.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    if len(lines) != 2:
        return bad(f"expected exactly 2 output lines, got {len(lines)}")
    m_conf = _CONFINEMENT_RE.match(lines[0])
    if not m_conf:
        return bad("first line is not a CONFINEMENT line")
    conf = Confinement(m_conf.group(1).strip(), m_conf.group(2).strip(), m_conf.group(3).strip())
    m_fail = _FAILED_RE.match(lines[1])
    m_ok = _SUCCEEDED_RE.match(lines[1])
    if m_fail and not m_ok:
        if run.rc != 1:
            return bad("FAILED line with a status other than 1")
        return ParsedRun("DENIED", int(m_fail.group(1)), conf, None)
    if m_ok and not m_fail:
        if run.rc != 0:
            return bad("SUCCEEDED line with a status other than 0")
        if m_ok.group(2).startswith("socket:["):
            return ParsedRun("OPEN", None, conf, None)
        return ParsedRun("INDETERMINATE", None, conf, "SUCCEEDED without a socket target")
    return bad("second line is neither SUCCEEDED nor FAILED")


# =================================================================================================
# enforcement evidence
# =================================================================================================


def _apparmor_value(conf: Confinement, backend: str) -> str:
    """The AppArmor attribute: the per-LSM file, or the generic one when AppArmor is the only LSM."""
    if conf.apparmor != UNREADABLE:
        return conf.apparmor
    if backend == "apparmor" and conf.attr != UNREADABLE:
        return conf.attr
    return UNREADABLE


def _selinux_value(conf: Confinement, backend: str) -> str:
    if conf.selinux != UNREADABLE:
        return conf.selinux
    if backend == "selinux" and conf.attr != UNREADABLE:
        return conf.attr
    return UNREADABLE


_APPARMOR_RE = re.compile(r"^(?P<name>.+) \((?P<mode>[a-z]+)\)$")


def apparmor_state(value: str) -> tuple[str, str | None]:
    """(CONFINED_ENFORCE | CONFINED_COMPLAIN | UNCONFINED | UNKNOWN, profile name)."""
    v = value.strip()
    if v == "unconfined":
        return "UNCONFINED", None
    m = _APPARMOR_RE.match(v)
    if not m:
        return "UNKNOWN", None
    if m.group("mode") == "enforce":
        return "CONFINED_ENFORCE", m.group("name")
    if m.group("mode") == "complain":
        return "CONFINED_COMPLAIN", m.group("name")
    return "UNKNOWN", None


def selinux_state(value: str) -> str:
    """CONFINED | UNCONFINED | UNKNOWN for an SELinux context ``user:role:type:level``."""
    v = value.strip()
    if v == UNREADABLE or v == "":
        return "UNKNOWN"
    parts = v.split(":")
    if len(parts) < 3 or not parts[2]:
        return "UNKNOWN"
    return "CONFINED" if parts[2] in CONFINED_SELINUX_TYPES else "UNCONFINED"


def _option_listed(options: tuple[str, ...] | None, name: str) -> bool | None:
    """Whether `docker info` lists a security option; None when the query failed."""
    if options is None:
        return None
    return any(o == f"name={name}" or o.startswith(f"name={name},") for o in options)


def evaluate_enforcement(host: HostObservation, conf: Confinement) -> Enforcement:
    """Does an enforcing LSM confine the probe's own container?  (O1, O3-AA, O3-SE)

    NON_ENFORCING is a positive finding (complain, Permissive, unconfined, no LSM, an option
    the daemon does not apply).  UNKNOWN is any evidence that is unreadable or failed.
    """
    backend = host.lsm_backend
    if backend == "none":
        return Enforcement("NON_ENFORCING", (), None, "no LSM is active on the host")
    if backend == "unknown":
        return Enforcement("UNKNOWN", (), None, "host LSM state could not be established")

    states: list[str] = []
    scope: list[str] = []
    details: list[str] = []
    profile: str | None = None

    if backend in ("apparmor", "both"):
        scope.append("apparmor")
        mode, name = apparmor_state(_apparmor_value(conf, backend))
        listed = _option_listed(host.docker_security_options, "apparmor")
        if listed is False:
            states.append("NON_ENFORCING")
            details.append("docker info does not list apparmor")
        elif mode == "CONFINED_ENFORCE":
            states.append("ENFORCING")
            profile = name
            details.append(f"apparmor profile {name} (enforce)")
        elif mode in ("CONFINED_COMPLAIN", "UNCONFINED"):
            states.append("NON_ENFORCING")
            details.append(f"apparmor {mode.lower()}")
        else:
            states.append("UNKNOWN")
            details.append("apparmor attribute unreadable")

    if backend in ("selinux", "both"):
        scope.append("selinux")
        listed = _option_listed(host.docker_security_options, "selinux")
        domain = selinux_state(_selinux_value(conf, backend))
        if host.selinux == "PERMISSIVE":
            states.append("NON_ENFORCING")
            details.append("selinux Permissive")
        elif listed is False:
            states.append("NON_ENFORCING")
            details.append("docker info does not list selinux")
        elif domain == "UNCONFINED":
            states.append("NON_ENFORCING")
            details.append("selinux context is not a container domain")
        elif listed is None or domain == "UNKNOWN":
            states.append("UNKNOWN")
            details.append("selinux evidence unreadable")
        else:
            states.append("ENFORCING")
            details.append("selinux Enforcing, container domain, listed by the daemon")

    if "UNKNOWN" in states:
        state = "UNKNOWN"
    elif "ENFORCING" in states:
        state = "ENFORCING"
    else:
        state = "NON_ENFORCING"
    return Enforcement(state, tuple(scope), profile, "; ".join(details))


def control_confinement(host: HostObservation, conf: Confinement) -> str:
    """CONFINED | UNCONFINED | UNKNOWN: did the control really remove the LSM confinement?"""
    backend = host.lsm_backend
    checks: list[str] = []
    if backend in ("apparmor", "both", "unknown", "none"):
        mode, _ = apparmor_state(_apparmor_value(conf, backend))
        if mode in ("CONFINED_ENFORCE", "CONFINED_COMPLAIN"):
            checks.append("CONFINED")
        elif mode == "UNCONFINED":
            checks.append("UNCONFINED")
        else:
            # An unreadable attribute is only acceptable where AppArmor is not in play.
            checks.append("UNCONFINED" if backend == "none" else "UNKNOWN")
    if backend in ("selinux", "both", "unknown", "none"):
        dom = selinux_state(_selinux_value(conf, backend))
        if dom == "CONFINED":
            checks.append("CONFINED")
        elif dom == "UNCONFINED":
            checks.append("UNCONFINED")
        else:
            checks.append("UNCONFINED" if backend == "none" else "UNKNOWN")
    if "CONFINED" in checks:
        return "CONFINED"
    if "UNKNOWN" in checks:
        return "UNKNOWN"
    return "UNCONFINED"


# =================================================================================================
# the classifier
# =================================================================================================


def classify(obs: Observations) -> Classification:
    """Spec 4A.5.  A pure function of the observations; the first matching row wins.

    Deliberately never reads ``obs.host.server_version``: the Engine version is corroboration
    only, so a custom deployed rule on an older Engine can verify and a new Engine with no
    rule cannot.
    """

    def result(label: str, *reasons: str, scope: tuple[str, ...] = ()) -> Classification:
        if label == MITIGATION_VERIFIED:
            deny = "OBSERVED_BEHAVIORAL"
        elif label == BYPASS_REPRODUCED:
            deny = "NOT_OBSERVED"
        else:
            deny = "UNKNOWN"
        return Classification(label, tuple(reasons), deny, scope)

    s_run = obs.runs.get("S")
    s = parse_run(s_run) if s_run is not None else None

    def identity_mismatch(run: RunRecord) -> str | None:
        if obs.expected_probe_sha256 is not None and run.probe_sha256 != obs.expected_probe_sha256:
            return "probe sha256 differs from the compiled probe"
        if obs.expected_image_id is not None and run.image_id != obs.expected_image_id:
            return "image id differs from the intended image"
        return None

    # 1. S untrustworthy.
    if s_run is None or s is None:
        return result(INFRASTRUCTURE_ERROR, "infra_subject", "subject run missing")
    if not s.trustworthy:
        return result(INFRASTRUCTURE_ERROR, "infra_subject", s.problem or "subject run untrustworthy")
    mism = identity_mismatch(s_run)
    if mism:
        return result(INFRASTRUCTURE_ERROR, "infra_subject", mism)

    # 2. A valid reproduced bypass outranks everything below.
    if s.kind == "OPEN":
        return result(BYPASS_REPRODUCED, "bypass_open")

    # 3. C, B1, B2 that ran but cannot be trusted, or ran against another probe or image.
    parsed: dict[str, ParsedRun] = {}
    for name in ("C", "B1", "B2"):
        run = obs.runs.get(name)
        if run is None:
            continue
        p = parse_run(run)
        parsed[name] = p
        if not p.trustworthy:
            return result(INFRASTRUCTURE_ERROR, "infra", f"{name}: {p.problem}")
        mism = identity_mismatch(run)
        if mism is None and s_run.probe_sha256 != run.probe_sha256:
            mism = "probe sha256 differs from S's"
        if mism is None and s_run.image_id != run.image_id:
            mism = "image id differs from S's"
        if mism:
            return result(INFRASTRUCTURE_ERROR, "infra", f"{name}: {mism}")

    c = parsed.get("C")
    b1, b2 = parsed.get("B1"), parsed.get("B2")

    # 4. The control must be open: the probe can open the socket on this kernel.
    if c is None or c.kind != "OPEN":
        reasons = ["control_not_open"]
        if c is not None and c.kind == "DENIED" and b1 is not None and b1.kind == "DENIED" \
                and b2 is not None and b2.kind == "DENIED":
            reasons.append("socketcall_blocked_wholesale")
        return result(INCONCLUSIVE, *reasons)

    # 5. The control's own line must show the confinement is really gone.
    assert c.confinement is not None and s.confinement is not None
    c_state = control_confinement(obs.host, c.confinement)
    if c_state == "CONFINED":
        return result(INVESTIGATION_REQUIRED, "control_invalid")

    # 6. The denial must be one an LSM issues.
    if s.errno not in DENIAL_ERRNOS:
        return result(INVESTIGATION_REQUIRED, "unexpected_errno", f"errno={s.errno}")

    # 7. and 8. The denial must be attributed to an enforcing LSM, by S's own container.
    enf = evaluate_enforcement(obs.host, s.confinement)
    if enf.state == "UNKNOWN":
        return result(INCONCLUSIVE, "enforcement_unverified", enf.detail)
    if enf.state == "NON_ENFORCING":
        return result(INVESTIGATION_REQUIRED, "denial_not_attributed", enf.detail)

    # 9. Route (1): Docker owns the policy, so the AppArmor profile must be Docker's.
    if obs.route == ROUTE and "apparmor" in enf.scope and enf.profile != obs.expected_profile:
        return result(INCONCLUSIVE, "profile_not_route_policy", f"profile={enf.profile!r}")

    # 10. No over-blocking: benign sockets still work through the same path.
    if b1 is None or b2 is None or b1.kind != "OPEN" or b2.kind != "OPEN":
        return result(INVESTIGATION_REQUIRED, "over_blocking")

    # (Not in the spec's table, which is silent: a control whose own confinement cannot be read does
    # not show the confinement was removed.  It only ever blocks row 11; it never changes the
    # outcome of rows 1 to 10.)
    if c_state == "UNKNOWN":
        return result(INCONCLUSIVE, "control_confinement_unverified")

    # 11. Everything above passed.
    return result(MITIGATION_VERIFIED, "verified", scope=enf.scope)


# =================================================================================================
# argv
# =================================================================================================


def control_options(lsm: str) -> tuple[str, ...]:
    """The one deliberate weakening of the control run: removal of LSM confinement.

    Never ``--privileged``, never ``seccomp=unconfined``: the control is S's argv plus these
    options and nothing else.
    """
    opts: list[str] = []
    if lsm in ("apparmor", "both", "unknown"):
        opts += ["--security-opt", "apparmor=unconfined"]
    if lsm in ("selinux", "both", "unknown"):
        opts += ["--security-opt", "label=disable"]
    return tuple(opts)


def control_argv(subject_argv: Sequence[str], lsm: str) -> list[str]:
    """S's argv plus only the LSM-removal options, inserted right after `docker create`."""
    argv = list(subject_argv)
    if argv[:2] != ["docker", "create"]:
        raise ValueError("expected a `docker create` argv")
    return argv[:2] + list(control_options(lsm)) + argv[2:]


def argv_difference(base: Sequence[str], other: Sequence[str]) -> list[str] | None:
    """The tokens ``other`` has beyond ``base``, or None when ``other`` is not base plus insertions.

    Used to prove the control differs from S by exactly the LSM option (the argv builders are
    called with the same name/command normalisation by the caller).
    """
    extra: list[str] = []
    i = 0
    for tok in other:
        if i < len(base) and tok == base[i]:
            i += 1
        else:
            extra.append(tok)
    return extra if i == len(base) else None


# =================================================================================================
# the record
# =================================================================================================


def _run_to_json(run: RunRecord) -> dict[str, Any]:
    parsed = parse_run(run)
    return {
        "name": run.name,
        "argv": list(run.argv),
        "container_id": run.container_id,
        "rc": run.rc,
        "stdout": run.stdout,
        "stderr": run.stderr,
        "errno": parsed.errno,
        "duration_s": run.duration_s,
        "timed_out": run.timed_out,
        "probe_sha256": run.probe_sha256,
        "image_id": run.image_id,
        "inspect": dict(run.inspect),
    }


def _run_from_json(d: Mapping[str, Any]) -> RunRecord:
    return RunRecord(
        name=str(d["name"]),
        argv=tuple(str(a) for a in d["argv"]),
        container_id=d.get("container_id"),
        rc=d.get("rc"),
        stdout=str(d["stdout"]),
        stderr=str(d["stderr"]),
        duration_s=float(d["duration_s"]),
        timed_out=bool(d["timed_out"]),
        probe_sha256=d.get("probe_sha256"),
        image_id=d.get("image_id"),
        inspect=dict(d.get("inspect", {})),
    )


def _host_to_json(host: HostObservation) -> dict[str, Any]:
    return {
        "apparmor": host.apparmor,
        "selinux": host.selinux,
        "docker_security_options": None if host.docker_security_options is None
        else list(host.docker_security_options),
        "server_version": host.server_version,
        "kernel_release": host.kernel_release,
        "lsm_backend": host.lsm_backend,
    }


def _host_from_json(d: Mapping[str, Any]) -> HostObservation:
    opts = d.get("docker_security_options")
    return HostObservation(
        apparmor=str(d["apparmor"]),
        selinux=str(d["selinux"]),
        docker_security_options=None if opts is None else tuple(str(o) for o in opts),
        server_version=d.get("server_version"),
        kernel_release=d.get("kernel_release"),
    )


def build_record(
    obs: Observations,
    *,
    invocation_id: str,
    image_ref: str | None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """The evidence record (``a9-observation.json``).  No secrets, no environment dumps."""
    cls = classify(obs)
    backend = obs.host.lsm_backend
    active = {"apparmor": ["apparmor"], "selinux": ["selinux"], "both": ["apparmor", "selinux"]}
    scope = list(active.get(backend, [])) if cls.label == MITIGATION_VERIFIED else []
    return {
        "schema_version": SCHEMA_VERSION,
        "invocation_id": invocation_id,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "probe_source_sha256": PROBE_SOURCE_SHA256,
        "compile_error": obs.compile_error,
        "expected": {"probe_sha256": obs.expected_probe_sha256, "image_id": obs.expected_image_id,
                     "image_ref": image_ref},
        "host": _host_to_json(obs.host),
        "runs": {name: _run_to_json(run) for name, run in obs.runs.items()},
        "route": obs.route,
        "expected_profile": obs.expected_profile,
        "engine_floor_corroboration": engine_floor_corroboration(obs.host.server_version),
        "classification": cls.label,
        "reasons": list(cls.reasons),
        "deny_rule": cls.deny_rule,
        "lsm_backend": backend,
        "verified_scope": scope,
        "combined_scope": backend == "both" and cls.label == MITIGATION_VERIFIED,
        "scope_note": (
            "This record certifies only the backends listed in verified_scope. When both are active the "
            "scope is combined and neither backend is certified independently."
        ),
    }


_TOP_LEVEL_KEYS = (
    "schema_version", "invocation_id", "generated_at", "probe_source_sha256", "expected", "host",
    "runs", "route", "expected_profile", "engine_floor_corroboration", "classification", "reasons",
    "deny_rule", "lsm_backend", "verified_scope", "combined_scope",
)
_HOST_ENUMS = {
    "apparmor": ("ENABLED", "DISABLED", "UNKNOWN"),
    "selinux": ("ENFORCING", "PERMISSIVE", "DISABLED", "UNKNOWN"),
}
_RUN_KEYS = ("name", "argv", "container_id", "rc", "stdout", "stderr", "errno", "duration_s", "timed_out")


def observations_from_record(record: Mapping[str, Any]) -> Observations:
    exp = record["expected"]
    return Observations(
        host=_host_from_json(record["host"]),
        runs={name: _run_from_json(r) for name, r in record["runs"].items()},
        expected_probe_sha256=exp.get("probe_sha256"),
        expected_image_id=exp.get("image_id"),
        route=int(record["route"]),
        expected_profile=str(record["expected_profile"]),
        compile_error=record.get("compile_error"),
    )


def validate_record(
    record: object,
    *,
    expect_invocation_id: str | None = None,
    max_age_s: float | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Problems with a record; an empty list means valid.  Fail closed on anything odd.

    Beyond the shape it checks that the stored classification, reasons and scope equal what the
    classifier computes from the stored raw runs (a record whose verdict does not follow from its
    own evidence is invalid), that the record names no backend that was not active (MV-15), and
    that it is not stale.
    """
    if not isinstance(record, dict):
        return ["record is not a JSON object"]
    problems: list[str] = []
    for key in _TOP_LEVEL_KEYS:
        if key not in record:
            problems.append(f"missing key {key!r}")
    if problems:
        return problems
    if record["schema_version"] != SCHEMA_VERSION:
        return [f"schema_version {record['schema_version']!r} is not {SCHEMA_VERSION!r}"]
    if record["classification"] not in CLASSIFICATIONS:
        problems.append(f"unknown classification {record['classification']!r}")
    if record["deny_rule"] not in ("OBSERVED_BEHAVIORAL", "NOT_OBSERVED", "UNKNOWN"):
        problems.append(f"unknown deny_rule {record['deny_rule']!r}")
    if not isinstance(record["reasons"], list) or not all(isinstance(r, str) for r in record["reasons"]):
        problems.append("reasons must be a list of strings")
    host = record["host"]
    if not isinstance(host, dict):
        return problems + ["host is not an object"]
    for key, allowed in _HOST_ENUMS.items():
        if host.get(key) not in allowed:
            problems.append(f"host.{key} {host.get(key)!r} not in {allowed}")
    runs = record["runs"]
    if not isinstance(runs, dict):
        return problems + ["runs is not an object"]
    for name, r in runs.items():
        if name not in RUN_NAMES:
            problems.append(f"unknown run {name!r}")
            continue
        if not isinstance(r, dict):
            problems.append(f"run {name} is not an object")
            continue
        for key in _RUN_KEYS:
            if key not in r:
                problems.append(f"run {name} missing key {key!r}")
    if problems:
        return problems

    try:
        obs = observations_from_record(record)
    except (KeyError, TypeError, ValueError) as exc:
        return [f"record cannot be read back: {exc}"]

    # The record must not certify what it did not exercise (MV-15).
    backend = obs.host.lsm_backend
    if record["lsm_backend"] != backend:
        problems.append(f"lsm_backend {record['lsm_backend']!r} does not follow from host ({backend!r})")
    active = {"apparmor": ["apparmor"], "selinux": ["selinux"], "both": ["apparmor", "selinux"]}
    allowed_scope = set(active.get(backend, []))
    scope = record["verified_scope"]
    if not isinstance(scope, list) or not set(scope) <= allowed_scope:
        problems.append(f"verified_scope {scope!r} names a backend that was not active ({backend!r})")
    if record["classification"] == MITIGATION_VERIFIED and (not scope or set(scope) != allowed_scope):
        problems.append("MITIGATION_VERIFIED must certify exactly the backends that were active")
    if record["classification"] != MITIGATION_VERIFIED and scope:
        problems.append("only MITIGATION_VERIFIED may carry a verified_scope")
    if record["combined_scope"] != (backend == "both" and record["classification"] == MITIGATION_VERIFIED):
        problems.append("combined_scope is inconsistent with lsm_backend and classification")

    # The corroboration flag is recorded, and recorded honestly.
    if record["engine_floor_corroboration"] != engine_floor_corroboration(obs.host.server_version):
        problems.append("engine_floor_corroboration does not follow from host.server_version")

    # The verdict must follow from the evidence in the record.
    recomputed = classify(obs)
    if recomputed.label != record["classification"]:
        problems.append(
            f"classification {record['classification']!r} does not follow from the recorded runs "
            f"(recomputed {recomputed.label!r})"
        )
    if list(recomputed.reasons) != record["reasons"]:
        problems.append("reasons do not follow from the recorded runs")
    if recomputed.deny_rule != record["deny_rule"]:
        problems.append("deny_rule does not follow from the recorded runs")

    # Staleness (MV-11).
    if expect_invocation_id is not None and record["invocation_id"] != expect_invocation_id:
        problems.append("record belongs to another invocation (stale)")
    if max_age_s is not None:
        try:
            made = datetime.fromisoformat(str(record["generated_at"]))
            if made.tzinfo is None:
                made = made.replace(tzinfo=timezone.utc)
            age = ((now or datetime.now(timezone.utc)) - made).total_seconds()
            if age > max_age_s or age < -60:
                problems.append(f"record age {age:.0f}s is outside the allowed window")
        except ValueError:
            problems.append("generated_at is not an ISO timestamp")
    return problems


def load_record(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"cannot read record {path}: {exc}"]
    try:
        rec = json.loads(raw)
    except ValueError as exc:
        return None, [f"record is not valid JSON: {exc}"]
    if not isinstance(rec, dict):
        return None, ["record is not a JSON object"]
    return rec, []


# =================================================================================================
# collector (runner-injected; the real runner shells out, the tests script it)
# =================================================================================================


@dataclass(frozen=True)
class CommandResult:
    rc: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    not_found: bool = False
    duration_s: float = 0.0


class Runner(Protocol):
    def __call__(self, argv: Sequence[str], timeout: float) -> CommandResult: ...


def subprocess_runner(argv: Sequence[str], timeout: float) -> CommandResult:
    """The real runner.  A timeout or a missing executable is reported, never raised."""
    start = time.monotonic()
    try:
        cp = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        def _txt(v: object) -> str:
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else (v if isinstance(v, str) else "")
        return CommandResult(None, _txt(exc.stdout), _txt(exc.stderr), timed_out=True,
                             duration_s=time.monotonic() - start)
    except FileNotFoundError:
        return CommandResult(None, "", f"{argv[0]}: not found", not_found=True,
                             duration_s=time.monotonic() - start)
    except OSError as exc:
        return CommandResult(None, "", f"{argv[0]}: {exc}", duration_s=time.monotonic() - start)
    return CommandResult(cp.returncode, cp.stdout, cp.stderr, duration_s=time.monotonic() - start)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text(path: str) -> tuple[str | None, str]:
    """(text, status) with status OK | ABSENT | ERROR.  ABSENT is conclusive, ERROR is not."""
    try:
        return Path(path).read_text(encoding="utf-8"), "OK"
    except FileNotFoundError:
        return None, "ABSENT"
    except OSError:
        return None, "ERROR"


def collect_host(
    runner: Runner,
    *,
    read_text: Callable[[str], tuple[str | None, str]] = _read_text,
    kernel_release: str | None = None,
    timeout: float = 20.0,
) -> HostObservation:
    """O1 and O2.  A failed or timed-out query is UNKNOWN, never DISABLED (H-R2-3)."""
    # AppArmor: the module parameter file is the host-side signal.
    text, status = read_text("/sys/module/apparmor/parameters/enabled")
    if status == "OK" and text is not None:
        apparmor = "ENABLED" if text.strip() == "Y" else "DISABLED"
    elif status == "ABSENT":
        apparmor = "DISABLED"
    else:
        apparmor = "UNKNOWN"

    # SELinux: getenforce, else the selinuxfs enforce file.
    selinux = "UNKNOWN"
    ge = runner(["getenforce"], timeout)
    if ge.rc == 0 and ge.stdout.strip() in ("Enforcing", "Permissive", "Disabled"):
        selinux = ge.stdout.strip().upper()
    elif ge.not_found:
        t2, s2 = read_text("/sys/fs/selinux/enforce")
        if s2 == "OK" and t2 is not None and t2.strip() in ("0", "1"):
            selinux = "ENFORCING" if t2.strip() == "1" else "PERMISSIVE"
        elif s2 == "ABSENT":
            selinux = "DISABLED"

    info = runner(["docker", "info", "--format", "{{json .SecurityOptions}}"], timeout)
    options: tuple[str, ...] | None = None
    if info.rc == 0:
        try:
            parsed = json.loads(info.stdout)
            if isinstance(parsed, list) and all(isinstance(o, str) for o in parsed):
                options = tuple(parsed)
        except ValueError:
            options = None

    ver = runner(["docker", "version", "--format", "{{.Server.Version}}"], timeout)
    server_version = ver.stdout.strip() if ver.rc == 0 and ver.stdout.strip() else None
    return HostObservation(apparmor, selinux, options, server_version, kernel_release)


def compile_probe(workdir: Path, runner: Runner, *, timeout: float = 120.0) -> tuple[Path | None, str | None, str]:
    """Compile the probe once.  Returns (binary, sha256, diagnostic)."""
    src = workdir / "probe.c"
    out = workdir / "probe"
    src.write_text(PROBE_C, encoding="utf-8")
    cp = runner(["gcc", "-m32", "-static", "-o", str(out), str(src)], timeout)
    if cp.rc != 0 or not out.exists():
        return None, None, (cp.stderr or cp.stdout or "gcc failed").strip()[:500]
    return out, sha256_file(out), ""


def _inspect_summary(inspect_json: str) -> tuple[Mapping[str, Any], str | None]:
    """The parts of `docker inspect` the method records (O4), and the image id."""
    try:
        data = json.loads(inspect_json)
        item = data[0]
        state = item.get("State", {})
        host_cfg = item.get("HostConfig", {})
        summary = {
            "status": state.get("Status"),
            "exit_code": state.get("ExitCode"),
            "error": state.get("Error"),
            "oom_killed": state.get("OOMKilled"),
            "host_security_opt": host_cfg.get("SecurityOpt"),
            "app_armor_profile": item.get("AppArmorProfile"),
            "image_id": item.get("Image"),
        }
        return summary, item.get("Image")
    except (ValueError, IndexError, AttributeError, TypeError):
        return {}, None


def run_probe(
    runner: Runner,
    create_argv: Sequence[str],
    *,
    name: str,
    probe_sha256: str | None,
    timeout: float = 60.0,
) -> RunRecord:
    """`docker create`, `docker start`, `docker inspect`, `docker rm`, one container, id recorded."""
    start = time.monotonic()
    created = runner(create_argv, timeout)
    cid = created.stdout.strip() if created.rc == 0 and created.stdout.strip() else None

    def finish(rc: int | None, out: str, err: str, timed_out: bool, inspect: Mapping[str, Any],
               image_id: str | None) -> RunRecord:
        if cid:
            runner(["docker", "rm", "-f", cid], 30.0)
        return RunRecord(name, tuple(create_argv), cid, rc, out, err, time.monotonic() - start,
                         timed_out, probe_sha256, image_id, inspect)

    if cid is None:
        # The daemon refused to create the container: no verdict from this run.
        return finish(125 if not created.timed_out else None, created.stdout, created.stderr,
                      created.timed_out, {}, None)

    started = runner(["docker", "start", "-a", cid], timeout)
    insp = runner(["docker", "inspect", cid], 30.0)
    summary, image_id = _inspect_summary(insp.stdout) if insp.rc == 0 else ({}, None)
    if started.timed_out:
        return finish(None, started.stdout, started.stderr, True, summary, image_id)

    # Exit status: what the container exited with when inspect says it ran; 125 (a daemon error)
    # when it never ran; `docker start`'s own status only when inspect itself was unavailable.
    status, exit_code = summary.get("status"), summary.get("exit_code")
    if status == "exited" and isinstance(exit_code, int):
        rc: int | None = exit_code
    elif not summary:
        rc = started.rc if started.rc is not None else 125
    else:
        rc = 125
    return finish(rc, started.stdout, started.stderr, False, summary, image_id)


ArgvBuilder = Callable[[str, tuple[str, ...]], list[str]]


def collect(
    runner: Runner,
    *,
    argv_builder: ArgvBuilder,
    image_ref: str,
    workdir: Path,
    probe_path_in_container: str | None = None,
    invocation_id: str | None = None,
    read_text: Callable[[str], tuple[str | None, str]] = _read_text,
    kernel_release: str | None = None,
) -> tuple[Observations, str]:
    """Run S, C, B1 and B2 and return the observations plus the invocation id.

    ``argv_builder(container_name, command)`` must return the product's own ``docker create``
    argv for a container named ``container_name`` running ``command`` (the A9 test wires in
    ``docker_backend._build_create_args``).  One probe binary and one image serve every run.
    """
    inv = invocation_id or uuid.uuid4().hex
    host = collect_host(runner, read_text=read_text, kernel_release=kernel_release)
    probe_bin, probe_sha, compile_error = compile_probe(workdir, runner)
    img = runner(["docker", "inspect", "--format", "{{.Id}}", image_ref], 30.0)
    expected_image_id = img.stdout.strip() if img.rc == 0 and img.stdout.strip() else None
    container_probe = probe_path_in_container or (str(probe_bin) if probe_bin else "/probe/probe")

    runs: dict[str, RunRecord] = {}
    if probe_bin is None:
        return Observations(host, runs, None, expected_image_id, compile_error=compile_error or None), inv

    lsm = host.lsm_backend
    for name in RUN_NAMES:
        domain, kind = RUN_PROBE_ARGS[name]
        cname = f"ocbrain-a9-{name.lower()}-{inv[:8]}"
        argv = argv_builder(cname, (container_probe, str(domain), str(kind)))
        if name == "C":
            argv = control_argv(argv, lsm)
        # Re-hash right before the run: a binary changed after compilation must be seen.
        sha_now = sha256_file(probe_bin) if probe_bin.exists() else None
        runs[name] = run_probe(runner, argv, name=name, probe_sha256=sha_now)
    return Observations(host, runs, probe_sha, expected_image_id), inv


# =================================================================================================
# CLI
# =================================================================================================


def _summary_lines(record: Mapping[str, Any]) -> list[str]:
    return [
        f"A9 classification: {record.get('classification')}",
        f"reasons: {', '.join(record.get('reasons', [])) or '-'}",
        f"deny_rule: {record.get('deny_rule')}",
        f"lsm_backend: {record.get('lsm_backend')}  verified_scope: {record.get('verified_scope')}",
        f"engine_floor_corroboration (never an input): {record.get('engine_floor_corroboration')}",
    ]


def _emit(lines: Sequence[str], text_path: Path | None) -> None:
    """Print the lines; when asked, also keep them as a file (it goes into the evidence artifact)."""
    print("\n".join(lines))
    if text_path is not None:
        text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_main(args: argparse.Namespace) -> int:
    text_path: Path | None = getattr(args, "text", None)
    record, problems = load_record(args.record)
    if record is not None:
        problems += validate_record(record, max_age_s=args.max_age_s)
    if problems:
        _emit(["A9 RECORD INVALID (red):"] + [f"  - {p}" for p in problems], text_path)
        return 2
    assert record is not None
    lines = _summary_lines(record)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("### A9 deny-rule verification\n\n" + "\n".join(f"- {ln}" for ln in lines) + "\n")
        except OSError:
            pass  # the printed output is the record of the classification
    if record["classification"] == MITIGATION_VERIFIED:
        _emit(lines + ["A9: MITIGATION_VERIFIED (a measurement of this host at this time, nothing more)"], text_path)
        return 0
    _emit(lines + [f"A9: {record['classification']} is red by design (H-D1, H-D12): "
                   "the deny rule was not verified on this host"], text_path)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ck = sub.add_parser("check", help="validate a record and print its classification")
    ck.add_argument("--record", required=True, type=Path)
    ck.add_argument("--max-age-s", type=float, default=None)
    ck.add_argument("--text", type=Path, default=None, help="also write the printed result to this file")
    ck.set_defaults(func=check_main)
    a = ap.parse_args(argv)
    return int(a.func(a))


if __name__ == "__main__":
    sys.exit(main())
