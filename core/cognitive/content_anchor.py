"""core/cognitive/content_anchor.py -- creative content-anchor detector (slice 1).

Architecture: ADR-KERNEL-07 (PROPOSED). Study:
docs/studies/OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md.

WHAT THIS IS -- AND IS NOT
--------------------------
This is a narrow experimental detector for ONE class of under-specification:
an open-ended creative-composition request that states only its *form*
("write a 1000 words story") and contains no content at all. It is the first
vertical slice toward intent sufficiency, NOT intent sufficiency. The study's
definition of material sufficiency is "would a different plausible resolution
of the unknown materially change the output?"; this detector does not
implement that. It cannot tell that "write a 1000-word science-fiction story"
still leaves premise, tone, audience and setting open -- any single content
token passes (fail-open by design). It is named for the signal it actually
measures so this heuristic is not frozen as the canonical definition.

`ClarificationPolicy` (planner.py / OrchestrationGovernor) asks a different
question ("unsure which *capability*?"). The two are kept apart by metadata
key: this module uses `content_anchor_score`, never `confidence`, so
ClarificationPolicy -- and ADR-K4.2-H-13's general-purpose exemption -- can
neither fire on nor swallow this decision.

Placement and ownership
-----------------------
Called by `Orchestrator.handle()` after `interpret_request()` and before
`plan()`. This detector consumes only the raw request text; it does NOT read
Intent/Goal state (goal_id is a correlation id). Semantic ownership sits here
(cognitive layer): this module decides what the score means. The governor
only applies a threshold, the same mechanism role it plays for
ClarificationPolicy. DRIFT-11 makes Orchestrator the sole authorized caller
of the cognitive entrypoints; interpret_request() is not modified.

Signal (deterministic, no model call, replayable)
-------------------------------------------------
Scope: generative verb + artifact noun (story/poem/essay/...). Everything
else is `in_scope=False` -> anchored (fail-open). In scope, the detector
counts content-bearing tokens left after removing form specification (verb,
artifact noun, numbers, length words), pronouns, articles and filler.

SCOPE OF SLICE 1: detect -> ask -> stop. It does NOT preserve the task, merge
the user's answer, or re-evaluate. IntentLifecycle.CLARIFICATION_PENDING and
CLARIFIED remain unreached; their existence as enum values does not mean a
clarification lifecycle is live.

State: none. Slice 1 keeps no attempt state across turns (ADR-KERNEL-07 D-3),
therefore it implements NO bounded-retry semantics: a resubmitted request is
a fresh request. This validates detection and short-circuiting only -- not a
multi-turn clarification lifecycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Tuple

from core.events.event_stream import EventStream, get_event_stream
from core.governance.governance_kernel import (
    GovernanceAction,
    GovernanceKernel,
    GovernanceResult,
    GovernanceVerdict,
    get_governance_kernel,
)
from core.observability.tracer import get_trace_id

_DETECTOR_ID = "CreativeContentAnchor"
DETECTOR_NAME = "creative_content_anchor"
DETECTOR_VERSION = "0"

# Metadata key the governor rule reads. Deliberately NOT "confidence": the
# ClarificationPolicy rule is keyed on that name (ADR-K4.2-H-13).
CONTENT_ANCHOR_SCORE_KEY = "content_anchor_score"
CONTENT_ANCHOR_ACTION_TYPE = "creative_content_anchor_check"

MISSING_SUBJECT = "subject_or_premise"


# ─────────────────────────────────────────────────────────────────────────
# Policy + result types
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ContentAnchorPolicy:
    """Threshold only. No max_escalations: slice 1 has no attempt carrier, so
    a bound would be unreachable governance logic (ADR-KERNEL-07 D-3)."""

    score_threshold: float = 0.5


@dataclass(frozen=True)
class ContentAnchorAssessment:
    """Pure result of detect_creative_content_anchors(). No governance, no I/O.

    MEANING OF ``score`` -- read this before using it. It is a coarse,
    detector-specific *presence indicator* for content-bearing tokens in the
    request text: min(1, content_token_count / 2). It is NOT a probability that
    the request is sufficient, NOT a measure of how well-specified it is, and
    NOT comparable across detectors or detector versions (the emitted event
    carries detector name + version for exactly that reason). 1.0 means only
    "at least two content tokens, or the user delegated the choice". A future
    intent-sufficiency model must not consume this number as if it were one.

    ``score is None`` means this detector ABSTAINED: the request is outside
    its scope, so no judgment was made. That is different from "known to be
    sufficient" and must never be treated as such.
    """

    score: Optional[float]            # in [0, 1]; None => this detector ABSTAINED (out of scope)
    in_scope: bool                    # False -> not a request this gate judges
    delegated: bool                   # user explicitly delegated the choice
    artifact: Optional[str]           # canonical artifact kind, when in scope
    missing: Tuple[str, ...]          # e.g. ("subject_or_premise",)
    content_token_count: int


class ContentAnchorStatus(str, Enum):
    ANCHORED = "anchored"                      # in scope, has an anchor (or delegated)
    ABSTAINED = "abstained"                    # out of scope: NO judgment made, not "sufficient"
    ANCHOR_MISSING = "anchor_missing"          # ask the user
    GOVERNANCE_BLOCKED = "governance_blocked"  # non-clarification denial


@dataclass(frozen=True)
class ContentAnchorResult:
    status: ContentAnchorStatus
    assessment: ContentAnchorAssessment
    governance_result: Optional[GovernanceResult] = None
    question: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────
# Lexicon (explicit, small, auditable)
# ─────────────────────────────────────────────────────────────────────────

_GENERATIVE_VERBS: FrozenSet[str] = frozenset({
    "write", "compose", "draft", "create", "generate", "make", "pen",
    "tell", "craft", "produce", "give",
})

# surface token -> canonical artifact kind
_ARTIFACTS: Dict[str, str] = {
    "story": "story", "stories": "story", "tale": "story", "fable": "story",
    "novel": "story",
    "poem": "poem", "poetry": "poem", "haiku": "poem", "limerick": "poem",
    "song": "song", "lyrics": "song",
    "essay": "essay",
    "joke": "joke",
}

_DELEGATION = re.compile(
    r"\b("
    r"surprise me|your choice|your call|up to you|whatever you (?:like|want|prefer)|"
    r"anything you (?:like|want)|any (?:topic|subject|genre|theme)|"
    r"use your (?:judg(?:e)?ment|imagination|discretion)|"
    r"pick (?:one|something|a topic)|you (?:choose|decide|pick)|"
    r"write anything|something random|random"
    r")\b",
    re.IGNORECASE,
)

# Form-specification / grammatical filler: tokens that carry no *content*.
_FILLER: FrozenSet[str] = frozenset("""
a an the and or but so as at by from in on of to for with without into onto
up out off over under about around approximately roughly approx
i me my mine we us our you your yours he she it they them this that these those
is are am be been being was were do does did have has had get got let lets
can could would should will shall may might must want need like wish hope
please pls kindly thanks thank ok okay hi hello hey now here there
some any another one another piece kind sort type something anything
good great nice cool interesting best amazing awesome decent new original
little quick lovely really very just also then than more less most least fewer
exactly minimum maximum min max at
word words page pages paragraph paragraphs sentence sentences line lines
short long brief longer shorter
zero two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty
fifty sixty seventy eighty ninety hundred thousand million
""".split())

_TOKEN = re.compile(r"[a-z0-9']+")
_NUMERIC = re.compile(r"\d+\w*")


# ─────────────────────────────────────────────────────────────────────────
# Pure assessment
# ─────────────────────────────────────────────────────────────────────────

def detect_creative_content_anchors(raw_text: str) -> ContentAnchorAssessment:
    """Deterministic, side-effect-free content-anchor detection.

    Anything not recognized as an open-ended creative-composition request is
    ``in_scope=False`` with ``score=None``: the detector ABSTAINS (makes no
    judgment). Callers proceed, but abstention is not a sufficiency verdict.
    """
    text = raw_text or ""
    tokens = _TOKEN.findall(text.lower())

    artifact: Optional[str] = None
    for tok in tokens:
        if tok in _ARTIFACTS:
            artifact = _ARTIFACTS[tok]
            break
    has_verb = any(tok in _GENERATIVE_VERBS for tok in tokens)

    if artifact is None or not has_verb:
        return ContentAnchorAssessment(
            score=None, in_scope=False, delegated=False, artifact=None,
            missing=(), content_token_count=0,
        )

    if _DELEGATION.search(text):
        return ContentAnchorAssessment(
            score=1.0, in_scope=True, delegated=True, artifact=artifact,
            missing=(), content_token_count=0,
        )

    content = [
        tok for tok in tokens
        if tok not in _FILLER
        and tok not in _GENERATIVE_VERBS
        and tok not in _ARTIFACTS
        and not _NUMERIC.fullmatch(tok)
    ]
    count = len(content)
    # Graded so the threshold is meaningful: 0 content tokens -> 0.0,
    # one -> 0.5, two or more -> 1.0. With the default 0.5 threshold a
    # single content token is enough (deliberately fail-open).
    score = min(1.0, count / 2.0)
    missing: Tuple[str, ...] = (MISSING_SUBJECT,) if count == 0 else ()
    return ContentAnchorAssessment(
        score=score, in_scope=True, delegated=False, artifact=artifact,
        missing=missing, content_token_count=count,
    )


def build_clarification_question(assessment: ContentAnchorAssessment) -> str:
    """Deterministic, specific question. Slice 1 is stateless, so it tells
    the user to resend the request with details (ADR-KERNEL-07 D-3)."""
    kind = assessment.artifact or "piece"
    return (
        f"Before I write this {kind}, what should it be about? A subject, "
        f"genre, or tone is enough (for example: a noir mystery, a cozy "
        f"fantasy, a funny office comedy) — or say \"surprise me\" and I'll "
        f"choose. Please send your request again with those details."
    )


# ─────────────────────────────────────────────────────────────────────────
# Governance-evaluated gate
# ─────────────────────────────────────────────────────────────────────────

async def evaluate_creative_content_anchors(
    raw_text: str,
    *,
    goal_id: str = "",
    policy: Optional[ContentAnchorPolicy] = None,
    event_stream: Optional[EventStream] = None,
    governance: Optional[GovernanceKernel] = None,
) -> ContentAnchorResult:
    """Detect, apply the policy through governance, emit one event.

    Ownership: the detector (this module) decides what the score means; the
    OrchestrationGovernor only applies the threshold and returns
    APPROVE / ESCALATE. Out-of-scope requests ABSTAIN (no governance call).
    Stateless: no attempt count is read or kept.
    """
    event_stream = event_stream or get_event_stream()
    governance = governance or get_governance_kernel()
    policy = policy or ContentAnchorPolicy()
    trace_id = get_trace_id()

    assessment = detect_creative_content_anchors(raw_text)

    if not assessment.in_scope:
        # Abstain: nothing to decide, so no governance action is fabricated.
        # An event is still emitted so replay shows the detector ran and
        # declined (Law 2), without claiming the request is sufficient.
        await event_stream.append(
            event_type="cognitive.content_anchor_evaluated",
            source=_DETECTOR_ID,
            payload={
                "trace_id": trace_id,
                "goal_id": goal_id,
                "detector": DETECTOR_NAME,
                "detector_version": DETECTOR_VERSION,
                "score": None,
                "in_scope": False,
                "delegated": False,
                "artifact": None,
                "missing": [],
                "verdict": None,
                "status": ContentAnchorStatus.ABSTAINED.value,
                "governor": None,
            },
        )
        return ContentAnchorResult(
            status=ContentAnchorStatus.ABSTAINED, assessment=assessment)

    action = GovernanceAction(
        action_type=CONTENT_ANCHOR_ACTION_TYPE,
        worker_id=_DETECTOR_ID,
        description=(
            f"Creative content-anchor check for goal {goal_id or '<unassigned>'}"
        ),
        metadata={
            "goal_id": goal_id,
            CONTENT_ANCHOR_SCORE_KEY: assessment.score,
            "content_anchor_threshold": policy.score_threshold,
            "in_scope": assessment.in_scope,
            "delegated": assessment.delegated,
        },
    )
    gov_result = governance.evaluate_action(action)

    if gov_result.verdict == GovernanceVerdict.APPROVE:
        status = ContentAnchorStatus.ANCHORED
    elif (gov_result.governor == "OrchestrationGovernor"
          and gov_result.verdict == GovernanceVerdict.ESCALATE):
        status = ContentAnchorStatus.ANCHOR_MISSING
    else:
        # Another governor (or an unexpected verdict) denied this action. That
        # is not a statement about the request's content, so never dress it up
        # as a clarifying question.
        status = ContentAnchorStatus.GOVERNANCE_BLOCKED

    await event_stream.append(
        event_type="cognitive.content_anchor_evaluated",
        source=_DETECTOR_ID,
        payload={
            "trace_id": trace_id,
            "goal_id": goal_id,
            "detector": DETECTOR_NAME,
            "detector_version": DETECTOR_VERSION,
            "score": assessment.score,
            "in_scope": assessment.in_scope,
            "delegated": assessment.delegated,
            "artifact": assessment.artifact,
            "missing": list(assessment.missing),
            "verdict": gov_result.verdict.value,
            "status": status.value,
            "governor": gov_result.governor,
        },
    )

    return ContentAnchorResult(
        status=status,
        assessment=assessment,
        governance_result=gov_result,
        question=(build_clarification_question(assessment)
                  if status == ContentAnchorStatus.ANCHOR_MISSING else None),
    )
