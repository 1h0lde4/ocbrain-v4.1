"""Tests for learning/chunker.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.chunker import chunk, score_quality, deduplicate, Chunk


def test_prose_chunk_basic():
    text   = "This is a sentence. " * 50
    chunks = chunk(text, "knowledge")
    assert len(chunks) > 0
    for c in chunks:
        assert len(c.text) > 0


def test_prose_chunk_respects_max_tokens():
    text   = " ".join([f"word{i}" for i in range(1000)])
    chunks = chunk(text, "knowledge")
    for c in chunks:
        word_count = len(c.text.split())
        assert word_count <= 400   # 300 + overlap tolerance


def test_code_chunk_keeps_functions():
    code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

class Calculator:
    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
'''
    chunks = chunk(code, "coding")
    texts  = [c.text for c in chunks]
    # Each function/class should be a separate chunk
    assert any("def add" in t for t in texts)
    assert any("def multiply" in t for t in texts)
    assert any("class Calculator" in t for t in texts)


def test_quality_score_range():
    texts = [
        "This is a well-written paragraph with proper sentences and good content.",
        "CAPS CAPS CAPS CAPS CAPS CAPS CAPS CAPS CAPS CAPS",
        "ok",
        "A moderately useful piece of text about machine learning concepts.",
    ]
    for text in texts:
        score = score_quality(text)
        assert 0.0 <= score <= 1.0


def test_quality_penalises_short():
    score = score_quality("hi")
    assert score < 0.5


def test_quality_rewards_content():
    score = score_quality(
        "Machine learning is a subset of artificial intelligence that enables "
        "computers to learn from data without being explicitly programmed."
    )
    assert score >= 0.5


def test_deduplicate_removes_duplicates():
    c1 = Chunk(text="The quick brown fox jumps over the lazy dog")
    c2 = Chunk(text="The quick brown fox jumps over the lazy dog")   # exact dup
    c3 = Chunk(text="A completely different sentence about Python.")
    result = deduplicate([c1, c2, c3])
    assert len(result) == 2   # c2 removed as near-duplicate of c1


def test_deduplicate_keeps_unique():
    chunks = [
        Chunk(text="Python is a high-level programming language."),
        Chunk(text="JavaScript runs in the browser and on servers."),
        Chunk(text="Rust provides memory safety without garbage collection."),
    ]
    result = deduplicate(chunks)
    assert len(result) == 3


def test_chunk_assigns_metadata():
    text   = "This is some content about AI systems."
    chunks = chunk(text, "knowledge", source_url="https://example.com", source_type="crawl")
    for c in chunks:
        assert c.source_url == "https://example.com"
        assert c.source_type == "crawl"
        assert c.timestamp > 0
