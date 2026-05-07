"""Tests for modules/system_ctrl/module.py — especially the safety allowlist."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from modules.system_ctrl.module import Module, ACTION_HANDLERS, _write_file, _read_file, _list_dir, _delete_file


def test_allowlist_contains_expected_actions():
    expected = {"open", "launch", "write_file", "read_file", "delete_file", "list_dir", "get_cwd"}
    for action in expected:
        assert action in ACTION_HANDLERS


def test_unknown_action_rejected():
    module = Module()
    result = module._execute({"action": "run_shell", "cmd": "rm -rf /"})
    assert "not in the allowed list" in result
    assert "rm" not in result  # never echoed back as executed


def test_empty_action_rejected():
    module = Module()
    result = module._execute({})
    assert "not in the allowed list" in result


def test_write_and_read_file(tmp_path):
    fpath = str(tmp_path / "test.txt")
    write_result = _write_file(fpath, "hello openclaw")
    assert "created" in write_result.lower() or "File" in write_result

    read_result = _read_file(fpath)
    assert "hello openclaw" in read_result


def test_read_nonexistent_file():
    result = _read_file("/nonexistent/path/file.txt")
    assert "not found" in result.lower()


def test_list_dir(tmp_path):
    (tmp_path / "file1.txt").write_text("a")
    (tmp_path / "file2.py").write_text("b")
    (tmp_path / "subdir").mkdir()
    result = _list_dir(str(tmp_path))
    assert "file1.txt" in result
    assert "file2.py" in result
    assert "[DIR]" in result


def test_delete_file(tmp_path):
    f = tmp_path / "todelete.txt"
    f.write_text("bye")
    result = _delete_file(str(f))
    assert "Deleted" in result
    assert not f.exists()


def test_delete_nonexistent_file():
    result = _delete_file("/nonexistent/file.txt")
    assert "not found" in result.lower()


def test_execute_write_file():
    module = Module()
    with tempfile.TemporaryDirectory() as d:
        result = module._execute({
            "action":  "write_file",
            "path":    f"{d}/hello.txt",
            "content": "test content",
        })
        assert "created" in result.lower() or "hello.txt" in result
        assert Path(f"{d}/hello.txt").exists()
