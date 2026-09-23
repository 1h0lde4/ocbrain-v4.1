"""
Observation / Interpretation (architecture v1 §12, mission §7.8, §33,
Phase 2 -- epistemic spine).

Observation -> Interpretation -> Claim (claim.py) is a distinct chain
from Observation -> Evidence (evidence.py). A semantic reading of what
was observed must never be recorded as if it were the raw observation
itself -- that is exactly the failure mode mission §7.8 names: "A
semantic interpretation must not masquerade as raw observation."

ObservationAuthority (epistemic.py) already answers "what source
established this" for a completed VerificationAssurance -- a summary
judgment made after assembling a whole verification. This module
answers a narrower, earlier question: what was actually captured, in
what form, and -- kept separate on purpose -- what is it taken to mean.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .epistemic import ObservationAuthority
from .identity import ObservationId


class ObservationForm(str, Enum):
    """What kind of raw thing was captured. Orthogonal to
    ObservationAuthority (who/what established it) -- a filesystem
    check and a human report can both yield a BOOLEAN observation."""
    TEXTUAL = "textual"
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    STRUCTURED = "structured"
    BINARY_PRESENCE = "binary_presence"  # e.g. "the file exists" -- presence only, no content captured


@dataclass(frozen=True)
class Observation:
    """
    A raw capture, not yet a claim about what it means. Deliberately
    thin: content_summary holds only what was captured, never an
    inference drawn from it. No execution/attempt-id binding yet,
    matching evidence.py's EvidenceItem at this same phase -- that
    wiring is Phase 13 (runtime-compatible integration), not Phase 2.
    """
    observation_id: ObservationId
    authority: ObservationAuthority
    form: ObservationForm
    content_summary: str
    observed_at: datetime
    locator: str  # exact locator: file path, event id, span, query, etc. -- never "somewhere in the output"

    def __post_init__(self) -> None:
        if not self.content_summary or not self.content_summary.strip():
            raise ValueError("Observation requires a non-empty content_summary")
        if not self.locator or not self.locator.strip():
            raise ValueError("Observation requires a non-empty locator")


@dataclass(frozen=True)
class Interpretation:
    """
    A semantic reading of an Observation -- what it is taken to mean.
    Structurally separate from Observation on purpose: meaning can be
    wrong even when the underlying Observation is accurate (mission
    §7.8), and folding the two together would make that error
    invisible. An Observation may have zero, one, or several competing
    Interpretations; this type does not resolve conflicts between them
    -- that is an assessment-layer concern (Phase 4), not an epistemic
    one.
    """
    observation_id: ObservationId
    meaning: str
    interpreted_by: str  # e.g. "deterministic_rule", "model:claude-sonnet-5", "human:<id>"

    def __post_init__(self) -> None:
        if not self.meaning or not self.meaning.strip():
            raise ValueError("Interpretation requires a non-empty meaning")
        if not self.interpreted_by or not self.interpreted_by.strip():
            raise ValueError("Interpretation requires a non-empty interpreted_by")
