"""
Verification target identity: frozen snapshot vs. live target.

Architecture v3 Part 1 section 4: "the frozen, exact version of what was
evaluated (content hash, version, timestamp), distinct from the live/
current version of that same logical target." Mostly a naming exercise
per v3's own framing -- makes explicit what the fingerprint-based mutation
model (v2 section 6) was already implicitly doing, so Phase C has an
actual named type instead of an implied one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VerificationTargetFingerprint:
    """A content-addressed identity for one exact version of a target.

    Two fingerprints being equal means "this is provably the same content
    that was verified" -- not "this is the same logical target." A single
    logical target accumulates many fingerprints over its lifetime as it
    changes; this type identifies one of them, not the target's lineage.
    """
    content_hash: str
    version: str

    def __post_init__(self) -> None:
        if not self.content_hash:
            raise ValueError("VerificationTargetFingerprint.content_hash must be non-empty")
        if not self.version:
            raise ValueError("VerificationTargetFingerprint.version must be non-empty")

    def matches(self, other: "VerificationTargetFingerprint") -> bool:
        return self.content_hash == other.content_hash


@dataclass(frozen=True)
class VerificationTargetSnapshot:
    """The frozen, exact thing a verification actually ran against.

    Distinct from whatever the logical target (e.g. a WorkGraph node's
    current output) looks like NOW -- a snapshot is immutable by
    construction; the live target is not. A stale VerificationReceipt
    (receipt.py) is detected by comparing a fresh fingerprint of the live
    target against the snapshot's fingerprint (is_stale_against, below),
    not by re-running verification speculatively to find out.
    """
    target_id: str
    fingerprint: VerificationTargetFingerprint
    captured_at: datetime

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("VerificationTargetSnapshot.target_id must be non-empty")

    def is_stale_against(self, current_fingerprint: VerificationTargetFingerprint) -> bool:
        """True if the live target has moved on from what this snapshot captured."""
        return not self.fingerprint.matches(current_fingerprint)
