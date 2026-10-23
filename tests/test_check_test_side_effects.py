"""Tests for the CI protected-runtime-tree mutation guard."""
import json
from pathlib import Path

from scripts.check_test_side_effects import capture_state, main


def test_snapshot_covers_untracked_nested_files_and_empty_directories(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.toml").write_text("[global]\n", encoding="utf-8")
    (tmp_path / "modules" / "generated" / "knowledge.db").mkdir(parents=True)
    (tmp_path / "modules" / "generated" / "knowledge.db" / "chroma.sqlite3").write_bytes(b"db")
    (tmp_path / "modules" / "empty-generated-dir").mkdir()

    state = capture_state(tmp_path)
    assert state["config/settings.toml"]["kind"] == "file"
    assert state["modules/generated/knowledge.db/chroma.sqlite3"]["kind"] == "file"
    assert state["modules/empty-generated-dir"]["kind"] == "directory"
    assert state["data/raw"]["kind"] == "missing"


def test_verify_fails_for_ignored_like_file_and_toml_changes(tmp_path):
    config = tmp_path / "config"
    modules = tmp_path / "modules"
    config.mkdir()
    modules.mkdir()
    (config / "settings.toml").write_text("[global]\nvalue = 1\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    assert main(["--snapshot", str(baseline), "--root", str(tmp_path)]) == 0

    (modules / "untracked-or-ignored.sqlite3").write_bytes(b"generated")
    (config / "settings.toml").write_text("[global]\nvalue = 2\n", encoding="utf-8")
    assert main(["--verify", str(baseline), "--root", str(tmp_path)]) == 1


def test_verify_detects_metadata_only_changes(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    protected_file = config / "settings.toml"
    protected_file.write_text("[global]\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    assert main(["--snapshot", str(baseline), "--root", str(tmp_path)]) == 0

    original_mode = protected_file.stat().st_mode & 0o777
    protected_file.chmod(0o600 if original_mode != 0o600 else 0o644)
    assert main(["--verify", str(baseline), "--root", str(tmp_path)]) == 1


def test_verify_detects_symlink_and_directory_changes(tmp_path):
    (tmp_path / "modules").mkdir()
    baseline = tmp_path / "baseline.json"
    assert main(["--snapshot", str(baseline), "--root", str(tmp_path)]) == 0
    generated = tmp_path / "modules" / "generated"
    generated.mkdir()
    link = tmp_path / "modules" / "generated-link"
    try:
        link.symlink_to(generated, target_is_directory=True)
    except (OSError, NotImplementedError):
        link = None
    assert main(["--verify", str(baseline), "--root", str(tmp_path)]) == 1
