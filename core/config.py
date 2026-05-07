"""
core/config.py — Single access point for ALL config files.
Loads: settings.toml, sources.toml, models.toml (existing)
       settings.yaml, user_prefs.yaml            (new in user's version)
Hot-reloads on file change. No restart needed for most settings.
"""
import sys
import threading
import time
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w
import yaml   # FIX BUG 5+6: load YAML config files

CONFIG_DIR = Path(__file__).parent.parent / "config"


class Config:
    def __init__(self):
        self._lock = threading.RLock()
        self._settings: dict = {}
        self._sources: dict  = {}
        self._models: dict   = {}
        self._yaml_settings: dict = {}   # from settings.yaml
        self._user_prefs: dict    = {}   # from user_prefs.yaml
        self._load_all()
        self._start_watcher()

    def _load_all(self):
        with self._lock:
            self._settings      = self._read_toml(CONFIG_DIR / "settings.toml")
            self._sources       = self._read_toml(CONFIG_DIR / "sources.toml")
            self._models        = self._read_toml(CONFIG_DIR / "models.toml")
            self._yaml_settings = self._read_yaml(CONFIG_DIR / "settings.yaml")
            self._user_prefs    = self._read_yaml(CONFIG_DIR / "user_prefs.yaml")

    def _read_toml(self, path: Path) -> dict:
        if not path.exists():
            return {}
        with open(path, "rb") as f:
            return tomllib.load(f)

    def _read_yaml(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[config] Failed to load {path.name}: {e}")
            return {}

    def _start_watcher(self):
        def _watch():
            mtimes = {}
            files = [
                CONFIG_DIR / "settings.toml",
                CONFIG_DIR / "sources.toml",
                CONFIG_DIR / "models.toml",
                CONFIG_DIR / "settings.yaml",
                CONFIG_DIR / "user_prefs.yaml",
            ]
            while True:
                for f in files:
                    try:
                        mt = f.stat().st_mtime
                        if mtimes.get(str(f)) != mt:
                            mtimes[str(f)] = mt
                            self._load_all()
                    except FileNotFoundError:
                        pass
                time.sleep(2)

        t = threading.Thread(target=_watch, daemon=True)
        t.start()

    # ── TOML access (dot-path) ────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-path access into settings.toml: config.get('global.ollama_host')"""
        with self._lock:
            parts = key.split(".")
            obj   = self._settings
            for p in parts:
                if not isinstance(obj, dict):
                    return default
                obj = obj.get(p)
                if obj is None:
                    return default
            return obj

    def set(self, key: str, value: Any):
        """Write a value back to settings.toml."""
        with self._lock:
            parts = key.split(".")
            obj   = self._settings
            for p in parts[:-1]:
                obj = obj.setdefault(p, {})
            obj[parts[-1]] = value
            with open(CONFIG_DIR / "settings.toml", "wb") as f:
                tomli_w.dump(self._settings, f)

    # ── YAML access ───────────────────────────────────────────

    def get_yaml(self, key: str, default: Any = None) -> Any:
        """Dot-path access into settings.yaml: config.get_yaml('orchestrator.max_parallel_modules')"""
        with self._lock:
            parts = key.split(".")
            obj   = self._yaml_settings
            for p in parts:
                if not isinstance(obj, dict):
                    return default
                obj = obj.get(p)
                if obj is None:
                    return default
            return obj

    def get_user_pref(self, key: str, default: Any = None) -> Any:
        """Dot-path access into user_prefs.yaml: config.get_user_pref('user.language')"""
        with self._lock:
            parts = key.split(".")
            obj   = self._user_prefs
            for p in parts:
                if not isinstance(obj, dict):
                    return default
                obj = obj.get(p)
                if obj is None:
                    return default
            return obj

    def get_user_trusted_sources(self, module_name: str) -> list[str]:
        """Get trusted sources from user_prefs.yaml for a module."""
        return self.get_user_pref(f"modules.{module_name}.trusted_sources", [])

    # ── Unified source lookup ─────────────────────────────────

    def get_sources(self, module_name: str) -> list[str]:
        """
        Merge sources from sources.toml AND user_prefs.yaml.
        User prefs take precedence; duplicates removed.
        """
        with self._lock:
            toml_sources = self._sources.get(module_name, {}).get("sources", [])
            yaml_sources = self.get_user_trusted_sources(module_name)
            merged = list(dict.fromkeys(toml_sources + yaml_sources))
            return merged

    def get_module_state(self, module_name: str) -> dict:
        with self._lock:
            return dict(self._models.get(module_name, {}))

    def set_module_state(self, module_name: str, key: str, value: Any):
        with self._lock:
            if module_name not in self._models:
                self._models[module_name] = {}
            self._models[module_name][key] = value
            with open(CONFIG_DIR / "models.toml", "wb") as f:
                tomli_w.dump(self._models, f)

    def get_module_keywords(self, module_name: str) -> list[str]:
        with self._lock:
            return self._settings.get("modules", {}).get(
                module_name, {}
            ).get("keywords", [])

    def all_module_names(self) -> list[str]:
        with self._lock:
            return list(self._models.keys())

    def register_module(self, name: str, model: str, keywords: list[str], sources: list[str]):
        """Called by module_factory after scaffolding a new module."""
        with self._lock:
            self._models[name] = {
                "stage": "bootstrap", "maturity_score": 0.0,
                "query_count": 0, "bootstrap_model": model,
                "base_model": "mistral:7b", "active_weights": "",
                "last_trained": "", "train_pairs": 0,
            }
            with open(CONFIG_DIR / "models.toml", "wb") as f:
                tomli_w.dump(self._models, f)

            self._settings.setdefault("modules", {})[name] = {
                "enabled": True, "keywords": keywords,
                "staleness_decay": True, "max_kb_size_mb": 500,
                "confidence_boost": 0.1, "pin_to_external": False,
            }
            with open(CONFIG_DIR / "settings.toml", "wb") as f:
                tomli_w.dump(self._settings, f)

            self._sources[name] = {"sources": sources}
            with open(CONFIG_DIR / "sources.toml", "wb") as f:
                tomli_w.dump(self._sources, f)

    def get_yaml_all(self) -> dict:
        """Return full yaml settings dict (for API /config endpoint)."""
        with self._lock:
            return {
                "toml": self._settings,
                "yaml": self._yaml_settings,
                "user_prefs": self._user_prefs,
            }


# Global singleton
config = Config()
