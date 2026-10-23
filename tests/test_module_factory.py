"""Tests for core/module_factory.py"""
import importlib
import sys
import shutil
from pathlib import Path

import pytest
import modules
from core.module_factory import create
from core.config import Config
from modules.embedding_fn import HashEmbeddingFunction


@pytest.fixture
def isolated_factory_env(tmp_path, monkeypatch):
    """Isolated configuration, module directory, and import environment
    for module_factory tests."""
    tmp_config_dir = tmp_path / "config"
    tmp_config_dir.mkdir(parents=True, exist_ok=True)
    tmp_modules_dir = tmp_path / "modules"
    tmp_modules_dir.mkdir(parents=True, exist_ok=True)

    (tmp_config_dir / "settings.toml").write_text("[global]\nmodule_factory_enabled = true\n")
    (tmp_config_dir / "models.toml").write_text("")
    (tmp_config_dir / "sources.toml").write_text("")

    test_cfg = Config(config_dir=tmp_config_dir, start_watcher=False)

    monkeypatch.setattr("core.module_factory.config", test_cfg)
    monkeypatch.setattr("core.module_factory.MODULES_DIR", tmp_modules_dir)
    monkeypatch.setattr("core.module_registry.MODULES_DIR", tmp_modules_dir)
    monkeypatch.setattr("modules.base.MODULES_DIR", tmp_modules_dir)

    monkeypatch.setattr("modules.embedding_fn.get_embedding_function", lambda name: HashEmbeddingFunction())

    orig_path = list(modules.__path__)
    monkeypatch.setattr(modules, "__path__", [str(tmp_modules_dir)] + orig_path)
    importlib.invalidate_caches()

    yield test_cfg, tmp_modules_dir, tmp_config_dir

    importlib.invalidate_caches()


def test_create_module_scaffolds_files(isolated_factory_env):
    test_cfg, tmp_modules_dir, _ = isolated_factory_env
    name = "test_finance_tmp"
    path = create(
        name=name,
        desc="Financial analysis module",
        model="mistral",
        keywords=["stock", "market", "invest"],
        sources=["source_finance_1"],
        config_obj=test_cfg,
        modules_dir=tmp_modules_dir,
    )
    assert path.exists()
    assert path.is_relative_to(tmp_modules_dir)
    assert (path / "module.py").exists()
    assert (path / "weights" / "active").exists()
    assert (path / "weights" / "previous").exists()
    assert (path / "weights" / "pending").exists()


def test_create_module_substitutes_placeholders(isolated_factory_env):
    test_cfg, tmp_modules_dir, _ = isolated_factory_env
    name = "test_medical_tmp"
    path = create(
        name=name,
        desc="Medical knowledge module",
        model="mistral",
        keywords=["doctor", "medicine", "symptom"],
        sources=[],
        config_obj=test_cfg,
        modules_dir=tmp_modules_dir,
    )
    content = (path / "module.py").read_text()
    assert "{{NAME}}" not in content
    assert "{{DESC}}" not in content
    assert name in content
    assert "Medical knowledge module" in content


def test_create_duplicate_raises(isolated_factory_env):
    test_cfg, tmp_modules_dir, _ = isolated_factory_env
    name = "test_dup_tmp"
    create(
        name=name, desc="First", model="mistral", keywords=[], sources=[],
        config_obj=test_cfg, modules_dir=tmp_modules_dir,
    )
    with pytest.raises(ValueError, match="already exists"):
        create(
            name=name, desc="Second", model="mistral", keywords=[], sources=[],
            config_obj=test_cfg, modules_dir=tmp_modules_dir,
        )


def test_create_invalid_name_raises(isolated_factory_env):
    test_cfg, tmp_modules_dir, _ = isolated_factory_env
    with pytest.raises(ValueError, match="Invalid module name"):
        create(
            name="my module!",   # spaces and ! are invalid
            desc="test",
            model="mistral",
            keywords=[],
            sources=[],
            config_obj=test_cfg,
            modules_dir=tmp_modules_dir,
        )


def test_create_registers_in_config(isolated_factory_env):
    test_cfg, tmp_modules_dir, tmp_config_dir = isolated_factory_env
    name = "test_config_reg_tmp"
    create(
        name=name,
        desc="Test registration",
        model="llama3",
        keywords=["test", "check"],
        sources=["source_entry_1"],
        config_obj=test_cfg,
        modules_dir=tmp_modules_dir,
    )
    state   = test_cfg.get_module_state(name)
    sources = test_cfg.get_sources(name)
    kws     = test_cfg.get_module_keywords(name)

    assert state.get("stage") == "bootstrap"
    assert state.get("bootstrap_model") == "llama3"
    assert sources == ["source_entry_1"]
    assert "test" in kws

    # Verify readback from disk using a fresh isolated Config instance
    readback_cfg = Config(config_dir=tmp_config_dir, start_watcher=False)
    assert readback_cfg.get_module_state(name).get("bootstrap_model") == "llama3"
    assert readback_cfg.get_sources(name) == ["source_entry_1"]
    assert "test" in readback_cfg.get_module_keywords(name)
