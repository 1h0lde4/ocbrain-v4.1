import asyncio
import sys
import os
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.runtime.state import StateStore

async def test_replay_ordering():
    db_path = ".data/test_ordering.sqlite"
    if os.path.exists(db_path): os.remove(db_path)
    
    store = StateStore(db_path=db_path)
    # Don't start the background loop, we'll flush manually
    
    print("Step 1: Queuing three sequential updates for 'mod_a'...")
    await store.update_maturity("mod_a", 0.1, 1) # v1
    await store.update_maturity("mod_a", 0.2, 2) # v2
    await store.update_maturity("mod_a", 0.3, 3) # v3 (Newest)
    
    assert len(store._queue) == 3
    
    print("Step 2: Simulating a failed flush for the first two items (v1, v2)...")
    # We'll manually simulate what happens in _flush_batch on failure
    batch = []
    batch.append(store._queue.popleft()) # v1
    batch.append(store._queue.popleft()) # v2
    
    # Simulate re-queueing on failure
    async with store._queue_lock:
        for item in reversed(batch):
            store._queue.appendleft(item)
    
    print(f"Queue size: {len(store._queue)}")
    # Expected order now: [v1, v2, v3] <-- CORRECT
    
    print("Step 3: Flushing the entire queue to DB...")
    while store._queue:
        await store._flush_batch()
        
    print("Step 4: Checking final state in DB...")
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT score, query_count FROM maturity WHERE module_name='mod_a'").fetchone()
        print(f"Final DB State: score={row[0]}, count={row[1]}")
        
        if row[1] == 2:
            print("CRITICAL ORDERING BUG CONFIRMED: v2 (older) overwrote v3 (newer)!")
        else:
            print("Ordering preserved.")

    try:
        if os.path.exists(db_path): os.remove(db_path)
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_replay_ordering())
