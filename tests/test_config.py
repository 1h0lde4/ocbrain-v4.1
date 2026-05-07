"""Tests for core/config.py"""
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def test_config_loads_defaults(tmp_path, monkeypatch):
    """Config loads and returns global settings."""
    # Point config at real config dir (read-only test)
    from core.config import config
    val = config.get("global.web_ui_port")
    assert val == 7437


def test_config_dot_path_access():
    from core.config import config
    val = config.get("privacy.save_history")
    assert isinstance(val, bool)


def test_config_missing_key_returns_default():
    from core.config import config
    val = config.get("nonexistent.deep.key", "fallback")
    assert val == "fallback"


def test_config_get_sources():
    from core.config import config
    sources = config.get_sources("coding")
    assert isinstance(sources, list)
    assert len(sources) > 0


def test_config_get_module_state():
    from core.config import config
    state = config.get_module_state("coding")
    assert "stage" in state
    assert state["stage"] in ("bootstrap", "shadow", "native")


def test_config_all_module_names():
    from core.config import config
    names = config.all_module_names()
    assert "coding" in names
    assert "web_search" in names
    assert "knowledge" in names
    assert "system_ctrl" in names


def test_config_get_module_keywords():
    from core.config import config
    kws = config.get_module_keywords("coding")
    assert isinstance(kws, list)
    assert len(kws) > 0
    assert "code" in kws or "write" in kws
