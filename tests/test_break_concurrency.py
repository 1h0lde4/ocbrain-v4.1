import asyncio
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.base import BaseModule, ModuleResult

class MockModule(BaseModule):
    name = "mock"
    async def run(self, task, context): pass
    async def run_own(self, task, context): pass

async def test_cache_concurrency():
    mod = MockModule()
    
    # Fill the cache near limit
    for i in range(120):
        mod.retrieve(f"query_{i}")
        
    async def hammering_retrieve():
        for i in range(100):
            # This triggers a read + potentially a write (which might trigger a delete of oldest)
            mod.retrieve(f"stress_{i}")
            await asyncio.sleep(0)

    async def hammering_ingest():
        for i in range(100):
            # This triggers a delete of all keys for this module
            mod.ingest([f"new_content_{i}"])
            await asyncio.sleep(0)

    print("Starting concurrency hammer...")
    # Run multiple retrievers and ingesters in parallel
    try:
        await asyncio.gather(
            hammering_retrieve(), hammering_retrieve(),
            hammering_ingest(), hammering_ingest()
        )
        print("Test finished without RuntimeError (lucky or GIL held strong).")
    except RuntimeError as e:
        print(f"CONCURRENCY BUG CONFIRMED: {e}")
    except Exception as e:
        print(f"Test failed with unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(test_cache_concurrency())
