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
    - a source that breaks its own ``str`` contract is UNKNOWN, never OFF and
      never an exception outside the guard hierarchy
    - every refusal survives copy and pickle (the worker pool and the task
      runner are separate processes)
    - INV-9: every refusal is logged with structured fields
"""
from __future__ import annotations

import ast
import asyncio
import copy
import gc
import logging
import os
import pickle
import re
import subprocess
import sys
import threading
import time
import warnings
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import pytest

from core.sandbox.backends import _sandbox_network as sn
from core.sandbox.backends._sandbox_network import (
    MAX_CONCURRENT_SANDBOX_NETWORKS,
    CapacityProbe,
    Ipv6Decision,
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
        check=False,
    )
    assert result.returncode == 0, f"import failed: {result.stderr}"


# Directories that are not repository code: VCS data, caches, virtual
# environments and vendored packages. The top-level ``tests`` directory is
# skipped by path in ``_production_python_files`` (tests may import the module).
_NOT_REPOSITORY_CODE = frozenset(
    {".git", ".hg", ".venv", "venv", "env", "node_modules", "site-packages", "__pycache__"}
)


def _production_python_files() -> Iterator[Path]:
    """Every ``.py`` file in the repository outside ``tests/`` and the
    directories above, not just ``core/``: the wiring batch could import the
    guards from ``interface/``, ``modules/``, ``scripts/`` or ``main.py``."""
    tests_root = REPO_ROOT / "tests"
    for directory, subdirectories, files in os.walk(REPO_ROOT):
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name not in _NOT_REPOSITORY_CODE
            and not name.endswith((".egg-info", "_cache"))
            and Path(directory, name) != tests_root
        )
        for name in sorted(files):
            if name.endswith(".py"):
                yield Path(directory, name)


def _guard_references(path: Path) -> list[int]:
    """Lines at which ``path`` names the guard module as an import or a string.
    A file that does not parse is searched as plain text instead of skipped."""
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [
            number
            for number, line in enumerate(source.splitlines(), start=1)
            if _GUARD_MODULE_NAME.search(line)
        ]
    lines: list[int] = []
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
            lines.append(node.lineno)
    return lines


def test_nothing_in_the_repository_imports_the_guard_module_yet() -> None:
    """Inertness pin (B03: 'not wired into create()'). B11 replaces this test
    with its wiring tests in the same change that wires the guards."""
    scanned = 0
    offenders: list[str] = []
    for path in _production_python_files():
        scanned += 1
        if path == MODULE_PATH:
            continue
        offenders += [f"{path.relative_to(REPO_ROOT)}:{line}" for line in _guard_references(path)]
    assert scanned > 100, f"the scan found only {scanned} files, so it is looking in the wrong place"
    assert not offenders, f"the B03 guards must stay inert until B11 wires them; referenced at {offenders}"


def test_the_pin_sees_a_reference_in_a_file_outside_core(tmp_path: Path) -> None:
    """The scan itself is tested: it must catch each way of naming the module,
    including from a file that does not parse."""
    import_form = tmp_path / "a.py"
    import_form.write_text("from core.sandbox.backends import _sandbox_network\n", encoding="utf-8")
    string_form = tmp_path / "b.py"
    string_form.write_text("name = 'core.sandbox.backends._sandbox_network'\n", encoding="utf-8")
    broken = tmp_path / "c.py"
    broken.write_text("def f(:\n    import _sandbox_network\n", encoding="utf-8")
    unrelated = tmp_path / "d.py"
    unrelated.write_text("from core.sandbox.backends.docker_backend import _ensure_sandbox_network\n", encoding="utf-8")
    assert _guard_references(import_form) == [1]
    assert _guard_references(string_form) == [1]
    assert _guard_references(broken) == [2]
    assert _guard_references(unrelated) == []


def test_module_does_no_dynamic_import_and_runs_no_generated_code() -> None:
    """LAW 3 and the leaf claim: no ``eval``/``exec``/``compile``/``__import__``
    and no ``importlib`` in the module."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    forbidden = {"eval", "exec", "compile", "__import__", "import_module"}
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute)
    }
    assert not called & forbidden, sorted(called & forbidden)
    assert "importlib" not in _imported_top_level_names(MODULE_PATH)


def test_the_ceiling_is_the_ruled_29() -> None:
    assert MAX_CONCURRENT_SANDBOX_NETWORKS == 29
    assert type(MAX_CONCURRENT_SANDBOX_NETWORKS) is int


def test_every_refusal_is_a_runtime_error_under_one_base() -> None:
    for error in (SandboxNetworkCapacityError, SandboxNetworkCapacityProbeError, SandboxIPv6RefusedError):
        assert issubclass(error, SandboxNetworkGuardError)
    assert issubclass(SandboxNetworkGuardError, RuntimeError)


# ---------------------------------------------------------------- refusals cross process boundaries

_REFUSALS = [
    pytest.param(
        # Distinct numbers, so that a rebuild which swaps the two is caught.
        lambda: SandboxNetworkCapacityError(limit=27, in_use=29, owner="op-1"),
        id="capacity",
    ),
    pytest.param(
        lambda: SandboxIPv6RefusedError(Ipv6Decision(Ipv6State.ON, "disable_ipv6 is 0 for 'all'")),
        id="ipv6-refused",
    ),
    pytest.param(
        lambda: SandboxNetworkCapacityProbeError("the probe failed"),
        id="probe-failed",
    ),
]


def _assert_same_refusal(clone: BaseException, original: BaseException) -> None:
    assert type(clone) is type(original)
    assert isinstance(clone, SandboxNetworkGuardError)
    assert clone.args == original.args
    assert str(clone) == str(original)
    assert vars(clone) == vars(original)


@pytest.mark.parametrize("make", _REFUSALS)
@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_a_refusal_survives_a_pickle_round_trip(make: Callable[[], BaseException], protocol: int) -> None:
    """The worker pool, the webhook process and the task runner are separate
    processes, so a refusal that cannot be pickled turns into an unrelated
    error where it is re-raised."""
    original = make()
    _assert_same_refusal(pickle.loads(pickle.dumps(original, protocol)), original)


@pytest.mark.parametrize("make", _REFUSALS)
def test_a_refusal_survives_copy_and_deepcopy(make: Callable[[], BaseException]) -> None:
    original = make()
    _assert_same_refusal(copy.copy(original), original)
    _assert_same_refusal(copy.deepcopy(original), original)


@pytest.mark.parametrize("make", _REFUSALS)
def test_a_pickled_refusal_keeps_notes_added_to_it(make: Callable[[], BaseException]) -> None:
    """Whatever ``BaseException`` keeps across a round trip by default
    (``add_note`` notes live in ``__dict__``) must still be kept."""
    original = make()
    original.add_note("raised while reserving a slot")
    clone = pickle.loads(pickle.dumps(original))
    assert clone.__notes__ == ["raised while reserving a slot"]


def test_a_copied_refusal_keeps_the_subclass_it_was_raised_as() -> None:
    """The rebuild goes through ``type(self)``, as ``BaseException`` does, not
    through the base class. (``copy`` is used because a class defined inside a
    test cannot be pickled by reference.)"""

    class _Capacity(SandboxNetworkCapacityError):
        pass

    class _Refused(SandboxIPv6RefusedError):
        pass

    capacity = copy.copy(_Capacity(limit=1, in_use=1, owner="op-2"))
    refused = copy.copy(_Refused(Ipv6Decision(Ipv6State.ON, "disable_ipv6 is 0 for 'all'")))
    assert type(capacity) is _Capacity
    assert type(refused) is _Refused


def test_a_pickled_capacity_refusal_keeps_its_fields() -> None:
    original = SandboxNetworkCapacityError(limit=5, in_use=3, owner="op-9")
    clone = pickle.loads(pickle.dumps(original))
    assert (clone.limit, clone.in_use, clone.owner) == (5, 3, "op-9")
    assert str(clone) == str(original)
    assert "3 of 5 slots in use" in str(clone) and "'op-9'" in str(clone)


def test_a_pickled_ipv6_refusal_keeps_its_decision() -> None:
    decision = Ipv6Decision(Ipv6State.UNKNOWN, "disable_ipv6 for 'all': unreadable")
    original = SandboxIPv6RefusedError(decision)
    clone = pickle.loads(pickle.dumps(original))
    assert clone.decision == decision
    assert clone.decision.state is Ipv6State.UNKNOWN
    assert clone.decision.supported is False
    assert str(clone) == str(original)
    assert "IPv6 is unknown on this host" in str(clone)


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


def test_an_async_probe_is_refused_as_a_probe_error() -> None:
    """Documented in the module docstring: ``probe()`` is synchronous, and an
    ``async def probe`` hands back a coroutine, which is not an integer."""

    class _AsyncProbe:
        async def probe(self) -> int:
            return 5

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # the coroutine is never awaited
        with pytest.raises(SandboxNetworkCapacityProbeError, match="coroutine"):
            resolve_effective_limit(cast(CapacityProbe, _AsyncProbe()))
        gc.collect()


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


def test_a_copied_slot_is_not_the_slot_and_cannot_release_it() -> None:
    """Documented on ``NetworkSlot``: release is by identity, so a copy that is
    released does not free the original, and a copy is not silently accepted."""
    limiter = NetworkSlotLimiter(1)
    slot = limiter.reserve("a")
    clone = copy.copy(slot)
    assert clone is not slot
    assert limiter.release(clone) is False
    assert limiter.in_use == 1, "releasing a copy must not free the original"
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(slot)
    assert limiter.release(slot) is True


class _LockCheckedSet(set[sn.NetworkSlot]):
    """A ``_held`` replacement that fails the moment the limiter touches its
    slot set without holding its lock. Deterministic, unlike the thread tests,
    which can only fail when a bad interleaving happens to occur."""

    lock: threading.Lock

    def _check(self) -> None:
        assert self.lock.locked(), "the limiter touched its slot set without holding its lock"

    def add(self, item: sn.NetworkSlot) -> None:
        self._check()
        super().add(item)

    def discard(self, item: object) -> None:
        self._check()
        super().discard(item)

    def __contains__(self, item: object) -> bool:
        self._check()
        return super().__contains__(item)

    def __len__(self) -> int:
        self._check()
        return super().__len__()


def test_every_touch_of_the_slot_set_happens_under_the_lock(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    limiter = NetworkSlotLimiter(3)
    checked = _LockCheckedSet()
    checked.lock = limiter._lock
    limiter._held = checked
    first = limiter.reserve("a")
    limiter.reserve("b")
    with _logging_fails(RuntimeError("log sink down")), pytest.raises(RuntimeError):
        limiter.reserve("compensated")  # the give-back path touches the set too
    limiter.reserve("c")
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("d")
    assert limiter.in_use == 3 and limiter.available == 0
    assert limiter.release(first) is True
    assert limiter.release(first) is False
    assert limiter.in_use == 2 and limiter.available == 1


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
    pytest.param({"net": RuntimeError("broken source")}, Ipv6State.UNKNOWN, id="net-check-unexpected-error"),
    pytest.param(
        {"ipv6_dir": RuntimeError("broken source")}, Ipv6State.UNKNOWN, id="ipv6-dir-check-unexpected-error"
    ),
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
    # The whole phrase: for ON the bare word "on" is also inside "isolation".
    assert f"IPv6 is {expected.value} on this host" in str(info.value)
    assert info.value.decision.reason in str(info.value)


def test_tc14_an_absent_ipv6_directory_is_not_followed_by_any_read() -> None:
    reads = _Reads(ipv6_dir=False)
    evaluate_ipv6(reads.sources())
    assert reads.asked == ["net", "ipv6_dir"]


def test_tc14_when_the_net_sysctl_is_unreadable_nothing_else_is_asked() -> None:
    reads = _Reads(net=False)
    decision = evaluate_ipv6(reads.sources())
    assert decision.state is Ipv6State.UNKNOWN
    assert "not readable" in decision.reason, "the reason must say why, not only refuse"
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
    assert decision.state is Ipv6State.ON
    # Exact text and order: the scopes are named in the order they are read
    # (``all`` then ``default``), so the same host always logs the same line.
    assert decision.reason == "disable_ipv6 is 0 for 'all' and 'default'"


# ---------------------------------------------------------------- TC-14: a source that breaks its contract


def _sources_answering(
    values: Mapping[str, object], *, net: object = True, ipv6_dir: object = True
) -> Ipv6Sources:
    """Sources that return ``values`` (scope reads), ``net`` and ``ipv6_dir``
    (the two presence checks) unchecked, including values that break the
    declared ``str`` and ``bool`` contracts (a faulty injected source)."""

    def read(scope: str) -> str:
        return cast(str, values[scope])

    return Ipv6Sources(
        sysctl_net_present=lambda: cast(bool, net),
        ipv6_dir_present=lambda: cast(bool, ipv6_dir),
        read_disable_ipv6=read,
    )


_NOT_TEXT = [
    pytest.param(None, id="None"),
    pytest.param(1, id="int-1"),
    pytest.param(0, id="int-0"),
    pytest.param(True, id="True"),
    pytest.param(False, id="False"),
    pytest.param(1.0, id="float-1"),
    pytest.param(b"1", id="bytes-1"),
    pytest.param(b"0", id="bytes-0"),
    pytest.param(["1"], id="list"),
    pytest.param(object(), id="object"),
]


@pytest.mark.parametrize("bad", _NOT_TEXT)
@pytest.mark.parametrize("bad_scope", ["all", "default"])
def test_tc14_a_non_text_value_is_unknown_never_off(bad: object, bad_scope: str) -> None:
    """Even a value that looks like a one (``1``, ``True``, ``b"1"``) is not
    the text ``"1"``, so it cannot make IPv6 count as off."""
    other = "default" if bad_scope == "all" else "all"
    decision = evaluate_ipv6(_sources_answering({bad_scope: bad, other: "1\n"}))
    assert decision.state is Ipv6State.UNKNOWN, decision.reason
    assert decision.supported is False
    assert f"{bad_scope}:" in decision.reason


@pytest.mark.parametrize("bad", _NOT_TEXT)
def test_tc14_the_guard_refuses_with_its_own_error_for_a_non_text_value(bad: object) -> None:
    """A faulty source must surface as the guard's defined refusal, not as an
    ``AttributeError`` from inside the evaluation that a caller catching
    ``SandboxNetworkGuardError`` would miss."""
    with pytest.raises(SandboxNetworkGuardError) as info:
        enforce_ipv6_guard(_sources_answering({"all": bad, "default": bad}))
    assert isinstance(info.value, SandboxIPv6RefusedError)
    assert info.value.decision.state is Ipv6State.UNKNOWN


@pytest.mark.parametrize(
    "values",
    [
        pytest.param({"all": "0\n", "default": None}, id="all-0-default-not-text"),
        pytest.param({"all": None, "default": "0\n"}, id="all-not-text-default-0"),
    ],
)
def test_tc14_a_zero_still_wins_over_a_non_text_value(values: dict[str, object]) -> None:
    """ON takes precedence over UNKNOWN, as it does for an unreadable scope."""
    decision = evaluate_ipv6(_sources_answering(values))
    assert decision.state is Ipv6State.ON, decision.reason


_NOT_BOOL = [
    pytest.param(None, id="None"),
    pytest.param(0, id="int-0"),
    pytest.param(1, id="int-1"),
    pytest.param("", id="empty-str"),
    pytest.param("no", id="str-no"),
    pytest.param("False", id="str-False"),
    pytest.param([], id="empty-list"),
    pytest.param(b"", id="empty-bytes"),
    pytest.param(object(), id="object"),
]
_ON_FACTS = {"all": "0\n", "default": "0\n"}


@pytest.mark.parametrize("bad", _NOT_BOOL)
def test_tc14_a_non_bool_ipv6_directory_check_is_unknown_never_off(bad: object) -> None:
    """A falsy non-bool from the presence check used to read as 'directory
    absent', which is OFF, even when the facts underneath say IPv6 is on."""
    decision = evaluate_ipv6(_sources_answering(_ON_FACTS, ipv6_dir=bad))
    assert decision.state is Ipv6State.UNKNOWN, decision.reason
    assert decision.supported is False
    assert decision.reason == (
        f"the ipv6 sysctl directory check returned a {type(bad).__name__}, not a bool"
    )


@pytest.mark.parametrize("bad", _NOT_BOOL)
def test_tc14_a_non_bool_net_sysctl_check_is_unknown_never_off(bad: object) -> None:
    """The same for the net-sysctl check: only a real ``True`` lets 'ipv6 absent'
    count, and only a real ``False`` is the documented 'not readable' case."""
    decision = evaluate_ipv6(_sources_answering(_ON_FACTS, net=bad, ipv6_dir=False))
    assert decision.state is Ipv6State.UNKNOWN, decision.reason
    assert decision.supported is False
    # The reason names the broken contract, not the documented "not readable"
    # case that only a real ``False`` may report.
    assert decision.reason == f"the net sysctl check returned a {type(bad).__name__}, not a bool"


@pytest.mark.parametrize("bad", _NOT_BOOL)
def test_tc14_the_guard_refuses_with_its_own_error_for_a_non_bool_check(bad: object) -> None:
    for kwargs in ({"ipv6_dir": bad}, {"net": bad, "ipv6_dir": False}):
        with pytest.raises(SandboxIPv6RefusedError) as info:
            enforce_ipv6_guard(_sources_answering(_ON_FACTS, **kwargs))
        assert info.value.decision.state is Ipv6State.UNKNOWN


def test_tc14_only_a_real_bool_pair_can_make_ipv6_off_by_absence() -> None:
    assert evaluate_ipv6(_sources_answering(_ON_FACTS, net=True, ipv6_dir=False)).state is Ipv6State.OFF
    assert evaluate_ipv6(_sources_answering(_ON_FACTS, net=True, ipv6_dir=True)).state is Ipv6State.ON


class _HostileText(Exception):
    """An exception whose own ``__str__`` raises: formatting it into a reason
    must not become a second, unrelated exception inside the guard."""

    def __str__(self) -> str:
        raise ValueError("str() of the exception is broken")


def _raise_hostile(*_: object) -> bool:
    raise _HostileText()


@pytest.mark.parametrize(
    ("which", "expected_in_reason"),
    [
        pytest.param("net", "could not check for the ipv6 sysctl directory", id="net-check"),
        pytest.param("ipv6_dir", "could not check for the ipv6 sysctl directory", id="ipv6-dir-check"),
        pytest.param("read", "all: unreadable", id="scope-read"),
    ],
)
def test_tc14_an_exception_with_a_broken_str_is_unknown_not_a_foreign_error(
    which: str, expected_in_reason: str
) -> None:
    sources = Ipv6Sources(
        sysctl_net_present=_raise_hostile if which == "net" else (lambda: True),
        ipv6_dir_present=_raise_hostile if which == "ipv6_dir" else (lambda: True),
        read_disable_ipv6=cast(Callable[[str], str], _raise_hostile) if which == "read" else (lambda scope: "1\n"),
    )
    decision = evaluate_ipv6(sources)
    assert decision.state is Ipv6State.UNKNOWN
    assert "_HostileText" in decision.reason and expected_in_reason in decision.reason
    with pytest.raises(SandboxIPv6RefusedError):
        enforce_ipv6_guard(sources)


def test_a_probe_that_raises_an_exception_with_a_broken_str_is_a_probe_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    with pytest.raises(SandboxNetworkCapacityProbeError) as info:
        resolve_effective_limit(_FailingProbe(_HostileText()))
    assert isinstance(info.value.__cause__, _HostileText)
    assert "_HostileText" in str(info.value)
    (record,) = _events(caplog, "sandbox_network_capacity_probe_failed")
    assert "_HostileText" in record.sandbox_network_event["error"]  # type: ignore[attr-defined]


def test_tc14_both_scopes_are_still_read_after_a_non_text_value() -> None:
    asked: list[str] = []

    def read(scope: str) -> str:
        asked.append(scope)
        return cast(str, None if scope == "all" else "1\n")

    decision = evaluate_ipv6(
        Ipv6Sources(lambda: True, lambda: True, read),
    )
    assert asked == ["all", "default"]
    assert decision.state is Ipv6State.UNKNOWN


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


def test_proc_sources_a_net_sysctl_that_is_a_file_is_unknown_not_absent(tmp_path: Path) -> None:
    """``stat('<file>/ipv6')`` is ``NotADirectoryError``, not ``FileNotFoundError``:
    only the latter may count as 'the ipv6 directory is absent'."""
    (tmp_path / "net").write_text("not a directory", encoding="ascii")
    decision = evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "net")))
    assert decision.state is Ipv6State.UNKNOWN
    assert "NotADirectoryError" in decision.reason


def test_proc_sources_a_scope_file_that_is_not_ascii_is_unknown(tmp_path: Path) -> None:
    (tmp_path / "net/ipv6/conf/all").mkdir(parents=True)
    (tmp_path / "net/ipv6/conf/all/disable_ipv6").write_bytes(b"1\xff")
    _write(tmp_path, "net/ipv6/conf/default/disable_ipv6", "1\n")
    decision = evaluate_ipv6(proc_ipv6_sources(str(tmp_path / "net")))
    assert decision.state is Ipv6State.UNKNOWN
    assert "all: unreadable (UnicodeDecodeError" in decision.reason


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


def _sequence(caplog: pytest.LogCaptureFixture) -> list[tuple[str, int, object]]:
    """``(event, level, in_use)`` of every guard record, in emission order."""
    return [
        (
            record.sandbox_network_event["event"],
            record.levelno,
            record.sandbox_network_event.get("in_use"),
        )
        for record in caplog.records
        if hasattr(record, "sandbox_network_event")
    ]


def test_reservations_and_releases_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    limiter = NetworkSlotLimiter(3)
    limiter.reserve("holder")
    slot = limiter.reserve("a")
    limiter.release(slot)
    limiter.release(slot)
    assert _sequence(caplog) == [
        ("sandbox_network_slot_reserved", logging.DEBUG, 1),
        ("sandbox_network_slot_reserved", logging.DEBUG, 2),
        ("sandbox_network_slot_released", logging.DEBUG, 1),
        ("sandbox_network_slot_release_ignored", logging.DEBUG, 1),
    ]
    reserved = _events(caplog, "sandbox_network_slot_reserved")[1]
    assert reserved.sandbox_network_event == {  # type: ignore[attr-defined]
        "event": "sandbox_network_slot_reserved",
        "owner": "a",
        "limit": 3,
        "in_use": 2,
    }


def test_every_guard_event_is_logged_under_the_one_documented_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Operators filter on the logger name; it is part of the observable contract
    (a child or renamed logger would silently drop a filter or a routing rule)."""
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    assert sn.logger.name == "ocbrain.sandbox.network"
    limiter = NetworkSlotLimiter(1)
    slot = limiter.reserve("first")
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("second")
    limiter.release(slot)
    with pytest.raises(SandboxNetworkCapacityProbeError):
        resolve_effective_limit(_FailingProbe(OSError("no daemon")))
    with pytest.raises(SandboxIPv6RefusedError):
        enforce_ipv6_guard(_Reads(all_="0\n").sources())
    guard_records = [r for r in caplog.records if hasattr(r, "sandbox_network_event")]
    assert {event for event, _level, _in_use in _sequence(caplog)} >= {
        "sandbox_network_slot_reserved",
        "sandbox_network_capacity_refused",
        "sandbox_network_slot_released",
        "sandbox_network_capacity_probe_failed",
        "sandbox_network_ipv6_refused",
    }
    assert {r.name for r in guard_records} == {"ocbrain.sandbox.network"}


class _RaisingFilter(logging.Filter):
    """A log filter that fails, standing in for any logging hook that raises:
    ``logging`` swallows a failing *handler*, but not a failing *filter*."""

    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self._error = error

    def filter(self, record: logging.LogRecord) -> bool:
        raise self._error


@contextmanager
def _logging_fails(error: BaseException) -> Iterator[None]:
    hostile = _RaisingFilter(error)
    sn.logger.addFilter(hostile)
    try:
        yield
    finally:
        sn.logger.removeFilter(hostile)


_LOGGING_FAILURES = [
    pytest.param(RuntimeError("log sink down"), id="RuntimeError"),
    pytest.param(KeyboardInterrupt(), id="KeyboardInterrupt"),
    pytest.param(asyncio.CancelledError(), id="CancelledError"),
]


@pytest.mark.parametrize("error", _LOGGING_FAILURES)
def test_a_failing_log_call_cannot_leak_a_reserved_slot(
    caplog: pytest.LogCaptureFixture, error: BaseException
) -> None:
    """A slot that ``reserve`` took but never handed back could never be
    released, so each one would shrink the limit for good (INV-7)."""
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    limiter = NetworkSlotLimiter(3)
    keeper = limiter.reserve("an unrelated holder")
    for attempt in range(6):
        with _logging_fails(error), pytest.raises(type(error)):
            limiter.reserve(f"attempt-{attempt}")
        assert limiter.in_use == 1, f"attempt {attempt}: a slot leaked, or the other holder lost its slot"
    first, second = limiter.reserve("after-1"), limiter.reserve("after-2")
    assert limiter.in_use == 3
    with pytest.raises(SandboxNetworkCapacityError):
        limiter.reserve("one too many")
    assert limiter.release(keeper) is True, "the unrelated holder must still own its slot"
    assert limiter.release(first) is True and limiter.release(second) is True
    assert limiter.in_use == 0


def test_an_owner_whose_repr_raises_cannot_leak_a_slot() -> None:
    """The log record is built from ``repr(owner)`` at any log level, so a
    hostile owner object fails the log call without any logging setup."""

    class _HostileOwner:
        def __repr__(self) -> str:
            raise ValueError("repr is broken")

    limiter = NetworkSlotLimiter(2)
    for attempt in range(4):
        with pytest.raises(ValueError, match="repr is broken"):
            limiter.reserve(cast(str, _HostileOwner()))
        assert limiter.in_use == 0, f"attempt {attempt} leaked a slot"
    assert limiter.release(limiter.reserve("fine")) is True


def test_a_failing_log_call_on_a_refusal_changes_no_state(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    limiter = NetworkSlotLimiter(1)
    held = limiter.reserve("holder")
    with _logging_fails(RuntimeError("log sink down")), pytest.raises(RuntimeError):
        limiter.reserve("refused")
    assert limiter.in_use == 1
    assert limiter.release(held) is True
    assert limiter.in_use == 0


def test_a_failing_log_call_on_release_still_releases(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    limiter = NetworkSlotLimiter(1)
    slot = limiter.reserve("a")
    with _logging_fails(RuntimeError("log sink down")), pytest.raises(RuntimeError):
        limiter.release(slot)
    assert limiter.in_use == 0, "the slot was freed before the log call and must stay freed"
    assert limiter.release(slot) is False
    limiter.reserve("b")


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
    (failed,) = _events(caplog, "sandbox_network_capacity_probe_failed")
    assert failed.levelno == logging.ERROR
    assert failed.sandbox_network_event["error"] == "RuntimeError: down"  # type: ignore[attr-defined]
    resolve_effective_limit(_FixedProbe(31))
    (record,) = _events(caplog, "sandbox_network_capacity_resolved")
    assert record.levelno == logging.INFO
    assert record.sandbox_network_event == {  # type: ignore[attr-defined]
        "event": "sandbox_network_capacity_resolved",
        "probe_result": 31,
        "ceiling": 29,
        "effective_limit": 29,
    }


def test_an_ipv6_pass_is_logged_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ocbrain.sandbox.network")
    enforce_ipv6_guard(_Reads().sources())
    (record,) = _events(caplog, "sandbox_network_ipv6_ok")
    assert record.levelno == logging.DEBUG
    assert record.sandbox_network_event["state"] == "off"  # type: ignore[attr-defined]
    assert not _events(caplog, "sandbox_network_ipv6_refused")


def test_every_name_in_all_exists() -> None:
    missing = [name for name in sn.__all__ if not hasattr(sn, name)]
    assert not missing, f"__all__ lists names the module does not define: {missing}"


def test_all_lists_every_public_name_the_module_defines() -> None:
    """The other direction: a public class, function or constant added later
    must be exported on purpose, not forgotten. ``logger`` is the one public
    name that is deliberately not part of the interface."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    defined: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            defined.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
        elif isinstance(node, ast.Assign):
            defined.update(target.id for target in node.targets if isinstance(target, ast.Name))
    public = {name for name in defined if not name.startswith("_")} - {"logger", "__all__"}
    assert public == set(sn.__all__)
    assert len(sn.__all__) == len(set(sn.__all__)), "__all__ lists a name twice"
