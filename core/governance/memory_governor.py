import logging
from typing import Dict, Any, List, Optional

from core.governance.governance_kernel import (
    Governor,
    GovernanceAction,
    GovernanceResult,
    GovernanceVerdict,
)

logger = logging.getLogger("ocbrain.governance.memory")

class MemoryGovernor(Governor):
    """
    Enforces safety, quality, and growth limits on the cognitive memory system.

    K2.4 reconciliation (PI §6.1 Required Governors; KERNEL_ARCHITECTURE_v1.0.md
    §14.3 "MemoryGovernor: exists, disconnected — interface incompatible"):
    this class now extends Governor and exposes the standard evaluate()
    entry point alongside its pre-existing, unmodified API
    (validate_ingestion / check_growth_limits / detect_contradiction /
    quarantine_unstable). The module-level singleton below is preserved
    exactly as before; GovernanceKernel registers its own separate
    instance (matching how RecursionGovernor / BudgetGovernor /
    EvolutionGovernor are registered) rather than reusing the singleton,
    so this is no longer singleton-only behavior.
    """

    name = "MemoryGovernor"

    def __init__(self, max_entries: int = 5000, quality_threshold: float = 0.6):
        self.max_entries = max_entries
        self.quality_threshold = quality_threshold
        self.stats = {
            "quarantined_count": 0,
            "rejected_count": 0,
            "consolidation_runs": 0
        }

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        """Evaluate a memory-related action via the standard Governor interface.

        Wraps the pre-existing validate_ingestion() / check_growth_limits()
        checks (unchanged, preserved below) behind evaluate(), so this
        governor participates in the same GovernanceKernel evaluation
        chain as every other governor (PI §6.1: "No worker may bypass
        governors").

        Only action_type == "memory_write" is evaluated; every other
        action_type is approved unconditionally, since memory-content
        validation is not meaningful for e.g. a general worker-execution
        authorization check.

        Scope note (documented explicitly, not left implicit): no current
        call site in the codebase constructs a GovernanceAction with
        action_type="memory_write" — UnifiedMemory.write() does not yet
        call evaluate_action(). Wiring that call site is Memory Runtime
        work, out of scope for K2.4 under this session's Architecture
        Freeze rule (governance components only). This method is fully
        reachable and tested via direct evaluate() calls today; it has no
        effect on production traffic until that future call site exists.
        Tracked as technical debt in the K2.4 session report.

        Args:
            action: The action to evaluate.

        Returns:
            GovernanceResult with verdict, reason, and governor name.
        """
        if action.action_type != "memory_write":
            return GovernanceResult(
                verdict=GovernanceVerdict.APPROVE, governor=self.name,
            )

        entry: Optional[Dict[str, Any]] = action.metadata.get("entry")
        if entry is None:
            # No entry payload supplied — nothing to validate against.
            # Approve rather than reject on missing data, matching
            # BudgetGovernor's established permissive-on-absence pattern.
            return GovernanceResult(
                verdict=GovernanceVerdict.APPROVE, governor=self.name,
            )

        if not self.validate_ingestion(entry):
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason="Memory entry failed quality/content validation",
                governor=self.name,
            )

        current_count = action.metadata.get("current_count")
        if current_count is not None and not self.check_growth_limits(int(current_count)):
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECT,
                reason=f"Memory capacity reached ({current_count}/{self.max_entries})",
                governor=self.name,
            )

        return GovernanceResult(
            verdict=GovernanceVerdict.APPROVE, governor=self.name,
        )

    def validate_ingestion(self, entry: Dict[str, Any]) -> bool:
        """
        Checks if a new memory entry meets the quality floor.
        """
        confidence = entry.get("confidence", 0.0)
        if confidence < self.quality_threshold:
            logger.warning(f"[MemoryGovernor] Entry rejected: Confidence {confidence} below threshold {self.quality_threshold}")
            self.stats["rejected_count"] += 1
            return False
        
        # Check for empty content
        if not entry.get("fact") and not entry.get("content"):
            return False
            
        return True

    def check_growth_limits(self, current_count: int) -> bool:
        """
        Returns True if the system can accept more memories.
        """
        if current_count >= self.max_entries:
            logger.error(f"[MemoryGovernor] Memory capacity reached ({current_count}/{self.max_entries})")
            return False
        return True

    def detect_contradiction(self, new_fact: str, existing_memories: List[Dict[str, Any]]) -> bool:
        """
        Placeholder for contradiction detection logic.
        Will use semantic similarity to find potential conflicts.
        """
        # Logic to be expanded in Phase 5
        return False

    def quarantine_unstable(self, entry: Dict[str, Any]):
        """
        Moves high-risk or low-confidence memories to a quarantine state.
        """
        entry["validation_state"] = "quarantined"
        self.stats["quarantined_count"] += 1
        logger.info(f"[MemoryGovernor] Memory {entry.get('id')} quarantined for review.")

# Global singleton
memory_governor = MemoryGovernor()
