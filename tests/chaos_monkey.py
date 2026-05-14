import asyncio
import sys
import random
import time
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.orchestrator import Orchestrator
from core.runtime.state import state_store

# --- CHAOS INJECTORS ---

def inject_db_chaos():
    """Monkeypatch sqlite3 to simulate locks and delays."""
    original_connect = sqlite3.connect
    
    def chaos_connect(*args, **kwargs):
        if random.random() < 0.2:
            # 20% chance of a slow connection
            time.sleep(random.uniform(0.1, 0.5))
        
        conn = original_connect(*args, **kwargs)
        
        # Wrap execute to randomly fail
        original_execute = conn.execute
        def chaos_execute(*args, **kwargs):
            if random.random() < 0.1:
                raise sqlite3.OperationalError("database is locked (Chaos Monkey)")
            return original_execute(*args, **kwargs)
        
        conn.execute = chaos_execute
        return conn

    sqlite3.connect = chaos_connect

async def random_canceller(task):
    """Randomly cancels a task mid-flight."""
    await asyncio.sleep(random.uniform(0.1, 2.0))
    if not task.done():
        print("  [CHAOS] Injecting random cancellation!")
        task.cancel()

# --- THE MONKEY RUNNER ---

async def run_chaos_monkey(duration=30):
    print("=" * 60)
    print("  OCBRAIN CHAOS MONKEY STARTING")
    print("=" * 60)
    
    inject_db_chaos()
    await state_store.start()
    
    orchestrator = Orchestrator(modules={}, context=MagicMock(), router=MagicMock())
    
    # Mock a module that sometimes fails, sometimes is slow
    async def chaotic_route(name, query, ctx):
        r = random.random()
        if r < 0.1:
            raise RuntimeError("Random Provider Failure")
        if r < 0.3:
            await asyncio.sleep(random.uniform(1.0, 5.0))
        return "Chaos result"
    
    orchestrator.router.route = chaotic_route
    
    start_time = time.time()
    task_count = 0
    failures = 0
    
    while time.time() - start_time < duration:
        task_count += 1
        query = f"Chaos query {task_count}"
        
        # Randomly duplicate an event to StateStore
        if random.random() < 0.1:
            await state_store.update_maturity("chaos_mod", 0.8, task_count)
        
        print(f"Dispatching {query}...")
        h_task = asyncio.create_task(orchestrator.handle(query))
        
        # Randomly decide to cancel this one
        if random.random() < 0.3:
            asyncio.create_task(random_canceller(h_task))
            
        try:
            await h_task
        except asyncio.CancelledError:
            print(f"  [OK] {query} was cancelled and cleaned up.")
        except Exception as e:
            print(f"  [FAIL] {query} failed with: {e}")
            failures += 1
            
        await asyncio.sleep(random.uniform(0.1, 0.5))

    print("=" * 60)
    print("  CHAOS MONKEY FINISHED")
    print(f"  Tasks: {task_count} | Failures: {failures}")
    print("=" * 60)
    
    await state_store.stop()

if __name__ == "__main__":
    asyncio.run(run_chaos_monkey())
