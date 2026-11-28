"""tests/test_workflow_instance_guard.py -- DEBT-028 / ADR-KERNEL-10 (PROPOSED).

The single-flight guard on a WorkflowRuntime ``instance_id``.

Structure:
    TestGuardProcessScope    the in-process registry, no I/O
    TestGuardConstruction    scope selection and argument validation
    TestSqliteClaimStore     the durable lease store, with an injected clock
    TestGuardHostScope       guard + store: heartbeat, lost claim, fail-closed
    TestRuntimeIntegration   execute()/resume() through the real WorkflowRuntime
    TestCrossProcess         two real processes, one hard-killed

Why ``test_without_the_guard_the_race_is_real`` exists: the guarded tests assert
"exactly one run".  That claim means nothing unless the same scenario provably
runs the node several times when the guard is absent, so this file asserts both.
"""

import asyncio
import contextlib
import os
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from core.events.event_stream import EventStream, SQLiteEventStore
from core.governance.governance_kernel import get_governance_kernel
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.workflow.definition import NodeStatus, WorkflowDefinition, WorkflowNode
from core.workflow.instance_guard import (
    ClaimInfo,
    ClaimScope,
    ClaimUnavailableError,
    InstanceBusyError,
    InstanceGuard,
    SqliteClaimStore,
)
from core.workflow.runtime import WorkflowNodeState, WorkflowRuntime

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── Helpers ──────────────────────────────────────────────────────────────────


class _Clock:
    """Deterministic clock for lease-expiry tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _ScriptedStore:
    """In-memory ClaimStore whose behaviour a test scripts."""

    def __init__(self, *, acquire_result=None, acquire_exc=None, renew_results=None) -> None:
        self.acquire_result = acquire_result
        self.acquire_exc = acquire_exc
        self.renew_results = list(renew_results or [])
        self.acquired = []
        self.released = []
        self.renew_calls = 0

    async def acquire(self, instance_id, *, holder_id, operation, ttl_s):
        if self.acquire_exc is not None:
            raise self.acquire_exc
        self.acquired.append((instance_id, holder_id))
        return self.acquire_result

    async def renew(self, instance_id, *, holder_id, ttl_s):
        self.renew_calls += 1
        outcome = self.renew_results.pop(0) if self.renew_results else True
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def release(self, instance_id, *, holder_id):
        self.released.append((instance_id, holder_id))


class _NoGuard:
    """Exactly the pre-DEBT-028 behaviour: nothing is ever refused."""

    scope = ClaimScope.PROCESS

    @asynccontextmanager
    async def claim(self, instance_id, *, operation, on_lost=None):
        yield


def _claim_rows(db_path) -> int:
    with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
        return conn.execute("SELECT COUNT(*) FROM workflow_instance_claims").fetchone()[0]


class GateWorker(AbstractCognitiveWorker):
    """Records every invocation, then blocks on a class-level gate.

    Class-level state because ExecutionRuntime builds a fresh worker instance
    per invoke() (ADR-003)."""

    worker_type = "GateWorker"
    invocations: list = []
    gate = None

    async def _run(self, context: WorkerContext) -> WorkerResult:
        type(self).invocations.append((context.metadata or {}).get("node_id"))
        if type(self).gate is not None:
            await type(self).gate.wait()
        return WorkerResult(success=True, output="done")

    @classmethod
    def reset(cls) -> None:
        cls.invocations = []
        cls.gate = asyncio.Event()


class WaitForCancelWorker(AbstractCognitiveWorker):
    """Runs until its CancellationToken fires (cooperative cancellation)."""

    worker_type = "WaitForCancelWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        token = context.cancellation_token
        for _ in range(250):
            if token is not None and token.is_cancelled:
                return WorkerResult(success=False, error="cancelled")
            await asyncio.sleep(0.02)
        return WorkerResult(success=True, output="ran to completion: claim loss was not noticed")


def _definition(worker_type: str, workflow_id: str = "w-guard") -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=workflow_id,
        nodes=[WorkflowNode(node_id="a", worker_type=worker_type)],
        entry_node="a",
    )


def _runtime(tmp_path, *worker_classes, guard=None) -> WorkflowRuntime:
    registry = WorkerRegistry()
    for cls in worker_classes:
        registry.register(cls)
    stream = EventStream(SQLiteEventStore(db_path=str(tmp_path / "events.db")))
    return WorkflowRuntime(
        execution_runtime=ExecutionRuntime(
            worker_registry=registry, governance=get_governance_kernel(), event_stream=stream,
        ),
        event_stream=stream,
        instance_guard=guard,
    )


def _record_events(runtime: WorkflowRuntime) -> list:
    seen: list = []
    original = runtime._emit_event

    async def spy(event_type, payload):
        seen.append((event_type, payload))
        await original(event_type, payload)

    runtime._emit_event = spy
    return seen


async def _seed_pending_checkpoint(runtime, instance_id: str, workflow_id: str = "w-guard") -> None:
    await runtime._save_checkpoint(
        instance_id, workflow_id,
        {"a": WorkflowNodeState(node_id="a", status=NodeStatus.PENDING)},
    )


# ── The in-process guard ─────────────────────────────────────────────────────


class TestGuardProcessScope:

    async def test_second_claim_on_a_held_id_is_rejected_immediately(self):
        guard = InstanceGuard()
        async with guard.claim("inst-1", operation="execute"):
            with pytest.raises(InstanceBusyError) as err:
                # wait_for proves "immediately": a queueing guard would hang here.
                await asyncio.wait_for(_enter(guard, "inst-1", "resume"), timeout=0.5)
        assert err.value.instance_id == "inst-1"
        assert err.value.scope is ClaimScope.PROCESS
        assert err.value.operation_in_flight == "execute"

    async def test_different_ids_do_not_interfere(self):
        guard = InstanceGuard()
        async with guard.claim("inst-a", operation="execute"):
            async with guard.claim("inst-b", operation="execute"):
                assert guard.active_count == 2
        assert guard.active_count == 0

    async def test_released_after_normal_exit_exception_and_cancellation(self):
        guard = InstanceGuard()
        async with guard.claim("inst-1", operation="execute"):
            pass
        with pytest.raises(RuntimeError):
            async with guard.claim("inst-1", operation="execute"):
                raise RuntimeError("body failed")

        async def holder():
            async with guard.claim("inst-1", operation="execute"):
                await asyncio.sleep(30)

        task = asyncio.create_task(holder())
        await asyncio.sleep(0.05)
        assert guard.active_count == 1
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert guard.active_count == 0
        async with guard.claim("inst-1", operation="resume"):  # free again
            pass

    async def test_registry_does_not_grow(self):
        guard = InstanceGuard()
        for i in range(1000):
            async with guard.claim(f"inst-{i}", operation="execute"):
                pass
        assert guard.active_count == 0

    async def test_storm_exactly_one_winner_and_nobody_waits(self):
        guard = InstanceGuard()
        outcomes: list = []
        release = asyncio.Event()

        async def contender(i: int) -> None:
            try:
                async with guard.claim("inst-storm", operation=f"op{i}"):
                    outcomes.append("won")
                    await release.wait()
            except InstanceBusyError:
                outcomes.append("busy")

        tasks = [asyncio.create_task(contender(i)) for i in range(50)]
        try:
            await asyncio.sleep(0.1)  # every loser is already rejected; the winner still holds
            assert outcomes.count("won") == 1
            assert outcomes.count("busy") == 49
        finally:
            release.set()  # a failing assertion must not leave tasks blocked
        await asyncio.gather(*tasks)
        assert guard.active_count == 0

    async def test_empty_instance_id_is_refused(self):
        with pytest.raises(ValueError):
            await _enter(InstanceGuard(), "", "execute")


async def _enter(guard, instance_id: str, operation: str) -> None:
    async with guard.claim(instance_id, operation=operation):
        pass


# ── Construction ─────────────────────────────────────────────────────────────


class TestGuardConstruction:

    def test_process_scope_is_the_default_and_does_no_io(self):
        assert InstanceGuard().scope is ClaimScope.PROCESS
        assert InstanceGuard.from_scope(" Process ").scope is ClaimScope.PROCESS

    def test_host_scope_builds_a_durable_store(self, tmp_path):
        db = tmp_path / "nested" / "claims.db"
        guard = InstanceGuard.from_scope("host", db_path=str(db))
        assert guard.scope is ClaimScope.HOST
        assert db.exists()

    def test_unknown_scope_is_an_error_not_a_fallback(self):
        with pytest.raises(ValueError, match="unknown workflow claim scope"):
            InstanceGuard.from_scope("cluster")

    @pytest.mark.parametrize("kwargs", [
        {"ttl_s": 0}, {"ttl_s": -1}, {"ttl_s": 1.0, "renew_interval_s": 1.0},
        {"ttl_s": 1.0, "renew_interval_s": 0},
    ])
    def test_invalid_timing_is_refused(self, kwargs):
        with pytest.raises(ValueError):
            InstanceGuard(**kwargs)


# ── The durable store ────────────────────────────────────────────────────────


class TestSqliteClaimStore:

    async def test_acquire_conflict_and_holder_details(self, tmp_path):
        clock = _Clock()
        a = SqliteClaimStore(str(tmp_path / "c.db"), clock=clock)
        b = SqliteClaimStore(str(tmp_path / "c.db"), clock=clock)  # a second "process"
        assert await a.acquire("i", holder_id="A", operation="execute", ttl_s=10) is None
        held = await b.acquire("i", holder_id="B", operation="resume", ttl_s=10)
        assert isinstance(held, ClaimInfo)
        assert (held.holder_id, held.operation, held.pid) == ("A", "execute", os.getpid())
        assert held.lease_expires_at == pytest.approx(clock.now + 10)

    async def test_expired_lease_can_be_taken_and_the_old_holder_cannot_interfere(self, tmp_path):
        clock = _Clock()
        store = SqliteClaimStore(str(tmp_path / "c.db"), clock=clock)
        assert await store.acquire("i", holder_id="old", operation="execute", ttl_s=10) is None
        clock.advance(10.5)  # the old holder crashed: nobody renewed
        assert await store.acquire("i", holder_id="new", operation="resume", ttl_s=10) is None
        assert await store.renew("i", holder_id="old", ttl_s=10) is False  # stale holder is told so
        await store.release("i", holder_id="old")  # ... and cannot free the new holder's claim
        held = await store.acquire("i", holder_id="third", operation="resume", ttl_s=10)
        assert held is not None and held.holder_id == "new"

    async def test_renew_extends_and_release_frees(self, tmp_path):
        clock = _Clock()
        store = SqliteClaimStore(str(tmp_path / "c.db"), clock=clock)
        await store.acquire("i", holder_id="A", operation="execute", ttl_s=10)
        clock.advance(8)
        assert await store.renew("i", holder_id="A", ttl_s=10) is True
        clock.advance(8)  # past the original expiry, inside the renewed one
        assert (await store.acquire("i", holder_id="B", operation="resume", ttl_s=10)) is not None
        await store.release("i", holder_id="A")
        assert await store.acquire("i", holder_id="B", operation="resume", ttl_s=10) is None

    async def test_expired_rows_are_purged_not_accumulated(self, tmp_path):
        clock = _Clock()
        db = tmp_path / "c.db"
        store = SqliteClaimStore(str(db), clock=clock)
        for i in range(25):
            await store.acquire(f"crashed-{i}", holder_id="x", operation="execute", ttl_s=5)
        assert _claim_rows(db) == 25
        clock.advance(6)
        await store.acquire("fresh", holder_id="y", operation="execute", ttl_s=5)
        assert _claim_rows(db) == 1

    async def test_concurrent_acquire_has_exactly_one_winner(self, tmp_path):
        db = str(tmp_path / "c.db")
        stores = [SqliteClaimStore(db) for _ in range(16)]
        results = await asyncio.gather(*[
            s.acquire("i", holder_id=f"h{n}", operation="resume", ttl_s=30)
            for n, s in enumerate(stores)
        ])
        assert sum(1 for r in results if r is None) == 1


# ── Guard + store ────────────────────────────────────────────────────────────


class TestGuardHostScope:

    async def test_second_guard_on_the_same_file_is_rejected_with_holder_details(self, tmp_path):
        db = str(tmp_path / "c.db")
        first = InstanceGuard(SqliteClaimStore(db))
        second = InstanceGuard(SqliteClaimStore(db))  # models a second process
        async with first.claim("inst-1", operation="execute"):
            with pytest.raises(InstanceBusyError) as err:
                await _enter(second, "inst-1", "resume")
        assert err.value.scope is ClaimScope.HOST
        assert err.value.holder is not None and err.value.holder.operation == "execute"
        assert second.active_count == 0  # the loser leaves nothing behind
        await _enter(second, "inst-1", "resume")  # released -> free

    async def test_store_failure_fails_closed_and_leaves_nothing_behind(self):
        guard = InstanceGuard(_ScriptedStore(acquire_exc=OSError("disk I/O error")))
        with pytest.raises(ClaimUnavailableError, match="disk I/O error"):
            await _enter(guard, "inst-1", "resume")
        assert guard.active_count == 0

    async def test_heartbeat_keeps_the_lease_alive_beyond_its_ttl(self, tmp_path):
        db = str(tmp_path / "c.db")
        guard = InstanceGuard(SqliteClaimStore(db), ttl_s=0.6, renew_interval_s=0.15)
        probe = SqliteClaimStore(db)
        async with guard.claim("inst-1", operation="resume"):
            await asyncio.sleep(1.3)  # > 2x ttl: only renewals can explain a live lease
            assert await probe.acquire("inst-1", holder_id="p", operation="p", ttl_s=5) is not None
        assert await probe.acquire("inst-1", holder_id="p", operation="p", ttl_s=5) is None

    async def test_lost_claim_invokes_on_lost(self):
        store = _ScriptedStore(renew_results=[False])
        guard = InstanceGuard(store, ttl_s=0.6, renew_interval_s=0.05)
        lost = asyncio.Event()

        async def on_lost() -> None:
            lost.set()

        async with guard.claim("inst-1", operation="execute", on_lost=on_lost):
            await asyncio.wait_for(lost.wait(), timeout=2.0)
        assert store.released == [("inst-1", store.acquired[0][1])]

    async def test_transient_renew_error_is_not_a_lost_claim(self):
        store = _ScriptedStore(renew_results=[OSError("busy"), True, True])
        guard = InstanceGuard(store, ttl_s=5.0, renew_interval_s=0.05)
        lost: list = []
        async with guard.claim("inst-1", operation="execute", on_lost=lambda: lost.append(1)):
            await asyncio.sleep(0.3)
        assert store.renew_calls >= 3 and lost == []

    async def test_cancel_during_acquire_still_releases_a_possibly_committed_claim(self):
        class SlowAcquire(_ScriptedStore):
            async def acquire(self, instance_id, *, holder_id, operation, ttl_s):
                self.acquired.append((instance_id, holder_id))  # "committed" in the worker thread
                await asyncio.sleep(30)

        store = SlowAcquire()
        guard = InstanceGuard(store)
        task = asyncio.create_task(_enter(guard, "inst-1", "resume"))
        await asyncio.sleep(0.05)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.1)
        assert store.released == [("inst-1", store.acquired[0][1])]
        assert guard.active_count == 0


# ── Through the real WorkflowRuntime ─────────────────────────────────────────


class TestRuntimeIntegration:

    async def test_without_the_guard_the_race_is_real(self, tmp_path):
        """DEBT-028, reproduced: with the pre-fix behaviour, N concurrent resumes
        of one instance all re-run the pending node."""
        GateWorker.reset()
        runtime = _runtime(tmp_path, GateWorker, guard=_NoGuard())
        await _seed_pending_checkpoint(runtime, "inst-race")
        tasks = [asyncio.create_task(runtime.resume(_definition("GateWorker"), "inst-race"))
                 for _ in range(5)]
        await asyncio.sleep(0.3)
        GateWorker.gate.set()
        await asyncio.gather(*tasks)
        assert len(GateWorker.invocations) == 5

    async def test_concurrent_resumes_run_the_node_exactly_once(self, tmp_path):
        GateWorker.reset()
        runtime = _runtime(tmp_path, GateWorker)
        events = _record_events(runtime)
        await _seed_pending_checkpoint(runtime, "inst-race")
        tasks = [asyncio.create_task(runtime.resume(_definition("GateWorker"), "inst-race"))
                 for _ in range(8)]
        try:
            await asyncio.sleep(0.3)  # one is inside the node; the other seven were refused at once
            assert len(GateWorker.invocations) == 1
        finally:
            GateWorker.gate.set()  # a failing assertion must not leave tasks blocked
        results = await asyncio.gather(*tasks)

        winners = [r for r in results if r.success]
        refused = [r for r in results if not r.success]
        assert len(winners) == 1 and len(refused) == 7
        assert all(r.metadata["claim_failure"] == "instance_busy" for r in refused)
        assert all(r.instance_id == "inst-race" for r in refused)
        assert len(GateWorker.invocations) == 1
        rejected = [p for (t, p) in events if t == "workflow.instance_claim_rejected"]
        assert len(rejected) == 7 and rejected[0]["reason"] == "instance_busy"
        # the claim is released afterwards: a later resume is allowed (and re-runs nothing)
        again = await runtime.resume(_definition("GateWorker"), "inst-race")
        assert again.success and len(GateWorker.invocations) == 1

    async def test_resume_is_refused_while_the_original_execute_is_still_running(self, tmp_path):
        GateWorker.reset()
        runtime = _runtime(tmp_path, GateWorker)
        running = asyncio.create_task(runtime.execute(_definition("GateWorker"), query="q"))
        await asyncio.sleep(0.2)
        (instance_id,) = list(runtime._instance_guard._active)  # the one in-flight execute
        await _seed_pending_checkpoint(runtime, instance_id)
        try:
            # bounded: an unguarded resume would block on the gate and hang this test
            duplicate = await asyncio.wait_for(
                runtime.resume(_definition("GateWorker"), instance_id), timeout=5)
            assert duplicate.success is False
            assert duplicate.metadata["claim_failure"] == "instance_busy"
        finally:
            GateWorker.gate.set()
        assert (await running).success is True
        assert len(GateWorker.invocations) == 1

    async def test_independent_executes_never_contend(self, tmp_path):
        GateWorker.reset()
        GateWorker.gate = None
        runtime = _runtime(tmp_path, GateWorker)
        results = await asyncio.gather(*[
            runtime.execute(_definition("GateWorker"), query=f"q{i}") for i in range(20)
        ])
        assert all(r.success for r in results)
        assert len({r.instance_id for r in results}) == 20
        assert runtime._instance_guard.active_count == 0

    async def test_host_scope_execute_runs_and_leaves_no_claim_behind(self, tmp_path):
        GateWorker.reset()
        GateWorker.gate = None
        db = tmp_path / "claims.db"
        runtime = _runtime(tmp_path, GateWorker, guard=InstanceGuard(SqliteClaimStore(str(db))))
        result = await runtime.execute(_definition("GateWorker"), query="q")
        assert result.success is True
        assert _claim_rows(db) == 0

    async def test_host_scope_fails_closed_without_running_the_node(self, tmp_path):
        GateWorker.reset()
        GateWorker.gate = None
        runtime = _runtime(tmp_path, GateWorker,
                           guard=InstanceGuard(_ScriptedStore(acquire_exc=OSError("locked"))))
        events = _record_events(runtime)
        result = await runtime.execute(_definition("GateWorker"), query="q")
        assert result.success is False
        assert result.metadata["claim_failure"] == "claim_unavailable"
        assert GateWorker.invocations == []
        assert [p["reason"] for (t, p) in events if t == "workflow.instance_claim_rejected"] \
            == ["claim_unavailable"]

    async def test_a_lost_claim_cancels_the_running_workflow(self, tmp_path):
        store = _ScriptedStore(renew_results=[False])
        runtime = _runtime(tmp_path, WaitForCancelWorker,
                           guard=InstanceGuard(store, ttl_s=0.6, renew_interval_s=0.05))
        events = _record_events(runtime)
        result = await asyncio.wait_for(
            runtime.execute(_definition("WaitForCancelWorker"), query="q"), timeout=10)
        assert result.success is False  # cancelled, NOT "ran to completion"
        assert "ran to completion" not in str(result.output)
        lost = [p for (t, p) in events if t == "workflow.instance_claim_lost"]
        assert len(lost) == 1 and lost[0]["scope"] == "host"


# ── Two real processes ───────────────────────────────────────────────────────


class TestCrossProcess:

    async def test_claim_held_by_another_process_blocks_survives_renewal_and_dies_with_it(self, tmp_path):
        db = str(tmp_path / "claims.db")
        ttl = 1.5
        child = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "tests" / "_instance_claim_child.py"),
             str(REPO_ROOT), db, "inst-xproc", str(ttl)],
            stdout=subprocess.PIPE, text=True,
        )
        watchdog = threading.Timer(60, child.kill)  # never let a broken child hang the suite
        watchdog.start()
        try:
            assert child.stdout.readline().strip() == "CLAIMED"
            parent = InstanceGuard(SqliteClaimStore(db), ttl_s=ttl)

            with pytest.raises(InstanceBusyError) as err:
                await _enter(parent, "inst-xproc", "resume")
            assert err.value.scope is ClaimScope.HOST
            assert err.value.holder.pid == child.pid  # refused because of the OTHER process

            await asyncio.sleep(ttl * 1.6)  # past the lease: only the child's heartbeat keeps it live
            with pytest.raises(InstanceBusyError):
                await _enter(parent, "inst-xproc", "resume")

            child.kill()  # hard kill: no cleanup, no release
            child.wait(timeout=10)
            deadline = time.monotonic() + ttl + 5
            while True:
                try:
                    await _enter(parent, "inst-xproc", "resume")
                    break
                except InstanceBusyError:
                    assert time.monotonic() < deadline, "lease of a killed holder never expired"
                    await asyncio.sleep(0.1)
        finally:
            watchdog.cancel()
            if child.poll() is None:
                child.kill()
            child.stdout.close()
