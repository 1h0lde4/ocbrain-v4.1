"""Tests for core/context.py"""
import sys
import time
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def test_context_save_and_retrieve(tmp_path, monkeypatch):
    """Context saves turns and retrieves them correctly."""
    # Redirect DB to temp dir
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_context.sqlite")
    from core.context import ContextMemory
    ctx = ContextMemory()

    ctx.save("what is AI?", ["knowledge"], "AI is artificial intelligence.")
    ctx.save("write hello world", ["coding"], "print('hello world')")

    turns = ctx.last_n(10)
    assert len(turns) == 2
    assert turns[0].query == "what is AI?"
    assert turns[1].query == "write hello world"


def test_context_last_n_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx2.sqlite")
    from core.context import ContextMemory
    ctx = ContextMemory()

    for i in range(20):
        ctx.save(f"query {i}", ["knowledge"], f"answer {i}")

    turns = ctx.last_n(5)
    assert len(turns) == 5
    # Should return the 5 most recent
    assert turns[-1].query == "query 19"


def test_context_boost_module(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx3.sqlite")
    from core.context import ContextMemory
    ctx = ContextMemory()

    ctx.save("write code", ["coding"], "some code")
    boost = ctx.boost_module("coding", recent_turns=3)
    assert boost > 0.0

    no_boost = ctx.boost_module("web_search", recent_turns=3)
    assert no_boost == 0.0


def test_context_entity_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx4.sqlite")
    from core.context import ContextMemory
    ctx = ContextMemory()

    ctx.save(
        "fetch https://example.com",
        ["web_search"],
        "fetched content",
        entities={"urls": ["https://example.com"], "languages": ["python"]},
    )

    urls = ctx.get_entity("urls")
    assert "https://example.com" in urls


def test_context_format_for_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx5.sqlite")
    from core.context import ContextMemory
    ctx = ContextMemory()

    ctx.save("Hello", ["knowledge"], "Hi there!")
    ctx.save("How are you?", ["knowledge"], "I am fine, thanks.")

    prompt_str = ctx.format_for_prompt(5)
    assert "Hello" in prompt_str
    assert "Hi there!" in prompt_str
    assert "How are you?" in prompt_str


def test_context_empty_db_format(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "test_ctx6.sqlite")
    from core.context import ContextMemory
    ctx = ContextMemory()
    assert ctx.format_for_prompt(5) == ""
