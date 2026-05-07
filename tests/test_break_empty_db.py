import asyncio
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.base import BaseModule

class MockModule(BaseModule):
    name = "empty_test"
    async def run(self, task, context): pass
    async def run_own(self, task, context): pass

def test_empty_retrieve():
    mod = MockModule()
    # Ensure collection is empty
    count = mod.db.count()
    if count > 0:
        # This is a bit destructive for a test, but necessary to prove the bug
        # In a real test we'd use a mock DB.
        pass 
    
    print(f"Testing retrieve on empty collection (count={count})...")
    # This should return [] but currently crashes
    res = mod.retrieve("some query")
    print(f"Result: {res}")
    assert res == []

if __name__ == "__main__":
    try:
        test_empty_retrieve()
        print("Test PASSED (Bug B02 not present?)")
    except Exception as e:
        print(f"BUG B02 CONFIRMED: {e}")
