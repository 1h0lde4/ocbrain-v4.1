import logging
from typing import Any

logger = logging.getLogger("ocbrain.meta.self_model")

SELF_MODEL = {
    "identity": {
        "name": "OCBrain",
        "version": "3.01",
        "current_phase": 4
    },
    "capabilities": {
        "memory_system": True,
        "hybrid_retrieval": True,
        "provider_mesh": True,
        "self_improvement": True,
        "web_learning": False,
        "autonomous_planning": False
    },
    "limits": {
        "vision_enabled": False,
        "max_context_length": 8192,
        "max_parallel_tasks": 3,
        "provider_limitations": {}
    },
    "health": {
        "memory_integrity": 1.0,
        "provider_reliability": {},
        "test_success_rate": 1.0,
        "retrieval_precision": 1.0,
        "system_stability": 1.0
    },
    "known_weaknesses": [],
    "pending_upgrades": [],
    "recent_failures": []
}

def update_capability(key: str, value: bool):
    """Updates a capability in the self-model."""
    if key in SELF_MODEL["capabilities"]:
        SELF_MODEL["capabilities"][key] = value
        logger.info(f"[SelfModel] Capability updated: {key} = {value}")

def update_health(metric: str, value: Any):
    """Updates a health metric in the self-model."""
    if metric in SELF_MODEL["health"]:
        SELF_MODEL["health"][metric] = value
        logger.info(f"[SelfModel] Health metric updated: {metric} = {value}")

class CapabilityDetector:
    """
    Scans the system at startup to detect real capabilities and status.
    """
    @staticmethod
    def detect_all():
        logger.info("[SelfModel] Starting dynamic capability detection...")
        CapabilityDetector._detect_providers()
        CapabilityDetector._detect_modules()
        CapabilityDetector._detect_memory()
        CapabilityDetector._detect_retrieval()
        logger.info("[SelfModel] Detection complete.")

    @staticmethod
    def _detect_providers():
        from core.provider_mesh import resolve_provider
        # Just a dummy module name to check resolution
        providers = resolve_provider("knowledge")
        reliability = {}
        for p in providers:
            reliability[p.name] = p.health_score / 100.0
        SELF_MODEL["health"]["provider_reliability"] = reliability

    @staticmethod
    def _detect_modules():
        from core.config import config
        SELF_MODEL["capabilities"]["module_registry"] = bool(config.get("modules", {}))

    @staticmethod
    def _detect_memory():
        """Detect UnifiedMemory's actual capability/health, not MemoryVault.

        UnifiedMemory has been the production memory owner since Session 4;
        MemoryVault is unused by production runtime. The previous check
        (`len(vault.entries) >= 0`) was a tautology -- always true
        regardless of actual state -- and the health value was an
        explicitly-labeled placeholder. Both are now real signals derived
        from UnifiedMemory.stats(), which is documented as safe to call
        synchronously for exactly this purpose.
        """
        from core.memory.unified_memory import get_unified_memory
        try:
            stats = get_unified_memory().stats()
            SELF_MODEL["capabilities"]["memory_system"] = {"writes", "searches", "l0"} <= stats.keys()
            SELF_MODEL["health"]["memory_integrity"] = 1.0
        except Exception:
            SELF_MODEL["capabilities"]["memory_system"] = False
            SELF_MODEL["health"]["memory_integrity"] = 0.0

    @staticmethod
    def _detect_retrieval():
        """Detect hybrid retrieval capability from UnifiedMemory, not the
        orphaned hybrid_retrieval.py file's mere existence.

        core.memory.hybrid_retrieval.HybridRetriever has had zero production
        consumers since Session 4 removed its only real usage from
        Orchestrator. find_spec() finding the file proves nothing about
        whether hybrid retrieval actually works today -- it has genuinely
        moved to UnifiedMemory.search() (BM25 + embeddings + RRF fusion,
        Session 3B), so that is what capability detection should check.
        """
        from core.memory.unified_memory import UnifiedMemory
        SELF_MODEL["capabilities"]["hybrid_retrieval"] = hasattr(UnifiedMemory, "search")
