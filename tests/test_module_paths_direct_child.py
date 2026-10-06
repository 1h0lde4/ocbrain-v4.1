"""
tests/test_module_paths_direct_child.py -- module_child() returns a DIRECT child
of `root`, decided on the canonical (symlink-resolved) path.

The contract in core/module_paths.py is "nothing that is not a direct child of
`root` comes back". Checking only that the result is somewhere *below* root let
a symlink to a nested descendant through, and symlink loops either leaked a
bare RuntimeError (Python <= 3.12, from Path.resolve) or were silently accepted
(Python >= 3.13, where Path.resolve no longer raises on a loop).

The helper now canonicalizes with os.path.realpath() and decides containment on
strings: candidate.startswith(base + os.sep), then exactly one component below
the base, then an os.stat() probe that treats ELOOP as a loop.

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


def test_realpath_hands_a_loop_back_so_stat_is_the_detector(root):
    """Premise of the probe, checked on this interpreter: the canonicalizer
    neither raises on a loop nor moves it out of root -- only the OS can say."""
    _link(root / "foo", "foo")
    canonical = os.path.realpath(root / "foo")
    assert os.path.dirname(canonical) == os.path.realpath(root)
    _rejected(root, "foo")


@pytest.mark.parametrize("make_exc", [
    lambda: OSError(errno.EIO, "boom"),
    lambda: ValueError("boom"),
])
def test_canonicalization_failure_is_converted(root, monkeypatch, make_exc):
    def boom(*args, **kwargs):
        raise make_exc()

    monkeypatch.setattr(module_paths.os.path, "realpath", boom)
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


# ── containment on canonical strings ──────────────────────────────────────

@pytest.fixture
def allowed(tmp_path) -> Path:
    r = tmp_path / "allowed_root"
    r.mkdir()
    (tmp_path / "allowed_root_evil" / "inner").mkdir(parents=True)
    return r


def test_sibling_directory_sharing_the_root_prefix_is_rejected(allowed, tmp_path):
    # "<root>_evil" starts with "<root>" but is not inside it.
    _link(allowed / "foo", tmp_path / "allowed_root_evil")
    _rejected(allowed, "foo")


def test_directory_inside_a_prefix_sibling_is_rejected(allowed, tmp_path):
    _link(allowed / "foo", tmp_path / "allowed_root_evil" / "inner")
    _rejected(allowed, "foo")


def test_suffix_traversal_into_a_prefix_sibling_is_rejected(allowed):
    (allowed / "bar").mkdir()
    _rejected(allowed, "bar", "/../../allowed_root_evil")
    _rejected(allowed, "bar", "/../../allowed_root_evil/inner")


def test_prefix_root_still_accepts_its_real_children(allowed):
    got = module_child(allowed, "foo")
    assert got == (allowed / "foo").resolve()
    _assert_direct_child(allowed, got)


def test_name_and_suffix_resolving_to_the_root_itself_are_rejected(root):
    (root / "bar").mkdir()
    _rejected(root, "bar", "/..")


@pytest.mark.skipif(os.name != "posix", reason="POSIX filesystem root")
def test_filesystem_root_as_base_still_yields_direct_children():
    name = "ocbrain_no_such_entry_for_module_paths_tests"
    assert not os.path.lexists("/" + name)
    got = module_child(Path("/"), name)
    assert got == Path("/" + name)
    assert module_child("/", name) == got
    _rejected(Path("/"), name, "/..")      # resolves to "/" itself
    _rejected(Path("/"), name, "/sub")     # deeper than one component


def test_root_may_be_a_str_or_a_path(root):
    assert module_child(str(root), "foo") == module_child(root, "foo")


def test_root_reached_through_a_symlink_is_canonicalized(tmp_path):
    real_root = tmp_path / "real_root"
    real_root.mkdir()
    _link(tmp_path / "link_root", real_root)
    got = module_child(tmp_path / "link_root", "foo")
    assert got == (real_root / "foo").resolve()
    _assert_direct_child(real_root, got)


def test_stat_probe_runs_only_on_the_validated_path(root, tmp_path, monkeypatch):
    _link(root / "esc", tmp_path / "outside")
    seen = []
    real_stat = os.stat

    def spy(path, *args, **kwargs):
        seen.append(os.fspath(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(module_paths.os, "stat", spy)
    _rejected(root, "esc")        # escapes the root: rejected before any probe
    _rejected(root, "..")         # hostile name: rejected before any probe
    assert seen == []
    good = module_child(root, "finance_helper")
    assert seen == [str(good)]


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
