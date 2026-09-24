"""
core/capabilities/foundation/readers/base.py — reader contracts, limits, sniffing.

A *reader* is one implementation of "bytes of a given format -> structured
document body". FILE_READING (the capability) is not a PDF parser: it routes
bytes to whichever registered reader claims them, so a parser can be replaced
(or a second one added) without changing the capability's identity or contract.

Two execution modes, chosen per reader, never per call:

    inline     stdlib-only, trivially bounded formats (text, markdown, CSV).
    isolated   any format parsed by a third-party library (PDF, DOCX, XLSX).
               Runs ONLY in a separate, resource-limited subprocess
               (readers/isolation.py); the host process never imports these
               libraries, so a parser bug cannot execute in the host.

Format detection never trusts a file extension or a declared media type on its
own: magic bytes decide the family; the declared type is a hint, and a
disagreement is reported (warning), not silently resolved.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import re
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.capabilities.descriptors import CapabilityStatus
from core.capabilities.foundation.schemas import Caps

MEDIA_PDF = "application/pdf"
MEDIA_DOCX = ("application/vnd.openxmlformats-officedocument."
              "wordprocessingml.document")
MEDIA_XLSX = ("application/vnd.openxmlformats-officedocument."
              "spreadsheetml.sheet")
MEDIA_MD = "text/markdown"
MEDIA_TXT = "text/plain"
MEDIA_CSV = "text/csv"
MEDIA_TSV = "text/tab-separated-values"

TEXT_MEDIA_TYPES = (MEDIA_TXT, MEDIA_MD, MEDIA_CSV, MEDIA_TSV)
SUPPORTED_MEDIA_TYPES = (MEDIA_PDF, MEDIA_DOCX, MEDIA_XLSX) + TEXT_MEDIA_TYPES

# Structural selectors are applied by the host after parsing (any reader);
# the others need the reader's cooperation and are declared per reader.
STRUCTURAL_SELECTORS = ("sections", "tables")


class ReaderError(Exception):
    """A reader outcome that is not a document: carries the capability status
    (unsupported / malformed / limit_exceeded / dependency_unavailable ...)
    and a stable machine ``reason`` code."""

    def __init__(self, status: str, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.status = status
        self.reason = reason
        self.message = message or reason


@dataclass(frozen=True)
class ReadLimits:
    """Hard resource limits for reading. A caller may *tighten* them per
    request (``tightened``); it can never raise them past the adapter's
    configured ceiling."""
    max_bytes: int = 10_000_000
    max_total_bytes: int = 30_000_000
    max_artifacts: int = 8
    max_pages: int = 200
    max_chars: int = 300_000
    max_blocks: int = 20_000
    max_tables: int = 200
    max_rows: int = 2_000
    max_cols: int = 100
    max_sheets: int = 20
    max_zip_entries: int = 2_000
    max_zip_uncompressed_bytes: int = 200_000_000
    max_zip_ratio: int = 100
    timeout_sec: float = 20.0
    memory_mb: int = 1024

    _TIGHTENABLE = ("max_bytes", "max_total_bytes", "max_artifacts",
                    "max_pages", "max_chars", "max_blocks", "max_tables",
                    "max_rows", "max_cols", "max_sheets", "timeout_sec")

    def tightened(self, requested: Any) -> "ReadLimits":
        if not isinstance(requested, dict):
            return self
        changes: Dict[str, Any] = {}
        for key in self._TIGHTENABLE:
            value = requested.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and 0 < value < getattr(self, key):
                changes[key] = type(getattr(self, key))(value)
        return replace(self, **changes) if changes else self

    def caps(self) -> Caps:
        return Caps(max_chars=self.max_chars, max_blocks=self.max_blocks,
                    max_tables=self.max_tables, max_rows=self.max_rows,
                    max_cols=self.max_cols)

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__
                if not k.startswith("_")}


# ── Sniffing ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Detected:
    family: str        # "pdf" | "zip" | "text" | "binary" | "empty"
    media_type: str    # type used for reading ("" if unknown / unsupported)
    declared: str = ""
    mismatch: bool = False


_EXT_TO_TEXT = {".md": MEDIA_MD, ".markdown": MEDIA_MD, ".csv": MEDIA_CSV,
                ".tsv": MEDIA_TSV, ".txt": MEDIA_TXT}
_BINARY_MAGIC = (
    (b"\xd0\xcf\x11\xe0", "application/x-ole-storage"),  # legacy .doc/.xls
    (b"\x89PNG", "image/png"), (b"GIF8", "image/gif"),
    (b"\xff\xd8\xff", "image/jpeg"), (b"\x1f\x8b", "application/gzip"),
    (b"\x7fELF", "application/x-elf"), (b"MZ", "application/x-msdownload"),
)


def detect(data: bytes, declared: str = "", filename: str = "") -> Detected:
    """Decide the format family from content. ``declared`` and the extension
    of ``filename`` are hints only, and only ever used to choose *between text
    variants*; they never turn non-text bytes into a text type."""
    declared_l = (declared or "").split(";")[0].strip().lower()
    if not data:
        return Detected("empty", declared_l or MEDIA_TXT, declared_l)
    head = data[:8]
    if head.startswith(b"%PDF-"):
        return Detected("pdf", MEDIA_PDF, declared_l,
                        bool(declared_l) and declared_l != MEDIA_PDF)
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        # docx vs xlsx (vs some other zip) is decided *inside* the isolated
        # reader from the archive's own structure -- the host never opens it.
        ok = declared_l in (MEDIA_DOCX, MEDIA_XLSX, "application/zip", "")
        return Detected("zip", "application/zip", declared_l, not ok)
    for magic, media in _BINARY_MAGIC:
        if head.startswith(magic):
            return Detected("binary", media, declared_l, False)
    if b"\x00" in data[:8192]:
        return Detected("binary", "application/octet-stream", declared_l, False)
    media = declared_l if declared_l in TEXT_MEDIA_TYPES else ""
    if not media:
        ext = re.search(r"(\.[A-Za-z0-9]+)$", filename or "")
        media = _EXT_TO_TEXT.get(ext.group(1).lower() if ext else "", MEDIA_TXT)
    mismatch = bool(declared_l) and declared_l not in TEXT_MEDIA_TYPES
    return Detected("text", media, declared_l, mismatch)


# ── Reader specs and registry ───────────────────────────────────────────────

_NUM = re.compile(r"\d+")


def _version_tuple(text: str) -> Tuple[int, ...]:
    return tuple(int(n) for n in _NUM.findall(text or "")[:3])


@dataclass(frozen=True)
class Dependency:
    """A third-party dependency of an isolated reader, checked WITHOUT
    importing it (importing would execute library code in the host)."""
    import_name: str
    dist_name: str
    min_version: str = ""   # security floor, see the reader spec that sets it

    def check(self) -> Tuple[bool, str]:
        if importlib.util.find_spec(self.import_name) is None:
            return False, f"{self.dist_name}_not_installed"
        if self.min_version:
            try:
                installed = importlib.metadata.version(self.dist_name)
            except importlib.metadata.PackageNotFoundError:
                return False, f"{self.dist_name}_version_unknown"
            if _version_tuple(installed) < _version_tuple(self.min_version):
                return False, (f"{self.dist_name}_{installed}_below_"
                               f"security_floor_{self.min_version}")
        return True, ""


@dataclass(frozen=True)
class ReaderSpec:
    reader_id: str
    reader_version: str          # version of THIS reader implementation
    families: Tuple[str, ...]    # sniff families served
    media_types: Tuple[str, ...]
    isolation: str               # "inline" | "isolated"
    supported_selection: Tuple[str, ...] = ()
    dependencies: Tuple[Dependency, ...] = ()
    # Distributions whose installed versions are recorded in provenance
    # (reader identity is reader_id@reader_version + these library versions).
    libraries: Tuple[str, ...] = ()

    def availability(self) -> Tuple[bool, str]:
        for dep in self.dependencies:
            ok, why = dep.check()
            if not ok:
                return False, why
        return True, ""

    def library_versions(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for dist in self.libraries:
            try:
                out[dist] = importlib.metadata.version(dist)
            except importlib.metadata.PackageNotFoundError:
                pass
        return out


@dataclass
class ReaderRegistry:
    """Ordered list of readers. First registered reader whose family and media
    type match wins; registering a second implementation for a format is how a
    parser is replaced or supplemented (the adapter falls back in order when a
    reader declines with unsupported / dependency_unavailable)."""
    _specs: List[ReaderSpec] = field(default_factory=list)
    _inline: Dict[str, Callable[[bytes, Dict[str, Any]], Dict[str, Any]]] = \
        field(default_factory=dict)

    def register(self, spec: ReaderSpec,
                 inline_fn: Optional[Callable[[bytes, Dict[str, Any]],
                                              Dict[str, Any]]] = None) -> None:
        if spec.isolation == "inline":
            if inline_fn is None:
                raise ValueError("inline reader requires a function")
            self._inline[spec.reader_id] = inline_fn
        elif spec.isolation != "isolated":
            raise ValueError(f"unknown isolation {spec.isolation!r}")
        self._specs.append(spec)

    def candidates(self, detected: Detected) -> List[ReaderSpec]:
        out = []
        for spec in self._specs:
            if detected.family in spec.families and (
                    detected.family in ("pdf", "zip")
                    or detected.media_type in spec.media_types):
                out.append(spec)
        return out

    def inline_fn(self, reader_id: str):
        return self._inline[reader_id]

    def specs(self) -> List[ReaderSpec]:
        return list(self._specs)
