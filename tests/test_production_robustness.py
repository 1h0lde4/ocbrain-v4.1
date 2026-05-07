import asyncio
import sys
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.runtime.state import StateStore
from core.runtime.resilience import CircuitBreaker, CircuitState, AdaptiveSemaphore
from core.runtime.limits import BackpressureGuard, PENDING_COUNTER

# 1. Test Batched State
@pytest.mark.asyncio
async def test_batched_state():
    db_path = ".data/test_state.sqlite"
    if os.path.exists(db_path): os.remove(db_path)
    
    store = StateStore(db_path=db_path)
    await store.start()
    
    # Hammer with 100 updates
    for i in range(100):
        await store.update_maturity("test_mod", 0.5 + (i/200.0), i)
    
    # Initially queue should have 100 items
    assert store._queue.qsize() == 100
    
    # Trigger manual flush
    await store._flush_batch()
    assert store._queue.qsize() == 0
    
    # Verify DB content
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT score, query_count FROM maturity WHERE module_name='test_mod'").fetchone()
        assert row[1] == 99 # query_count of last update
        
    await store.stop()
    if os.path.exists(db_path): os.remove(db_path)

# 2. Test Circuit Breaker
@pytest.mark.asyncio
async def test_circuit_breaker():
    breaker = CircuitBreaker("test", threshold=2, reset_timeout=0.1)
    
    async def failing_fn():
        raise RuntimeError("Fail")
        
    async def success_fn():
        return "ok"

    # 1. Fail twice to open
    with pytest.raises(RuntimeError): await breaker.call(failing_fn)
    assert breaker.state == CircuitState.CLOSED
    with pytest.raises(RuntimeError): await breaker.call(failing_fn)
    assert breaker.state == CircuitState.OPEN
    
    # 2. Immediate call should fail with circuit OPEN error
    with pytest.raises(RuntimeError, match="Circuit test is OPEN"):
        await breaker.call(success_fn)
        
    # 3. Wait for reset timeout
    await asyncio.sleep(0.15)
    
    # 4. Success should close it (via half-open)
    res = await breaker.call(success_fn)
    assert res == "ok"
    assert breaker.state == CircuitState.CLOSED

# 3. Test Adaptive Concurrency
@pytest.mark.asyncio
async def test_adaptive_concurrency():
    # Target latency 50ms
    sem = AdaptiveSemaphore(min_limit=1, max_limit=5, target_latency_ms=50)
    assert sem.current_limit == 1
    
    # 1. Fast call -> Increase
    async with sem:
        await asyncio.sleep(0.01)
    assert sem.current_limit == 2
    
    # 2. Slow call -> Decrease
    async with sem:
        await asyncio.sleep(0.1)
    assert sem.current_limit == 1

# 4. Test Backpressure
@pytest.mark.asyncio
async def test_backpressure():
    # Exhaust the global counter manually for testing
    for _ in range(100):
        await PENDING_COUNTER.acquire()
        
    guard = BackpressureGuard()
    with pytest.raises(RuntimeError, match="System is overloaded"):
        async with guard:
            pass
            
    # Release one and try again
    PENDING_COUNTER.release()
    async with guard:
        pass # Should work now

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
