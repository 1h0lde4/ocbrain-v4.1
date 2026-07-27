"""
core/governance/orchestration_governor.py — OrchestrationGovernor (K2.4 + K4.2.5)

Enforces orchestration-level execution authorization: which worker types
are currently authorized to execute in this deployment. Extended in
K4.2.5 (Packet 03, Planner Completion) to evaluate a ClarificationPolicy
supplied by the Planner: whether a low-confidence ExecutionPlan should be
escalated for clarification, and whether that escalation is itself
bounded rather than repeated indefinitely.

Architecture references:
  - PI LAW 1: "No autonomous capability may bypass governance."
  - PI §6.1: Required Governors — OrchestrationGovernor.
             Governance Responsibilities — "execution authorization,
             ... policy enforcement."
  - KERNEL_ARCHITECTURE_v1.0.md §14.3 — OrchestrationGovernor: K2.4 target.
  - K4.2 §2 — "ClarificationPolicy — Policy data..., owned by
               GovernanceKernel like any other Policy, evaluated by the
               OrchestrationGovernor rule, not a new component or a new
               gate."
  - K4.2 §14 — the escalation path is bounded: a Goal escalated more than
               a small, configured ceiling on the same underlying
               ambiguity is handed to SupervisorWorker as a stalled case
               rather than re-escalated indefinitely.

Scope (K2.4, unchanged): this governor's worker-type check answers one
question only: is `metadata["worker_type"]` currently authorized to
execute at all? It remains deliberately distinct from RecursionGovernor
(how deep may a call chain go) and AgentGovernor (which worker may
delegate to which, and per-call cost).

Scope addition (K4.2.5): a second, independent question, evaluated only
when the action's metadata describes a confidence-bearing decision (i.e.
`metadata["confidence"]` is present) — orthogonal to the worker-type
check above and does not alter it. This governor remains a dedicated,
two-question evaluator, not a generic rule registry: no rule-registration
API was added, GovernanceKernel's Governor list is unchanged (still one
OrchestrationGovernor instance, not a rule-plugin collection), and
ClarificationPolicy is not imported here as a type — its two parameters
(confidence_threshold, max_escalations) are read as plain values out of
GovernanceAction.metadata, the same generic Dict[str, Any] extension
point the existing worker_type check already uses. This avoids a
governance-layer (core/governance/) import of a Cognitive Runtime type
(core/cognitive/planner.py) that would otherwise invert this codebase's
existing layering (Cognitive Runtime depends on Governance's public
types, not the reverse — see core/cognitive/planner.py's own imports of
GovernanceAction/GovernanceResult/GovernanceVerdict for the direction
that already holds everywhere else in this codebase).

The escalation bound (K4.2 §14: "reusing RecursionGovernor's existing
bounded-loop principle rather than inventing a second one") is
implemented as a small counter-vs-ceiling comparison within this same
evaluate() call — the same shape of check RecursionGovernor already
performs (a bounded counter compared against a configured max, reject
once exceeded) — rather than literally routing through
RecursionGovernor's own max_depth/recursion_depth, which is a separate,
general-purpose field shared by unrelated recursion contexts elsewhere in
this system; overloading it for clarification-retry counting specifically
risked exactly the field-conflation "reuse... rather than inventing a
second one" is trying to prevent, not the behavior it endorses. Documented
here as a deliberate implementation choice, not a silent assumption.

Default policy: permissive. All worker types are authorized unless
explicitly denied at construction — matching the permissive-default risk
mitigation in K2_IMPLEMENTATION_PLAN.md's K2.4 risk assessment ("New
governors too restrictive, blocking normal operation" — mitigated via
"permissive defaults, logging-only mode initially"). The clarification
check is equally permissive-on-absence: an action with no `confidence`
key in metadata is unaffected by this addition entirely, matching the
worker-type check's own established permissive-on-absence pattern.
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

_DEFAULT_CONFIDENCE_THRESHOLD = 0.5
_DEFAULT_MAX_ESCALATIONS = 2


class OrchestrationGovernor(Governor):
    """Authorizes which worker types may execute, and evaluates
    ClarificationPolicy escalation for low-confidence ExecutionPlans.

    Architecture:
        PI §6.1 — "execution authorization"
        KERNEL_ARCHITECTURE_v1.0.md §14.3 — OrchestrationGovernor (K2.4)
        K4.2 §2/§14 — ClarificationPolicy evaluation (K4.2.5)
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
        clarification_result = self._evaluate_clarification_policy(action)
        if clarification_result is not None:
            return clarification_result

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

    def _evaluate_clarification_policy(
        self, action: GovernanceAction,
    ) -> Optional[GovernanceResult]:
        """Evaluates ClarificationPolicy for a confidence-bearing action.

        Architecture: K4.2 §2/§14 (see module docstring for full
        citation). Returns None (defer to the worker-type check) when
        `metadata["confidence"]` is absent — this action isn't a
        confidence-bearing decision at all, permissive-on-absence like
        every other check this governor performs.

        Expected metadata keys, all supplied by the caller (Planner /
        a future Plan Compilation packet), none imported as a type here:
            confidence (float): the ExecutionPlan's estimated confidence.
            confidence_threshold (float, default 0.5): ClarificationPolicy's
                threshold below which escalation is considered.
            clarification_attempt (int, default 0): how many times this
                specific ambiguity has already been escalated.
            max_escalations (int, default 2): ClarificationPolicy's bound
                on repeated escalation for the same ambiguity.
        """
        confidence = action.metadata.get("confidence")
        if confidence is None:
            return None

        threshold = action.metadata.get(
            "confidence_threshold", _DEFAULT_CONFIDENCE_THRESHOLD,
        )
        if confidence >= threshold:
            return None

        attempt = action.metadata.get("clarification_attempt", 0)
        max_escalations = action.metadata.get(
            "max_escalations", _DEFAULT_MAX_ESCALATIONS,
        )

        if attempt >= max_escalations:
            logger.warning(
                "[OrchestrationGovernor] Clarification bound exceeded "
                "(confidence=%.2f, threshold=%.2f, attempt=%d, "
                "max_escalations=%d, worker_id=%s) — stalled, route to "
                "SupervisorWorker rather than escalate again.",
                confidence, threshold, attempt, max_escalations,
                action.worker_id,
            )
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=(
                    f"Confidence {confidence:.2f} below threshold "
                    f"{threshold:.2f} after {attempt} clarification "
                    f"attempt(s), exceeding max_escalations="
                    f"{max_escalations} — stalled case, route to "
                    f"SupervisorWorker rather than escalate again "
                    f"(K4.2 §14)."
                ),
                governor=self.name,
            )

        return GovernanceResult(
            verdict=GovernanceVerdict.ESCALATE,
            reason=(
                f"Confidence {confidence:.2f} below threshold "
                f"{threshold:.2f} (clarification attempt {attempt + 1} "
                f"of {max_escalations})."
            ),
            governor=self.name,
        )
