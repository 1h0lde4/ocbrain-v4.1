"""
core/capabilities/foundation/readers/text_readers.py — inline readers.

Stdlib only, single pass, bounded by the artifact size limit the adapter
enforces before calling. Each function takes (bytes, options) and returns a
plain *body dict* (blocks / tables / warnings ...) that the host then passes
through Document.from_untrusted() -- inline readers get exactly the same
strict coercion and caps as isolated ones.

Deliberate scope:
  * text/plain      paragraphs (blank-line separated), ``lines`` selection
  * text/markdown   ATX headings, fenced code, list items, paragraphs.
                    Setext headings, Markdown tables and front matter are NOT
                    interpreted (they read as paragraphs) -- documented gap.
                    Links/images are text; nothing is fetched or rendered.
  * text/csv, tsv   one table; the first row is *assumed* to be a header
                    (warning header_row_assumed) -- an explicit convention,
                    not a guess dressed up as fact.
"""
from __future__ import annotations

import codecs
import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from core.capabilities.descriptors import CapabilityStatus
from core.capabilities.foundation.readers.base import (
    MEDIA_TSV, ReaderError,
)

READER_VERSION = "1.0.0"
_FIELD_LIMIT = 262_144  # per-field cap for the csv module


def _warn(code: str, message: str = "", locator: str = "") -> Dict[str, str]:
    return {"code": code, "message": message, "locator": locator}


def decode_text(data: bytes) -> Tuple[str, List[Dict[str, str]]]:
    warnings: List[Dict[str, str]] = []
    if data.startswith(codecs.BOM_UTF8):
        text = data[3:].decode("utf-8", errors="strict")
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError as e:
            raise ReaderError(CapabilityStatus.MALFORMED, "not_valid_utf16") from e
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
            warnings.append(_warn(
                "encoding_fallback_cp1252",
                "not valid UTF-8; decoded as Windows-1252 (lossy)"))
    if "\x00" in text:
        raise ReaderError(CapabilityStatus.MALFORMED, "binary_content",
                          "NUL bytes in text artifact")
    return text.replace("\r\n", "\n").replace("\r", "\n"), warnings


def _line_window(opts: Dict[str, Any], total: int) -> Tuple[int, int]:
    """Resolve the ``lines`` selector (1-based, inclusive) to a 0-based
    half-open window."""
    lines = (opts.get("selection") or {}).get("lines")
    if lines is None:
        return 0, total
    if (not isinstance(lines, (list, tuple)) or len(lines) != 2
            or not all(isinstance(n, int) and not isinstance(n, bool)
                       for n in lines) or lines[0] < 1 or lines[1] < lines[0]):
        raise ReaderError(CapabilityStatus.INVALID_REQUEST, "bad_lines_selector",
                          "lines must be [start, end], 1-based, start<=end")
    return min(lines[0] - 1, total), min(lines[1], total)


def read_text(data: bytes, opts: Dict[str, Any]) -> Dict[str, Any]:
    text, warnings = decode_text(data)
    lines = text.split("\n")
    lo, hi = _line_window(opts, len(lines))
    blocks: List[Dict[str, Any]] = []
    start: Optional[int] = None
    for i in range(lo, hi + 1):
        blank = i >= hi or not lines[i].strip()
        if not blank and start is None:
            start = i
        elif blank and start is not None:
            blocks.append({"kind": "paragraph",
                           "text": "\n".join(lines[start:i]).strip(),
                           "locator": f"lines={start + 1}-{i}"})
            start = None
    return {"blocks": blocks, "warnings": warnings}


_ATX = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_LIST = re.compile(r"^[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+(.*\S)[ \t]*$")
_FENCE = re.compile(r"^[ \t]{0,3}(```+|~~~+)")


def read_markdown(data: bytes, opts: Dict[str, Any]) -> Dict[str, Any]:
    text, warnings = decode_text(data)
    lines = text.split("\n")
    lo, hi = _line_window(opts, len(lines))
    blocks: List[Dict[str, Any]] = []
    title = ""
    para_start: Optional[int] = None

    def flush_para(end: int) -> None:
        nonlocal para_start
        if para_start is not None:
            blocks.append({"kind": "paragraph",
                           "text": "\n".join(lines[para_start:end]).strip(),
                           "locator": f"lines={para_start + 1}-{end}"})
            para_start = None

    i = lo
    while i < hi:
        line = lines[i]
        fence = _FENCE.match(line)
        if fence:
            flush_para(i)
            marker = fence.group(1)
            j = i + 1
            while j < hi and not lines[j].lstrip().startswith(marker[:3]):
                j += 1
            blocks.append({"kind": "code", "text": "\n".join(lines[i + 1:j]),
                           "locator": f"lines={i + 1}-{min(j + 1, hi)}"})
            i = j + 1
            continue
        heading = _ATX.match(line)
        if heading:
            flush_para(i)
            level = len(heading.group(1))
            blocks.append({"kind": "heading", "level": level,
                           "text": heading.group(2), "locator": f"lines={i + 1}"})
            if level == 1 and not title:
                title = heading.group(2)
        elif _LIST.match(line):
            flush_para(i)
            blocks.append({"kind": "list_item", "text": _LIST.match(line).group(1),
                           "locator": f"lines={i + 1}"})
        elif not line.strip():
            flush_para(i)
        elif para_start is None:
            para_start = i
        i += 1
    flush_para(min(i, hi))
    return {"title": title, "blocks": blocks, "warnings": warnings}


def _col_letter(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out or "A"


def read_csv(data: bytes, opts: Dict[str, Any]) -> Dict[str, Any]:
    text, warnings = decode_text(data)
    if (opts.get("selection") or {}).get("lines") is not None:
        raise ReaderError(CapabilityStatus.UNSUPPORTED, "selection_unsupported:lines",
                          "line selection is not defined for tabular data")
    limits = opts.get("limits") or {}
    max_rows = int(limits.get("max_rows", 2000))
    max_cols = int(limits.get("max_cols", 100))
    delimiter = "\t" if opts.get("media_type") == MEDIA_TSV else ","
    csv.field_size_limit(_FIELD_LIMIT)
    rows: List[List[str]] = []
    total_rows = 0
    widest = 0
    truncated = False
    try:
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter):
            if not any(cell.strip() for cell in row):
                continue
            total_rows += 1
            widest = max(widest, len(row))
            if len(rows) < max_rows:
                rows.append(row[:max_cols])
            else:
                truncated = True
    except csv.Error as e:
        raise ReaderError(CapabilityStatus.MALFORMED, "csv_parse_error",
                          str(e)[:200]) from e
    if not rows:
        return {"blocks": [], "tables": [], "warnings": warnings}
    if widest > max_cols:
        truncated = True
    header_rows = 1 if len(rows) >= 2 else 0
    if header_rows:
        warnings.append(_warn("header_row_assumed",
                              "first row treated as a header (convention)"))
    table = {"rows": rows, "header_rows": header_rows, "truncated": truncated,
             "row_count": total_rows, "col_count": widest,
             "range": f"A1:{_col_letter(min(widest, max_cols))}{len(rows)}",
             "locator": f"rows=1-{len(rows)}"}
    return {"blocks": [{"kind": "table", "table_ref": 1, "text": "",
                        "locator": table["locator"]}],
            "tables": [table], "warnings": warnings}
