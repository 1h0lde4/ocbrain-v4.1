"""
core/runtime/progress_monitor.py — ProgressMonitor (K4.4)

Generic, execution-source-agnostic progress tracking. Deliberately not
LLM-specific: the same monitor works for a streaming LLM generation today,
and — per the architecture-reconciliation brief's "future workers and
capabilities" requirement — for a Worker's step-by-step progress or a
Capability's phase transitions later, without redesign. Only the *source*
that calls report_progress() changes; this class never assumes tokens.

Distinguishes "activity" (something arrived) from "meaningful progress"
(the execution materially advanced) so a pathological provider sending
empty/whitespace-only keepalive chunks cannot indefinitely postpone stall
detection just by looking "active." See the LLM adapter note on
report_progress() for the concrete heuristic used for streaming text.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProgressState(str, Enum):
    """Qualitative progress state. Per spec: qualitative progress is the
    primary signal; quantitative (token counts) is optional/best-effort."""

    PENDING = "pending"
    ACTIVE = "active"
    PROGRESSING = "progressing"
    WAITING = "waiting"
    STALLED = "stalled"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressSnapshot:
    """Read-only snapshot of monitor state at one instant. Safe to pass to
    a watchdog, or (future UI phase) a user-safe projection layer, without
    exposing the monitor's mutable internals."""

    state: ProgressState
    activity_count: int
    progress_count: int
    first_progress_at: Optional[float]
    last_progress_at: Optional[float]
    output_size: int
    throughput_per_sec: Optional[float]


class ProgressMonitor:
    """Tracks activity/progress for one execution attempt.

    Generic usage:
        monitor = ProgressMonitor()
        monitor.start()
        monitor.report_activity()                 # something arrived
        monitor.report_progress(units=len(chunk))  # it was meaningful
        monitor.complete()  /  monitor.fail()  /  monitor.cancel()

    LLM streaming adapter (see ModelRouter integration): a chunk counts as
    meaningful progress iff it has non-whitespace content — a simple,
    tokenizer-free heuristic (no exact tokenizer exists in this repo) that
    still defeats whitespace-only keepalive traffic. Empty/whitespace
    chunks should call report_activity() only.
    """

    def __init__(self) -> None:
        self._state = ProgressState.PENDING
        self._activity_count = 0
        self._progress_count = 0
        self._output_size = 0
        self._first_progress_at: Optional[float] = None
        self._last_progress_at: Optional[float] = None

    def start(self) -> None:
        self._state = ProgressState.ACTIVE

    def report_activity(self) -> None:
        """Something arrived (a chunk, a callback). Logged for diagnostics
        but does NOT by itself reset stall detection — see report_progress."""
        self._activity_count += 1

    def report_progress(self, units: int = 1) -> None:
        """Meaningful progress occurred — resets the stall clock.

        Args:
            units: approximate size of this increment (e.g. characters in a
                streamed chunk, or 1 for a completed subtask step).
                Best-effort; never treated as an exact token count.
        """
        now = time.monotonic()
        self._progress_count += 1
        self._output_size += max(0, units)
        if self._first_progress_at is None:
            self._first_progress_at = now
        self._last_progress_at = now
        if self._state in (ProgressState.ACTIVE, ProgressState.PENDING, ProgressState.WAITING):
            self._state = ProgressState.PROGRESSING

    def mark_waiting(self) -> None:
        self._state = ProgressState.WAITING

    def mark_stalled(self) -> None:
        self._state = ProgressState.STALLED

    def mark_recovering(self) -> None:
        self._state = ProgressState.RECOVERING

    def complete(self) -> None:
        self._state = ProgressState.COMPLETED

    def fail(self) -> None:
        self._state = ProgressState.FAILED

    def cancel(self) -> None:
        self._state = ProgressState.CANCELLED

    @property
    def state(self) -> ProgressState:
        return self._state

    def has_progressed(self) -> bool:
        """Whether at least one meaningful-progress event has ever been
        recorded. Distinguishes "never started" (startup-deadline concern)
        from "started, then went quiet" (stall concern) — these are
        different failure modes with different watchdog handling."""
        return self._last_progress_at is not None

    def since_last_progress_s(self) -> float:
        """Seconds since the last meaningful progress event.

        Only meaningful once has_progressed() is True — callers must check
        that first (the watchdog does).
        """
        if self._last_progress_at is None:
            return 0.0
        return time.monotonic() - self._last_progress_at

    def throughput_per_sec(self) -> Optional[float]:
        """Best-effort units/sec since first meaningful progress. None
        until at least one progress event has been recorded."""
        if self._first_progress_at is None or self._last_progress_at is None:
            return None
        elapsed = self._last_progress_at - self._first_progress_at
        if elapsed <= 0:
            return None
        return self._output_size / elapsed

    def snapshot(self) -> ProgressSnapshot:
        return ProgressSnapshot(
            state=self._state,
            activity_count=self._activity_count,
            progress_count=self._progress_count,
            first_progress_at=self._first_progress_at,
            last_progress_at=self._last_progress_at,
            output_size=self._output_size,
            throughput_per_sec=self.throughput_per_sec(),
        )
