#!/usr/bin/env python3
"""Fail-closed Docker prerequisite check for the Docker-backed sandbox tests (CI).

WHY THIS EXISTS
---------------
``DockerBackend.create()`` resolves its image with ``docker inspect --format
{{index .RepoDigests 0}} <ref>`` (``core/sandbox/backends/docker_backend.py``,
``_resolve_image_digest``).  The reference comes from ``OCBRAIN_SANDBOX_DOCKER_IMAGE``
and defaults to ``alpine:3``.  The CI ``tests`` job never provisioned that image in
the runner's daemon, so on the first hosted run every test that creates a Docker
sandbox failed with ``no such object: alpine:3`` (75 failures, none of them on the
known-failure list).  Nothing in the workflow said the image was a prerequisite, and
nothing recorded which image (digest) the tests ran against.

There is a second, latent layer: about fifteen tests launch ``python3`` *inside* the
container (see the "image must contain python3" note in
``tests/core/sandbox/test_network_isolation_contract.py``).  A bare ``alpine:3`` has no
python3, so merely pulling it would turn the 75 failures into ~17 different ones.

WHAT IT DOES
------------
Four stages, in order; the first failure stops the run, is named in the report and the
exit code, and nothing is substituted:

``daemon``     a docker CLI is on PATH and the daemon answers ``docker info``.
``provision``  the exact requested reference is present in THIS daemon: inspected
               first, otherwise pulled with a bounded number of attempts.  There is no
               fallback image, no mock and no skip.
``identity``   the image id is readable and the product's own digest question
               (``docker inspect --format {{index .RepoDigests 0}}``) gets a usable
               answer, exactly the acceptance rule ``_resolve_image_digest`` applies.
``smoke``      a container is actually started from the image (``--pull never``,
               ``--network none``), and, for every ``--require-executable NAME``, NAME
               is found as an executable along the image's own PATH.

The JSON report (schema ``ocbrain.ci.docker-preflight/1``) is written on failure too, so
the evidence of what was provisioned survives a red run.

EXIT CODES
----------
0 passed; 1 a stage failed; 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "ocbrain.ci.docker-preflight/1"

# Exactly the question DockerBackend._resolve_image_digest asks the daemon.
_PRODUCT_DIGEST_FORMAT = "{{index .RepoDigests 0}}"
_IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BARE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_TAIL = 400


class PreflightFailure(Exception):
    """A named preflight stage failed."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"[{stage}] {message}")
        self.stage = stage
        self.message = message


def _tail(text: str, limit: int = _TAIL) -> str:
    text = (text or "").strip().replace("\r", "")
    return text if len(text) <= limit else "..." + text[-limit:]


def _docker(args: Sequence[str], timeout: float) -> tuple[int, str, str]:
    """Run ``docker <args>``; never raises.  rc 127: no docker executable; 124: timed out."""
    try:
        proc = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, "", f"docker executable not found: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", f"`docker {' '.join(args[:3])} ...` timed out after {timeout:.0f}s"
    return proc.returncode, proc.stdout, proc.stderr


# ----------------------------------------------------------------------------- stages


def _check_daemon(report: dict[str, Any]) -> None:
    rc, out, err = _docker(
        ["info", "--format", "{{.ID}}|{{.ServerVersion}}|{{.OSType}}/{{.Architecture}}"], 60
    )
    if rc != 0:
        raise PreflightFailure("daemon", f"the docker daemon is not reachable (rc={rc}): {_tail(err or out)}")
    parts = out.strip().split("|")
    if len(parts) != 3 or not parts[1]:
        raise PreflightFailure("daemon", f"`docker info` returned an unusable answer: {_tail(out)!r}")
    ctx_rc, ctx_out, _ = _docker(["context", "show"], 30)
    report["daemon"] = {
        "id": parts[0],
        "version": parts[1],
        "platform": parts[2],
        "context": ctx_out.strip() if ctx_rc == 0 else None,
        "docker_host": os.environ.get("DOCKER_HOST"),
    }
    d = report["daemon"]
    print(
        f"docker-preflight: daemon id={d['id']} version={d['version']} platform={d['platform']} "
        f"context={d['context']} DOCKER_HOST={d['docker_host']}"
    )


def _image_present(image: str) -> tuple[bool, str]:
    rc, out, err = _docker(["image", "inspect", "--format", "{{.Id}}", image], 60)
    return rc == 0, _tail(err or out)


def _provision(image: str, attempts: int, delay: float, report: dict[str, Any]) -> None:
    present, _ = _image_present(image)
    prov: dict[str, Any] = {"status": "already-present", "attempts": []}
    report["provision"] = prov
    if not present:
        prov["status"] = "pulled"
        last = ""
        for n in range(1, attempts + 1):
            rc, out, err = _docker(["pull", image], 900)
            last = _tail(err or out)
            prov["attempts"].append({"attempt": n, "rc": rc, "output_tail": last})
            if rc == 0:
                break
            if n < attempts:
                time.sleep(delay)
        else:
            prov["status"] = "failed"
            raise PreflightFailure(
                "provision",
                f"could not pull {image!r} after {attempts} attempt(s); last rc={prov['attempts'][-1]['rc']}: {last}",
            )
        present, why = _image_present(image)
        if not present:
            prov["status"] = "failed"
            raise PreflightFailure("provision", f"`docker pull {image}` succeeded but the image is not present: {why}")
    print(f"docker-preflight: image {image!r} {prov['status']} ({len(prov['attempts'])} pull attempt(s))")


def _check_identity(image: str, report: dict[str, Any]) -> None:
    rc, out, err = _docker(["inspect", "--format", "{{.Id}}", image], 60)
    image_id = out.strip()
    if rc != 0 or not _IMAGE_ID_RE.match(image_id):
        raise PreflightFailure(
            "identity", f"could not read the image id of {image!r} (rc={rc}, got {image_id!r}): {_tail(err)}"
        )
    rc, out, err = _docker(["inspect", "--format", _PRODUCT_DIGEST_FORMAT, image], 60)
    digest = out.strip()
    if rc != 0:
        raise PreflightFailure(
            "identity", f"DockerBackend's digest lookup fails for {image!r} (rc={rc}): {_tail(err)}"
        )
    if not digest or digest == "<no value>":
        raise PreflightFailure(
            "identity",
            f"{image!r} has no local RepoDigests, so DockerBackend._resolve_image_digest would refuse it "
            f"(got {digest!r})",
        )
    report["image"] = {"ref": image, "id": image_id, "resolved_digest": digest}
    print(f"docker-preflight: image id={image_id}")
    print(f"docker-preflight: resolved digest={digest}")


# POSIX-sh lookup of each name along the image's own PATH (what `docker create <ref> <name>`
# resolves against); `command -v` is avoided because it also reports shell builtins.
_FIND_EXECUTABLES = (
    'rc=0; for c in "$@"; do f=0; old=$IFS; IFS=:; '
    'for d in $PATH; do if [ -x "$d/$c" ] && [ ! -d "$d/$c" ]; then f=1; fi; done; IFS=$old; '
    'if [ "$f" = 0 ]; then echo "missing: $c"; rc=1; fi; done; exit $rc'
)


def _smoke(image: str, required: Sequence[str], report: dict[str, Any]) -> None:
    rc, out, err = _docker(["run", "--rm", "--pull", "never", "--network", "none", image, "true"], 180)
    smoke: dict[str, Any] = {
        "command": f"docker run --rm --pull never --network none {image} true",
        "rc": rc,
        "required_executables": list(required),
    }
    report["smoke"] = smoke
    if rc != 0:
        raise PreflightFailure(
            "smoke", f"the daemon holds {image!r} but could not run a container from it (rc={rc}): {_tail(err or out)}"
        )
    if required:
        rc, out, err = _docker(
            ["run", "--rm", "--pull", "never", "--network", "none", "--entrypoint", "sh", image,
             "-c", _FIND_EXECUTABLES, "sh", *required],
            180,
        )
        smoke["executables_rc"] = rc
        if rc != 0:
            raise PreflightFailure("smoke", f"{image!r} lacks required executables: {_tail(out or err)}")


def run_preflight(
    image: str, attempts: int, delay: float, required: Sequence[str] = ()
) -> tuple[dict[str, Any], PreflightFailure | None]:
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "image_ref": image,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result": "failed",
        "failed_stage": None,
        "message": None,
    }
    failure: PreflightFailure | None = None
    try:
        _check_daemon(report)
        _provision(image, attempts, delay, report)
        _check_identity(image, report)
        _smoke(image, required, report)
        report["result"] = "passed"
    except PreflightFailure as exc:
        failure = exc
        report["failed_stage"] = exc.stage
        report["message"] = exc.message
    report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return report, failure


# ----------------------------------------------------------------------------- CLI


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Fail-closed Docker preflight: daemon, image provisioning, identity, smoke run."
    )
    ap.add_argument("--image", required=True, help="exact image reference the tests use, e.g. python:3.12-alpine")
    ap.add_argument("--report", type=Path, help="write a JSON report here (also on failure)")
    ap.add_argument("--pull-attempts", type=int, default=3, help="bounded pull attempts (default 3)")
    ap.add_argument("--retry-delay", type=float, default=5.0, help="seconds between pull attempts (default 5)")
    ap.add_argument(
        "--require-executable", action="append", default=[], metavar="NAME",
        help="bare executable name that must exist on the image's PATH (repeatable)",
    )
    args = ap.parse_args(argv)
    if not args.image.strip():
        ap.error("--image must be a non-empty image reference (there is no default image)")
    if args.pull_attempts < 1:
        ap.error("--pull-attempts must be at least 1")
    if args.retry_delay < 0:
        ap.error("--retry-delay must not be negative")
    for name in args.require_executable:
        if not _BARE_NAME_RE.match(name):
            ap.error(f"--require-executable takes a bare executable name, got {name!r}")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    image = args.image.strip()
    report, failure = run_preflight(image, args.pull_attempts, args.retry_delay, args.require_executable)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failure is not None:
        print(f"docker-preflight: FAIL [{failure.stage}] {failure.message}", file=sys.stderr)
        return 1
    required = report["smoke"]["required_executables"]
    print(
        "docker-preflight: smoke run ok; required executables present: "
        f"{', '.join(required) if required else '(none requested)'}"
    )
    print("docker-preflight: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
