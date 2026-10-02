"""
Security regression tests for CTX-EXPORT-001 (KNOWN_ISSUES.md DEBT-019).

Two independent primitives, same root cause (module_name used to build a
filesystem path with zero validation), same fix (.isidentifier()):

1. import_module() -- path-traversal-to-arbitrary-deletion. Built a path
   directly from an attacker-controlled manifest.json's module_name
   field, then shutil.rmtree()'d it, before any validation ran. A
   module_name like "../../etc" pointed that deletion outside modules/
   entirely. Fixed previously; covered by the two tests below.

2. export_module() -- path-traversal-to-arbitrary-read (CodeQL
   py/path-injection; flagged against live `main` and confirmed still
   unfixed on 2026-09-26 -- export_module() never received the
   validation import_module() did). module_name reaches this function
   from an HTTP request body (ExportRequest.module_name, both
   interface/api.py's and core/brain_api.py's /export routers) and was
   used, unvalidated, to build mod_dir/weights_src/kb_src/eval_src/
   raw_dir and output_path -- a module_name like "../../../etc" could
   make export read (and hand back inside the returned bundle) arbitrary
   directories outside modules/. Covered by TestExportModuleNameValidation
   below.
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

    # Bundles must sit inside the import root now (PR: /import containment);
    # put the root at tmp_path so this still exercises the module_name guard
    # rather than passing because the bundle path was rejected.
    monkeypatch.setattr(be, "EXPORTS", tmp_path)

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

    monkeypatch.setattr(be, "EXPORTS", tmp_path)  # bundle lives inside the import root

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


class TestExportModuleNameValidation:
    """export_module() side of CTX-EXPORT-001 (CodeQL py/path-injection,
    core/brain_export.py). Same vulnerability shape as the import_module()
    tests above -- module_name used to build a path with no validation --
    applied to the read/export direction instead of the delete/import one.
    """

    def test_path_traversal_module_name_rejected_before_any_filesystem_access(
        self, tmp_path, monkeypatch
    ):
        """A module_name shaped like a path must be rejected before
        mod_dir is even built, let alone read from -- proven against a
        decoy directory that a pre-fix export_module() could have copied
        into the bundle it hands back to the caller."""
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "modules").mkdir(parents=True)
        (fake_repo / "data").mkdir(parents=True)
        monkeypatch.setattr(be, "MODULES", fake_repo / "modules")
        monkeypatch.setattr(be, "DATA", fake_repo / "data")
        monkeypatch.setattr(be, "EXPORTS", fake_repo / "data" / "exports")

        decoy = tmp_path / "victim_area" / "decoy_dir"
        decoy.mkdir(parents=True)
        (decoy / "secret.txt").write_text("must never be read by export")

        with pytest.raises(ValueError, match="Invalid module_name"):
            be.export_module("../../victim_area/decoy_dir")

        # No bundle should exist -- the rejection must happen before any
        # export I/O, not merely before the zip is finalized.
        exports_dir = fake_repo / "data" / "exports"
        assert not exports_dir.exists() or not any(exports_dir.iterdir())

    def test_legitimate_module_name_passes_validation(self, tmp_path, monkeypatch):
        """The fix must not reject ordinary module names -- only ones
        shaped like a path. A legitimate name with no matching module
        directory must fail with the pre-existing 'not found' error,
        never the new 'Invalid module_name' validation error -- proving
        the new check sits in front of, and is independent from, the
        existing not-found check."""
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "modules").mkdir(parents=True)
        (fake_repo / "data").mkdir(parents=True)
        monkeypatch.setattr(be, "MODULES", fake_repo / "modules")
        monkeypatch.setattr(be, "DATA", fake_repo / "data")

        with pytest.raises(ValueError, match="not found"):
            be.export_module("finance_helper")


class TestZipSlipExtraction:
    """import_module()'s zip-extraction step (CodeQL py/path-injection flags
    the extractall() call in core/brain_export.py). These tests pin down the
    strictness _safe_extractall adds: a member whose name tries to leave the
    extraction directory rejects the whole bundle before anything is
    extracted. They do NOT demonstrate a vulnerability that plain
    extractall() had -- CPython's zipfile already drops '..' and absolute
    components from member names (verified on Python 3.12.3: nothing
    escaped; the same filter is in the 3.11 and 3.13 sources), so the original write-up of this as an exploitable
    arbitrary-file-write was wrong. This is defense-in-depth.
    """

    def _malicious_bundle(self, path: Path) -> Path:
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("manifest.json", json.dumps({
                "format": "ocbrain/1.0",
                "module_name": "finance_helper",
                "stage": "bootstrap",
                "base_model": "mistral",
            }))
            zf.writestr("../victim_area/evil.txt", "must never be written")
        return path

    def test_malicious_entry_rejected_before_manifest_is_read(self, tmp_path):
        """A zip member shaped like a path escape must be rejected during
        extraction itself -- proven against a decoy directory outside the
        extraction root, and proven fail-closed: since _safe_extractall
        validates every member before extracting any of them, a bundle
        can't smuggle a traversal entry past review by pairing it with an
        otherwise well-formed manifest.json in the same archive."""
        decoy = tmp_path / "victim_area"
        decoy.mkdir()
        bundle = self._malicious_bundle(tmp_path / "evil.ocbrain")

        dest = tmp_path / "extract_here"
        dest.mkdir()

        with zipfile.ZipFile(bundle, "r") as zf:
            with pytest.raises(ValueError, match="resolves outside"):
                be._safe_extractall(zf, dest)

        assert not (decoy / "evil.txt").exists()
        assert not any(dest.iterdir())  # nothing partial extracted either

    def test_legitimate_bundle_still_extracts(self, tmp_path):
        """The fix must not interfere with normal, well-formed bundles."""
        bundle = tmp_path / "legit.ocbrain"
        with zipfile.ZipFile(bundle, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"module_name": "finance_helper"}))
            zf.writestr("module/weights/model.bin", b"fake weights")

        dest = tmp_path / "extract_here"
        dest.mkdir()

        with zipfile.ZipFile(bundle, "r") as zf:
            be._safe_extractall(zf, dest)

        assert (dest / "manifest.json").exists()
        assert (dest / "module" / "weights" / "model.bin").exists()

    def test_import_module_rejects_malicious_bundle_end_to_end(self, tmp_path, monkeypatch):
        """Same property, exercised through the real import_module() call
        site rather than the helper in isolation."""
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "modules").mkdir(parents=True)
        monkeypatch.setattr(be, "MODULES", fake_repo / "modules")
        monkeypatch.setattr(be, "EXPORTS", tmp_path)  # bundle inside the import root

        decoy = tmp_path / "victim_area"
        decoy.mkdir()
        bundle = self._malicious_bundle(tmp_path / "evil.ocbrain")

        # match= so this cannot pass merely because the bundle path itself
        # was rejected (BundlePathError is also a ValueError).
        with pytest.raises(ValueError, match="resolves outside"):
            be.import_module(bundle)

        assert not (decoy / "evil.txt").exists()
