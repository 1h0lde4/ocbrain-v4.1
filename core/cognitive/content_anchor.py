"""core/cognitive/sufficiency.py — Intent Sufficiency Gate, slice 1.

Architecture: ADR-KERNEL-07 (PROPOSED). Study:
docs/studies/OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md.

Question this module answers -- and the one it does NOT
--------------------------------------------------------
``ClarificationPolicy`` (planner.py / OrchestrationGovernor) asks "am I
unsure which *capability* to use?". This module asks a different question:
"does the request contain enough *content* to produce something the user
would recognize as what they asked for?". The two are deliberately kept
apart: this gate uses its own governance metadata key
(``sufficiency_score``, never ``confidence``) so ClarificationPolicy -- and
its ADR-K4.2-H-13 general-purpose exemption -- can neither fire on nor
swallow a sufficiency decision.

Placement
---------
Called by ``Orchestrator.handle()`` after ``interpret_request()`` and
before ``plan()``. It is a *new module* on purpose: DRIFT-05/DRIFT-10 forbid
governance calls inside ``intent.py``/``planner.py`` and DRIFT-11 freezes the
three entrypoint signatures. Governance is invoked here exactly as
``compiler.py`` and ``learning.py`` already do it (GovernanceAction ->
``GovernanceKernel.evaluate_action()``); no new governor, gate or rule
registry is introduced.

Signal (deterministic, no model call, replayable)
-------------------------------------------------
Scope is intentionally narrow: open-ended creative composition only
(a generative verb plus an artifact noun such as story/poem/essay). For
those requests the assessment counts *content-bearing tokens* -- tokens left
after removing the form specification (verb, artifact noun, length
words/numbers), pronouns, articles and generic filler. Zero content tokens
means the request fixes only the *form* ("write a 1000 words story"), so
subject/premise is undetermined. Everything outside that scope is reported
``in_scope=False`` and treated as sufficient (fail-open): the gate must not
ask questions it has no evidence are needed.

Known limits (documented, not hidden): the lexical signal is coarse. Any
single content token passes (fail-open), so it under-triggers on e.g.
"write a funny story"; it has only been exercised on constructed cases, not
a real request corpus. It is a replaceable signal behind a stable governance
shape (study Gate 3).

State: none. Slice 1 is stateless per request -- no pending-clarification
store exists (ADR-KERNEL-07 D-3). ``attempt`` is a caller-supplied value so
the governor-level bound is real and testable even though the current caller
always passes 0.
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

_SUFFICIENCY_ID = "IntentSufficiency"

# Metadata key the governor rule reads. Deliberately NOT "confidence": the
# ClarificationPolicy rule is keyed on that name (ADR-K4.2-H-13).
SUFFICIENCY_SCORE_KEY = "sufficiency_score"
SUFFICIENCY_ACTION_TYPE = "intent_sufficiency"

MISSING_SUBJECT = "subject_or_premise"


# ─────────────────────────────────────────────────────────────────────────
# Policy + result types
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SufficiencyPolicy:
    """Policy data for the sufficiency gate.

    Same two parameters -- and nothing more -- as ClarificationPolicy
    (planner.py): a threshold and a bound on repetition. ``score`` below
    ``score_threshold`` escalates while ``attempt < max_escalations``;
    at the bound the case is stalled (rejected) rather than re-escalated.
    """

    score_threshold: float = 0.5
    max_escalations: int = 2


@dataclass(frozen=True)
class SufficiencyAssessment:
    """Pure result of assess_sufficiency(). No governance, no I/O."""

    score: float                      # in [0, 1]; 1.0 when out of scope
    in_scope: bool                    # False -> not a request this gate judges
    delegated: bool                   # user explicitly delegated the choice
    artifact: Optional[str]           # canonical artifact kind, when in scope
    missing: Tuple[str, ...]          # e.g. ("subject_or_premise",)
    content_token_count: int


class SufficiencyStatus(str, Enum):
    SUFFICIENT = "sufficient"
    CLARIFICATION_REQUIRED = "clarification_required"
    STALLED = "stalled"                       # bound reached; do not re-ask blindly
    GOVERNANCE_BLOCKED = "governance_blocked"  # non-clarification denial


@dataclass(frozen=True)
class SufficiencyResult:
    status: SufficiencyStatus
    assessment: SufficiencyAssessment
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

def assess_sufficiency(raw_text: str) -> SufficiencyAssessment:
    """Deterministic, side-effect-free sufficiency assessment.

    Fail-open by construction: anything not recognized as an open-ended
    creative-composition request is ``in_scope=False`` with score 1.0.
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
        return SufficiencyAssessment(
            score=1.0, in_scope=False, delegated=False, artifact=None,
            missing=(), content_token_count=0,
        )

    if _DELEGATION.search(text):
        return SufficiencyAssessment(
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
    return SufficiencyAssessment(
        score=score, in_scope=True, delegated=False, artifact=artifact,
        missing=missing, content_token_count=count,
    )


def build_clarification_question(assessment: SufficiencyAssessment) -> str:
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

async def evaluate_intent_sufficiency(
    raw_text: str,
    *,
    goal_id: str = "",
    policy: Optional[SufficiencyPolicy] = None,
    attempt: int = 0,
    event_stream: Optional[EventStream] = None,
    governance: Optional[GovernanceKernel] = None,
) -> SufficiencyResult:
    """Assess the request, route the decision through governance, emit one event.

    The decision is governance's, not this function's: the assessment supplies
    ``sufficiency_score`` and the policy parameters as metadata, and
    OrchestrationGovernor returns APPROVE / ESCALATE / REJECT (PI LAW 1).
    """
    event_stream = event_stream or get_event_stream()
    governance = governance or get_governance_kernel()
    policy = policy or SufficiencyPolicy()
    trace_id = get_trace_id()

    assessment = assess_sufficiency(raw_text)

    metadata: Dict[str, Any] = {
        "goal_id": goal_id,
        SUFFICIENCY_SCORE_KEY: assessment.score,
        "sufficiency_threshold": policy.score_threshold,
        "sufficiency_attempt": attempt,
        "sufficiency_max_escalations": policy.max_escalations,
        "in_scope": assessment.in_scope,
        "delegated": assessment.delegated,
    }
    action = GovernanceAction(
        action_type=SUFFICIENCY_ACTION_TYPE,
        worker_id=_SUFFICIENCY_ID,
        description=(
            f"Assess intent sufficiency for goal {goal_id or '<unassigned>'}"
        ),
        metadata=metadata,
    )
    gov_result = governance.evaluate_action(action)

    if gov_result.verdict == GovernanceVerdict.APPROVE:
        status = SufficiencyStatus.SUFFICIENT
    elif gov_result.governor == "OrchestrationGovernor":
        status = (
            SufficiencyStatus.STALLED
            if gov_result.verdict == GovernanceVerdict.REJECT
            else SufficiencyStatus.CLARIFICATION_REQUIRED
        )
    else:
        # Some other governor denied this action. That is not a statement
        # about the request's sufficiency, so never dress it up as a question.
        status = SufficiencyStatus.GOVERNANCE_BLOCKED

    await event_stream.append(
        event_type="cognitive.intent_sufficiency_evaluated",
        source=_SUFFICIENCY_ID,
        payload={
            "trace_id": trace_id,
            "goal_id": goal_id,
            "score": assessment.score,
            "in_scope": assessment.in_scope,
            "delegated": assessment.delegated,
            "artifact": assessment.artifact,
            "missing": list(assessment.missing),
            "verdict": gov_result.verdict.value,
            "status": status.value,
            "governor": gov_result.governor,
            "attempt": attempt,
        },
    )

    question = (
        build_clarification_question(assessment)
        if status in (SufficiencyStatus.CLARIFICATION_REQUIRED,
                      SufficiencyStatus.STALLED)
        else None
    )
    return SufficiencyResult(
        status=status,
        assessment=assessment,
        governance_result=gov_result,
        question=question,
    )
