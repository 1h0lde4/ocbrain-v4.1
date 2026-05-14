"""
core/event_bus.py — Internal pub/sub event system.
Modules emit events; OpenClaw components subscribe.
No polling needed anywhere in the system.

Usage:
    from core.event_bus import bus

    # Subscribe
    bus.on("module.promoted", my_handler)

    # Emit
    await bus.emit("module.promoted", {"module": "coding", "stage": "native"})
"""
import asyncio
import logging
from collections import defaultdict
from typing import Callable

log = logging.getLogger(__name__)

# ── Event catalogue (all valid event names) ──────────────────
EVENTS = {
    # Module lifecycle
    "module.promoted",          # module reached next stage
    "module.rollback",          # module regressed to previous stage
    "module.weights_updated",   # hot-swap completed successfully
    "module.weights_failed",    # new weights failed evaluation
    "module.created",           # new custom module scaffolded
    # Learning pipeline
    "learning.crawl_done",      # crawler finished a run
    "learning.clean_done",      # cleaner processed raw data
    "learning.train_started",   # fine-tuning run began
    "learning.train_done",      # fine-tuning run completed
    "learning.distill_done",    # distillation batch completed
    "learning.gap_detected",    # gap detector found knowledge holes
    # Knowledge store
    "kb.ingested",              # new chunks written to ChromaDB
    # Brain health
    "brain.ready",              # brain fully initialised
    "brain.degraded",           # one or more modules unhealthy
    # Query lifecycle
    "query.received",           # user sent a query
    "query.answered",           # answer returned to caller
}


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, handler: Callable):
        """Register a sync or async handler for an event."""
        if event not in EVENTS:
            log.warning(f"[event_bus] Unknown event: '{event}' — registering anyway")
        self._handlers[event].append(handler)

    def off(self, event: str, handler: Callable):
        """Unregister a handler."""
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            pass

    async def emit(self, event: str, payload: dict = None):
        """
        Fire all handlers for this event.
        Async handlers are awaited; sync handlers run in executor.
        Errors in handlers are logged but never propagate to the caller.
        """
        if payload is None:
            payload = {}
        payload["_event"] = event

        handlers = list(self._handlers.get(event, []))
        if not handlers:
            return

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(payload)
                else:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, handler, payload)
            except Exception as e:
                log.error(f"[event_bus] Handler error on '{event}': {e}")

    def emit_sync(self, event: str, payload: dict = None):
        """Fire event from synchronous context (schedules on running loop)."""
        try:
            loop = asyncio.get_running_loop()
            # Running inside async context — schedule as task
            loop.create_task(self.emit(event, payload or {}))
        except RuntimeError:
            # No running loop — we are in a sync context, run directly
            try:
                asyncio.run(self.emit(event, payload or {}))
            except Exception as e:
                log.error(f"[event_bus] emit_sync error on '{event}': {e}")
        except Exception as e:
            log.error(f"[event_bus] emit_sync error on '{event}': {e}")


# Global singleton — import this everywhere
bus = EventBus()
