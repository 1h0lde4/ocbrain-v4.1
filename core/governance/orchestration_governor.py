"""
core/governance/orchestration_governor.py — OrchestrationGovernor (K2.4)

Enforces orchestration-level execution authorization: which worker types
are currently authorized to execute in this deployment.

Architecture references:
  - PI LAW 1: "No autonomous capability may bypass governance."
  - PI §6.1: Required Governors — OrchestrationGovernor.
             Governance Responsibilities — "execution authorization,
             ... policy enforcement."
  - KERNEL_ARCHITECTURE_v1.0.md §14.3 — OrchestrationGovernor: K2.4 target.

Scope (K2.4):
    This governor answers one question only: is `metadata["worker_type"]`
    currently authorized to execute at all? It is deliberately distinct
    from RecursionGovernor (how deep may a call chain go) and
    AgentGovernor (which worker may delegate to which, and per-call cost).
    A worker type can be constructable — registered in WorkerRegistry —
    yet administratively disabled here, e.g. during a staged rollout or
    an incident, without touching WorkerRegistry or ExecutionRuntime.
    This is a policy-layer concern, not a resolution-layer one.

    The only live governance call site today, AbstractCognitiveWorker
    .execute(), always populates `metadata["worker_type"]`. This governor
    therefore has real, testable effect on the current execution path,
    not only a forward-looking one.

Default policy: permissive. All worker types are authorized unless
explicitly denied at construction — matching the permissive-default risk
mitigation in K2_IMPLEMENTATION_PLAN.md's K2.4 risk assessment ("New
governors too restrictive, blocking normal operation" — mitigated via
"permissive defaults, logging-only mode initially"). Registering this
governor does not change behavior for any worker type already in
production until a deny list is explicitly configured.
"""

import logging
from typing import FrozenSet, Optional

from core.governance.governance_kernel import (
    Governor,
    GovernanceAction,
    GovernanceResult,
    GovernanceVerdict,
)

logger = logging.getLogger("ocbrain.governance.orchestration")


class OrchestrationGovernor(Governor):
    """Authorizes which worker types may execute at the orchestration level.

    Architecture:
        PI §6.1 — "execution authorization"
        KERNEL_ARCHITECTURE_v1.0.md §14.3 — OrchestrationGovernor (K2.4)
    """

    name = "OrchestrationGovernor"

    def __init__(self, deny_worker_types: Optional[FrozenSet[str]] = None) -> None:
        """
        Args:
            deny_worker_types: Worker type names that are NOT authorized to
                execute. Empty by default (fully permissive).
        """
        self.deny_worker_types: FrozenSet[str] = deny_worker_types or frozenset()

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        worker_type: Optional[str] = action.metadata.get("worker_type")

        if worker_type is None:
            # No worker-type context supplied — nothing to authorize
            # against. Approve rather than reject on missing data,
            # matching BudgetGovernor's established permissive-on-absence
            # pattern (core/governance/governance_kernel.py, BudgetGovernor).
            return GovernanceResult(
                verdict=GovernanceVerdict.APPROVE, governor=self.name,
            )

        if worker_type in self.deny_worker_types:
            logger.warning(
                "[OrchestrationGovernor] Denied worker type '%s' "
                "(worker_id=%s, action_type=%s)",
                worker_type, action.worker_id, action.action_type,
            )
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=f"Worker type '{worker_type}' is not authorized to execute",
                governor=self.name,
            )

        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE, governor=self.name,
        )
