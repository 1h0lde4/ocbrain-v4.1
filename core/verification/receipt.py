"""
Immutable verification receipts with supersession lineage.

The immutability guarantee is enforced by @dataclass(frozen=True) plus
`superseded_by` returning a NEW object via dataclasses.replace rather
than mutating the original -- this is a real, checkable property, not
a docstring claim (see tests/test_verification_contracts.py).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Optional

from .identity import ReceiptId, VerificationId
from .verdict import VerificationResult


class Replayability(str, Enum):
    FULLY_REPLAYABLE = "fully_replayable"
    PARTIALLY_REPLAYABLE = "partially_replayable"
    NON_REPLAYABLE = "non_replayable"


@dataclass(frozen=True)
class VerificationReceipt:
    receipt_id: ReceiptId
    verification_id: VerificationId
    result: VerificationResult
    issued_at: datetime
    replayability: Replayability
    supersedes_receipt_id: Optional[ReceiptId] = None
    superseded_by_receipt_id: Optional[ReceiptId] = None

    def superseded_by(self, new_receipt_id: ReceiptId) -> "VerificationReceipt":
        """Returns a NEW receipt object; the original instance is
        never touched. That is the actual enforcement mechanism for
        'historical receipts are immutable' -- not a comment, a
        structural fact about frozen dataclasses."""
        return replace(self, superseded_by_receipt_id=new_receipt_id)
