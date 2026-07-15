"""
core/governance/agent_governor.py — AgentGovernor (K2.4)

Enforces per-agent constraints distinct from RecursionGovernor (call-chain
depth) and BudgetGovernor (cumulative workflow budget):

  1. Per-call resource cost ceiling — a single action's own resource_cost
     may not exceed a configured ceiling, independent of the workflow's
     cumulative budget. This is live and testable today: `resource_cost`
     is a first-class field on every GovernanceAction.
  2. Delegation permission matrix — which worker types a delegating
     worker (e.g. a future SupervisorWorker) is permitted to invoke.

Architecture references:
  - PI LAW 1: "No autonomous capability may bypass governance."
  - PI §6.1: Required Governors — AgentGovernor.
  - KERNEL_ARCHITECTURE_v1.0.md §14.3 — AgentGovernor: K2.4 target.

Scope (K2.4):
    The delegation permission matrix is forward-looking: no canonical
    worker type currently delegates to another — SupervisorWorker (PI
    §7.1) is not yet built, and no live call site populates
    `metadata["delegating_worker_type"]`. The check itself is real and
    fully tested; it is a documented no-op against current production
    traffic until SupervisorWorker exists, at which point it becomes
    live with no further change required here.

Default policy: permissive, matching K2_IMPLEMENTATION_PLAN.md's K2.4
risk mitigation.
"""

import logging
from typing import Dict, FrozenSet, Optional

from core.governance.governance_kernel import (
    Governor,
    GovernanceAction,
    GovernanceResult,
    GovernanceVerdict,
)

logger = logging.getLogger("ocbrain.governance.agent")


class AgentGovernor(Governor):
    """Per-agent resource ceiling and delegation permission matrix.

    Architecture:
        PI §6.1 — "delegation depth, token budgets, permission matrix"
        KERNEL_ARCHITECTURE_v1.0.md §14.3 — AgentGovernor (K2.4)
    """

    name = "AgentGovernor"

    def __init__(
        self,
        max_call_cost: float = 10_000.0,
        permission_matrix: Optional[Dict[str, FrozenSet[str]]] = None,
    ) -> None:
        """
        Args:
            max_call_cost: Maximum resource_cost permitted for a single
                action, independent of the workflow's cumulative budget
                (BudgetGovernor governs the cumulative case).
            permission_matrix: Maps a delegating worker_type to the set of
                worker_types it is permitted to invoke. A delegating
                worker_type absent from this mapping is permitted to
                delegate to anything (permissive default). Empty by
                default.
        """
        self.max_call_cost = max_call_cost
        self.permission_matrix: Dict[str, FrozenSet[str]] = permission_matrix or {}

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        if action.resource_cost > self.max_call_cost:
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=(f"Single-action resource cost {action.resource_cost:.0f} "
                        f"exceeds per-call ceiling {self.max_call_cost:.0f}"),
                governor=self.name,
            )

        delegator: Optional[str] = action.metadata.get("delegating_worker_type")
        target: Optional[str] = action.metadata.get("worker_type")

        if delegator is not None and target is not None:
            allowed = self.permission_matrix.get(delegator)
            if allowed is not None and target not in allowed:
                logger.warning(
                    "[AgentGovernor] Denied delegation '%s' -> '%s' "
                    "(worker_id=%s)", delegator, target, action.worker_id,
                )
                return GovernanceResult(
                    verdict=GovernanceVerdict.REJECT,
                    reason=(f"'{delegator}' is not permitted to delegate to "
                            f"'{target}'"),
                    governor=self.name,
                )

        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE, governor=self.name,
        )
