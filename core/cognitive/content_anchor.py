"""core/cognitive/content_anchor.py -- creative content-anchor detector (slice 1).

Architecture: ADR-KERNEL-07 (PROPOSED; D-5 resolved as Option C by Moncif,
2026-09-29). Study: docs/studies/OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md.

WHAT THIS IS -- AND IS NOT
--------------------------
A narrow experimental detector for ONE class of under-specification: an
open-ended creative-composition request that states only its *form* ("write a
1000 words story") and contains no content at all. It is the first vertical
slice toward intent sufficiency, NOT intent sufficiency. It cannot tell that
"write a 1000-word science-fiction story" still leaves premise, tone,
audience and setting open -- any single content token passes (fail-open by
design). It is named for the signal it measures so this heuristic is not
frozen as the canonical definition of sufficiency.

ARCHITECTURE (Option C -- K4.2's "no dedicated clarification gate" is kept)
---------------------------------------------------------------------------
    interpret -> detect (THIS MODULE: pure, non-governing) -> plan
      -> compile() -> existing OrchestrationGovernor at Plan Compilation
      -> ESCALATE -> clarification response

* This module OBSERVES; it never governs. It imports no governance code and
  makes no allow/deny decision. (Enforced by an architecture test.)
* Its result is carried through planning to compile(), where the existing
  OrchestrationGovernor applies a threshold to it alongside
  ClarificationPolicy, on the same "plan_compile" action but under its OWN
  metadata key (`content_anchor_score`, never `confidence`), so neither rule
  can fire on or swallow the other -- including ADR-K4.2-H-13's
  general_purpose_only exemption, which applies only to ClarificationPolicy.
* No new clarification gate and no new governance boundary exist.
* On ESCALATE the Orchestrator surfaces a detector-specific question paired
  with the concrete interpreted plan/intent K4.2 expects to be shown.

Cost (measured, ADR §10.2): plan() makes one unconditional decomposition
model call before compile(), so an intercepted request still pays that call;
what is avoided is execution/generation.

SCORE / ABSTENTION SEMANTICS
----------------------------
See ContentAnchorAssessment: `score` is a coarse presence indicator, NOT a
probability of sufficiency; `score is None` means the detector ABSTAINED
(out of scope) -- not "known sufficient".

SCOPE OF SLICE 1: detect -> ask -> stop. It does NOT preserve the task, merge
the user's answer, or re-evaluate. IntentLifecycle.CLARIFICATION_PENDING and
CLARIFIED remain unreached (ADR-KERNEL-07 D-3). No attempt state exists, so
no bounded-retry semantics are implemented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Sequence, Tuple

from core.events.event_stream import EventStream, get_event_stream
from core.observability.tracer import get_trace_id

_DETECTOR_ID = "CreativeContentAnchor"
DETECTOR_NAME = "creative_content_anchor"
DETECTOR_VERSION = "0"

# Metadata keys read by OrchestrationGovernor._evaluate_content_anchor_policy.
# Deliberately NOT "confidence": ClarificationPolicy is keyed on that name.
CONTENT_ANCHOR_SCORE_KEY = "content_anchor_score"
CONTENT_ANCHOR_THRESHOLD_KEY = "content_anchor_threshold"
CONTENT_ANCHOR_SCORE_THRESHOLD = 0.5

MISSING_SUBJECT = "subject_or_premise"


# ─────────────────────────────────────────────────────────────────────────
# Assessment type
# ─────────────────────────────────────────────────────────────────────────

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


def anchor_missing(assessment: Optional["ContentAnchorAssessment"]) -> bool:
    """True iff an in-scope assessment falls below the policy threshold.

    This is the SAME predicate OrchestrationGovernor applies to
    `content_anchor_score` (score < threshold), used by the caller to
    recognize that an ESCALATED compilation was caused by a missing anchor.
    Abstention (score None) is never "missing".
    """
    return (
        assessment is not None
        and assessment.in_scope
        and assessment.score is not None
        and assessment.score < CONTENT_ANCHOR_SCORE_THRESHOLD
    )


def governance_metadata(
    assessment: Optional["ContentAnchorAssessment"],
) -> Dict[str, Any]:
    """Metadata the Plan Compiler adds to its governance action.

    Empty for None or an abstaining assessment: an abstaining detector has
    nothing to contribute, so the governor rule stays inert.
    """
    if assessment is None or not assessment.in_scope or assessment.score is None:
        return {}
    return {
        CONTENT_ANCHOR_SCORE_KEY: assessment.score,
        CONTENT_ANCHOR_THRESHOLD_KEY: CONTENT_ANCHOR_SCORE_THRESHOLD,
    }


# ─────────────────────────────────────────────────────────────────────────
# Non-governing observation (pre-plan)
# ─────────────────────────────────────────────────────────────────────────

async def observe_creative_content_anchors(
    raw_text: str,
    *,
    goal_id: str = "",
    event_stream: Optional[EventStream] = None,
) -> "ContentAnchorAssessment":
    """Detect and record. Does NOT decide, block, or consult governance.

    Emits one `cognitive.content_anchor_observed` event so replay shows what
    the detector saw (including abstentions), then returns the assessment for
    the caller to carry to compile(). No raw request text is recorded.
    """
    event_stream = event_stream or get_event_stream()
    assessment = detect_creative_content_anchors(raw_text)
    await event_stream.append(
        event_type="cognitive.content_anchor_observed",
        source=_DETECTOR_ID,
        payload={
            "trace_id": get_trace_id(),
            "goal_id": goal_id,
            "detector": DETECTOR_NAME,
            "detector_version": DETECTOR_VERSION,
            "score": assessment.score,
            "in_scope": assessment.in_scope,
            "delegated": assessment.delegated,
            "artifact": assessment.artifact,
            "missing": list(assessment.missing),
            "abstained": not assessment.in_scope,
        },
    )
    return assessment


# ─────────────────────────────────────────────────────────────────────────
# Clarification response (post-ESCALATE) -- C-plus (DEBT-043, ADR-KERNEL-07 §10.5)
# ─────────────────────────────────────────────────────────────────────────
#
# K4.2 pairing is retained: a detector-specific question is surfaced ONLY together
# with (1) a truthful representation of the intent and (2) a genuine provisional
# plan.  If either cannot be produced, the response is the generic safe failure
# below -- never an unpaired question.  Nothing here calls a model, validates the
# quality of a planner step, or adds a governance decision: it only presents the
# data the detector and the planner already produced.

_MAX_STEPS_SHOWN = 3
_MAX_TEXT = 160

SAFE_FAILURE_MESSAGE = (
    "I couldn't form a reliable draft plan for this request. Please restate "
    "what you'd like me to create and include any details you already know."
)
FAILURE_NO_USABLE_INTENT = "no_usable_intent"
FAILURE_NO_USABLE_PLAN = "no_usable_plan"

_STEP_MARKER = re.compile(r"^\s*(?:\d{1,3}[.)]|[-*\u2022])\s+")
_DEGRADED_PLAN_WORD = "unspecified"   # planner._decompose's degrade placeholder
_SURPRISE_WAY_OUT = 'or say "surprise me" and I\'ll choose'  # backed by _DELEGATION


def _one_line(text: Any, limit: int = _MAX_TEXT) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "\u2026"


def _normalized(text: Any) -> str:
    return " ".join(str(text or "").casefold().split()).strip(" \t.,;:!?\"'")


def genuine_plan_steps(plan_steps: Sequence[Any], request_text: str = "") -> list:
    """The usable, displayable steps of a planner-produced plan, in plan order.

    Skipped: non-string, empty or whitespace-only entries; a leading list marker
    ("1.", "-", "*") is stripped so the display never shows "1. 2. step".
    Returns [] -- no genuine plan -- when the plan is the planner's degrade
    fallback: `planner._decompose` answers a failed or unparsable model call with
    ONE step that is the goal description itself (or "unspecified").  That step
    is the request echoed back, not a plan, and must not be presented as one.
    """
    steps = []
    for raw in plan_steps or ():
        if not isinstance(raw, str):
            continue
        text = _one_line(_STEP_MARKER.sub("", raw))
        if text:
            steps.append(text)
    if len(steps) == 1 and _normalized(steps[0]) in (_normalized(request_text), _DEGRADED_PLAN_WORD):
        return []
    return steps


def build_clarification_intent(assessment: Optional["ContentAnchorAssessment"]) -> Optional[str]:
    """What the detector actually established, stated plainly -- or None.

    The only intent data available here is the artifact kind the request names
    and the fact that it carries no subject/premise content.  The user's own
    words are deliberately NOT echoed as an "interpretation": by K4.2-H1 the
    goal description IS the raw request, so echoing it would present the request
    as if it were an independent reading of it.
    """
    if assessment is None or not getattr(assessment, "in_scope", False):
        return None
    kind = str(assessment.artifact or "").strip()
    if not kind:
        return None
    article = "an" if kind[:1].lower() in "aeiou" else "a"
    text = f"I understand this as a request for {article} {kind}."
    if MISSING_SUBJECT in (assessment.missing or ()):
        text += f" It doesn't say what the {kind} should be about."
    return text


_KIND_QUESTIONS = {
    "story": "What should the story be about? A short description, such as a subject, genre or tone, helps",
    "poem": "What should the poem be about? A subject, theme or mood helps",
    "essay": "Which topic or question should the essay address?",
    "song": "What should the song be about, or what mood should it have?",
    "joke": "Is there a topic you'd like the joke to be about?",
}


def build_clarification_question(assessment: "ContentAnchorAssessment") -> str:
    """Deterministic, artifact-appropriate question.  It presupposes no subject,
    genre or process, and promises nothing about the result.  Slice 1 is stateless,
    so it tells the user to resend the request with the detail (ADR-KERNEL-07 D-3)."""
    kind = str(getattr(assessment, "artifact", "") or "").strip() or "piece"
    ask = _KIND_QUESTIONS.get(kind, f"What should the {kind} be about?")
    if ask.endswith("?"):
        way_out = f" {_SURPRISE_WAY_OUT[0].upper()}{_SURPRISE_WAY_OUT[1:]}."
    else:
        way_out = f" \u2014 {_SURPRISE_WAY_OUT}."
    return f"{ask}{way_out} Please send your request again with that detail."


@dataclass(frozen=True)
class ClarificationRendering:
    """Result of rendering the clarification.  `paired` is True only when the
    intent statement, at least one genuine plan step and the detector-specific
    question are all present; otherwise `text` is SAFE_FAILURE_MESSAGE."""
    text: str
    paired: bool
    steps_shown: int = 0
    steps_total: int = 0
    failure_reason: Optional[str] = None


def render_clarification_response(
    assessment: Optional["ContentAnchorAssessment"],
    *,
    request_text: str = "",
    plan_steps: Sequence[Any] = (),
) -> ClarificationRendering:
    """Render the paired clarification, or the safe failure (never an unpaired question).

    `request_text` is used ONLY to recognize the planner's degrade fallback; it is
    never displayed.  Planner steps are shown as separate numbered lines, in plan
    order, at most _MAX_STEPS_SHOWN of them, labelled provisional.  The underlying
    execution plan is not modified; omitted steps are stated as omitted.
    """
    intent = build_clarification_intent(assessment)
    if intent is None:
        return ClarificationRendering(SAFE_FAILURE_MESSAGE, False, failure_reason=FAILURE_NO_USABLE_INTENT)
    steps = genuine_plan_steps(plan_steps, request_text)
    if not steps:
        return ClarificationRendering(SAFE_FAILURE_MESSAGE, False, failure_reason=FAILURE_NO_USABLE_PLAN)
    shown = steps[:_MAX_STEPS_SHOWN]
    notes = ["not checked or approved"]
    if MISSING_SUBJECT in (assessment.missing or ()):
        notes.append("not yet tailored to a subject")
    if len(steps) > len(shown):
        notes.append(f"first {len(shown)} of {len(steps)} steps")
    listing = "\n".join(f"{i}. {t}" for i, t in enumerate(shown, 1))
    text = "\n\n".join([
        intent,
        f"Provisional draft plan ({'; '.join(notes)}):\n{listing}",
        build_clarification_question(assessment),
    ])
    return ClarificationRendering(text, True, steps_shown=len(shown), steps_total=len(steps))


def build_clarification_response(
    assessment: Optional["ContentAnchorAssessment"],
    *,
    request_text: str = "",
    plan_steps: Sequence[Any] = (),
) -> str:
    """Text of `render_clarification_response` (kept for callers that need only the string)."""
    return render_clarification_response(assessment, request_text=request_text, plan_steps=plan_steps).text
