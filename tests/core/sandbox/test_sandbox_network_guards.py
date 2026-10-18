"""tests/core/sandbox/test_sandbox_network_guards.py -- B03: capacity and IPv6
guard primitives (workstream ``sandbox-network-isolation``).

Architecture sources:
    docs/architecture/sandbox-network-isolation-master-specification.md
    section 8 (capacity, ruling OD-5), section 9 (IPv6), invariants INV-7 and
    INV-8, test TC-14, batch B03; evidence record: reconciliation document
    section 22.
    core/sandbox/backends/_sandbox_network.py

Scope: unit tests of two INERT primitives. Nothing here needs Docker, root, a
firewall or the network, and none of it is evidence that the product enforces
INV-7 or INV-8: the guards are not wired into ``DockerBackend.create()`` (the
pin below fails if someone does that without replacing it with the wiring
batch's own tests). TC-13 (capacity against a real daemon) and TC-15 (IPv6 on
a real host) belong to later batches and are not claimed here.

Coverage:
    - structure: the module is a leaf (standard library imports only, so it
      cannot form an import cycle with ``docker_backend``) and nothing in
      ``core/`` imports it yet (inertness pin)
    - the ceiling is the ruled 29 and a limiter cannot be built above it
    - the effective limit is ``min(29, probe result)``; a failing or
      malformed probe is an error, never a silent fallback to the ceiling
    - limiter: limit, refusal without residue, release, idempotent release,
      foreign slots, slots that are never released stay held
    - limiter under concurrency: never above the limit, a slot is released
      once however many threads release it (D11)
    - TC-14: the IPv6 detection matrix over injected sources, plus the real
      procfs sources against a temporary tree
    - INV-9: every refusal is logged with structured fields
"""
from __future__ import annotations

import ast
import asyncio
import logging
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.sandbox.backends import _sandbox_network as sn
from core.sandbox.backends._sandbox_network import (
    MAX_CONCURRENT_SANDBOX_NETWORKS,
    Ipv6Sources,
    Ipv6State,
    NetworkSlotLimiter,
    SandboxIPv6RefusedError,
    SandboxNetworkCapacityError,
    SandboxNetworkCapacityProbeError,
    SandboxNetworkGuardError,
    effective_limit,
    enforce_ipv6_guard,
    evaluate_ipv6,
    proc_ipv6_sources,
    resolve_effective_limit,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "core" / "sandbox" / "backends" / "_sandbox_network.py"
# The module's own name as a whole identifier: docker_backend.py already has an
# unrelated `_ensure_sandbox_network()`, which must not count as a reference.
_GUARD_MODULE_NAME = re.compile(r"(?<![A-Za-z0-9_])_sandbox_network(?![A-Za-z0-9_])")


# ---------------------------------------------------------------- structure


def _imported_top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import would tie the guard module to its package"
            assert node.module is not None
            names.add(node.module.split(".")[0])
    return names


def test_module_is_a_leaf_with_standard_library_imports_only() -> None:
    imported = _imported_top_level_names(MODULE_PATH)
    foreign = sorted(imported - set(sys.stdlib_module_names) - {"__future__"})
    assert not foreign, (
        f"_sandbox_network.py must stay a leaf (it will be imported by docker_backend.py in B11, "
        f"so importing anything from this repository would create a cycle); found {foreign}"
    )


@pytest.mark.parametrize(
    "statement",
    [
        "import core.sandbox.backends._sandbox_network; import core.sandbox.backends.docker_backend",
        "import core.sandbox.backends.docker_backend; import core.sandbox.backends._sandbox_network",
    ],
)
def test_both_import_orders_work_in_a_fresh_interpreter(statement: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"import failed: {result.stderr}"


def test_nothing_in_core_imports_the_guard_module_yet() -> None:
    """Inertness pin (B03: 'not wired into create()'). B11 replaces this test
    with its wiring tests in the same change that wires the guards."""
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "core").rglob("*.py")):
        if path == MODULE_PATH:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str]
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [alias.name for alias in node.names]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names = [node.value]
            else:
                continue
            if any(_GUARD_MODULE_NAME.search(name) for name in names):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, f"the B03 guards must stay inert until B11 wires them; referenced at {offenders}"


def test_the_ceiling_is_the_ruled_29() -> None:
    assert MAX_CONCURRENT_SANDBOX_NETWORKS == 29
    assert type(MAX_CONCURRENT_SANDBOX_NETWORKS) is int


def test_every_refusal_is_a_runtime_error_under_one_base() -> None:
    for error in (SandboxNetworkCapacityError, SandboxNetworkCapacityProbeError, SandboxIPv6RefusedError):
        assert issubclass(error, SandboxNetworkGuardError)
    assert issubclass(SandboxNetworkGuardError, RuntimeError)


# ---------------------------------------------------------------- effective limit


@pytest.mark.parametrize(
    ("probe_result", "expected"),
    [(0, 0), (1, 1), (10, 10), (28, 28), (29, 29), (30, 29), (31, 29), (1000, 29)],
)
def test_effective_limit_is_min_of_29_and_the_probe_result(probe_result: int, expected: int) -> None:
    assert effective_limit(probe_result) == expected


@pytest.mark.parametrize("bad", [-1, -29, True, False, 1.5, 29.0, "29", None, [29], b"29"])
def test_a_malformed_probe_result_is_an_error_not_the_ceiling(bad: object) -> None:
    with pytest.raises(SandboxNetworkCapacityProbeError):
        effective_limit(bad)


class _FixedProbe:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0

    def probe(self) -> int:
        self.calls += 1
        return self.result  # type: ignore[return-value]


class _FailingProbe:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def probe(self) -> int:
        raise self.error


def test_resolve_calls_the_probe_exactly_once() -> None:
    probe = _FixedProbe(12)
    assert resolve_effective_limit(probe) == 12
    assert probe.calls == 1


@pytest.mark.parametrize("error", [RuntimeError("daemon down"), OSError("socket"), TimeoutError("slow")])
def test_a_failing_probe_is_a_chained_probe_error(error: Exception) -> None:
    with pytest.raises(SandboxNetworkCapacityProbeError) as info:
        resolve_effective_limit(_FailingProbe(error))
    assert info.value.__cause__ is error


def test_a_probe_returning_garbage_is_a_probe_error() -> None:
    with pytest.raises(SandboxNetworkCapacityProbeError):
        resolve_effective_limit(_FixedProbe("many"))


def test_cancellation_inside_the_probe_is_not_converted() -> None:
    cancelled = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError) as info:
        resolve_effective_limit(_FailingProbe(cancelled))
    assert info.value is cancelled


def test_a_limiter_built_from_a_probe_has_the_effective_limit() -> None:
    assert NetworkSlotLimiter.from_probe(_FixedProbe(40)).limit == 29
    assert NetworkSlotLimiter.from_probe(_FixedProbe(7)).limit == 7
    assert NetworkSlotLimiter.from_probe(_FixedProbe(0)).limit == 0


def test_a_limiter_cannot_be_built_from_a_failing_probe() -> None:
    with pytest.raises(SandboxNetworkCapacityProbeError):
        NetworkSlotLimiter.from_probe(_FailingProbe(RuntimeError("no daemon")))


# ---------------------------------------------------------------- limiter


@pytest.mark.parametrize("bad", [1.0, "3", None, True, False])
def test_limit_must_be_an_int(bad: object) -> None:
    with pytest.raises(TypeError):
        NetworkSlotLimiter(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [-1, 30, MAX_CONCURRENT_SANDBOX_NETWORKS + 1, 10**6])
def test_a_limiter_cannot_be_built_outside_zero_to_the_ceiling(bad: int) -> None:
    with pytest.raises(ValueError):
        NetworkSlotLimiter(bad)


def test_the_limit_is_accepted_at_both_ends() -> None:
    assert NetworkSlotLimiter(0).limit == 0
    assert NetworkSlotLimiter(MAX_CONCURRENT_SANDBOX_NETWORKS).limit == 29


def test_reservations_up_to_the_limit_then_a_defined_refusal() -> None:
    limiter = NetworkSlotLimiter(3)
    slots = [limiter.reserve(f"s{i}") for i in range(3)]
    assert limiter.in_use == 3 and limiter.available == 0
    with pytest.raises(SandboxNetworkCapacityError) as info:
        limiter.reserve("s3")
    assert (info.value.limit, info.value.in_use, info.value.owner) == (3, 3, "s3")
    assert "3 of 3" in str(info.value)
    assert limiter.in_use == 3, "a refused reservation must leave no residue"
    assert len(set(slots)) == 3


def test_a_limit_of_zero_refuses_everything() -> None:
    limiter = NetworkSlotLimiter(0)
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("only")
    assert limiter.in_use == 0


def test_release_frees_exactly_one_slot() -> None:
    limiter = NetworkSlotLimiter(2)
    first = limiter.reserve("a")
    limiter.reserve("b")
    assert limiter.release(first) is True
    assert limiter.in_use == 1
    limiter.reserve("c")
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("d")


def test_a_double_release_is_ignored_and_cannot_open_the_limit() -> None:
    limiter = NetworkSlotLimiter(2)
    first = limiter.reserve("a")
    limiter.reserve("b")
    assert limiter.release(first) is True
    assert limiter.release(first) is False
    assert limiter.release(first) is False
    assert limiter.in_use == 1
    limiter.reserve("c")
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("d")


def test_a_slot_that_is_never_released_stays_held() -> None:
    """Removal not confirmed: the caller keeps the slot, and the limiter must
    keep counting it however many other cycles run."""
    limiter = NetworkSlotLimiter(2)
    limiter.reserve("kept-because-removal-was-not-confirmed")
    for i in range(10):
        limiter.release(limiter.reserve(f"cycle-{i}"))
    assert limiter.in_use == 1
    limiter.reserve("second")
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("third")


def test_two_reservations_by_one_owner_are_two_slots() -> None:
    limiter = NetworkSlotLimiter(2)
    first = limiter.reserve("same")
    second = limiter.reserve("same")
    assert first is not second
    assert limiter.release(first) is True
    assert limiter.in_use == 1
    assert limiter.release(second) is True


def test_a_foreign_slot_is_rejected_and_changes_nothing() -> None:
    mine, other = NetworkSlotLimiter(1), NetworkSlotLimiter(1)
    foreign = other.reserve("x")
    mine_slot = mine.reserve("y")
    with pytest.raises(ValueError):
        mine.release(foreign)
    assert (mine.in_use, other.in_use) == (1, 1)
    assert mine.release(mine_slot) is True


# ---------------------------------------------------------------- limiter, concurrently


@pytest.fixture
def fast_thread_switching() -> Iterator[None]:
    """Make the interpreter switch threads very often so that a missing lock
    shows up instead of hiding behind the GIL's long default time slice."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_reservations_never_exceed_the_limit(fast_thread_switching: None) -> None:
    limit, workers = 5, 64
    limiter = NetworkSlotLimiter(limit)
    barrier = threading.Barrier(workers)
    outcomes: list[bool] = []

    def worker(index: int) -> None:
        barrier.wait()
        try:
            limiter.reserve(f"w{index}")
        except SandboxNetworkCapacityError:
            outcomes.append(False)
        else:
            outcomes.append(True)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert len(outcomes) == workers
    assert outcomes.count(True) == limit
    assert outcomes.count(False) == workers - limit
    assert limiter.in_use == limit


def test_concurrent_reserve_release_churn_never_holds_more_than_the_limit(
    fast_thread_switching: None,
) -> None:
    limit, workers, rounds = 4, 16, 300
    limiter = NetworkSlotLimiter(limit)
    barrier = threading.Barrier(workers)
    guard = threading.Lock()
    state = {"holding": 0, "peak": 0, "granted": 0, "refused": 0}

    def worker(index: int) -> None:
        barrier.wait()
        for _ in range(rounds):
            try:
                slot = limiter.reserve(f"w{index}")
            except SandboxNetworkCapacityError:
                with guard:
                    state["refused"] += 1
                continue
            with guard:
                state["granted"] += 1
                state["holding"] += 1
                state["peak"] = max(state["peak"], state["holding"])
            time.sleep(0)  # yield while holding, so that over-granted slots overlap
            assert limiter.in_use <= limit, "the limiter itself holds more slots than its limit"
            with guard:
                state["holding"] -= 1
            assert limiter.release(slot) is True

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert state["granted"] + state["refused"] == workers * rounds
    assert state["granted"] > 0
    assert state["peak"] <= limit, f"{state['peak']} slots were held at once, limit is {limit}"
    assert limiter.in_use == 0


def test_many_threads_releasing_one_slot_release_it_once(fast_thread_switching: None) -> None:
    limiter = NetworkSlotLimiter(1)
    slot = limiter.reserve("only")
    workers = 32
    barrier = threading.Barrier(workers)
    results: list[bool] = []

    def worker() -> None:
        barrier.wait()
        results.append(limiter.release(slot))

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert results.count(True) == 1
    assert results.count(False) == workers - 1
    assert limiter.in_use == 0
    limiter.reserve("next")
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("one too many")


# ---------------------------------------------------------------- TC-14: IPv6 matrix


class _Reads:
    """Injected sources that record what the guard asked for."""

    def __init__(
        self,
        *,
        net: bool | BaseException = True,
        ipv6_dir: bool | BaseException = True,
        all_: str | BaseException = "1\n",
        default: str | BaseException = "1\n",
    ) -> None:
        self.net, self.ipv6_dir = net, ipv6_dir
        self.values: dict[str, str | BaseException] = {"all": all_, "default": default}
        self.asked: list[str] = []

    def _answer(self, label: str, value: bool | BaseException) -> bool:
        self.asked.append(label)
        if isinstance(value, BaseException):
            raise value
        return value

    def sources(self) -> Ipv6Sources:
        def read(scope: str) -> str:
            self.asked.append(f"read:{scope}")
            value = self.values[scope]
            if isinstance(value, BaseException):
                raise value
            return value

        return Ipv6Sources(
            sysctl_net_present=lambda: self._answer("net", self.net),
            ipv6_dir_present=lambda: self._answer("ipv6_dir", self.ipv6_dir),
            read_disable_ipv6=read,
        )


_DENIED = PermissionError(13, "Permission denied")

_MATRIX = [
    pytest.param({"ipv6_dir": False}, Ipv6State.OFF, id="absent"),
    pytest.param({}, Ipv6State.OFF, id="both-1"),
    pytest.param({"all_": "1", "default": "1"}, Ipv6State.OFF, id="both-1-no-newline"),
    pytest.param({"all_": "0\n", "default": "0\n"}, Ipv6State.ON, id="both-0"),
    pytest.param({"all_": "1\n", "default": "0\n"}, Ipv6State.ON, id="all-1-default-0"),
    pytest.param({"all_": "0\n", "default": "1\n"}, Ipv6State.ON, id="all-0-default-1"),
    pytest.param({"all_": _DENIED}, Ipv6State.UNKNOWN, id="all-unreadable"),
    pytest.param({"default": _DENIED}, Ipv6State.UNKNOWN, id="default-unreadable"),
    pytest.param({"all_": _DENIED, "default": _DENIED}, Ipv6State.UNKNOWN, id="both-unreadable"),
    pytest.param({"all_": "0\n", "default": _DENIED}, Ipv6State.ON, id="all-0-default-unreadable"),
    pytest.param({"all_": _DENIED, "default": "0\n"}, Ipv6State.ON, id="all-unreadable-default-0"),
    pytest.param({"all_": ""}, Ipv6State.UNKNOWN, id="all-empty"),
    pytest.param({"default": "2\n"}, Ipv6State.UNKNOWN, id="default-2"),
    pytest.param({"all_": "yes"}, Ipv6State.UNKNOWN, id="all-yes"),
    pytest.param({"all_": "01"}, Ipv6State.UNKNOWN, id="all-01"),
    pytest.param({"all_": UnicodeDecodeError("ascii", b"\xff", 0, 1, "bad")}, Ipv6State.UNKNOWN, id="all-undecodable"),
    pytest.param({"default": RuntimeError("broken source")}, Ipv6State.UNKNOWN, id="unexpected-error-fails-closed"),
    pytest.param({"net": False, "ipv6_dir": False}, Ipv6State.UNKNOWN, id="net-sysctl-not-readable"),
    pytest.param({"net": _DENIED}, Ipv6State.UNKNOWN, id="net-check-denied"),
    pytest.param({"ipv6_dir": OSError(5, "I/O error")}, Ipv6State.UNKNOWN, id="ipv6-dir-check-failed"),
]


@pytest.mark.parametrize(("kwargs", "expected"), _MATRIX)
def test_tc14_detection_matrix(kwargs: dict[str, object], expected: Ipv6State) -> None:
    reads = _Reads(**kwargs)  # type: ignore[arg-type]
    decision = evaluate_ipv6(reads.sources())
    assert decision.state is expected, decision.reason
    assert decision.supported is (expected is Ipv6State.OFF)
    assert decision.reason


@pytest.mark.parametrize(("kwargs", "expected"), _MATRIX)
def test_tc14_the_guard_refuses_unless_ipv6_is_off(kwargs: dict[str, object], expected: Ipv6State) -> None:
    reads = _Reads(**kwargs)  # type: ignore[arg-type]
    if expected is Ipv6State.OFF:
        assert enforce_ipv6_guard(reads.sources()).state is Ipv6State.OFF
        return
    with pytest.raises(SandboxIPv6RefusedError) as info:
        enforce_ipv6_guard(reads.sources())
    assert info.value.decision.state is expected
    assert expected.value in str(info.value)
    assert info.value.decision.reason in str(info.value)


def test_tc14_an_absent_ipv6_directory_is_not_followed_by_any_read() -> None:
    reads = _Reads(ipv6_dir=False)
    evaluate_ipv6(reads.sources())
    assert reads.asked == ["net", "ipv6_dir"]


def test_tc14_when_the_net_sysctl_is_unreadable_nothing_else_is_asked() -> None:
    reads = _Reads(net=False)
    assert evaluate_ipv6(reads.sources()).state is Ipv6State.UNKNOWN
    assert reads.asked == ["net"]


def test_tc14_exactly_all_and_default_are_read_each_once() -> None:
    reads = _Reads()
    evaluate_ipv6(reads.sources())
    assert reads.asked == ["net", "ipv6_dir", "read:all", "read:default"]


def test_tc14_a_zero_in_one_scope_is_still_checked_in_the_other() -> None:
    """Both scopes are read even when the first already says ON, so the reason
    names every scope that is enabled."""
    reads = _Reads(all_="0\n", default="0\n")
    decision = evaluate_ipv6(reads.sources())
    assert "'all'" in decision.reason and "'default'" in decision.reason


# ---------------------------------------------------------------- TC-14: real procfs sources


def _write(root: Path, relative: str, text: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="ascii")


def test_proc_sources_ipv6_directory_absent_is_off(tmp_path: Path) -> None:
    (tmp_path / "net").mkdir()
    decision = evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "net")))
    assert decision.state is Ipv6State.OFF


def test_proc_sources_missing_net_sysctl_is_unknown_not_off(tmp_path: Path) -> None:
    decision = evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "no-such-net")))
    assert decision.state is Ipv6State.UNKNOWN


@pytest.mark.parametrize(
    ("all_value", "default_value", "expected"),
    [
        ("1\n", "1\n", Ipv6State.OFF),
        ("0\n", "0\n", Ipv6State.ON),
        ("1\n", "0\n", Ipv6State.ON),
        ("0\n", "1\n", Ipv6State.ON),
        ("1\n", "x\n", Ipv6State.UNKNOWN),
    ],
)
def test_proc_sources_read_both_scopes_from_a_tree(
    tmp_path: Path, all_value: str, default_value: str, expected: Ipv6State
) -> None:
    _write(tmp_path, "net/ipv6/conf/all/disable_ipv6", all_value)
    _write(tmp_path, "net/ipv6/conf/default/disable_ipv6", default_value)
    assert evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "net"))).state is expected


def test_proc_sources_a_missing_scope_file_is_unknown(tmp_path: Path) -> None:
    _write(tmp_path, "net/ipv6/conf/all/disable_ipv6", "1\n")
    (tmp_path / "net/ipv6/conf/default").mkdir(parents=True)
    decision = evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "net")))
    assert decision.state is Ipv6State.UNKNOWN
    assert "default" in decision.reason


def test_proc_sources_an_unreadable_scope_file_is_unknown(tmp_path: Path) -> None:
    _write(tmp_path, "net/ipv6/conf/all/disable_ipv6", "1\n")
    (tmp_path / "net/ipv6/conf/default/disable_ipv6").mkdir(parents=True)  # a directory cannot be read as a file
    assert evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "net"))).state is Ipv6State.UNKNOWN


def test_proc_sources_a_failed_stat_is_unknown_not_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fail-open trap: ``os.path.isdir`` would turn a permission error into
    'absent', and 'absent' means IPv6 off."""
    (tmp_path / "net").mkdir()
    ipv6_path = str(tmp_path / "net" / "ipv6")
    real_stat = os.stat

    def stat(path: str | os.PathLike[str] | int, *args: object, **kwargs: object) -> os.stat_result:
        if str(path) == ipv6_path:
            raise PermissionError(13, "Permission denied", ipv6_path)
        return real_stat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "stat", stat)
    decision = evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "net")))
    assert decision.state is Ipv6State.UNKNOWN
    assert not decision.supported


def test_proc_sources_on_this_host_agree_with_a_direct_look() -> None:
    """The real /proc, once. The state depends on the host (this one boots with
    ipv6.disable=1); the assertion is only that the guard agrees with what the
    directory listing says, never what the value should be."""
    decision = evaluate_ipv6(proc_ipv6_sources())
    net, ipv6 = Path("/proc/sys/net"), Path("/proc/sys/net/ipv6")
    if not net.exists():
        assert decision.state is Ipv6State.UNKNOWN
    elif not ipv6.exists():
        assert decision.state is Ipv6State.OFF
    else:
        assert isinstance(decision.state, Ipv6State)
    assert decision.supported is (decision.state is Ipv6State.OFF)


# ---------------------------------------------------------------- INV-9: refusals are observable


def _events(caplog: pytest.LogCaptureFixture, event: str) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if getattr(record, "sandbox_network_event", {}).get("event") == event
    ]


def test_a_capacity_refusal_is_logged_with_structured_fields(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    limiter = NetworkSlotLimiter(1)
    limiter.reserve("first")
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("second")
    (record,) = _events(caplog, "sandbox_network_capacity_refused")
    assert record.levelno == logging.WARNING
    assert record.sandbox_network_event == {  # type: ignore[attr-defined]
        "event": "sandbox_network_capacity_refused",
        "owner": "second",
        "limit": 1,
        "in_use": 1,
    }


def test_reservations_and_releases_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    limiter = NetworkSlotLimiter(2)
    slot = limiter.reserve("a")
    limiter.release(slot)
    limiter.release(slot)
    assert len(_events(caplog, "sandbox_network_slot_reserved")) == 1
    assert len(_events(caplog, "sandbox_network_slot_released")) == 1
    assert len(_events(caplog, "sandbox_network_slot_release_ignored")) == 1


def test_an_ipv6_refusal_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    with pytest.raises(SandboxIPv6RefusedError):
        enforce_ipv6_guard(_Reads(all_="0\n").sources())
    (record,) = _events(caplog, "sandbox_network_ipv6_refused")
    assert record.levelno == logging.WARNING
    assert record.sandbox_network_event["state"] == "on"  # type: ignore[attr-defined]


def test_a_probe_failure_and_the_resolved_limit_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    with pytest.raises(SandboxNetworkCapacityProbeError):
        resolve_effective_limit(_FailingProbe(RuntimeError("down")))
    assert len(_events(caplog, "sandbox_network_capacity_probe_failed")) == 1
    resolve_effective_limit(_FixedProbe(31))
    (record,) = _events(caplog, "sandbox_network_capacity_resolved")
    assert record.sandbox_network_event["effective_limit"] == 29  # type: ignore[attr-defined]


def test_every_name_in_all_exists() -> None:
    missing = [name for name in sn.__all__ if not hasattr(sn, name)]
    assert not missing, f"__all__ lists names the module does not define: {missing}"
