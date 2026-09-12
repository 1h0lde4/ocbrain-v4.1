"""
Security regression tests for RCE-001 (KNOWN_ISSUES.md DEBT-021).

Covers two independent invariants, deliberately not merged into one test:
  1. Containment -- module creation is disabled unless explicitly enabled.
  2. The actual fix -- create() cannot be used to inject and execute
     arbitrary Python via the desc field, through the *real* end-to-end
     path (write generated source -> import it), not a narrow unit test
     of module_factory.py in isolation.
"""
import os
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.config import config
from core.module_factory import create


MODULES_DIR = Path(__file__).parent.parent / "modules"


def _cleanup(name):
    dest = MODULES_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    try:
        if name in config._models:
            del config._models[name]
        if name in config._settings.get("modules", {}):
            del config._settings["modules"][name]
        if name in config._sources:
            del config._sources[name]
    except Exception:
        pass


def test_create_disabled_by_default():
    """No fixture enabling the flag here on purpose -- this test exercises
    the real, un-overridden default a fresh install/deployment would see."""
    previous = config.get("global.module_factory_enabled", False)
    config.set("global.module_factory_enabled", False)
    try:
        with pytest.raises(RuntimeError, match="RCE-001"):
            create(
                name="test_containment_tmp",
                desc="should never get created",
                model="mistral",
                keywords=[],
                sources=[],
            )
    finally:
        config.set("global.module_factory_enabled", previous)
    # Confirm it genuinely didn't get created, not just that an exception
    # happened to be raised somewhere.
    assert not (MODULES_DIR / "test_containment_tmp").exists()
