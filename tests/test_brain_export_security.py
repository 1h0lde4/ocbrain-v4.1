"""
Security regression tests for CTX-EXPORT-001 (KNOWN_ISSUES.md DEBT-019).

Covers the path-traversal-to-arbitrary-deletion primitive: import_module()
built a filesystem path directly from an attacker-controlled
manifest.json's module_name field, then shutil.rmtree()'d it, before any
validation ran. A module_name like "../../etc" pointed that deletion
outside modules/ entirely.
"""
import json
import zipfile
from pathlib import Path

import pytest

import core.brain_export as be


def _make_bundle(path: Path, module_name: str) -> Path:
    manifest = {
        "format": "ocbrain/1.0",
        "module_name": module_name,
        "stage": "bootstrap",
        "base_model": "mistral",
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
    return path


def test_path_traversal_module_name_cannot_delete_outside_modules_dir(tmp_path, monkeypatch):
    """The exact exploit: a module_name that walks outside modules/ via
    '..' must not let shutil.rmtree() reach anything outside it. Proven
    against a decoy directory that sits deliberately outside the
    redirected modules/ dir -- if this test's own setup pointed the
    traversal at something imaginary, it would pass for the wrong reason.
    """
    fake_repo = tmp_path / "fake_repo"
    (fake_repo / "modules").mkdir(parents=True)
    (fake_repo / "data").mkdir(parents=True)
    monkeypatch.setattr(be, "MODULES", fake_repo / "modules")
    monkeypatch.setattr(be, "DATA", fake_repo / "data")

    decoy = tmp_path / "victim_area" / "decoy_dir"
    decoy.mkdir(parents=True)
    (decoy / "important_file.txt").write_text("irreplaceable decoy content")
    assert decoy.exists()

    bundle = _make_bundle(tmp_path / "malicious.ocbrain", "../../victim_area/decoy_dir")

    # Deliberately not asserting on a specific exception type here: with
    # the pre-fix brain_export.py, the deletion happens, then a *different*
    # security control (RCE-001's containment gate in module_factory.py)
    # fires afterward and raises its own RuntimeError -- which would mask
    # this vulnerability entirely if this test required ValueError
    # specifically. The property that actually matters is unconditional:
    # regardless of what happens afterward, the decoy must survive.
    try:
        be.import_module(bundle, overwrite=True)
    except Exception:
        pass

    assert decoy.exists(), "CTX-EXPORT-001 regression: path traversal deleted outside modules/"
    assert (decoy / "important_file.txt").exists()


def test_legitimate_module_name_still_imports(tmp_path, monkeypatch):
    """The fix must not reject ordinary module names -- only ones shaped
    like a path."""
    fake_repo = tmp_path / "fake_repo"
    (fake_repo / "modules").mkdir(parents=True)
    (fake_repo / "data").mkdir(parents=True)
    monkeypatch.setattr(be, "MODULES", fake_repo / "modules")
    monkeypatch.setattr(be, "DATA", fake_repo / "data")

    import core.module_factory as factory_module
    monkeypatch.setattr(factory_module, "MODULES_DIR", fake_repo / "modules")
    monkeypatch.setattr(factory_module, "TEMPLATE_DIR", Path("modules/_template").resolve())

    import core.config as config_module
    monkeypatch.setattr(
        config_module.config, "get",
        lambda key, default=None: True if key == "global.module_factory_enabled" else default,
    )
    monkeypatch.setattr(config_module.config, "register_module", lambda *a, **k: None)
    monkeypatch.setattr(config_module.config, "set_module_state", lambda *a, **k: None)

    bundle = _make_bundle(tmp_path / "legit.ocbrain", "finance_helper")
    name = be.import_module(bundle, overwrite=True)
    assert name == "finance_helper"
    assert (fake_repo / "modules" / "finance_helper").exists()
