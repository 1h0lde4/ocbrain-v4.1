"""
tests/test_k3_5_1_governance_consistency.py — K3.5.1 Kernel Closure test suite.

Covers the invariant established by K3.5.1: no persistent state mutation
inside UnifiedMemory (write, update, delete) bypasses GovernanceKernel.

K3.5 already governed write(). This suite covers the two remaining
mutation entry points closed by K3.5.1:
  - update() calls evaluate_action() (action_type="memory_update") before
    any storage mutation, cache invalidation, archive write, or graph sync.
  - delete() calls evaluate_action() (action_type="memory_delete") after
    loading the entry (read-only) but before any hook or mutation.
  - REJECT/ESCALATE short-circuits both, returns False, and emits a
    durable KnowledgeEvent (memory_update_rejected/escalated,
    memory_delete_rejected/escalated) rather than silently no-op'ing.
  - The permissive-when-governance-absent pattern (matching write()) is
    preserved: with no GovernanceKernel registered, both proceed exactly
    as before this change.
  - Governance runs before the mutation, not after: a REJECT must leave
    the entry provably unmutated / undeleted.

Architecture references: PROJECT_INSTRUCTIONS.md LAW 1 (Governance Before
Capability), Constitution Law 1 (Bounded Autonomy),
core/memory/unified_memory.py (K3.5.1).
"""

import os

import pytest
import pytest_asyncio

from core.governance.governance_kernel import (
    GovernanceKernel,
    Governor,
    GovernanceAction,
    GovernanceVerdict,
    GovernanceResult,
)
from core.memory.unified_memory import UnifiedMemory


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_prefix(tmp_path) -> str:
    prefix = str(tmp_path / "memory")
    os.makedirs(prefix, exist_ok=True)
    return prefix


@pytest.fixture
def memory(tmp_prefix) -> UnifiedMemory:
    """Ungoverned instance — mirrors write()'s permissive-when-absent baseline."""
    return UnifiedMemory(db_prefix=tmp_prefix)


class _AlwaysRejectGovernor(Governor):
    """Test double: rejects every action_type it's told to target, approves the rest."""

    def __init__(self, target_action_type: str, reason: str = "test rejection"):
        self._target = target_action_type
        self._reason = reason

    @property
    def name(self) -> str:
        return "AlwaysRejectGovernor"

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        if action.action_type == self._target:
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=self._reason,
                governor=self.name,
            )
        return GovernanceResult(verdict=GovernanceVerdict.APPROVE, governor=self.name)


class _AlwaysEscalateGovernor(Governor):
    """Test double: escalates every action_type it's told to target, approves the rest."""

    def __init__(self, target_action_type: str, reason: str = "test escalation"):
        self._target = target_action_type
        self._reason = reason

    @property
    def name(self) -> str:
        return "AlwaysEscalateGovernor"

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        if action.action_type == self._target:
            return GovernanceResult(
                verdict=GovernanceVerdict.ESCALATE,
                reason=self._reason,
                governor=self.name,
            )
        return GovernanceResult(verdict=GovernanceVerdict.APPROVE, governor=self.name)


class _RecordingApproveGovernor(Governor):
    """Test double: always approves, but records every action it saw."""

    def __init__(self):
        self.seen: list = []

    @property
    def name(self) -> str:
        return "RecordingApproveGovernor"

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        self.seen.append(action)
        return GovernanceResult(verdict=GovernanceVerdict.APPROVE, governor=self.name)


def _kernel_with(governor: Governor) -> GovernanceKernel:
    """A minimal kernel running only the supplied governor -- avoids coupling
    these tests to the full 7-governor default chain's unrelated behavior."""
    kernel = GovernanceKernel()
    kernel._governors = [governor]
    return kernel


# ── update() governance ────────────────────────────────────────────────────────

class TestUpdateGovernance:
    @pytest.mark.asyncio
    async def test_permissive_when_governance_absent(self, memory):
        """No GovernanceKernel registered -> update() proceeds exactly as
        it did before K3.5.1 (matches write()'s established baseline).
        Uses `confidence` as the mutated field: SQLiteStorageBackend.update()
        only accepts a fixed whitelist of columns, and `content` is not one
        of them (content is write-once; corrections happen via new entries,
        not content mutation) -- confirmed directly against the storage
        layer, not assumed."""
        entry_id = await memory.write(content="original", content_type="fact", confidence=0.5)
        ok = await memory.update(entry_id, {"confidence": 0.9})
        assert ok is True
        entry = await memory.read(entry_id)
        assert entry.confidence == 0.9

    @pytest.mark.asyncio
    async def test_reject_blocks_mutation_and_returns_false(self, memory):
        entry_id = await memory.write(content="original", content_type="fact", confidence=0.5)
        memory.register_governance(_kernel_with(_AlwaysRejectGovernor("memory_update")))

        ok = await memory.update(entry_id, {"confidence": 0.9})

        assert ok is False
        entry = await memory.read(entry_id)
        assert entry.confidence == 0.5, \
            "REJECT must run before the mutation -- entry must be provably unchanged"

    @pytest.mark.asyncio
    async def test_escalate_blocks_mutation_and_returns_false(self, memory):
        entry_id = await memory.write(content="original", content_type="fact", confidence=0.5)
        memory.register_governance(_kernel_with(_AlwaysEscalateGovernor("memory_update")))

        ok = await memory.update(entry_id, {"confidence": 0.9})

        assert ok is False
        entry = await memory.read(entry_id)
        assert entry.confidence == 0.5

    @pytest.mark.asyncio
    async def test_reject_emits_durable_event(self, memory):
        entry_id = await memory.write(content="original", content_type="fact")
        memory.register_governance(_kernel_with(_AlwaysRejectGovernor("memory_update", reason="policy X")))

        await memory.update(entry_id, {"confidence": 0.9})

        events = await memory._archive.query_events(
            entry_id=entry_id, event_type="memory_update_rejected",
        )
        assert len(events) == 1
        assert events[0].metadata["reason"] == "policy X"
        assert events[0].metadata["governor"] == "AlwaysRejectGovernor"

    @pytest.mark.asyncio
    async def test_escalate_emits_durable_event(self, memory):
        entry_id = await memory.write(content="original", content_type="fact")
        memory.register_governance(_kernel_with(_AlwaysEscalateGovernor("memory_update", reason="needs review")))

        await memory.update(entry_id, {"confidence": 0.9})

        events = await memory._archive.query_events(
            entry_id=entry_id, event_type="memory_update_escalated",
        )
        assert len(events) == 1
        assert events[0].metadata["reason"] == "needs review"

    @pytest.mark.asyncio
    async def test_approve_allows_mutation_through(self, memory):
        entry_id = await memory.write(content="original", content_type="fact", confidence=0.5)
        recorder = _RecordingApproveGovernor()
        memory.register_governance(_kernel_with(recorder))

        ok = await memory.update(entry_id, {"confidence": 0.9})

        assert ok is True
        entry = await memory.read(entry_id)
        assert entry.confidence == 0.9
        assert len(recorder.seen) == 1
        assert recorder.seen[0].action_type == "memory_update"
        assert recorder.seen[0].metadata["entry_id"] == entry_id

    @pytest.mark.asyncio
    async def test_metadata_shape_matches_established_pattern(self, memory):
        """Objective 1: only fields that already exist -- entry, confidence,
        content, current_count, entry_id. No invented metadata."""
        entry_id = await memory.write(content="original", content_type="fact")
        recorder = _RecordingApproveGovernor()
        memory.register_governance(_kernel_with(recorder))

        await memory.update(entry_id, {"content": "x", "confidence": 0.9})

        action = recorder.seen[0]
        assert set(action.metadata.keys()) == {"entry", "current_count", "entry_id"}
        assert set(action.metadata["entry"].keys()) == {"confidence", "content"}
        assert action.metadata["entry"]["content"] == "x"
        assert action.metadata["entry"]["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_governance_runs_before_graph_sync_and_hooks(self, memory):
        """Governance must be the first thing that happens -- before storage,
        cache invalidation, archive write, or graph sync, per write()'s
        established placement."""
        entry_id = await memory.write(content="original", content_type="fact")
        call_order = []

        class _OrderTrackingGovernor(Governor):
            @property
            def name(self):
                return "OrderTracker"

            def evaluate(self, action):
                call_order.append("governance")
                return GovernanceResult(verdict=GovernanceVerdict.APPROVE, governor=self.name)

        memory.register_governance(_kernel_with(_OrderTrackingGovernor()))
        original_storage_update = memory._storage.update

        async def _tracking_update(*args, **kwargs):
            call_order.append("storage")
            return await original_storage_update(*args, **kwargs)

        memory._storage.update = _tracking_update

        await memory.update(entry_id, {"confidence": 0.9})

        assert call_order == ["governance", "storage"]


# ── delete() governance ────────────────────────────────────────────────────────

class TestDeleteGovernance:
    @pytest.mark.asyncio
    async def test_permissive_when_governance_absent(self, memory):
        entry_id = await memory.write(content="to delete", content_type="fact")
        ok = await memory.delete(entry_id)
        assert ok is True
        assert await memory.read(entry_id) is None

    @pytest.mark.asyncio
    async def test_reject_blocks_deletion_and_returns_false(self, memory):
        entry_id = await memory.write(content="must survive", content_type="fact")
        memory.register_governance(_kernel_with(_AlwaysRejectGovernor("memory_delete")))

        ok = await memory.delete(entry_id)

        assert ok is False
        entry = await memory.read(entry_id)
        assert entry is not None, "REJECT must prevent deletion -- entry must still exist"
        assert entry.content == "must survive"

    @pytest.mark.asyncio
    async def test_escalate_blocks_deletion_and_returns_false(self, memory):
        entry_id = await memory.write(content="must survive", content_type="fact")
        memory.register_governance(_kernel_with(_AlwaysEscalateGovernor("memory_delete")))

        ok = await memory.delete(entry_id)

        assert ok is False
        assert await memory.read(entry_id) is not None

    @pytest.mark.asyncio
    async def test_nonexistent_entry_short_circuits_before_governance(self, memory):
        """Load-then-check-existence (step 1) happens before governance
        (step 2) -- a nonexistent entry_id must not construct a
        GovernanceAction at all, matching the documented orchestration order."""
        recorder = _RecordingApproveGovernor()
        memory.register_governance(_kernel_with(recorder))

        ok = await memory.delete("does-not-exist")

        assert ok is False
        assert recorder.seen == [], \
            "governance must not be evaluated for an entry that was never loaded"

    @pytest.mark.asyncio
    async def test_reject_emits_durable_event(self, memory):
        entry_id = await memory.write(content="must survive", content_type="fact")
        memory.register_governance(_kernel_with(_AlwaysRejectGovernor("memory_delete", reason="policy Y")))

        await memory.delete(entry_id)

        events = await memory._archive.query_events(
            entry_id=entry_id, event_type="memory_delete_rejected",
        )
        assert len(events) == 1
        assert events[0].metadata["reason"] == "policy Y"
        assert events[0].metadata["governor"] == "AlwaysRejectGovernor"

    @pytest.mark.asyncio
    async def test_escalate_emits_durable_event(self, memory):
        entry_id = await memory.write(content="must survive", content_type="fact")
        memory.register_governance(_kernel_with(_AlwaysEscalateGovernor("memory_delete", reason="needs review")))

        await memory.delete(entry_id)

        events = await memory._archive.query_events(
            entry_id=entry_id, event_type="memory_delete_escalated",
        )
        assert len(events) == 1
        assert events[0].metadata["reason"] == "needs review"

    @pytest.mark.asyncio
    async def test_approve_allows_deletion_through(self, memory):
        entry_id = await memory.write(content="to delete", content_type="fact")
        recorder = _RecordingApproveGovernor()
        memory.register_governance(_kernel_with(recorder))

        ok = await memory.delete(entry_id)

        assert ok is True
        assert await memory.read(entry_id) is None
        assert len(recorder.seen) == 1
        assert recorder.seen[0].action_type == "memory_delete"
        assert recorder.seen[0].metadata["entry_id"] == entry_id

    @pytest.mark.asyncio
    async def test_metadata_shape_matches_established_pattern(self, memory):
        entry_id = await memory.write(
            content="original content", content_type="fact", confidence=0.75,
        )
        recorder = _RecordingApproveGovernor()
        memory.register_governance(_kernel_with(recorder))

        await memory.delete(entry_id)

        action = recorder.seen[0]
        assert set(action.metadata.keys()) == {"entry", "current_count", "entry_id"}
        assert action.metadata["entry"]["content"] == "original content"
        assert action.metadata["entry"]["confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_governance_runs_before_hooks_and_archive(self, memory):
        entry_id = await memory.write(content="to delete", content_type="fact")
        call_order = []

        class _OrderTrackingGovernor(Governor):
            @property
            def name(self):
                return "OrderTracker"

            def evaluate(self, action):
                call_order.append("governance")
                return GovernanceResult(verdict=GovernanceVerdict.APPROVE, governor=self.name)

        memory.register_governance(_kernel_with(_OrderTrackingGovernor()))

        def _tracking_hook(entry):
            call_order.append("before_delete_hook")
            return entry

        memory._hooks.before_delete.append(_tracking_hook)

        await memory.delete(entry_id)

        assert call_order == ["governance", "before_delete_hook"]


# ── Regression: pre-existing write() event-emission bug, found this session ────

class TestWriteEventEmissionRegression:
    """Not part of K3.5.1's stated scope (write() was already governed by
    K3.5) -- but K3.5.1 copied write()'s reject/escalate event-construction
    pattern for update()/delete(), which surfaced a real, pre-existing,
    silently-swallowed bug: KnowledgeEvent has no `payload` field (the real
    field is `metadata`), so every K3.5 write()-reject/escalate event
    construction raised, was caught by the wrapping try/except, and never
    reached the archive -- `memory_write_rejected`/`memory_write_escalated`
    events (already listed as canonical in ADR-K3.5-01 and CURRENT_STATE.md)
    were never actually being persisted. Fixed in the same pass across all
    six occurrences (write's pre-existing two, update's and delete's new
    four) for consistency, since leaving write()'s broken while fixing only
    the new code would be an inconsistent, half-governed state. Also
    registered the four new K3.5.1 event-type strings in EVENT_TYPES;
    without that, KnowledgeEvent.__post_init__ silently downgrades any
    unrecognized event_type to "created", which would have caused this same
    class of event to exist in the archive under the wrong type -- a
    second, more subtle way this exact bug pattern could resurface.

    This class exists to catch a regression of that specific bug, not to
    re-test K3.5.1's own scope (covered above)."""

    @pytest.mark.asyncio
    async def test_write_reject_event_actually_persists(self, memory):
        memory.register_governance(_kernel_with(_AlwaysRejectGovernor("memory_write", reason="fixture reason")))

        result = await memory.write(content="should be rejected", content_type="fact")

        assert result == ""
        events = await memory._archive.query_events(event_type="memory_write_rejected")
        assert len(events) == 1, \
            "memory_write_rejected must actually reach the archive, not just log a warning"
        assert events[0].metadata["reason"] == "fixture reason"

    @pytest.mark.asyncio
    async def test_write_escalate_event_actually_persists(self, memory):
        memory.register_governance(_kernel_with(_AlwaysEscalateGovernor("memory_write", reason="fixture escalation")))

        result = await memory.write(content="should be escalated", content_type="fact")

        assert result == ""
        events = await memory._archive.query_events(event_type="memory_write_escalated")
        assert len(events) == 1
        assert events[0].metadata["reason"] == "fixture escalation"

class TestFullChainIntegration:
    @pytest.mark.asyncio
    async def test_update_flows_through_real_governance_kernel(self, memory):
        """Uses the actual GovernanceKernel with its default 7-governor
        chain (not a stub) -- confirms memory_update reaches MemoryGovernor
        and is approved (MemoryGovernor no-ops on non-memory_write actions
        by its own documented design)."""
        entry_id = await memory.write(content="original", content_type="fact", confidence=0.5)
        memory.register_governance(GovernanceKernel())

        ok = await memory.update(entry_id, {"confidence": 0.9})

        assert ok is True
        entry = await memory.read(entry_id)
        assert entry.confidence == 0.9

    @pytest.mark.asyncio
    async def test_delete_flows_through_real_governance_kernel(self, memory):
        entry_id = await memory.write(content="original", content_type="fact")
        memory.register_governance(GovernanceKernel())

        ok = await memory.delete(entry_id)

        assert ok is True
        assert await memory.read(entry_id) is None

    @pytest.mark.asyncio
    async def test_write_update_delete_all_governed_by_same_kernel_instance(self, memory):
        """End-to-end proof of the K3.5.1 invariant: one GovernanceKernel
        instance sees all three mutation types across a full lifecycle."""
        recorder = _RecordingApproveGovernor()
        memory.register_governance(_kernel_with(recorder))

        entry_id = await memory.write(content="v1", content_type="fact")
        await memory.update(entry_id, {"confidence": 0.9})
        await memory.delete(entry_id)

        action_types = [a.action_type for a in recorder.seen]
        assert action_types == ["memory_write", "memory_update", "memory_delete"]
