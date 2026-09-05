"""
Retention policies: Evidence / Receipt / Source, kept independent.

Architecture v3 Part 1 section 6: three SEPARATE policies, not layers of
one shared policy. Evidence can be pruned for storage or privacy reasons
(v2 section 44, minimum sufficient evidence) while its receipt remains.
The three classes below are deliberately near-identical in shape and kept
as distinct types anyway (rather than one parametrized class) so a
caller cannot accidentally pass one kind of retention policy where
another was meant -- the whole point of "kept separate" is a type-level
guarantee, not just a naming convention.

Explicit consequence chain, per v3: evidence expires -> the historical
receipt still stands as the record of what was concluded -> but current
replayability degrades (v2 section 27) -> exact re-verification of that
specific claim may require gathering evidence again from scratch, not
resuming from the old record. A receipt outliving its evidence is
therefore the expected, common case -- not a bug to guard against.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RetentionRule(str, Enum):
    """Shared vocabulary only -- each *Retention type below applies this independently."""
    RETAIN_INDEFINITELY = "retain_indefinitely"
    RETAIN_UNTIL_SUPERSEDED = "retain_until_superseded"
    RETAIN_FOR_DURATION = "retain_for_duration"
    PRUNE_ELIGIBLE_IMMEDIATELY = "prune_eligible_immediately"


def _validate_retention(rule: RetentionRule, retention_days: Optional[int], type_name: str) -> None:
    if rule == RetentionRule.RETAIN_FOR_DURATION and retention_days is None:
        raise ValueError(f"{type_name} with RETAIN_FOR_DURATION requires retention_days")
    if retention_days is not None and retention_days <= 0:
        raise ValueError(f"{type_name}.retention_days must be positive, got {retention_days}")


@dataclass(frozen=True)
class EvidenceRetention:
    """Governs EvidenceItem lifetime (evidence.py) -- independent of ReceiptRetention."""
    rule: RetentionRule
    retention_days: Optional[int] = None

    def __post_init__(self) -> None:
        _validate_retention(self.rule, self.retention_days, "EvidenceRetention")


@dataclass(frozen=True)
class ReceiptRetention:
    """Governs VerificationReceipt lifetime (receipt.py) -- independent of EvidenceRetention."""
    rule: RetentionRule
    retention_days: Optional[int] = None

    def __post_init__(self) -> None:
        _validate_retention(self.rule, self.retention_days, "ReceiptRetention")


@dataclass(frozen=True)
class SourceRetention:
    """Governs how long an EvidenceSource's own backing material stays accessible.

    Distinct from EvidenceRetention: an EvidenceItem can remain (as a
    recorded observation) after the SOURCE it was drawn from is no longer
    itself retrievable -- e.g. a quoted line from a log file that log
    rotation has since deleted. The EvidenceItem does not become invalid;
    it becomes unable to be freshly re-inspected.
    """
    rule: RetentionRule
    retention_days: Optional[int] = None

    def __post_init__(self) -> None:
        _validate_retention(self.rule, self.retention_days, "SourceRetention")
