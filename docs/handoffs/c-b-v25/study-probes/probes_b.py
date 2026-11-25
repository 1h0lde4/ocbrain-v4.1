"""Probe batch B -- see probes_a.py header. Python 3.11 against a throwaway copy of ocbrain-v4.1 @ ed3d141."""
import asyncio
import json
import os
import sys
import threading
import time
import types

sys.argv_saved = list(sys.argv)
import probes_a as A  # noqa: E402  (re-uses harness; chdir + sys.path already done)
from core.runtime.cancellation import CancellationToken  # noqa: E402
from core.runtime.execution_context import ExecutionContext  # noqa: E402
from core.runtime.execution_graph import execution_registry  # noqa: E402
from core.governance.governance_kernel import get_governance_kernel  # noqa: E402
from core.workflow.definition import RetryPolicy, WorkflowDefinition, WorkflowNode  # noqa: E402
from core.workers.base import WorkerResult  # noqa: E402


class SourceDelayStream(A.DelayStream):
    """Delay keyed by (event_type, source) so the workflow-level terminal event can be targeted."""

    async def append(self, event_type, *, source="", **kw):
        d = self.delays.get((event_type, source))
        if d:
            await asyncio.sleep(d)
        return await super(A.DelayStream, self).append(event_type, source=source, **kw)


def mk_src_stream(delays):
    s = A.mk_stream()
    return SourceDelayStream(s._store, delays)


async def p6b_cancel_during_workflow_terminal_event():
    stream = mk_src_stream({("execution.completed", "WorkflowRuntime"): 1.0})
    rt, _ = A.mk_wf(stream, A.Quick)
    d = A.one_node("p6b", "Quick")
    task = asyncio.create_task(rt.execute(d, query="q", metadata={"execution_id": "p6b-exec"}))
    obs = await A.cancel_and_observe(task, 0.4)
    await asyncio.sleep(0.2)
    leaked = A.leaked_watchdogs()
    g = execution_registry.get("p6b-exec")
    snap = await g.snapshot()
    root = [n for n in snap["nodes"] if n["node_id"] == snap["root_id"]][0]
    node = [n for n in snap["nodes"] if n["node_id"] == "n"][0]
    obs.update(leaked_watchdog_tasks=len(leaked), graph_root_status=root["status"], node_status=node["status"],
               workflow_level_terminal_events=[e[0] for e in await A.event_types(stream)
                                               if e[0] in ("execution.failed", "execution.cancelled")]
               + [x for x in ["execution.completed(WorkflowRuntime)"] if False])
    for t in leaked:
        t.cancel()
    return obs


async def p10_native_cancel_enters_error_branch():
    stream = A.mk_stream()
    rt, _ = A.mk_wf(stream, A.Sleeper, A.Recovery)
    A.Sleeper.runs, A.Sleeper.dur, A.Recovery.runs = 0, 2.0, 0
    d = WorkflowDefinition(
        workflow_id="p10", name="p10",
        nodes=[WorkflowNode(node_id="n", worker_type="Sleeper", error_branch="rec", retry_policy=RetryPolicy(max_retries=0)),
               WorkflowNode(node_id="rec", worker_type="Recovery")], entry_node="n")
    task = asyncio.create_task(rt.execute(d, query="q"))
    obs = await A.cancel_and_observe(task, 0.3)
    obs.update(sleeper_executions=A.Sleeper.runs, recovery_executions=A.Recovery.runs)
    return obs


# ── Planner / gather ────────────────────────────────────────────────────────

async def p11_planner_gather_child_vs_parent_cancel():
    sys.modules["core.classifier_v3"] = types.SimpleNamespace(
        classify=lambda q, top_k=2: [{"module": "alpha"}, {"module": "beta"}])

    async def _assemble(q):
        return ""
    sys.modules["core.memory.assembly"] = types.SimpleNamespace(
        context_assembler=types.SimpleNamespace(assemble_context=_assemble))
    from core.model_router import RouteResult
    from core.workers.planner import PlannerWorker
    stream = A.mk_stream()
    out = {}

    async def run(kind):
        w = PlannerWorker(governance=get_governance_kernel(), event_stream=stream, modules={'alpha': object(), 'beta': object()})
        started = {"alpha": False, "beta": False}
        finished = {"alpha": False, "beta": False}

        async def dispatch(mod, query, context):
            started[mod] = True
            if kind == "child_cancelled" and mod == "alpha":
                raise asyncio.CancelledError()            # an independently cancelled child
            await asyncio.sleep(1.0 if kind == "parent_cancelled" else 0.1)
            finished[mod] = True          # only reached if NOT cancelled
            return RouteResult(answer=f"answer-from-{mod}", source="external")
        w._dispatch_module = dispatch
        ctx = ExecutionContext(metadata={"query": "q"})
        task = asyncio.create_task(w._run(ctx))
        if kind == "parent_cancelled":
            await asyncio.sleep(0.2)
            task.cancel()
        try:
            r = await task
            return {"how": "returned", "success": r.success, "output": r.output, "error": r.error}
        except asyncio.CancelledError:
            await asyncio.sleep(1.2)
            return {"how": "raised CancelledError", "children_ran_to_completion_after_parent_cancel": finished}

    for kind in ("child_cancelled", "parent_cancelled"):
        out[kind] = await run(kind)
    return out


async def p11b_gather_semantics_isolated():
    """Pure-asyncio statement of the gather(return_exceptions=True) behaviour PlannerWorker relies on."""
    async def child_cancel():
        raise asyncio.CancelledError()

    async def ok():
        return "ok"
    res = await asyncio.gather(child_cancel(), ok(), return_exceptions=True)
    return {"results": [repr(r) for r in res], "isinstance_Exception": [isinstance(r, Exception) for r in res],
            "isinstance_BaseException": [isinstance(r, BaseException) for r in res]}


# ── CancellationToken thread-safety (H16) ───────────────────────────────────

async def p12_token_cancel_from_other_thread():
    out = {}
    for label, debug in (("normal", False), ("asyncio_debug", True)):
        loop = asyncio.get_running_loop()
        loop.set_debug(debug)
        tok = CancellationToken()
        t0 = time.monotonic()
        waiter = asyncio.create_task(tok.wait(timeout=3.0))
        await asyncio.sleep(0.05)
        err = {}

        def other_thread():
            try:
                time.sleep(0.3)   # loop is idle (selecting) when the foreign thread cancels
                tok.cancel("from-thread")
            except BaseException as e:
                err["e"] = f"{type(e).__name__}: {e}"
        th = threading.Thread(target=other_thread)
        th.start()
        try:
            got = await asyncio.wait_for(asyncio.shield(waiter), timeout=8.0)
            woke = round(time.monotonic() - t0, 2)
        except asyncio.TimeoutError:
            got, woke = "NO WAKEUP within 8s (waiter never resumed)", None
            waiter.cancel()
        out[label] = {"wait_returned": got, "woke_after_s": woke,
                      "is_cancelled_flag": tok.is_cancelled, "exception_in_thread": err.get("e")}
        loop.set_debug(False)
    return out


# ── Voice callback (H17) ────────────────────────────────────────────────────

async def p13_voice_callback_from_non_loop_thread():
    async def handle(q):
        return f"handled {q}"
    res = {}

    def _handle_voice(q):                      # verbatim body of main.py:442-443
        asyncio.create_task(handle(q))

    def cb_thread():
        try:
            _handle_voice("hello")
            res["outcome"] = "scheduled (no error)"
        except BaseException as e:
            res["outcome"] = f"{type(e).__name__}: {e}"
    th = threading.Thread(target=cb_thread, name="keyboard-listener-sim")
    th.start(); th.join()
    # control: same call on the loop thread works
    ctl = {}
    try:
        _handle_voice("hello")
        ctl["outcome"] = "scheduled (no error)"
    except BaseException as e:
        ctl["outcome"] = f"{type(e).__name__}: {e}"
    await asyncio.sleep(0.05)
    return {"called_from_non_loop_thread": res, "control_called_on_loop_thread": ctl}


# ── EventStream cancelled mid-persist ───────────────────────────────────────

async def p15_eventstream_cancel_mid_append():
    import sqlite3
    from core.events import event_stream as es
    stream = A.mk_stream()
    seen = []
    stream.subscribe("*", lambda e: seen.append(e.event_type))
    orig = stream._store._append_sync

    def slow_append(event):
        time.sleep(0.6)                      # the executor thread is busy persisting
        return orig(event)
    stream._store._append_sync = slow_append
    task = asyncio.create_task(stream.append("probe.event", source="p15", payload={"k": 1}))
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
        how = "returned"
    except asyncio.CancelledError:
        how = "raised CancelledError"
    await asyncio.sleep(1.0)
    stream._store._append_sync = orig
    rows = await stream.query(event_type="probe.event")
    return {"awaiter": how, "persisted_rows": len(rows), "subscribers_notified": seen}


PROBES = {k: v for k, v in globals().items() if k.startswith("p") and k[1:2].isdigit() and asyncio.iscoroutinefunction(v)}


async def main(names):
    for name, fn in PROBES.items():
        if names and not any(name.startswith(n) for n in names):
            continue
        try:
            r = await asyncio.wait_for(fn(), timeout=40)
        except Exception as e:
            r = {"PROBE_ERROR": f"{type(e).__name__}: {e}"}
        print(f"=== {name} ===")
        print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    names = [a for a in sys.argv[1:]]
    sys.argv = sys.argv[:1]
    print("python", sys.version.split()[0])
    asyncio.run(main(names))
