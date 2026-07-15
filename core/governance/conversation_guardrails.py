"""
core/governance/conversation_guardrails.py — ConversationGuardrails (K2.4)

Session-level content policy: rejects actions whose description contains
an explicitly configured disallowed marker.

Architecture references:
  - PI LAW 1: "No autonomous capability may bypass governance."
  - PI §6.1: Required Governors — ConversationGuardrails.
             Governance Responsibilities — "policy enforcement."
  - KERNEL_ARCHITECTURE_v1.0.md §14.3 — ConversationGuardrails: K2.4 target.

Scope (K2.4):
    This is a deliberately narrow, explicit pattern-match gate — not a
    content-safety classifier, which would be well beyond a governance
    layer's documented responsibility ("policy enforcement", not "content
    moderation ML"). `GovernanceAction.description` reliably carries a
    snippet of the actual task/query text from the only live call site
    (AbstractCognitiveWorker.execute()), so this check has real effect
    today against whatever markers are configured.

Default policy: permissive — the denylist is empty by default, matching
K2_IMPLEMENTATION_PLAN.md's K2.4 risk mitigation. An empty denylist
approves every action unconditionally; this governor has no effect until
a specific, deliberately-chosen denylist is supplied at construction.
"""

import logging
from typing import FrozenSet, Optional

from core.governance.governance_kernel import (
    Governor,
    GovernanceAction,
    GovernanceResult,
    GovernanceVerdict,
)

logger = logging.getLogger("ocbrain.governance.conversation")


class ConversationGuardrails(Governor):
    """Rejects actions whose description matches a configured denylist.

    Architecture:
        PI §6.1 — "policy enforcement"
        KERNEL_ARCHITECTURE_v1.0.md §14.3 — ConversationGuardrails (K2.4)
    """

    name = "ConversationGuardrails"

    def __init__(self, denylist: Optional[FrozenSet[str]] = None) -> None:
        """
        Args:
            denylist: Lowercase substrings that, if present in
                `action.description` (case-insensitive), cause rejection.
                Empty by default (fully permissive).
        """
        self.denylist: FrozenSet[str] = denylist or frozenset()

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        if not self.denylist:
            return GovernanceResult(
                verdict=GovernanceVerdict.APPROVE, governor=self.name,
            )

        description_lower = action.description.lower()
        for marker in self.denylist:
            if marker in description_lower:
                logger.warning(
                    "[ConversationGuardrails] Rejected action (worker_id=%s): "
                    "description matched denylisted marker",
                    action.worker_id,
                )
                return GovernanceResult(
                    verdict=GovernanceVerdict.REJECT,
                    reason=f"Description matched disallowed marker: '{marker}'",
                    governor=self.name,
                )

        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE, governor=self.name,
        )
