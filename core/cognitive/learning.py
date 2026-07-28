"""
core/cognitive/learning.py — K4.2.6 Shared ValidationGate + Learning Wiring.

Architecture:
    OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md §6
    (Learning Architecture), §7 (Cognitive Memory), §8 (Evolution), §11
    (Event Integration), §12 (Data Contracts), §13 (State Machines), §15
    (K4.2.6 roadmap entry), §16 (Final Validation item 1).

Packet:
    Packet 04 — K4.2.6 Shared ValidationGate + Learning Wiring.

Scope:
    K4.2 §6 / §16 item 1: one shared ValidationGate function, parameterized
    by content-domain, used by all three promotion paths (Skill, Intent
    Ontology, User Cognitive Model) through a single code path — the
    duplication risk §16 names as the primary thing this packet must
    close.
    K4.2 §12: LearningRecord, CognitiveDecision data contracts.
    K4.2 §11: cognitive.pattern_learned (Learning tier), cognitive.
    ontology_evolved (Evolution tier) events.
    K4.2 §13: Learning lifecycle — observed -> accumulated -> candidate
    -> gated -> [promoted | rejected].
    K4.2 §8: tier-conditional governance — Learning is routine; Adaptation
    requires strict held-out improvement; Evolution additionally requires
    EvolutionGovernor.SELF_MODIFYING_ACTIONS evaluation and is "never
    automatic."

Boundary (K4 §1, Evolution Directive):
    This module provides the *shared gating policy* three promotion paths
    call into. It does not implement the domain-specific systems that
    would call it: no Skill Runtime/registry, no Intent Ontology storage,
    no User Cognitive Model projection. Domain-specific held-out scoring
    (how good is this candidate, in domain-specific terms) is the
    caller's responsibility; this module owns only the shared
    accept/reject/escalate policy applied uniformly once a score exists.

Explicitly NOT in scope:
    - User Cognitive Model projection/read path (Packet 05 / K4.2.7).
    - A genuine Skill Runtime or skill-creation pipeline (no such system
      exists in this codebase; see Gap note below).
    - A HITL approval-queue workflow. Evolution-tier candidates that
      clear this gate's own checks are escalated to GovernanceKernel per
      K4.2 §8's "never automatic" and go no further within this module.
      `hitl_approved` is the single, explicit seam a future approval
      surface would use to signal that a human already approved this
      exact candidate; no code path in this module sets it to True on a
      caller's behalf, and no approval-tracking/queue/UI is built here.

Gap note (documented per this project's established precedent — Packets
01-03 each found and recorded architecture-vs-repository gaps rather than
silently inventing around them; see k4_2_3/4/5_completion_report.md):
    K4.2 §15's K4.2.6 roadmap entry names "existing v4.3.9 Instinct->Skill
    pipeline" as a dependency, and K4.2 §6 asserts Skills already reuse
    "the SkillOpt-style validation gate... already adopted." A
    repository-wide search (grep for "SkillOpt", "instinct", "class
    SkillRegistry"/"class SkillOpt" across core/**/*.py) found none of
    these anywhere in the codebase — only in
    docs/archive/research/OCBRAIN_FUTURE_ARCHITECTURE.md, where "Instinct
    -> Skill Learning" is listed as a *proposed future* roadmap item
    ("Add v4.3.9"), not built work.

    `core/learning/gate.py`'s `should_learn()` is a real, working gate,
    but it solves a different problem: it scores *web-acquisition*
    chunks for the crawl -> extract -> ... -> memory pipeline (semantic-
    similarity-to-topic + LLM-judge), with no held-out-improvement
    scoring, no contradiction check, and no GovernanceKernel integration.
    It is deliberately not reused or merged into here — force-merging two
    gates that answer different questions ("is this web content worth
    keeping" vs. "does this candidate strictly improve on what exists,
    without contradicting it, cleared by governance") would itself
    create the kind of hidden coupling this project's engineering
    standards warn against. `core/skills/skill_interface.py` defines
    Skill *execution* (BaseSkill) with no promotion/creation path.

    `EvolutionGovernor.SELF_MODIFYING_ACTIONS` already includes
    "skill_promote"/"skill_create" (pre-existing, unmodified by this
    packet), so the governance vocabulary for Skill promotion is real
    even though no production caller produces it yet. This means
    `ContentDomain.SKILL` is genuinely exercised by this packet's own
    tests (proving the shared code path serves it identically to the
    other two domains) but has no production caller today — the same
    situation Packet 03 documented for Skill preconditions in
    decomposition, handled the same way: built to be correct when a real
    caller arrives, not stubbed out or fabricated around.

    "intent_ontology_promote" did not previously exist in
    EvolutionGovernor.SELF_MODIFYING_ACTIONS; it is added by this packet
    (core/governance/governance_kernel.py, one line) because Intent
    Ontology is the one domain this packet actually exercises with a real
    Evolution-tier caller path. "user_model_promote" is deliberately not
    added — no caller exists until Packet 05 builds one, and adding
    unused governance vocabulary ahead of a real caller is exactly the
    "speculative infrastructure" this project's standing practice
    rejects (see k4_2_4_completion_report.md, Discrepancy 1 resolution).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.events.event_stream import EventStream, get_event_stream
from core.governance.governance_kernel import (
    EvolutionGovernor,
    GovernanceAction,
    GovernanceKernel,
    GovernanceVerdict,
    get_governance_kernel,
)
from core.memory.unified_memory import UnifiedMemory, get_unified_memory


# ─────────────────────────────────────────────────────────────────────────
# Tier / domain / lifecycle / verdict constants — K4.2 §8, §12, §13
# ─────────────────────────────────────────────────────────────────────────

class LearningTier:
    """K4.2 §8: Learning / Adaptation / Evolution, escalating governance
    weight. These are not sequential stages a single candidate passes
    through — a caller picks the tier matching what changed (new instance
    data vs. a tuned parameter vs. a new category), per §8's table."""
    LEARNING = "learning"
    ADAPTATION = "adaptation"
    EVOLUTION = "evolution"

    ALL = (LEARNING, ADAPTATION, EVOLUTION)


class ContentDomain:
    """K4.2 §6: the three content domains sharing one ValidationGate."""
    SKILL = "skill"
    INTENT_ONTOLOGY = "intent_ontology"
    USER_MODEL = "user_model"

    ALL = (SKILL, INTENT_ONTOLOGY, USER_MODEL)


class LearningLifecycle:
    """K4.2 §13 Learning lifecycle: observed -> accumulated -> candidate
    -> gated -> [promoted | rejected]; a promoted entry may later become
    deprecated via the rollback mechanism (§8). States restated exactly
    as specified, not redefined or renamed."""
    OBSERVED = "observed"
    ACCUMULATED = "accumulated"
    CANDIDATE = "candidate"
    GATED = "gated"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class CognitiveVerdict:
    """K4.2 §12: CognitiveDecision.verdict: "proceed"|"reject"|"escalate".
    Distinct from core.governance.governance_kernel.GovernanceVerdict
    (APPROVE/REJECT/ESCALATE) — this is the cognitive-layer decision
    shape; GovernanceVerdict.APPROVE maps to CognitiveVerdict.PROCEED
    where Evolution-tier routes through GovernanceKernel."""
    PROCEED = "proceed"
    REJECT = "reject"
    ESCALATE = "escalate"


# Adaptation/Evolution-tier absolute score floor, used only when no
# baseline_score is supplied (a genuinely new candidate with no direct
# prior to compare against). Matches the existing
# MemoryGovernor.quality_threshold default (0.6) for consistency with
# this codebase's established quality bar.
DEFAULT_SCORE_FLOOR = 0.6


class ContradictionCheckError(RuntimeError):
    """Raised when the pre-write contradiction check fails to complete
    (as opposed to completing and finding no contradiction).

    ValidationGate treats this as fail-closed: an inconclusive check
    blocks promotion rather than silently proceeding, because K4.2 §8
    names the contradiction check as a precondition of promotion, not a
    best-effort courtesy.
    """


# ─────────────────────────────────────────────────────────────────────────
# Data contracts — K4.2 §12. Fields are "illustrative... not frozen
# implementation schemas" per §12's own preamble; `lifecycle_state` below
# is added because §13's Learning lifecycle has to be tracked on the one
# shape it attaches to, not because the lifecycle states themselves are
# being redefined (they are not — see LearningLifecycle above).
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CognitiveDecision:
    """K4.2 §12: the shared shape logged at any governance-style
    evaluation originating from the Cognitive Front-End — generalizes
    plan_compile, intent_ontology_promote, user_model_promote,
    meta_parameter_adjust into one consistent log shape."""
    action_type: str = ""
    subject_ref: str = ""
    verdict: str = CognitiveVerdict.REJECT
    reason: str = ""
    evaluated_at: float = field(default_factory=time.time)


@dataclass
class LearningRecord:
    """K4.2 §12: the shared shape produced by any Learning/Adaptation/
    Evolution-tier event (§8)."""
    tier: str = LearningTier.LEARNING
    content_domain: str = ""
    trigger_signals: List[str] = field(default_factory=list)
    gate_result: CognitiveDecision = field(default_factory=CognitiveDecision)
    resulting_entry_ref: Optional[str] = None
    lifecycle_state: str = LearningLifecycle.OBSERVED


# ─────────────────────────────────────────────────────────────────────────
# Contradiction detection — K4.2 §8 promotion criteria: "a contradiction-
# check against Graph Memory before write." No existing primitive checks
# an unwritten candidate against the graph:
# GraphEngine.find_contradictions()/UnifiedMemory.find_contradictions()
# are both parameterless whole-graph sweeps over already-indexed nodes
# (confirmed by reading both — see completion report). This implements
# the pre-write check the architecture requires, reusing UnifiedMemory's
# existing hybrid search (K4.2 §7: "existing hybrid BM25 + semantic +
# RRF... unchanged") rather than building new retrieval, and a
# conservative negation-cue heuristic mirroring
# core.cognitive.planner._detect_contradictions' documented approach and
# stated limits.
# ─────────────────────────────────────────────────────────────────────────

_NEGATION_MARKERS = {
    "not", "never", "no", "none", "cannot", "cant", "wont", "isnt",
    "arent", "doesnt", "dont", "didnt", "wasnt", "werent", "shouldnt",
    "false", "neither", "nor",
}

_STOP_WORDS = {
    "must", "not", "should", "the", "a", "an", "is", "are", "be", "to",
    "of", "in", "for", "and", "or", "it", "this", "that", "was", "were",
    "will", "would", "can", "could", "has", "have", "had", "on", "at",
    "with", "as", "by", "from",
}


def _is_textual_contradiction(a: str, b: str) -> bool:
    """Conservative negation-cue + keyword-overlap contradiction check.

    Mirrors core.cognitive.planner._detect_contradictions' approach:
    flags a contradiction only when exactly one of the two texts carries
    a negation cue and the two share meaningful (non-stopword) content
    words — e.g. "the deploy step requires manual approval" vs. "the
    deploy step never requires approval". Subtler, non-negation-based
    conflicts are not detected; this is a deliberate, documented limit
    (matching the precedent's own framing), not an oversight.
    """
    if not a or not b:
        return False

    a_words = set(re.findall(r"[a-z0-9]+", a.lower()))
    b_words = set(re.findall(r"[a-z0-9]+", b.lower()))

    a_negated = bool(a_words & _NEGATION_MARKERS)
    b_negated = bool(b_words & _NEGATION_MARKERS)
    if a_negated == b_negated:
        # Both negated or both affirmative: not a negation-based conflict.
        return False

    a_content = a_words - _STOP_WORDS - _NEGATION_MARKERS
    b_content = b_words - _STOP_WORDS - _NEGATION_MARKERS
    return bool(a_content & b_content)


async def _find_contradiction(
    content_domain: str,
    candidate_content: str,
    memory: UnifiedMemory,
) -> Optional[str]:
    """Return the entry_id of a contradicting *verified* entry in the
    same content_domain, or None if no contradiction is found.

    Raises ContradictionCheckError if the underlying search itself fails
    to complete — ValidationGate treats that as fail-closed (blocking),
    not fail-open. Note this is distinct from a *successful* search that
    returns no results, which is a legitimate "no contradiction found".
    """
    try:
        results = await memory.search(candidate_content, limit=5)
    except Exception as e:
        raise ContradictionCheckError(
            f"Contradiction pre-check search failed: {e}"
        ) from e

    for result in results:
        entry = result.entry
        if entry.truth_status != "verified":
            continue
        if entry.metadata.get("content_domain") != content_domain:
            continue
        if _is_textual_contradiction(candidate_content, entry.content):
            return entry.entry_id
    return None


# ─────────────────────────────────────────────────────────────────────────
# ValidationGate — K4.2 §6/§16 item 1: ONE shared function, parameterized
# by content_domain, serving all three promotion paths through one code
# path. Tier-conditional behavior restates K4.2 §8's table exactly.
# ─────────────────────────────────────────────────────────────────────────

async def validation_gate(
    *,
    tier: str,
    content_domain: str,
    subject_ref: str,
    candidate_content: str,
    trigger_signals: List[str],
    held_out_score: Optional[float] = None,
    baseline_score: Optional[float] = None,
    importance: float = 0.5,
    hitl_approved: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    memory: Optional[UnifiedMemory] = None,
    governance: Optional[GovernanceKernel] = None,
    event_stream: Optional[EventStream] = None,
) -> LearningRecord:
    """The shared ValidationGate (K4.2 §6) — one function, parameterized
    by content_domain, serving Skill / Intent Ontology / User Cognitive
    Model promotion (K4.2 §16 item 1: "one shared ValidationGate
    function... used by all three promotion paths", closing the
    duplication risk named there).

    Tier-conditional behavior restates K4.2 §8's table exactly:

      - LEARNING: "existing memory_write gate only (K3.5) — routine."
        No held-out-improvement or contradiction check; written directly
        and reported via cognitive.pattern_learned.

      - ADAPTATION: "accept only on strict, held-out improvement," plus
        (per the Promotion Criteria paragraph) a contradiction-check
        against Graph Memory before write. No event is emitted — K4.2
        §11's Event Integration table names events for Learning and
        Evolution tiers only; Adaptation-tier writes remain event-sourced
        via UnifiedMemory.write()'s own existing archive-event mechanism.

      - EVOLUTION: the same two checks, PLUS GovernanceKernel evaluation
        via EvolutionGovernor.SELF_MODIFYING_ACTIONS, "never automatic"
        (§8). `hitl_approved` defaults to False, so every real call
        today is escalated, never silently promoted; it exists purely as
        the seam a future HITL-approval surface would use once a human
        has actually approved this exact candidate (see module
        docstring — no such surface is built here, and no code path in
        this module sets the flag on a caller's behalf).

    Args:
        tier: LearningTier.LEARNING | ADAPTATION | EVOLUTION.
        content_domain: ContentDomain.SKILL | INTENT_ONTOLOGY | USER_MODEL.
        subject_ref: identifier of what this candidate is about (e.g. an
            existing entry_id being adapted, or a new category name).
        candidate_content: the candidate's textual content.
        trigger_signals: K4.2 §6 signal source names that produced this
            candidate (e.g. "reflection", "execution_outcome").
        held_out_score: the candidate's measured held-out evaluation
            score. Required for ADAPTATION/EVOLUTION (rejected if
            omitted — "strict... improvement" cannot be verified without
            one); ignored for LEARNING. Computing this score is the
            caller's domain-specific responsibility, not this gate's —
            this function owns the shared accept/reject/escalate policy
            applied once a score exists, not domain-specific scoring.
        baseline_score: the current/prior score the candidate must
            strictly exceed. None for a genuinely new candidate with
            nothing to compare against, in which case
            DEFAULT_SCORE_FLOOR is used instead.
        importance: KnowledgeEntry importance for a resulting write.
        hitl_approved: see EVOLUTION behavior above. Ignored for
            LEARNING/ADAPTATION (neither ever calls GovernanceKernel).
        metadata: additional KnowledgeEntry metadata for a resulting
            write. "content_domain" is always set to `content_domain` by
            this function (overwriting any caller-supplied value), so
            future contradiction checks can correctly scope lookups.
        memory, governance, event_stream: injected dependencies for
            testing; default to the shared singletons.

    Returns:
        A LearningRecord describing the outcome. `resulting_entry_ref`
        is set only when a write actually occurred (lifecycle_state ==
        PROMOTED); it is None for REJECTED and for GATED (Evolution-tier
        escalation pending approval).

    Raises:
        ValueError: if `tier` or `content_domain` is not one of the
            values above.
    """
    if tier not in LearningTier.ALL:
        raise ValueError(f"Unknown tier: {tier!r}")
    if content_domain not in ContentDomain.ALL:
        raise ValueError(f"Unknown content_domain: {content_domain!r}")

    memory = memory or get_unified_memory()
    governance = governance or get_governance_kernel()
    event_stream = event_stream or get_event_stream()

    entry_metadata = dict(metadata or {})
    entry_metadata["content_domain"] = content_domain
    signals = list(trigger_signals)

    # ── LEARNING tier: routine, existing memory_write gate only (K3.5) ──
    if tier == LearningTier.LEARNING:
        entry_id = await memory.write(
            content=candidate_content,
            content_type=content_domain,
            importance=importance,
            metadata=entry_metadata,
            derived_from=[subject_ref] if subject_ref else None,
            source="ValidationGate",
        )
        await event_stream.append(
            "cognitive.pattern_learned",
            source="ValidationGate",
            payload={
                "content_domain": content_domain,
                "subject_ref": subject_ref,
                "entry_id": entry_id,
                "trigger_signals": signals,
            },
        )
        return LearningRecord(
            tier=tier,
            content_domain=content_domain,
            trigger_signals=signals,
            gate_result=CognitiveDecision(
                action_type=f"{content_domain}_learn",
                subject_ref=subject_ref,
                verdict=CognitiveVerdict.PROCEED,
                reason="Learning-tier: routine instance recording via the "
                       "existing memory_write gate only (K4.2 §8); no "
                       "held-out-improvement or contradiction check "
                       "applies at this tier.",
            ),
            resulting_entry_ref=entry_id,
            lifecycle_state=LearningLifecycle.PROMOTED,
        )

    # ── ADAPTATION / EVOLUTION: strict held-out improvement required ───
    action_type = (
        f"{content_domain}_promote" if tier == LearningTier.EVOLUTION
        else f"{content_domain}_adapt"
    )

    def _rejected(reason: str) -> LearningRecord:
        return LearningRecord(
            tier=tier,
            content_domain=content_domain,
            trigger_signals=signals,
            gate_result=CognitiveDecision(
                action_type=action_type,
                subject_ref=subject_ref,
                verdict=CognitiveVerdict.REJECT,
                reason=reason,
            ),
            lifecycle_state=LearningLifecycle.REJECTED,
        )

    if held_out_score is None:
        return _rejected(
            "No held_out_score supplied; strict held-out improvement "
            "cannot be verified (K4.2 §8 promotion criteria)."
        )

    floor = baseline_score if baseline_score is not None else DEFAULT_SCORE_FLOOR
    if not (held_out_score > floor):
        basis = "baseline_score" if baseline_score is not None else "DEFAULT_SCORE_FLOOR"
        return _rejected(
            f"held_out_score {held_out_score} does not strictly exceed "
            f"{basis} ({floor}) (K4.2 §8: 'accept only on strict, "
            f"held-out improvement')."
        )

    try:
        contradiction = await _find_contradiction(
            content_domain, candidate_content, memory,
        )
    except ContradictionCheckError as e:
        return _rejected(f"Contradiction pre-check inconclusive, failing "
                          f"closed: {e}")

    if contradiction is not None:
        return _rejected(
            f"Candidate contradicts verified entry {contradiction} "
            f"(K4.2 §8 promotion criteria: contradiction-check against "
            f"Graph Memory before write)."
        )

    # Cleared both checks.
    if tier == LearningTier.ADAPTATION:
        entry_id = await memory.write(
            content=candidate_content,
            content_type=content_domain,
            importance=importance,
            truth_status="candidate",
            metadata=entry_metadata,
            derived_from=[subject_ref] if subject_ref else None,
            source="ValidationGate",
        )
        return LearningRecord(
            tier=tier,
            content_domain=content_domain,
            trigger_signals=signals,
            gate_result=CognitiveDecision(
                action_type=action_type,
                subject_ref=subject_ref,
                verdict=CognitiveVerdict.PROCEED,
                reason=f"Cleared strict held-out improvement "
                       f"({held_out_score} > {floor}) and the "
                       f"contradiction check (K4.2 §8).",
            ),
            resulting_entry_ref=entry_id,
            lifecycle_state=LearningLifecycle.PROMOTED,
        )

    # tier == EVOLUTION: EvolutionGovernor.SELF_MODIFYING_ACTIONS,
    # "never automatic" (K4.2 §8).
    if action_type not in EvolutionGovernor.SELF_MODIFYING_ACTIONS:
        return _rejected(
            f"{action_type!r} is not registered with "
            f"EvolutionGovernor.SELF_MODIFYING_ACTIONS; rejecting rather "
            f"than risking an unrecognized Evolution-tier action "
            f"silently auto-approving through GovernanceKernel."
        )

    action = GovernanceAction(
        action_type=action_type,
        worker_id="ValidationGate",
        description=f"Evolution-tier promotion: {content_domain} "
                    f"({subject_ref})",
        requires_approval=not hitl_approved,
        metadata={"subject_ref": subject_ref, "content_domain": content_domain},
    )
    result = governance.evaluate_action(action)

    if result.verdict == GovernanceVerdict.ESCALATE:
        return LearningRecord(
            tier=tier,
            content_domain=content_domain,
            trigger_signals=signals,
            gate_result=CognitiveDecision(
                action_type=action_type,
                subject_ref=subject_ref,
                verdict=CognitiveVerdict.ESCALATE,
                reason=result.reason,
            ),
            lifecycle_state=LearningLifecycle.GATED,
        )
    if result.verdict == GovernanceVerdict.REJECT:
        return _rejected(result.reason)

    # APPROVE — reachable only when hitl_approved=True was explicitly
    # supplied by the caller (see docstring: no path here sets it
    # automatically).
    entry_id = await memory.write(
        content=candidate_content,
        content_type=content_domain,
        importance=importance,
        truth_status="verified",
        metadata=entry_metadata,
        derived_from=[subject_ref] if subject_ref else None,
        source="ValidationGate",
    )
    await event_stream.append(
        "cognitive.ontology_evolved",
        source="ValidationGate",
        payload={
            "content_domain": content_domain,
            "subject_ref": subject_ref,
            "entry_id": entry_id,
            "trigger_signals": signals,
        },
    )
    return LearningRecord(
        tier=tier,
        content_domain=content_domain,
        trigger_signals=signals,
        gate_result=CognitiveDecision(
            action_type=action_type,
            subject_ref=subject_ref,
            verdict=CognitiveVerdict.PROCEED,
            reason="Cleared held-out improvement, the contradiction "
                   "check, and HITL-approved GovernanceKernel evaluation "
                   "(K4.2 §8).",
        ),
        resulting_entry_ref=entry_id,
        lifecycle_state=LearningLifecycle.PROMOTED,
    )
