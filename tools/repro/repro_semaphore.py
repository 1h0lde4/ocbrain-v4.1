import asyncio
import time
from core.runtime.resilience import AdaptiveSemaphore

async def task(name, semaphore, sleep_time):
    print(f"Task {name} starting")
    async with semaphore:
        print(f"Task {name} acquired semaphore")
        await asyncio.sleep(sleep_time)
        print(f"Task {name} releasing semaphore")
    print(f"Task {name} done")

async def main():
    # Limit to 2 for easy reproduction
    sem = AdaptiveSemaphore(min_limit=2, max_limit=2, target_latency_ms=5000)

    # Run two tasks that overlap
    await asyncio.gather(
        task("A", sem, 1.0),
        task("B", sem, 0.5)
    )

if __name__ == "__main__":
    asyncio.run(main())
