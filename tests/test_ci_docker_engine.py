"""Tests for scripts/ci_docker_engine.py (the pinned Docker Engine the A9 job needs).

Nothing here touches a real daemon, apt or the network: the module's ``Runner`` is replaced by a
scripted fake host that records every command, and the apt directory is a temporary tree.  What
the tests establish is the *logic*: the order of the stages, that the signing key is verified
before ANY apt configuration is touched, that exactly the pinned versions are installed, and that
every failure is named, fail-closed and still leaves a report.  They establish nothing about what
Docker's repository serves today (that is observed by the hosted run, see the spec).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ci_a9_verifier  # noqa: E402
import ci_docker_engine as eng  # noqa: E402

PINNED = "29.8.2"
APT_VERSION = "5:29.8.2-1~ubuntu.26.04~resolute"
OS_RELEASE = 'ID=ubuntu\nVERSION_ID="26.04"\nVERSION_CODENAME=resolute\nUBUNTU_CODENAME=resolute\n'
FPR = eng.DOCKER_KEY_FINGERPRINT


def gpg_output(primary: Sequence[str] = (FPR,), subkeys: Sequence[str] = ("AAAA" * 10,)) -> str:
    lines: list[str] = []
    for fpr in primary:
        lines.append("pub:-:4096:1:8D81803C0EBFCD88:1487788586:::-:::scESC::::::23::0:")
        lines.append(f"fpr:::::::::{fpr}:")
        lines.append("uid:-::::1487788586::1234::Docker Release (CE deb) <docker@docker.com>::::::::::0:")
        for sub in subkeys:
            lines.append("sub:-:4096:1:7EA0A9C3F273FCD8:1487788586::::::s::::::23:")
            lines.append(f"fpr:::::::::{sub}:")
    return "\n".join(lines) + "\n"


def madison(versions: Sequence[str] = (APT_VERSION,), packages: Sequence[str] = eng.PACKAGES) -> str:
    return "".join(
        f" {p} | {v} | https://download.docker.com/linux/ubuntu resolute/stable amd64 Packages\n"
        for p in packages
        for v in versions
    )


class FakeHost:
    """A scripted host.  ``calls`` records every argv; behaviour is set through attributes."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.server = "29.4.2"
        self.client = "29.4.2"
        self.gpg = gpg_output()
        self.madison = madison()
        self.fail: dict[str, int] = {}  # stage key -> rc
        self.key_bytes = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
        self.info_answers_after = 0  # `docker info` answers only after this many failed tries
        self._info_calls_since_restart = 0
        self.restarted = False
        self.post_install_server: str | None = None
        self.post_install_client: str | None = None

    # --- helpers
    def names(self) -> list[str]:
        out: list[str] = []
        for c in self.calls:
            args = [a for a in c if a != "sudo"]
            out.append(args[0] if args[0] != "env" else args[2])
        return out

    def with_prefix(self, *prefix: str) -> list[list[str]]:
        return [c for c in self.calls if [a for a in c if a != "sudo"][: len(prefix)] == list(prefix)]

    def _rc(self, key: str) -> int:
        return self.fail.get(key, 0)

    def __call__(self, args: Sequence[str], timeout: float) -> tuple[int, str, str]:
        argv = list(args)
        self.calls.append(argv)
        a = [x for x in argv if x != "sudo"]
        if a[0] == "docker" and a[1] == "version":
            which = "Server" if "{{.Server.Version}}" in a else "Client"
            value = self.server if which == "Server" else self.client
            return 0, value + "\n", ""
        if a[0] == "docker" and a[1] == "info":
            if "{{json .SecurityOptions}}" in a:
                return 0, '["name=apparmor","name=seccomp,profile=builtin"]\n', ""
            self._info_calls_since_restart += 1
            if self._info_calls_since_restart <= self.info_answers_after:
                return 1, "", "Cannot connect to the Docker daemon"
            return 0, self.server + "\n", ""
        if a[0] == "curl":
            if self._rc("curl"):
                return self._rc("curl"), "", "curl: (22) The requested URL returned error: 404"
            Path(a[a.index("-o") + 1]).write_text(self.key_bytes, encoding="utf-8")
            return 0, "", ""
        if a[0] == "gpg":
            return self._rc("gpg"), self.gpg, ""
        if a[0] == "rm":
            return self._rc("rm"), "", ""
        if a[0] == "install":
            return self._rc("install"), "", ""
        if a[0] == "apt-get" and a[1] == "update":
            return self._rc("apt-update"), "", "E: boom" if self._rc("apt-update") else ""
        if a[0] == "apt-cache":
            return self._rc("madison"), self.madison, ""
        if a[0] == "env" and "apt-get" in a:
            rc = self._rc("apt-install")
            if rc == 0:
                self.server = self.post_install_server or PINNED
                self.client = self.post_install_client or PINNED
            return rc, "", "E: dpkg was interrupted" if rc else ""
        if a[0] == "systemctl":
            self.restarted = True
            self._info_calls_since_restart = 0
            return self._rc("systemctl"), "", ""
        if a[0] == "uname":
            return 0, "7.0.0-1012-azure\n", ""
        raise AssertionError(f"unexpected command {argv!r}")


@pytest.fixture
def env(tmp_path: Path) -> tuple[eng.Config, FakeHost, list[float]]:
    apt = tmp_path / "apt"
    (apt / "sources.list.d").mkdir(parents=True)
    (apt / "sources.list").write_text("# nothing\n", encoding="utf-8")
    osr = tmp_path / "os-release"
    osr.write_text(OS_RELEASE, encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    sleeps: list[float] = []
    cfg = eng.Config(
        version=PINNED, apt_dir=apt, os_release=osr, work_dir=work,
        daemon_wait_attempts=4, daemon_wait_delay=0.5, sleep=sleeps.append,
    )
    return cfg, FakeHost(), sleeps


# ------------------------------------------------------------------ pure helpers


@pytest.mark.parametrize("text", ["29.8.2", "29.10.0", "30.0.0", " 29.8.2 "])
def test_parse_version_accepts_exact_stable_versions(text: str) -> None:
    assert eng.parse_version(text) == tuple(int(p) for p in text.strip().split("."))


@pytest.mark.parametrize(
    "text", ["", "29.8", "29", "29.8.2.1", "29.8.2-rc1", "v29.8.2", "29.8.x", "29.08.2", "latest", "29.8.*", ">=29.8.0"],
)
def test_parse_version_rejects_everything_that_is_not_an_exact_stable_version(text: str) -> None:
    with pytest.raises(ValueError):
        eng.parse_version(text)


@pytest.mark.parametrize(
    "version, expected",
    [((29, 7, 2), False), ((29, 8, 0), True), ((29, 8, 2), True), ((29, 10, 0), True),
     ((30, 0, 0), True), ((28, 99, 99), False), ((29, 4, 2), False)],
)
def test_floor_comparison(version: tuple[int, int, int], expected: bool) -> None:
    assert eng.at_or_above_floor(version) is expected


def test_floor_is_the_spec_floor_and_agrees_with_the_a9_verifier() -> None:
    # H-D13c route 1: Docker owns the deny rule from Engine 29.8.0; the verifier records the same floor.
    assert eng.ENGINE_FLOOR == (29, 8, 0)
    assert eng.ENGINE_FLOOR == ci_a9_verifier.ENGINE_FLOOR


def test_apt_version_string_matches_dockers_documented_format() -> None:
    assert eng.apt_version_string("29.8.2", "1", "26.04", "resolute") == APT_VERSION
    assert eng.apt_version_string("29.10.0", "1", "24.04", "noble") == "5:29.10.0-1~ubuntu.24.04~noble"


@pytest.mark.parametrize(
    "args", [("29.8", "1", "26.04", "resolute"), ("29.8.2", "0", "26.04", "resolute"),
             ("29.8.2", "x", "26.04", "resolute"), ("29.8.2", "1", "26", "resolute"),
             ("29.8.2", "1", "26.04", ""), ("29.8.2", "1", "26.04", "Resolute"), ("29.8.2", "1", "26.04", "res olute")],
)
def test_apt_version_string_rejects_unusable_inputs(args: tuple[str, str, str, str]) -> None:
    with pytest.raises(ValueError):
        eng.apt_version_string(*args)


def test_primary_fingerprints_ignore_subkeys() -> None:
    assert eng.primary_fingerprints(gpg_output()) == [FPR]
    assert eng.primary_fingerprints(gpg_output(primary=("B" * 40, FPR))) == ["B" * 40, FPR]


def test_key_is_pinned_only_for_exactly_the_pinned_primary_key() -> None:
    assert eng.key_is_pinned(gpg_output())
    assert eng.key_is_pinned(gpg_output(primary=(FPR.lower(),)))  # case-insensitive hex
    assert not eng.key_is_pinned("")
    assert not eng.key_is_pinned("garbage\n")
    assert not eng.key_is_pinned(gpg_output(primary=("B" * 40,)))
    assert not eng.key_is_pinned(gpg_output(primary=(FPR, "B" * 40)))  # an extra primary key
    assert not eng.key_is_pinned(gpg_output(primary=(FPR, FPR)))  # exactly one, not "at least one"
    assert not eng.key_is_pinned(gpg_output(primary=("B" * 40,), subkeys=(FPR,)))  # only a SUBkey matches
    assert not eng.key_is_pinned(gpg_output(primary=(FPR[:-1],)))  # truncated


def test_parse_madison() -> None:
    assert eng.parse_madison(madison(("1", "2"), ("docker-ce",))) == [("docker-ce", "1"), ("docker-ce", "2")]
    assert eng.parse_madison("\nnonsense\n") == []


def test_parse_os_release() -> None:
    d = eng.parse_os_release(OS_RELEASE + "# c=d\nNAME='Ubuntu'\n")
    assert d["ID"] == "ubuntu" and d["VERSION_ID"] == "26.04" and d["NAME"] == "Ubuntu" and "# c" not in d


def test_sudo_prefix() -> None:
    assert eng.sudo_prefix(0) == ()
    assert eng.sudo_prefix(1000) == ("sudo",)
    assert eng.sudo_prefix(1) == ("sudo",)


def test_constants_are_pinned() -> None:
    assert len(FPR) == 40 and FPR == FPR.upper() and FPR == "9DC858229FC7DD38854AE2D88D81803C0EBFCD88"
    assert eng.KEY_URL == "https://download.docker.com/linux/ubuntu/gpg"
    assert eng.REPO_URL == "https://download.docker.com/linux/ubuntu"
    assert eng.PACKAGES == ("docker-ce", "docker-ce-cli")
    assert eng.EPOCH == "5"
    assert eng.SCHEMA == "ocbrain.ci.docker-engine/1"


# ------------------------------------------------------------------ provision: the happy path


def test_happy_path_order_and_report(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    report, failure = eng.provision(cfg, host)
    assert failure is None
    assert report["result"] == "passed" and report["installed"] is True and report["failed_stage"] is None
    assert report["before"] == {"server_version": "29.4.2", "client_version": "29.4.2"}
    assert report["after"]["server_version"] == PINNED and report["after"]["client_version"] == PINNED
    assert report["after"]["kernel"] == "7.0.0-1012-azure"
    assert report["apt_version"] == APT_VERSION
    assert report["key"]["primary_fingerprints"] == [FPR]
    names = host.names()
    # key verified before anything under /etc/apt is touched; install after the refresh; restart after install
    first_install = names.index("install")
    assert names.index("curl") < names.index("gpg") < first_install
    assert first_install < names.index("apt-get") < names.index("apt-cache") < names.index("apt-get", names.index("apt-cache"))
    assert names.index("apt-get", names.index("apt-cache")) < names.index("systemctl")
    assert names.index("systemctl") < len(names) - 1  # docker info / version verification follows the restart


def test_install_argv_is_exact(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    eng.provision(cfg, host)
    (install,) = [c for c in host.calls if "install" in c and "apt-get" in c]
    assert install[0] == "sudo"
    assert install[1:3] == ["env", "DEBIAN_FRONTEND=noninteractive"]
    assert "--allow-downgrades" in install and "--no-install-recommends" in install and "-y" in install
    assert f"docker-ce={APT_VERSION}" in install and f"docker-ce-cli={APT_VERSION}" in install
    pkgs = [a for a in install if "=" in a and not a.startswith(("DEBIAN_FRONTEND", "-"))]
    assert sorted(pkgs) == sorted(f"{p}={APT_VERSION}" for p in eng.PACKAGES)
    joined = " ".join(install)
    for forbidden in ("containerd", "--force-yes", "latest", "docker-compose", "buildx"):
        assert forbidden not in joined


def test_apt_update_is_limited_to_the_pinned_docker_source(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    eng.provision(cfg, host)
    (upd,) = [c for c in host.calls if "apt-get" in c and "update" in c]
    list_dest = cfg.apt_dir / "sources.list.d" / eng.LIST_DEST_NAME
    assert f"Dir::Etc::sourcelist={list_dest}" in upd
    assert "Dir::Etc::sourceparts=-" in upd


def test_source_line_and_key_destination(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    eng.provision(cfg, host)
    key_dest = cfg.apt_dir / "keyrings" / eng.KEY_DEST_NAME
    line = (cfg.work_dir / eng.LIST_DEST_NAME).read_text(encoding="utf-8")
    assert line == f"deb [arch=amd64 signed-by={key_dest}] https://download.docker.com/linux/ubuntu resolute stable\n"
    installs = host.with_prefix("install")
    assert any(c[-1] == str(key_dest) and c[-2] == str(cfg.work_dir / "ocbrain-docker-key.asc") for c in installs)
    assert any(c[-1] == str(cfg.apt_dir / "sources.list.d" / eng.LIST_DEST_NAME) for c in installs)
    assert all("0644" in c or "0755" in c for c in installs)


def test_no_sudo_when_already_root(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    cfg.sudo = ()
    report, failure = eng.provision(cfg, host)
    assert failure is None and report["result"] == "passed"
    assert all("sudo" not in c for c in host.calls)


def test_already_at_the_pinned_version_installs_nothing(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.server = host.client = PINNED
    report, failure = eng.provision(cfg, host)
    assert failure is None and report["result"] == "passed" and report["installed"] is False
    assert set(host.names()) <= {"docker", "uname"}
    assert not host.restarted


def test_daemon_at_version_but_client_not_still_installs(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.server, host.client = PINNED, "29.4.2"
    report, failure = eng.provision(cfg, host)
    assert failure is None and report["installed"] is True


# ------------------------------------------------------------------ provision: fail-closed


def _assert_no_apt_or_sudo_activity(host: FakeHost) -> None:
    assert not [c for c in host.calls if "sudo" in c], host.calls
    assert not {"apt-get", "apt-cache", "install", "systemctl", "rm"} & set(host.names()), host.names()


def test_wrong_key_stops_before_any_apt_configuration(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.gpg = gpg_output(primary=("B" * 40,))
    report, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "key"
    assert report["result"] == "failed" and report["failed_stage"] == "key"
    assert "Nothing was installed" in report["message"]
    assert report["key"]["primary_fingerprints"] == ["B" * 40]
    _assert_no_apt_or_sudo_activity(host)


def test_extra_primary_key_in_the_file_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.gpg = gpg_output(primary=(FPR, "C" * 40))
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "key"
    _assert_no_apt_or_sudo_activity(host)


def test_key_with_only_a_matching_subkey_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.gpg = gpg_output(primary=("B" * 40,), subkeys=(FPR,))
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "key"
    _assert_no_apt_or_sudo_activity(host)


@pytest.mark.parametrize("stage_key", ["curl", "gpg"])
def test_key_download_or_read_failure_stops(env: tuple[eng.Config, FakeHost, list[float]], stage_key: str) -> None:
    cfg, host, _ = env
    host.fail[stage_key] = 22
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "key"
    _assert_no_apt_or_sudo_activity(host)


def test_curl_success_without_a_file_is_still_a_failure(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env

    def runner(args: Sequence[str], timeout: float) -> tuple[int, str, str]:
        if args[0] == "curl":
            host.calls.append(list(args))
            return 0, "", ""
        return host(args, timeout)

    _, failure = eng.provision(cfg, runner)
    assert failure is not None and failure.stage == "key"


def test_stale_key_file_is_never_reused(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    (cfg.work_dir / "ocbrain-docker-key.asc").write_text("stale but valid-looking\n", encoding="utf-8")

    def runner(args: Sequence[str], timeout: float) -> tuple[int, str, str]:
        if args[0] == "curl":
            host.calls.append(list(args))
            return 0, "", ""  # claims success, writes nothing
        return host(args, timeout)

    _, failure = eng.provision(cfg, runner)
    assert failure is not None and failure.stage == "key"
    _assert_no_apt_or_sudo_activity(host)


def test_key_download_argv_fails_on_http_errors_and_uses_https(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    eng.provision(cfg, host)
    (curl,) = host.with_prefix("curl")
    assert "-fsSL" in curl and curl[-1] == "https://download.docker.com/linux/ubuntu/gpg"
    assert curl[curl.index("-o") + 1] == str(cfg.work_dir / "ocbrain-docker-key.asc")
    assert "--max-time" in curl and "--retry" in curl
    (gpg,) = host.with_prefix("gpg")
    assert gpg[:5] == ["gpg", "--batch", "--show-keys", "--with-colons", str(cfg.work_dir / "ocbrain-docker-key.asc")]


def test_existing_docker_sources_are_removed_and_recorded(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    d = cfg.apt_dir / "sources.list.d"
    (d / "docker.list").write_text("deb https://download.docker.com/linux/ubuntu resolute stable\n", encoding="utf-8")
    (d / "docker.sources").write_text("URIs: https://download.docker.com/linux/ubuntu\n", encoding="utf-8")
    (d / "other.list").write_text("deb http://archive.ubuntu.com/ubuntu resolute main\n", encoding="utf-8")
    (d / eng.LIST_DEST_NAME).write_text("deb https://download.docker.com/linux/ubuntu resolute stable\n", encoding="utf-8")
    report, failure = eng.provision(cfg, host)
    assert failure is None
    removed = sorted(Path(c[-1]).name for c in host.with_prefix("rm"))
    assert removed == ["docker.list", "docker.sources"]
    assert sorted(Path(p).name for p in report["removed_sources"]) == ["docker.list", "docker.sources"]
    assert all(c[:3] == ["sudo", "rm", "-f"] and "--" in c for c in host.with_prefix("rm"))


def test_main_sources_list_referencing_docker_is_refused(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    (cfg.apt_dir / "sources.list").write_text("deb https://download.docker.com/linux/ubuntu resolute stable\n", encoding="utf-8")
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "sources" and "refusing to edit" in failure.message
    assert "install" not in host.names() and "apt-get" not in host.names()


def test_removal_failure_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    (cfg.apt_dir / "sources.list.d" / "docker.list").write_text("deb https://download.docker.com/x\n", encoding="utf-8")
    host.fail["rm"] = 1
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "sources"
    assert "apt-get" not in host.names()


@pytest.mark.parametrize(
    "text, fragment",
    [("ID=debian\nVERSION_ID=12\nVERSION_CODENAME=bookworm\n", "only Ubuntu"),
     ("ID=ubuntu\nVERSION_ID=26.04\n", "lacks"),
     ("ID=ubuntu\nVERSION_CODENAME=resolute\n", "lacks"),
     ("", "only Ubuntu")],
)
def test_unsupported_or_incomplete_os_release_stops(env: tuple[eng.Config, FakeHost, list[float]], text: str, fragment: str) -> None:
    cfg, host, _ = env
    cfg.os_release.write_text(text, encoding="utf-8")
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "sources" and fragment in failure.message
    assert "curl" not in host.names()


def test_missing_os_release_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    cfg.os_release.unlink()
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "sources"


def test_pinned_version_not_offered_lists_what_is(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.madison = madison(("5:29.4.2-1~ubuntu.26.04~resolute", "5:29.10.0-1~ubuntu.26.04~resolute"))
    report, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "repository"
    assert "5:29.10.0-1~ubuntu.26.04~resolute" in failure.message and APT_VERSION in failure.message
    assert report["failed_stage"] == "repository"
    assert not [c for c in host.calls if "apt-get" in c and "install" in c]


def test_cli_package_missing_while_engine_package_present_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.madison = madison((APT_VERSION,), ("docker-ce",))
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "repository" and "docker-ce-cli" in failure.message


def test_a_different_revision_is_not_accepted(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.madison = madison(("5:29.8.2-2~ubuntu.26.04~resolute",))
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "repository"


def test_apt_update_failure_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.fail["apt-update"] = 100
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "repository" and "E: boom" in failure.message


def test_madison_failure_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.fail["madison"] = 1
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "repository"


def test_install_failure_stops_before_the_restart(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.fail["apt-install"] = 100
    report, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "install" and "dpkg was interrupted" in failure.message
    assert not host.restarted and report["installed"] is False


def test_restart_failure_stops(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, _ = env
    host.fail["systemctl"] = 1
    report, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "daemon"
    assert report["installed"] is True  # the report says the packages were installed even though the run failed


def test_daemon_that_never_answers_is_bounded(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, sleeps = env
    host.info_answers_after = 10_000
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "daemon" and "4 attempts" in failure.message
    waits = [c for c in host.calls if c[:2] == ["docker", "info"] and "{{.ServerVersion}}" in c]
    assert len(waits) == cfg.daemon_wait_attempts
    assert sleeps == [0.5] * (cfg.daemon_wait_attempts - 1)


def test_daemon_that_answers_late_is_accepted(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    cfg, host, sleeps = env
    host.info_answers_after = 2
    _, failure = eng.provision(cfg, host)
    assert failure is None and sleeps == [0.5, 0.5]


@pytest.mark.parametrize("attr", ["post_install_server", "post_install_client"])
def test_version_mismatch_after_install_stops(env: tuple[eng.Config, FakeHost, list[float]], attr: str) -> None:
    cfg, host, _ = env
    setattr(host, attr, "29.4.2")
    report, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "verify"
    assert report["after"]["server_version"] is not None


def test_floor_is_not_the_acceptance_rule_exactness_is(env: tuple[eng.Config, FakeHost, list[float]]) -> None:
    # 29.10.0 is above the floor but is not the pinned 29.8.2: a drifted daemon is a failure.
    cfg, host, _ = env
    host.post_install_server = "29.10.0"
    _, failure = eng.provision(cfg, host)
    assert failure is not None and failure.stage == "verify"


# ------------------------------------------------------------------ process and CLI


def test_run_command_reports_missing_executable_and_timeout() -> None:
    rc, _, err = eng.run_command(["definitely-not-a-real-executable-xyz"], 5)
    assert rc == 127 and "not found" in err
    rc, _, err = eng.run_command([sys.executable, "-c", "import time; time.sleep(30)"], 0.3)
    assert rc == 124 and "timed out" in err
    rc, out, _ = eng.run_command([sys.executable, "-c", "print('ok')"], 30)
    assert rc == 0 and out.strip() == "ok"


def _stub_provision(monkeypatch: pytest.MonkeyPatch, failure: eng.ProvisionFailure | None) -> list[eng.Config]:
    seen: list[eng.Config] = []

    def fake(cfg: eng.Config, run: Any = None) -> tuple[dict[str, Any], eng.ProvisionFailure | None]:
        seen.append(cfg)
        return {"schema": eng.SCHEMA, "result": "failed" if failure else "passed",
                "failed_stage": failure.stage if failure else None,
                "message": failure.message if failure else None}, failure

    monkeypatch.setattr(eng, "provision", fake)
    return seen


def test_main_success_writes_the_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    seen = _stub_provision(monkeypatch, None)
    report = tmp_path / "deep" / "dir" / "engine.json"
    assert eng.main(["--version", PINNED, "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["result"] == "passed"
    assert "docker-engine: PASS" in capsys.readouterr().out
    assert seen[0].version == PINNED and seen[0].revision == "1"
    assert seen[0].work_dir.name.startswith("ocbrain-docker-engine-")
    assert seen[0].sudo == (() if os.geteuid() == 0 else ("sudo",))


def test_main_failure_is_exit_1_and_still_writes_the_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _stub_provision(monkeypatch, eng.ProvisionFailure("key", "wrong key"))
    report = tmp_path / "engine.json"
    assert eng.main(["--version", PINNED, "--report", str(report)]) == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["failed_stage"] == "key" and data["message"] == "wrong key"
    assert "FAIL [key] wrong key" in capsys.readouterr().err


@pytest.mark.parametrize("euid, expected", [(0, ()), (1000, ("sudo",))])
def test_main_derives_sudo_from_the_effective_uid(monkeypatch: pytest.MonkeyPatch, euid: int, expected: tuple[str, ...]) -> None:
    seen = _stub_provision(monkeypatch, None)
    monkeypatch.setattr(eng.os, "geteuid", lambda: euid)
    assert eng.main(["--version", PINNED]) == 0
    assert seen[0].sudo == expected


def test_main_scratch_directory_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _stub_provision(monkeypatch, None)
    assert eng.main(["--version", PINNED]) == 0
    assert not seen[0].work_dir.exists()


@pytest.mark.parametrize(
    "argv",
    [[], ["--version"], ["--version", "29.4.2"], ["--version", "29.7.9"], ["--version", "29.8"], ["--version", "latest"],
     ["--version", "29.8.2-rc1"], ["--version", "29.8.2", "--apt-revision", "0"], ["--version", "29.8.2", "--apt-revision", "-1"],
     ["--version", "29.8.2", "--apt-revision", "x"]],
)
def test_main_usage_errors_exit_2_and_install_nothing(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    seen = _stub_provision(monkeypatch, None)
    with pytest.raises(SystemExit) as exc:
        eng.main(argv)
    assert exc.value.code == 2 and not seen


def test_main_accepts_the_floor_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_provision(monkeypatch, None)
    assert eng.main(["--version", "29.8.0"]) == 0


# ------------------------------------------------------------------ source hygiene


def test_script_source_has_no_shell_or_weakening_constructs() -> None:
    src = Path(eng.__file__).read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
    for forbidden in ("shell=True", "apt-key", "--force-yes", "--privileged", "seccomp=unconfined", "apparmor=unconfined",
                      "| sh", "| bash", "--insecure", " -k ", "[trusted=yes", "allow-insecure", "--allow-unauthenticated"):
        assert forbidden not in code, forbidden
