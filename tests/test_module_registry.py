"""Regression tests for root-bound dynamic module discovery and loading."""
import sys
import types
from pathlib import Path

import pytest
import modules

from core.config import Config
from core.module_factory import create
from core.module_registry import load_all, reload_module
from modules.base import BaseModule
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
        if search_path:
            locations.extend(list(search_path))
        if any(_is_beneath(location, root) for location in locations):
            remove.append(module_name)
    for module_name in sorted(remove, key=lambda name: name.count("."), reverse=True):
        sys.modules.pop(module_name, None)


@pytest.fixture
def registry_env(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.toml").write_text(
        '[global]\nmodule_factory_enabled = true\nlog_level = "INFO"\n'
    )
    (config_dir / "models.toml").write_text("")
    (config_dir / "sources.toml").write_text("")
    config = Config(config_dir=config_dir, start_watcher=False)

    root_a = tmp_path / "modules_a"
    root_b = tmp_path / "modules_b"
    root_a.mkdir()
    root_b.mkdir()
    monkeypatch.setattr(
        "modules.embedding_fn.get_embedding_function",
        lambda name: HashEmbeddingFunction(),
    )

    original_package_path = tuple(modules.__path__)
    try:
        yield config, root_a, root_b, tmp_path
    finally:
        _cleanup_imports_beneath(tmp_path)
        assert tuple(modules.__path__) == original_package_path, (
            "registry loading must not mutate modules.__path__"
        )


def _create_probe(config, root, desc):
    return create(
        name="registry_root_probe",
        desc=desc,
        model="mistral",
        keywords=["registry"],
        sources=[],
        config_obj=config,
        modules_dir=root,
    )


def _assert_loaded_from(instance, root, desc):
    assert isinstance(instance, BaseModule)
    module_object = sys.modules[instance.__class__.__module__]
    expected_source = (root / "registry_root_probe" / "module.py").resolve()
    assert Path(module_object.__file__).resolve() == expected_source
    assert instance.desc == desc
    expected_storage = (root / "registry_root_probe").resolve()
    assert Path(instance.root).resolve() == expected_storage
    assert Path(instance.root).resolve().is_relative_to(Path(root).resolve())
    assert (Path(instance.root) / "knowledge.db").is_dir()


def test_load_all_and_reload_module_honor_requested_root_despite_cached_name(
    registry_env, monkeypatch
):
    config, root_a, root_b, _ = registry_env
    path_a = _create_probe(config, root_a, "defined in root A")
    path_b = _create_probe(config, root_b, "defined in root B")
    assert path_a == root_a / "registry_root_probe"
    assert path_b == root_b / "registry_root_probe"

    # Load A through the public registry API first.
    loaded_a = load_all(modules_dir=root_a)["registry_root_probe"]
    _assert_loaded_from(loaded_a, root_a, "defined in root A")
    module_a = sys.modules[loaded_a.__class__.__module__]

    # Seed the stale canonical modules.<name>.module cache that previously
    # hijacked imports. The new registry must ignore it and bind B's source to
    # its own root, without changing modules.__path__ or MODULES_DIR.
    legacy_package_name = "modules.registry_root_probe"
    legacy_module_name = legacy_package_name + ".module"
    legacy_package = types.ModuleType(legacy_package_name)
    legacy_package.__path__ = [str(path_a)]
    monkeypatch.setitem(sys.modules, legacy_package_name, legacy_package)
    monkeypatch.setitem(sys.modules, legacy_module_name, module_a)
    monkeypatch.setattr(modules, "registry_root_probe", legacy_package, raising=False)

    loaded_b_by_reload = reload_module("registry_root_probe", {}, modules_dir=root_b)
    assert loaded_b_by_reload is not None
    _assert_loaded_from(loaded_b_by_reload, root_b, "defined in root B")

    loaded_b_by_discovery = load_all(modules_dir=root_b)["registry_root_probe"]
    _assert_loaded_from(loaded_b_by_discovery, root_b, "defined in root B")

    # Loading B must not poison the independently-scoped root A either.
    loaded_a_again = reload_module("registry_root_probe", {}, modules_dir=root_a)
    assert loaded_a_again is not None
    _assert_loaded_from(loaded_a_again, root_a, "defined in root A")


def test_load_all_rejects_directory_and_file_symlinks_outside_root(registry_env):
    _, requested_root, _, tmp_path = registry_env
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    directory_target = outside_root / "directory_target"
    directory_target.mkdir()
    file_target_dir = outside_root / "file_target"
    file_target_dir.mkdir()

    directory_marker = tmp_path / "directory_payload_executed"
    file_marker = tmp_path / "file_payload_executed"
    (directory_target / "module.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(directory_marker)!r}).write_text('executed')\n"
    )
    external_file = file_target_dir / "payload.py"
    external_file.write_text(
        "from pathlib import Path\n"
        f"Path({str(file_marker)!r}).write_text('executed')\n"
    )
    file_link_dir = requested_root / "file_link"
    file_link_dir.mkdir()

    try:
        (requested_root / "directory_link").symlink_to(directory_target, target_is_directory=True)
        (file_link_dir / "module.py").symlink_to(external_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this platform")

    assert load_all(modules_dir=requested_root) == {}
    assert not directory_marker.exists()
    assert not file_marker.exists()
    assert not (directory_target / "knowledge.db").exists()
    assert not (file_link_dir / "knowledge.db").exists()


def test_registry_root_context_is_reset_after_loading(registry_env):
    from modules import base as base_module

    config, root_a, root_b, _ = registry_env
    _create_probe(config, root_a, "root A")
    _create_probe(config, root_b, "root B")
    load_all(modules_dir=root_a)

    loaded_b = reload_module("registry_root_probe", {}, modules_dir=root_b)
    assert loaded_b is not None
    _assert_loaded_from(loaded_b, root_b, "root B")
    assert base_module._ACTIVE_MODULES_DIR.get() is None



def test_registry_rejects_module_class_name_mismatch_before_storage_write(registry_env):
    _, requested_root, _, _ = registry_env
    module_dir = requested_root / "requested_name"
    module_dir.mkdir()
    # The class is intentionally abstract: reject its name mismatch before
    # trying construction or creating any storage.
    (module_dir / "module.py").write_text(
        "from modules.base import BaseModule\n"
        "class Module(BaseModule):\n"
        "    name = 'different_name'\n"
    )

    assert load_all(modules_dir=requested_root) == {}
    assert not (requested_root / "different_name").exists()
    assert not (module_dir / "knowledge.db").exists()
