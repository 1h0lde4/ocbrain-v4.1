"""
core/capabilities/foundation/handoff.py — consuming typed hand-offs safely.

TEXT_GENERATION and STRUCTURED_REASONING both consume "source material": plain
text, a FILE_READING document set, or another capability's analysis. This module
turns that material into *labelled data blocks* for a prompt, and records which
labels exist so that a model's citations can be checked against what it was
actually shown (a citation to a block the model never saw resolves to nothing).

Boundary rules enforced here (ADR-CAP-02):
  * Source material is DATA. It is rendered inside delimited blocks and never
    concatenated into the instruction channel.
  * Structured hand-offs are schema-checked before they are trusted: an
    incompatible schema major is an invalid_request, not a best-effort parse.
  * The input status travels: partial / degraded / empty inputs are reported to
    the caller instead of being laundered into a clean-looking result.
  * A hand-off that claims to be a *failure* is rejected -- failed results are
    not source material.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.capabilities.descriptors import CapabilityStatus as S, SUCCESS_STATUSES
from core.capabilities.foundation.schemas import (
    SCHEMA_ANALYSIS, SCHEMA_DOCUMENT_SET, SCHEMA_TEXT, clip, schema_compatible,
)


@dataclass(frozen=True)
class DataBlock:
    label: str    # S1 / A1 / T1
    kind: str     # document_set | analysis | text
    body: str


@dataclass
class SourceBundle:
    blocks: List[DataBlock] = field(default_factory=list)
    # citation tag -> resolved reference (only tags that were actually rendered)
    catalog: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    input_statuses: List[str] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    substantive: bool = False   # any real content at all
    problems: List[Tuple[str, str]] = field(default_factory=list)  # (status, reason)

    @property
    def degraded_inputs(self) -> bool:
        return any(s in (S.PARTIAL, S.DEGRADED) for s in self.input_statuses)

    def input_status(self) -> Dict[str, Any]:
        return {"statuses": list(self.input_statuses),
                "degraded": self.degraded_inputs,
                "truncated_to_budget": self.truncated}


class _Budget:
    def __init__(self, chars: int) -> None:
        self.left = max(chars, 0)
        self.hit = False

    def take(self, text: str) -> str:
        if len(text) <= self.left:
            self.left -= len(text)
            return text
        self.hit = True
        cut = text[: self.left]
        self.left = 0
        return cut + " [truncated]"


def _flatten(items: Any) -> List[Any]:
    if items is None:
        return []
    if isinstance(items, (list, tuple)):
        return list(items)
    return [items]


def build_bundle(sources: Any, *, max_chars: int) -> SourceBundle:
    """Normalize ``sources`` (str | handoff dict | list of those) into labelled
    data blocks under a character budget."""
    bundle = SourceBundle()
    budget = _Budget(max_chars)
    counters = {"S": 0, "A": 0, "T": 0}

    for item in _flatten(sources):
        if isinstance(item, str):
            if not item.strip():
                continue
            counters["T"] += 1
            label = f"T{counters['T']}"
            body = budget.take(item)
            bundle.blocks.append(DataBlock(label, "text", body))
            bundle.catalog[label] = {"kind": "text", "label": label}
            bundle.substantive = True
        elif isinstance(item, dict):
            schema = item.get("schema")
            if schema_compatible(schema, SCHEMA_DOCUMENT_SET):
                _add_documents(bundle, item, budget, counters)
            elif schema_compatible(schema, SCHEMA_ANALYSIS):
                _add_analysis(bundle, item, budget, counters)
            elif schema_compatible(schema, SCHEMA_TEXT):
                status = item.get("status", S.OK)
                if status not in SUCCESS_STATUSES:
                    bundle.problems.append((S.INVALID_REQUEST, "failed_result_not_source"))
                    continue
                bundle.input_statuses.append(status)
                text = clip(item.get("text"), max_chars)
                if text.strip():
                    counters["T"] += 1
                    label = f"T{counters['T']}"
                    bundle.blocks.append(DataBlock(label, "text", budget.take(text)))
                    bundle.catalog[label] = {"kind": "text", "label": label}
                    bundle.substantive = True
            else:
                bundle.problems.append(
                    (S.INVALID_REQUEST, f"incompatible_schema:{clip(schema, 64)}"))
        else:
            bundle.problems.append((S.INVALID_REQUEST, "source_must_be_text_or_object"))
    bundle.truncated = budget.hit
    return bundle


def _add_documents(bundle: SourceBundle, item: Dict[str, Any],
                   budget: _Budget, counters: Dict[str, int]) -> None:
    status = item.get("status", S.OK)
    if status not in SUCCESS_STATUSES:
        bundle.problems.append((S.INVALID_REQUEST, "failed_result_not_source"))
        return
    bundle.input_statuses.append(status)
    for outcome in item.get("documents") or []:
        if not isinstance(outcome, dict):
            continue
        ostatus = outcome.get("status")
        bundle.input_statuses.append(ostatus if isinstance(ostatus, str) else S.FAILED)
        doc = outcome.get("document")
        art = outcome.get("artifact") or {}
        if ostatus not in SUCCESS_STATUSES or not isinstance(doc, dict):
            continue
        bundle.artifacts.append(art)
        counters["S"] += 1
        n = counters["S"]
        reader = doc.get("reader") or {}
        lines = [f"[S{n}] artifact={clip(art.get('artifact_id'), 64)} "
                 f"revision={clip(art.get('revision'), 32) or '-'} "
                 f"sha256={clip(art.get('content_sha256'), 12)} "
                 f"reader={clip(reader.get('id'), 24)}@{clip(reader.get('version'), 16)} "
                 f"status={ostatus}"]
        producer = f"{reader.get('id', '')}@{reader.get('version', '')}"
        tables = {t.get("table_id"): t for t in doc.get("tables") or []
                  if isinstance(t, dict)}
        for b in doc.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            if budget.left <= 0:
                budget.hit = True
                break
            tag = f"S{n}:{b.get('block_id')}"
            if b.get("kind") == "table":
                t = tables.get(b.get("table_id"))
                if not t:
                    continue
                head = (f"[S{n}:{t.get('table_id')}] TABLE sheet={clip(t.get('sheet'), 40) or '-'} "
                        f"range={clip(t.get('range'), 24) or '-'} "
                        f"rows={t.get('row_count')} cols={t.get('col_count')}")
                rows = [" | ".join(str(c) for c in r) for r in (t.get("rows") or [])]
                text = head + ("\n" + "\n".join(rows) if rows else "")
                tag = f"S{n}:{t.get('table_id')}"
                locator = t.get("locator", "")
            else:
                kind = b.get("kind")
                prefix = f"[{tag}]" + (f" ({kind}" + (f" L{b['level']}" if b.get("level") else "") + ")"
                                       if kind in ("heading", "list_item", "code") else "")
                text = f"{prefix} {b.get('text', '')}"
                locator = b.get("locator", "")
            lines.append(budget.take(text))
            bundle.catalog[tag] = {
                "kind": "document", "artifact_id": art.get("artifact_id", ""),
                "revision": art.get("revision", ""),
                "content_sha256": art.get("content_sha256", ""),
                "locator": locator, "producer": producer}
            if b.get("kind") != "table" and str(b.get("text", "")).strip():
                bundle.substantive = True
            if b.get("kind") == "table":
                bundle.substantive = bundle.substantive or bool(tables.get(b.get("table_id"), {}).get("rows"))
        bundle.blocks.append(DataBlock(f"S{n}", "document_set", "\n".join(lines)))


def _add_analysis(bundle: SourceBundle, item: Dict[str, Any],
                  budget: _Budget, counters: Dict[str, int]) -> None:
    status = item.get("status", S.OK)
    if status not in SUCCESS_STATUSES:
        bundle.problems.append((S.INVALID_REQUEST, "failed_result_not_source"))
        return
    bundle.input_statuses.append(status)
    counters["A"] += 1
    n = counters["A"]
    lines = [f"[A{n}] prior analysis (status={status}; unverified model output)"]
    for f in item.get("findings") or []:
        if not isinstance(f, dict):
            continue
        tag = f"A{n}:{f.get('finding_id')}"
        lines.append(budget.take(
            f"[{tag}] ({f.get('kind')}, {f.get('support')}) {clip(f.get('statement'), 1000)}"))
        bundle.catalog[tag] = {"kind": "analysis", "finding_id": f.get("finding_id", ""),
                               "sources": f.get("sources") or []}
        bundle.substantive = True
        # Lineage: the artifacts this analysis was derived from stay visible
        # to whatever consumes it (a consumer's provenance lists them), so
        # traceability does not stop at the first capability boundary.
        for src in f.get("sources") or []:
            if isinstance(src, dict) and src.get("artifact_id"):
                ident = {"artifact_id": src["artifact_id"],
                         "revision": src.get("revision", ""),
                         "content_sha256": src.get("content_sha256", "")}
                if ident not in bundle.artifacts:
                    bundle.artifacts.append(ident)
    for label, key in (("conclusion", "conclusions"), ("uncertainty", "uncertainties")):
        for i, txt in enumerate(item.get(key) or [], 1):
            lines.append(budget.take(f"[A{n}:{label[0]}{i}] {label}: {clip(txt, 600)}"))
            bundle.substantive = True
    bundle.blocks.append(DataBlock(f"A{n}", "analysis", "\n".join(lines)))
