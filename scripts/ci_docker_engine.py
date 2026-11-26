#!/usr/bin/env python3
"""Provision a pinned Docker Engine on the CI runner (the A9 prerequisite).

WHY THIS EXISTS
---------------
A9 (``tests/core/sandbox/test_docker_backend.py``) requires verified mitigation of the
32-bit ``socketcall`` ``AF_VSOCK`` bypass.  Under H-D13c route 1 the deny rule is owned by
Docker (Engine 29.8.0 or later, whose default AppArmor/SELinux policy refuses the 32-bit
``socketcall`` path to ``AF_VSOCK``); OCBrain owns the *verification* (``ci_a9_verifier``).

The GitHub-hosted runner ships Engine 29.4.2 (actions/runner-images, Ubuntu 26.04 readme).
Engine 29.4.2 blocks the ``socketcall`` multiplexer wholesale in its default seccomp
profile, so on the first two hosted runs the control run could not open the socket and
every benign run failed too: A9 classified INCONCLUSIVE (``control_not_open``,
``socketcall_blocked_wholesale``).  No verification is possible on that Engine, however
the tests are written.  Spec section 4A.9, E6: "the GitHub-hosted runner with a
provisioned Engine 29.8.0 or later".  This script is that provisioning.

WHAT IT DOES
------------
Stages, in order; the first failure stops the run, is named in the report and the exit
code, and nothing is substituted:

``before``      record the daemon and client versions that are there (informational).
``key``         download Docker's apt signing key and require that the key file contains
                EXACTLY ONE primary key whose fingerprint equals the pinned fingerprint.
                This happens before any apt configuration is touched.
``sources``     remove every apt source that already points at download.docker.com (the
                runner is a disposable VM; the removal is recorded), install the verified
                key and write ONE source line signed by it.
``repository``  refresh only that source and require that the exact pinned package
                versions of ``docker-ce`` and ``docker-ce-cli`` are offered.
``install``     install exactly those two versions (``--allow-downgrades``; no range, no
                "latest").
``daemon``      restart the daemon (from Engine 29.4.3 the default AppArmor profile is
                re-installed at daemon start) and wait, bounded, until it answers.
``verify``      the daemon and the client both report exactly the pinned version.

It never installs anything else, never touches ``core/``, never weakens a security option,
and never decides anything about A9.  The Engine version stays corroboration only for the
A9 classifier (spec 4A.2): the classification comes from the behavioral runs.

The JSON report (schema ``ocbrain.ci.docker-engine/1``) is written on failure too.

EXIT CODES
----------
0 provisioned (or already at the pinned version); 1 a stage failed; 2 usage error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

SCHEMA = "ocbrain.ci.docker-engine/1"

# H-D13c route 1: the Engine that owns the deny rule.  tests/test_ci_docker_engine.py pins this.
ENGINE_FLOOR: tuple[int, int, int] = (29, 8, 0)

KEY_URL = "https://download.docker.com/linux/ubuntu/gpg"
# Docker's official apt repository key (fingerprint published in Docker's own install
# documentation, historically as `apt-key fingerprint 0EBFCD88`).  Compared as 40 upper-case hex.
DOCKER_KEY_FINGERPRINT = "9DC858229FC7DD38854AE2D88D81803C0EBFCD88"
REPO_URL = "https://download.docker.com/linux/ubuntu"
KEY_DEST_NAME = "ocbrain-docker.asc"
LIST_DEST_NAME = "ocbrain-docker.list"
PACKAGES = ("docker-ce", "docker-ce-cli")
EPOCH = "5"  # Docker's apt packages carry epoch 5 (docs.docker.com/engine/install/ubuntu)

_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_REVISION_RE = re.compile(r"^[1-9][0-9]*$")
_TAIL = 400

Result = tuple[int, str, str]
Runner = Callable[[Sequence[str], float], Result]


class ProvisionFailure(Exception):
    """A named provisioning stage failed."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"[{stage}] {message}")
        self.stage = stage
        self.message = message


# ----------------------------------------------------------------------------- pure helpers


def parse_version(text: str) -> tuple[int, int, int]:
    """Strict ``X.Y.Z``.  Anything else (``29.8``, ``29.8.2-rc1``, ``v29.8.2``, ``29.8.x``) raises."""
    m = _VERSION_RE.match(text.strip())
    if m is None:
        raise ValueError(f"not an exact stable Engine version (X.Y.Z): {text!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def at_or_above_floor(version: tuple[int, int, int]) -> bool:
    return version >= ENGINE_FLOOR


def apt_version_string(version: str, revision: str, version_id: str, codename: str) -> str:
    """The apt version of docker-ce / docker-ce-cli, e.g. ``5:29.8.2-1~ubuntu.26.04~resolute``."""
    parse_version(version)
    if _REVISION_RE.match(revision) is None:
        raise ValueError(f"apt revision must be a positive integer: {revision!r}")
    if not re.match(r"^\d+\.\d+$", version_id) or not re.match(r"^[a-z]+$", codename):
        raise ValueError(f"unusable Ubuntu release: VERSION_ID={version_id!r} codename={codename!r}")
    return f"{EPOCH}:{version}-{revision}~ubuntu.{version_id}~{codename}"


def primary_fingerprints(gpg_colon_output: str) -> list[str]:
    """Fingerprints of the PRIMARY keys in ``gpg --show-keys --with-colons`` output.

    The ``fpr`` record that follows a ``pub`` record is the primary key's; those after ``sub``
    records are subkeys and are not counted.
    """
    found: list[str] = []
    expecting_primary = False
    for line in gpg_colon_output.splitlines():
        fields = line.split(":")
        kind = fields[0]
        if kind == "pub":
            expecting_primary = True
        elif kind == "sub":
            expecting_primary = False
        elif kind == "fpr" and expecting_primary:
            expecting_primary = False
            found.append(fields[9].strip().upper() if len(fields) > 9 else "")
    return found


def key_is_pinned(gpg_colon_output: str, expected: str = DOCKER_KEY_FINGERPRINT) -> bool:
    """True only when the file holds exactly one primary key and it is the pinned one."""
    found = primary_fingerprints(gpg_colon_output)
    return len(found) == 1 and found[0] == expected


def parse_madison(text: str) -> list[tuple[str, str]]:
    """``apt-cache madison`` lines -> (package, version) pairs."""
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0] and parts[1]:
            rows.append((parts[0], parts[1]))
    return rows


def parse_os_release(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def references_docker_repo(text: str) -> bool:
    return "download.docker.com" in text


# ----------------------------------------------------------------------------- process


def _tail(text: str, limit: int = _TAIL) -> str:
    text = (text or "").strip().replace("\r", "")
    return text if len(text) <= limit else "..." + text[-limit:]


def run_command(args: Sequence[str], timeout: float) -> Result:
    """Run a command; never raises.  rc 127: executable not found; 124: timed out."""
    try:
        proc = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, "", f"executable not found: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", f"`{' '.join(args[:3])} ...` timed out after {timeout:.0f}s"
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class Config:
    version: str
    revision: str = "1"
    apt_dir: Path = Path("/etc/apt")
    os_release: Path = Path("/etc/os-release")
    work_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()))
    sudo: tuple[str, ...] = ("sudo",)
    key_url: str = KEY_URL
    daemon_wait_attempts: int = 30
    daemon_wait_delay: float = 2.0
    sleep: Callable[[float], None] = time.sleep


# ----------------------------------------------------------------------------- stages


def _docker_version(run: Runner, which: str) -> str | None:
    rc, out, _ = run(["docker", "version", "--format", "{{." + which + ".Version}}"], 60)
    text = out.strip()
    return text if rc == 0 and text else None


def _stage_before(cfg: Config, run: Runner, report: dict[str, Any]) -> None:
    report["before"] = {
        "server_version": _docker_version(run, "Server"),
        "client_version": _docker_version(run, "Client"),
    }
    b = report["before"]
    print(f"docker-engine: before: server={b['server_version']} client={b['client_version']}")


def _os_release(cfg: Config) -> tuple[str, str]:
    try:
        text = cfg.os_release.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProvisionFailure("sources", f"cannot read {cfg.os_release}: {exc}") from exc
    data = parse_os_release(text)
    if data.get("ID") != "ubuntu":
        raise ProvisionFailure("sources", f"only Ubuntu runners are supported, ID={data.get('ID')!r}")
    version_id = data.get("VERSION_ID", "")
    codename = data.get("UBUNTU_CODENAME") or data.get("VERSION_CODENAME") or ""
    if not version_id or not codename:
        raise ProvisionFailure("sources", f"{cfg.os_release} lacks VERSION_ID or a codename")
    return version_id, codename


def _stage_key(cfg: Config, run: Runner, report: dict[str, Any]) -> Path:
    key_file = cfg.work_dir / "ocbrain-docker-key.asc"
    key_file.unlink(missing_ok=True)
    rc, out, err = run(
        ["curl", "-fsSL", "--retry", "3", "--retry-delay", "2", "--max-time", "60", "-o", str(key_file), cfg.key_url],
        120,
    )
    if rc != 0 or not key_file.exists():
        raise ProvisionFailure("key", f"could not download the signing key from {cfg.key_url} (rc={rc}): {_tail(err or out)}")
    rc, out, err = run(["gpg", "--batch", "--show-keys", "--with-colons", str(key_file)], 60)
    if rc != 0:
        raise ProvisionFailure("key", f"gpg could not read the downloaded key (rc={rc}): {_tail(err or out)}")
    found = primary_fingerprints(out)
    report["key"] = {"url": cfg.key_url, "primary_fingerprints": found, "expected": DOCKER_KEY_FINGERPRINT}
    if not key_is_pinned(out):
        raise ProvisionFailure(
            "key",
            f"the downloaded key is not the pinned Docker key: primary fingerprints {found!r}, "
            f"expected exactly [{DOCKER_KEY_FINGERPRINT!r}].  Nothing was installed.",
        )
    print(f"docker-engine: signing key verified: {DOCKER_KEY_FINGERPRINT}")
    return key_file


def _existing_docker_sources(cfg: Config) -> list[str]:
    paths = sorted(glob.glob(str(cfg.apt_dir / "sources.list.d" / "*")))
    hits: list[str] = []
    for p in paths:
        path = Path(p)
        if path.name in (LIST_DEST_NAME,) or not path.is_file():
            continue
        try:
            if references_docker_repo(path.read_text(encoding="utf-8", errors="replace")):
                hits.append(p)
        except OSError:
            continue
    return hits


def _stage_sources(cfg: Config, run: Runner, key_file: Path, version_id: str, codename: str, report: dict[str, Any]) -> Path:
    main_list = cfg.apt_dir / "sources.list"
    try:
        if main_list.is_file() and references_docker_repo(main_list.read_text(encoding="utf-8", errors="replace")):
            raise ProvisionFailure("sources", f"{main_list} itself references download.docker.com; refusing to edit it")
    except OSError as exc:
        raise ProvisionFailure("sources", f"cannot read {main_list}: {exc}") from exc

    removed = _existing_docker_sources(cfg)
    for p in removed:
        rc, out, err = run([*cfg.sudo, "rm", "-f", "--", p], 60)
        if rc != 0:
            raise ProvisionFailure("sources", f"could not remove the existing Docker source {p} (rc={rc}): {_tail(err or out)}")
    report["removed_sources"] = removed
    if removed:
        print(f"docker-engine: removed existing Docker apt sources: {', '.join(removed)}")

    key_dest = cfg.apt_dir / "keyrings" / KEY_DEST_NAME
    list_dest = cfg.apt_dir / "sources.list.d" / LIST_DEST_NAME
    list_tmp = cfg.work_dir / LIST_DEST_NAME
    list_tmp.write_text(
        f"deb [arch=amd64 signed-by={key_dest}] {REPO_URL} {codename} stable\n", encoding="utf-8"
    )
    for cmd in (
        [*cfg.sudo, "install", "-d", "-m", "0755", str(key_dest.parent)],
        [*cfg.sudo, "install", "-m", "0644", str(key_file), str(key_dest)],
        [*cfg.sudo, "install", "-m", "0644", str(list_tmp), str(list_dest)],
    ):
        rc, out, err = run(cmd, 60)
        if rc != 0:
            raise ProvisionFailure("sources", f"`{' '.join(cmd[:4])} ...` failed (rc={rc}): {_tail(err or out)}")
    report["source_list"] = str(list_dest)
    return list_dest


def _stage_repository(cfg: Config, run: Runner, list_dest: Path, apt_version: str, report: dict[str, Any]) -> None:
    rc, out, err = run(
        [
            *cfg.sudo, "apt-get", "update",
            "-o", f"Dir::Etc::sourcelist={list_dest}",
            "-o", "Dir::Etc::sourceparts=-",
            "-o", "APT::Get::List-Cleanup=0",
        ],
        300,
    )
    if rc != 0:
        raise ProvisionFailure("repository", f"apt-get update of the Docker source failed (rc={rc}): {_tail(err or out)}")
    rc, out, err = run(["apt-cache", "madison", *PACKAGES], 60)
    if rc != 0:
        raise ProvisionFailure("repository", f"apt-cache madison failed (rc={rc}): {_tail(err or out)}")
    rows = parse_madison(out)
    missing = [p for p in PACKAGES if (p, apt_version) not in rows]
    report["apt_version"] = apt_version
    if missing:
        offered = sorted({v for p, v in rows if p == "docker-ce"})
        raise ProvisionFailure(
            "repository",
            f"the pinned version {apt_version} is not offered for {', '.join(missing)}; "
            f"docker-ce versions offered: {', '.join(offered[-12:]) or '(none)'}",
        )
    print(f"docker-engine: repository offers {apt_version} for {', '.join(PACKAGES)}")


def _stage_install(cfg: Config, run: Runner, apt_version: str) -> None:
    cmd = [
        *cfg.sudo, "env", "DEBIAN_FRONTEND=noninteractive",
        "apt-get", "install", "-y", "--no-install-recommends", "--allow-downgrades",
        *(f"{p}={apt_version}" for p in PACKAGES),
    ]
    rc, out, err = run(cmd, 900)
    if rc != 0:
        raise ProvisionFailure("install", f"apt-get install failed (rc={rc}): {_tail(err or out)}")


def _stage_daemon(cfg: Config, run: Runner) -> None:
    rc, out, err = run([*cfg.sudo, "systemctl", "restart", "docker"], 180)
    if rc != 0:
        raise ProvisionFailure("daemon", f"could not restart the docker daemon (rc={rc}): {_tail(err or out)}")
    last = ""
    for attempt in range(cfg.daemon_wait_attempts):
        rc, out, err = run(["docker", "info", "--format", "{{.ServerVersion}}"], 30)
        if rc == 0 and out.strip():
            return
        last = _tail(err or out)
        if attempt + 1 < cfg.daemon_wait_attempts:
            cfg.sleep(cfg.daemon_wait_delay)
    raise ProvisionFailure(
        "daemon", f"the daemon did not answer `docker info` after {cfg.daemon_wait_attempts} attempts: {last}"
    )


def _stage_verify(cfg: Config, run: Runner, report: dict[str, Any]) -> None:
    server = _docker_version(run, "Server")
    client = _docker_version(run, "Client")
    rc, sec, _ = run(["docker", "info", "--format", "{{json .SecurityOptions}}"], 60)
    krc, kernel, _ = run(["uname", "-r"], 30)
    report["after"] = {
        "server_version": server,
        "client_version": client,
        "security_options": sec.strip() if rc == 0 else None,
        "kernel": kernel.strip() if krc == 0 else None,
    }
    for label, got in (("daemon", server), ("client", client)):
        if got != cfg.version:
            raise ProvisionFailure("verify", f"the {label} reports version {got!r}, expected exactly {cfg.version!r}")
    a = report["after"]
    print(
        f"docker-engine: after: server={a['server_version']} client={a['client_version']} "
        f"security_options={a['security_options']} kernel={a['kernel']}"
    )


def provision(cfg: Config, run: Runner = run_command) -> tuple[dict[str, Any], ProvisionFailure | None]:
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "target_version": cfg.version,
        "floor": ".".join(str(n) for n in ENGINE_FLOOR),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result": "failed",
        "failed_stage": None,
        "message": None,
        "installed": False,
    }
    failure: ProvisionFailure | None = None
    try:
        _stage_before(cfg, run, report)
        if report["before"]["server_version"] == cfg.version and report["before"]["client_version"] == cfg.version:
            print(f"docker-engine: already at the pinned version {cfg.version}; nothing to install")
        else:
            version_id, codename = _os_release(cfg)
            apt_version = apt_version_string(cfg.version, cfg.revision, version_id, codename)
            key_file = _stage_key(cfg, run, report)
            list_dest = _stage_sources(cfg, run, key_file, version_id, codename, report)
            _stage_repository(cfg, run, list_dest, apt_version, report)
            _stage_install(cfg, run, apt_version)
            report["installed"] = True
            _stage_daemon(cfg, run)
        _stage_verify(cfg, run, report)
        report["result"] = "passed"
    except ProvisionFailure as exc:
        failure = exc
        report["failed_stage"] = exc.stage
        report["message"] = exc.message
    report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return report, failure


# ----------------------------------------------------------------------------- CLI


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Provision the pinned Docker Engine that A9 needs (fail-closed; no range, no latest)."
    )
    ap.add_argument("--version", required=True, help="exact stable Engine version X.Y.Z, at or above 29.8.0")
    ap.add_argument("--apt-revision", default="1", help="the package revision after the version (default 1)")
    ap.add_argument("--report", type=Path, help="write a JSON report here (also on failure)")
    args = ap.parse_args(argv)
    try:
        version = parse_version(args.version)
    except ValueError as exc:
        ap.error(str(exc))
    if not at_or_above_floor(version):
        ap.error(
            f"--version {args.version} is below the Engine floor {'.'.join(str(n) for n in ENGINE_FLOOR)}; "
            "A9 cannot be verified on it (spec 4A.9, E6)"
        )
    if _REVISION_RE.match(args.apt_revision) is None:
        ap.error(f"--apt-revision must be a positive integer, got {args.apt_revision!r}")
    return args


def sudo_prefix(euid: int) -> tuple[str, ...]:
    """Privileged commands run through ``sudo`` unless the process is already root."""
    return () if euid == 0 else ("sudo",)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    # A private (0700) scratch directory: the downloaded key and the source line are staged here
    # before the verified copies are installed under /etc/apt.
    with tempfile.TemporaryDirectory(prefix="ocbrain-docker-engine-") as scratch:
        cfg = Config(
            version=args.version.strip(),
            revision=args.apt_revision,
            work_dir=Path(scratch),
            sudo=sudo_prefix(os.geteuid()),
        )
        report, failure = provision(cfg)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failure is not None:
        print(f"docker-engine: FAIL [{failure.stage}] {failure.message}", file=sys.stderr)
        return 1
    print("docker-engine: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
