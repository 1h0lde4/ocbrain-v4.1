import pytest
import asyncio
from core.runtime.limits import safe_llm_call, IterationBudget

@pytest.mark.asyncio
async def test_safe_llm_call_success():
    async def mock_llm_call(query):
        return f"Response to {query}"
        
    result = await safe_llm_call(mock_llm_call, "Hello")
    assert result == "Response to Hello"

@pytest.mark.asyncio
async def test_safe_llm_call_timeout():
    async def hanging_call():
        await asyncio.sleep(40) # Should hit the 30s timeout
        return "Done"
        
    try:
        # Patch for test
        original_wait_for = asyncio.wait_for

        async def mock_wait_for(coro, timeout):
            return await original_wait_for(coro, timeout=0.1)
        
        asyncio.wait_for = mock_wait_for
        
        with pytest.raises(asyncio.TimeoutError):
            await safe_llm_call(hanging_call)
    finally:
        asyncio.wait_for = original_wait_for

def test_iteration_budget():
    budget = IterationBudget(max_steps=2)
    
    budget.check() # step 1
    budget.check() # step 2
    
    with pytest.raises(RuntimeError, match="Iteration limit exceeded"):
        budget.check() # step 3 should fail
