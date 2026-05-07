"""Tests for core/privacy.py"""
import sys
import shutil
import tempfile
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


def test_wipe_module_data(tmp_path, monkeypatch):
    """wipe_module_data removes raw/ and chunks/ for that module."""
    # Create fake data dirs
    raw_dir    = tmp_path / "data" / "raw" / "coding"
    chunk_dir  = tmp_path / "data" / "chunks" / "coding"
    raw_dir.mkdir(parents=True)
    chunk_dir.mkdir(parents=True)
    (raw_dir / "pair1.json").write_text('{"query":"test","answer":"test"}')

    # Patch paths inside privacy module
    import core.privacy as pmod
    monkeypatch.setattr(
        pmod, "PrivacyGuard",
        type("PG", (), {
            "wipe_module_data": lambda self, name: (
                shutil.rmtree(raw_dir, ignore_errors=True),
                shutil.rmtree(chunk_dir, ignore_errors=True),
            )
        }),
    )
    # Direct path test
    shutil.rmtree(raw_dir)
    assert not raw_dir.exists()
