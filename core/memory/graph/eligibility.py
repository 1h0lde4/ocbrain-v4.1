"""
core/memory/graph/eligibility.py — Session 5.25 Graph Index Foundation.

GraphEligibilityPolicy centralizes "should this KnowledgeEntry get a graph
node?" logic, which previously lived as a single hardcoded call
(`entry.is_graph_eligible()`) inline inside UnifiedMemory.write(). Session
5.25 objective: policy-driven eligibility, not hardcoded in UnifiedMemory.

Backward-compatibility constraint (reality-first): several existing tests
(tests/test_session4b_memory_hardening.py::test_l3_graph_failure_does_not_break_write,
::test_graph_backend_unregistered_in_production_is_a_clean_noop, and others)
patch the module-level core.memory.knowledge_entry.GRAPH_ELIGIBLE_STATUSES
constant directly to force eligibility during a test. The default policy
below MUST keep consulting that same live value -- so it delegates to
entry.is_graph_eligible() rather than re-implementing the truth_status
check -- or those patches would silently stop working.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from core.memory.knowledge_entry import KnowledgeEntry


@dataclass
class EligibilityResult:
    """Outcome of a policy evaluation. `reason` is for logs/debugging only
    -- callers should branch on `eligible`, never parse `reason`."""
    eligible: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.eligible


class GraphEligibilityPolicy(ABC):
    """Decides whether a KnowledgeEntry should be represented in the graph.

    Implementations must be pure functions of the entry (and, in future,
    caller-supplied context) -- no I/O, no side effects, so GraphIndexer can
    call evaluate() freely without worrying about cost or ordering.
    """

    @abstractmethod
    def evaluate(self, entry: "KnowledgeEntry") -> EligibilityResult: ...


class TruthStatusEligibilityPolicy(GraphEligibilityPolicy):
    """Default policy. Wraps entry.is_graph_eligible() (truth_status in
    GRAPH_ELIGIBLE_STATUSES) with an optional confidence floor on top.

    min_confidence=0.0 (default) makes this behaviorally IDENTICAL to the
    pre-Session-5.25 inline check -- this policy is additive infrastructure,
    not a behavior change, until a caller raises min_confidence above 0.
    """

    def __init__(self, min_confidence: float = 0.0) -> None:
        self.min_confidence = min_confidence

    def evaluate(self, entry: "KnowledgeEntry") -> EligibilityResult:
        if not entry.is_graph_eligible():
            return EligibilityResult(
                False, f"truth_status={entry.truth_status!r} not graph-eligible")
        if entry.confidence < self.min_confidence:
            return EligibilityResult(
                False,
                f"confidence {entry.confidence:.2f} < floor {self.min_confidence:.2f}")
        return EligibilityResult(True, "truth_status + confidence pass")


class AllOf(GraphEligibilityPolicy):
    """Composite: eligible only if every sub-policy is eligible. Lets callers
    layer new criteria (content_type allowlist, worker allowlist, source
    trust, extracted-entity presence, ...) without touching UnifiedMemory or
    the policies already in production."""

    def __init__(self, *policies: GraphEligibilityPolicy) -> None:
        self.policies: List[GraphEligibilityPolicy] = list(policies)

    def evaluate(self, entry: "KnowledgeEntry") -> EligibilityResult:
        for policy in self.policies:
            result = policy.evaluate(entry)
            if not result.eligible:
                return result
        return EligibilityResult(True, "all sub-policies passed")


class AnyOf(GraphEligibilityPolicy):
    """Composite: eligible if any sub-policy is eligible."""

    def __init__(self, *policies: GraphEligibilityPolicy) -> None:
        self.policies: List[GraphEligibilityPolicy] = list(policies)

    def evaluate(self, entry: "KnowledgeEntry") -> EligibilityResult:
        last = EligibilityResult(False, "no sub-policies")
        for policy in self.policies:
            last = policy.evaluate(entry)
            if last.eligible:
                return last
        return last
