"""Tests for scripts/ci_docker_preflight.py.

The preflight makes the Docker prerequisites of the sandbox tests explicit in CI:
a reachable daemon, exactly the requested image provisioned, the image resolved
the way DockerBackend resolves it, and a container actually started from it.  It
must fail closed and name the failing stage.

These tests need no Docker daemon.  A fake ``docker`` executable (a small Python
script placed first on PATH) answers the sub-commands the preflight uses, records
every call, and is configured per scenario.  What is pinned:

* the success paths (image pulled; image already present, no pull at all);
* every failure stage, with its exit code and the stage named in the report;
* no fallback: only the requested image reference is ever passed to docker;
* the identity stage asks the daemon the same question DockerBackend asks;
* required executables are looked up on the image's own PATH (the lookup snippet
  that runs inside the image is also executed for real, against a controlled PATH);
* the report is written on failure as well as on success;
* the CLI contract (missing or empty --image is a usage error).
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci_docker_preflight.py"
IMAGE = "python:3.12-alpine"  # deliberately not the product default (alpine:3): a fallback to the default must be visible
DIGEST = "python@sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
PRODUCT_DIGEST_FORMAT = "{{index .RepoDigests 0}}"

# A fake docker CLI.  Behaviour comes from the JSON file named by FAKE_DOCKER_CFG; every
# call is appended to FAKE_DOCKER_LOG; whether the image is present, and how many pulls
# happened, live in a state file beside the config.
_FAKE_DOCKER = f'''#!{sys.executable}
import json, os, sys

argv = sys.argv[1:]
cfg = json.load(open(os.environ["FAKE_DOCKER_CFG"]))
state_path = os.environ["FAKE_DOCKER_CFG"] + ".state"
try:
    state = json.load(open(state_path))
except FileNotFoundError:
    state = {{"present": cfg["present"], "pulls": 0}}
with open(os.environ["FAKE_DOCKER_LOG"], "a") as fh:
    fh.write(json.dumps(argv) + "\\n")


def save():
    json.dump(state, open(state_path, "w"))


def out(text="", rc=0, err=""):
    save()
    sys.stdout.write(text)
    sys.stderr.write(err)
    sys.exit(rc)


cmd = argv[0] if argv else ""
if cmd == "info":
    out(cfg["info_out"], cfg["info_rc"], "Cannot connect to the Docker daemon" if cfg["info_rc"] else "")
if cmd == "context":
    out("default\\n")
if cmd == "pull":
    state["pulls"] += 1
    rcs = cfg["pull_rcs"]
    rc = rcs[min(state["pulls"] - 1, len(rcs) - 1)]
    if rc == 0 and cfg.get("pull_populates", True):
        state["present"] = True
    out("pulled\\n" if rc == 0 else "", rc, "" if rc == 0 else "Error response from daemon: pull access denied")
if cmd == "image" and argv[1] == "inspect":
    if state["present"]:
        out(cfg["id"] + "\\n")
    out("", 1, "Error response from daemon: No such image: " + argv[-1])
if cmd == "inspect":
    fmt = argv[argv.index("--format") + 1]
    if not state["present"]:
        out("", 1, "Error: No such object: " + argv[-1])
    if fmt == "{{{{.Id}}}}":
        out(cfg["id"] + "\\n", cfg["id_rc"], "id lookup failed" if cfg["id_rc"] else "")
    out(cfg["digest"] + "\\n", cfg["digest_rc"], "digest lookup failed" if cfg["digest_rc"] else "")
if cmd == "run":
    if "--entrypoint" in argv:
        out(cfg["exec_out"] if cfg["exec_rc"] else "", cfg["exec_rc"])
    out("", cfg["smoke_rc"], "container could not start" if cfg["smoke_rc"] else "")
out("", 99, "fake docker: unexpected sub-command " + " ".join(argv))
'''


def _cfg(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "present": False,
        "info_rc": 0,
        "info_out": "11111111-2222-3333-4444-555555555555|29.8.2|linux/x86_64\n",
        "pull_rcs": [0],
        "id": IMAGE_ID,
        "id_rc": 0,
        "digest": DIGEST,
        "digest_rc": 0,
        "smoke_rc": 0,
        "exec_rc": 0,
        "exec_out": "missing: python3\n",
    }
    for key, value in overrides.items():
        if key == "version_rc":  # historical alias used by one test: `docker info` failing
            key = "info_rc"
        base[key] = value
    return base


class Env:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.bin = tmp / "bin"
        self.bin.mkdir()
        fake = self.bin / "docker"
        fake.write_text(_FAKE_DOCKER, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.cfg_path = tmp / "cfg.json"
        self.log_path = tmp / "calls.jsonl"
        self.report_path = tmp / "report.json"

    def run(self, cfg: dict[str, object], *extra: str, image: str | None = IMAGE, path_has_docker: bool = True):
        self.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        Path(str(self.cfg_path) + ".state").unlink(missing_ok=True)
        self.log_path.write_text("", encoding="utf-8")
        env = dict(os.environ)
        env["PATH"] = (str(self.bin) + os.pathsep + env.get("PATH", "")) if path_has_docker else str(self.tmp / "empty")
        env["FAKE_DOCKER_CFG"] = str(self.cfg_path)
        env["FAKE_DOCKER_LOG"] = str(self.log_path)
        argv = [sys.executable, str(SCRIPT)]
        if image is not None:
            argv += ["--image", image]
        argv += ["--report", str(self.report_path), "--retry-delay", "0", *extra]
        return subprocess.run(argv, capture_output=True, text=True, env=env, timeout=60)

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line]

    def report(self) -> dict:
        return json.loads(self.report_path.read_text(encoding="utf-8"))


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


# ---------------------------------------------------------------- success paths


def test_absent_image_is_pulled_resolved_and_smoke_tested(env: Env) -> None:
    proc = env.run(_cfg())
    assert proc.returncode == 0, proc.stderr
    assert "PASS" in proc.stdout
    rep = env.report()
    assert rep["schema"] == "ocbrain.ci.docker-preflight/1"
    assert rep["result"] == "passed" and rep["failed_stage"] is None
    assert rep["image_ref"] == IMAGE
    assert rep["provision"]["status"] == "pulled" and [a["rc"] for a in rep["provision"]["attempts"]] == [0]
    assert rep["image"] == {"ref": IMAGE, "id": IMAGE_ID, "resolved_digest": DIGEST}
    assert rep["smoke"]["rc"] == 0
    assert rep["daemon"]["version"] == "29.8.2" and rep["daemon"]["platform"] == "linux/x86_64"
    assert ["pull", IMAGE] in env.calls()


def test_image_already_present_is_not_pulled_again(env: Env) -> None:
    proc = env.run(_cfg(present=True))
    assert proc.returncode == 0, proc.stderr
    assert not [c for c in env.calls() if c[0] == "pull"]
    rep = env.report()
    assert rep["provision"] == {"status": "already-present", "attempts": []}
    assert "already-present (0 pull attempt(s))" in proc.stdout


def test_a_transient_pull_failure_is_retried_and_every_attempt_is_recorded(env: Env) -> None:
    proc = env.run(_cfg(pull_rcs=[1, 1, 0]), "--pull-attempts", "3")
    assert proc.returncode == 0, proc.stderr
    rep = env.report()
    assert [a["rc"] for a in rep["provision"]["attempts"]] == [1, 1, 0]
    assert len([c for c in env.calls() if c[0] == "pull"]) == 3


# ---------------------------------------------------------------- failure stages


def test_unreachable_daemon_fails_at_the_daemon_stage_and_provisions_nothing(env: Env) -> None:
    proc = env.run(_cfg(info_rc=1))
    assert proc.returncode == 1
    assert "FAIL [daemon]" in proc.stderr
    rep = env.report()
    assert rep["failed_stage"] == "daemon" and rep["result"] == "failed"
    assert not [c for c in env.calls() if c[0] in ("pull", "run", "inspect")]


def test_a_daemon_that_cannot_describe_itself_fails_at_the_daemon_stage(env: Env) -> None:
    proc = env.run(_cfg(info_out="garbage\n"))
    assert proc.returncode == 1
    assert env.report()["failed_stage"] == "daemon"


def test_missing_docker_executable_fails_at_the_daemon_stage(env: Env) -> None:
    proc = env.run(_cfg(), path_has_docker=False)
    assert proc.returncode == 1
    assert "FAIL [daemon]" in proc.stderr
    assert env.report()["failed_stage"] == "daemon"


def test_pull_that_keeps_failing_fails_at_the_provision_stage_after_bounded_attempts(env: Env) -> None:
    proc = env.run(_cfg(pull_rcs=[1]), "--pull-attempts", "2")
    assert proc.returncode == 1
    assert "FAIL [provision]" in proc.stderr
    rep = env.report()
    assert rep["failed_stage"] == "provision"
    assert [a["rc"] for a in rep["provision"]["attempts"]] == [1, 1]
    assert len([c for c in env.calls() if c[0] == "pull"]) == 2, "attempts must be bounded"
    assert not [c for c in env.calls() if c[0] == "run"], "nothing may run when provisioning failed"


def test_a_pull_that_reports_success_but_leaves_no_image_fails_at_the_provision_stage(env: Env) -> None:
    proc = env.run(_cfg(pull_populates=False))
    assert proc.returncode == 1
    assert "FAIL [provision]" in proc.stderr
    assert env.report()["failed_stage"] == "provision"


@pytest.mark.parametrize("digest", ["", "<no value>"])
def test_an_image_without_a_usable_repo_digest_fails_at_the_identity_stage(env: Env, digest: str) -> None:
    proc = env.run(_cfg(present=True, digest=digest))
    assert proc.returncode == 1
    assert "FAIL [identity]" in proc.stderr and "RepoDigests" in proc.stderr
    assert env.report()["failed_stage"] == "identity"
    assert not [c for c in env.calls() if c[0] == "run"]


def test_a_digest_lookup_that_errors_fails_at_the_identity_stage(env: Env) -> None:
    proc = env.run(_cfg(present=True, digest_rc=1))
    assert proc.returncode == 1
    assert env.report()["failed_stage"] == "identity"


def test_an_unreadable_image_id_fails_at_the_identity_stage(env: Env) -> None:
    proc = env.run(_cfg(present=True, id="not-a-sha"))
    assert proc.returncode == 1
    assert env.report()["failed_stage"] == "identity"


def test_an_image_the_daemon_cannot_run_fails_at_the_smoke_stage(env: Env) -> None:
    proc = env.run(_cfg(present=True, smoke_rc=125))
    assert proc.returncode == 1
    assert "FAIL [smoke]" in proc.stderr
    rep = env.report()
    assert rep["failed_stage"] == "smoke" and rep["smoke"]["rc"] == 125
    assert rep["result"] == "failed"


# ---------------------------------------------------------------- required executables


def test_required_executables_are_looked_up_on_the_images_own_path(env: Env) -> None:
    proc = env.run(_cfg(), "--require-executable", "python3", "--require-executable", "sleep")
    assert proc.returncode == 0, proc.stderr
    assert "python3, sleep" in proc.stdout
    rep = env.report()
    assert rep["smoke"]["required_executables"] == ["python3", "sleep"] and rep["smoke"]["executables_rc"] == 0
    checks = [c for c in env.calls() if c[0] == "run" and "--entrypoint" in c]
    assert len(checks) == 1
    call = checks[0]
    assert call[call.index("--entrypoint") + 1] == "sh" and call[-3:] == ["sh", "python3", "sleep"]
    assert "--pull" in call and "--network" in call and IMAGE in call


def test_an_image_missing_a_required_executable_fails_at_the_smoke_stage_naming_it(env: Env) -> None:
    proc = env.run(_cfg(exec_rc=1), "--require-executable", "python3")
    assert proc.returncode == 1
    assert "FAIL [smoke]" in proc.stderr and "lacks required executables" in proc.stderr and "python3" in proc.stderr
    assert env.report()["failed_stage"] == "smoke"


@pytest.mark.parametrize("bad", ["/usr/bin/python3", "--help", "", "  ", "-x", "a b"])
def test_required_executables_must_be_bare_names(env: Env, bad: str) -> None:
    proc = env.run(_cfg(), "--require-executable", bad)
    assert proc.returncode == 2


# ---------------------------------------------------------------- invariants


def test_only_the_requested_image_is_ever_passed_to_docker(env: Env) -> None:
    """No fallback image: every image-bearing call names exactly the requested reference."""
    env.run(_cfg(pull_rcs=[1, 0]), "--pull-attempts", "2", "--require-executable", "sh")
    for call in env.calls():
        if call[0] in ("pull",):
            assert call == ["pull", IMAGE]
        elif call[0] in ("inspect", "image"):
            assert call[-1] == IMAGE
        elif call[0] == "run":
            assert call.count(IMAGE) == 1
            # nothing else in a `run` call may look like an image reference
            assert not any(a in ("alpine", "busybox", "ubuntu", "debian", "scratch") or a.startswith(("alpine:", "busybox:", "ubuntu:", "debian:")) for a in call if a != IMAGE)


def test_the_identity_stage_asks_the_daemon_what_dockerbackend_asks(env: Env) -> None:
    env.run(_cfg())
    assert ["inspect", "--format", PRODUCT_DIGEST_FORMAT, IMAGE] in env.calls()
    product = (ROOT / "core" / "sandbox" / "backends" / "docker_backend.py").read_text(encoding="utf-8")
    # If DockerBackend ever changes its resolution command, this preflight must follow it.
    assert f'"{PRODUCT_DIGEST_FORMAT}"' in product


def test_the_smoke_run_cannot_pull_and_has_no_network(env: Env) -> None:
    env.run(_cfg())
    runs = [c for c in env.calls() if c[0] == "run"]
    assert runs == [["run", "--rm", "--pull", "never", "--network", "none", IMAGE, "true"]]


def test_the_report_is_written_on_failure_too(env: Env) -> None:
    env.run(_cfg(version_rc=1))
    rep = env.report()
    assert rep["schema"] == "ocbrain.ci.docker-preflight/1"
    assert rep["result"] == "failed" and rep["failed_stage"] == "daemon" and rep["message"]
    assert rep["started_at"] and rep["finished_at"]


# ---------------------------------------------------------------- CLI contract


def test_image_is_required(env: Env) -> None:
    proc = env.run(_cfg(), image=None)
    assert proc.returncode == 2
    assert "--image" in proc.stderr


@pytest.mark.parametrize("bad", [["--image", ""], ["--image", "  "]])
def test_an_empty_image_is_a_usage_error_not_a_silent_default(env: Env, bad: list[str]) -> None:
    env.cfg_path.write_text(json.dumps(_cfg()), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), *bad], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 2


def test_zero_pull_attempts_is_a_usage_error(env: Env) -> None:
    proc = env.run(_cfg(), "--pull-attempts", "0")
    assert proc.returncode == 2



# ---------------------------------------------------------------- the in-container lookup, run for real
#
# The fake docker above cannot execute the shell snippet that runs INSIDE the image, so the
# snippet is exercised here with a real POSIX sh against a controlled PATH.  It decides whether
# an image "has" an executable, so each way it could be fooled is pinned.


def _load_preflight():
    import importlib.util

    spec = importlib.util.spec_from_file_location("ci_docker_preflight_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lookup(path_dirs: list[Path], *names: str) -> subprocess.CompletedProcess[str]:
    import shutil

    sh = shutil.which("sh")
    assert sh, "a POSIX sh is required"
    snippet = _load_preflight()._FIND_EXECUTABLES
    env = {"PATH": os.pathsep.join(str(d) for d in path_dirs)}  # nothing else: builtins must not count
    return subprocess.run([sh, "-c", snippet, "sh", *names], capture_output=True, text=True, env=env, timeout=30)


def _make_exec(directory: Path, name: str, *, executable: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / name
    p.write_text("#!/bin/sh\n", encoding="utf-8")
    p.chmod(0o755 if executable else 0o644)
    return p


def test_lookup_succeeds_silently_when_every_name_is_an_executable_on_path(tmp_path: Path) -> None:
    _make_exec(tmp_path / "a", "python3")
    _make_exec(tmp_path / "b", "sleep")  # found in the SECOND path entry
    r = _lookup([tmp_path / "a", tmp_path / "b"], "python3", "sleep")
    assert r.returncode == 0 and r.stdout == ""


def test_lookup_names_exactly_the_missing_ones_and_fails(tmp_path: Path) -> None:
    _make_exec(tmp_path / "a", "sleep")
    r = _lookup([tmp_path / "a"], "python3", "sleep", "yes")
    assert r.returncode == 1
    assert r.stdout.splitlines() == ["missing: python3", "missing: yes"]


def test_lookup_does_not_count_a_non_executable_file(tmp_path: Path) -> None:
    _make_exec(tmp_path / "a", "python3", executable=False)
    r = _lookup([tmp_path / "a"], "python3")
    assert r.returncode == 1 and "missing: python3" in r.stdout


def test_lookup_does_not_count_a_directory_with_the_name(tmp_path: Path) -> None:
    (tmp_path / "a" / "python3").mkdir(parents=True)  # directories carry the x bit
    r = _lookup([tmp_path / "a"], "python3")
    assert r.returncode == 1 and "missing: python3" in r.stdout


def test_lookup_does_not_count_shell_builtins(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    r = _lookup([tmp_path / "empty"], "cd")  # `cd` is a builtin; with an empty PATH there is no binary
    assert r.returncode == 1 and "missing: cd" in r.stdout


def test_lookup_with_no_names_succeeds(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    assert _lookup([tmp_path / "empty"]).returncode == 0
