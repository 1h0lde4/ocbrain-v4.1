"""
tests/test_import_bundle_boundary.py -- the /import bundle_path boundary
(CTX-EXPORT-001, issue #54; CodeQL py/path-injection alert #12).

Accepted design decisions under test:
  D1  no configured import root => the import is refused; no implicit default
  D2  a relative bundle_path is relative to the import root, never the CWD
  D3  the ".ocbrain" suffix is required
  D4  containment is canonical-string realpath + startswith(root + os.sep)
  D5  the suffix is defense in depth, not the proof of containment

The boundary is enforced in the sink (core.brain_export.import_module), so it
covers every caller; both HTTP routes only translate the refusal into a 400.
"""
import asyncio  # noqa: F401  (pytest-asyncio auto mode)
import json
import os
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException

import core.brain_api as brain_api_module
import core.brain_export as be
import interface.api as api_module
from core.brain_export import BundlePathError, resolve_bundle_path

NO_ROOT = "Import is disabled: no import root is configured."
OUTSIDE = "bundle_path must be a .ocbrain file inside the configured import root."


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a real bundle")
    return path


def _link(link: Path, target) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")


def _make_bundle(path: Path, module_name: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps({
            "format": "ocbrain/1.0", "module_name": module_name,
            "stage": "bootstrap", "base_model": "mistral"}))
    return path


def _forbid_touching(monkeypatch, target: Path) -> None:
    """Fail if `target` is existence-probed or opened as a zip. Narrow on
    purpose: patching Path.exists/ZipFile globally breaks pytest's own failure
    reporting."""
    target_real = os.path.realpath(target)
    real_exists, real_zip = Path.exists, zipfile.ZipFile

    def exists(self, *a, **k):
        if os.path.realpath(self) == target_real:
            pytest.fail("existence of an outside path was probed")
        return real_exists(self, *a, **k)

    def zipper(file, *a, **k):
        if os.path.realpath(os.fspath(file)) == target_real:
            pytest.fail("an outside path was opened as a zip")
        return real_zip(file, *a, **k)

    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(zipfile, "ZipFile", zipper)


def _config_returns(monkeypatch, value):
    import core.config as config_module
    monkeypatch.setattr(
        config_module.config, "get",
        lambda key, default=None: value if key == "global.import_root" else default)


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    r = tmp_path / "imports"
    r.mkdir()
    monkeypatch.setattr(be, "import_root", lambda: os.path.realpath(r))
    return r


def _refused(arg, message=OUTSIDE):
    with pytest.raises(BundlePathError) as e:
        resolve_bundle_path(arg)
    assert isinstance(e.value, ValueError)
    assert str(e.value) == message          # the fixed constant: nothing is echoed
    return e.value


# ── import_root(): configuration, fail closed ─────────────────────────────

def test_import_root_is_none_when_unset(monkeypatch):
    _config_returns(monkeypatch, None)
    assert be.import_root() is None


@pytest.mark.parametrize("value", ["", "   ", 5, True, ["x"], {"a": 1}])
def test_import_root_is_none_for_unusable_values(monkeypatch, value):
    _config_returns(monkeypatch, value)
    assert be.import_root() is None


def test_import_root_with_nul_byte_is_none(monkeypatch):
    _config_returns(monkeypatch, "bad\x00root")
    assert be.import_root() is None


def test_absolute_import_root_is_canonicalized(tmp_path, monkeypatch):
    real = tmp_path / "real_imports"
    real.mkdir()
    _link(tmp_path / "link_imports", real)
    _config_returns(monkeypatch, str(tmp_path / "link_imports"))
    assert be.import_root() == os.path.realpath(real)


def test_relative_import_root_is_resolved_against_the_project_root(tmp_path, monkeypatch):
    monkeypatch.setattr(be, "ROOT", tmp_path)
    _config_returns(monkeypatch, "inbox")
    assert be.import_root() == os.path.realpath(tmp_path / "inbox")


# ── D1: no root => refused, and no implicit fallback ──────────────────────

@pytest.mark.parametrize("arg", ["x.ocbrain", "/etc/passwd", "", "../x.ocbrain"])
def test_no_root_refuses_everything(monkeypatch, arg):
    monkeypatch.setattr(be, "import_root", lambda: None)
    _refused(arg, NO_ROOT)


def test_unconfigured_root_does_not_fall_back_to_data_exports(tmp_path, monkeypatch):
    exports = tmp_path / "exports"
    bundle = _make_bundle(exports / "b.ocbrain", "finance_helper")
    monkeypatch.setattr(be, "EXPORTS", exports)
    monkeypatch.setattr(be, "ROOT", tmp_path)
    _config_returns(monkeypatch, None)          # genuinely unset, real import_root()
    opened = []
    monkeypatch.setattr(zipfile, "ZipFile", lambda *a, **k: opened.append(a) or pytest.fail("opened"))
    for arg in (bundle, "b.ocbrain", str(bundle)):
        with pytest.raises(BundlePathError) as e:
            be.import_module(Path(arg))
        assert str(e.value) == NO_ROOT
    assert opened == []


# ── accepted paths, D2 ────────────────────────────────────────────────────

def test_absolute_path_inside_the_root_is_accepted(root):
    bundle = _touch(root / "b.ocbrain")
    got = resolve_bundle_path(bundle)
    assert got == Path(os.path.realpath(bundle))
    assert resolve_bundle_path(str(bundle)) == got      # str and Path agree


def test_relative_path_is_relative_to_the_root(root):
    _touch(root / "b.ocbrain")
    assert resolve_bundle_path("b.ocbrain") == Path(os.path.realpath(root / "b.ocbrain"))


def test_relative_path_is_never_relative_to_the_working_directory(root, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    _touch(elsewhere / "b.ocbrain")             # same name, in the CWD
    monkeypatch.chdir(elsewhere)
    got = resolve_bundle_path("b.ocbrain")
    assert got == Path(os.path.realpath(root / "b.ocbrain"))
    assert Path(os.path.realpath(elsewhere)) not in got.parents


def test_nested_directory_below_the_root_is_accepted(root):
    nested = _touch(root / "team" / "a" / "b.ocbrain")
    assert resolve_bundle_path("team/a/b.ocbrain") == Path(os.path.realpath(nested))


def test_symlink_inside_the_root_to_a_bundle_inside_the_root_is_accepted(root):
    _touch(root / "real.ocbrain")
    _link(root / "alias.ocbrain", root / "real.ocbrain")
    assert resolve_bundle_path("alias.ocbrain") == Path(os.path.realpath(root / "real.ocbrain"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX filesystem root")
def test_filesystem_root_as_import_root_has_no_separator_bug(monkeypatch):
    monkeypatch.setattr(be, "import_root", lambda: os.path.realpath("/"))
    name = "ocbrain_no_such_bundle_for_boundary_tests.ocbrain"
    assert resolve_bundle_path(name) == Path("/" + name)
    _refused("/")


# ── D3 / D5: suffix is required, and is not the proof ─────────────────────

@pytest.mark.parametrize("name", ["b", "b.zip", "b.ocbrain.zip", "b.OCBRAIN", "b.ocbrain "])
def test_wrong_or_missing_suffix_is_refused(root, name):
    _touch(root / name)
    _refused(name)


def test_suffix_is_checked_on_the_canonical_path(root):
    _touch(root / "real.zip")
    _link(root / "alias.ocbrain", root / "real.zip")    # looks right, resolves wrong
    _refused("alias.ocbrain")


def test_suffix_does_not_make_an_outside_path_acceptable(root, tmp_path):
    outside = _touch(tmp_path / "outside" / "b.ocbrain")
    _refused(outside)
    _refused(str(outside))
    _refused("../outside/b.ocbrain")


def test_suffixed_symlink_to_an_outside_bundle_is_refused(root, tmp_path):
    outside = _touch(tmp_path / "outside" / "b.ocbrain")
    _link(root / "b.ocbrain", outside)
    _refused("b.ocbrain")
    _refused(root / "b.ocbrain")


def test_suffixed_symlink_to_an_outside_directory_is_refused(root, tmp_path):
    outside = tmp_path / "outside"
    _touch(outside / "b.ocbrain")
    _link(root / "linked", outside)
    _refused("linked/b.ocbrain")


# ── D4: containment on canonical strings ──────────────────────────────────

@pytest.mark.parametrize("arg", [
    "..", "../b.ocbrain", "../../b.ocbrain", "sub/../../b.ocbrain",
    "a/../../imports_evil/b.ocbrain",
])
def test_traversal_is_refused(root, tmp_path, arg):
    _touch(tmp_path / "b.ocbrain")
    _touch(tmp_path / "imports_evil" / "b.ocbrain")
    _refused(arg)


def test_sibling_directory_sharing_the_root_prefix_is_refused(root, tmp_path):
    evil = _touch(tmp_path / "imports_evil" / "b.ocbrain")
    _refused(evil)                              # absolute
    _refused("../imports_evil/b.ocbrain")       # relative
    _link(root / "x.ocbrain", evil)             # via a link
    _refused("x.ocbrain")


@pytest.mark.parametrize("arg", ["", ".", "sub/..", "a/b/../.."])
def test_the_root_itself_is_refused(root, arg):
    (root / "sub").mkdir(exist_ok=True)
    (root / "a" / "b").mkdir(parents=True, exist_ok=True)
    _refused(arg)
    _refused(root)


@pytest.mark.parametrize("arg", ["", ".", "sub/.."])
def test_the_root_is_refused_even_when_its_own_name_ends_in_the_suffix(tmp_path, monkeypatch, arg):
    # D5: here the suffix check passes for the root itself, so only the
    # containment check can refuse it.
    weird = tmp_path / "inbox.ocbrain"
    (weird / "sub").mkdir(parents=True)
    monkeypatch.setattr(be, "import_root", lambda: os.path.realpath(weird))
    _refused(arg)
    _refused(weird)


@pytest.mark.parametrize("arg", ["/etc/passwd", "/etc/passwd.ocbrain", "/"])
def test_absolute_paths_outside_the_root_are_refused(root, arg):
    _refused(arg)


def test_nul_byte_is_refused(root):
    with pytest.raises(BundlePathError) as e:
        resolve_bundle_path("a\x00b.ocbrain")
    assert str(e.value) == OUTSIDE


def test_non_path_argument_is_refused(root):
    with pytest.raises(BundlePathError):
        resolve_bundle_path(None)               # type: ignore[arg-type]


def test_symlink_loop_cannot_be_used_to_escape_or_crash(root):
    _link(root / "loop.ocbrain", "loop.ocbrain")
    got = resolve_bundle_path("loop.ocbrain")   # inside the root; I/O decides later
    assert got.parent == Path(os.path.realpath(root))
    with pytest.raises(FileNotFoundError):
        be.import_module(Path("loop.ocbrain"))


def test_the_refusal_text_is_identical_whatever_exists(root, tmp_path):
    present = _touch(tmp_path / "outside" / "present.ocbrain")
    absent = tmp_path / "outside" / "absent.ocbrain"
    texts = set()
    for p in (present, absent):
        with pytest.raises(BundlePathError) as e:
            resolve_bundle_path(p)
        texts.add(str(e.value))
    assert texts == {OUTSIDE}                   # no existence oracle


def test_error_text_does_not_reveal_the_root(root):
    e = _refused("../x.ocbrain")
    assert str(root) not in str(e)
    assert os.path.realpath(root) not in str(e)


# ── the sink: containment first, existence second ─────────────────────────

def test_sink_refuses_an_outside_path_before_touching_the_filesystem(root, tmp_path, monkeypatch):
    outside = _touch(tmp_path / "outside" / "b.ocbrain")
    never = tmp_path / "outside" / "never_created.ocbrain"
    _forbid_touching(monkeypatch, outside)
    with pytest.raises(BundlePathError):
        be.import_module(outside)
    _forbid_touching(monkeypatch, never)
    with pytest.raises(BundlePathError):
        be.import_module(never)


def test_missing_bundle_inside_the_root_is_still_file_not_found(root):
    with pytest.raises(FileNotFoundError):
        be.import_module(root / "missing.ocbrain")
    with pytest.raises(FileNotFoundError):
        be.import_module(Path("missing.ocbrain"))   # relative to the root


def test_sink_opens_the_canonical_path_it_validated(root, monkeypatch):
    _touch(root / "real.ocbrain")
    _link(root / "alias.ocbrain", root / "real.ocbrain")
    opened = []

    class Stop(Exception):
        pass

    def spy(path, *a, **k):
        opened.append(os.fspath(path))
        raise Stop

    monkeypatch.setattr(zipfile, "ZipFile", spy)
    with pytest.raises(Stop):
        be.import_module(Path("alias.ocbrain"))
    assert opened == [os.path.realpath(root / "real.ocbrain")]


def test_a_legitimate_bundle_inside_the_root_still_imports(tmp_path, monkeypatch, root):
    fake_repo = tmp_path / "fake_repo"
    (fake_repo / "modules").mkdir(parents=True)
    (fake_repo / "data").mkdir(parents=True)
    monkeypatch.setattr(be, "MODULES", fake_repo / "modules")
    monkeypatch.setattr(be, "DATA", fake_repo / "data")

    import core.config as config_module
    import core.module_factory as factory_module
    monkeypatch.setattr(factory_module, "MODULES_DIR", fake_repo / "modules")
    monkeypatch.setattr(factory_module, "TEMPLATE_DIR", Path("modules/_template").resolve())
    monkeypatch.setattr(
        config_module.config, "get",
        lambda key, default=None: True if key == "global.module_factory_enabled" else default)
    monkeypatch.setattr(config_module.config, "register_module", lambda *a, **k: None)
    monkeypatch.setattr(config_module.config, "set_module_state", lambda *a, **k: None)

    _make_bundle(root / "legit.ocbrain", "finance_helper")
    assert be.import_module(Path("legit.ocbrain"), overwrite=True) == "finance_helper"
    assert (fake_repo / "modules" / "finance_helper").exists()


# ── both routes: 400 with fixed text, nothing else changes ────────────────

def _brain_v2_import():
    brain_api_module.register(FastAPI(), {})
    routes = [r for r in brain_api_module.router.routes
              if getattr(r, "path", "") == "/brain/v2/import"]
    assert routes, "route not registered"
    return routes[-1].endpoint


def _routes():
    return [
        ("interface.api /import", api_module.import_module, api_module.ImportRequest),
        ("brain_api /brain/v2/import", _brain_v2_import(), brain_api_module.ImportRequest),
    ]


@pytest.mark.parametrize("which", [0, 1])
async def test_routes_refuse_an_outside_path_with_400(root, tmp_path, which):
    _name, endpoint, request_model = _routes()[which]
    outside = _touch(tmp_path / "outside" / "b.ocbrain")
    for raw in (str(outside), "../outside/b.ocbrain", "/etc/passwd"):
        with pytest.raises(HTTPException) as e:
            await endpoint(request_model(bundle_path=raw))
        assert e.value.status_code == 400
        assert e.value.detail == OUTSIDE
        assert raw not in str(e.value.detail)


@pytest.mark.parametrize("which", [0, 1])
async def test_routes_refuse_everything_when_no_root_is_configured(monkeypatch, tmp_path, which):
    _name, endpoint, request_model = _routes()[which]
    monkeypatch.setattr(be, "import_root", lambda: None)
    bundle = _touch(tmp_path / "b.ocbrain")
    with pytest.raises(HTTPException) as e:
        await endpoint(request_model(bundle_path=str(bundle)))
    assert (e.value.status_code, e.value.detail) == (400, NO_ROOT)


@pytest.mark.parametrize("which", [0, 1])
async def test_routes_leave_file_not_found_unchanged(root, which):
    _name, endpoint, request_model = _routes()[which]
    with pytest.raises(FileNotFoundError):
        await endpoint(request_model(bundle_path="missing.ocbrain"))


@pytest.mark.parametrize("which", [0, 1])
async def test_routes_still_return_the_import_result(root, monkeypatch, which):
    _name, endpoint, request_model = _routes()[which]
    seen = {}

    def fake_import(path, overwrite=False):
        seen["args"] = (path, overwrite)
        return "finance_helper"

    monkeypatch.setattr(be, "import_module", fake_import)
    out = await endpoint(request_model(bundle_path="b.ocbrain", overwrite=True))
    assert out == {"status": "imported", "module": "finance_helper"}
    assert seen["args"] == (Path("b.ocbrain"), True)
