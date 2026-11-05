"""
core/memory/sqlite_runtime.py — SQLite runtime compatibility gate (Rev 3 Amendment 1)

OCBrain's persistent memory database runs in WAL mode with multiple
connections (connection-per-operation, thread executor) and optionally
multiple processes. SQLite has documented a WAL-reset bug that can cause
database corruption under a specific sequence involving concurrent
connections, writes and checkpoints.

Affected upstream versions: 3.7.0 through 3.51.2.
Fix included in: 3.51.3+.
Documented backports: 3.44.6, 3.50.7.

This module implements the Rev 3 Amendment 1 compatibility gate:

  * The accepted-*version* policy is intentionally authoritative here and
    is evaluated independently of FTS5 feature probes: a working FTS5
    feature probe does NOT establish WAL safety (Amendment 1 §B).
  * A Python version does not determine the SQLite version (Amendment 1 §B)
    — every decision is made from the actual runtime report below.
  * An explicitly verified vendor build may be accepted ONLY on exact,
    complete provenance records (distribution + evidence + verification
    date). Anything less is rejected (fail closed, Amendment 1 §D).
  * When the runtime is affected and no verified patched build is admitted,
    the caller MUST NOT report the multi-connection WAL deployment as fully
    supported and MUST NOT claim overall implementation acceptance
    (Amendment 1 §D). Callers get a structured finding + remediation plan.

The gate is a *compatibility and operational-reporting* gate. It does not
attempt to reproduce the WAL-reset race through ordinary concurrency tests
(Amendment 1 §E) — the acceptance mechanism is version/build compatibility
plus operational verification, not defeat/concurrency spelunking.
"""

from __future__ import annotations

import logging
import os
import platform
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger("ocbrain.memory.sqlite_runtime")

# ── Amendment 1 §A — documented version facts ────────────────────────────────

# First version of the fix release line.
WAL_FIX_FIRST_VERSION: Tuple[int, int, int] = (3, 51, 3)
# Documented backport releases that contain the same fix.
WAL_FIX_BACKPORT_VERSIONS: Tuple[Tuple[int, int, int], ...] = ((3, 44, 6), (3, 50, 7))
# First version in the affected range (WAL mode introduction).
WAL_AFFECTED_FIRST_VERSION: Tuple[int, int, int] = (3, 7, 0)

# Operational connection-management model of the memory backends. Reported in
# every runtime inventory (Amendment 1 §C) so the finding documents what the
# gate is actually gating, not just a version number.
CONNECTION_MODEL = (
    "connection-per-operation: SQLiteStorageBackend / SQLiteArchiveBackend / "
    "GraphEngine open and close one sqlite3 connection per call (thread "
    "executor); multiple connections per process; WAL mode enables "
    "concurrent readers with a single writer across processes."
)


def parse_sqlite_version(text: str) -> Tuple[int, int, int]:
    """Parse '3.50.4' / '3.51.3' / '3.45.1' into (3, 50, 4) — raises on junk."""
    parts = [p for p in text.strip().split(".") if p != ""]
    if len(parts) < 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"unparseable SQLite version: {text!r}")
    while len(parts) < 3:
        parts.append("0")
    return tuple(int(p) for p in parts[:3])  # type: ignore[return-value]


@dataclass
class VendorBuildProvenance:
    """
    An explicitly verified vendor build record (Amendment 1 §B/§C).

    Every field is mandatory: a record that merely names a version without
    distribution, evidence and a verification date is NOT provenance and must
    fail closed. `evidence_url` should point at the vendor's release notes or
    the committed provenance document that says this build contains the
    upstream WAL-reset fix.
    """
    source_id: str
    distribution: str
    evidence_url: str
    verified_on: str

    def validate(self) -> List[str]:
        """Return a list of validation errors (empty = valid)."""
        errors = []
        for name in ("source_id", "distribution", "evidence_url", "verified_on"):
            value = getattr(self, name)
            if not str(value).strip():
                errors.append(f"{name}: required non-empty provenance field missing")
        return errors

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "distribution": self.distribution,
            "evidence_url": self.evidence_url,
            "verified_on": self.verified_on,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "VendorBuildProvenance":
        return cls(
            source_id=str(raw.get("source_id", "")),
            distribution=str(raw.get("distribution", "")),
            evidence_url=str(raw.get("evidence_url", "")),
            verified_on=str(raw.get("verified_on", "")),
        )


def _normalize_source_id(value: Any) -> str:
    """sqlite_source_id() strings are matched exactly after whitespace trim."""
    return str(value).strip()


@dataclass
class RuntimeDecision:
    """
    The compatibility verdict for the process's SQLite runtime.

    Attributes:
        decision: one of
            "approved"                  — released fix version (always safe).
            "approved_backport"         — documented backport release.
            "approved_vendor_build"     — verified vendor build (provenance).
            "rejected_affected"         — in the affected range, unpatched.
            "rejected_pre_program"      — predates the WAL program entirely.
            "rejected_unproven_build"   — vendor claim without full provenance
                                          (fail closed, Amendment 1 §D).
        wal_safe: True only for the three approved decisions. Fail-closed.
        affected_by_wal_reset_bug: True for versions inside the affected range.
        full_wal_support: True only when the multi-connection WAL deployment
            may be described as fully supported (Amendment 1 §D).
        reason: human-readable justification (must appear in findings/logs).
        remediation: concrete plan text when NOT approved.
        vendor_evidence: the matched provenance record, if any.
        inventory: the runtime inventory this decision was made from.
    """
    decision: str
    wal_safe: bool
    affected_by_wal_reset_bug: bool
    full_wal_support: bool
    reason: str
    remediation: str
    vendor_evidence: Optional[Dict[str, Any]] = None
    inventory: Dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        return (f"{self.decision}: wal_safe={self.wal_safe} "
                f"affected={self.affected_by_wal_reset_bug}")


# ── Runtime inventory (Amendment 1 §C) ───────────────────────────────────────

def collect_runtime_inventory() -> Dict[str, Any]:
    """
    The static, per-process runtime inventory required by Amendment 1 §C.

    Journal mode / autocheckpoint are connection-level facts and are collected
    by `collect_connection_inventory()` from an actual connection. This
    function must never assume the SQLite version from the Python version —
    both are reported separately (Amendment 1 §B).
    """
    provenance: List[str] = []
    try:
        build_mod = getattr(sqlite3, "_sqlite3", None)
        if build_mod is not None and getattr(build_mod, "__file__", None):
            provenance.append(f"sqlite3 C module: {build_mod.__file__}")
        if build_mod is not None:
            apiver = getattr(build_mod, "module_version", None)
            if apiver:
                provenance.append(f"sqlite3 module version: {apiver}")
    except Exception as exc:  # pragma: no cover - provenance is best-effort
        provenance.append(f"provenance lookup error: {exc}")

    try:
        conn = sqlite3.connect(":memory:")
        try:
            sql_version, source_id = conn.execute(
                "SELECT sqlite_version(), sqlite_source_id()"
            ).fetchone()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - defensive
        sql_version, source_id = "unknown", f"query error: {exc}"
        provenance.append(f"sqlite_version() query error: {exc}")

    return {
        "python_version": sys.version.replace("\n", " "),
        "sqlite3_sqlite_version": sqlite3.sqlite_version,
        "sqlite_version_sql": sql_version,
        "sqlite_source_id": source_id,
        "os": platform.platform(),
        "machine": platform.machine(),
        "build_provenance": provenance,
        "connection_model": CONNECTION_MODEL,
        "automatic_checkpoint_config": (
            "SQLite default wal_autocheckpoint=1000 pages per connection; "
            "the memory backends do not override it. See "
            "collect_connection_inventory() for a live connection."
        ),
    }


def collect_connection_inventory(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Connection-scoped inventory pieces (Amendment 1 §C) for an open conn."""
    out: Dict[str, Any] = {}
    for pragma, key in (
        ("journal_mode", "journal_mode"),
        ("wal_autocheckpoint", "wal_autocheckpoint"),
        ("secure_delete", "core_secure_delete"),
        ("page_size", "page_size"),
        ("page_count", "page_count"),
    ):
        try:
            out[key] = conn.execute(f"PRAGMA {pragma}").fetchone()[0]
        except sqlite3.Error as exc:
            out[key] = f"error: {exc}"
    return out


# ── The decision function (Amendment 1 §B/§C) ───────────────────────────────

def classify_wal_safety(
    inventory: Optional[Dict[str, Any]] = None,
    *,
    approved_vendor_builds: Optional[Iterable[VendorBuildProvenance]] = None,
) -> RuntimeDecision:
    """
    Decide whether the current process's SQLite runtime is WAL-safe.

    The policy (Amendment 1 §B):

      1. Released fix line (>= 3.51.3)               -> approved.
      2. Documented backports (3.44.6, 3.50.7)       -> approved_backport.
      3. Any build inside the affected range that exactly matches a
         *verified* vendor provenance record          -> approved_vendor_build
         (only when the record is complete — see VendorBuildProvenance).
      4. Any other build inside the affected range    -> rejected_affected.
         A successful FTS5 feature probe, passing ordinary tests or a
         particular Python version can never be used as approval.
      5. Builds outside/before the affected range that predate the WAL
         program                                      -> rejected_pre_program.
      6. A vendor claim that fails provenance validation fails closed as
         rejected_unproven_build (Amendment 1 §D).
    """
    inv = inventory if inventory is not None else collect_runtime_inventory()
    version_raw = inv.get("sqlite_version_sql") or inv.get("sqlite3_sqlite_version")
    source_id_raw = inv.get("sqlite_source_id", "")
    try:
        version = parse_sqlite_version(str(version_raw))
    except ValueError as exc:
        return RuntimeDecision(
            decision="rejected_affected",
            wal_safe=False,
            affected_by_wal_reset_bug=True,
            full_wal_support=False,
            reason=f"SQLite runtime version could not be parsed: {exc}",
            remediation=(
                "Install a SQLite build from the SQLite project whose "
                f">={_v(WAL_FIX_FIRST_VERSION)} release line or one of the documented "
                f"backports {_vmap(WAL_FIX_BACKPORT_VERSIONS)} is verifiable, then re-run."
            ),
            inventory=inv,
        )
    source_id = _normalize_source_id(source_id_raw)

    if version >= WAL_FIX_FIRST_VERSION:
        return RuntimeDecision(
            decision="approved",
            wal_safe=True,
            affected_by_wal_reset_bug=False,
            full_wal_support=True,
            reason=(
                f"SQLite {version_raw} includes the upstream WAL-reset fix "
                f"(fix line starts at {_v(WAL_FIX_FIRST_VERSION)})."
            ),
            remediation="",
            inventory=inv,
        )

    if version in WAL_FIX_BACKPORT_VERSIONS:
        return RuntimeDecision(
            decision="approved_backport",
            wal_safe=True,
            affected_by_wal_reset_bug=False,
            full_wal_support=True,
            reason=(
                f"SQLite {version_raw} is a documented backport release "
                f"containing the WAL-reset fix ({_vmap(WAL_FIX_BACKPORT_VERSIONS)})."
            ),
            remediation="",
            inventory=inv,
        )

    # Vendor-build path: only an explicitly verified, fully documented build
    # record can admit an affected version (Amendment 1 §B/§C). A record that
    # names this build but fails provenance validation fails closed as
    # rejected_unproven_build — an incomplete claim never accepts.
    matching_record = None
    complete_record = None
    for prov in (approved_vendor_builds or []):
        if _normalize_source_id(prov.source_id) == source_id:
            if matching_record is None:
                matching_record = prov
            if complete_record is None and not prov.validate():
                complete_record = prov
    if matching_record is not None and complete_record is None:
        invalid_fields = ", ".join(matching_record.validate()) or "unknown"
        return RuntimeDecision(
            decision="rejected_unproven_build",
            wal_safe=False,
            affected_by_wal_reset_bug=True,
            full_wal_support=False,
            reason=(
                f"SQLite {version_raw} matches a vendor-build record whose "
                f"provenance is incomplete ({invalid_fields}) — fail closed, "
                "documented provenance is required (Amendment 1 §B/§D)."
            ),
            remediation=(
                "Complete the provenance record (distribution, evidence, "
                "verified_on) before accepting this build, or use a released "
                "fix-line/backport version."
            ),
            inventory=inv,
        )
    if complete_record is not None:
        plain = f"{complete_record.source_id} matches the running build"
        # This branch is only reachable for builds that are neither the
        # fix line nor a documented backport — i.e. inside the affected
        # range — accepted here solely on verified provenance.
        return RuntimeDecision(
            decision="approved_vendor_build",
            wal_safe=True,
            affected_by_wal_reset_bug=True,
            full_wal_support=True,
            reason=(
                f"SQLite {version_raw} is accepted on verified vendor-build "
                f"provenance ({plain}); distribution={complete_record.distribution}, "
                f"evidence={complete_record.evidence_url}, "
                f"verified_on={complete_record.verified_on}."
            ),
            remediation="",
            vendor_evidence=complete_record.as_dict(),
            inventory=inv,
        )
    # An affected version whose source_id does NOT match any approved
    # record continues below -> rejected_affected.

    in_affected_range = WAL_AFFECTED_FIRST_VERSION <= version
    if in_affected_range:
        return RuntimeDecision(
            decision="rejected_affected",
            wal_safe=False,
            affected_by_wal_reset_bug=True,
            full_wal_support=False,
            reason=(
                f"SQLite {version_raw} is inside the affected range "
                f"({_v(WAL_AFFECTED_FIRST_VERSION)} .. {_v(WAL_FIX_FIRST_VERSION)}) and is "
                "not a documented backport; no verified vendor-build provenance "
                "matched this exact source_id."
            ),
            remediation=(
                "Upgrade to SQLite >= 3.51.3 (pull a newer Python/sdk build) or "
                f"install documented backports ({_vmap(WAL_FIX_BACKPORT_VERSIONS)}), "
                "or run a vendor build whose provenance record is registered "
                "with this deployment (source_id, distribution, evidence, "
                "verified_on) — see REV3 report Remediation Plan R1. The "
                "memory service must not report full readiness in the meantime."
            ),
            inventory=inv,
        )
    return RuntimeDecision(
        decision="rejected_pre_program",
        wal_safe=False,
        affected_by_wal_reset_bug=False,
        full_wal_support=False,
        reason=(
            f"SQLite {version_raw} predates the WAL compatibility program "
            f"(WAL support starts at {_v(WAL_AFFECTED_FIRST_VERSION)})."
        ),
        remediation="Upgrade SQLite before using WAL multi-connection memory storage.",
        inventory=inv,
    )


def _v(t: Tuple[int, int, int]) -> str:
    return ".".join(str(x) for x in t)


def _vmap(versions: Sequence[Tuple[int, int, int]]) -> str:
    return ", ".join(_v(t) for t in versions)


# ── Gate plumbing for the backend and CLI ───────────────────────────────────

GATE_ENV_VAR = "OCBRAIN_MEMORY_RUNTIME_ACK"

GATE_ENFORCE = "enforce"
GATE_ACKNOWLEDGE = "acknowledge"


def load_configured_vendor_provenance() -> List[VendorBuildProvenance]:
    """
    Amendment 1 §C: a deployment may register verified vendor-build
    provenance records in config/settings.toml:

        [memory]
        wal_gate_mode = "enforce"          # or "acknowledge" (explicit exception)

        [[memory.wal_gate.approved_vendor_builds]]
        source_id     = "…"
        distribution  = "…"
        evidence_url  = "…"
        verified_on   = "…"

    Nothing is fabricated here: with no entries in settings.toml the list is
    EMPTY and every affected build fails closed. Each element is returned as
    a VendorBuildProvenance even when incomplete — classification itself
    validates every record and rejects an incomplete one as
    rejected_unproven_build (fail closed, Amendment 1 §D).
    """
    records: List[VendorBuildProvenance] = []
    try:
        from core.config import config as app_config
        raw = app_config.get("memory.wal_gate.approved_vendor_builds")
    except Exception:
        return records
    if isinstance(raw, dict):
        raw = [raw]
    for item in raw or []:
        if isinstance(item, dict):
            records.append(VendorBuildProvenance.from_dict(item))
    return records


def resolve_gate_mode(requested: Optional[str] = None) -> str:
    """
    Resolve the gate mode for a memory-backend construction.

    Default is `enforce` (fail closed). The explicit acknowledgement value
    `acknowledge` exists so that (a) the test suite can run on an affected
    runtime while every readiness report honestly says so and (b) an
    operator can deliberately run an unsupported runtime that they have
    accepted in writing. Acknowledgement never changes the verdict — it only
    downgrades enforcement; all reporting stays explicit (Amendment 1 §D/§E).
    """
    if requested is None:
        requested = os.environ.get(GATE_ENV_VAR)
    if requested in (None, "", "enforce"):
        return GATE_ENFORCE
    if requested == GATE_ACKNOWLEDGE:
        return GATE_ACKNOWLEDGE
    raise ValueError(
        f"{GATE_ENV_VAR} must be set to 'acknowledge' or unset; got {requested!r}"
    )


class MemoryRuntimeCompatibilityError(RuntimeError):
    """Raised when construction proceeds under `enforce` and the runtime
    SQLite build is not WAL-safe. Carries the complete finding."""

    def __init__(self, verdict: RuntimeDecision):
        self.verdict = verdict
        finding = {
            "kind": "sqlite_wal_runtime_compatibility",
            "decision": verdict.decision,
            "wal_safe": verdict.wal_safe,
            "full_wal_support": verdict.full_wal_support,
            "reason": verdict.reason,
            "inventory": verdict.inventory,
        }
        super().__init__(
            "SQLite WAL runtime compatibility gate: memory backend refuses "
            "readiness. " + verdict.reason
        )
        self.finding = finding
        self.remediation = verdict.remediation
