"""Tests for modules/system_ctrl/module.py — especially the safety allowlist."""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.system_ctrl.module import (
    ACTION_HANDLERS,
    SAFE_ROOT,
    Module,
    _delete_file,
    _list_dir,
    _read_file,
    _write_file,
)


@pytest.fixture
def safe_tmp_path(tmp_path):
    """Create an isolated test directory inside the system_ctrl sandbox."""
    path = SAFE_ROOT / "test_system_ctrl" / tmp_path.name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_allowlist_contains_expected_actions():
    expected = {
        "open",
        "launch",
        "write_file",
        "read_file",
        "delete_file",
        "list_dir",
        "get_cwd",
    }
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


def test_write_and_read_file(safe_tmp_path):
    fpath = str(safe_tmp_path / "test.txt")
    write_result = _write_file(fpath, "hello openclaw")
    assert "created" in write_result.lower() or "File" in write_result

    read_result = _read_file(fpath)
    assert "hello openclaw" in read_result


def test_read_nonexistent_file():
    result = _read_file("/nonexistent/path/file.txt")
    assert "not found" in result.lower()


def test_list_dir(safe_tmp_path):
    (safe_tmp_path / "file1.txt").write_text("a")
    (safe_tmp_path / "file2.py").write_text("b")
    (safe_tmp_path / "subdir").mkdir()
    result = _list_dir(str(safe_tmp_path))
    assert "file1.txt" in result
    assert "file2.py" in result
    assert "[DIR]" in result


def test_delete_file(safe_tmp_path):
    f = safe_tmp_path / "todelete.txt"
    f.write_text("bye")
    result = _delete_file(str(f))
    assert "Deleted" in result
    assert not f.exists()


def test_delete_nonexistent_file():
    result = _delete_file("/nonexistent/file.txt")
    assert "not found" in result.lower()


def test_execute_write_file():
    module = Module()
    target = SAFE_ROOT / "test_system_ctrl" / "execute_write_file" / "hello.txt"
    shutil.rmtree(target.parent, ignore_errors=True)
    try:
        result = module._execute(
            {
                "action": "write_file",
                "path": str(target),
                "content": "test content",
            }
        )
        assert "created" in result.lower() or "hello.txt" in result
        assert target.exists()
    finally:
        shutil.rmtree(target.parent, ignore_errors=True)
