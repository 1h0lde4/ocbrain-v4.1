"""Regression tests for instance-scoped Config watcher paths."""
from pathlib import Path

import threading

import pytest

import core.config as config_module
from core.config import Config


def _write_config(root: Path, language: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.toml").write_text(
        f'[global]\nlanguage = "{language}"\n', encoding="utf-8"
    )
    (root / "models.toml").write_text("", encoding="utf-8")
    (root / "sources.toml").write_text("", encoding="utf-8")


def test_watcher_uses_instance_path_after_global_default_changes(tmp_path, monkeypatch):
    instance_root = tmp_path / "instance-config"
    default_root = tmp_path / "new-global-default"
    _write_config(instance_root, "instance-root")
    _write_config(default_root, "global-default")

    cfg = Config(config_dir=instance_root, start_watcher=False)
    assert cfg.get("global.language") == "instance-root"

    captured = {}

    class CapturedThread:
        def __init__(self, *, target, daemon):
            captured["target"] = target
            captured["daemon"] = daemon

        def start(self):
            # Invoke the target manually after changing CONFIG_DIR below. No
            # real daemon thread or timing-dependent sleep is required.
            return None

    monkeypatch.setattr(config_module.threading, "Thread", CapturedThread)
    cfg._start_watcher()
    monkeypatch.setattr(config_module, "CONFIG_DIR", default_root)

    class StopAfterFirstScan(Exception):
        pass

    assert captured["daemon"] is True

    original_sleep = config_module.time.sleep
    scan_thread_id = threading.get_ident()

    def stop_after_scan(seconds):
        # time is a shared module; keep the already-running singleton watcher
        # unaffected and stop only the synchronously captured test target.
        if threading.get_ident() == scan_thread_id:
            raise StopAfterFirstScan
        return original_sleep(seconds)

    monkeypatch.setattr(config_module.time, "sleep", stop_after_scan)
    with pytest.raises(StopAfterFirstScan):
        captured["target"]()

    assert cfg.config_dir == instance_root
    assert cfg.get("global.language") == "instance-root"
    assert Config(config_dir=default_root, start_watcher=False).get("global.language") == "global-default"
