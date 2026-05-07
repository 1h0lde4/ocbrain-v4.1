"""
core/privacy.py — Enforces privacy settings across all layers.
Every write to disk or network call checks through this guard.
"""
from pathlib import Path
from .config import config


class PrivacyGuard:
    def can_save_history(self) -> bool:
        return bool(config.get("privacy.save_history", True))

    def can_save_training(self) -> bool:
        return bool(config.get("privacy.save_training_pairs", True))

    def can_crawl(self, module_name: str) -> bool:
        if not config.get("learning.training_enabled", True):
            return False
        module_cfg = config.get(f"modules.{module_name}", {}) or {}
        return bool(module_cfg.get("enabled", True))

    def wipe_module_data(self, module_name: str):
        """Delete all raw pairs and chunks for a module."""
        import shutil
        for folder in ["data/raw", "data/chunks"]:
            p = Path(__file__).parent.parent / folder / module_name
            if p.exists():
                shutil.rmtree(p)
        # Also wipe ChromaDB — handled by calling module.db.reset()

    def wipe_all(self):
        """Nuclear option — wipe all user data."""
        import shutil
        root = Path(__file__).parent.parent
        for folder in ["data/raw", "data/chunks"]:
            p = root / folder
            if p.exists():
                shutil.rmtree(p)
                p.mkdir(parents=True)
        # Wipe SQLite context
        ctx = root / "data" / "context.sqlite"
        if ctx.exists():
            ctx.unlink()


privacy = PrivacyGuard()
