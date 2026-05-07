"""
core/module_registry.py — Auto-discovers all modules at startup.
Scans modules/ for any folder containing a valid module.py with a Module class.
No manual import needed anywhere — just drop in a folder.
"""
import importlib
import sys
from pathlib import Path
from typing import Optional

from modules.base import BaseModule

MODULES_DIR = Path(__file__).parent.parent / "modules"
_SKIP = {"__pycache__", "_template", "base"}


def load_all() -> dict[str, BaseModule]:
    """
    Returns dict of {module_name: Module instance}.
    Called once at startup by main.py.
    """
    modules: dict[str, BaseModule] = {}

    for path in sorted(MODULES_DIR.iterdir()):
        if not path.is_dir():
            continue
        if path.name in _SKIP or path.name.startswith("."):
            continue
        mod_file = path / "module.py"
        if not mod_file.exists():
            continue

        try:
            # Ensure modules dir is importable
            root = str(MODULES_DIR.parent)
            if root not in sys.path:
                sys.path.insert(0, root)

            mod_path = f"modules.{path.name}.module"
            module   = importlib.import_module(mod_path)
            instance = module.Module()

            # Validate it's a proper BaseModule subclass
            if not isinstance(instance, BaseModule):
                print(f"[registry] Skipping {path.name}: Module is not a BaseModule subclass")
                continue

            modules[path.name] = instance
            print(f"[registry] Loaded module: {path.name} (stage={instance.health()['stage']})")

        except Exception as e:
            print(f"[registry] Failed to load {path.name}: {e}")

    return modules


def reload_module(module_name: str, existing: dict) -> Optional[BaseModule]:
    """Hot-reload a single module after weight update."""
    path = MODULES_DIR / module_name / "module.py"
    if not path.exists():
        return None
    try:
        mod_path = f"modules.{module_name}.module"
        if mod_path in sys.modules:
            importlib.reload(sys.modules[mod_path])
        module   = importlib.import_module(mod_path)
        instance = module.Module()
        existing[module_name] = instance
        return instance
    except Exception as e:
        print(f"[registry] Failed to reload {module_name}: {e}")
        return None
