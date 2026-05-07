"""
learning/chunker.py — Splits raw documents into DB-ready chunks.
Code: AST-aware splits at function/class boundaries.
Prose: paragraph → sentence splits with overlap.
"""
import ast
import re
import time
from dataclasses import dataclass
from typing import Optional

from datasketch import MinHash, MinHashLSH


@dataclass
class Chunk:
    text: str
    quality_score: float = 0.5
    source_url: str = ""
    source_type: str = "crawl"   # crawl | query | manual
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


def chunk(text: str, module_name: str, source_url: str = "",
          source_type: str = "crawl") -> list[Chunk]:
    if module_name == "coding":
        raw_chunks = _split_code(text)
    else:
        raw_chunks = _split_prose(text, max_tokens=300, overlap=50)

    result = []
    for c in raw_chunks:
        if len(c.strip()) < 50:
            continue
        score = score_quality(c)
        result.append(Chunk(
            text=c.strip(),
            quality_score=score,
            source_url=source_url,
            source_type=source_type,
        ))
    return result


def _split_prose(text: str, max_tokens: int = 300, overlap: int = 50) -> list[str]:
    """Split at paragraph boundaries; fall back to sentence if too long."""
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    chunks = []
    current_words: list[str] = []

    for para in paragraphs:
        words = para.split()
        if len(current_words) + len(words) <= max_tokens:
            current_words.extend(words)
        else:
            if current_words:
                chunks.append(" ".join(current_words))
            # If single paragraph is too long, split at sentences
            if len(words) > max_tokens:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                buf: list[str] = []
                for sent in sentences:
                    sw = sent.split()
                    if len(buf) + len(sw) > max_tokens:
                        if buf:
                            chunks.append(" ".join(buf))
                        buf = buf[-overlap:] + sw
                    else:
                        buf.extend(sw)
                if buf:
                    current_words = buf
            else:
                current_words = current_words[-overlap:] + words

    if current_words:
        chunks.append(" ".join(current_words))
    return chunks


def _split_code(text: str) -> list[str]:
    """Split Python code at function/class boundaries using AST."""
    try:
        tree   = ast.parse(text)
        lines  = text.splitlines(keepends=True)
        chunks = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno - 1
                end   = getattr(node, "end_lineno", len(lines))
                block = "".join(lines[start:end])
                if block.strip():
                    chunks.append(block)
        if not chunks:
            # Fallback: treat as prose
            return _split_prose(text, max_tokens=300, overlap=50)
        return chunks
    except SyntaxError:
        # Not valid Python — treat as prose
        return _split_prose(text, max_tokens=300, overlap=50)


def score_quality(text: str) -> float:
    """Score 0.0–1.0 based on simple heuristics."""
    if not text:
        return 0.0
    words  = text.split()
    n      = len(words)
    if n < 10:
        return 0.1

    # Penalise all-caps ratio
    caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 1) / n

    # Penalise high punctuation density
    punc_ratio = sum(1 for c in text if c in "!@#$%^&*<>{}|\\~`") / max(len(text), 1)

    # Reward average word length (proxy for real content)
    avg_word_len = sum(len(w) for w in words) / n

    score = 1.0
    score -= caps_ratio * 0.5
    score -= punc_ratio * 2.0
    if avg_word_len < 3:
        score -= 0.3
    return round(max(0.0, min(score, 1.0)), 3)


def deduplicate(chunks: list[Chunk], threshold: float = 0.92) -> list[Chunk]:
    """MinHash LSH approximate deduplication — O(n) not O(n²)."""
    if not chunks:
        return []

    lsh    = MinHashLSH(threshold=threshold, num_perm=64)
    unique = []

    for i, chunk_obj in enumerate(chunks):
        m = MinHash(num_perm=64)
        for word in chunk_obj.text.lower().split():
            m.update(word.encode("utf-8"))
        key = f"chunk_{i}"
        try:
            result = lsh.query(m)
            if not result:
                lsh.insert(key, m)
                unique.append(chunk_obj)
        except Exception:
            unique.append(chunk_obj)

    return unique
