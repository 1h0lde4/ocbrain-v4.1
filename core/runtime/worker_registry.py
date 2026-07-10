"""
core/runtime/worker_registry.py — WorkerRegistry (K2.1)

Static index of constructable Worker types.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §6.1 — WorkerRegistry.
    Populated at startup, read-only after initialization.

Design:
    - Maps worker_type strings to Worker classes.
    - get() returns the class (not an instance) — ExecutionRuntime
      instantiates a fresh worker per invoke() call (ADR-003).
    - Registration is explicit (composition root), not auto-discovery.
"""

import logging
from typing import Dict, List, Optional, Type

from core.workers.base import AbstractCognitiveWorker

logger = logging.getLogger("ocbrain.runtime.worker_registry")


class WorkerRegistry:
    """Static index of constructable Worker types.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §6.1 — WorkerRegistry.
        ADR-003 — Workers are ephemeral (new instance per invoke).

    Usage:
        registry = WorkerRegistry()
        registry.register(MemoryCuratorWorker)
        worker_cls = registry.get("MemoryCuratorWorker")
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Type[AbstractCognitiveWorker]] = {}

    def register(self, worker_class: Type[AbstractCognitiveWorker]) -> None:
        """Register a worker type.

        Args:
            worker_class: The worker class to register.
                          Must have a worker_type class attribute.

        Raises:
            ValueError: If worker_type is already registered.
        """
        worker_type = worker_class.worker_type
        if worker_type in self._registry:
            raise ValueError(
                f"Worker type '{worker_type}' is already registered "
                f"(existing: {self._registry[worker_type].__name__}, "
                f"new: {worker_class.__name__})"
            )
        self._registry[worker_type] = worker_class
        logger.info("WorkerRegistry: registered '%s' → %s",
                     worker_type, worker_class.__name__)

    def get(self, worker_type: str) -> Optional[Type[AbstractCognitiveWorker]]:
        """Look up a worker class by type name.

        Args:
            worker_type: The worker_type string to look up.

        Returns:
            The worker class, or None if not found.
        """
        return self._registry.get(worker_type)

    def list_types(self) -> List[str]:
        """Return all registered worker type names."""
        return list(self._registry.keys())

    def stats(self) -> Dict[str, str]:
        """Return registry contents for observability."""
        return {
            worker_type: cls.__name__
            for worker_type, cls in self._registry.items()
        }
