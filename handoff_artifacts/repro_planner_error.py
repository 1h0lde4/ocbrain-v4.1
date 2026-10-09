import asyncio, sys, logging
sys.path.insert(0, "/home/claude/ocb"); sys.path.insert(0, "/home/claude/ocb/tests")
from unittest.mock import MagicMock
import test_k2_2_runtime_migration as t

SECRET = "SECRET-DETAIL /var/lib/ocbrain/data/context.sqlite locked"

async def main():
    ctx = t._make_context()
    ctx.save = MagicMock(side_effect=RuntimeError(SECRET))   # outside dispatch try/except
    orch, memory, context, router = t._make_orchestrator_with_workflow_runtime(context=ctx)
    try:
        answer = await orch.handle("what is OCBrain?")
    finally:
        await orch.close()
    print("ANSWER RETURNED TO CALLER:", repr(answer))
    print("LEAKS EXCEPTION TEXT:", SECRET in answer)

logging.disable(logging.CRITICAL)
asyncio.run(main())
