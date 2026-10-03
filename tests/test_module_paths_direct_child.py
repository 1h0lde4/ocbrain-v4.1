"""
tests/test_module_paths_direct_child.py -- module_child() returns a DIRECT child
of `root`, decided on the canonical (symlink-resolved) path.

The contract in core/module_paths.py is "nothing that is not a direct child of
`root` comes back". Checking only that the result is somewhere *below* root let
a symlink to a nested descendant through, and symlink loops either leaked a
bare RuntimeError (Python <= 3.12, from Path.resolve) or were silently accepted
(Python >= 3.13, where Path.resolve no longer raises on a loop).

This file imports nothing but the helper, so it runs on any interpreter that
has pytest. Behaviour must be identical on every supported Python version.
"""
import errno
import os
from pathlib import Path

import pytest

from core import module_paths
from core.module_paths import InvalidModuleName, module_child

FIXED_MESSAGE = "Invalid module_name: must be a single path component."


@pytest.fixture
def root(tmp_path) -> Path:
    r = tmp_path / "root"
    (r / "real").mkdir(parents=True)
    (r / "nested" / "actual_foo").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    return r


def _link(link: Path, target, *, is_dir=True) -> None:
    try:
        link.symlink_to(target, target_is_directory=is_dir)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")


def _rejected(root: Path, name: str, suffix: str = "") -> None:
    with pytest.raises(InvalidModuleName) as e:
        module_child(root, name, suffix)
    assert isinstance(e.value, ValueError)
    assert str(e.value) == FIXED_MESSAGE  # fixed text, never echoes input


def _assert_direct_child(root: Path, result: Path) -> None:
    assert result.parent == root.resolve()
    assert result != root.resolve()


# ── accepted: ordinary names ──────────────────────────────────────────────

def test_ordinary_valid_child(root):
    got = module_child(root, "finance_helper")
    assert got == (root / "finance_helper").resolve()  # need not exist yet
    _assert_direct_child(root, got)


def test_existing_directory_child(root):
    got = module_child(root, "real")
    assert got == (root / "real").resolve()
    _assert_direct_child(root, got)


@pytest.mark.parametrize("name", ["my-module", "mod.v2", "a b", "Ünï"])
def test_registry_style_names_are_valid(root, name):
    # Registry keys are directory basenames, not identifiers.
    got = module_child(root, name)
    assert got == (root / name).resolve()
    _assert_direct_child(root, got)


# ── symlinks: the direct-child invariant ──────────────────────────────────

def test_symlink_to_another_direct_child_returns_the_canonical_target(root):
    _link(root / "alias", root / "real")
    got = module_child(root, "alias")
    # Documented behaviour: both names address one directory inside root.
    assert got == (root / "real").resolve()
    _assert_direct_child(root, got)


def test_symlink_to_a_nested_descendant_is_rejected(root):
    # root/foo -> root/nested/actual_foo: below root, but not a direct child.
    _link(root / "foo", root / "nested" / "actual_foo")
    _rejected(root, "foo")


def test_relative_symlink_to_a_nested_descendant_is_rejected(root):
    _link(root / "foo", Path("nested") / "actual_foo")
    _rejected(root, "foo")


def test_symlink_outside_the_root_is_rejected(root, tmp_path):
    _link(root / "foo", tmp_path / "outside")
    _rejected(root, "foo")


def test_symlink_to_the_root_itself_is_rejected(root):
    _link(root / "foo", root)
    _rejected(root, "foo")


def test_symlink_to_the_parent_of_root_is_rejected(root):
    _link(root / "foo", root.parent)
    _rejected(root, "foo")


def test_dangling_symlink_to_a_direct_child_is_accepted(root):
    # Target does not exist yet; callers create it. Not a containment question.
    _link(root / "foo", root / "not_created_yet")
    got = module_child(root, "foo")
    assert got == (root / "not_created_yet").resolve()
    _assert_direct_child(root, got)


def test_dangling_symlink_outside_the_root_is_rejected(root, tmp_path):
    _link(root / "foo", tmp_path / "outside" / "missing")
    _rejected(root, "foo")


# ── symlink loops: controlled error on every Python version ───────────────

def test_self_referential_symlink_is_rejected(root):
    _link(root / "foo", "foo")
    _rejected(root, "foo")


def test_two_symlink_cycle_is_rejected(root):
    _link(root / "foo", "baz")
    _link(root / "baz", "foo")
    _rejected(root, "foo")
    _rejected(root, "baz")


def test_symlink_to_a_nested_loop_is_rejected(root):
    _link(root / "nested" / "lp", "lp")
    _link(root / "foo", root / "nested" / "lp")
    _rejected(root, "foo")


def test_loop_in_the_root_path_is_rejected(tmp_path):
    _link(tmp_path / "loop_root", "loop_root")
    _rejected(tmp_path / "loop_root", "foo")


def test_resolve_runtime_error_is_converted(root, monkeypatch):
    """The Python <= 3.12 failure mode, exercised on any interpreter."""
    def boom(self, strict=False):
        raise RuntimeError("Symlink loop from %r" % str(self))

    monkeypatch.setattr(Path, "resolve", boom)
    _rejected(root, "foo")


def test_loop_is_detected_by_stat_when_resolve_does_not_raise(root, monkeypatch):
    """The Python >= 3.13 failure mode: resolve() hands back a loop untouched."""
    _link(root / "foo", "foo")
    real_resolve = Path.resolve

    def lenient(self, strict=False):
        try:
            return real_resolve(self, strict=strict)
        except RuntimeError:
            return Path(os.path.abspath(self))  # what >= 3.13 effectively does

    monkeypatch.setattr(Path, "resolve", lenient)
    _rejected(root, "foo")


def test_only_eloop_is_a_loop_verdict(root, monkeypatch):
    """Other stat() failures say nothing about containment and must not reject."""
    real_stat = os.stat

    def denied(path, *a, **kw):
        if str(path).endswith("finance_helper"):
            raise PermissionError(errno.EACCES, "denied")
        return real_stat(path, *a, **kw)

    monkeypatch.setattr(module_paths.os, "stat", denied)
    assert module_child(root, "finance_helper") == (root / "finance_helper").resolve()


# ── hostile names ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "..", ".", "", "../escaped", "../../escaped", "a/b", "a\\b", "/etc/passwd",
    "x\x00y", "sub/../../up", "real/..",
])
def test_traversal_separator_and_nul_names_are_rejected(root, name):
    _rejected(root, name)


def test_non_string_name_is_rejected(root):
    with pytest.raises(InvalidModuleName):
        module_child(root, None)  # type: ignore[arg-type]


# ── suffix behaviour ──────────────────────────────────────────────────────

def test_suffix_is_appended_and_the_result_is_a_direct_child(root):
    got = module_child(root, "foo", ".json")
    assert got == (root / "foo.json").resolve()
    _assert_direct_child(root, got)


@pytest.mark.parametrize("name,suffix", [
    ("my-module", "_gaps.json"), ("my-module", "_known.json"),
    ("foo", "_train.jsonl"), ("foo", "_20261003T120000.ocbrain"),
])
def test_every_suffix_shape_used_by_callers_still_works(root, name, suffix):
    got = module_child(root, name, suffix)
    assert got == (root / (name + suffix)).resolve()
    _assert_direct_child(root, got)


def test_suffix_cannot_climb_out_of_the_root(root):
    _rejected(root, "foo", "/../../escaped")


def test_suffix_that_descends_is_not_a_direct_child(root):
    _rejected(root, "real", "/sub")


def test_suffixed_symlink_to_a_nested_descendant_is_rejected(root):
    _link(root / "foo.json", root / "nested" / "x.json", is_dir=False)
    _rejected(root, "foo", ".json")


def test_suffixed_symlink_outside_the_root_is_rejected(root, tmp_path):
    _link(root / "foo.json", tmp_path / "outside" / "x.json", is_dir=False)
    _rejected(root, "foo", ".json")


def test_suffixed_symlink_loop_is_rejected(root):
    _link(root / "foo.json", "foo.json", is_dir=False)
    _rejected(root, "foo", ".json")


def test_suffixed_symlink_to_another_direct_child_is_accepted(root):
    (root / "other.json").write_text("{}")
    _link(root / "foo.json", root / "other.json", is_dir=False)
    got = module_child(root, "foo", ".json")
    assert got == (root / "other.json").resolve()
    _assert_direct_child(root, got)
