"""Tests for core/privacy.py"""
import sys
import shutil
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_can_save_history_default():
    from core.privacy import PrivacyGuard
    guard = PrivacyGuard()
    # Default in settings.toml is true
    assert guard.can_save_history() is True


def test_can_save_training_default():
    from core.privacy import PrivacyGuard
    guard = PrivacyGuard()
    assert guard.can_save_training() is True


def test_can_crawl_enabled_module():
    from core.privacy import PrivacyGuard
    guard = PrivacyGuard()
    # coding is enabled in settings.toml
    assert guard.can_crawl("coding") is True


# ---------------------------------------------------------------------------
# wipe_module_data(): deletion containment (same class as CTX-EXPORT-001).
#
# wipe_module_data() does shutil.rmtree on ROOT/data/{raw,chunks}/<module_name>.
# The test that used to be here replaced PrivacyGuard with a stub and then
# called shutil.rmtree itself, so it exercised the standard library, not
# OCBrain, and would have passed against ANY implementation -- including a
# broken one. These tests run the real method.
#
# The method builds its paths from Path(__file__), so pointing
# core.privacy.__file__ at a temp tree keeps every deletion inside tmp_path.
#
# SAFETY: a red run of a deletion-exploit test *executes the exploit*. Every
# payload below must therefore resolve inside tmp_path. In particular a bare
# absolute name such as "/etc" must never be used as a payload: pathlib's
# Path("a") / "/etc" is Path("/etc"), i.e. an absolute module_name replaces the
# root entirely, and against unguarded code that would be rmtree("/etc").
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    import core.privacy as pmod
    root = tmp_path / "fake_repo"
    (root / "core").mkdir(parents=True)
    monkeypatch.setattr(pmod, "__file__", str(root / "core" / "privacy.py"))
    return root


def _seed(root, sub, name, fname="pair1.json"):
    d = root / "data" / sub / name
    d.mkdir(parents=True)
    (d / fname).write_text('{"query":"test","answer":"test"}')
    return d


@pytest.mark.parametrize("name", ["coding", "my-module"])
def test_wipe_module_data(fake_repo, name):
    """wipe_module_data removes raw/ and chunks/ for that module -- and only that module."""
    from core.privacy import PrivacyGuard
    raw, chunks = _seed(fake_repo, "raw", name), _seed(fake_repo, "chunks", name)
    other_raw, other_chunks = _seed(fake_repo, "raw", "other"), _seed(fake_repo, "chunks", "other")

    PrivacyGuard().wipe_module_data(name)

    assert not raw.exists() and not chunks.exists()
    assert other_raw.exists() and other_chunks.exists()  # neighbours untouched


def test_wipe_module_data_for_a_module_with_no_data_is_a_noop(fake_repo):
    from core.privacy import PrivacyGuard
    keep = _seed(fake_repo, "raw", "other")
    PrivacyGuard().wipe_module_data("never_had_data")
    assert keep.exists()


def test_wipe_module_data_cannot_delete_outside_the_data_dirs(fake_repo):
    """A traversal-shaped module_name must not let rmtree reach a directory
    outside data/raw and data/chunks."""
    from core.privacy import PrivacyGuard
    _seed(fake_repo, "raw", "legit")
    _seed(fake_repo, "chunks", "legit")
    decoy = fake_repo / "decoy_dir"
    decoy.mkdir()
    (decoy / "keep.txt").write_text("precious")
    traversal = "../../decoy_dir"

    # Self-check so this cannot pass for the wrong reason: the traversal really
    # does resolve onto the decoy, and the decoy really is outside data/.
    assert (fake_repo / "data" / "raw" / traversal).resolve() == decoy.resolve()
    assert (fake_repo / "data" / "chunks" / traversal).resolve() == decoy.resolve()
    assert (fake_repo / "data").resolve() not in decoy.resolve().parents

    try:
        PrivacyGuard().wipe_module_data(traversal)
    except Exception:
        pass  # what matters is what survived, not which exception was raised

    assert decoy.is_dir() and (decoy / "keep.txt").read_text() == "precious"


def test_wipe_module_data_rejects_an_absolute_path_as_a_module_name(fake_repo):
    """pathlib: Path("a") / "/abs" == Path("/abs"), so an absolute module_name
    replaces the root entirely. The decoy lives inside tmp_path -- see SAFETY."""
    from core.privacy import PrivacyGuard
    decoy = fake_repo / "decoy_abs"
    decoy.mkdir()
    (decoy / "keep.txt").write_text("precious")
    assert Path(str(decoy)).is_absolute()

    try:
        PrivacyGuard().wipe_module_data(str(decoy))
    except Exception:
        pass

    assert decoy.is_dir() and (decoy / "keep.txt").read_text() == "precious"


@pytest.mark.parametrize("bad", ["..", ".", "", "../x", "a/b", "x\x00y"])
def test_wipe_module_data_rejects_non_names_before_deleting_anything(fake_repo, bad):
    """Fail closed: an invalid name raises before ANY directory is removed."""
    from core.privacy import PrivacyGuard
    from core.module_paths import InvalidModuleName
    raw, chunks = _seed(fake_repo, "raw", "legit"), _seed(fake_repo, "chunks", "legit")

    with pytest.raises(InvalidModuleName):
        PrivacyGuard().wipe_module_data(bad)

    assert raw.exists() and chunks.exists()
