"""
core/capabilities/foundation/schemas.py — typed hand-off structures.

What crosses a capability boundary, as plain JSON-serializable dicts with a
``schema`` id (``"<name>/<major>"``). A consumer checks the schema id before it
trusts the shape; only the major participates (descriptors.TypeSpec.accepts).

Design rules (ADR-CAP-02):

  * JSON-safe by construction -- no bytes, no objects. Node results are
    checkpointed (core/workflow/runtime.py _worker_result_to_dict) and events
    are persisted; artifact *content* never appears in a result, only extracted
    text and identity.
  * Identity is never a filename or path. An artifact is identified by
    (artifact_id, revision, content_sha256); ``display_name`` is for humans.
  * Every extracted item carries where it came from (SourceRef); the shape
    (source_type / source_id / producer / locator) mirrors the evidence
    source shape of the unmerged Verification branch so a future Verification
    consumer can ingest it without this package importing or implementing
    Verification.
  * Extracted content is *data with zero instruction authority*: every
    document-derived structure carries ``trust`` and every model-derived
    structure carries ``verification: "not_performed"`` -- an explicit
    statement that no verification happened, so absence of a flag is never
    read as "verified".
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_ARTIFACT_INPUT = "ocbrain.artifact_input/1"
SCHEMA_DOCUMENT_SET = "ocbrain.document_set/1"
SCHEMA_ANALYSIS = "ocbrain.analysis/1"
SCHEMA_TEXT = "ocbrain.text/1"

# Boundary statements, machine-readable (Workspace §F.1: extracted content has
# high *data* trust at best and zero *instruction* authority).
TRUST_UNTRUSTED: Dict[str, str] = {
    "data_trust": "untrusted",
    "instruction_authority": "none",
}
# Model-derived structures: still no instruction authority, and explicitly not
# verified -- generated text/analysis is a claim, never evidence for itself.
TRUST_GENERATED: Dict[str, str] = {
    "data_trust": "unverified_model_output",
    "instruction_authority": "none",
}
VERIFICATION_NOT_PERFORMED = "not_performed"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}$")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def schema_major(schema_id: str) -> Optional[int]:
    _, _, major = (schema_id or "").rpartition("/")
    return int(major) if major.isdigit() else None


def schema_compatible(found: Any, expected: str) -> bool:
    """Same schema name and major (minor changes are additive by rule)."""
    if not isinstance(found, str) or "/" not in found:
        return False
    return found.rpartition("/")[0] == expected.rpartition("/")[0] \
        and schema_major(found) == schema_major(expected)


def clip(text: Any, limit: int) -> str:
    text = "" if text is None else (text if isinstance(text, str) else str(text))
    return text if len(text) <= limit else text[:limit]


def valid_artifact_id(value: Any) -> bool:
    """Opaque ids only. Anything path-shaped ('/', '\\', '..', drive letters,
    URLs) is refused: FILE_READING never resolves paths, so a path must not be
    smuggled in as an identity either."""
    return isinstance(value, str) and bool(_ID_RE.match(value)) \
        and ".." not in value


# ── Identity and provenance ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ArtifactIdentity:
    artifact_id: str
    revision: str = ""
    content_sha256: str = ""
    media_type: str = ""
    size_bytes: int = 0
    display_name: str = ""  # human label only -- never identity

    @property
    def identity_key(self) -> str:
        rev = self.revision or "-"
        return f"{self.artifact_id}@{rev}#{self.content_sha256[:16]}"

    def to_dict(self) -> Dict[str, Any]:
        return {"artifact_id": self.artifact_id, "revision": self.revision,
                "content_sha256": self.content_sha256,
                "media_type": self.media_type, "size_bytes": self.size_bytes,
                "display_name": self.display_name,
                "identity_key": self.identity_key}


@dataclass(frozen=True)
class SourceRef:
    """Where a piece of extracted content (or a cited claim) came from."""
    artifact_id: str
    revision: str
    content_sha256: str
    locator: str      # e.g. "page=3;para=2", "sheet=Sales;range=A1:C9", "lines=10-42"
    producer: str     # "<reader_id>@<version>"

    def to_dict(self) -> Dict[str, str]:
        return {"artifact_id": self.artifact_id, "revision": self.revision,
                "content_sha256": self.content_sha256,
                "locator": self.locator, "producer": self.producer}

    def to_evidence_source(self) -> Dict[str, str]:
        """Evidence-source-shaped projection (source_type/source_id/producer/
        locator). Plain data; produces no verdict."""
        return {"source_type": "artifact",
                "source_id": f"{self.artifact_id}@{self.revision or '-'}"
                             f"#{self.content_sha256[:16]}",
                "producer": self.producer, "locator": self.locator}


# ── Structured document representation ──────────────────────────────────────

@dataclass
class ReadWarning:
    code: str
    message: str = ""
    locator: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message,
                "locator": self.locator}


@dataclass
class Block:
    block_id: str
    kind: str                # heading | paragraph | list_item | code | table
    text: str = ""
    page: Optional[int] = None
    locator: str = ""
    table_id: str = ""       # set when kind == "table"
    level: int = 0           # heading level (1..9); 0 for non-headings

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"block_id": self.block_id, "kind": self.kind,
                             "text": self.text, "locator": self.locator}
        if self.page is not None:
            d["page"] = self.page
        if self.table_id:
            d["table_id"] = self.table_id
        if self.level:
            d["level"] = self.level
        return d


@dataclass
class Table:
    table_id: str
    rows: List[List[str]]
    header_rows: int = 0
    caption: str = ""
    page: Optional[int] = None
    sheet: str = ""
    cell_range: str = ""
    locator: str = ""
    row_count: int = 0
    col_count: int = 0
    truncated: bool = False

    def to_dict(self, *, include_rows: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "table_id": self.table_id, "header_rows": self.header_rows,
            "caption": self.caption, "sheet": self.sheet,
            "range": self.cell_range, "locator": self.locator,
            "row_count": self.row_count, "col_count": self.col_count,
            "truncated": self.truncated,
        }
        if self.page is not None:
            d["page"] = self.page
        if include_rows:
            d["rows"] = self.rows
        return d


@dataclass
class Section:
    section_id: str
    heading: str
    level: int
    block_start: int   # index into Document.blocks (inclusive)
    block_end: int     # exclusive: next heading of level <= this one, or end
    locator: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"section_id": self.section_id, "heading": self.heading,
                "level": self.level, "block_start": self.block_start,
                "block_end": self.block_end, "locator": self.locator}


@dataclass
class Caps:
    """Hard structural caps applied to *any* reader output, including output
    that came back from an isolated subprocess (which is untrusted too)."""
    max_chars: int = 300_000
    max_blocks: int = 20_000
    max_tables: int = 200
    max_rows: int = 2_000
    max_cols: int = 100
    max_cell_chars: int = 2_000
    max_meta_chars: int = 200


def _s(value: Any, limit: int) -> str:
    return clip(value, limit)


def _opt_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


@dataclass
class Document:
    identity: ArtifactIdentity
    reader_id: str
    reader_version: str
    title: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    page_count: Optional[int] = None
    blocks: List[Block] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    warnings: List[ReadWarning] = field(default_factory=list)
    truncated: bool = False
    truncation_reason: str = ""
    outline_only: bool = False
    selection: Dict[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return (sum(len(b.text) for b in self.blocks if b.kind != "table")
                + sum(len(c) for t in self.tables for r in t.rows for c in r))

    def source_ref(self, locator: str) -> SourceRef:
        return SourceRef(self.identity.artifact_id, self.identity.revision,
                         self.identity.content_sha256, locator,
                         f"{self.reader_id}@{self.reader_version}")

    def subset(self, keep_blocks: Sequence[int],
               keep_sections: Optional[Sequence[Section]] = None) -> "Document":
        """A new Document containing only the blocks at ``keep_blocks`` (old
        indices, kept in order) and the tables they reference. Section ids are
        preserved (so a consumer can select "s3" and see "s3" back); their
        block ranges are remapped onto the smaller block list. Pure."""
        keep = sorted(set(keep_blocks))
        new_index = {old: n for n, old in enumerate(keep)}
        out = Document(identity=self.identity, reader_id=self.reader_id,
                       reader_version=self.reader_version, title=self.title,
                       metadata=dict(self.metadata), page_count=self.page_count,
                       warnings=list(self.warnings), truncated=self.truncated,
                       truncation_reason=self.truncation_reason,
                       outline_only=self.outline_only,
                       selection=dict(self.selection))
        out.blocks = [self.blocks[i] for i in keep]
        used = {b.table_id for b in out.blocks if b.kind == "table" and b.table_id}
        out.tables = [t for t in self.tables if t.table_id in used]
        for sec in (self.sections if keep_sections is None else keep_sections):
            if sec.block_start not in new_index:
                continue
            after = [n for old, n in new_index.items() if old >= sec.block_end]
            out.sections.append(Section(
                section_id=sec.section_id, heading=sec.heading, level=sec.level,
                block_start=new_index[sec.block_start],
                block_end=min(after) if after else len(out.blocks),
                locator=sec.locator))
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "reader": {"id": self.reader_id, "version": self.reader_version},
            "title": self.title,
            # Metadata is attacker-controlled text like any other content.
            "metadata": dict(self.metadata),
            "page_count": self.page_count,
            "outline_only": self.outline_only,
            "sections": [s.to_dict() for s in self.sections],
            "blocks": [b.to_dict() for b in self.blocks],
            "tables": [t.to_dict(include_rows=not self.outline_only)
                       for t in self.tables],
            "warnings": [w.to_dict() for w in self.warnings],
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "selection": dict(self.selection),
            "stats": {"blocks": len(self.blocks), "tables": len(self.tables),
                      "sections": len(self.sections), "chars": self.char_count},
        }

    @classmethod
    def from_untrusted(cls, body: Any, identity: ArtifactIdentity,
                       reader_id: str, reader_version: str,
                       caps: Caps) -> "Document":
        """Build a Document from reader output that may have crossed a process
        boundary. Strict coercion + caps; identity always comes from the host
        (a reader cannot claim a different artifact identity)."""
        if not isinstance(body, dict):
            raise ValueError("reader output is not an object")
        doc = cls(identity=identity, reader_id=reader_id,
                  reader_version=reader_version,
                  title=_s(body.get("title"), caps.max_cell_chars),
                  page_count=_opt_int(body.get("page_count")))
        meta = body.get("metadata")
        if isinstance(meta, dict):
            for k, v in list(meta.items())[:16]:
                if isinstance(k, str) and isinstance(v, str):
                    doc.metadata[_s(k, 64)] = _s(v, caps.max_meta_chars)

        chars = 0
        raw_blocks = body.get("blocks")
        for raw in (raw_blocks if isinstance(raw_blocks, list) else []):
            if not isinstance(raw, dict):
                continue
            if len(doc.blocks) >= caps.max_blocks:
                doc.truncated, doc.truncation_reason = True, "max_blocks"
                break
            text = _s(raw.get("text"), caps.max_chars)
            if chars + len(text) > caps.max_chars:
                text = text[: max(0, caps.max_chars - chars)]
                doc.truncated, doc.truncation_reason = True, "max_chars"
            chars += len(text)
            kind = raw.get("kind") if raw.get("kind") in (
                "heading", "paragraph", "list_item", "code", "table") else "paragraph"
            doc.blocks.append(Block(
                block_id=f"b{len(doc.blocks) + 1}", kind=kind, text=text,
                page=_opt_int(raw.get("page")), locator=_s(raw.get("locator"), 128),
                table_id=_s(raw.get("table_ref"), 16) if kind == "table" else "",
                level=(min(max(_opt_int(raw.get("level")) or 1, 1), 9)
                       if kind == "heading" else 0)))
            if doc.truncated:
                break

        raw_tables = body.get("tables")
        for raw in (raw_tables if isinstance(raw_tables, list) else []):
            if not isinstance(raw, dict):
                continue
            if len(doc.tables) >= caps.max_tables:
                doc.truncated = True
                doc.truncation_reason = doc.truncation_reason or "max_tables"
                break
            rows: List[List[str]] = []
            truncated = bool(raw.get("truncated"))
            for r in (raw.get("rows") if isinstance(raw.get("rows"), list) else []):
                if not isinstance(r, list):
                    continue
                if len(rows) >= caps.max_rows:
                    truncated = True
                    break
                row = [_s(c, caps.max_cell_chars) for c in r[: caps.max_cols]]
                if len(r) > caps.max_cols:
                    truncated = True
                chars += sum(len(c) for c in row)
                rows.append(row)
            if chars > caps.max_chars * 2:  # tables get bounded headroom
                doc.truncated = True
                doc.truncation_reason = doc.truncation_reason or "max_chars"
                break
            doc.tables.append(Table(
                table_id=f"t{len(doc.tables) + 1}", rows=rows,
                header_rows=min(_opt_int(raw.get("header_rows")) or 0, len(rows)),
                caption=_s(raw.get("caption"), caps.max_cell_chars),
                page=_opt_int(raw.get("page")), sheet=_s(raw.get("sheet"), 128),
                cell_range=_s(raw.get("range"), 32),
                locator=_s(raw.get("locator"), 128),
                row_count=_opt_int(raw.get("row_count")) or len(rows),
                col_count=_opt_int(raw.get("col_count"))
                or max((len(r) for r in rows), default=0),
                truncated=truncated))
            if truncated:
                doc.truncated = True
                doc.truncation_reason = doc.truncation_reason or "table_limits"

        # Table blocks reference tables by 1-based position in the reader's
        # own table list; remap to the ids assigned above.
        for b in doc.blocks:
            if b.kind == "table":
                n = b.table_id.lstrip("t")
                b.table_id = f"t{n}" if n.isdigit() and int(n) <= len(doc.tables) else ""

        # Sections are derived by the host from heading blocks (a reader cannot
        # invent a structure that disagrees with its own blocks).
        heads = [(i, b) for i, b in enumerate(doc.blocks) if b.kind == "heading"]
        for n, (i, b) in enumerate(heads, 1):
            doc.sections.append(Section(
                section_id=f"s{n}", heading=b.text, level=b.level or 1,
                block_start=i, block_end=len(doc.blocks), locator=b.locator))
        for n, sec in enumerate(doc.sections):
            for later in doc.sections[n + 1:]:
                if later.level <= sec.level:
                    sec.block_end = later.block_start
                    break

        raw_warn = body.get("warnings")
        for w in (raw_warn if isinstance(raw_warn, list) else [])[:100]:
            if isinstance(w, dict) and isinstance(w.get("code"), str):
                doc.warnings.append(ReadWarning(
                    _s(w["code"], 64), _s(w.get("message"), 240),
                    _s(w.get("locator"), 128)))
        return doc


@dataclass
class ReadOutcome:
    """The reading result for ONE artifact inside a document set."""
    identity: ArtifactIdentity
    status: str
    reason: str = ""
    error: str = ""
    document: Optional[Document] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"artifact": self.identity.to_dict(), "status": self.status,
                "reason": self.reason, "error": self.error,
                "document": self.document.to_dict() if self.document else None,
                "provenance": dict(self.provenance)}


def document_set_dict(status: str, outcomes: Sequence[ReadOutcome],
                      operation: str) -> Dict[str, Any]:
    return {
        "schema": SCHEMA_DOCUMENT_SET,
        "operation": operation,
        "status": status,
        "documents": [o.to_dict() for o in outcomes],
        "trust": dict(TRUST_UNTRUSTED),
    }


# ── Selection (progressive reading) ─────────────────────────────────────────

SELECTION_KEYS = ("pages", "sections", "tables", "lines", "sheets")


def apply_structural_selection(doc: Document, selection: Dict[str, Any]
                               ) -> Tuple[Document, List[str]]:
    """Post-parse selection by ``sections`` (ids or heading text) and
    ``tables`` (ids). ``pages`` / ``lines`` / ``sheets`` are applied by the
    readers that understand them (a page or a line is not a structural id).
    Returns (document, unmatched selectors). Pure: builds a new Document."""
    want_sections = [str(x) for x in selection.get("sections") or []]
    want_tables = [str(x) for x in selection.get("tables") or []]
    if not want_sections and not want_tables:
        return doc, []

    unmatched: List[str] = []
    keep: set = set()
    chosen: List[Section] = []
    for w in want_sections:
        found = [s for s in doc.sections if s.section_id == w
                 or s.heading.strip().lower() == w.strip().lower()]
        if not found:
            unmatched.append(f"section:{w}")
        for sec in found:
            if sec not in chosen:
                chosen.append(sec)
            keep.update(range(sec.block_start, sec.block_end))
    for w in want_tables:
        hit = [i for i, b in enumerate(doc.blocks)
               if b.kind == "table" and b.table_id == w]
        if not hit:
            unmatched.append(f"table:{w}")
        keep.update(hit)

    out = doc.subset(sorted(keep))  # sections whose heading survives (incl. nested)
    out.selection = {"requested": {k: selection[k] for k in ("sections", "tables")
                                   if selection.get(k)},
                     "unmatched": list(unmatched)}
    return out, unmatched


def outline_of(doc: Document) -> Document:
    """Outline view for progressive reading: headings and table placeholders
    only (bodies dropped). Section ids are stable across outline -> read."""
    keep = [i for i, b in enumerate(doc.blocks)
            if b.kind in ("heading", "table")]
    out = doc.subset(keep)
    out.outline_only = True
    return out
