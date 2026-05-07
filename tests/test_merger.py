"""Tests for core/merger.py (sync parts only — LLM calls mocked)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch
from core.merger import _deduplicate, _word_overlap, merge
from core.dispatcher import TaskResult
from core.model_router import RouteResult


def test_word_overlap_identical():
    assert _word_overlap("hello world test", "hello world test") == 1.0


def test_word_overlap_zero():
    assert _word_overlap("apple banana cherry", "dog cat fish") == 0.0


def test_word_overlap_partial():
    score = _word_overlap("python is great", "python is fast")
    assert 0.0 < score < 1.0


def test_deduplicate_keeps_unique():
    answers = [
        "Python is a programming language.",
        "JavaScript runs in browsers.",
        "Rust ensures memory safety.",
    ]
    result = _deduplicate(answers)
    assert len(result) == 3


def test_deduplicate_removes_near_identical():
    answers = [
        "Python is a high-level programming language used for many things.",
        "Python is a high-level programming language used for many things.",
    ]
    result = _deduplicate(answers)
    assert len(result) == 1


def _make_result(answer, module="knowledge", source="external"):
    return TaskResult(
        task_id="t1",
        module=module,
        result=RouteResult(answer=answer, source=source),
    )


@pytest.mark.asyncio
async def test_merge_single_result():
    results = [_make_result("The answer is 42.")]
    answer  = await merge(results, "what is the answer")
    assert answer == "The answer is 42."


@pytest.mark.asyncio
async def test_merge_empty_results():
    answer = await merge([], "anything")
    assert "unable" in answer.lower() or len(answer) > 0


@pytest.mark.asyncio
async def test_merge_skips_error_results():
    results = [
        _make_result("[Module coding error: timeout]", source="error"),
        _make_result("Python uses indentation for blocks.", source="external"),
    ]
    answer = await merge(results, "how does python work")
    assert "Python uses indentation" in answer


@pytest.mark.asyncio
async def test_merge_multi_calls_weave(monkeypatch):
    """With multiple valid results, merger should call LLM weave or join."""
    results = [
        _make_result("Answer from web search.", module="web_search"),
        _make_result("Answer from knowledge base.", module="knowledge"),
    ]
    # Mock the LLM call to avoid needing Ollama in tests
    with patch("core.merger._weave", new_callable=AsyncMock) as mock_weave:
        mock_weave.return_value = "Combined answer."
        answer = await merge(results, "test query")
        assert mock_weave.called
        assert answer == "Combined answer."
