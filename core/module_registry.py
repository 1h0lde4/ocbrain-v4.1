"""
core/module_registry.py — root-bound discovery and loading for module packages.

A caller-supplied modules_dir is authoritative for both imported source and
BaseModule-managed storage. Modules are loaded under a private package namespace
derived from that canonical root, so stale modules in the ordinary modules.*
namespace cannot redirect a load to another tree.
"""
import hashlib
import importlib.machinery
import importlib.util
import sys
import threading
import types
from pathlib import Path
from typing import Optional

from core.module_paths import module_child
from modules.base import BaseModule, module_storage_root

MODULES_DIR = Path(__file__).parent.parent / "modules"
_SKIP = {"__pycache__", "_template", "base"}
_NAMESPACE_PREFIX = "_ocbrain_registry_"
_REGISTRY_LOCK = threading.RLock()


def _namespace_for_root(root: Path) -> str:
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:20]
    return f"{_NAMESPACE_PREFIX}{digest}"


def _remove_import_tree(prefix: str) -> None:
    """Remove one cached import tree and detach its parent's attribute."""
    old_module = sys.modules.get(prefix)
    parent_name, _, leaf = prefix.rpartition(".")
    parent = sys.modules.get(parent_name) if parent_name else None
    if parent is not None and hasattr(parent, leaf):
        attached = getattr(parent, leaf)
        if old_module is None or attached is old_module:
            delattr(parent, leaf)
    names = [
        name for name in list(sys.modules)
        if name == prefix or name.startswith(prefix + ".")
    ]
    for name in sorted(names, key=lambda item: item.count("."), reverse=True):
        sys.modules.pop(name, None)


def _package_paths(package: object) -> tuple[str, ...]:
    paths = getattr(package, "__path__", None)
    if paths is None:
        return ()
    try:
        return tuple(str(Path(item).resolve()) for item in paths)
    except (OSError, RuntimeError, TypeError, ValueError):
        return ()


def _package_matches(package: object, path: Path, init_file: Path | None) -> bool:
    if _package_paths(package) != (str(path.resolve()),):
        return False
    origin = getattr(package, "__file__", None)
    if init_file is None:
        return origin is None
    try:
        return origin is not None and Path(origin).resolve(strict=True) == init_file.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _ensure_package(name: str, path: Path, init_file: Path | None = None):
    """Create or validate a package whose search path is exactly path."""
    path = path.resolve()
    if init_file is not None:
        init_file = init_file.resolve(strict=True)
        if init_file != path / "__init__.py" or not init_file.is_file():
            raise ImportError("Module package initializer is outside the requested root")

    current = sys.modules.get(name)
    if current is not None and _package_matches(current, path, init_file):
        return current

    _remove_import_tree(name)

    if init_file is not None:
        spec = importlib.util.spec_from_file_location(
            name, str(init_file), submodule_search_locations=[str(path)]
        )
        if spec is None or spec.loader is None:
            raise ImportError("Unable to load module package initializer")
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        try:
            spec.loader.exec_module(package)
        except Exception:
            _remove_import_tree(name)
            raise
        if not _package_matches(package, path, init_file):
            _remove_import_tree(name)
            raise ImportError("Module package changed its requested import root")
    else:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        package.__package__ = name
        spec = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
        spec.submodule_search_locations = [str(path)]
        package.__spec__ = spec
        sys.modules[name] = package

    parent_name, _, leaf = name.rpartition(".")
    parent = sys.modules.get(parent_name) if parent_name else None
    if parent is not None:
        setattr(parent, leaf, package)
    return package


def _source_for_module(root: Path, module_name: str) -> tuple[Path, Path]:
    """Resolve a module entry and reject directory/file symlinks outside root."""
    root = root.resolve()
    module_dir = module_child(root, module_name)
    source = module_dir / "module.py"
    if not source.is_file():
        raise FileNotFoundError("Module source does not exist")
    resolved_source = source.resolve(strict=True)
    if resolved_source != source or resolved_source.parent != module_dir:
        raise ImportError("Module source is not a regular file inside the requested root")

    init_file = module_dir / "__init__.py"
    if init_file.exists() or init_file.is_symlink():
        resolved_init = init_file.resolve(strict=True)
        if resolved_init != init_file or not resolved_init.is_file():
            raise ImportError("Module initializer is not a regular file inside the requested root")
    return module_dir, resolved_source


def _validate_managed_storage_paths(module_root: Path) -> None:
    """Refuse pre-existing storage symlinks before a constructor can write through them."""
    module_root = module_root.resolve()
    relatives = (
        Path("weights"),
        Path("weights/active"),
        Path("weights/previous"),
        Path("weights/pending"),
        Path("knowledge.db"),
    )
    for relative in relatives:
        candidate = module_root / relative
        if candidate.is_symlink():
            raise RuntimeError(
                f"Module storage path '{relative.as_posix()}' must not be a symlink"
            )
        if candidate.exists():
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise RuntimeError(
                    f"Module storage path '{relative.as_posix()}' cannot be resolved safely"
                ) from exc
            if resolved != candidate:
                raise RuntimeError(
                    f"Module storage path '{relative.as_posix()}' escapes its module directory"
                )


def _import_module_from_root(root: Path, module_name: str):
    root = root.resolve()
    module_dir, source = _source_for_module(root, module_name)
    namespace = _namespace_for_root(root)
    _ensure_package(namespace, root)

    name_digest = hashlib.sha256(module_name.encode("utf-8")).hexdigest()[:20]
    package_name = f"{namespace}._module_{name_digest}"
    init_file = module_dir / "__init__.py"
    _ensure_package(package_name, module_dir, init_file if init_file.is_file() else None)

    qualified_name = f"{package_name}.module"
    _remove_import_tree(qualified_name)
    spec = importlib.util.spec_from_file_location(qualified_name, str(source))
    if spec is None or spec.loader is None:
        raise ImportError("Unable to create a loader for the requested module source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified_name] = module
    package = sys.modules[package_name]
    setattr(package, "module", module)
    try:
        spec.loader.exec_module(module)
    except Exception:
        _remove_import_tree(qualified_name)
        raise

    try:
        imported_source = Path(module.__file__).resolve(strict=True)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        _remove_import_tree(qualified_name)
        raise ImportError("Imported module has no verifiable source path") from exc
    if imported_source != source:
        _remove_import_tree(qualified_name)
        raise ImportError("Imported module source does not match the requested root")
    if not _package_matches(sys.modules[package_name], module_dir, init_file if init_file.is_file() else None):
        _remove_import_tree(qualified_name)
        raise ImportError("Imported module package no longer points at the requested root")
    return module


def _instantiate_from_root(module, module_name: str, root: Path) -> BaseModule:
    module_class = getattr(module, "Module", None)
    if not isinstance(module_class, type) or not issubclass(module_class, BaseModule):
        raise TypeError("Module is not a BaseModule subclass")
    if getattr(module_class, "name", None) != module_name:
        raise TypeError("Module class name does not match its registry directory")

    expected_root = module_child(root, module_name).resolve()
    _validate_managed_storage_paths(expected_root)

    # This context overrides constructor defaults. Legacy subclasses that call
    # super().__init__() still create weights and ChromaDB beneath this root.
    with module_storage_root(root):
        instance = module_class()

    if not isinstance(instance, BaseModule):
        raise TypeError("Module constructor did not produce a BaseModule")
    try:
        instance_root = Path(instance.root).resolve(strict=True)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise RuntimeError("Module did not expose a valid storage root") from exc
    if instance_root != expected_root:
        raise RuntimeError("Module storage root does not match the requested module directory")
    if not (instance_root / "knowledge.db").is_dir():
        raise RuntimeError("Module ChromaDB storage was not created under the requested root")
    return instance


def load_all(modules_dir: Path | None = None) -> dict[str, BaseModule]:
    """
    Return {module_name: instance} for modules under the requested directory.

    Passing modules_dir binds import resolution and BaseModule-managed storage to
    that root; no global package path or sys.path mutation is needed.
    """
    target_modules_dir = Path(modules_dir if modules_dir is not None else MODULES_DIR).resolve()
    modules: dict[str, BaseModule] = {}

    for path in sorted(target_modules_dir.iterdir()):
        if not path.is_dir() or path.name in _SKIP or path.name.startswith("."):
            continue
        if not (path / "module.py").is_file():
            continue

        try:
            with _REGISTRY_LOCK:
                module_file = _import_module_from_root(target_modules_dir, path.name)
                instance = _instantiate_from_root(module_file, path.name, target_modules_dir)
                modules[path.name] = instance
            print(f"[registry] Loaded module: {path.name} (stage={instance.health()['stage']})")
        except Exception as exc:
            print(f"[registry] Failed to load {path.name}: {exc}")

    return modules


def reload_module(
    module_name: str,
    existing: dict,
    modules_dir: Path | None = None,
) -> Optional[BaseModule]:
    """Reload one module from the requested root after a weight update."""
    target_modules_dir = Path(modules_dir if modules_dir is not None else MODULES_DIR).resolve()
    try:
        _source_for_module(target_modules_dir, module_name)
    except FileNotFoundError:
        return None

    try:
        with _REGISTRY_LOCK:
            module_file = _import_module_from_root(target_modules_dir, module_name)
            instance = _instantiate_from_root(module_file, module_name, target_modules_dir)
            existing[module_name] = instance
        return instance
    except Exception as exc:
        print(f"[registry] Failed to reload {module_name}: {exc}")
        return None
