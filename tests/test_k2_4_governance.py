"""
tests/test_k2_4_governance.py — K2.4 Governance Completion test suite.

Covers (per the K2.4 session's Rule 7 requirements):
  - governor registration (all 7, correct names, correct order)
  - evaluation order (registration order; first REJECT/ESCALATE short-circuits)
  - deny/allow behavior for each new governor
  - policy propagation (GovernanceResult surfaces correctly through evaluate_action)
  - execution interruption (REJECT/ESCALATE correctly signal "do not proceed")
  - ConversationGuardrails
  - OrchestrationGovernor decisions
  - AgentGovernor decisions
  - MemoryGovernor participation, including its preserved pre-K2.4 API
  - Regression baseline for RecursionGovernor / BudgetGovernor / EvolutionGovernor,
    which had no prior dedicated test file before this session.

Architecture references: PROJECT_INSTRUCTIONS.md §6.1,
KERNEL_ARCHITECTURE_v1.0.md §14.
"""

from core.governance.governance_kernel import (
    GovernanceKernel,
    GovernanceAction,
    GovernanceVerdict,
    Governor,
    RecursionGovernor,
    BudgetGovernor,
    EvolutionGovernor,
)
from core.governance.orchestration_governor import OrchestrationGovernor
from core.governance.agent_governor import AgentGovernor
from core.governance.conversation_guardrails import ConversationGuardrails
from core.governance.memory_governor import MemoryGovernor, memory_governor


# ── Registration ─────────────────────────────────────────────────────────────

class TestGovernorRegistration:
    def test_kernel_registers_all_seven_governors_in_order(self):
        kernel = GovernanceKernel()
        assert kernel.stats()["governors"] == [
            "RecursionGovernor",
            "BudgetGovernor",
            "EvolutionGovernor",
            "OrchestrationGovernor",
            "AgentGovernor",
            "ConversationGuardrails",
            "MemoryGovernor",
        ]

    def test_each_kernel_instance_owns_independent_governor_instances(self):
        # K2.4 Rule 4: "no singleton-only behavior" for MemoryGovernor.
        # Confirm GovernanceKernel registers its own MemoryGovernor instance
        # per kernel, not a shared global.
        k1 = GovernanceKernel()
        k2 = GovernanceKernel()
        assert k1 is not k2
        mg1 = next(g for g in k1._governors if g.name == "MemoryGovernor")
        mg2 = next(g for g in k2._governors if g.name == "MemoryGovernor")
        assert mg1 is not mg2
        assert isinstance(mg1, MemoryGovernor)

    def test_all_governors_are_governor_subclasses(self):
        kernel = GovernanceKernel()
        for governor in kernel._governors:
            assert isinstance(governor, Governor)


# ── Evaluation order / short-circuit ─────────────────────────────────────────

class TestEvaluationOrder:
    def test_first_rejection_short_circuits_remaining_governors(self):
        kernel = GovernanceKernel()
        action = GovernanceAction(
            action_type="worker_execute", worker_id="w1",
            recursion_depth=999,  # exceeds RecursionGovernor's default max_depth=10
            metadata={"worker_type": "PlannerWorker"},
        )
        result = kernel.evaluate_action(action)
        assert result.verdict == GovernanceVerdict.REJECT
        assert result.governor == "RecursionGovernor"

    def test_escalation_short_circuits_remaining_governors(self):
        kernel = GovernanceKernel()
        action = GovernanceAction(
            action_type="skill_promote", worker_id="w1", requires_approval=True,
        )
        result = kernel.evaluate_action(action)
        assert result.verdict == GovernanceVerdict.ESCALATE
        assert result.governor == "EvolutionGovernor"

    def test_all_approve_falls_through_to_kernel_approval(self):
        kernel = GovernanceKernel()
        action = GovernanceAction(action_type="worker_execute", worker_id="w1")
        result = kernel.evaluate_action(action)
        assert result.verdict == GovernanceVerdict.APPROVE
        assert result.governor == "GovernanceKernel"

    def test_governor_exception_is_contained_as_rejection(self):
        # Pre-existing containment behavior (GovernanceKernel.evaluate_action's
        # try/except around each governor.evaluate() call) is unchanged by
        # K2.4 — this exercises it through the now-seven-governor chain.
        kernel = GovernanceKernel()

        class ExplodingGovernor:
            name = "ExplodingGovernor"

            def evaluate(self, action):
                raise RuntimeError("boom")

        kernel.register_governor(ExplodingGovernor())
        result = kernel.evaluate_action(GovernanceAction(action_type="worker_execute"))
        assert result.verdict == GovernanceVerdict.REJECT
        assert result.governor == "ExplodingGovernor"


# ── OrchestrationGovernor ─────────────────────────────────────────────────────

class TestOrchestrationGovernor:
    def test_permissive_by_default(self):
        gov = OrchestrationGovernor()
        result = gov.evaluate(GovernanceAction(metadata={"worker_type": "PlannerWorker"}))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_denies_configured_worker_type(self):
        gov = OrchestrationGovernor(deny_worker_types=frozenset({"CoderWorker"}))
        result = gov.evaluate(GovernanceAction(metadata={"worker_type": "CoderWorker"}))
        assert result.verdict == GovernanceVerdict.REJECT
        assert "CoderWorker" in result.reason

    def test_approves_worker_type_not_in_deny_list(self):
        gov = OrchestrationGovernor(deny_worker_types=frozenset({"CoderWorker"}))
        result = gov.evaluate(GovernanceAction(metadata={"worker_type": "PlannerWorker"}))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_approves_missing_worker_type_context(self):
        gov = OrchestrationGovernor(deny_worker_types=frozenset({"CoderWorker"}))
        result = gov.evaluate(GovernanceAction())
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_wired_into_kernel_end_to_end(self):
        kernel = GovernanceKernel()
        kernel._governors = [g for g in kernel._governors
                              if g.name != "OrchestrationGovernor"]
        kernel.register_governor(
            OrchestrationGovernor(deny_worker_types=frozenset({"CoderWorker"}))
        )
        result = kernel.evaluate_action(GovernanceAction(
            action_type="worker_execute", metadata={"worker_type": "CoderWorker"},
        ))
        assert result.verdict == GovernanceVerdict.REJECT
        assert result.governor == "OrchestrationGovernor"


# ── AgentGovernor ─────────────────────────────────────────────────────────────

class TestAgentGovernor:
    def test_permissive_by_default(self):
        gov = AgentGovernor()
        result = gov.evaluate(GovernanceAction(resource_cost=50.0))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_rejects_over_per_call_ceiling(self):
        gov = AgentGovernor(max_call_cost=100.0)
        result = gov.evaluate(GovernanceAction(resource_cost=150.0))
        assert result.verdict == GovernanceVerdict.REJECT

    def test_approves_at_or_under_ceiling(self):
        gov = AgentGovernor(max_call_cost=100.0)
        assert gov.evaluate(GovernanceAction(resource_cost=100.0)).verdict == GovernanceVerdict.APPROVE
        assert gov.evaluate(GovernanceAction(resource_cost=0.0)).verdict == GovernanceVerdict.APPROVE

    def test_permission_matrix_denies_undeclared_target(self):
        gov = AgentGovernor(
            permission_matrix={"SupervisorWorker": frozenset({"PlannerWorker"})}
        )
        result = gov.evaluate(GovernanceAction(metadata={
            "delegating_worker_type": "SupervisorWorker",
            "worker_type": "CoderWorker",
        }))
        assert result.verdict == GovernanceVerdict.REJECT

    def test_permission_matrix_allows_declared_target(self):
        gov = AgentGovernor(
            permission_matrix={"SupervisorWorker": frozenset({"PlannerWorker"})}
        )
        result = gov.evaluate(GovernanceAction(metadata={
            "delegating_worker_type": "SupervisorWorker",
            "worker_type": "PlannerWorker",
        }))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_delegator_absent_from_matrix_is_permissive(self):
        gov = AgentGovernor(permission_matrix={"SupervisorWorker": frozenset()})
        result = gov.evaluate(GovernanceAction(metadata={
            "delegating_worker_type": "UnlistedWorker",
            "worker_type": "CoderWorker",
        }))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_no_delegation_context_is_permissive(self):
        gov = AgentGovernor(
            permission_matrix={"SupervisorWorker": frozenset({"PlannerWorker"})}
        )
        result = gov.evaluate(GovernanceAction(metadata={"worker_type": "CoderWorker"}))
        assert result.verdict == GovernanceVerdict.APPROVE


# ── ConversationGuardrails ────────────────────────────────────────────────────

class TestConversationGuardrails:
    def test_permissive_with_empty_denylist(self):
        gov = ConversationGuardrails()
        result = gov.evaluate(GovernanceAction(description="anything at all"))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_rejects_configured_marker(self):
        gov = ConversationGuardrails(denylist=frozenset({"forbidden_marker"}))
        result = gov.evaluate(GovernanceAction(description="this contains forbidden_marker here"))
        assert result.verdict == GovernanceVerdict.REJECT
        assert "forbidden_marker" in result.reason

    def test_match_is_case_insensitive(self):
        gov = ConversationGuardrails(denylist=frozenset({"forbidden_marker"}))
        result = gov.evaluate(GovernanceAction(description="THIS CONTAINS FORBIDDEN_MARKER"))
        assert result.verdict == GovernanceVerdict.REJECT

    def test_no_match_approves(self):
        gov = ConversationGuardrails(denylist=frozenset({"forbidden_marker"}))
        result = gov.evaluate(GovernanceAction(description="a perfectly ordinary request"))
        assert result.verdict == GovernanceVerdict.APPROVE


# ── MemoryGovernor reconciliation ─────────────────────────────────────────────

class TestMemoryGovernorReconciliation:
    def test_is_a_governor_subclass(self):
        assert issubclass(MemoryGovernor, Governor)
        assert MemoryGovernor.name == "MemoryGovernor"

    def test_non_memory_write_actions_are_approved(self):
        gov = MemoryGovernor()
        result = gov.evaluate(GovernanceAction(action_type="worker_execute"))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_missing_entry_context_is_approved(self):
        gov = MemoryGovernor()
        result = gov.evaluate(GovernanceAction(action_type="memory_write"))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_rejects_low_confidence_entry(self):
        gov = MemoryGovernor(quality_threshold=0.6)
        result = gov.evaluate(GovernanceAction(
            action_type="memory_write",
            metadata={"entry": {"confidence": 0.1, "fact": "x"}},
        ))
        assert result.verdict == GovernanceVerdict.REJECT

    def test_approves_high_confidence_entry(self):
        gov = MemoryGovernor(quality_threshold=0.6)
        result = gov.evaluate(GovernanceAction(
            action_type="memory_write",
            metadata={"entry": {"confidence": 0.9, "fact": "x"}},
        ))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_rejects_at_growth_limit(self):
        gov = MemoryGovernor(max_entries=10)
        result = gov.evaluate(GovernanceAction(
            action_type="memory_write",
            metadata={"entry": {"confidence": 0.9, "fact": "x"}, "current_count": 10},
        ))
        assert result.verdict == GovernanceVerdict.REJECT

    def test_approves_under_growth_limit(self):
        gov = MemoryGovernor(max_entries=10)
        result = gov.evaluate(GovernanceAction(
            action_type="memory_write",
            metadata={"entry": {"confidence": 0.9, "fact": "x"}, "current_count": 5},
        ))
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_legacy_methods_still_work_standalone(self):
        # Rule 4 (K2.4): "preserve existing functionality" — the pre-K2.4
        # API surface must be untouched and independently callable.
        gov = MemoryGovernor(quality_threshold=0.5)
        assert gov.validate_ingestion({"confidence": 0.9, "fact": "x"}) is True
        assert gov.validate_ingestion({"confidence": 0.1, "fact": "x"}) is False
        assert gov.check_growth_limits(0) is True
        assert gov.detect_contradiction("x", []) is False
        entry = {"id": "e1"}
        gov.quarantine_unstable(entry)
        assert entry["validation_state"] == "quarantined"
        assert gov.stats["quarantined_count"] == 1

    def test_global_singleton_unchanged(self):
        # The pre-existing module-level singleton must still exist and
        # behave identically — no import path broken.
        assert isinstance(memory_governor, MemoryGovernor)
        assert isinstance(memory_governor, Governor)

    def test_wired_into_kernel_end_to_end(self):
        kernel = GovernanceKernel()
        result = kernel.evaluate_action(GovernanceAction(
            action_type="memory_write",
            metadata={"entry": {"confidence": 0.05, "fact": "x"}},
        ))
        assert result.verdict == GovernanceVerdict.REJECT
        assert result.governor == "MemoryGovernor"


# ── Full-chain integration ────────────────────────────────────────────────────

class TestFullChainIntegration:
    """End-to-end: realistic actions through the complete, seven-governor
    chain, exercising every governor at least once."""

    def test_typical_worker_execution_approved(self):
        kernel = GovernanceKernel()
        action = GovernanceAction(
            action_type="worker_execute", worker_id="w1",
            recursion_depth=2, resource_cost=5.0,
            description="Plan a simple research task",
            metadata={"worker_type": "PlannerWorker", "workflow_id": "wf-1"},
        )
        result = kernel.evaluate_action(action)
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_self_modifying_action_without_approval_escalates(self):
        kernel = GovernanceKernel()
        action = GovernanceAction(
            action_type="memory_prune", worker_id="w1", requires_approval=True,
        )
        result = kernel.evaluate_action(action)
        assert result.verdict == GovernanceVerdict.ESCALATE
        assert result.governor == "EvolutionGovernor"

    def test_memory_write_flows_through_full_chain_to_memory_governor(self):
        kernel = GovernanceKernel()
        action = GovernanceAction(
            action_type="memory_write", worker_id="curator-1",
            metadata={"entry": {"confidence": 0.95, "fact": "verified"},
                      "current_count": 3},
        )
        result = kernel.evaluate_action(action)
        # Recursion / Budget / Evolution / Orchestration / Agent /
        # ConversationGuardrails all approve (none of their conditions
        # apply to this action); only MemoryGovernor has an opinion, and
        # approves a valid entry.
        assert result.verdict == GovernanceVerdict.APPROVE

    def test_denied_worker_type_rejected_before_reaching_memory_governor(self):
        # Policy propagation check: confirms the REJECT from an earlier
        # governor in the chain is what the caller actually receives, not
        # silently overridden by a later governor's approval.
        kernel = GovernanceKernel()
        kernel._governors = [g for g in kernel._governors
                              if g.name != "OrchestrationGovernor"]
        kernel.register_governor(
            OrchestrationGovernor(deny_worker_types=frozenset({"CoderWorker"}))
        )
        action = GovernanceAction(
            action_type="worker_execute",
            metadata={"worker_type": "CoderWorker"},
        )
        result = kernel.evaluate_action(action)
        assert result.verdict == GovernanceVerdict.REJECT
        assert result.governor == "OrchestrationGovernor"


# ── Regression baseline: pre-existing governors (no prior test file existed) ──

class TestPreexistingGovernorsUnaffected:
    """K2.4 added four governors and reconciled a fifth; the three governors
    that predate K2.4 must behave exactly as before. No dedicated test file
    existed for these prior to this session — this establishes the baseline."""

    def test_recursion_governor_unchanged(self):
        gov = RecursionGovernor(max_depth=3)
        assert gov.evaluate(GovernanceAction(recursion_depth=3)).verdict == GovernanceVerdict.APPROVE
        assert gov.evaluate(GovernanceAction(recursion_depth=4)).verdict == GovernanceVerdict.REJECT

    def test_budget_governor_unchanged(self):
        gov = BudgetGovernor(max_steps=5)
        # No budget context in metadata -> permissive (pre-existing BUG-03 fix behavior).
        assert gov.evaluate(GovernanceAction()).verdict == GovernanceVerdict.APPROVE
        assert gov.evaluate(
            GovernanceAction(metadata={"step_count": 6})
        ).verdict == GovernanceVerdict.REJECT

    def test_evolution_governor_unchanged(self):
        gov = EvolutionGovernor()
        assert gov.evaluate(
            GovernanceAction(action_type="worker_execute")
        ).verdict == GovernanceVerdict.APPROVE
        assert gov.evaluate(
            GovernanceAction(action_type="memory_prune", requires_approval=True)
        ).verdict == GovernanceVerdict.ESCALATE
