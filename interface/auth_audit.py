"""
interface/auth_audit.py -- durable sink for the authentication boundary's audit records (DEBT-025).

Records (see interface/auth.py):
* ``api.auth_disabled`` / ``api.auth_enabled``: one record per transition of the opt-out, in both directions.
* ``api.auth_denied``: one *aggregate* record per time window (total, per-reason breakdown, how many
  were logged and how many suppressed), never one record per denied request.

What is never persisted: bearer tokens, ``Authorization`` headers or any other credential, request
paths, client addresses.  Payloads are built from fixed fields only.

Failure semantics (the owner's rules): an audit-storage failure never makes authentication fail open.
A pending ``api.auth_disabled`` record keeps the effective mode at "required", so disabling
authentication cannot silently succeed while its record is lost; a failure to persist a denial
aggregate or an ``api.auth_enabled`` record changes nothing about who is let in.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol

SOURCE = "ApiAuth"
SCHEMA_VERSION = 1

AUDIT_TIMEOUT_S = 2.0          # one append may take at most this long
AUDIT_RETRY_BACKOFF_S = 5.0    # after a failure, do not try again for this long (no per-request latency)
MAX_PENDING_AGGREGATES = 100   # bound on unsent denial aggregates; overflow is counted, not hidden


class AuthAuditSink(Protocol):
    async def append(self, event_type: str, payload: Mapping[str, Any]) -> None:
        """Persist one record or raise.  Must not swallow errors."""


class EventStreamSink:
    """Appends to the project's EventStream (SQLite, WAL).  A database error propagates to the caller."""

    async def append(self, event_type: str, payload: Mapping[str, Any]) -> None:
        from core.events.event_stream import get_event_stream  # lazy: clients importing interface.auth stay light
        await get_event_stream().append(event_type, source=SOURCE, payload=dict(payload))


_sink: Optional[AuthAuditSink] = None


def get_sink() -> AuthAuditSink:
    return _sink if _sink is not None else EventStreamSink()


def set_sink(sink: Optional[AuthAuditSink]) -> None:
    """Install a sink (tests, alternative stores); None restores the EventStream default."""
    global _sink
    _sink = sink
