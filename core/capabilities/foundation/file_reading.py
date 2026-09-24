"""
core/capabilities/foundation/file_reading.py — FILE_READING implementation A.

Semantic reading of an *already-authorized artifact*. Not filesystem access:

    ACCESS      obtain the permitted artifact      -> NOT this adapter. The
                (FILE_ACCESS, declared, unregistered; Workspace §G.5/§I)
    READING     parse / inspect / extract          -> this adapter
    REASONING   interpret the content              -> STRUCTURED_REASONING
    GENERATION  create / transform output          -> TEXT_GENERATION

Input boundary (fail-closed):
  * artifacts arrive as {artifact_id, content(bytes|str), ...}. There is no
    ``path`` / ``uri`` / ``url`` input: such keys are refused, and an
    artifact_id that is path-shaped is refused too. The adapter never opens a
    filesystem path and never fetches a URL.
  * content-less artifacts are only resolvable through an injected
    ArtifactResolver -- the seam to the future ACCESS layer, which is where
    Principal/project authorization (Workspace P0) will live. With no resolver
    configured they are ``unreadable`` (no_resolver_configured).

Everything extracted is data with zero instruction authority; the result says
so (trust block) and carries no verification claim.

Repeatable and side-effect free: the adapter keeps no cache and no mutable
state. Any future cache is keyed by ``read_key`` (content hash + reader
identity + selection + limits), which is recorded in provenance.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from core.capabilities.capability import (
    BaseAdapter, CapabilityRequest, CapabilityResult, CapabilityType,
)
from core.capabilities.descriptors import (
    CapabilityStatus as S, FALLTHROUGH_STATUSES, SUCCESS_STATUSES,
)
from core.capabilities.foundation.readers.base import (
    Detected, ReadLimits, ReaderError, ReaderRegistry, ReaderSpec,
    STRUCTURAL_SELECTORS, detect,
)
from core.capabilities.foundation.readers.defaults import default_reader_registry
from core.capabilities.foundation.readers.isolation import (
    IsolatedRunner, IsolationLimits, SubprocessRunner,
)
from core.capabilities.foundation.schemas import (
    ArtifactIdentity, Document, ReadOutcome, ReadWarning, SELECTION_KEYS,
    apply_structural_selection, clip, document_set_dict, outline_of, sha256_hex,
    valid_artifact_id,
)

ADAPTER_VERSION = "1.0.0"
_FORBIDDEN_KEYS = ("path", "file_path", "filepath", "filename_path", "uri",
                   "url", "file", "location")
# Warnings that mean "read, but with reduced fidelity".
_DEGRADING = frozenset({"encoding_fallback_cp1252", "pages_without_text",
                        "declared_media_type_mismatch"})


class ArtifactAccessError(Exception):
    """Raised by an ArtifactResolver when access is not granted / not found."""

    def __init__(self, reason: str = "access_denied") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ResolvedArtifact:
    artifact_id: str
    content: bytes
    revision: str = ""
    media_type: str = ""
    display_name: str = ""


class ArtifactResolver(Protocol):
    """Seam to the future ACCESS layer (FILE_ACCESS / Workspace). Implementations
    own authorization; this adapter trusts nothing about a bare reference."""

    async def resolve(self, ref: Dict[str, Any], *,
                      trace_id: str) -> ResolvedArtifact: ...


def _outcome(ident: ArtifactIdentity, status: str, reason: str = "",
             error: str = "", document: Optional[Document] = None,
             provenance: Optional[Dict[str, Any]] = None) -> ReadOutcome:
    return ReadOutcome(ident, status, reason, error or reason, document,
                       provenance or {})


class FileReadingAdapter(BaseAdapter):
    adapter_name = "file-reading-readers"
    capability_type = CapabilityType.FILE_READING
    adapter_version = ADAPTER_VERSION
    implements_contract = "1"
    supported_operations = ("read_document", "extract_structure")

    def __init__(self, *, readers: Optional[ReaderRegistry] = None,
                 runner: Optional[IsolatedRunner] = None,
                 limits: Optional[ReadLimits] = None,
                 resolver: Optional[ArtifactResolver] = None) -> None:
        super().__init__()
        self._readers = readers or default_reader_registry()
        self._runner = runner or SubprocessRunner()
        self._limits = limits or ReadLimits()
        self._resolver = resolver

    # ── Adapter.execute ─────────────────────────────────────────────────────

    async def execute(self, request: CapabilityRequest,
                      resources: Any) -> CapabilityResult:
        op = request.operation or "read_document"
        payload = request.payload
        limits = self._limits.tightened(payload.get("limits"))

        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, (list, tuple)) or not artifacts:
            return CapabilityResult.of(
                S.INVALID_REQUEST, error="artifacts must be a non-empty list")
        if len(artifacts) > limits.max_artifacts:
            return CapabilityResult.of(
                S.LIMIT_EXCEEDED,
                error=f"{len(artifacts)} artifacts exceed max_artifacts="
                      f"{limits.max_artifacts}")
        selection = payload.get("selection") or {}
        if not isinstance(selection, dict):
            return CapabilityResult.of(S.INVALID_REQUEST,
                                       error="selection must be an object")
        unknown = [k for k in selection if k not in SELECTION_KEYS]
        if unknown:
            return CapabilityResult.of(
                S.INVALID_REQUEST, error=f"unknown selector(s): {unknown}")

        outcomes: List[ReadOutcome] = []
        spent = 0
        for raw in artifacts:
            outcome, size = await self._read_one(
                raw, op, selection, limits, request.trace_id,
                budget_left=limits.max_total_bytes - spent)
            spent += size
            outcomes.append(outcome)

        status = self._aggregate([o.status for o in outcomes])
        output = document_set_dict(status, outcomes, op)
        error = ""
        if status not in SUCCESS_STATUSES:
            first = next((o for o in outcomes if o.status not in SUCCESS_STATUSES),
                         outcomes[0])
            error = f"{first.status}: {first.reason or first.error}"
        return CapabilityResult.of(
            status, output=output, error=error,
            provenance={
                "inputs": [o.identity.to_dict() for o in outcomes],
                "outcomes": [{"artifact_id": o.identity.artifact_id,
                              "status": o.status, "reason": o.reason,
                              "reader": o.provenance.get("reader"),
                              "read_key": o.provenance.get("read_key")}
                             for o in outcomes],
                "verification": "not_performed",
            })

    @staticmethod
    def _aggregate(statuses: List[str]) -> str:
        ok = [s for s in statuses if s in SUCCESS_STATUSES]
        bad = [s for s in statuses if s not in SUCCESS_STATUSES]
        if ok and bad:
            return S.PARTIAL
        if ok:
            if S.PARTIAL in ok:
                return S.PARTIAL
            if S.DEGRADED in ok:
                return S.DEGRADED
            if all(s == S.EMPTY for s in ok):
                return S.EMPTY
            return S.OK
        if len(set(bad)) == 1:
            return bad[0]
        if S.FAILED in bad:
            return S.FAILED
        return bad[0]

    # ── one artifact ────────────────────────────────────────────────────────

    async def _read_one(self, raw: Any, op: str, selection: Dict[str, Any],
                        limits: ReadLimits, trace_id: str, *,
                        budget_left: int) -> Tuple[ReadOutcome, int]:
        started = time.monotonic()
        blank = ArtifactIdentity(artifact_id="")
        if not isinstance(raw, dict):
            return _outcome(blank, S.INVALID_REQUEST, "artifact_not_an_object"), 0
        bad_keys = [k for k in _FORBIDDEN_KEYS if k in raw]
        artifact_id = raw.get("artifact_id")
        ident0 = ArtifactIdentity(
            artifact_id=clip(artifact_id, 128) if isinstance(artifact_id, str) else "",
            revision=clip(raw.get("revision"), 64),
            display_name=clip(raw.get("filename"), 200))
        if bad_keys:
            return _outcome(ident0, S.INVALID_REQUEST, "paths_not_accepted",
                            f"artifact refused: {bad_keys} not accepted; "
                            f"supply content and an opaque artifact_id"), 0
        if not valid_artifact_id(artifact_id):
            return _outcome(ident0, S.INVALID_REQUEST, "invalid_artifact_id",
                            "artifact_id must be an opaque id "
                            "(path-shaped ids are refused)"), 0

        # obtain bytes: inline content, or via the injected resolver only
        content = raw.get("content")
        media_hint = clip(raw.get("media_type"), 100)
        try:
            if content is None:
                if self._resolver is None:
                    return _outcome(ident0, S.UNREADABLE, "no_resolver_configured",
                                    "no content supplied and no ArtifactResolver "
                                    "is configured"), 0
                resolved = await self._resolver.resolve(dict(raw), trace_id=trace_id)
                content = resolved.content
                media_hint = media_hint or resolved.media_type
                ident0 = ArtifactIdentity(
                    artifact_id=ident0.artifact_id,
                    revision=resolved.revision or ident0.revision,
                    display_name=resolved.display_name or ident0.display_name)
        except ArtifactAccessError as e:
            return _outcome(ident0, S.UNREADABLE, e.reason,
                            f"artifact access refused: {e.reason}"), 0
        if isinstance(content, str):
            content = content.encode("utf-8")
        elif isinstance(content, (bytearray, memoryview)):
            content = bytes(content)
        if not isinstance(content, bytes):
            return _outcome(ident0, S.INVALID_REQUEST, "content_must_be_bytes_or_text"), 0

        size = len(content)
        digest = sha256_hex(content)
        ident = ArtifactIdentity(ident0.artifact_id, ident0.revision, digest,
                                 "", size, ident0.display_name)
        expected = raw.get("sha256")
        if isinstance(expected, str) and expected and expected.lower() != digest:
            return _outcome(ident, S.INVALID_REQUEST, "content_hash_mismatch",
                            "supplied bytes do not match the expected sha256 "
                            "(stale or wrong revision)"), size
        if size > limits.max_bytes or size > budget_left:
            return _outcome(ident, S.LIMIT_EXCEEDED, "artifact_too_large",
                            f"{size} bytes exceeds the read limit"), size

        detected = detect(content, media_hint, ident.display_name)
        ident = ArtifactIdentity(ident.artifact_id, ident.revision, digest,
                                 detected.media_type, size, ident.display_name)
        if detected.family == "empty":
            doc = Document(ident, "none", "0")
            return _outcome(ident, S.EMPTY, "zero_length_artifact", document=doc,
                            provenance=self._prov(None, detected, "-", digest,
                                                  op, selection, limits, started)), size

        candidates = self._readers.candidates(detected)
        if not candidates:
            return _outcome(ident, S.UNSUPPORTED,
                            f"unsupported_media_type:{detected.media_type}",
                            provenance={"detected": detected.media_type}), size

        declines: List[ReadOutcome] = []
        for spec in candidates:
            outcome = await self._try_reader(spec, detected, content, ident, op,
                                             selection, limits, started, digest)
            if outcome.status in FALLTHROUGH_STATUSES:
                declines.append(outcome)
                continue
            return outcome, size
        return declines[0], size

    async def _try_reader(self, spec: ReaderSpec, detected: Detected,
                          content: bytes, ident: ArtifactIdentity, op: str,
                          selection: Dict[str, Any], limits: ReadLimits,
                          started: float, digest: str) -> ReadOutcome:
        prov = self._prov(spec, detected, spec.reader_version, digest, op,
                          selection, limits, started)
        reader_keys = [k for k in selection if k not in STRUCTURAL_SELECTORS]
        unsupported = [k for k in reader_keys if k not in spec.supported_selection]
        if unsupported:
            return _outcome(ident, S.UNSUPPORTED,
                            f"selection_unsupported:{unsupported[0]}",
                            provenance=prov)
        ok, why = spec.availability()
        if not ok:
            return _outcome(ident, S.DEPENDENCY_UNAVAILABLE, why, provenance=prov)

        opts = {"limits": limits.to_dict(),
                "selection": {k: selection[k] for k in reader_keys},
                "media_type": detected.media_type,
                "filename": ident.display_name}
        try:
            body = await self._run_reader(spec, content, opts, limits)
        except ReaderError as e:
            return _outcome(ident, e.status, e.reason, e.message, provenance=prov)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a bug in a reader must not crash the runtime
            return _outcome(ident, S.FAILED, "reader_internal_error",
                            type(e).__name__, provenance=prov)

        try:
            doc = Document.from_untrusted(
                body, ident, spec.reader_id, spec.reader_version, limits.caps())
        except (ValueError, TypeError, KeyError):
            return _outcome(ident, S.MALFORMED, "bad_reader_output", provenance=prov)
        doc.selection = {}
        if detected.mismatch:
            doc.warnings.append(ReadWarning(
                "declared_media_type_mismatch",
                f"declared {detected.declared!r}, content is {detected.media_type}"))
        unmatched: List[str] = []
        if any(k in selection for k in STRUCTURAL_SELECTORS):
            doc, unmatched = apply_structural_selection(doc, selection)
        for u in unmatched:
            doc.warnings.append(ReadWarning("selection_not_found", u))
        pages_missing = [w for w in doc.warnings if w.code == "selection_not_found"
                         and w.locator.startswith(("page=", "sheet="))]
        if op == "extract_structure":
            doc = outline_of(doc)
        prov["stats"] = {"blocks": len(doc.blocks), "tables": len(doc.tables)}

        requested = any(selection.get(k) for k in SELECTION_KEYS)
        empty = not doc.blocks and not doc.tables
        codes = {w.code for w in doc.warnings}
        failed = int(body.get("failed_pages") or 0) if isinstance(body, dict) else 0
        if empty:
            status = S.EMPTY
        elif doc.truncated or failed or unmatched or pages_missing:
            status = S.PARTIAL
        elif codes & _DEGRADING:
            status = S.DEGRADED
        else:
            status = S.OK
        reason = {S.EMPTY: "no_content_matched" if requested else "no_content",
                  S.PARTIAL: doc.truncation_reason or "selection_partially_matched"
                  if (doc.truncated or unmatched or pages_missing) else "page_errors"}.get(status, "")
        return _outcome(ident, status, reason, document=doc, provenance=prov)

    async def _run_reader(self, spec: ReaderSpec, content: bytes,
                          opts: Dict[str, Any], limits: ReadLimits) -> Dict[str, Any]:
        if spec.isolation == "inline":
            fn = self._readers.inline_fn(spec.reader_id)
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(fn, content, opts), limits.timeout_sec)
            except asyncio.TimeoutError as e:
                raise ReaderError(S.LIMIT_EXCEEDED, "parse_timeout") from e
        result = await self._runner.run(
            spec.reader_id, json.dumps(opts), content,
            IsolationLimits(timeout_sec=limits.timeout_sec))
        # Resource exhaustion attributable to the INPUT is a request-level
        # outcome (limit_exceeded), never a health-affecting adapter failure:
        # otherwise one hostile file could put the capability into cooldown
        # for everyone.
        if result.termination == "spawn_failed":
            raise ReaderError(S.DEPENDENCY_UNAVAILABLE,
                              "isolation_runtime_unavailable")
        if result.termination == "timeout":
            raise ReaderError(S.LIMIT_EXCEEDED, "parse_timeout")
        if result.termination == "output_limit":
            raise ReaderError(S.LIMIT_EXCEEDED, "reader_output_limit")
        if result.termination == "crashed" or result.exit_code not in (0, None):
            code = result.exit_code
            if code in (-9, -24):  # SIGKILL (e.g. address-space) / SIGXCPU
                raise ReaderError(S.LIMIT_EXCEEDED, "resource_limit")
            raise ReaderError(S.MALFORMED, f"parser_crashed:{code}")
        try:
            msg = json.loads(result.stdout.decode("ascii"))
        except (ValueError, UnicodeDecodeError) as e:
            raise ReaderError(S.MALFORMED, "bad_reader_output") from e
        if isinstance(msg, dict) and isinstance(msg.get("error"), dict):
            err = msg["error"]
            status = err.get("status") if err.get("status") in (
                S.UNSUPPORTED, S.MALFORMED, S.LIMIT_EXCEEDED, S.INVALID_REQUEST,
                S.DEPENDENCY_UNAVAILABLE) else S.MALFORMED
            raise ReaderError(status, clip(err.get("reason"), 96),
                              clip(err.get("message"), 240))
        if not isinstance(msg, dict) or not isinstance(msg.get("ok"), dict):
            raise ReaderError(S.MALFORMED, "bad_reader_output")
        return msg["ok"]

    def _prov(self, spec: Optional[ReaderSpec], detected: Detected, version: str,
              digest: str, op: str, selection: Dict[str, Any],
              limits: ReadLimits, started: float) -> Dict[str, Any]:
        rid = spec.reader_id if spec else "none"
        key_src = json.dumps([digest, f"{rid}@{version}", op, selection,
                              limits.to_dict()], sort_keys=True, default=str)
        return {
            "reader": {"id": rid, "version": version,
                       "isolation": spec.isolation if spec else "",
                       "libraries": spec.library_versions() if spec else {}},
            "detected_media_type": detected.media_type,
            "declared_media_type": detected.declared,
            "read_key": hashlib.sha256(key_src.encode()).hexdigest(),
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
