import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch

from core.context import context_memory
from core.model_router import model_router
from core.orchestrator import Orchestrator


async def run_stress(num_requests=30):
    orchestrator = Orchestrator(modules={}, context=context_memory, router=model_router)

    # We mock generate_with_fallback to simulate a slow LLM (2s per call)
    # This will trigger queueing because semaphore is likely 3.
    async def slow_mock(*args, **kwargs):
        await asyncio.sleep(2.0)
        return "mocked answer"

    with patch("core.model_router.generate_with_fallback", side_effect=slow_mock):
        print(f"Starting Stress Test: {num_requests} concurrent requests...")
        start_time = time.perf_counter()

        tasks = [orchestrator.handle(f"Stress query {i}") for i in range(num_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.perf_counter()
        duration = end_time - start_time

        successes = [r for r in results if isinstance(r, str) and "Sorry" not in r]
        errors = [r for r in results if not isinstance(r, str) or "Sorry" in r]

        print("\nSTRESS TEST COMPLETE")
        print(f"Total time: {duration:.2f}s")
        print(f"Throughput: {num_requests / duration:.2f} req/s")
        print(f"Successes: {len(successes)}")
        print(f"Failures: {len(errors)}")

        # If semaphore is 3, then 30 requests should take at least (30/3)*2 = 20s
        # If it takes much less, semaphore is not working.
        # If it takes much more or hangs, we have a queueing efficiency issue.


if __name__ == "__main__":
    asyncio.run(run_stress())
