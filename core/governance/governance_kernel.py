"""
core/governance/governance_kernel.py — GovernanceKernel (v4.3.5)

Central enforcement point for all autonomous actions in OCBrain.

Architecture references:
  - PI LAW 1: "No autonomous capability may bypass governance."
  - PI §6.1: "The GovernanceKernel is mandatory."
  - FA §4.1 Layer 0: GovernanceKernel (recursion, steps, tokens, workers)
  - FA §4.1 Layer 0: EvolutionGovernor (self-modification requires approval)

Required Governors (PI §6.1):
  - OrchestrationGovernor
  - MemoryGovernor (exists: core/governance/memory_governor.py)
  - AgentGovernor
  - EvolutionGovernor
  - ConversationGuardrails

Design:
  - Template Method enforcement: Workers call execute() which wraps _run()
    inside evaluate_action(), ensuring no bypass.
  - Governor registration: Governors register at startup, kernel orchestrates.
  - Action model: Every governed action is described by a GovernanceAction
    dataclass, evaluated by all registered governors before execution.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ocbrain.governance.kernel")


class GovernanceVerdict(Enum):
    """Outcome of a governance evaluation.

    Architecture:
        PI §6.1 — Every autonomous action must pass through governance evaluation.
    """

    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"   # Requires HITL approval (FA §4.1 HumanApprovalNode)


@dataclass
class GovernanceAction:
    """Describes a single action to be evaluated by the GovernanceKernel.

    Architecture:
        PI LAW 1 — governance evaluation requires a structured action description.
        PI §6.1 — "recursion depth limits, budget enforcement, approval requirements,
                    execution authorization, memory protection, self-modification
                    prevention, policy enforcement."

    Attributes:
        action_type: Category of action (worker_execute, memory_write, etc.).
        worker_id: Which worker is requesting the action.
        description: Human-readable summary.
        resource_cost: Estimated resource consumption (tokens, compute).
        recursion_depth: Current recursion depth for loop detection.
        requires_approval: Whether HITL approval is needed.
        metadata: Additional context for governor evaluation.
    """

    action_type:       str            = ""
    worker_id:         str            = ""
    description:       str            = ""
    resource_cost:     float          = 0.0
    recursion_depth:   int            = 0
    requires_approval: bool           = False
    metadata:          Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceResult:
    """Result of a governance evaluation.

    Attributes:
        verdict: APPROVE, REJECT, or ESCALATE.
        reason: Explanation of the decision.
        governor: Which governor produced this result.
        constraints: Any constraints the action must obey.
    """

    verdict:     GovernanceVerdict = GovernanceVerdict.APPROVE
    reason:      str               = ""
    governor:    str               = ""
    constraints: Dict[str, Any]    = field(default_factory=dict)


class Governor:
    """Base class for all governors.

    Architecture:
        PI §6.1 Required Governors: OrchestrationGovernor, MemoryGovernor,
        AgentGovernor, EvolutionGovernor, ConversationGuardrails.
        FA §4.1 Layer 0: Governance & Security layer.

    Subclasses override evaluate() to implement domain-specific policy.
    """

    name: str = "BaseGovernor"

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        """Evaluate a governance action. Override in subclasses.

        Args:
            action: The action to evaluate.

        Returns:
            GovernanceResult with verdict, reason, and any constraints.
        """
        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE,
            governor=self.name,
        )


class RecursionGovernor(Governor):
    """Prevents runaway recursive loops.

    Architecture:
        PI §6.1 — "recursion depth limits"
        FA §4.1 Layer 0 — GovernanceKernel (recursion, steps, tokens, workers)
    """

    name = "RecursionGovernor"

    def __init__(self, max_depth: int = 10) -> None:
        self.max_depth = max_depth

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        if action.recursion_depth > self.max_depth:
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=(f"Recursion depth {action.recursion_depth} exceeds "
                        f"limit {self.max_depth}"),
                governor=self.name,
            )
        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE, governor=self.name,
        )


class BudgetGovernor(Governor):
    """Enforces token and step budgets per workflow.

    Architecture:
        PI §6.1 — "budget enforcement"
        FA §4.1 Layer 0 — GovernanceKernel (tokens)
    """

    name = "BudgetGovernor"

    def __init__(self, max_steps: int = 100,
                 max_token_budget: float = 1_000_000.0) -> None:
        self.max_steps = max_steps
        self.max_token_budget = max_token_budget
        self._step_count: int = 0
        self._token_spend: float = 0.0

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        self._step_count += 1
        self._token_spend += action.resource_cost

        if self._step_count > self.max_steps:
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=f"Step budget exhausted ({self._step_count}/{self.max_steps})",
                governor=self.name,
            )
        if self._token_spend > self.max_token_budget:
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=f"Token budget exhausted ({self._token_spend:.0f}/{self.max_token_budget:.0f})",
                governor=self.name,
            )
        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE, governor=self.name,
        )

    def reset(self) -> None:
        """Reset counters for a new workflow."""
        self._step_count = 0
        self._token_spend = 0.0


class EvolutionGovernor(Governor):
    """Controls self-modification actions.

    Architecture:
        FA §4.1 Layer 0 — "EvolutionGovernor (self-modification requires approval)"
        FA §8 Risk 7 — "Incorrect fact derivation (mitigate: low confidence score
                         + review); over-pruning (mitigate: importance threshold
                         before delete, log pruned entries to L4)"
    """

    name = "EvolutionGovernor"

    SELF_MODIFYING_ACTIONS = {
        "memory_curate", "skill_create", "skill_promote",
        "memory_derive", "memory_prune", "memory_merge",
    }

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        if action.action_type in self.SELF_MODIFYING_ACTIONS:
            if action.requires_approval:
                return GovernanceResult(
                    verdict=GovernanceVerdict.ESCALATE,
                    reason=f"Self-modifying action '{action.action_type}' requires HITL approval",
                    governor=self.name,
                )
            logger.info("[EvolutionGovernor] Auto-approved self-modifying action: %s",
                        action.action_type)
        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE, governor=self.name,
        )


class GovernanceKernel:
    """Central governance enforcement point.

    Architecture:
        PI §6.1: "The GovernanceKernel is mandatory."
        PI LAW 1: "No autonomous capability may bypass governance."
        FA §4.1 Layer 0: "GovernanceKernel (recursion, steps, tokens, workers)"

    All worker execution, memory writes, and workflow transitions pass through
    evaluate_action() before proceeding. This is enforced by the Template Method
    pattern in AbstractCognitiveWorker.execute().

    Usage:
        kernel = GovernanceKernel()
        result = kernel.evaluate_action(action)
        if result.verdict == GovernanceVerdict.APPROVE:
            # proceed
        elif result.verdict == GovernanceVerdict.REJECT:
            # abort with reason
        elif result.verdict == GovernanceVerdict.ESCALATE:
            # queue for HITL approval
    """

    def __init__(self) -> None:
        self._governors: List[Governor] = []
        self._evaluation_count: int = 0
        self._rejection_count: int = 0
        self._escalation_count: int = 0
        self._last_rejection: Optional[GovernanceResult] = None

        # Register default governors (PI §6.1 canonical set)
        self.register_governor(RecursionGovernor())
        self.register_governor(BudgetGovernor())
        self.register_governor(EvolutionGovernor())

        logger.info("GovernanceKernel initialized with %d governor(s)",
                     len(self._governors))

    def register_governor(self, governor: Governor) -> None:
        """Register a governor for action evaluation.

        Args:
            governor: Governor instance to add to the evaluation chain.

        Architecture:
            PI §6.1 — Governors are registered at startup. The kernel
            orchestrates their evaluation in registration order.
        """
        self._governors.append(governor)
        logger.info("Governor registered: %s", governor.name)

    def evaluate_action(self, action: GovernanceAction) -> GovernanceResult:
        """Evaluate an action against all registered governors.

        This is the single entry point for governance. All governors are
        evaluated in order. The first REJECT or ESCALATE terminates evaluation.

        Args:
            action: The GovernanceAction describing what the caller wants to do.

        Returns:
            GovernanceResult with the aggregate verdict.

        Architecture:
            PI LAW 1 — Every autonomous action passes through here.
            PI §6.1 — "Every autonomous action must pass through governance
                        evaluation."
        """
        self._evaluation_count += 1

        for governor in self._governors:
            try:
                result = governor.evaluate(action)
            except Exception as e:
                logger.error("[GovernanceKernel] Governor %s raised: %s",
                             governor.name, e)
                result = GovernanceResult(
                    verdict=GovernanceVerdict.REJECT,
                    reason=f"Governor {governor.name} error: {e}",
                    governor=governor.name,
                )

            if result.verdict == GovernanceVerdict.REJECT:
                self._rejection_count += 1
                self._last_rejection = result
                logger.warning("[GovernanceKernel] REJECTED by %s: %s",
                               result.governor, result.reason)
                return result

            if result.verdict == GovernanceVerdict.ESCALATE:
                self._escalation_count += 1
                logger.info("[GovernanceKernel] ESCALATED by %s: %s",
                            result.governor, result.reason)
                return result

        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE,
            governor="GovernanceKernel",
            reason="All governors approved",
        )

    def stats(self) -> Dict[str, Any]:
        """Return governance statistics.

        Returns:
            Dict with evaluation, rejection, escalation counts.
        """
        return {
            "evaluations": self._evaluation_count,
            "rejections": self._rejection_count,
            "escalations": self._escalation_count,
            "governors": [g.name for g in self._governors],
            "last_rejection": (
                {"reason": self._last_rejection.reason,
                 "governor": self._last_rejection.governor}
                if self._last_rejection else None
            ),
        }


# ── Module-level singleton ────────────────────────────────────────────────────

_kernel: Optional[GovernanceKernel] = None


def get_governance_kernel() -> GovernanceKernel:
    """Return (or create) the shared GovernanceKernel singleton.

    Architecture:
        PI §6.1 — There is exactly one GovernanceKernel per process.
    """
    global _kernel
    if _kernel is None:
        _kernel = GovernanceKernel()
    return _kernel
