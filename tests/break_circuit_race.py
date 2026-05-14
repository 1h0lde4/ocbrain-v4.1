import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.runtime.resilience import CircuitBreaker, CircuitState

async def test_breaker_race():
    # threshold 1 to make it easy to open
    breaker = CircuitBreaker("race_test", threshold=1, reset_timeout=0.2)
    
    async def fail():
        raise RuntimeError("Fail")

    async def slow_success():
        await asyncio.sleep(0.5)
        return "ok"

    # 1. Open the circuit
    print("Opening circuit...")
    try:
        await breaker.call(fail)
    except RuntimeError:
        pass
    assert breaker.state == CircuitState.OPEN
    
    # 2. Wait for reset timeout
    await asyncio.sleep(0.25)
    print("Circuit should be ready for HALF_OPEN.")
    
    # 3. Hammer with 10 parallel requests
    # If there's a race, all 10 might enter the success_fn simultaneously
    print("Hammering HALF_OPEN state with 10 parallel probes...")
    
    tasks = [breaker.call(slow_success) for _ in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = [r for r in results if r == "ok"]
    errors = [r for r in results if isinstance(r, Exception)]
    
    print(f"Results: {len(successes)} successes, {len(errors)} errors")
    
    # A correct HALF_OPEN should only allow ONE probe through at a time
    # (or at least manage the transition atomically).
    # If 10 succeeded, it means 10 probes were allowed in parallel during HALF_OPEN.
    if len(successes) > 1:
        print(f"CRITICAL RACE CONFIRMED: {len(successes)} parallel probes allowed in HALF_OPEN!")
    else:
        print("No race detected (unlikely without a lock).")

if __name__ == "__main__":
    asyncio.run(test_breaker_race())
