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
* every container the preflight starts gets DockerBackend's PATH and no network, can
  never pull, and is started by tag AND by the resolved RepoDigest;
* required executables are looked up on that PATH (the lookup snippet that runs inside
  the image is also executed for real, against a controlled PATH);
* the capability probes (applet features) are exercised on request, and their snippet is
  executed for real as well;
* a docker call that times out fails closed;
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
IMAGE = "python:3.12-slim"  # deliberately not the product default (alpine:3): a fallback to the default must be visible
DIGEST = "python@sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
PRODUCT_DIGEST_FORMAT = "{{index .RepoDigests 0}}"
CONTAINER_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"  # what DockerBackend sets in every container

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
        script = argv[argv.index("-c") + 1]
        if "missing:" in script:  # the executable lookup
            out(cfg["exec_out"] if cfg["exec_rc"] else "", cfg["exec_rc"])
        out(cfg["probe_out"] if cfg["probe_rc"] else "", cfg["probe_rc"])  # the capability probes
    if cfg["digest"] in argv:  # a run by the resolved RepoDigest
        out("", cfg["digest_run_rc"], "digest run failed" if cfg["digest_run_rc"] else "")
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
        "digest_run_rc": 0,
        "probe_rc": 0,
        "probe_out": "probe failed: date +%s%N has no nanoseconds (got: 1731N)\n",
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


def test_required_executables_are_looked_up_on_the_container_path_with_exact_flags(env: Env) -> None:
    proc = env.run(_cfg(), "--require-executable", "python3", "--require-executable", "sleep")
    assert proc.returncode == 0, proc.stderr
    assert "python3, sleep" in proc.stdout
    rep = env.report()
    assert rep["smoke"]["required_executables"] == ["python3", "sleep"] and rep["smoke"]["executables_rc"] == 0
    checks = [c for c in env.calls() if c[0] == "run" and "--entrypoint" in c]
    assert len(checks) == 1
    # The WHOLE argv, not a few tokens: `--pull always` would let a second pull change the image whose
    # digest was recorded, `--network host` would hand the container the network.
    assert checks[0] == [
        "run", "--rm", "--pull", "never", "--network", "none", "-e", f"PATH={CONTAINER_PATH}",
        "--entrypoint", "sh", IMAGE, "-c", _load_preflight()._FIND_EXECUTABLES, "sh", "python3", "sleep",
    ]


def test_an_image_missing_a_required_executable_fails_at_the_smoke_stage_naming_it(env: Env) -> None:
    proc = env.run(_cfg(exec_rc=1), "--require-executable", "python3")
    assert proc.returncode == 1
    assert "FAIL [smoke]" in proc.stderr and "lacks required executables" in proc.stderr and "python3" in proc.stderr
    assert env.report()["failed_stage"] == "smoke"


@pytest.mark.parametrize("bad", ["/usr/bin/python3", "--help", "", "  ", "-x", "a b"])
def test_required_executables_must_be_bare_names(env: Env, bad: str) -> None:
    proc = env.run(_cfg(), "--require-executable", bad)
    assert proc.returncode == 2


@pytest.mark.parametrize("bad", ["-x", "--help", "/usr/bin/python3", "a b", "a;b", "$(id)"])
def test_the_equals_form_reaches_the_name_validation_not_just_argparse(env: Env, bad: str) -> None:
    """`--require-executable=-x` is NOT rejected by argparse's own option parsing, so only the
    bare-name regex stands between such a value and the shell snippet that receives it."""
    proc = env.run(_cfg(), f"--require-executable={bad}")
    assert proc.returncode == 2
    assert "bare executable name" in proc.stderr
    assert not env.calls(), "validation must happen before docker is touched"


@pytest.mark.parametrize("name", ["python3", "mkfifo", "x86_64-linux-gnu-gcc", "g++", "ld.so", "a_b"])
def test_ordinary_executable_names_are_accepted(env: Env, name: str) -> None:
    assert env.run(_cfg(), f"--require-executable={name}").returncode == 0


# ---------------------------------------------------------------- invariants


def test_only_the_requested_image_is_ever_passed_to_docker(env: Env) -> None:
    """No fallback image: every image-bearing call names the requested reference, or (for a run) the
    RepoDigest the daemon resolved for exactly that reference."""
    env.run(_cfg(pull_rcs=[1, 0]), "--pull-attempts", "2", "--require-executable", "sh", "--probe-capabilities")
    seen_runs = 0
    for call in env.calls():
        if call[0] in ("pull",):
            assert call == ["pull", IMAGE]
        elif call[0] in ("inspect", "image"):
            assert call[-1] == IMAGE
        elif call[0] == "run":
            seen_runs += 1
            assert call.count(IMAGE) + call.count(DIGEST) == 1, call
            # nothing else in a `run` call may look like an image reference
            assert not any(a in ("alpine", "busybox", "ubuntu", "debian", "scratch") or a.startswith(("alpine:", "busybox:", "ubuntu:", "debian:")) for a in call if a not in (IMAGE, DIGEST))
    assert seen_runs == 4, "tag run, digest run, executable lookup, capability probes"


def test_the_identity_stage_asks_the_daemon_what_dockerbackend_asks(env: Env) -> None:
    env.run(_cfg())
    assert ["inspect", "--format", PRODUCT_DIGEST_FORMAT, IMAGE] in env.calls()
    product = (ROOT / "core" / "sandbox" / "backends" / "docker_backend.py").read_text(encoding="utf-8")
    # If DockerBackend ever changes its resolution command, this preflight must follow it.
    assert f'"{PRODUCT_DIGEST_FORMAT}"' in product


def test_the_smoke_runs_cannot_pull_have_no_network_and_use_the_product_path(env: Env) -> None:
    env.run(_cfg())
    runs = [c for c in env.calls() if c[0] == "run"]
    flags = ["run", "--rm", "--pull", "never", "--network", "none", "-e", f"PATH={CONTAINER_PATH}"]
    assert runs == [[*flags, IMAGE, "true"], [*flags, DIGEST, "true"]]


def test_the_container_path_is_the_one_dockerbackend_gives_every_container() -> None:
    """The lookup must resolve names against what `docker create` will really use: DockerBackend
    always sets PATH explicitly (`_build_container_env`), overriding the image's own ENV PATH."""
    from core.sandbox.backends.docker_backend import _build_container_env

    assert _load_preflight()._CONTAINER_PATH == _build_container_env({})["PATH"]
    assert CONTAINER_PATH == _build_container_env({})["PATH"]


def test_the_digest_dockerbackend_will_run_must_itself_start_a_container(env: Env) -> None:
    proc = env.run(_cfg(present=True, digest_run_rc=125))
    assert proc.returncode == 1
    assert "FAIL [smoke]" in proc.stderr and "resolved digest reference" in proc.stderr and DIGEST in proc.stderr
    rep = env.report()
    assert rep["failed_stage"] == "smoke" and rep["smoke"]["rc"] == 0 and rep["smoke"]["digest_run_rc"] == 125
    assert rep["smoke"]["digest_ref"] == DIGEST


# ---------------------------------------------------------------- capability probes


def test_capability_probes_run_only_when_requested(env: Env) -> None:
    assert env.run(_cfg(present=True, probe_rc=1)).returncode == 0, "not requested, so not run"
    assert env.report()["smoke"]["capability_probes"] is False
    assert not [c for c in env.calls() if "--entrypoint" in c]


def test_capability_probes_that_pass_are_recorded(env: Env) -> None:
    proc = env.run(_cfg(present=True), "--probe-capabilities")
    assert proc.returncode == 0, proc.stderr
    assert "capability probes: passed" in proc.stdout
    rep = env.report()
    assert rep["smoke"]["capability_probes"] is True and rep["smoke"]["capabilities_rc"] == 0
    probes = [c for c in env.calls() if c[0] == "run" and "--entrypoint" in c]
    assert probes == [[
        "run", "--rm", "--pull", "never", "--network", "none", "-e", f"PATH={CONTAINER_PATH}",
        "--entrypoint", "sh", IMAGE, "-c", _load_preflight()._CAPABILITY_PROBES,
    ]]


def test_an_image_whose_applets_lack_a_feature_the_tests_use_fails_at_the_smoke_stage(env: Env) -> None:
    proc = env.run(_cfg(present=True, probe_rc=1), "--probe-capabilities")
    assert proc.returncode == 1
    assert "FAIL [smoke]" in proc.stderr and "applet feature" in proc.stderr and "date +%s%N" in proc.stderr
    rep = env.report()
    assert rep["failed_stage"] == "smoke" and rep["smoke"]["capabilities_rc"] == 1


# ---------------------------------------------------------------- timeouts fail closed


def _fake_docker_run_with(env: Env, timeout_on: str):
    """The preflight module with `subprocess.run` replaced: calls whose docker sub-command is
    `timeout_on` raise TimeoutExpired, every other call goes to the fake docker executable."""
    module = _load_preflight()
    real_run = subprocess.run

    def fake_run(argv, **kwargs):
        if argv[:2] == ["docker", timeout_on] or (timeout_on == "run" and argv[:2] == ["docker", "run"]):
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 1))
        return real_run(argv, **kwargs)

    module.subprocess = type("S", (), {**vars(subprocess), "run": staticmethod(fake_run)})  # type: ignore[assignment]
    return module


@pytest.mark.parametrize("hung, stage", [("info", "daemon"), ("pull", "provision"), ("run", "smoke")])
def test_a_docker_call_that_times_out_fails_the_stage_it_belongs_to(env: Env, monkeypatch: pytest.MonkeyPatch, hung: str, stage: str) -> None:
    env.cfg_path.write_text(json.dumps(_cfg(present=(hung != "pull"))), encoding="utf-8")
    Path(str(env.cfg_path) + ".state").unlink(missing_ok=True)
    env.log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("PATH", str(env.bin) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("FAKE_DOCKER_CFG", str(env.cfg_path))
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(env.log_path))
    module = _fake_docker_run_with(env, hung)
    report, failure = module.run_preflight(IMAGE, 1, 0.0, ())
    assert failure is not None and failure.stage == stage, (hung, report)
    assert report["result"] == "failed" and "timed out" in report["message"]


def test_docker_helper_maps_a_missing_binary_and_a_timeout_to_distinct_nonzero_codes(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_preflight()
    monkeypatch.setenv("PATH", str(env.tmp / "empty"))
    assert module._docker(["info"], 5)[0] == 127
    monkeypatch.setenv("PATH", str(env.bin) + os.pathsep + os.environ.get("PATH", ""))
    module = _fake_docker_run_with(env, "info")
    rc, _, err = module._docker(["info"], 5)
    assert rc == 124 and "timed out" in err


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


@pytest.mark.parametrize("bad", ["--image=-foo", "--image=--privileged"])
def test_an_image_that_looks_like_a_docker_option_is_a_usage_error(env: Env, bad: str) -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT), bad], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 2 and "not an option" in proc.stderr


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


# ---------------------------------------------------------------- the capability probes, run for real
#
# Same idea as the lookup above: the probe snippet runs inside the image, so it is executed here with a
# real POSIX sh and shim applets, one feature broken at a time.


def _probe(tmp_path: Path, *, date: str = "1731000000123456789", sleep_rc: int = 0, head_rc: int = 0) -> subprocess.CompletedProcess[str]:
    import shutil

    sh = shutil.which("sh")
    assert sh, "a POSIX sh is required"
    bindir = tmp_path / "shims"
    bindir.mkdir(exist_ok=True)
    for name, body in {
        "date": f"echo '{date}'",
        "sleep": f"exit {sleep_rc}",
        "head": f"exit {head_rc}",
    }.items():
        shim = bindir / name
        shim.write_text(f"#!{sh}\n{body}\n", encoding="utf-8")
        shim.chmod(0o755)
    snippet = _load_preflight()._CAPABILITY_PROBES
    return subprocess.run([sh, "-c", snippet], capture_output=True, text=True, env={"PATH": str(bindir)}, timeout=30)


def test_probes_pass_for_nanosecond_date_fractional_sleep_and_head_c(tmp_path: Path) -> None:
    r = _probe(tmp_path)
    assert r.returncode == 0 and r.stdout == ""


@pytest.mark.parametrize("date", ["1731000000N", "N", "", "1731000000", "17310000001234567", "abc123"])
def test_probes_reject_a_date_without_nanoseconds(tmp_path: Path, date: str) -> None:
    r = _probe(tmp_path, date=date)
    assert r.returncode == 1 and "probe failed: date +%s%N" in r.stdout


def test_probes_reject_a_sleep_that_refuses_fractions(tmp_path: Path) -> None:
    r = _probe(tmp_path, sleep_rc=1)
    assert r.returncode == 1 and r.stdout.splitlines() == ["probe failed: sleep rejects a fractional duration"]


def test_probes_reject_a_head_without_c(tmp_path: Path) -> None:
    r = _probe(tmp_path, head_rc=1)
    assert r.returncode == 1 and r.stdout.splitlines() == ["probe failed: head does not support -c"]


def test_probes_report_every_broken_feature_not_just_the_first(tmp_path: Path) -> None:
    r = _probe(tmp_path, date="1N", sleep_rc=1, head_rc=1)
    assert r.returncode == 1 and len(r.stdout.splitlines()) == 3


def test_probes_pass_against_this_hosts_real_applets() -> None:
    """Sanity check of the snippet's syntax and of its premise on a real userland (GNU here, busybox in CI)."""
    import shutil

    sh = shutil.which("sh")
    assert sh
    r = subprocess.run([sh, "-c", _load_preflight()._CAPABILITY_PROBES], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout
