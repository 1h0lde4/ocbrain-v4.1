import pytest
from core.web.parser import parse_html
from core.web.cleaner import normalize_text, chunk_text, deduplicate_chunks

SAMPLE_HTML = (
    "<html>"
    "<head><style>.hidden { display: none; }</style></head>"
    "<body>"
    "<header>Header content</header>"
    "<main>"
    "<h1>Main Title</h1>"
    "<p>This is the core content.</p>"
    '<script>console.log("Ignore me");</script>'
    "</main>"
    "<footer>Footer content</footer>"
    "</body>"
    "</html>"
)

def test_parse_html():
    text = parse_html(SAMPLE_HTML)
    assert "Ignore me" not in text
    assert ".hidden" not in text
    assert "Header content" not in text
    assert "Footer content" not in text
    assert "Main Title" in text
    assert "This is the core content." in text

def test_normalize_text():
    raw = "This   has \t extra spaces.\n\n\nAnd  newlines."
    cleaned = normalize_text(raw)
    assert "This has extra spaces." in cleaned
    assert "\n\nAnd newlines." in cleaned

def test_chunk_text():
    # 100 words, chunk=60, overlap=20 → step=40
    # Chunk 1: words[0:60], Chunk 2: words[40:100] (60 words), no more.
    text = "word " * 100
    chunks = chunk_text(text, chunk_size_words=60, overlap_words=20)
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 60
    assert len(chunks[1].split()) == 60

def test_chunk_text_overlap_error():
    text = "word " * 10
    with pytest.raises(ValueError):
        chunk_text(text, chunk_size_words=10, overlap_words=10)

def test_deduplicate_chunks():
    chunks = [
        "This is a chunk.",
        "This is a chunk.  ",  # Should be deduped (whitespace-normalized)
        "This is another chunk."
    ]
    unique = deduplicate_chunks(chunks)
    assert len(unique) == 2
    assert unique[0] == "This is a chunk."
    assert unique[1] == "This is another chunk."
