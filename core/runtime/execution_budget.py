"""
core/runtime/execution_budget.py — ExecutionBudget & ExecutionPolicy (K4.4)

Replaces the hardcoded `timeout=60.0` in core/runtime/limits.py::safe_llm_call
with a governed, dynamic execution-time budget.

Architecture
------------
Extends KERNEL_ARCHITECTURE_v1.0.md §7 (ExecutionContext, CancellationToken)
additively. Deliberately does NOT duplicate or compete with:

  * ADR-K4.2-H-05 `OperationRecoveryBudget` (core/cognitive/recovery.py) --
    that is the sole operation-level *autonomous recovery* budget (how many
    times the Planner/Supervisor may retry across a whole user operation).
    ExecutionBudget governs a single execution *attempt*'s time/progress
    envelope. The two are never substitutable for one another; see the
    Recovery Invariant discussion in execution_watchdog.py.

  * `IterationBudget` (core/runtime/limits.py) -- a flat step-count limiter
    for loop iterations. Orthogonal axis (steps, not time).

  * `CancellationToken` (core/runtime/cancellation.py) -- remains the sole
    enforcement primitive. Nothing in this module cancels anything; see
    execution_watchdog.py for the component that actually calls
    `CancellationToken.cancel()`.

Design
------
  * `ExecutionPolicy` derives an `ExecutionBudget` *before* execution starts,
    from static configuration and (when available) observed historical
    throughput -- following the same "adapt from observed latency, fall back
    to a safe static default" precedent already established by
    `AdaptiveSemaphore` (core/runtime/resilience.py).
  * `ExecutionBudget` is pure runtime accounting for one execution attempt:
    deadlines, elapsed time, bounded extension bookkeeping. It does NOT track
    *progress* -- that's ProgressMonitor's job (progress_monitor.py). Keeping
    these separate avoids two components racing to own "did anything happen
    recently."
  * Fields are additive-only, mirroring ExecutionContext's own convention.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from core.config import config as _config

# ── Safe static defaults (used whenever config / history is unavailable) ────
# These intentionally reproduce today's behavior for un-budgeted callers:
# default_budget() below is functionally identical to the old flat 60s cap.

_DEFAULT_STARTUP_BUDGET_S = 10.0
_DEFAULT_PROGRESS_BUDGET_S = 45.0
_DEFAULT_HARD_CEILING_S = 300.0
_DEFAULT_MAX_EXTENSION_S = 240.0
_DEFAULT_SHORT_REQUEST_CEILING_S = 60.0  # == the old hardcoded value, unchanged
_FALLBACK_TOKENS_PER_SEC = 12.0  # conservative estimate for local CPU-bound Ollama


# ── Historical throughput (process-local; not durable — see impl. report) ───

class _ThroughputHistory:
    """Tiny in-memory exponential moving average of tokens/sec per
    (provider, model). Mirrors AdaptiveSemaphore's philosophy: adapt from
    observed reality, never trust a single pathological sample."""

    def __init__(self, alpha: float = 0.3) -> None:
        self._ema: dict[str, float] = {}
        self._alpha = alpha

    def record(self, key: str, tokens_per_sec: float) -> None:
        if tokens_per_sec <= 0:
            return  # guard: a provider-outage or instant-failure sample must
                     # never pull the average toward zero/nonsense
        prev = self._ema.get(key)
        self._ema[key] = (
            tokens_per_sec if prev is None
            else self._alpha * tokens_per_sec + (1 - self._alpha) * prev
        )

    def get(self, key: str) -> Optional[float]:
        return self._ema.get(key)


_THROUGHPUT_HISTORY = _ThroughputHistory()


def record_observed_throughput(provider: str, model: str, tokens_per_sec: float) -> None:
    """Feed an observed generation rate back into policy history.

    Called by ModelRouter after a monitored streaming generation completes.
    Non-positive samples are silently ignored rather than corrupting the
    running average (guards against provider-outage samples, per spec).
    """
    _THROUGHPUT_HISTORY.record(f"{provider}:{model}", tokens_per_sec)


def _cfg(key: str, default: float) -> float:
    try:
        value = _config.get(f"runtime.{key}", default)
        return float(value)
    except Exception:
        return default


# ── ExecutionBudget ───────────────────────────────────────────────────────

@dataclass
class ExecutionBudget:
    """Runtime accounting for one execution attempt.

    Owns deadlines and bounded-extension bookkeeping only. Progress timing
    (first/last meaningful progress) lives on ProgressMonitor, not here --
    see module docstring.
    """

    startup_deadline_s: float
    progress_deadline_s: float
    hard_ceiling_s: float
    absolute_ceiling_s: float
    max_extension_s: float

    created_at: float = field(default_factory=time.monotonic)
    extension_consumed_s: float = 0.0
    _grace_deadline: Optional[float] = field(default=None, repr=False)

    def elapsed_s(self) -> float:
        return time.monotonic() - self.created_at

    @property
    def remaining_extension_s(self) -> float:
        return max(0.0, self.max_extension_s - self.extension_consumed_s)

    def is_hard_expired(self) -> bool:
        return self.elapsed_s() >= self.hard_ceiling_s

    def grant_extension(self, seconds: float) -> bool:
        """Bounded, one-shot-per-stall-episode extension.

        Pushes `hard_ceiling_s` out (so the operation is genuinely allowed
        to keep running) AND opens a grace window (`in_grace_period`) so
        repeated watchdog polls don't re-detect the *same* stall and
        re-grant on every tick. Invariant enforced here, not trusted to the
        caller: hard_ceiling_s can never exceed absolute_ceiling_s, and
        cumulative extension can never exceed max_extension_s.

        Returns whether any extension was actually granted.
        """
        seconds = min(max(0.0, seconds), self.remaining_extension_s)
        seconds = min(seconds, max(0.0, self.absolute_ceiling_s - self.hard_ceiling_s))
        if seconds <= 0:
            return False
        now = time.monotonic()
        self.hard_ceiling_s += seconds
        self.extension_consumed_s += seconds
        self._grace_deadline = now + seconds
        return True

    def in_grace_period(self) -> bool:
        return self._grace_deadline is not None and time.monotonic() < self._grace_deadline


# ── ExecutionPolicy ──────────────────────────────────────────────────────

class ExecutionPolicy:
    """Derives an ExecutionBudget *before* execution starts.

    Reads config/settings.toml [runtime] for static defaults (falling back
    to the module-level _DEFAULT_* constants when config access fails, e.g.
    in isolated unit tests). Uses observed historical throughput when a
    (provider, model) pair has any.
    """

    @classmethod
    def default_budget(cls) -> ExecutionBudget:
        """Budget for callers that don't specify anything.

        Functionally identical to the old flat 60s cap -- existing
        safe_llm_call callers see no behavior change unless they opt into
        a budget explicitly. This is the §20/§27 compatibility guarantee.
        """
        ceiling = _cfg("default_short_request_ceiling_s", _DEFAULT_SHORT_REQUEST_CEILING_S)
        return ExecutionBudget(
            startup_deadline_s=ceiling,
            progress_deadline_s=ceiling,
            hard_ceiling_s=ceiling,
            absolute_ceiling_s=ceiling,
            max_extension_s=0.0,  # no extension on the un-budgeted/default path
        )

    @classmethod
    def for_generation(
        cls,
        *,
        provider: str = "unknown",
        model: str = "unknown",
        estimated_output_tokens: Optional[int] = None,
        long_form: bool = False,
    ) -> ExecutionBudget:
        """Derive a budget for an LLM generation request.

        long_form=False (ordinary chat turns, "Hi"): identical shape to
        default_budget() -- fast, bounded, no extension. This is the
        regression guard for short requests.

        long_form=True: sized from estimated output tokens and observed
        throughput when available, else a conservative safe fallback --
        `estimated_execution_cost = estimated_generation_time + safety_margin`,
        deterministic when no history exists.
        """
        if not long_form:
            return cls.default_budget()

        absolute_ceiling = _cfg("default_hard_ceiling_s", _DEFAULT_HARD_CEILING_S)
        max_extension = _cfg("max_budget_extension_s", _DEFAULT_MAX_EXTENSION_S)
        progress_deadline = _cfg("default_progress_budget_s", _DEFAULT_PROGRESS_BUDGET_S)
        startup_deadline = _cfg("default_startup_budget_s", _DEFAULT_STARTUP_BUDGET_S)

        if estimated_output_tokens and estimated_output_tokens > 0:
            tps = _THROUGHPUT_HISTORY.get(f"{provider}:{model}") or _FALLBACK_TOKENS_PER_SEC
            tps = max(tps, 0.1)  # guard against a near-zero sample causing an absurd estimate
            estimated_generation_s = estimated_output_tokens / tps
            safety_margin_s = max(15.0, estimated_generation_s * 0.5)
            initial_ceiling = estimated_generation_s + safety_margin_s
        else:
            # No size signal available: start conservative, rely on the
            # extension mechanism (bounded by max_extension) rather than a
            # generous guess.
            initial_ceiling = absolute_ceiling * 0.4

        initial_ceiling = max(startup_deadline, min(initial_ceiling, absolute_ceiling))

        return ExecutionBudget(
            startup_deadline_s=startup_deadline,
            progress_deadline_s=progress_deadline,
            hard_ceiling_s=initial_ceiling,
            absolute_ceiling_s=absolute_ceiling,
            max_extension_s=max_extension,
        )
