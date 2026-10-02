"""
tests/test_import_root_containment.py -- POST /import path containment.

bundle_path is a server-side file path named by the HTTP caller
(ImportRequest.bundle_path; interface/api.py's /import and core/brain_api.py's
/brain/v2/import). Before this change import_module() opened whatever path it
was given, so any readable file on the host could be handed to zipfile. It now
requires the path to resolve (symlinks followed) to a file inside
global.import_root, defaulting to data/exports where export_module() writes.

CodeQL's py/path-injection alerts on the /import sources (interface/api.py:481,
core/brain_api.py:152) are the scanner view of the same boundary. Whether
CodeQL treats resolve() + is_relative_to() as a barrier is untested; these
tests establish the actual behavior.
"""
import json
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

import core.brain_export as be
import core.config as config_module
import interface.api as api_module

FIXED = "bundle_path must be a file inside the configured import root."


def _bundle(path: Path, module_name: str = "finance_helper") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps({
            "format": "ocbrain/1.0", "module_name": module_name,
            "stage": "bootstrap", "base_model": "mistral",
        }))
    return path


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Default import root (= EXPORTS) redirected to a temp directory."""
    r = tmp_path / "exports"
    r.mkdir()
    monkeypatch.setattr(be, "EXPORTS", r)
    # Make sure no real settings.toml value leaks into the default case.
    monkeypatch.setattr(
        config_module.config, "get",
        lambda key, default=None: default,
    )
    return r.resolve()


# ── resolve_bundle_path ────────────────────────────────────────────────

def test_absolute_path_inside_root_is_accepted(root):
    b = _bundle(root / "ok.ocbrain")
    assert be.resolve_bundle_path(b) == b.resolve()


def test_relative_path_is_taken_relative_to_the_root(root):
    b = _bundle(root / "sub" / "ok.ocbrain")
    assert be.resolve_bundle_path("sub/ok.ocbrain") == b.resolve()


def test_absolute_path_outside_root_is_rejected(tmp_path, root):
    outside = _bundle(tmp_path / "elsewhere" / "x.ocbrain")
    with pytest.raises(be.BundlePathError) as e:
        be.resolve_bundle_path(outside)
    assert str(outside) not in str(e.value) and str(root) not in str(e.value)
    assert str(e.value) == FIXED


@pytest.mark.parametrize("make", [
    lambda root, outside: "../outside.ocbrain",
    lambda root, outside: str(root / ".." / "outside.ocbrain"),
    lambda root, outside: "sub/../../outside.ocbrain",
])
def test_dotdot_traversal_is_rejected(tmp_path, root, make):
    outside = _bundle(tmp_path / "outside.ocbrain")
    with pytest.raises(be.BundlePathError):
        be.resolve_bundle_path(make(root, outside))


def test_sibling_directory_sharing_a_prefix_is_rejected(tmp_path, root):
    # A plain str.startswith() check would accept ".../exports_evil/...".
    evil = _bundle(tmp_path / "exports_evil" / "x.ocbrain")
    with pytest.raises(be.BundlePathError):
        be.resolve_bundle_path(evil)


def test_symlink_inside_root_pointing_outside_is_rejected(tmp_path, root):
    outside = _bundle(tmp_path / "private" / "secret.ocbrain")
    link = root / "innocent.ocbrain"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")
    with pytest.raises(be.BundlePathError):
        be.resolve_bundle_path(link)


def test_nul_byte_is_rejected_as_a_bundle_path_error(root):
    with pytest.raises(be.BundlePathError):
        be.resolve_bundle_path("a\x00b.ocbrain")


def test_configured_root_is_honoured_and_replaces_the_default(tmp_path, root, monkeypatch):
    custom = tmp_path / "imports"
    inside_custom = _bundle(custom / "c.ocbrain")
    inside_default = _bundle(root / "d.ocbrain")
    monkeypatch.setattr(
        config_module.config, "get",
        lambda key, default=None: str(custom) if key == "global.import_root" else default,
    )
    assert be.resolve_bundle_path(inside_custom) == inside_custom.resolve()
    with pytest.raises(be.BundlePathError):
        be.resolve_bundle_path(inside_default)


def test_relative_configured_root_is_resolved_against_the_project_root(monkeypatch, root):
    monkeypatch.setattr(
        config_module.config, "get",
        lambda key, default=None: "data/some_imports" if key == "global.import_root" else default,
    )
    assert be.import_root() == (be.ROOT / "data" / "some_imports").resolve()


# ── import_module (the sink every caller goes through) ────────────────

def test_import_module_rejects_an_outside_bundle_before_opening_it(tmp_path, root, monkeypatch):
    modules = tmp_path / "modules"
    modules.mkdir()
    monkeypatch.setattr(be, "MODULES", modules)
    outside = _bundle(tmp_path / "elsewhere" / "valid.ocbrain")  # a perfectly valid bundle

    def _must_not_open(*a, **kw):
        raise AssertionError("import_module opened a bundle outside the import root")

    monkeypatch.setattr(be.zipfile, "ZipFile", _must_not_open)
    with pytest.raises(be.BundlePathError):
        be.import_module(outside, overwrite=True)
    assert list(modules.iterdir()) == []


def test_no_existence_oracle_for_paths_outside_the_root(tmp_path, root):
    # A missing file outside the root must look the same as an existing one.
    with pytest.raises(be.BundlePathError):
        be.import_module(tmp_path / "does_not_exist.ocbrain")


def test_missing_bundle_inside_the_root_is_still_file_not_found(root):
    with pytest.raises(FileNotFoundError):
        be.import_module(root / "missing.ocbrain")


# ── Both HTTP routes return a clean 400 with a fixed message ──────────

@pytest.mark.asyncio
async def test_api_import_returns_400_without_echoing_input(tmp_path, root):
    outside = _bundle(tmp_path / "elsewhere" / "x.ocbrain")
    req = api_module.ImportRequest(bundle_path=str(outside))
    with pytest.raises(HTTPException) as exc:
        await api_module.import_module(req)
    assert exc.value.status_code == 400
    assert exc.value.detail == FIXED
    assert str(outside) not in exc.value.detail and str(root) not in exc.value.detail


def test_brain_v2_import_returns_400_without_echoing_input(tmp_path, root):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core.brain_api import register

    app = FastAPI()
    register(app, {})
    outside = _bundle(tmp_path / "elsewhere" / "x.ocbrain")
    r = TestClient(app, raise_server_exceptions=False).post(
        "/brain/v2/import", json={"bundle_path": str(outside)},
    )
    assert r.status_code == 400, r.text
    assert FIXED in r.text
    assert str(outside) not in r.text and str(root) not in r.text
