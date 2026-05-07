"""Tests for core/parser.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parser import parse


def test_basic_parse():
    result = parse("write a python script to sort a list")
    assert result.raw == "write a python script to sort a list"
    assert "python" in result.keywords or "python" in [e.lower() for e in result.entities.get("languages", [])]
    assert len(result.tokens) > 0


def test_url_extraction():
    result = parse("fetch data from https://example.com and process it")
    assert "https://example.com" in result.entities["urls"]


def test_filename_extraction():
    result = parse("open the file report.pdf and summarize it")
    assert any("report.pdf" in f for f in result.entities["filenames"])


def test_language_detection():
    result = parse("write a rust function to parse JSON")
    assert "rust" in result.entities["languages"]


def test_empty_query():
    result = parse("")
    assert result.raw == ""
    assert result.tokens == []


def test_stopwords_removed():
    result = parse("what is the meaning of life")
    # stop words like "is", "the", "of" should not be in keywords
    assert "the" not in result.keywords
    assert "is" not in result.keywords


def test_multiple_languages():
    result = parse("compare python and javascript performance")
    langs = result.entities["languages"]
    assert "python" in langs
    assert "javascript" in langs
