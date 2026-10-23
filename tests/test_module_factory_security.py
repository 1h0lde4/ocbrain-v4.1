"""
Security regression tests for RCE-001 (KNOWN_ISSUES.md DEBT-021).

Covers:
  1. Containment -- module creation is disabled unless explicitly enabled,
     verified against a clean baseline without pre-setting the flag to false.
  2. The actual fix -- create() cannot be used to inject and execute
     arbitrary Python via the desc field, through the *real* end-to-end
     path (write generated source -> import it -> instantiate BaseModule),
     proving path, import, and ChromaDB/runtime storage isolation.
  3. Repeated create/import/instantiate/cleanup cycles within one process.
"""
import os
import sys
import shutil
from pathlib import Path

import pytest
import modules
import core.module_registry as registry_module
from modules import base as base_module
from core.config import Config
from core.module_factory import create
from core.module_registry import _namespace_for_root, reload_module
from modules.embedding_fn import HashEmbeddingFunction


def _is_beneath(path, root):
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _cleanup_imports_beneath(root):
    """Remove only import entries whose origin/search path is inside this temp tree."""
    root = Path(root).resolve()
    remove = []
    for module_name, module_obj in list(sys.modules.items()):
        locations = []
        origin = getattr(module_obj, "__file__", None)
        if origin:
            locations.append(origin)
        search_path = getattr(module_obj, "__path__", None)
        if search_path is not None:
            # Some third-party pseudo-packages expose a truthy but non-iterable
            # __path__ sentinel; cleanup must not turn that into a teardown error.
            try:
                locations.extend(list(search_path))
            except Exception:
                pass
        if any(_is_beneath(location, root) for location in locations):
            remove.append(module_name)
    for module_name in sorted(remove, key=lambda name: name.count("."), reverse=True):
        sys.modules.pop(module_name, None)


@pytest.fixture
def isolated_factory_env(tmp_path, monkeypatch):
    """Isolated environment for security tests."""
    tmp_config_dir = tmp_path / "config"
    tmp_config_dir.mkdir(parents=True, exist_ok=True)
    tmp_modules_dir = tmp_path / "modules"
    tmp_modules_dir.mkdir(parents=True, exist_ok=True)

    # Write clean default settings (factory disabled by default)
    (tmp_config_dir / "settings.toml").write_text("[global]\nlog_level = \"INFO\"\n")
    (tmp_config_dir / "models.toml").write_text("")
    (tmp_config_dir / "sources.toml").write_text("")

    test_cfg = Config(config_dir=tmp_config_dir, start_watcher=False)

    monkeypatch.setattr("modules.embedding_fn.get_embedding_function", lambda name: HashEmbeddingFunction())

    original_package_path = tuple(modules.__path__)
    original_sys_path = tuple(sys.path)
    original_registry_root = registry_module.MODULES_DIR
    original_base_root = base_module.MODULES_DIR
    try:
        yield test_cfg, tmp_modules_dir, tmp_config_dir
    finally:
        _cleanup_imports_beneath(tmp_path)
        assert tuple(modules.__path__) == original_package_path, (
            "security tests must not mutate the production modules package path"
        )
        assert tuple(sys.path) == original_sys_path, "security tests must not mutate sys.path"
        assert registry_module.MODULES_DIR == original_registry_root
        assert base_module.MODULES_DIR == original_base_root


def test_create_disabled_by_default(isolated_factory_env):
    """Refusal test against a clean baseline without first mutating the flag."""
    test_cfg, tmp_modules_dir, tmp_config_dir = isolated_factory_env

    # 1. Assert disabled value without first setting it to false
    assert test_cfg.get("global.module_factory_enabled", False) is False

    # 2. Call factory and assert expected refusal
    with pytest.raises(RuntimeError, match="RCE-001"):
        create(
            name="test_containment_tmp",
            desc="should never get created",
            model="mistral",
            keywords=[],
            sources=[],
            config_obj=test_cfg,
            modules_dir=tmp_modules_dir,
        )

    # 3. Assert no module directory created in temporary tree
    assert not (tmp_modules_dir / "test_containment_tmp").exists()

    # 4. Assert no module entry persisted in temporary config files
    models_txt = (tmp_config_dir / "models.toml").read_text()
    settings_txt = (tmp_config_dir / "settings.toml").read_text()
    sources_txt = (tmp_config_dir / "sources.toml").read_text()

    assert "test_containment_tmp" not in models_txt
    assert "test_containment_tmp" not in settings_txt
    assert "test_containment_tmp" not in sources_txt


def test_desc_field_cannot_break_out_of_generated_source(isolated_factory_env):
    """
    RCE-001: a desc value shaped exactly like the traced exploit (a quote
    that would have broken the old pre-quoted template, followed by
    class-body-indented statements) must not execute anything when the
    generated module is imported.
    """
    test_cfg, tmp_modules_dir, _ = isolated_factory_env
    test_cfg.set("global.module_factory_enabled", True)

    marker_key = "OCBRAIN_RCE001_TEST_MARKER"
    orig_marker_val = os.environ.get(marker_key)
    os.environ.pop(marker_key, None)

    payload = (
        'Legitimate-looking description"\n'
        '    import os\n'
        f'    os.environ["{marker_key}"] = "PWNED"\n'
        '    _unused = "'
    )

    name = "test_rce001_tmp"
    try:
        path = create(
            name=name,
            desc=payload,
            model="mistral",
            keywords=[],
            sources=[],
            config_obj=test_cfg,
            modules_dir=tmp_modules_dir,
        )

        assert path.exists()
        assert path.is_relative_to(tmp_modules_dir)
        generated = (path / "module.py").read_text()
        assert "\nimport os\n" not in generated

        instance = reload_module(name, {}, modules_dir=tmp_modules_dir)
        assert instance is not None, "reload_module() returned None"

        mod_sys_entry = sys.modules.get(instance.__class__.__module__)
        assert mod_sys_entry is not None
        imported_file = Path(mod_sys_entry.__file__).resolve()
        expected_file = (path / "module.py").resolve()
        assert imported_file == expected_file, (
            f"Registry imported {imported_file}, requested {expected_file}"
        )
        assert instance.root.resolve().is_relative_to(tmp_modules_dir.resolve()), (
            f"Module instance storage root {instance.root} is outside {tmp_modules_dir}"
        )

        assert os.environ.get(marker_key) is None, "RCE-001 regression: injected code executed"
        assert instance.desc == payload
    finally:
        if orig_marker_val is None:
            os.environ.pop(marker_key, None)
        else:
            os.environ[marker_key] = orig_marker_val


def test_name_field_also_uses_safe_literal_substitution(isolated_factory_env):
    test_cfg, tmp_modules_dir, _ = isolated_factory_env
    test_cfg.set("global.module_factory_enabled", True)

    name = "test_rce001_name_tmp"
    path = create(
        name=name, desc="plain desc", model="mistral",
        keywords=[], sources=[],
        config_obj=test_cfg, modules_dir=tmp_modules_dir,
    )
    assert path.is_relative_to(tmp_modules_dir)

    instance = reload_module(name, {}, modules_dir=tmp_modules_dir)
    assert instance is not None
    assert instance.name == name
    assert instance.root.resolve().is_relative_to(tmp_modules_dir.resolve())


def test_repeated_cycles_in_one_process(isolated_factory_env):
    """Run 10 consecutive create/import/instantiate/cleanup cycles in one process."""
    test_cfg, tmp_modules_dir, _ = isolated_factory_env
    test_cfg.set("global.module_factory_enabled", True)
    import_namespace = _namespace_for_root(tmp_modules_dir.resolve())

    for i in range(10):
        name = f"test_repeat_cycle_{i}"
        path = tmp_modules_dir / name
        instance = None
        try:
            path = create(
                name=name,
                desc=f"Cycle {i} description",
                model="mistral",
                keywords=[f"key{i}"],
                sources=[f"source_{i}"],
                config_obj=test_cfg,
                modules_dir=tmp_modules_dir,
            )
            assert path.is_relative_to(tmp_modules_dir)

            instance = reload_module(name, {}, modules_dir=tmp_modules_dir)
            assert instance is not None
            assert instance.name == name
            assert instance.desc == f"Cycle {i} description"

            imported_file = Path(sys.modules[instance.__class__.__module__].__file__).resolve()
            assert imported_file == (path / "module.py").resolve()
            assert instance.root.resolve() == (tmp_modules_dir / name).resolve()
        finally:
            # Cleanup also runs when creation, import, or an assertion fails;
            # no private package/cache entries survive into the next cycle.
            for cached_name in list(sys.modules):
                if cached_name == import_namespace or cached_name.startswith(import_namespace + "."):
                    sys.modules.pop(cached_name, None)
            if path.exists():
                shutil.rmtree(path)
            importlib.invalidate_caches()
            instance = None
