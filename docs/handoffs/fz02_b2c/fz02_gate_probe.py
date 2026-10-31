"""FZ-02 / B2c gate probe (evidence artifact, not a test; not collected by pytest).

Question: how does the graph watchdog actually stop a node, and is router-level
cancellation exercised by the REAL workflow?

Run against any checkout:   OCROOT=/path/to/checkout python3 docs/handoffs/fz02_gate_probe.py

Everything is real (WorkflowRuntime, ExecutionRuntime, Worker.execute, ModelRouter
monitored streaming) except the provider stream, which hangs after one token. The
node calls the router with a production-shaped context (no `cancellation_token`
attribute, like ContextMemory).

  PROBE 1  graph budget hard=0.3 s; router's own hard deadline = 2.0 s.
           Does the graph watchdog's token cancel stop the node?
  PROBE 2  the task running WorkflowRuntime.execute() is cancelled at 0.5 s;
           node retry policy max_retries=1. Does the cancellation propagate? Is the
           provider stream closed at the cancel (router fix) or orphaned?
"""
import asyncio, os, sys, time
ROOT = os.environ["OCROOT"]; sys.path.insert(0, ROOT); os.chdir(ROOT)
import core.model_router as mr
from core.model_router import ModelRouter
from core.workflow.definition import RetryPolicy, WorkflowDefinition, WorkflowNode
from core.workflow.runtime import WorkflowRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.governance.governance_kernel import get_governance_kernel
from core.events.event_stream import get_event_stream

LONG = "write a short story of 1000 words, fantasy type"   # explicit word count => monitored streaming
S = {"attempts": 0, "closes": [], "router_returned_at": None}


class ProdShapedCtx:            # what PlannerWorker/orchestrator hand the router: no cancellation_token
    metadata = {}
    def format_for_prompt(self, n, scope=None): return ""


mr.config.get_module_state = lambda name: {"stage": "bootstrap", "bootstrap_model": "mistral"}
mr.ExecutionPolicy.for_generation = classmethod(lambda cls, **kw: ExecutionBudget(
    startup_deadline_s=0.3, progress_deadline_s=10.0, hard_ceiling_s=2.0,
    absolute_ceiling_s=2.0, max_extension_s=0.0))
ROUTER = ModelRouter()


async def hang_stream(module_name, subtask, context, scope=""):
    yield "Beginning the tale"
    try:
        await asyncio.sleep(9999)
    finally:
        S["closes"].append(time.monotonic())


async def _noop(*a, **k): return None
ROUTER._stream_external = hang_stream
ROUTER._record_training_pair = _noop
ROUTER._increment_query_count = lambda m: 1
ROUTER._maybe_promote = lambda *a, **k: None


class RouterNodeWorker(AbstractCognitiveWorker):
    worker_type = "RouterNodeWorker"
    async def _run(self, context: WorkerContext) -> WorkerResult:
        S["attempts"] += 1
        await ROUTER.route("m", LONG, ProdShapedCtx())
        S["router_returned_at"] = time.monotonic()
        return WorkerResult(success=False, error="router returned")


def runtime():
    reg = WorkerRegistry(); reg.register(RouterNodeWorker)
    st = get_event_stream()
    return WorkflowRuntime(execution_runtime=ExecutionRuntime(
        worker_registry=reg, governance=get_governance_kernel(), event_stream=st), event_stream=st)


def definition(wid, retries=0):
    return WorkflowDefinition(workflow_id=wid, entry_node="a", nodes=[WorkflowNode(
        node_id="a", worker_type="RouterNodeWorker",
        retry_policy=RetryPolicy(max_retries=retries, backoff_seconds=0.01))])


async def probe1():
    print("== PROBE 1: graph watchdog (hard 0.3 s) vs a node hung inside the real router (router hard deadline 2.0 s)")
    S.update(attempts=0, closes=[], router_returned_at=None)
    tok = CancellationToken()
    gb = ExecutionBudget(startup_deadline_s=0.1, progress_deadline_s=0.1, hard_ceiling_s=0.3,
                         absolute_ceiling_s=0.4, max_extension_s=0.1)
    t0 = time.monotonic()
    res = await runtime().execute(definition("p1"), query="hi", cancellation_token=tok,
                                  metadata={"execution_budget": gb})
    print(f"  workflow returned after {time.monotonic()-t0:.2f}s | success={res.success}")
    print(f"  workflow token cancelled={tok.is_cancelled} reason={tok.reason!r}")
    print(f"  node attempts={S['attempts']} | router returned after {S['router_returned_at']-t0:.2f}s"
          f" | provider stream closed after {S['closes'][0]-t0:.2f}s")


async def probe2():
    print("== PROBE 2: the TASK running the workflow is cancelled at 0.5 s (node retry policy: max_retries=1)")
    S.update(attempts=0, closes=[], router_returned_at=None)
    t0 = time.monotonic()
    task = asyncio.create_task(runtime().execute(definition("p2", retries=1), query="hi"))
    await asyncio.sleep(0.5)
    task.cancel()
    try:
        res = await asyncio.wait_for(task, timeout=8)
        print(f"  execute() RETURNED a result after {time.monotonic()-t0:.2f}s (cancellation did NOT propagate)"
              f" | success={res.success} | task.cancelled()={task.cancelled()}")
    except asyncio.CancelledError:
        print(f"  execute() raised CancelledError after {time.monotonic()-t0:.2f}s | task.cancelled()={task.cancelled()}")
    except asyncio.TimeoutError:
        print("  execute() still running 8 s after the cancel")
    print(f"  node attempts={S['attempts']} | provider stream close times after t0 (s): {[round(c-t0,2) for c in S['closes']]}")


async def main():
    await probe1(); await probe2()

asyncio.run(main())
