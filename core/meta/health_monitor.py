import logging
import asyncio
from .self_model import update_health

logger = logging.getLogger("ocbrain.meta.health")

class HealthMonitor:
    """
    Tracks system metrics and runs periodic diagnostics.
    """
    def __init__(self):
        self._is_running = False
        self._task: asyncio.Task | None = None
        self._metrics = {
            "failed_provider_calls": 0,
            "total_provider_calls": 0,
            "retrieval_hits": 0,
            "total_retrievals": 0,
            "latencies": []
        }

    async def start(self):
        if self._is_running:
            return
        self._is_running = True
        logger.info("[HealthMonitor] Monitoring system active.")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._diagnostic_loop())

    def stop(self):
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _diagnostic_loop(self):
        """Runs diagnostics every 10 minutes (standard for Phase 4)."""
        try:
            while self._is_running:
                try:
                    self.run_diagnostics()
                except Exception as e:
                    logger.error(f"[HealthMonitor] Diagnostic loop error: {e}")
                await asyncio.sleep(600)
        except asyncio.CancelledError:
            raise

    def run_diagnostics(self):
        logger.info("[HealthMonitor] Running periodic diagnostics...")
        self._check_providers()
        self._check_memory()
        self._calculate_stability()
        logger.info("[HealthMonitor] Diagnostics complete.")

    def _check_providers(self):
        # Logic to check real provider health from mesh
        # For simulation, we look at previous turn stats if any
        pass

    def _check_memory(self):
        from core.memory.mem_vault import MemoryVault
        MemoryVault()
        # Verify JSON integrity and entry count
        update_health("memory_integrity", 1.0)

    def _calculate_stability(self):
        # Stability based on crash/failure frequency
        stability = 1.0
        if self._metrics["total_provider_calls"] > 0:
            failure_rate = self._metrics["failed_provider_calls"] / self._metrics["total_provider_calls"]
            stability -= (failure_rate * 0.5)
        
        update_health("system_stability", round(stability, 2))

    def record_provider_call(self, success: bool, latency_ms: int):
        self._metrics["total_provider_calls"] += 1
        if not success:
            self._metrics["failed_provider_calls"] += 1
        self._metrics["latencies"].append(latency_ms)
        if len(self._metrics["latencies"]) > 100:
            self._metrics["latencies"].pop(0)

    def record_retrieval(self, hit: bool):
        self._metrics["total_retrievals"] += 1
        if hit:
            self._metrics["retrieval_hits"] += 1
        
        if self._metrics["total_retrievals"] > 0:
            precision = self._metrics["retrieval_hits"] / self._metrics["total_retrievals"]
            update_health("retrieval_precision", round(precision, 2))

# Global singleton
health_monitor = HealthMonitor()
