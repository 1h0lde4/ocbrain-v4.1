"""
core/cognitive/recovery.py — K4.2-H1 Unified Operation Recovery Budget.

Architecture:
    docs/architecture/K4_2_CONTRACT_EVOLUTION_AND_DIAGNOSTIC_ARCHITECTURE_SPECIFICATION.md
    §12 (Impasse & Recovery Architecture) and
    docs/architecture/implementation_plan - K42 v1-0 FINAL PRE-FREEZE
    ARCHITECTURE SPECIFICATION frozen.md §4/§6/§10 (D5 — Unified Recovery
    Budget; ADR-K4.2-H-05).

Scope (D5, frozen):
    v1.0 autonomous recovery is exactly two actions, both bounded by the
    SAME OperationRecoveryBudget instance:
        1. Planner re-planning (Orchestrator re-invokes plan() on impasse).
        2. Supervisor worker retry (Supervisor retries a failed worker
           invocation via ExecutionRuntime).
    Autonomous re-compilation is explicitly NOT a v1.0 recovery action
    (compilation rejection is surfaced by Supervisor, never retried --
    K4 §16 invariant 9, unchanged).

Ownership (Recovery Invariant, frozen):
    "Every user operation has one authoritative autonomous recovery
    budget. No component may create an independent recovery budget
    outside this contract. Planner and Supervisor consume the same
    budget instance. Neither may create a hidden retry universe."

    core/orchestrator.py is the sole creator (one budget per handle()
    K4.2-branch invocation) and threads the same instance into both the
    Planner re-plan loop it drives directly and into
    context.parameters["recovery_budget"] for SupervisorWorker. Planner
    itself never receives or consumes the budget -- plan() returns a
    PlannerResult; Orchestrator alone decides whether to re-invoke it
    (see core/orchestrator.py's K4.2 branch).

This module defines the data contract only -- no recovery *policy*
(when to retry, how many attempts) beyond the bound itself, and no
wiring to Orchestrator/Supervisor (those live in their own modules).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OperationRecoveryBudget:
    """One recovery budget per user operation (scoped by trace_id).

    The default of 3 is a configuration default
    (config/settings.toml [runtime] max_recovery_attempts), not an
    architectural constant -- callers may construct this with any
    max_total_recovery_attempts value.
    """
    max_total_recovery_attempts: int = 3
    internal_recovery_used: int = 0

    @property
    def remaining(self) -> int:
        """Attempts still available. Never negative even if
        internal_recovery_used somehow exceeds the max (defensive)."""
        return max(0, self.max_total_recovery_attempts - self.internal_recovery_used)

    @property
    def exhausted(self) -> bool:
        return self.internal_recovery_used >= self.max_total_recovery_attempts

    def consume(self) -> bool:
        """Attempts to consume one recovery action.

        Returns:
            True if this recovery attempt is permitted (and has been
                counted against the budget). False if the budget is
                already exhausted -- the caller must treat this as a
                terminal outcome, not retry through some other path.
        """
        if self.exhausted:
            return False
        self.internal_recovery_used += 1
        return True
