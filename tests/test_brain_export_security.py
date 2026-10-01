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


# ---------------------------------------------------------------------------
# export_module(): the same traversal class as CTX-EXPORT-001, on the sibling
# function. CTX-EXPORT-001 validated the manifest's module_name in
# import_module() but export_module() takes module_name straight from the
# request body (interface/api.py POST /export AND core/brain_api.py's
# /export route -- two HTTP entry points into one sink) and used it, unvalidated,
# to build five different paths: MODULES/<name>, DATA/evals/<name>.json,
# DATA/raw/<name>, and the output bundle's own filename. Its only check was
# mod_dir.exists(), which is not a containment check.
# ---------------------------------------------------------------------------

from types import SimpleNamespace

SECRET = "SECRET-OUTSIDE-MODULES-DIR"


@pytest.fixture
def export_sandbox(tmp_path, monkeypatch):
    """A fake repo mirroring the real layout (modules/, data/exports/ are
    siblings under a root) with a decoy directory that sits *outside*
    modules/ -- and, importantly, reachable such that the output bundle's
    own path also resolves somewhere writable. Without that second
    property an exploit attempt would fail at ZipFile() for an unrelated
    reason and this test would pass on unfixed code for the wrong reason.
    """
    fake_repo = tmp_path / "fake_repo"
    (fake_repo / "modules" / "legit_module").mkdir(parents=True)
    (fake_repo / "data").mkdir(parents=True)
    exports = fake_repo / "data" / "exports"

    monkeypatch.setattr(be, "ROOT", fake_repo)
    monkeypatch.setattr(be, "MODULES", fake_repo / "modules")
    monkeypatch.setattr(be, "DATA", fake_repo / "data")
    monkeypatch.setattr(be, "EXPORTS", exports)

    # export_module() reads two global singletons; stub them so the test is
    # hermetic and can't touch the repo's live config/brain-version state.
    from core.config import config
    from core.brain_version import brain_version_manager
    monkeypatch.setattr(config, "get_module_state", lambda name: {})
    monkeypatch.setattr(
        brain_version_manager, "get_state", lambda: SimpleNamespace(modules={})
    )

    decoy = fake_repo / "decoy_area"
    (decoy / "weights" / "active").mkdir(parents=True)
    (decoy / "weights" / "active" / "secret.txt").write_text(SECRET)

    # Self-check, per this file's own convention: the traversal string
    # really does resolve onto the decoy, and the decoy really is outside
    # modules/. If either were false the test below would prove nothing.
    traversal = "../decoy_area"
    assert (fake_repo / "modules" / traversal).resolve() == decoy.resolve()
    assert (fake_repo / "modules") not in decoy.resolve().parents

    return SimpleNamespace(
        root=fake_repo, exports=exports, decoy=decoy, traversal=traversal,
        tmp=tmp_path,
    )


def _attempt_export(name):
    # Deliberately not asserting an exception type: the property that
    # matters is what did or didn't happen on disk, unconditionally.
    try:
        be.export_module(name)
    except Exception:
        pass


def test_export_path_traversal_cannot_write_bundle_outside_exports_dir(export_sandbox):
    """The output filename is f"{module_name}_{ts}.ocbrain" joined onto
    EXPORTS. A '/' or '..' in module_name must not let the bundle land
    anywhere except directly inside EXPORTS."""
    _attempt_export(export_sandbox.traversal)

    outside = [
        p for p in export_sandbox.tmp.rglob("*.ocbrain")
        if export_sandbox.exports.resolve() not in p.resolve().parents
    ]
    assert not outside, f"bundle written outside EXPORTS: {outside}"


def test_export_path_traversal_cannot_exfiltrate_files_from_outside_modules_dir(export_sandbox):
    """export_module() copies weights/active and knowledge.db out of
    MODULES/<name>. A traversal name must not let it harvest those from a
    directory outside modules/ into a bundle."""
    _attempt_export(export_sandbox.traversal)

    leaked = []
    for bundle in export_sandbox.tmp.rglob("*.ocbrain"):
        with zipfile.ZipFile(bundle) as zf:
            for member in zf.namelist():
                if SECRET.encode() in zf.read(member):
                    leaked.append((bundle.name, member))
    assert not leaked, f"decoy content exfiltrated into a bundle: {leaked}"


def test_legitimate_module_name_still_exports(export_sandbox):
    """Positive control: the fix must not reject or break a real module.
    (Also guards the two tests above against passing trivially -- e.g. if
    export were simply broken in the sandbox, they'd pass for that reason.)"""
    path = be.export_module("legit_module")

    assert path.exists()
    assert export_sandbox.exports.resolve() in path.resolve().parents
    with zipfile.ZipFile(path) as zf:
        assert "manifest.json" in zf.namelist()
