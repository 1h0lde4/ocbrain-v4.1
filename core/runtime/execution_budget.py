"""Dynamic execution budget, distinct from recovery budgeting."""

import time
from dataclasses import dataclass


@dataclass
class ExecutionBudget:
    startup_deadline_seconds: float = 10.0
    progress_deadline_seconds: float = 45.0
    hard_deadline_seconds: float = 300.0
    max_extension_seconds: float = 180.0
    extension_used_seconds: float = 0.0
    started_at: float = 0.0

    def start(self, now: float | None = None) -> None:
        self.started_at = now if now is not None else time.monotonic()

    @property
    def hard_deadline_at(self) -> float:
        return self.started_at + self.hard_deadline_seconds if self.started_at else 0.0

    def extend(self, seconds: float) -> float:
        remaining = max(0.0, self.max_extension_seconds - self.extension_used_seconds)
        granted = min(max(0.0, seconds), remaining)
        self.extension_used_seconds += granted
        self.hard_deadline_seconds += granted
        return granted

    def expired(self, now: float | None = None) -> bool:
        return bool(self.started_at and (now or time.monotonic()) >= self.hard_deadline_at)
