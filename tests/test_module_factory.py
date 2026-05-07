"""Tests for core/module_factory.py"""
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.module_factory import create
from core.config import config


def _cleanup(name):
    """Remove a test module if it exists."""
    dest = Path(__file__).parent.parent / "modules" / name
    if dest.exists():
        shutil.rmtree(dest)
    # Remove from config
    try:
        if name in config._models:
            del config._models[name]
        if name in config._settings.get("modules", {}):
            del config._settings["modules"][name]
        if name in config._sources:
            del config._sources[name]
    except Exception:
        pass


def test_create_module_scaffolds_files():
    name = "test_finance_tmp"
    _cleanup(name)
    try:
        path = create(
            name=name,
            desc="Financial analysis module",
            model="mistral",
            keywords=["stock", "market", "invest"],
            sources=["https://finance.yahoo.com"],
        )
        assert path.exists()
        assert (path / "module.py").exists()
        assert (path / "weights" / "active").exists()
        assert (path / "weights" / "previous").exists()
        assert (path / "weights" / "pending").exists()
    finally:
        _cleanup(name)


def test_create_module_substitutes_placeholders():
    name = "test_medical_tmp"
    _cleanup(name)
    try:
        path = create(
            name=name,
            desc="Medical knowledge module",
            model="mistral",
            keywords=["doctor", "medicine", "symptom"],
            sources=[],
        )
        content = (path / "module.py").read_text()
        assert "{{NAME}}" not in content
        assert "{{DESC}}" not in content
        assert name in content
        assert "Medical knowledge module" in content
    finally:
        _cleanup(name)


def test_create_duplicate_raises():
    name = "test_dup_tmp"
    _cleanup(name)
    try:
        create(name=name, desc="First", model="mistral", keywords=[], sources=[])
        with pytest.raises(ValueError, match="already exists"):
            create(name=name, desc="Second", model="mistral", keywords=[], sources=[])
    finally:
        _cleanup(name)


def test_create_invalid_name_raises():
    with pytest.raises(ValueError, match="Invalid module name"):
        create(
            name="my module!",   # spaces and ! are invalid
            desc="test",
            model="mistral",
            keywords=[],
            sources=[],
        )


def test_create_registers_in_config():
    name = "test_config_reg_tmp"
    _cleanup(name)
    try:
        create(
            name=name,
            desc="Test registration",
            model="llama3",
            keywords=["test", "check"],
            sources=["https://example.com"],
        )
        state   = config.get_module_state(name)
        sources = config.get_sources(name)
        kws     = config.get_module_keywords(name)

        assert state.get("stage") == "bootstrap"
        assert state.get("bootstrap_model") == "llama3"
        assert "https://example.com" in sources
        assert "test" in kws
    finally:
        _cleanup(name)
