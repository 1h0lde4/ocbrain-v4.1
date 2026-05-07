"""
learning/cleaner.py — Raw text → clean, scored, deduped chunks.
Runs every 6 hours over data/raw/ backlog.
"""
import re
from pathlib import Path

from learning.chunker import Chunk, chunk, deduplicate, score_quality
from learning.embedder import ingest_chunks

DATA_RAW    = Path(__file__).parent.parent / "data" / "raw"
DATA_CHUNKS = Path(__file__).parent.parent / "data" / "chunks"


def run_all(registry: dict):
    for module_name in registry:
        run_module(module_name, registry)


def run_module(module_name: str, registry: dict):
    in_dir = DATA_RAW / module_name
    if not in_dir.exists():
        return

    all_chunks: list[Chunk] = []

    for fpath in in_dir.glob("*.txt"):
        try:
            raw_text   = fpath.read_text(encoding="utf-8", errors="replace")
            source_url = _extract_url(raw_text)
            body       = _strip_header(raw_text)
            body       = _clean(body)
            chunks     = chunk(body, module_name,
                               source_url=source_url, source_type="crawl")
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"[cleaner] {fpath.name}: {e}")

    # Deduplicate across all chunks for this module
    unique = deduplicate(all_chunks)

    # Ingest into ChromaDB
    ingest_chunks(module_name, unique, registry)
    print(f"[cleaner] {module_name}: {len(all_chunks)} → {len(unique)} unique chunks")

    # Move processed files to chunks dir
    done_dir = DATA_CHUNKS / module_name
    done_dir.mkdir(parents=True, exist_ok=True)
    for fpath in in_dir.glob("*.txt"):
        fpath.rename(done_dir / fpath.name)


def _clean(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)               # strip HTML tags
    text = re.sub(r'\s{3,}', '\n\n', text)             # collapse whitespace
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F]+', ' ', text)  # strip non-Latin
    text = text.strip()
    return text


def _extract_url(text: str) -> str:
    m = re.match(r'^SOURCE:\s*(\S+)', text)
    return m.group(1) if m else ""


def _strip_header(text: str) -> str:
    lines = text.splitlines()
    # Remove "SOURCE: url" header line
    if lines and lines[0].startswith("SOURCE:"):
        lines = lines[2:]
    return "\n".join(lines)
