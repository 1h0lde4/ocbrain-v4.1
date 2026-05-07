"""Tests for core/decomposer.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parser import parse
from core.classifier import Label
from core.decomposer import build, Task


def _labels(*modules):
    return [Label(module=m, confidence=0.8, subtask="test") for m in modules]


def test_single_module_no_deps():
    parsed = parse("explain neural networks")
    labels = _labels("knowledge")
    tasks  = build(parsed, labels)
    assert len(tasks) == 1
    assert tasks[0].module == "knowledge"
    assert tasks[0].deps == []


def test_parallel_two_modules():
    parsed = parse("search the web and open spotify")
    labels = _labels("web_search", "system_ctrl")
    tasks  = build(parsed, labels)
    # No sequential signal → parallel → both should have no deps
    assert len(tasks) == 2
    modules = {t.module for t in tasks}
    assert "web_search" in modules
    assert "system_ctrl" in modules


def test_sequential_signal():
    parsed = parse("search for python docs then write a script")
    labels = _labels("web_search", "coding")
    tasks  = build(parsed, labels)
    assert len(tasks) == 2
    # Coding task should depend on web_search task
    coding_task = next(t for t in tasks if t.module == "coding")
    web_task    = next(t for t in tasks if t.module == "web_search")
    assert web_task.id in coding_task.deps


def test_empty_labels():
    parsed = parse("hello")
    tasks  = build(parsed, [])
    assert tasks == []


def test_task_ids_unique():
    parsed = parse("search and code and explain")
    labels = _labels("web_search", "coding", "knowledge")
    tasks  = build(parsed, labels)
    ids = [t.id for t in tasks]
    assert len(ids) == len(set(ids))
