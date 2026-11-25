"""Probe batch C -- real uvicorn server (in-process) serving interface.api.app (ed3d141, throwaway copy), Python 3.11."""
import asyncio
import json
import os
import socket
import sys
import time
import types

import probes_a as A
from core.runtime.execution_graph import execution_registry

import uvicorn
import interface.api as api


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Server:
    def __init__(self, **cfg):
        self.port = free_port()
        self.server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=self.port,
                                                    log_level="warning", loop="asyncio", **cfg))
        self.task = None

    async def start(self):
        self.task = asyncio.create_task(self.server.serve())
        for _ in range(100):
            if self.server.started:
                return
            await asyncio.sleep(0.05)
        raise RuntimeError("server did not start")

    async def stop(self):
        self.server.should_exit = True
        t0 = time.monotonic()
        await asyncio.wait_for(self.task, timeout=20)
        return round(time.monotonic() - t0, 2)


async def raw_post(port, path, body):
    r, w = await asyncio.open_connection("127.0.0.1", port)
    data = json.dumps(body).encode()
    w.write(f"POST {path} HTTP/1.1\r\nHost: x\r\nX-OCBrain-Local: 1\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\n\r\n".encode() + data)
    await w.drain()
    return r, w


async def raw_get(port, path):
    r, w = await asyncio.open_connection("127.0.0.1", port)
    w.write(f"GET {path} HTTP/1.1\r\nHost: x\r\nAccept: text/event-stream\r\n\r\n".encode())
    await w.drain()
    return r, w


class FakeOrch:
    def __init__(self, dur=2.0):
        self.log, self.dur, self.context = [], dur, types.SimpleNamespace()

    async def handle(self, q, **kw):
        self.log.append("handle:start")
        try:
            await asyncio.sleep(self.dur)
            self.log.append("handle:COMPLETED (logical operation ran to the end)")
            return "answer"
        except asyncio.CancelledError:
            self.log.append("handle:CANCELLED")
            raise


async def c1_nonstream_query_client_disconnect():
    orch = FakeOrch(2.0)
    api._orchestrator = orch
    srv = Server(); await srv.start()
    r, w = await raw_post(srv.port, "/query", {"query": "hi", "stream": False})
    await asyncio.sleep(0.3)
    w.close()                                  # client goes away mid-request
    await asyncio.sleep(3.0)
    await srv.stop()
    return {"orchestrator_log": orch.log}


async def c2_sse_query_client_disconnect():
    log = []
    stream = A.mk_stream()
    execution_registry.attach_event_stream(stream)
    import core.events.event_stream as es
    es._event_stream = stream if hasattr(es, "_event_stream") else None  # best effort: same stream for API-side emits
    from core import classifier, decomposer
    from core.model_router import model_router

    async def fake_label(parsed, ctx, scope=""):
        return [{"module": "alpha"}]
    classifier.label = fake_label
    decomposer.build = lambda parsed, labels: [types.SimpleNamespace(module="alpha", subtask="x")]

    async def fake_stream(module, subtask, ctx, scope=""):
        log.append("provider-stream:start")
        try:
            for i in range(30):
                await asyncio.sleep(0.2)
                yield f"tok{i} "
            log.append("provider-stream:COMPLETED")
        except BaseException as e:
            log.append(f"provider-stream:{type(e).__name__}")
            raise
    model_router.stream_route = fake_stream
    api._orchestrator = FakeOrch()
    srv = Server(); await srv.start()
    r, w = await raw_post(srv.port, "/query", {"query": "hi", "stream": True, "execution_id": "c2-exec"})
    buf = b""
    while b"tok1" not in buf:
        buf += await asyncio.wait_for(r.read(300), timeout=5)
    first = buf
    w.close()
    await asyncio.sleep(2.0)
    await srv.stop()
    g = execution_registry.get("c2-exec")
    snap = await g.snapshot()
    nodes = {n["node_id"]: (n["title"], n["status"]) for n in snap["nodes"]}
    evs = [e[0] for e in await A.event_types(stream, ("execution.",))]
    return {"got_first_bytes": bool(first), "provider_log": log, "graph_nodes": nodes, "execution_events": evs}


async def c3_execution_events_terminal_gap():
    stream = A.mk_stream({"workflow.started": 1.0})
    execution_registry.create("c3-exec", title="probe")
    execution_registry.attach_event_stream(stream)
    api._orchestrator = FakeOrch()
    srv = Server(); await srv.start()
    r, w = await raw_get(srv.port, "/executions/c3-exec/events")
    got = []

    async def reader():
        buf = b""
        while True:
            chunk = await r.read(4096)
            if not chunk:
                got.append("<<stream closed by server>>"); return
            if chunk.endswith(b"0\r\n\r\n"):
                got.append("<<response ended (chunked terminator)>>")
            buf += chunk
            while b"\n\n" in buf:
                msg, buf = buf.split(b"\n\n", 1)
                if b"data:" in msg:
                    try:
                        got.append(json.loads(msg.split(b"data:", 1)[1].decode())["event_type"])
                    except Exception:
                        got.append("<unparsed>")
    rd = asyncio.create_task(reader())
    rt, _ = A.mk_wf(stream, A.Quick)
    task = asyncio.create_task(rt.execute(A.one_node("c3", "Quick"), query="q", metadata={"execution_id": "c3-exec"}))
    await A.cancel_and_observe(task, 0.4)            # CancelledError escapes WorkflowRuntime._run (see p6)
    await asyncio.sleep(3.0)
    still_open_without_terminal = not rd.done()
    snapshot_before = list(got)
    # control: the predicate itself works -- emitting a recognised terminal event ends the stream
    await stream.append("execution.cancelled", source="probe", payload={"execution_id": "c3-exec"})
    await asyncio.sleep(0.5)
    out = {"events_received_by_subscriber_before_manual_terminal": snapshot_before,
           "subscriber_still_waiting_3s_after_cancel": still_open_without_terminal,
           "after_manually_emitting_execution.cancelled": got[len(snapshot_before):], "reader_done_after_control": rd.done()}
    w.close(); rd.cancel()
    for t in A.leaked_watchdogs():
        t.cancel()
    await srv.stop()
    return out


async def c4_graceful_shutdown_with_inflight_request():
    orch = FakeOrch(5.0)
    api._orchestrator = orch
    srv = Server(); await srv.start()
    r, w = await raw_post(srv.port, "/query", {"query": "hi", "stream": False})
    await asyncio.sleep(0.4)
    took = await srv.stop()                     # same path as SIGTERM/SIGINT -> Server.should_exit; main.py sets no timeout_graceful_shutdown
    body = await asyncio.wait_for(r.read(400), timeout=2)
    return {"server_exit_took_s": took, "orchestrator_log": orch.log, "client_got_response": body[:60].decode(errors="replace")}


async def c4b_graceful_shutdown_with_timeout():
    orch = FakeOrch(5.0)
    api._orchestrator = orch
    srv = Server(timeout_graceful_shutdown=1); await srv.start()
    r, w = await raw_post(srv.port, "/query", {"query": "hi", "stream": False})
    await asyncio.sleep(0.4)
    took = await srv.stop()
    return {"server_exit_took_s": took, "orchestrator_log": orch.log}


async def c5_terminal_event_persisted_but_not_broadcast():
    """Reviewer point B: the terminal event is persisted but the emitter is cancelled before broadcast."""
    from core.runtime.execution_graph import ExecutionStatus
    from core.runtime.progress import ProgressMonitor
    stream = A.mk_stream()
    g = execution_registry.create("c5-exec", title="probe")
    execution_registry.attach_event_stream(stream)
    api._orchestrator = FakeOrch()
    srv = Server(); await srv.start()
    r, w = await raw_get(srv.port, "/executions/c5-exec/events")
    got = []

    async def reader():
        buf = b""
        while True:
            chunk = await r.read(4096)
            if not chunk:
                got.append("<<closed>>"); return
            if chunk.endswith(b"0\r\n\r\n"):
                got.append("<<response ended>>")
            buf += chunk
            while b"\n\n" in buf:
                msg, buf = buf.split(b"\n\n", 1)
                if b"data:" in msg:
                    try: got.append(json.loads(msg.split(b"data:", 1)[1].decode())["event_type"])
                    except Exception: got.append("<unparsed>")
    rd = asyncio.create_task(reader())
    # graph is finalised terminally (snapshot-visible) ...
    await ProgressMonitor(g, stream).record_status(g.root.node_id, ExecutionStatus.CANCELLED, summary="cancelled")
    await asyncio.sleep(0.3)
    got_before = list(got)
    # ... and the terminal event is persisted but the emitting task is cancelled before the broadcast
    orig = stream._store._append_sync
    def slow(event):
        time.sleep(0.6); return orig(event)
    stream._store._append_sync = slow
    t = asyncio.create_task(stream.append("execution.cancelled", source="probe", payload={"execution_id": "c5-exec"}))
    await asyncio.sleep(0.2); t.cancel()
    try: await t
    except asyncio.CancelledError: pass
    await asyncio.sleep(2.0)
    stream._store._append_sync = orig
    rows = await stream.query(event_type="execution.cancelled")
    snap = await g.snapshot()
    root = [n for n in snap["nodes"] if n["node_id"] == snap["root_id"]][0]
    out = {"graph_snapshot_root_status": root["status"], "terminal_event_persisted_rows": len(rows),
           "subscriber_saw_before": got_before, "subscriber_saw_total": list(got),
           "subscriber_terminated": rd.done() or "<<response ended>>" in got}
    w.close(); rd.cancel(); await srv.stop()
    return out


PROBES = {k: v for k, v in globals().items() if k[0] == "c" and k[1:2].isdigit() and asyncio.iscoroutinefunction(v)}


async def main(names):
    for name, fn in PROBES.items():
        if names and not any(name.startswith(n) for n in names):
            continue
        try:
            r = await asyncio.wait_for(fn(), timeout=60)
        except Exception as e:
            r = {"PROBE_ERROR": f"{type(e).__name__}: {e}"}
        print(f"=== {name} ===")
        print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    names = sys.argv[1:]
    sys.argv = sys.argv[:1]
    print("python", sys.version.split()[0])
    asyncio.run(main(names))
