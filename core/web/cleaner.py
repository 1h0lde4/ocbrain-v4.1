import re
from typing import List

def normalize_text(text: str) -> str:
    """
    Remove boilerplate and normalize text.
    """
    # Replace multiple spaces with a single space
    text = re.sub(r'[ \t]+', ' ', text)
    # Replace multiple newlines with a double newline
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

def chunk_text(text: str, chunk_size_words: int = 250, overlap_words: int = 50) -> List[str]:
    """
    Chunk text into manageable pieces. Uses word count as a proxy for tokens
    (approx 1 word ~ 1.3 tokens). 250 words is roughly 300-350 tokens.
    """
    if overlap_words >= chunk_size_words:
        raise ValueError("overlap_words must be strictly less than chunk_size_words")
        
    words = text.split()
    chunks = []
    
    if not words:
        return chunks

    i = 0
    while i < len(words):
        end = min(i + chunk_size_words, len(words))
        chunk_words = words[i:end]
        chunk = ' '.join(chunk_words)
        chunks.append(chunk)
        if end == len(words):
            break
        i += chunk_size_words - overlap_words
        
    return chunks

def deduplicate_chunks(chunks: List[str]) -> List[str]:
    """
    Simple exact-match deduplication for chunks extracted from a single source.
    """
    seen = set()
    unique_chunks = []
    for chunk in chunks:
        # A simple normalization for deduplication purposes
        normalized = chunk.lower().strip()
        if normalized not in seen:
            seen.add(normalized)
            unique_chunks.append(chunk)
    return unique_chunks

def clean_and_chunk(raw_text: str) -> List[str]:
    """
    Full pipeline to normalize, chunk, and deduplicate text.
    """
    normalized = normalize_text(raw_text)
    chunks = chunk_text(normalized)
    return deduplicate_chunks(chunks)
