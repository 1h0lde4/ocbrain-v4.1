"""
core/runtime/working_memory.py — WorkingMemory (K2.1)

L0 — in-process, per-execution scratch space.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §7.3 — Working Memory.
    PROJECT_INSTRUCTIONS.md §8.1 — L0 Working Memory.

Design:
    - Key-value store scoped to one execution.
    - Created by ExecutionRuntime at invocation.
    - Readable/writable by the Worker during execution.
    - Cleaned up after execution completes.
    - Never persists across requests.
    - Long-term persistence is UnifiedMemory's responsibility.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("ocbrain.runtime.working_memory")


class WorkingMemory:
    """L0 — in-process, per-execution scratch space.

    A key-value store scoped to one execution. Workers use this to store
    intermediate results, retrieval context, and scratch data during a
    single _run() invocation. Contents are discarded after execution.

    Usage:
        wm = WorkingMemory()
        wm.set("retrieval_context", context_obj)
        ctx = wm.get("retrieval_context")
        wm.clear()
    """

    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from working memory.

        Args:
            key: The key to look up.
            default: Value to return if key is not found.

        Returns:
            The stored value, or default if not found.
        """
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a value in working memory.

        Args:
            key: The key to store under.
            value: The value to store.
        """
        self._store[key] = value

    def has(self, key: str) -> bool:
        """Check if a key exists in working memory."""
        return key in self._store

    def remove(self, key: str) -> Optional[Any]:
        """Remove a key from working memory.

        Returns:
            The removed value, or None if key was not found.
        """
        return self._store.pop(key, None)

    def keys(self) -> list:
        """Return all keys in working memory."""
        return list(self._store.keys())

    def clear(self) -> None:
        """Clear all working memory contents.

        Called by ExecutionRuntime after execution completes.
        """
        self._store.clear()

    def snapshot(self) -> Dict[str, Any]:
        """Return a shallow copy of all working memory contents.

        Useful for debugging and event payloads. Does not deep-copy values.
        """
        return dict(self._store)

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"WorkingMemory(keys={self.keys()})"
