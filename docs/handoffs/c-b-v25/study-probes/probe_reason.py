import asyncio, os, sys
sys.path.insert(0, "/tmp/probe");
import probes_a as A
from core.runtime.execution_graph import ExecutionGraph
from core.runtime.progress import ProgressMonitor
from core.runtime.watchdog import GraphExecutionWatchdog
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.watchdog_decision import CancelReason
async def main():
    s = A.mk_stream(); g = ExecutionGraph("r"); await g.add_node(title="n", operation_type="x")
    tok = CancellationToken()
    wd = GraphExecutionWatchdog(g, ExecutionBudget(startup_deadline_s=10, progress_deadline_s=45, hard_ceiling_s=0.01, absolute_ceiling_s=0.02, max_extension_s=0.01), tok, ProgressMonitor(g, s))
    await asyncio.sleep(0.05)
    state = await wd.inspect()
    print("graph-watchdog token.reason =", repr(tok.reason), "| CancelReason.HARD_DEADLINE.value =", repr(CancelReason.HARD_DEADLINE.value), "| equal:", tok.reason == CancelReason.HARD_DEADLINE.value)
asyncio.run(main())
