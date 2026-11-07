"""Configuration tests for .github/workflows/ci.yml (B03 CI remediation).

What these pin, and why:

* TRIGGERS.  The first hosted verification of PR #86 ran only because someone
  pushed the PR's tree to an ``integration/**`` branch: the PR itself targets
  ``sandbox-network-isolation/b01-base`` and the workflow listened for pull
  requests into ``main`` only.  The pull_request filter must name both ``main``
  and that base, exactly (no wildcard that would also fire for every other
  workstream branch), and the existing ``push`` filter must be preserved.
* NO BYPASS.  No job or step may be conditional on the event, the branch or the
  actor, and nothing may continue past a failure.  The only conditionals allowed
  are ``if: always()`` on artifact uploads.
* DOCKER PREFLIGHT.  The ``tests`` job must run the preflight before pytest, in the
  same job, against the same image variable pytest reads, and must require every
  executable the Docker-backed tests launch inside the container.
* MYPY.  A pinned, narrow mypy job over the two B03 files, default and --strict.
* PACKET OWNERSHIP.  The real ``run:`` block is executed under a pull_request-style
  environment (``GITHUB_HEAD_REF`` set) and a push-style one (``GITHUB_REF_NAME``
  only): a declared packet branch is recognised either way; B03's branch is not a
  declared packet branch, so the step skips explicitly rather than silently.

Nothing here touches the D10 known-failure list or scripts/ci_test_gate.py; the
gate's own tests are tests/test_ci_test_gate.py.
"""
from __future__ import annotations

import ast
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
MANIFEST = ROOT / "docs" / "architecture" / "h2_packet_ownership.json"
DOCKER_TESTS = ROOT / "tests" / "core" / "sandbox" / "test_docker_backend.py"

B03_PR_BASE = "sandbox-network-isolation/b01-base"
B03_PR_HEAD = "sandbox-network-isolation/b03-capacity-ipv6-guards"
B03_FILES = (
    "core/sandbox/backends/_sandbox_network.py",
    "tests/core/sandbox/test_sandbox_network_guards.py",
)
JOBS = ("drift-and-ownership", "tests", "typecheck-b03")


def _doc() -> dict[Any, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers() -> dict[str, Any]:
    doc = _doc()
    # PyYAML (YAML 1.1) parses the bare key `on` as the boolean True.
    return doc["on"] if "on" in doc else doc[True]


def _steps(job: str) -> list[dict[str, Any]]:
    return list(_doc()["jobs"][job]["steps"])


def _step(job: str, prefix: str) -> dict[str, Any]:
    found = [s for s in _steps(job) if s.get("name", "").startswith(prefix)]
    assert len(found) == 1, f"expected exactly one {prefix!r} step in {job}, found {len(found)}"
    return found[0]


# ------------------------------------------------------------------ triggers


def test_pull_request_trigger_covers_main_and_the_b03_target_and_nothing_broader() -> None:
    branches = _triggers()["pull_request"]["branches"]
    assert sorted(branches) == sorted(["main", B03_PR_BASE])
    assert not any("*" in b for b in branches), "a wildcard would trigger for unrelated workstream branches"


def test_push_trigger_is_preserved() -> None:
    assert sorted(_triggers()["push"]["branches"]) == sorted(["main", "h2/**", "integration/**"])


def test_the_workflow_listens_to_exactly_push_and_pull_request() -> None:
    assert sorted(_triggers()) == ["pull_request", "push"], "no workflow_dispatch or other manual path"


def test_the_workflow_keeps_read_only_permissions() -> None:
    assert _doc()["permissions"] == {"contents": "read"}


# ------------------------------------------------------------------ no bypass


def test_no_job_is_conditional_and_nothing_continues_past_a_failure() -> None:
    doc = _doc()
    assert sorted(doc["jobs"]) == sorted(JOBS)
    for name, job in doc["jobs"].items():
        assert "if" not in job, f"job {name} is conditional"
        assert "continue-on-error" not in job, f"job {name} continues on error"
        for step in job["steps"]:
            assert "continue-on-error" not in step, f"{name}/{step.get('name')} continues on error"


def test_the_only_step_conditionals_are_always_on_artifact_uploads() -> None:
    conditional: list[tuple[str, str, str]] = []
    for name in JOBS:
        for step in _steps(name):
            if "if" in step:
                conditional.append((name, step["name"], str(step["if"])))
    assert conditional, "the artifact uploads are expected to use if: always()"
    for job, step, cond in conditional:
        assert cond == "always()", f"{job}/{step}: unexpected condition {cond!r}"
        assert step.startswith("Upload "), f"{job}/{step}: only upload steps may be conditional"


def test_every_hosted_job_uploads_its_evidence_even_on_failure() -> None:
    wanted = {
        "drift-and-ownership": {"drift-report"},
        "tests": {"docker-preflight", "pytest-output"},
        "typecheck-b03": {"mypy-b03"},
    }
    for job, names in wanted.items():
        uploaded = {s["with"]["name"] for s in _steps(job) if str(s.get("uses", "")).startswith("actions/upload-artifact@")}
        assert names <= uploaded, f"{job}: missing artifact uploads {names - uploaded}"


# ------------------------------------------------------------------ docker preflight


def test_preflight_runs_before_pytest_in_the_same_job_and_reads_the_same_image_variable() -> None:
    names = [s.get("name", "") for s in _steps("tests")]
    pre = next(i for i, n in enumerate(names) if n.startswith("Docker preflight"))
    run = next(i for i, n in enumerate(names) if n.startswith("Run test suite"))
    assert pre < run
    job_env = _doc()["jobs"]["tests"]["env"]
    image = job_env["OCBRAIN_SANDBOX_DOCKER_IMAGE"]
    assert image and image != "alpine:3", "bare alpine:3 has no python3"
    pre_step = _steps("tests")[pre]
    assert '--image "$OCBRAIN_SANDBOX_DOCKER_IMAGE"' in pre_step["run"]
    for step in (pre_step, _steps("tests")[run]):
        assert "OCBRAIN_SANDBOX_DOCKER_IMAGE" not in step.get("env", {}), "the image must be set once, at job level"


def test_preflight_has_no_fallback_image_and_no_escape_hatch() -> None:
    run = _step("tests", "Docker preflight")["run"]
    assert "||" not in run and "continue-on-error" not in run
    assert "docker pull" not in run, "provisioning belongs to the tested script, not inline shell"
    assert "ci_docker_preflight.py" in run


def _preflight_required_executables() -> set[str]:
    tokens = _step("tests", "Docker preflight")["run"].replace("\\\n", " ").split()
    return {tokens[i + 1] for i, t in enumerate(tokens) if t == "--require-executable"}


def _commands_launched_in_containers() -> set[str]:
    """First token of every SandboxRequest(command=...) in the Docker backend tests."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(DOCKER_TESTS.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "SandboxRequest":
            for kw in node.keywords:
                if kw.arg == "command" and isinstance(kw.value, (ast.Tuple, ast.List)) and kw.value.elts:
                    first = kw.value.elts[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        found.add(first.value)
    return found


def test_preflight_requires_every_executable_the_docker_tests_launch() -> None:
    launched = _commands_launched_in_containers()
    assert {"python3", "sh", "sleep", "true", "echo"} <= launched, "the scan found too little: has the test file changed shape?"
    required = _preflight_required_executables()
    assert launched <= required, f"the image check does not cover {sorted(launched - required)}"
    # Tools used inside `sh -c` snippets (not visible as a first token): kept explicit.
    assert {"yes", "head", "grep"} <= required


# ------------------------------------------------------------------ mypy


def test_mypy_job_is_pinned_narrow_and_covers_both_b03_files_in_both_modes() -> None:
    install = _step("typecheck-b03", "Install pinned mypy")["run"]
    assert "mypy==2.4.0" in install
    run = _step("typecheck-b03", "mypy on the B03 files")["run"]
    for path in B03_FILES:
        assert path in run
    # The two actual invocations (not the echo banners that merely mention "--strict").
    invocations = [ln.strip() for ln in run.splitlines() if ln.strip().startswith("mypy ") and "--version" not in ln]
    assert len(invocations) == 2, invocations
    default_run, strict_run = invocations
    assert default_run.startswith("mypy --explicit-package-bases --follow-imports=silent $FILES")
    assert strict_run.startswith("mypy --strict --explicit-package-bases --follow-imports=silent $FILES")
    assert 'FILES="' + " ".join(B03_FILES) + '"' in run, "FILES must be exactly the two B03 files"
    assert "MYPYPATH=." in run
    # Both exit codes are kept and both must be zero; nothing is swallowed.
    assert "RC_DEFAULT=${PIPESTATUS[0]}" in run and "RC_STRICT=${PIPESTATUS[0]}" in run
    assert run.rstrip().endswith('[ "$RC_DEFAULT" = "0" ] && [ "$RC_STRICT" = "0" ]')
    assert "|| true" not in run
    # Narrow on purpose: no repository-wide typing gate.
    assert "mypy ." not in run and " core/ " not in run and "tests/ " not in run


# ------------------------------------------------------------------ packet ownership


@pytest.mark.skipif(sys.platform == "win32" or shutil.which("bash") is None, reason="executes the workflow's bash step")
class TestPacketOwnershipStep:
    def _run(self, tmp_path: Path, **env_vars: str) -> subprocess.CompletedProcess[str]:
        bindir = tmp_path / "bin"
        bindir.mkdir(exist_ok=True)
        shim = bindir / "python3"
        # `python3 -c ...` (the manifest lookup) runs for real; the ownership checker itself is stubbed.
        shim.write_text(f'#!/bin/bash\nif [ "$1" = "-c" ]; then exec "{sys.executable}" "$@"; fi\necho "SHIM python3 $*"\n')
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
        script = tmp_path / "step.sh"
        script.write_text(_step("drift-and-ownership", "Packet ownership check")["run"], encoding="utf-8")
        env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path), **env_vars}
        # `bash -e` is GitHub's default shell for run: steps.
        return subprocess.run(["bash", "-e", str(script)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)

    @staticmethod
    def _declared_packet() -> tuple[str, str]:
        packets = json.loads(MANIFEST.read_text(encoding="utf-8"))["packets"]
        pid, entry = next(iter(packets.items()))
        return pid, entry["branch"]

    def test_declared_packet_branch_is_recognised_under_a_pull_request_event(self, tmp_path: Path) -> None:
        pid, branch = self._declared_packet()
        # pull_request: GITHUB_HEAD_REF is the PR's head branch, GITHUB_REF_NAME is "<n>/merge".
        r = self._run(tmp_path, GITHUB_HEAD_REF=branch, GITHUB_REF_NAME="86/merge")
        assert r.returncode == 0, r.stderr
        assert f"-> packet {pid}" in r.stdout
        assert f"SHIM python3 scripts/check_packet_ownership.py --packet {pid}" in r.stdout

    def test_declared_packet_branch_is_recognised_under_a_push_event(self, tmp_path: Path) -> None:
        pid, branch = self._declared_packet()
        r = self._run(tmp_path, GITHUB_REF_NAME=branch)
        assert r.returncode == 0, r.stderr
        assert f"-> packet {pid}" in r.stdout

    @pytest.mark.parametrize("event_env", [
        {"GITHUB_HEAD_REF": B03_PR_HEAD, "GITHUB_REF_NAME": "86/merge"},  # pull_request
        {"GITHUB_REF_NAME": B03_PR_HEAD},                                   # push to the PR branch
        {"GITHUB_REF_NAME": "integration/b03-ci-remediation-20261106"},     # push to an integration branch
    ])
    def test_b03_branch_is_not_a_declared_packet_branch_and_the_step_skips_explicitly(self, tmp_path: Path, event_env: dict[str, str]) -> None:
        declared = {e["branch"] for e in json.loads(MANIFEST.read_text(encoding="utf-8"))["packets"].values()}
        assert B03_PR_HEAD not in declared, "if B03 gains a manifest entry this test must become a recognition test"
        r = self._run(tmp_path, **event_env)
        assert r.returncode == 0, r.stderr
        assert "is not one of this manifest's declared packet branches" in r.stdout
        assert "skipping cleanly" in r.stdout
        assert "SHIM python3" not in r.stdout, "the ownership checker must not run for a non-packet branch"
