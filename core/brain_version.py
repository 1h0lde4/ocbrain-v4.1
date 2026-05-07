"""
core/brain_version.py — Separate version tracking for brain state.
App version and brain version evolve independently.
Brain version persists across app upgrades.

brain_version  = state of trained weights + KB + context
app_version    = code version (pyproject.toml / version.txt)
"""
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

BRAIN_STATE_PATH = Path(__file__).parent.parent / "data" / "brain_state.json"
APP_VERSION_PATH = Path(__file__).parent.parent / "version.txt"


@dataclass
class ModuleBrainState:
    name: str
    stage: str                       # bootstrap | shadow | native
    base_model: str                  # e.g. "mistral:7b"
    lora_version: int = 0            # increments each training run
    total_training_pairs: int = 0
    total_kb_chunks: int = 0
    last_trained: str = ""
    created_at: str = ""


@dataclass
class BrainState:
    brain_version: str = "2.0.0"
    app_version: str = "2.0.0"
    created_at: str = ""
    last_updated: str = ""
    schema_version: int = 2          # increments when migrations run
    modules: dict = field(default_factory=dict)
    total_queries_handled: int = 0
    distillation_runs: int = 0

    def __post_init__(self):
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.created_at:
            self.created_at = now
        if not self.last_updated:
            self.last_updated = now


class BrainVersionManager:
    def __init__(self):
        BRAIN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def _load(self) -> BrainState:
        if BRAIN_STATE_PATH.exists():
            try:
                data = json.loads(BRAIN_STATE_PATH.read_text())
                return BrainState(**{
                    k: v for k, v in data.items()
                    if k in BrainState.__dataclass_fields__
                })
            except Exception:
                pass
        return BrainState()

    def _save(self):
        self._state.last_updated = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        BRAIN_STATE_PATH.write_text(
            json.dumps(asdict(self._state), indent=2)
        )

    @property
    def brain_version(self) -> str:
        return self._state.brain_version

    @property
    def app_version(self) -> str:
        try:
            return APP_VERSION_PATH.read_text().strip()
        except Exception:
            return "2.0.0"

    @property
    def schema_version(self) -> int:
        return self._state.schema_version

    def get_state(self) -> BrainState:
        return self._state

    def update_module(self, name: str, **kwargs):
        """Update brain state for a specific module."""
        if name not in self._state.modules:
            self._state.modules[name] = asdict(ModuleBrainState(name=name, **{
                k: v for k, v in kwargs.items()
                if k in ModuleBrainState.__dataclass_fields__
            }))
        else:
            self._state.modules[name].update(kwargs)
        self._state.modules[name]["name"] = name
        self._save()

    def record_training(self, module_name: str, new_pairs: int):
        mod = self._state.modules.setdefault(module_name, {})
        mod["lora_version"] = mod.get("lora_version", 0) + 1
        mod["total_training_pairs"] = mod.get("total_training_pairs", 0) + new_pairs
        mod["last_trained"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._save()

    def record_query(self):
        self._state.total_queries_handled += 1
        if self._state.total_queries_handled % 100 == 0:
            self._save()

    def record_distillation(self):
        self._state.distillation_runs += 1
        self._save()

    def bump_schema(self, new_version: int):
        self._state.schema_version = new_version
        self._save()

    def to_dict(self) -> dict:
        return asdict(self._state)

    def needs_migration(self) -> bool:
        """True if brain schema is behind current app's expected schema."""
        return self._state.schema_version < 2   # update as schema evolves


brain_version_manager = BrainVersionManager()
