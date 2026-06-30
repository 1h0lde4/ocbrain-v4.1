import pytest
import asyncio
from core.meta.self_model import SELF_MODEL, CapabilityDetector
from core.meta.introspection import summarize_system_state, explain_capabilities
from core.meta.health_monitor import health_monitor
from core.web_learning.trust import trust_manager
from core.meta.planner import upgrade_planner

@pytest.mark.asyncio
async def test_self_model_and_introspection():
    # Trigger detection
    CapabilityDetector.detect_all()
    
    assert SELF_MODEL["identity"]["name"] == "OCBrain"
    
    summary = summarize_system_state()
    assert "System Stability" in summary
    
    caps = explain_capabilities()
    assert "memory system" in caps.lower()

@pytest.mark.asyncio
async def test_health_monitor_recording():
    # Simulate some activity
    health_monitor.record_provider_call(success=True, latency_ms=100)
    health_monitor.record_provider_call(success=False, latency_ms=50)
    
    health_monitor.run_diagnostics()
    
    # Stability should have dropped from 1.0
    assert SELF_MODEL["health"]["system_stability"] < 1.0

@pytest.mark.asyncio
async def test_web_learning_trust():
    score = trust_manager.get_trust_score("https://wikipedia.org/wiki/Test")
    assert score >= 0.9
    
    low_score = trust_manager.get_trust_score("https://unknown-blog.com/post")
    assert low_score <= 0.5

@pytest.mark.asyncio
async def test_upgrade_planner():
    # Artificially lower health
    SELF_MODEL["health"]["retrieval_precision"] = 0.5
    
    proposals = upgrade_planner.propose_upgrades()
    assert len(proposals) > 0
    assert any(p["type"] == "memory_optimization" for p in proposals)

if __name__ == "__main__":
    asyncio.run(test_self_model_and_introspection())
    asyncio.run(test_health_monitor_recording())
    asyncio.run(test_web_learning_trust())
    asyncio.run(test_upgrade_planner())
    print("Phase 4 tests passed!")
