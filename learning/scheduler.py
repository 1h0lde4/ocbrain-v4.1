"""
learning/scheduler.py — V2: adds distillation cycle + gap detection.
"""
import asyncio
from core.config import config
from core.event_bus import bus


class Scheduler:
    def __init__(self, registry_ref: dict):
        self.registry = registry_ref
        self._running = False

    async def start(self):
        self._running = True
        await asyncio.gather(
            self._loop_crawler(),
            self._loop_cleaner(),
            self._loop_trainer(),
            self._loop_distiller(),    # NEW in V2
            self._loop_gap_detector(), # NEW in V2
        )

    def stop(self):
        self._running = False

    async def _loop_crawler(self):
        from learning.crawler import run_all
        while self._running:
            interval = float(config.get("learning.crawl_interval_h") or 1) * 3600
            try:
                await run_all(self.registry)
                await bus.emit("learning.crawl_done", {"modules": list(self.registry.keys())})
            except Exception as e:
                print(f"[scheduler] crawler error: {e}")
            await asyncio.sleep(interval)

    async def _loop_cleaner(self):
        from learning import cleaner
        while self._running:
            interval = float(config.get("learning.clean_interval_h") or 6) * 3600
            await asyncio.sleep(interval)
            try:
                cleaner.run_all(self.registry)
                await bus.emit("learning.clean_done", {})
            except Exception as e:
                print(f"[scheduler] cleaner error: {e}")

    async def _loop_trainer(self):
        while self._running:
            interval = float(config.get("learning.train_interval_h") or 24) * 3600
            await asyncio.sleep(interval)
            try:
                await self._training_cycle()
            except Exception as e:
                print(f"[scheduler] training error: {e}")

    async def _loop_distiller(self):
        """V2: run gap-targeted distillation every 12 hours."""
        while self._running:
            await asyncio.sleep(12 * 3600)
            if not config.get("learning.training_enabled", True):
                continue
            try:
                await self._distillation_cycle()
            except Exception as e:
                print(f"[scheduler] distillation error: {e}")

    async def _loop_gap_detector(self):
        """V2: detect knowledge gaps every 6 hours."""
        while self._running:
            await asyncio.sleep(6 * 3600)
            try:
                await self._gap_detection_cycle()
            except Exception as e:
                print(f"[scheduler] gap detector error: {e}")

    async def _training_cycle(self):
        from learning import trainer, finetuner, evaluator
        from core.model_router import model_router
        from core.brain_version import brain_version_manager

        for name, module in self.registry.items():
            state = config.get_module_state(name)
            if state.get("pin_to_external", False):
                continue

            data_path = trainer.prepare(name, self.registry)
            if data_path is None:
                continue

            await bus.emit("learning.train_started", {"module": name})

            pending_path = finetuner.train(name, data_path)
            if pending_path is None:
                continue

            passed = await evaluator.evaluate(name, pending_path, self.registry)
            if passed:
                module.load_weights(pending_path)
                model_router._update_maturity(name, 0.7)
                model_router._maybe_promote(name)
                with open(data_path) as _f:
                    n_pairs = sum(1 for _ in _f)
                brain_version_manager.record_training(name, n_pairs)
                await bus.emit("learning.train_done", {"module": name, "passed": True})
                await bus.emit("module.weights_updated", {"module": name})
                print(f"[scheduler] {name}: weights hot-swapped ✓")
            else:
                import shutil
                shutil.rmtree(pending_path, ignore_errors=True)
                await bus.emit("module.weights_failed", {"module": name})
                print(f"[scheduler] {name}: weights failed eval — kept previous")

    async def _distillation_cycle(self):
        """Run distillation for any pending gap queues."""
        from learning.gap_detector import load_gap_queue, clear_gap_queue, mark_topic_known
        from learning.distiller import distill_topic
        from core.brain_version import brain_version_manager

        for name in self.registry:
            gaps = load_gap_queue(name)
            if not gaps:
                continue
            print(f"[scheduler] Distilling {len(gaps)} gaps for '{name}'")
            for topic in gaps:
                try:
                    n = await distill_topic(name, topic, num_pairs=30)
                    if n > 0:
                        mark_topic_known(name, topic)
                        brain_version_manager.record_distillation()
                except Exception as e:
                    print(f"[scheduler] distill '{topic}' for {name}: {e}")
            clear_gap_queue(name)

    async def _gap_detection_cycle(self):
        from learning.gap_detector import detect_and_queue
        for name in self.registry:
            try:
                gaps = await detect_and_queue(name, self.registry)
                if gaps:
                    print(f"[scheduler] {name}: queued {len(gaps)} gap topics")
            except Exception as e:
                print(f"[scheduler] gap detection for {name}: {e}")

    async def trigger_module(self, module_name: str) -> str:
        from learning import trainer, finetuner, evaluator
        from core.model_router import model_router

        data_path = trainer.prepare(module_name, self.registry)
        if data_path is None:
            return f"Not enough training pairs for '{module_name}'."
        pending = finetuner.train(module_name, data_path)
        if pending is None:
            return f"Fine-tuning failed for '{module_name}'."
        passed = await evaluator.evaluate(module_name, pending, self.registry)
        if passed:
            self.registry[module_name].load_weights(pending)
            await bus.emit("module.weights_updated", {"module": module_name})
            return f"'{module_name}' updated and hot-swapped successfully."
        else:
            import shutil
            shutil.rmtree(pending, ignore_errors=True)
            return f"'{module_name}' new weights failed evaluation — kept previous."
