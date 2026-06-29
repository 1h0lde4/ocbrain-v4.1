import asyncio
import time
from core.runtime.resilience import AdaptiveSemaphore

async def task(name, semaphore, sleep_time):
    print(f"Task {name} trying to acquire")
    try:
        async with semaphore:
            print(f"Task {name} acquired")
            await asyncio.sleep(sleep_time)
            print(f"Task {name} releasing")
    except Exception as e:
        print(f"Task {name} error: {e}")
    print(f"Task {name} done")

async def main():
    # Limit = 1
    sem = AdaptiveSemaphore(min_limit=1, max_limit=1, target_latency_ms=5000)

    print(f"--- First batch (should work) ---")
    await asyncio.gather(
        task("A", sem, 0.1),
    )

    print(f"\n--- Second batch (overlapping, should trigger bug) ---")
    # This might be tricky because of the semaphore itself.
    # If limit is 1, they won't overlap IN the context manager.

    # If limit is 2
    sem = AdaptiveSemaphore(min_limit=2, max_limit=2, target_latency_ms=5000)
    print(f"\n--- Third batch (limit 2, overlapping) ---")
    await asyncio.gather(
        task("C", sem, 0.5),
        task("D", sem, 0.1)
    )

    print(f"\n--- Fourth batch (checking if one was leaked) ---")
    # If D exited first, it set _acquired to False.
    # C will then NOT release the semaphore.
    # So now 1 slot is leaked.

    # If we try to run 2 more tasks, one should hang if one was leaked.
    try:
        await asyncio.wait_for(asyncio.gather(
            task("E", sem, 0.1),
            task("F", sem, 0.1)
        ), timeout=2.0)
    except asyncio.TimeoutError:
        print("\nTIMEOUT: Detected semaphore leak! (Expected)")

if __name__ == "__main__":
    asyncio.run(main())
