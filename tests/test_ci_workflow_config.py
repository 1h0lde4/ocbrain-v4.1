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
  same job, against the same image variable pytest reads, as ONE command (nothing
  appended that could turn its exit code into success), and must require every
  executable the Docker-backed tests launch inside the container.
* NO VACUOUS DOCKER SUITE.  After the gate, a step fails the job if pytest reports a
  skip whose reason says the daemon or the image is missing (the preflight has just
  proved both); its real ``run:`` block is executed against sample pytest output.
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
import re
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


def test_pytest_report_flags_keep_the_failures_the_gate_parses_and_add_skip_reasons() -> None:
    """`-r` REPLACES pytest's default short-summary set.  The gate reads FAILED/ERROR node ids from
    that summary, so `-rs` alone makes a run with failures unparseable (the gate reports
    "N failed but 0 distinct FAILED node ID(s)").  Require f, E and s."""
    run = _step("tests", "Run test suite")["run"]
    flags = re.findall(r"(?<!\S)-r([A-Za-z]+)(?!\S)", run)
    assert flags, "no -r flag: skip reasons would not be attributable"
    assert set("fEs") <= set("".join(flags)), f"-r flags {flags!r} must include f, E and s"


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


def _single_command(run: str) -> list[str]:
    """The tokens of a `run:` block that must be exactly one command (continuation lines joined).

    Nothing may be chained to it (`;`, `&&`, `||`, `|`, `&`), no second line may follow it, and it
    may not be prefixed by shell options or assignments: `exit 0`, `; true`, `set +e` all turn a
    failing command into a passing step.
    """
    joined = run.replace("\\\n", " ").strip()
    assert "\n" not in joined, f"expected one command, got several lines: {joined!r}"
    assert not re.search(r"[;&|]", joined), f"expected one command, found a chaining operator: {joined!r}"
    return joined.split()


def test_the_preflight_and_the_gate_are_each_exactly_one_command() -> None:
    pre = _single_command(_step("tests", "Docker preflight")["run"])
    assert pre[:2] == ["python3", "scripts/ci_docker_preflight.py"]
    gate = _single_command(_step("tests", "Gate on pytest exit code")["run"])
    assert gate[:2] == ["python3", "scripts/ci_test_gate.py"]
    assert "docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt" in gate, "the gate must use the D10 list, unchanged"


def test_the_preflight_exercises_the_applet_capabilities_the_tests_rely_on() -> None:
    assert "--probe-capabilities" in _single_command(_step("tests", "Docker preflight")["run"])


def test_single_command_helper_rejects_every_way_to_neuter_a_step() -> None:
    ok = "python3 scripts/x.py \\\n  --a b"
    assert _single_command(ok) == ["python3", "scripts/x.py", "--a", "b"]
    for bad in (ok + "\nexit 0", ok + " ; true", ok + " && true", ok + " || true", ok + " | cat", "set +e\n" + ok):
        with pytest.raises(AssertionError):
            _single_command(bad)


def _preflight_required_executables() -> set[str]:
    return {t for i, t in enumerate(_single_command(_step("tests", "Docker preflight")["run"])[1:], 1)
            if _single_command(_step("tests", "Docker preflight")["run"])[i - 1] == "--require-executable"}


CONTRACT_TESTS = ROOT / "tests" / "core" / "sandbox" / "test_network_isolation_contract.py"
DOCKER_TEST_FILES = (DOCKER_TESTS, CONTRACT_TESTS)

# Every utility the Docker-backed tests run INSIDE the image (the container's own PATH), found by
# reading the tests: SandboxRequest(command=(...)) first tokens, `docker exec <id> X` / `docker run
# ... <image> X`, and the words of `sh -c` snippets (the heartbeat loop `date`/`mv`, the manifest
# test `mkdir`, the read-only-mount test `rm`/`cat`, the symlink test `ln`, the UTS test `hostname`,
# the namespace probes `readlink`, the pid-namespace test `ls`, the FIFO test `mkfifo`).  The
# preflight must require all of them: an image check that omitted one would go green and the test
# would then fail (or, for `mkfifo`, pass without exercising what it claims to) inside the container.
IN_CONTAINER_TOOLS = frozenset({
    "python3", "sh", "sleep", "true", "echo", "printenv", "yes", "head", "grep",
    "date", "mv", "rm", "cat", "ln", "mkdir", "mkfifo", "hostname", "readlink", "ls",
})
# Words from the same candidate list that appear in the tests but are NOT run inside the container:
# docker sub-commands (ps, cp, rm/ls in `docker rm`/`docker network ls`), shell builtins (kill,
# printf, test, exec, exit), parameters or data (timeout, env, id=, ip in a python probe), prose.
NOT_RUN_IN_CONTAINER = frozenset({
    "exec", "exit", "kill", "printf", "test", "false", "mount", "cp", "id", "ps", "timeout", "env",
    "find", "ip",
})
# Utilities whose appearance in a test string must be classified (ratchet): anything here that is in
# neither set above fails the test below until a human decides which side it belongs on.
_UTILITY_CANDIDATES = frozenset(
    "cat cp date echo env exec exit false find grep head hostname id ip kill ln ls mkdir mount mv "
    "printenv printf ps python python3 readlink rm sh sleep test timeout true yes wait cd mkfifo mknod "
    "awk base64 basename chmod chown curl cut dd df dirname gzip md5sum nc nohup nproc od perl "
    "pwd setsid sed sha256sum sort stat tail tar tee touch tr uname uniq unshare wc wget xargs".split()
)


def _string_constants(path: Path) -> list[str]:
    """Non-docstring string constants (f-string literal parts included) of a test file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)
    }
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


def _words_in_test_strings() -> set[str]:
    words: set[str] = set()
    for path in DOCKER_TEST_FILES:
        for text in _string_constants(path):
            words |= {w for w in re.findall(r"(?<![\w./-])([A-Za-z0-9_+-]+)(?![\w/.-])", text) if w in _UTILITY_CANDIDATES}
    return words


def _commands_launched_in_containers() -> set[str]:
    """First token of every SandboxRequest(command=...) and of every `docker exec/run` command."""
    found: set[str] = set()
    for path in DOCKER_TEST_FILES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "SandboxRequest":
                for kw in node.keywords:
                    if kw.arg == "command" and isinstance(kw.value, (ast.Tuple, ast.List)) and kw.value.elts:
                        first = kw.value.elts[0]
                        if isinstance(first, ast.Constant) and isinstance(first.value, str):
                            found.add(first.value)
            if isinstance(node, ast.List) and len(node.elts) >= 4:
                lits = [e.value if isinstance(e, ast.Constant) and isinstance(e.value, str) else None for e in node.elts]
                if lits[0] == "docker" and lits[1] == "exec" and lits[3] is not None:
                    found.add(lits[3])  # docker exec <container> <tool> ...
    return found


def test_preflight_requires_every_executable_the_docker_tests_launch() -> None:
    launched = _commands_launched_in_containers()
    assert {"python3", "sh", "sleep", "true", "echo", "cat", "hostname", "readlink"} <= launched, (
        "the scan found too little: has a test file changed shape?"
    )
    required = _preflight_required_executables()
    assert launched <= required, f"the image check does not cover {sorted(launched - required)}"
    assert IN_CONTAINER_TOOLS <= required, f"the image check does not cover {sorted(IN_CONTAINER_TOOLS - required)}"


def test_every_utility_word_in_the_docker_tests_is_classified_and_none_is_stale() -> None:
    seen = _words_in_test_strings()
    unclassified = seen - IN_CONTAINER_TOOLS - NOT_RUN_IN_CONTAINER
    assert not unclassified, (
        f"the Docker tests now mention {sorted(unclassified)}: decide whether each runs inside the image "
        "(add it to IN_CONTAINER_TOOLS and to the preflight's --require-executable list) or not "
        "(NOT_RUN_IN_CONTAINER), so the image check keeps covering what the tests launch"
    )
    stale = (IN_CONTAINER_TOOLS | NOT_RUN_IN_CONTAINER) - seen - {"python3"}
    assert not stale, f"classified but no longer mentioned in the tests: {sorted(stale)}"
    assert not (IN_CONTAINER_TOOLS & NOT_RUN_IN_CONTAINER)


# ------------------------------------------------------------------ commands inside container shell scripts
#
# The word ratchet above only sees words from a closed candidate list, so a utility nobody listed
# (that is how `mkfifo` slipped through) is invisible to it.  This one reads the shell scripts the
# tests hand to `sh -c` and takes whatever stands in COMMAND position, with no candidate list.

SHELL_KEYWORDS_AND_BUILTINS = frozenset({
    "exit", "kill", "printf", "cd", "wait", "exec", "test", "set", "read", "eval", "trap", "done", "fi", "esac",
    "for", "in", "case", "return", "break", "continue", "export", "unset", "shift", "type", "command",
})
_KEYWORDS_BEFORE_COMMAND = re.compile(r"\b(?:do|then|else|elif|if|while|until)\b")
_COMMAND_POSITION = re.compile(
    r"""(?:^|[;&|(){}\n`]|\$\(|-c\s+['"])\s*([A-Za-z_][\w.+-]*)(?=[\s;&|()}'"]|$)"""
)
_SH_C_IN_TEXT = re.compile(r"""["']sh["']\s*,\s*["']-c["']\s*,\s*"((?:[^"\\]|\\.)*)\"""")


def _render(node: ast.AST, scopes: list[dict[str, str]]) -> str | None:
    """The text of a string expression: literals, f-strings, `+`, and names bound to those."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant):
                parts.append(str(part.value))
            elif isinstance(part, ast.FormattedValue):
                parts.append(_render(part.value, scopes) or "X")
        return "".join(parts)
    if isinstance(node, ast.Name):
        return next((scope[node.id] for scope in scopes if node.id in scope), None)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _render(node.left, scopes), _render(node.right, scopes)
        return left + right if left is not None and right is not None else None
    return None


def _bindings(nodes: Any, scopes: list[dict[str, str]]) -> dict[str, str]:
    bound: dict[str, str] = {}
    for n in nodes:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            text = _render(n.value, [bound, *scopes])
            if text is not None:
                bound[n.targets[0].id] = text
    return bound


def _container_shell_scripts() -> list[tuple[str, int, str]]:
    """(file, line, script) for every ``... "sh", "-c", <script> ...`` list/tuple, plus every such
    pattern spelled inside a string constant (the tests that run a Python helper in a subprocess)."""
    found: list[tuple[str, int, str]] = []
    for path in DOCKER_TEST_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module_scope = _bindings(tree.body, [])

        def visit(node: ast.AST, scopes: list[dict[str, str]]) -> None:
            for child in ast.iter_child_nodes(node):
                inner = scopes
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    inner = [_bindings(ast.walk(child), scopes), *scopes]
                if isinstance(child, (ast.Tuple, ast.List)):
                    lits = [e.value if isinstance(e, ast.Constant) and isinstance(e.value, str) else None for e in child.elts]
                    for i in range(len(lits) - 2):
                        if lits[i] == "sh" and lits[i + 1] == "-c":
                            text = _render(child.elts[i + 2], inner)
                            assert text is not None, f"{path.name}:{child.lineno}: cannot resolve the sh -c script"
                            found.append((path.name, child.lineno, text))
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    for m in _SH_C_IN_TEXT.finditer(child.value):
                        found.append((path.name, child.lineno, m.group(1)))
                visit(child, inner)

        visit(tree, [module_scope])
    return found


def _command_words(script: str) -> set[str]:
    text = _KEYWORDS_BEFORE_COMMAND.sub(";", script)
    return {m.group(1) for m in _COMMAND_POSITION.finditer(text)}


def test_command_word_extraction_handles_the_shapes_the_tests_use() -> None:
    assert _command_words("while true; do date +%s%N > /w/h.tmp && mv -f /w/h.tmp /w/h; sleep 0.2; done") == {
        "true", "date", "mv", "sleep", "done"}
    assert _command_words("sh -c '(sh -c \"echo x\" &) ; sleep 30'") == {"sh", "echo", "sleep"}
    assert _command_words("python3 -c \"'x'*10**9\" 2>/dev/null || : $(yes | head -c 200000000)") == {"python3", "yes", "head"}
    assert _command_words("mkfifo pipe; echo ok > legit.txt") == {"mkfifo", "echo"}
    assert _command_words("ls /proc | grep -c '^1$' || true") == {"ls", "grep", "true"}
    assert _command_words("X=1; printf 'deep' > f") == {"printf"}, "assignments and quoted arguments are not commands"


def test_every_command_a_container_shell_script_runs_is_required_or_a_shell_builtin() -> None:
    scripts = _container_shell_scripts()
    words: set[str] = set()
    for _, _, script in scripts:
        words |= _command_words(script)
    words -= SHELL_KEYWORDS_AND_BUILTINS
    assert len(scripts) >= 15, "the scan found too few `sh -c` scripts: has a test file changed shape?"
    assert {"date", "mv", "sleep", "mkfifo", "ln", "mkdir", "grep", "head", "yes", "python3", "ls", "cat", "rm"} <= words, (
        f"the scan misses commands it is known to see: {sorted(words)}"
    )
    required = _preflight_required_executables()
    assert words <= required, (
        f"container shell scripts run {sorted(words - required)}, which the preflight does not require: add each to "
        "the workflow's --require-executable list (or, if it is a shell builtin, to SHELL_KEYWORDS_AND_BUILTINS)"
    )


# ------------------------------------------------------------------ the Docker suite must not skip silently


_SKIP_STEP_NAME = "Assert the Docker-backed tests ran"


def _run_skip_step(tmp_path: Path, pytest_output: str) -> subprocess.CompletedProcess[str]:
    run = _step("tests", _SKIP_STEP_NAME)["run"]
    assert "/tmp/pytest-output.txt" in run
    out = tmp_path / "pytest-output.txt"
    out.write_text(pytest_output, encoding="utf-8")
    script = tmp_path / "step.sh"
    script.write_text(run.replace("/tmp/pytest-output.txt", str(out)), encoding="utf-8")
    return subprocess.run(["bash", "-e", str(script)], capture_output=True, text=True, timeout=60)


def test_the_skip_step_runs_after_the_gate_and_the_reasons_it_matches_are_the_tests_own() -> None:
    names = [s.get("name", "") for s in _steps("tests")]
    gate = next(i for i, n in enumerate(names) if n.startswith("Gate on pytest exit code"))
    skip = next(i for i, n in enumerate(names) if n.startswith(_SKIP_STEP_NAME))
    assert gate < skip
    assert "if" not in _steps("tests")[skip] and "continue-on-error" not in _steps("tests")[skip]
    run = _steps("tests")[skip]["run"]
    gating_sources = (DOCKER_TESTS.read_text(encoding="utf-8"), CONTRACT_TESTS.read_text(encoding="utf-8"))
    for reason in ("requires a reachable Docker daemon", "requires the test image"):
        assert reason in run, f"the step no longer matches {reason!r}"
        assert any(reason in src for src in gating_sources), f"no Docker test gate uses the reason {reason!r} any more"


@pytest.mark.skipif(shutil.which("bash") is None, reason="executes the workflow's bash step")
class TestDockerSkipAssertionStep:
    CLEAN = "....\n=== short test summary info ===\nFAILED tests/x.py::t - boom\n10 passed, 1 failed in 1.0s\n"

    @pytest.mark.parametrize("reason", [
        "requires a reachable Docker daemon",
        "requires the test image 'python:3.12-slim' locally (OCBRAIN_SANDBOX_DOCKER_IMAGE; it must contain python3)",
    ])
    def test_a_docker_prerequisite_skip_fails_the_job(self, tmp_path: Path, reason: str) -> None:
        r = _run_skip_step(tmp_path, self.CLEAN + f"SKIPPED [57] tests/core/sandbox/test_docker_backend.py: {reason}\n")
        assert r.returncode == 1, r.stdout
        assert "::error::" in r.stdout

    def test_an_unrelated_skip_does_not(self, tmp_path: Path) -> None:
        r = _run_skip_step(tmp_path, self.CLEAN + "SKIPPED [1] tests/core/sandbox/test_docker_backend.py:870: requires gcc-multilib (a real 32-bit static toolchain)\n")
        assert r.returncode == 0, r.stdout
        assert "no Docker-prerequisite skips" in r.stdout

    def test_a_run_without_skips_passes(self, tmp_path: Path) -> None:
        assert _run_skip_step(tmp_path, self.CLEAN).returncode == 0

    def test_the_words_in_a_test_name_or_a_failure_message_are_not_a_skip(self, tmp_path: Path) -> None:
        r = _run_skip_step(tmp_path, "FAILED tests/x.py::test_requires_a_reachable_Docker_daemon - requires a reachable Docker daemon\n")
        assert r.returncode == 0, "only SKIPPED lines count"


# ------------------------------------------------------------------ mypy


def test_mypy_job_is_pinned_narrow_and_covers_both_b03_files_in_both_modes() -> None:
    install = _step("typecheck-b03", "Install pinned mypy")["run"]
    assert "mypy==2.4.0" in install and "pytest==9.2.0" in install, "both tools pinned to the evidence versions"
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
