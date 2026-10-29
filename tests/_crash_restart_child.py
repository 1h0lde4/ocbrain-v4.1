"""Child process for tests/test_workflow_crash_restart_subprocess.py (not a test module: no ``test_`` prefix).

argv: <repo_root> <crash|resume> <event_db_path> <invocation_log_path> [<instance_id>]

Runs workflow a -> b -> c on a persistent SQLite event store.  Every node invocation is appended to a JSONL
file (with the PID, fsync'd) because in-memory state does not survive a process boundary.  In ``crash`` mode
node ``b`` calls ``os._exit(137)`` while executing: a hard kill with no cleanup, no ``except`` and no
``atexit``.  In ``resume`` mode a fresh process resumes the instance from the on-disk checkpoint alone.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
MODE, DB, LOG = sys.argv[2], sys.argv[3], sys.argv[4]
INSTANCE = sys.argv[5] if len(sys.argv) > 5 else ""

from core.events.event_stream import EventStream, SQLiteEventStore  # noqa: E402
from core.governance.governance_kernel import get_governance_kernel  # noqa: E402
from core.runtime.execution_runtime import ExecutionRuntime  # noqa: E402
from core.runtime.worker_registry import WorkerRegistry  # noqa: E402
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult  # noqa: E402
from core.workflow.definition import WorkflowDefinition, WorkflowEdge, WorkflowNode  # noqa: E402
from core.workflow.runtime import WorkflowRuntime  # noqa: E402


def _log(node: str, event: str) -> None:
    with open(LOG, "a") as f:
        f.write(json.dumps({"pid": os.getpid(), "node": node, "event": event}) + "\n")
        f.flush()
        os.fsync(f.fileno())


class LoggingNodeWorker(AbstractCognitiveWorker):
    worker_type = "LoggingNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        node = (context.metadata or {}).get("node_id")
        _log(node, "start")
        if MODE == "crash" and node == "b":
            os._exit(137)  # killed mid-node: 'b' never reports done, never returns a result
        _log(node, "done")
        return WorkerResult(success=True, output=f"done:{node}")


definition = WorkflowDefinition(
    workflow_id="w-crash-restart", name="crash-restart",
    nodes=[WorkflowNode(node_id=n, worker_type="LoggingNodeWorker") for n in ("a", "b", "c")],
    edges=[WorkflowEdge(from_node="a", to_node="b"), WorkflowEdge(from_node="b", to_node="c")],
    entry_node="a",
)
registry = WorkerRegistry()
registry.register(LoggingNodeWorker)
stream = EventStream(SQLiteEventStore(db_path=DB))
runtime = WorkflowRuntime(
    execution_runtime=ExecutionRuntime(
        worker_registry=registry, governance=get_governance_kernel(), event_stream=stream),
    event_stream=stream,
)


async def main() -> None:
    if MODE == "crash":
        await runtime.execute(definition, query="q")
        print("UNREACHABLE: execute() returned although node b hard-kills the process", flush=True)
    else:
        r = await runtime.resume(definition, INSTANCE, query="q")
        print(json.dumps({"success": r.success, "error": r.error,
                          "outputs": {k: v.output for k, v in r.node_results.items()}}), flush=True)


asyncio.run(main())
