"""Probe batch A -- read-only experiments against a THROWAWAY COPY of ocbrain-v4.1 @ ed3d141.

Nothing here writes to the study checkout. All EventStream DBs live in temp dirs.
Run:  /tmp/probe/v311/bin/python /tmp/probe/probes_a.py [probe-name ...]
"""
import asyncio
import json
import os
import sys
import tempfile
import time

ROOT = os.environ.get("OCROOT", "/tmp/probe/repo")
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from core.events.event_stream import EventStream, SQLiteEventStore
from core.governance.governance_kernel import get_governance_kernel
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_context import ExecutionContext
from core.runtime.execution_graph import ExecutionGraph, execution_registry
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.progress import ProgressMonitor
from core.runtime.watchdog import GraphExecutionWatchdog
from core.runtime.worker_registry import WorkerRegistry
from core.workers.base import AbstractCognitiveWorker, WorkerResult
from core.workflow.definition import RetryPolicy, WorkflowDefinition, WorkflowNode
from core.workflow.runtime import WorkflowRuntime


class DelayStream(EventStream):
    """EventStream whose append() sleeps BEFORE persisting for chosen event types."""

    def __init__(self, store, delays=None):
        super().__init__(store)
        self.delays = delays or {}

    async def append(self, event_type, **kw):
        d = self.delays.get(event_type)
        if d:
            await asyncio.sleep(d)
        return await super().append(event_type, **kw)


def mk_stream(delays=None):
    d = tempfile.mkdtemp(prefix="ocprobe_")
    return DelayStream(SQLiteEventStore(db_path=os.path.join(d, "s.db")), delays)


async def event_types(stream, prefixes=("worker.", "execution.", "workflow.")):
    evs = await stream.query(limit=1000)
    out = [e for e in reversed(evs) if e.event_type.startswith(prefixes)]
    return [(e.event_type, {k: v for k, v in e.payload.items()
                            if k in ("success", "status", "node_id", "error", "summary")}) for e in out]


class Sleeper(AbstractCognitiveWorker):
    """Ignores the cancellation token; sleeps `dur` seconds then succeeds."""
    worker_type = "Sleeper"
    runs = 0
    dur = 2.0

    async def _run(self, context):
        type(self).runs += 1
        await asyncio.sleep(type(self).dur)
        return WorkerResult(success=True, output="slept-complete")


class Quick(AbstractCognitiveWorker):
    worker_type = "Quick"

    async def _run(self, context):
        return WorkerResult(success=True, output="quick-complete")


class Coop(AbstractCognitiveWorker):
    """Cooperative: polls the token every 50 ms and returns an ordinary failed result."""
    worker_type = "Coop"
    runs = 0

    async def _run(self, context):
        type(self).runs += 1
        for _ in range(100):
            if context.cancellation_token.is_cancelled:
                return WorkerResult(success=False, error="Cancelled (cooperative)")
            await asyncio.sleep(0.05)
        return WorkerResult(success=True, output="coop-finished")


class Recovery(AbstractCognitiveWorker):
    worker_type = "Recovery"
    runs = 0

    async def _run(self, context):
        type(self).runs += 1
        return WorkerResult(success=True, output="recovered")


def mk_wf(stream, *classes):
    reg = WorkerRegistry()
    for c in classes:
        reg.register(c)
    er = ExecutionRuntime(worker_registry=reg, governance=get_governance_kernel(), event_stream=stream)
    return WorkflowRuntime(execution_runtime=er, event_stream=stream), er


def one_node(wid, wtype, retry=None, error_branch=""):
    return WorkflowDefinition(
        workflow_id=wid, name=wid,
        nodes=[WorkflowNode(node_id="n", worker_type=wtype,
                            retry_policy=retry or RetryPolicy(max_retries=0), error_branch=error_branch)],
        entry_node="n",
    )


def leaked_watchdogs():
    return [t for t in asyncio.all_tasks() if "GraphExecutionWatchdog" in repr(t.get_coro()) and not t.done()]


async def cancel_and_observe(task, after):
    await asyncio.sleep(after)
    task.cancel()
    try:
        r = await task
        return {"how": "returned", "value_type": type(r).__name__,
                "success": getattr(r, "success", None), "error": getattr(r, "error", None),
                "task_cancelled": task.cancelled(), "cancelling": task.cancelling()}
    except asyncio.CancelledError:
        return {"how": "raised CancelledError", "task_cancelled": task.cancelled(), "cancelling": task.cancelling()}


# ───────────────────────────── probes ─────────────────────────────

async def p1_h1_workflow_retry_after_native_cancel():
    """H1/H8: cancel the task running WorkflowRuntime.execute() mid-node; node retry policy max_retries=1."""
    stream = mk_stream()
    rt, _ = mk_wf(stream, Sleeper)
    Sleeper.runs, Sleeper.dur = 0, 2.0
    d = one_node("p1", "Sleeper", RetryPolicy(max_retries=1, backoff_seconds=0.1))
    t0 = time.monotonic()
    task = asyncio.create_task(rt.execute(d, query="q"))
    obs = await cancel_and_observe(task, 0.3)
    obs["elapsed_s"] = round(time.monotonic() - t0, 2)
    obs["node_executions"] = Sleeper.runs
    obs["events"] = [e[0] for e in await event_types(stream)]
    return obs


async def p2_h2_cancel_during_worker_started_emit():
    stream = mk_stream({"worker.started": 1.0})
    w = Sleeper(governance=get_governance_kernel(), event_stream=stream)
    ctx = ExecutionContext(metadata={"query": "q"})
    task = asyncio.create_task(w.execute(ctx))
    obs = await cancel_and_observe(task, 0.2)
    obs.update(worker_state=w.state.value, total_failures=w.stats()["total_failures"],
               events=[e[0] for e in await event_types(stream)])
    return obs


async def p3_h3_cancel_during_worker_completed_emit():
    stream = mk_stream({"worker.completed": 1.0})
    w = Quick(governance=get_governance_kernel(), event_stream=stream)
    ctx = ExecutionContext(metadata={"query": "q"})
    task = asyncio.create_task(w.execute(ctx))
    obs = await cancel_and_observe(task, 0.3)
    obs.update(worker_state=w.state.value, total_failures=w.stats()["total_failures"],
               events=[e[0] for e in await event_types(stream)],
               note="_run() had already returned success=True before the cancel arrived")
    return obs


async def p4_h4_runtime_cleanup_on_escaping_cancel():
    """Cancel while worker.started is being emitted (CancelledError escapes Worker.execute)."""
    out = {}
    for label, delays, cancel_at in (("escaping_cancel(during worker.started)", {"worker.started": 1.0}, 0.2),
                                     ("cancel_during__run", {}, 0.3)):
        stream = mk_stream(delays)
        reg = WorkerRegistry(); reg.register(Sleeper)
        Sleeper.dur = 2.0
        er = ExecutionRuntime(worker_registry=reg, governance=get_governance_kernel(), event_stream=stream)
        ctx = ExecutionContext(metadata={"query": "q"})
        ctx.working_memory.set("scratch", "present")
        task = asyncio.create_task(er.invoke("Sleeper", context=ctx))
        obs = await cancel_and_observe(task, cancel_at)
        obs["working_memory_after"] = ctx.working_memory.get("scratch", "<cleared>")
        obs["runtime_event_emitted"] = any(e[0] == "execution.completed" for e in await event_types(stream))
        out[label] = obs
    return out


async def p5_second_cancel_during_cancelled_event():
    """Two cancels: one during _run, a second while worker.cancelled is being emitted."""
    stream = mk_stream({"worker.cancelled": 1.0})
    reg = WorkerRegistry(); reg.register(Sleeper)
    Sleeper.dur = 2.0
    er = ExecutionRuntime(worker_registry=reg, governance=get_governance_kernel(), event_stream=stream)
    ctx = ExecutionContext(metadata={"query": "q"})
    ctx.working_memory.set("scratch", "present")
    task = asyncio.create_task(er.invoke("Sleeper", context=ctx))
    await asyncio.sleep(0.3)
    task.cancel()
    await asyncio.sleep(0.3)   # now inside the (slow) worker.cancelled emission
    task.cancel()
    try:
        r = await task
        obs = {"how": "returned", "success": r.success, "error": r.error}
    except asyncio.CancelledError:
        obs = {"how": "raised CancelledError"}
    obs["working_memory_after"] = ctx.working_memory.get("scratch", "<cleared>")
    obs["events"] = [e[0] for e in await event_types(stream)]
    return obs


async def p6_h5_workflow_watchdog_lifetime():
    out = {}
    for label, delays, at in (("cancel_during_workflow.started", {"workflow.started": 1.0}, 0.3),
                              ("cancel_during_execution.completed(terminal event)", {"execution.completed": 1.0}, 0.4)):
        stream = mk_stream(delays)
        rt, _ = mk_wf(stream, Quick)
        d = one_node("p6", "Quick")
        exec_id = f"p6-{abs(hash(label)) % 10**6}"
        task = asyncio.create_task(rt.execute(d, query="q", metadata={"execution_id": exec_id}))
        obs = await cancel_and_observe(task, at)
        await asyncio.sleep(0.2)
        leaked = leaked_watchdogs()
        g = execution_registry.get(exec_id)
        snap = await g.snapshot()
        root = [n for n in snap["nodes"] if n["node_id"] == snap["root_id"]][0]
        obs.update(leaked_watchdog_tasks=len(leaked), graph_root_status=root["status"],
                   terminal_events=[e[0] for e in await event_types(stream) if e[0] in ("execution.completed", "execution.failed", "execution.cancelled")])
        for t in leaked:
            t.cancel()
        out[label] = obs
    return out


async def p7_h6_watchdog_stop_swallows_caller_cancel():
    stream = mk_stream()
    g = ExecutionGraph("p7")
    wd = GraphExecutionWatchdog(g, WorkflowRuntime.default_budget_for("q"), CancellationToken(), ProgressMonitor(g, stream))

    async def slow_cleanup_child():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            await asyncio.sleep(0.5)      # cleanup that takes a while, then honours the cancel
            raise

    wd._task = asyncio.create_task(slow_cleanup_child())
    await asyncio.sleep(0)

    async def caller():
        await wd.stop()
        return "stop() returned normally; caller continues running"

    ct = asyncio.create_task(caller())
    await asyncio.sleep(0.1)
    ct.cancel()
    try:
        r = await ct
        return {"how": "returned", "value": r, "caller_task_cancelled": ct.cancelled(), "cancelling": ct.cancelling(),
                "watchdog_task_cleared": wd._task is None}
    except asyncio.CancelledError:
        return {"how": "raised CancelledError (correct)", "caller_task_cancelled": ct.cancelled()}


async def p8_h7_graph_failed_before_termination():
    """Graph watchdog hard deadline + a worker that ignores the token and later succeeds."""
    stream = mk_stream()
    rt, _ = mk_wf(stream, Sleeper)
    Sleeper.runs, Sleeper.dur = 0, 2.6
    budget = ExecutionBudget(startup_deadline_s=10.0, progress_deadline_s=45.0, hard_ceiling_s=0.4,
                             absolute_ceiling_s=0.5, max_extension_s=0.1)
    d = one_node("p8", "Sleeper")
    exec_id = "p8-exec"
    t0 = time.monotonic()
    res = await rt.execute(d, query="q", metadata={"execution_id": exec_id, "execution_budget": budget})
    g = execution_registry.get(exec_id)
    snap = await g.snapshot()
    node = [n for n in snap["nodes"] if n["node_id"] == "n"][0]
    root = [n for n in snap["nodes"] if n["node_id"] == snap["root_id"]][0]
    return {"elapsed_s": round(time.monotonic() - t0, 2), "workflow_success": res.success, "workflow_error": res.error,
            "worker_ran_to_completion": Sleeper.runs == 1, "node_status_final": node["status"], "node_failure_type": node["failure_type"],
            "root_status_final": root["status"],
            "execution_events": [e for e in await event_types(stream, ("execution.",))]}


async def p9_h9_token_cancel_retry_and_error_branch():
    """Token cancelled mid-node; cooperative worker returns an ordinary failure; retry policy + error_branch present."""
    stream = mk_stream()
    rt, _ = mk_wf(stream, Coop, Recovery)
    Coop.runs, Recovery.runs = 0, 0
    d = WorkflowDefinition(
        workflow_id="p9", name="p9",
        nodes=[WorkflowNode(node_id="n", worker_type="Coop", error_branch="rec",
                            retry_policy=RetryPolicy(max_retries=2, backoff_seconds=1.5, backoff_multiplier=1.0, max_backoff_seconds=1.5)),
               WorkflowNode(node_id="rec", worker_type="Recovery")],
        entry_node="n",
    )
    tok = CancellationToken()
    t0 = time.monotonic()

    async def fire():
        await asyncio.sleep(0.3)
        tok.cancel("user-stop")
    asyncio.create_task(fire())
    res = await rt.execute(d, query="q", cancellation_token=tok, metadata={"execution_id": "p9-exec"})
    return {"elapsed_s": round(time.monotonic() - t0, 2), "success": res.success, "error": res.error,
            "coop_worker_executions": Coop.runs, "recovery_executions": Recovery.runs,
            "node_results": {k: (v.success, v.error) for k, v in res.node_results.items()},
            "execution_events": [e for e in await event_types(stream, ("execution.",)) if e[0] != "execution.completed" or True]}


PROBES = {k[:k.index("_")] + k[k.index("_"):]: v for k, v in globals().items() if k.startswith("p") and k[1].isdigit() and asyncio.iscoroutinefunction(v)}


async def main(names):
    for name, fn in PROBES.items():
        if names and not any(name.startswith(n) for n in names):
            continue
        try:
            r = await asyncio.wait_for(fn(), timeout=30)
        except Exception as e:  # report, do not hide
            r = {"PROBE_ERROR": f"{type(e).__name__}: {e}"}
        print(f"=== {name} ===")
        print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    print("python", sys.version.split()[0], "| repo", ROOT)
    asyncio.run(main(sys.argv[1:]))
