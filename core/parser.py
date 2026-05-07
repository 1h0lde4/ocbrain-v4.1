"""
core/parser.py — Tokenize raw query, extract entities and keywords.
No LLM needed — pure NLP. Runs in < 5 ms.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedQuery:
    raw: str
    tokens: list[str]
    entities: dict          # {urls, filenames, language, dates, names}
    language: str           # detected user language code
    keywords: list[str]     # lower-case signal words


# Regex patterns
_URL_RE      = re.compile(r'https?://\S+')
_FILE_RE     = re.compile(r'\b[\w\-]+\.\w{1,6}\b')
_DATE_RE     = re.compile(r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b')
_CODE_LANG   = re.compile(
    r'\b(python|javascript|typescript|rust|go|java|c\+\+|cpp|ruby|php|swift|kotlin|bash|sql)\b',
    re.IGNORECASE,
)
_STOP_WORDS  = {
    "a","an","the","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","could",
    "should","may","might","shall","can","need","dare","ought",
    "used","to","of","in","for","on","with","at","by","from",
    "as","or","and","but","if","then","than","so","yet","nor",
    "not","no","nor","just","also","too",
}


def parse(raw: str) -> ParsedQuery:
    text   = raw.strip()
    tokens = text.lower().split()

    # Entities
    urls      = _URL_RE.findall(text)
    filenames = [f for f in _FILE_RE.findall(text) if "." in f and f not in urls]
    dates     = _DATE_RE.findall(text)
    languages = _CODE_LANG.findall(text)

    entities = {
        "urls":      urls,
        "filenames": filenames,
        "dates":     dates,
        "languages": [l.lower() for l in languages],
    }

    # Detect query language (basic heuristic — extend with langdetect if needed)
    lang = _detect_language(text)

    # Keywords: meaningful tokens stripped of stop words
    keywords = [
        t.lower().strip(".,!?;:'\"()")
        for t in tokens
        if t.lower() not in _STOP_WORDS and len(t) > 2
    ]

    return ParsedQuery(
        raw=raw,
        tokens=tokens,
        entities=entities,
        language=lang,
        keywords=keywords,
    )


def _detect_language(text: str) -> str:
    """Very lightweight language detection — extend later."""
    try:
        import langdetect
        return langdetect.detect(text)
    except Exception:
        return "en"
