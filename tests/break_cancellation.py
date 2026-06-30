import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.orchestrator import Orchestrator
from core.runtime.limits import ADAPTIVE_LLM_LIMIT
from core.runtime.state import state_store
from core.memory.unified_memory import get_unified_memory

async def test_cancellation_leak():
    # Mocking a slow module that ignores cancellation or takes time to clean up
    async def slow_module_task(*args, **kwargs):
        try:
            print("Module task started...")
            await asyncio.sleep(5.0) # Simulate long work
            print("Module task finished (should NOT happen if cancelled)")
            return "finished"
        except asyncio.CancelledError:
            print("Module task received Cancellation (GOOD)")
            raise

    # 1. Start an orchestration
    orchestrator = Orchestrator(modules={}, context=None, router=AsyncMock(),
                                 memory=get_unified_memory())
    
    # We patch the router to use our slow task
    orchestrator.router.route = slow_module_task

    print("\nStarting handle() and cancelling it after 1s...")
    task = asyncio.create_task(orchestrator.handle("test query"))
    await asyncio.sleep(1.0)
    
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Orchestrator.handle() cancelled.")

    # 2. Check if resources are held
    # If the module task is still running, it might still hold a semaphore slot
    # (In this mock it doesn't use the semaphore unless we wrap it)
    
    print("Checking if any tasks are still running...")
    await asyncio.sleep(2.0) # Wait to see if "finished" prints
    
    # Check Semaphore
    print(f"Semaphore current limit: {ADAPTIVE_LLM_LIMIT.current_limit}")
    print(f"Semaphore available: {ADAPTIVE_LLM_LIMIT._semaphore._value}")
    
    # Check if StateStore queue is clean
    print(f"StateStore queue size: {state_store._queue.qsize()}")

if __name__ == "__main__":
    asyncio.run(test_cancellation_leak())
