import logging
from importlib.util import find_spec
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
        from core.memory.mem_vault import MemoryVault
        vault = MemoryVault()
        SELF_MODEL["capabilities"]["memory_system"] = len(vault.entries) >= 0 # Always true if class exists
        SELF_MODEL["health"]["memory_integrity"] = 1.0 # Placeholder for actual validation

    @staticmethod
    def _detect_retrieval():
        SELF_MODEL["capabilities"]["hybrid_retrieval"] = (
            find_spec("core.memory.hybrid_retrieval") is not None
        )
