import asyncio
import sys
import os
import time
import statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.runtime.resilience import AdaptiveSemaphore

async def test_adaptive_thrash():
    # target 2s
    sem = AdaptiveSemaphore(min_limit=1, max_limit=10, target_latency_ms=2000)
    
    limits = []
    
    async def simulate_call(latency):
        async with sem:
            await asyncio.sleep(latency)
        limits.append(sem.current_limit)

    print("Starting Adaptive Thrash simulation...")
    # Alternating 100ms and 5s (oscillating around the 2s target)
    for _ in range(10):
        # 3 fast calls
        await asyncio.gather(simulate_call(0.1), simulate_call(0.1), simulate_call(0.1))
        # 1 slow call
        await simulate_call(5.0)

    print(f"Limit History: {limits}")
    
    # Check for oscillation (constant jumping between extremes)
    unique_limits = set(limits)
    print(f"Unique Limits encountered: {unique_limits}")
    
    std_dev = statistics.stdev(limits) if len(limits) > 1 else 0
    print(f"Standard Deviation of limits: {std_dev:.2f}")
    
    if std_dev > 1.5:
        print("INSTABILITY CONFIRMED: High oscillation in concurrency limits!")
    else:
        print("System appears stable (or too slow to react).")

if __name__ == "__main__":
    asyncio.run(test_adaptive_thrash())
