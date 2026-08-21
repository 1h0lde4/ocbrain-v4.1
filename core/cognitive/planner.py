"""
core/cognitive/planner.py — K4.2.3 Constraint Extraction + Planner Contracts.

Architecture:
    OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md §5 (Planner
    Interface), §11 (Event Integration), §12 (Data Contracts), §15 (K4.2.3
    roadmap).

Packet:
    Packet 01 — K4.2.3 Constraint Extraction + Planner Contracts.

Scope:
    K4.2 §12 data contracts: Constraint, PlannerRequest, PlannerHint,
    PlannerResult, ImpasseRecord.
    K4.2 §5: _extract_constraints(goal) → List[Constraint].
    K4.2 §11: cognitive.constraints_extracted event.

    K4.2 §15 K4.2.3: "Objective: Constraint data model wired into Planner.
    _extract_constraints(); PlannerRequest/PlannerResult formalized.
    Modules: core/cognitive/planner.py."

Boundary (K4 §1, Evolution Directive):
    Produces Cognitive Artifacts and ephemeral parameter objects only.
    Never invokes capabilities, never selects experts, never performs
    execution, never writes to UnifiedMemory. Capability selection
    belongs exclusively to the future Cognitive Runtime (C-MoE).

Governance: none invoked directly. Governance evaluation is reserved
for Plan Compilation (K4 §15, a later milestone).

Explicitly NOT in scope:
    - Capability discovery (Packet 02 / K4.2.4)
    - Planner completion / plan() (Packet 03 / K4.2.5)
    - Plan Compilation (Packet 06)
    - ClarificationPolicy (Packet 03 / K4.2.5)
    - Learning / Evolution (Packet 04 / K4.2.6)
    - User Cognitive Model (Packet 05 / K4.2.7)
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.capabilities.capability import CapabilityContract
from core.capabilities.registry import CapabilityRegistry
from core.cognitive.intent import Goal
from core.events.event_stream import EventStream, get_event_stream
from core.governance.governance_kernel import (
    GovernanceAction,
    GovernanceResult,
    GovernanceVerdict,
)
from core.observability.tracer import get_trace_id
from core.provider_mesh import generate_with_fallback, resolve_provider


# ─────────────────────────────────────────────────────────────────────────
# Constraint — K4.2 §12 (embedded, not a Resource)
# ─────────────────────────────────────────────────────────────────────────

class ConstraintKind:
    """K4.2 §12: kind: "hard"|"soft"."""
    HARD = "hard"
    SOFT = "soft"


class ConstraintRelation:
    """K4.2 §12: relation: "satisfies"|"partially_satisfies"|"conflicts_with"."""
    SATISFIES = "satisfies"
    PARTIALLY_SATISFIES = "partially_satisfies"
    CONFLICTS_WITH = "conflicts_with"


class ConstraintSource:
    """K4.2 §12: source: "explicit"|"inferred"|"policy"."""
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    POLICY = "policy"


@dataclass
class Constraint:
    """A checkable constraint on plan execution.

    Architecture: K4.2 §12 — "Constraint (embedded, not a Resource):
    kind: 'hard'|'soft', relation: 'satisfies'|'partially_satisfies'|
    'conflicts_with', source: 'explicit'|'inferred'|'policy',
    rationale: str, validated_by: Optional[str]."

    K4.2 §5: "A Constraint (§4.7 of K4.2-R, unchanged) is binding and
    checkable — EvaluatorWorker can fail a plan against it."

    K4.2 §12's own closing note: Constraint is an "embedded field-set,
    not independently identified" — no resource_id, no derived_from,
    no lifecycle_state of its own. It exists inside an ExecutionPlan's
    constraint list, not as a standalone Resource.
    """
    kind: str = ConstraintKind.HARD
    relation: str = ConstraintRelation.SATISFIES
    source: str = ConstraintSource.EXPLICIT
    rationale: str = ""
    validated_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# PlannerHint — K4.2 §12 (embedded, not a Resource)
# ─────────────────────────────────────────────────────────────────────────

class HintSource:
    """K4.2 §12: source: "intent_dimension"|"user_model"."""
    INTENT_DIMENSION = "intent_dimension"
    USER_MODEL = "user_model"


@dataclass
class PlannerHint:
    """Advisory-only signal influencing Planner choices.

    Architecture: K4.2 §5 — "A PlannerHint is advisory only — it
    influences Planner's own internal choices (how many _alternative_plans
    to generate, whether to bias toward speed vs. thoroughness) but is
    never validated or enforced, and a plan can never 'fail' a hint,
    only under- or over-weight it."

    K4.2 §12 — "PlannerHint (embedded, not a Resource): kind: str,
    weight: float, source: 'intent_dimension'|'user_model'."
    """
    kind: str = ""
    weight: float = 0.0
    source: str = HintSource.INTENT_DIMENSION

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# PlannerRequest — K4.2 §12 (ephemeral parameter object)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class PlannerRequest:
    """Input to Planner.plan().

    Architecture: K4.2 §5 — "Planner contract: Planner.plan(request:
    PlannerRequest) -> PlannerResult."

    K4.2 §12 — "PlannerRequest (ephemeral parameter object): goal_id,
    goal: Goal, context_view_ref, hints: List[PlannerHint]."

    K4.2 §12's closing note places PlannerRequest as an "ephemeral
    parameter object (K1.6's fourth category) — constructed, consumed,
    discarded within one invocation." No resource_id, no lifecycle.
    """
    goal_id: str = ""
    goal: Optional[Goal] = None
    context_view_ref: str = ""
    hints: List[PlannerHint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# ImpasseRecord — K4.2 §5, §12 (referenced by PlannerResult)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class ImpasseRecord:
    """Detail of a planning impasse.

    Architecture: K4.2 §5 — "status: 'impasse'... routed through the
    Soar-derived impasse→subgoaling pattern (K4.2-R §4.9)."

    K4.2 §12 — "impasse_detail: Optional[ImpasseRecord] — present iff
    status == impasse."

    K4.2 §15 K4.2.5 names ImpasseRecord as an interface for Planner
    completion. This packet defines the data shape; the impasse→subgoaling
    logic belongs to Packet 03 (K4.2.5).
    """
    reason: str = ""
    unresolved_subgoals: List[str] = field(default_factory=list)
    attempted_capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# PlannerResult — K4.2 §12 (ephemeral parameter object)
# ─────────────────────────────────────────────────────────────────────────

class PlannerStatus:
    """K4.2 §12: status values for PlannerResult."""
    READY_FOR_COMPILATION = "ready_for_compilation"
    IMPASSE = "impasse"
    REJECTED_PRECHECK = "rejected_precheck"


@dataclass
class PlannerResult:
    """Output of Planner.plan().

    Architecture: K4.2 §12 — "PlannerResult (ephemeral parameter object):
    status: 'ready_for_compilation'|'impasse'|'rejected_precheck',
    execution_plan: Optional[ExecutionPlan], impasse_detail:
    Optional[ImpasseRecord]."

    K4.2 §5 — "status: 'rejected_precheck' covers cases Planner can
    determine are hopeless before even attempting decomposition (e.g.,
    a Goal whose hard Constraints are mutually contradictory)."

    execution_plan is typed as Optional[Any] because ExecutionPlan is
    produced by Planner completion (Packet 03 / K4.2.5) and does not
    exist yet. This will be narrowed to Optional[ExecutionPlan] once
    that packet is implemented.

    operation_id (K4.2-H1 D8, ADR-K4.2-H-08): the operation_id plan()
    generated for this invocation, surfaced back to the caller
    (Orchestrator) so it can reference the same identifier in its own
    diagnostic events (e.g. cognitive.planner_impasse_terminal) without
    Orchestrator needing to pre-generate and inject one -- D8: "plan()
    ... generate[s] one," not the caller.
    """
    status: str = PlannerStatus.READY_FOR_COMPILATION
    execution_plan: Optional[Any] = None
    impasse_detail: Optional[ImpasseRecord] = None
    operation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# Constraint Extraction — K4.2 §5
# ─────────────────────────────────────────────────────────────────────────

# Patterns for extracting explicit constraints from goal text.
# K4.2 §5: "Constraint handling. Unchanged from K4.2-R §4.7 —
# _extract_constraints(goal) produces the List[Constraint] attached
# to the in-progress ExecutionPlan, sourced explicit/inferred/policy."
# K4.2 §12: Constraint.source distinguishes explicit/inferred/policy.

_EXPLICIT_CONSTRAINT_PATTERNS = [
    # "must" / "must not" indicate hard explicit constraints.
    (re.compile(r"\bmust\s+not\b", re.I), ConstraintKind.HARD, "negation_constraint"),
    (re.compile(r"\bmust\b", re.I), ConstraintKind.HARD, "requirement_constraint"),
    # "should" / "should not" indicate soft explicit constraints.
    (re.compile(r"\bshould\s+not\b", re.I), ConstraintKind.SOFT, "soft_negation_constraint"),
    (re.compile(r"\bshould\b", re.I), ConstraintKind.SOFT, "soft_requirement_constraint"),
    # "without" indicates a hard negation constraint.
    (re.compile(r"\bwithout\b", re.I), ConstraintKind.HARD, "exclusion_constraint"),
    # "only" / "exclusively" indicates a hard scoping constraint.
    (re.compile(r"\bonly\b", re.I), ConstraintKind.HARD, "scoping_constraint"),
    (re.compile(r"\bexclusively\b", re.I), ConstraintKind.HARD, "scoping_constraint"),
]


def _extract_explicit_constraints(text: str) -> List[Constraint]:
    """Extract constraints expressed explicitly in the goal text.

    Architecture: K4.2 §12 — Constraint.source: "explicit" — constraints
    the user stated directly in the request.

    Implementation choice: the architecture does not specify the exact
    extraction method. A deliberately simple pattern-matching heuristic
    is used here, consistent with the Input Normalization precedent
    (K4.2 §2: "ordinary, deterministic code, not model-assisted
    reasoning" for auditable seam-crossing operations). The VALUES
    and FIELDS it produces are architecture-cited; the heuristic
    itself is not.

    Patterns are checked in priority order (e.g. "must not" before plain
    "must"), and a match is skipped if its character span overlaps a span
    already claimed by an earlier, more specific pattern -- otherwise
    "must not" would independently match both the "must not" pattern and
    the plain "must" pattern on the same words, producing a spurious
    second constraint whose rationale text overlaps the first closely
    enough to later read as a self-contradiction in _detect_contradictions
    (bug found during Packet 01 Post-Implementation Review: a single
    "must not do X, because Y" statement with a normal-length trailing
    clause was misclassified as two constraints and incorrectly triggered
    rejected_precheck on a goal with no actual contradiction). Deduplicating
    by claimed span rather than by the rendered context string is what
    makes this reliable regardless of surrounding text length -- the
    previous context-string dedup only worked by accident, when both
    matches' context windows happened to get clamped to the same
    end-of-string.
    """
    constraints: List[Constraint] = []
    claimed_spans: List[tuple] = []

    def _overlaps_claimed(start: int, end: int) -> bool:
        return any(start < c_end and end > c_start for c_start, c_end in claimed_spans)

    for pattern, kind, rationale_type in _EXPLICIT_CONSTRAINT_PATTERNS:
        for match in pattern.finditer(text):
            if _overlaps_claimed(match.start(), match.end()):
                continue
            claimed_spans.append((match.start(), match.end()))

            # Extract context around the match for the rationale.
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 60)
            context = text[start:end].strip()

            constraints.append(Constraint(
                kind=kind,
                relation=ConstraintRelation.SATISFIES,
                source=ConstraintSource.EXPLICIT,
                rationale=f"{rationale_type}: {context}",
            ))

    return constraints


def _extract_inferred_constraints(goal: Goal) -> List[Constraint]:
    """Extract constraints inferred from the goal's structure.

    Architecture: K4.2 §12 — Constraint.source: "inferred" — constraints
    derived from goal analysis rather than explicit user statement.

    Implementation choice: infers a complexity constraint from the goal's
    confidence level and a scope constraint from compound goals
    (sub_goals present). These are soft constraints that inform Planner
    behavior without blocking execution.
    """
    constraints: List[Constraint] = []

    # Low confidence → inferred constraint to prefer conservative plans.
    if goal.confidence < 0.5:
        constraints.append(Constraint(
            kind=ConstraintKind.SOFT,
            relation=ConstraintRelation.SATISFIES,
            source=ConstraintSource.INFERRED,
            rationale="low_confidence: goal confidence below 0.5, "
                      "prefer conservative planning approach",
        ))

    # Compound goal → inferred constraint for independent execution.
    if goal.sub_goals:
        constraints.append(Constraint(
            kind=ConstraintKind.SOFT,
            relation=ConstraintRelation.SATISFIES,
            source=ConstraintSource.INFERRED,
            rationale="compound_goal: goal is part of a compound request, "
                      "sub-goals should be independently plannable",
        ))

    return constraints


def _detect_contradictions(constraints: List[Constraint]) -> bool:
    """Detect mutually contradictory hard constraints.

    Architecture: K4.2 §5 — "status: 'rejected_precheck' covers cases
    Planner can determine are hopeless before even attempting
    decomposition (e.g., a Goal whose hard Constraints are mutually
    contradictory) — surfaced immediately rather than spending a full
    decomposition attempt on a provably-unsatisfiable Goal."

    K4.2 §15 K4.2.3 validation: "contradictory-hard-constraint fixture
    correctly yields rejected_precheck."

    Implementation choice: detects contradiction when hard constraints
    include both a requirement and its negation (e.g., "must" and
    "must not" on the same concept). This is a deliberately conservative
    check — only clear, provable contradictions are detected. Subtler
    conflicts are deferred to full Planner decomposition (Packet 03).
    """
    hard_constraints = [c for c in constraints if c.kind == ConstraintKind.HARD]

    # Check for requirement/negation pairs.
    requirements = [c for c in hard_constraints
                    if "requirement_constraint" in c.rationale
                    and "negation" not in c.rationale]
    negations = [c for c in hard_constraints
                 if "negation_constraint" in c.rationale]

    if requirements and negations:
        # Check if any requirement and negation reference overlapping text.
        for req in requirements:
            req_text = req.rationale.split(": ", 1)[-1].lower()
            for neg in negations:
                neg_text = neg.rationale.split(": ", 1)[-1].lower()
                # Extract the core terms (words) and check overlap.
                req_words = set(re.findall(r"\w+", req_text))
                neg_words = set(re.findall(r"\w+", neg_text))
                # Remove common stop words and constraint markers.
                stop_words = {"must", "not", "should", "the", "a", "an",
                              "is", "are", "be", "to", "of", "in", "for",
                              "and", "or", "it", "this", "that"}
                req_content = req_words - stop_words
                neg_content = neg_words - stop_words
                # If meaningful words overlap, constraints are contradictory.
                if req_content & neg_content:
                    return True

    return False


async def _extract_constraints(
    goal: Goal,
    *,
    event_stream: Optional[EventStream] = None,
    operation_id: Optional[str] = None,
) -> List[Constraint]:
    """Extract constraints from a Goal.

    Architecture: K4.2 §5 — "_extract_constraints(goal) produces the
    List[Constraint] attached to the in-progress ExecutionPlan, sourced
    explicit/inferred/policy."

    K4.2 §11 — event: cognitive.constraints_extracted.

    K4.2 §15 K4.2.3: "given a Goal, produces a well-formed
    ConstraintSet."

    This function extracts constraints from the goal text and structure.
    Policy constraints are not extracted here — they belong to
    GovernanceKernel evaluation at Plan Compilation (K4 §15), which is
    a later milestone.

    Args:
        goal: The Goal to extract constraints from.
        event_stream: EventStream for event emission. Uses singleton
            if not provided.
        operation_id: D8 (ADR-K4.2-H-08) — the parent plan() call's
            operation_id, passed through unchanged. This function does
            not generate its own; it is a stage within one plan()
            operation (stage_tag="constraint_extraction").

    Returns:
        List of extracted Constraint objects.
    """
    event_stream = event_stream or get_event_stream()

    constraints: List[Constraint] = []

    # 1. Extract explicit constraints from the goal description.
    description = goal.structured_form.get("description", "")
    raw_request = goal.structured_form.get("raw_request", "")
    # Use the most specific text available.
    text = description if description != "unknown" else raw_request
    constraints.extend(_extract_explicit_constraints(text))

    # 2. Extract inferred constraints from the goal's structure.
    constraints.extend(_extract_inferred_constraints(goal))

    # 3. Emit event (K4.2 §11).
    await event_stream.append(
        "cognitive.constraints_extracted",
        source="Planner",
        payload={
            "trace_id": get_trace_id(),
            "operation_id": operation_id,
            "stage_tag": "constraint_extraction",
            "goal_id": goal.resource_id,
            "constraint_count": len(constraints),
            "hard_count": sum(1 for c in constraints
                              if c.kind == ConstraintKind.HARD),
            "soft_count": sum(1 for c in constraints
                              if c.kind == ConstraintKind.SOFT),
            "sources": list(set(c.source for c in constraints)),
        },
    )

    return constraints


def check_precheck_rejection(constraints: List[Constraint]) -> Optional[PlannerResult]:
    """Check if constraints are provably unsatisfiable.

    Architecture: K4.2 §5 — "status: 'rejected_precheck' covers cases
    Planner can determine are hopeless before even attempting
    decomposition."

    K4.2 §15 K4.2.3 validation: "contradictory-hard-constraint fixture
    correctly yields rejected_precheck."

    Returns:
        PlannerResult with status=rejected_precheck if contradictions
        detected, None otherwise.
    """
    if _detect_contradictions(constraints):
        return PlannerResult(
            status=PlannerStatus.REJECTED_PRECHECK,
            impasse_detail=ImpasseRecord(
                reason="contradictory_hard_constraints",
            ),
        )
    return None


def build_planner_request(
    goal: Goal,
    constraints: List[Constraint],
    *,
    context_view_ref: str = "",
) -> PlannerRequest:
    """Build a PlannerRequest from a Goal and extracted constraints.

    Architecture: K4.2 §5 — "Planner inputs — PlannerRequest
    (illustrative): goal_id, goal, context_view_ref,
    hints: List[PlannerHint]."

    K4.2 §5 — "PlannerHint... sourced from Intent.dimensions.
    complexity_estimate and from the User Cognitive Model (§3)."

    Hints from User Cognitive Model are not available until
    Packet 05 (K4.2.7). This function produces hints solely from
    Intent dimensions, which are already available in the Goal's
    parent Intent.
    """
    hints: List[PlannerHint] = []

    # Generate hint from complexity estimate if available.
    # K4.2 §5: "a user who consistently prefers terse answers yields
    # a PlannerHint biasing toward fewer, more direct steps."
    # K4.2 §2: complexity_estimate available via Intent.dimensions.
    category = goal.structured_form.get("category", "novel")
    if category == "novel":
        hints.append(PlannerHint(
            kind="prefer_thoroughness",
            weight=0.7,
            source=HintSource.INTENT_DIMENSION,
        ))

    # Low confidence goals get a hint for conservative planning.
    if goal.confidence < 0.5:
        hints.append(PlannerHint(
            kind="prefer_thoroughness",
            weight=0.8,
            source=HintSource.INTENT_DIMENSION,
        ))
    elif goal.confidence > 0.8:
        hints.append(PlannerHint(
            kind="prefer_speed",
            weight=0.6,
            source=HintSource.INTENT_DIMENSION,
        ))

    return PlannerRequest(
        goal_id=goal.resource_id,
        goal=goal,
        context_view_ref=context_view_ref,
        hints=hints,
    )


# ─────────────────────────────────────────────────────────────────────────
# CapabilityDiscoveryRequest — K4.2 §12 (Packet 02 / K4.2.4 Capability Discovery)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CapabilityDiscoveryRequest:
    """A discovery-time query: "what capabilities might satisfy this
    sub-goal, given these constraints?"

    Architecture: K4.2 §12. Named `CapabilityDiscoveryRequest` per the
    July 25, 2026 architecture correction -- K4.2 §12 originally called
    this type `CapabilityRequest`, which collided with the unrelated,
    pre-existing K2.3 execution-time type at
    core.capabilities.capability.CapabilityRequest (the input to one
    Adapter.execute() call: capability_type, payload, trace_id,
    metadata). That type asks an Adapter to actually do something; this
    type asks the CapabilityRegistry what might be able to do something,
    before anything is selected or invoked. The K2.3 type keeps its
    original name unchanged; only this, the newer and not-yet-depended-
    upon type, was renamed -- see docs/architecture/
    k4_2_4_completion_report.md's Addendum for the full resolution and
    docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md
    §5/§12/§15 for the corresponding architecture-document updates.
    """
    subgoal_ref: str
    description: str
    applicable_constraints: List[Constraint] = field(default_factory=list)
    context_view_ref: str = ""


def build_capability_discovery_request(
    goal: Goal,
    constraints: List[Constraint],
    context_view_ref: str = "",
) -> CapabilityDiscoveryRequest:
    """Constructs a CapabilityDiscoveryRequest from a Goal and its Constraints.

    Architecture: K4.2 §12; mirrors build_planner_request's established
    pattern (Packet 01).

    subgoal_ref: Decomposition -- breaking a Goal into the sub-goals
    Planner will actually execute -- is Planner's own job and does not
    exist yet (Packet 03: Planner Completion, K4.2.5). Goal.sub_goals
    (K4.2 §4) is a different thing: sibling-Goal references from
    compound-request splitting, not Planner-decomposition sub-goals.
    Until decomposition exists, this uses the Goal's own resource_id as
    subgoal_ref -- there is exactly one thing to discover capabilities
    for (the whole Goal) until decomposition produces real sub-goals.
    Documented here, not silently assumed, so Packet 03 knows to replace
    this call site once real sub-goals exist.
    """
    return CapabilityDiscoveryRequest(
        subgoal_ref=goal.resource_id,
        description=(goal.structured_form or {}).get("description", ""),
        applicable_constraints=list(constraints),
        context_view_ref=context_view_ref,
    )


# ─────────────────────────────────────────────────────────────────────────
# CapabilityMatch / CapabilityDiscoveryResult — K4.2-H1 D4 (ADR-K4.2-H-04)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CapabilityMatch:
    """One candidate from capability discovery.

    Architecture: K4.2-H1 D4 -- discover_capabilities() returns a
    structured, ranked result instead of a bare List[CapabilityContract],
    so the Planner can consume scores, evidence, and ranking rather than
    an unordered-looking list that silently discards how/why each
    candidate was matched.

    evidence is diagnostic/explanatory metadata -- NOT a second source
    of truth. relevance_score (and the specificity-dominance ordering
    discover_capabilities() applies before returning) remain the
    canonical ranking signal; nothing downstream should re-derive a
    ranking decision from evidence's contents. Only evidence keys that
    actually have a real signal behind them in v1.0 are populated
    (lexical_score, specificity_tier, general_fallback) -- domain_match/
    schema_match/embedding_score/language_match are NOT fabricated here;
    a future signal can add a new evidence key without changing this
    dataclass's contract (H1-G11).
    """
    capability_type: str
    contract: CapabilityContract
    relevance_score: float
    subgoal_ref: str
    is_general_purpose: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityDiscoveryResult:
    """Ranked discovery output for one CapabilityDiscoveryRequest.

    Architecture: K4.2-H1 D4 -- the canonical, structured production
    path discover_capabilities() returns. matches is already ordered by
    specificity dominance (strong specific > weak specific >
    general-purpose fallback) before this is constructed -- consumers
    should not need to re-sort.
    """
    matches: List[CapabilityMatch]
    subgoal_ref: str

    @property
    def contracts(self) -> List[CapabilityContract]:
        """Legacy-shape compatibility projection: the bare
        List[CapabilityContract] discover_capabilities() used to return,
        in the same (now ranked) order. Provided so any future caller
        that only needs contracts, not scores/evidence, is not forced
        to unpack CapabilityMatch itself."""
        return [m.contract for m in self.matches]

    @property
    def top_match(self) -> Optional[CapabilityMatch]:
        """Highest-ranked candidate, or None if no candidate matched."""
        return self.matches[0] if self.matches else None


# ─────────────────────────────────────────────────────────────────────────
# Capability matching and discovery — K4.2 §12 line 176, §11
# ─────────────────────────────────────────────────────────────────────────

_CAPABILITY_STOP_WORDS = frozenset({
    "a", "an", "the", "to", "of", "for", "in", "on", "and", "or", "is",
    "this", "that", "with", "from", "via", "by", "at", "as",
})


def _tokenize(text: str) -> set:
    """Lowercase word tokens, stripped of punctuation. Deterministic, no
    external dependency -- consistent with this module's existing
    pattern-based (not model-assisted) approach to text analysis
    (_extract_explicit_constraints uses the same style of plain regex)."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _capability_match_score(request: CapabilityDiscoveryRequest,
                             contract: CapabilityContract) -> float:
    """Deterministic description-overlap score in [0, 1].

    This task's Step 6/8 require "deterministic discovery" and
    "description-and-schema matching"; no specific scoring formula is
    given anywhere read in K4.2 -- discovery method, like constraint
    extraction's method, is left to implementation judgment. Token
    overlap (Jaccard similarity over non-stopword tokens) is used for
    the same reason it was used for constraint extraction: simple,
    auditable, no model call -- not a claim that this exact formula is
    architecture-mandated.
    """
    request_tokens = _tokenize(request.description) - _CAPABILITY_STOP_WORDS
    contract_tokens = _tokenize(contract.description) - _CAPABILITY_STOP_WORDS
    if not request_tokens or not contract_tokens:
        return 0.0
    overlap = request_tokens & contract_tokens
    union = request_tokens | contract_tokens
    return len(overlap) / len(union)


def _classify_specificity_tier(score: float, is_general_purpose: bool) -> str:
    """Diagnostic-only label for CapabilityMatch.evidence["specificity_tier"].

    K4.2-H1 D2/D4: evidence is "diagnostic/explanatory metadata -- NOT a
    second source of truth." This label does not affect inclusion or
    ranking -- both are governed entirely by discover_capabilities()'s
    own min_score/is_general_purpose check and specificity-dominance
    sort, not by this function. The 0.5 cutoff between "strong" and
    "weak" specific is a display convenience (Jaccard overlap >= 0.5 is
    already a substantial majority-token match), not an architectural
    threshold -- D2 explicitly warns against hard-coding one of those
    for anything that actually gates behavior; this one doesn't.
    """
    if is_general_purpose and score <= 0.0:
        return "general_fallback"
    return "strong_specific" if score >= 0.5 else "weak_specific"


async def discover_capabilities(
    request: CapabilityDiscoveryRequest,
    registry: CapabilityRegistry,
    *,
    event_stream: Optional[EventStream] = None,
    min_score: float = 0.0,
    operation_id: Optional[str] = None,
) -> CapabilityDiscoveryResult:
    """Discovers candidate capabilities for a CapabilityDiscoveryRequest.

    Architecture: this packet's own task spec -- "discovering candidate
    capabilities; querying the Capability Registry; matching capabilities
    against the Goal and extracted Constraints; returning deterministic
    capability candidates together with their published schemas." K4.2
    §5 ("Capability requests," corrected July 25, 2026): resolved by
    querying CapabilityRegistry directly via its real API.

    Only CapabilityRegistry is queried: no CognitiveService Registry
    exists anywhere in this codebase (confirmed by repository-wide
    search during this packet's audit) -- K4.1 Part III describes one
    conceptually but it was never implemented. Querying it is Not
    Applicable, not a gap this packet leaves open; nothing here invents
    a stand-in for it.

    registry is an explicit parameter, not a singleton accessor:
    CapabilityRegistry's own module docstring states "No global state.
    No singleton lookups. No hidden dependencies," and no
    get_capability_registry() accessor exists anywhere in this codebase
    -- inventing one here would contradict that stated design.

    K4.2-H1 D4 (ADR-K4.2-H-04): returns a CapabilityDiscoveryResult --
    ranked CapabilityMatch entries carrying scores and evidence -- in
    place of the bare List[CapabilityContract] this returned before H1.
    All callers are internal to this module (_decompose(), below);
    confirmed by repository-wide search, no external consumer exists.
    CapabilityDiscoveryResult.contracts projects back to the old
    List[CapabilityContract] shape for any future caller that only
    needs contracts, not scores.

    K4.2-H1 D2 (ADR-K4.2-H-02, fixes K42-002): a capability whose
    CapabilityContract.is_general_purpose is True is included as a
    fallback candidate REGARDLESS of min_score -- that is the entire
    point of marking it general-purpose (K4.2-H1 D2: "Specificity
    dominance. No hard-coded routing"). Every other capability is still
    filtered by min_score exactly as before H1. Ranking then applies
    specificity dominance below: any non-general-purpose match (however
    weak, as long as it cleared min_score) outranks every
    general-purpose-only match. This is the fix for K42-002: with only
    LLM_COMPLETION (is_general_purpose=True) registered, a realistic
    task phrasing scoring 0.0 against its description used to be
    filtered out entirely by _decompose()'s min_score=0.01, producing
    zero candidates and a spurious impasse on every realistic query;
    LLM_COMPLETION is now included as the (here, sole, hence top-ranked)
    fallback candidate. [Implementation note: the spec's own illustrative
    discovery-flow snippet gated ALL candidates -- general-purpose
    included -- behind `if score >= min_score`, which would have left
    K42-002 unfixed for exactly the scenario it exists to fix; this
    function implements D2's stated intent (fallback bypasses the
    lexical gate) rather than that snippet literally, per the
    specification's own "implementation guidance, not rigid patch
    instructions" framing.]

    Candidates with zero registered adapters (CapabilityRegistry's own
    "declared but unfulfilled" category, per its validate() method) are
    excluded: a capability nothing can currently execute is not a usable
    candidate for whatever selects from this list next. This does not
    invoke, or even inspect, any adapter beyond confirming one is
    registered -- get_adapters() returns a list; it calls nothing.

    Never calls Adapter.execute(), never ranks down to a single winner
    (selection is explicitly deferred to a future Cognitive Runtime
    packet, per the Evolution Directive's discovery/selection split),
    never touches memory or governance.

    operation_id (D8, ADR-K4.2-H-08): the parent plan() call's
    operation_id, passed through unchanged -- discover_capabilities()
    does NOT generate its own operation_id (D8: it "shares the parent
    operation_id with a stage_tag discriminator"; it is called in a loop
    inside _decompose(), not as an independent top-level operation).
    None is accepted (e.g. direct/test callers outside a plan()
    invocation) and simply passed through as None.
    """
    event_stream = event_stream or get_event_stream()

    scored: List[CapabilityMatch] = []
    for capability_type in registry.list_capabilities():
        contract = registry.get_contract(capability_type)
        if contract is None:
            continue
        if not registry.get_adapters(capability_type):
            continue

        score = _capability_match_score(request, contract)
        is_general = contract.is_general_purpose

        # D2: min_score gates ordinary (non-general-purpose) candidates
        # exactly as before H1. A general-purpose capability bypasses
        # this gate -- it is a fallback BY CONSTRUCTION, not filtered
        # out for the same reason a specific-but-irrelevant capability
        # would be. See the docstring note above for why this differs
        # from the spec's own illustrative snippet.
        if score < min_score and not is_general:
            continue

        scored.append(CapabilityMatch(
            capability_type=contract.capability_type,
            contract=contract,
            relevance_score=score,
            subgoal_ref=request.subgoal_ref,
            is_general_purpose=is_general,
            evidence={
                "lexical_score": round(score, 4),
                "specificity_tier": _classify_specificity_tier(score, is_general),
                "general_fallback": is_general,
            },
        ))

    # D2: specificity dominance -- every non-general-purpose match ranks
    # above every general-purpose-only match; within each group, higher
    # relevance_score ranks first. Reads only CapabilityContract.
    # is_general_purpose and CapabilityMatch.relevance_score -- no
    # hard-coded capability_type routing (D2), no Planner-side special
    # case; the registry remains the single dynamic source of what is
    # general-purpose.
    scored.sort(key=lambda m: (m.is_general_purpose, -m.relevance_score))

    await event_stream.append(
        "cognitive.capabilities_discovered",
        source="CapabilityDiscovery",
        payload={
            "trace_id": get_trace_id(),
            "operation_id": operation_id,
            "stage_tag": f"capability_discovery:{request.subgoal_ref}",
            "subgoal_ref": request.subgoal_ref,
            "candidate_count": len(scored),
            "candidates": [
                {"capability_type": m.capability_type,
                 "score": round(m.relevance_score, 3),
                 "is_general_purpose": m.is_general_purpose}
                for m in scored
            ],
        },
    )

    return CapabilityDiscoveryResult(matches=scored, subgoal_ref=request.subgoal_ref)


# ─────────────────────────────────────────────────────────────────────────
# Planner Completion — K4 §5/§6, K4.2 §5/§12/§14/§15 (Packet 03 / K4.2.5)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class ClarificationPolicy:
    """Policy data governing when a low-confidence ExecutionPlan should be
    escalated for human clarification rather than compiled and run.

    Architecture: K4.2 §2 -- "ClarificationPolicy -- Policy data
    (Constitution glossary: 'a specific, declared rule constraining what
    a capability or resource may do'), owned by GovernanceKernel like any
    other Policy, evaluated by the OrchestrationGovernor rule, not a new
    component or a new gate." K4.2 §14 -- the escalation path is itself
    bounded: a Goal escalated more than max_escalations times on the same
    underlying ambiguity is handed to SupervisorWorker as a stalled case
    rather than re-escalated indefinitely, "reusing RecursionGovernor's
    existing bounded-loop principle rather than inventing a second one."

    Design note (per explicit direction received during this packet's
    planning phase): implemented as narrowly-scoped policy parameters
    consumed by OrchestrationGovernor.evaluate() -- not a generic rule
    registry, not a new governor, not a plugin system. confidence_threshold
    and max_escalations are the two parameters the architecture actually
    names (a confidence bound, and a bound on repetition); nothing beyond
    that is added.

    max_escalations is a policy parameter here rather than reusing
    RecursionGovernor's shared, general-purpose max_depth: RecursionGovernor
    already exists and is registered independently in GovernanceKernel for
    unrelated recursion contexts elsewhere in the system, with its own
    general default (10). Overloading the same field+threshold for a
    semantically different, much smaller ceiling (clarification retries
    specifically) risked exactly the kind of conflation "reuse... rather
    than inventing a second one" is trying to avoid, not the thing it
    endorses -- the principle being reused is the shape of the check
    (bounded counter compared against a small configured ceiling, REJECT
    once exceeded), applied within OrchestrationGovernor's own evaluate()
    using the same action.metadata pattern it already uses for
    worker_type, not RecursionGovernor's specific field. Documented here
    as a judgment call, not a silent assumption.
    """
    confidence_threshold: float = 0.5
    max_escalations: int = 2


class ExecutionPlanLifecycle:
    """Lifecycle values for ExecutionPlan. Architecture: K4 §6 --
    "lifecycle_state: str # draft -> compiled -> executing -> completed |
    failed | superseded." Packet 03 (Planner) only ever produces DRAFT --
    the remaining states belong to Plan Compilation and WorkflowRuntime,
    neither of which this packet touches."""
    DRAFT = "draft"
    COMPILED = "compiled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


@dataclass
class PlanStep:
    """One step of an in-progress ExecutionPlan.

    Architecture: K4 §6 -- "steps: List[PlanStep] # ordered; each maps to
    one eventual WorkflowNode" and "PlanStep maps onto WorkflowNode
    roughly 1:1 (WorkflowNode is confirmed minimal: node_id, worker_type,
    config, retry_policy, error_branch -- one worker per node)."

    Fields chosen to carry what Planning-time reasoning actually knows
    (step_id/description/capability_type/error_branch) without
    prematurely deciding Plan Compiler's worker_type mapping mechanics --
    which specific WorkerType executes a given capability_type is
    Compilation's job (K4 §6: "Plan Compiler's actual job is narrow:
    reduce Planner's richer reasoning... down to the single concrete
    sequence WorkflowRuntime already knows how to run"), not something
    this packet needs to resolve to produce a valid, "roughly 1:1"
    PlanStep.
    """
    step_id: str
    description: str
    capability_type: str
    error_branch: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Planner's own output: an ordered set of steps intended to satisfy
    a Goal, not yet compiled into a runnable WorkflowDefinition.

    Architecture: K4 §6 -- "resource_id, goal_id, steps: List[PlanStep],
    confidence: float, alternatives: List[str] # references to
    alternative ExecutionPlan.resource_id, not embedded copies,
    justification: str, lifecycle_state: str." Specializes CognitiveArtifact
    (K4.1 Part IV) the same way Intent/Goal do -- resource_id is present
    here (unlike the ephemeral parameter objects PlannerRequest/
    CapabilityDiscoveryRequest/PlannerResult), matching K4 §6's own
    "ExecutionPlan is a Cognitive Runtime artifact" framing and its
    explicit resource_id field.

    produced_by/derived_from are included for the same reason they were
    added to Intent in K4.2.1: this type is explicitly framed as a
    CognitiveArtifact by K4 §6 ("provenance... the naming convention
    already established in core/capabilities/resource.py"), and K4.1 Part
    IV's base contract requires them even where a specific field-level
    schema (here, K4 §6's) doesn't re-list every inherited field.

    caused_by (K4.2-H1 D9, ADR-K4.2-H-09): Optional[str] event_id. None
    for a plan produced by the ordinary plan() path; populated when this
    plan resulted from a recovery re-plan (Orchestrator's K4.2-branch
    re-plan loop) triggered by a specific prior impasse event.

    general_purpose_only (ADR-K4.2-H-13): not part of K4 §6's original
    field list -- added 2026-08-20 after live debugging showed
    ClarificationPolicy's confidence gate (K4.2 §14) escalating
    indiscriminately on low confidence, including the case where the low
    score comes entirely from the general-purpose fallback (K4.2-H1 D2)
    having no specific alternative to be compared against, not from
    genuine ambiguity among real candidates. True iff
    _is_general_purpose_only(steps_with_candidates) at plan() time (see
    that function in this module). Read by compile()
    (core/cognitive/compiler.py) and consumed by OrchestrationGovernor
    (core/governance/orchestration_governor.py) to exempt such plans from
    escalation regardless of their raw confidence value.
    """
    resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    produced_by: str = "Planner"
    goal_id: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    confidence: float = 0.0
    general_purpose_only: bool = False
    alternatives: List[str] = field(default_factory=list)
    justification: str = ""
    derived_from: List[str] = field(default_factory=list)
    caused_by: Optional[str] = None
    lifecycle_state: str = ExecutionPlanLifecycle.DRAFT

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


_DECOMPOSITION_PROMPT_TEMPLATE = """You are the Planner of a governed cognitive runtime.
Given a goal, break it into an ordered list of concrete steps needed to
achieve it. Most goals need only one step; only split into multiple
steps when the goal genuinely requires distinct, sequential actions that
cannot be done as a single step.

Output one step per line, describing what that step must accomplish.
Do not number the steps or add any other text.

Goal:
{description}

Steps:"""


def _parse_decomposition(completion: Optional[str]) -> List[str]:
    """Parses the provider's raw completion into step descriptions -- one
    non-empty line per step, consistent with _parse_hypotheses's
    established line-based parsing style (K4.2.1)."""
    lines = [line.strip() for line in (completion or "").splitlines()]
    return [line for line in lines if line]


async def _decompose(
    goal: Goal,
    registry: CapabilityRegistry,
    *,
    event_stream: Optional[EventStream] = None,
    operation_id: Optional[str] = None,
) -> List[tuple]:
    """Breaks a Goal into an ordered list of steps, each grounded in real
    discovered capability candidates.

    Architecture: K4 §5's illustrative pseudocode -- "candidate_steps =
    self._decompose(goal) # goal -> ordered tasks." K4.1 Part III
    describes Planner's reasoning as "already LLM-assisted" -- consistent
    with that precedent (and with Intent Interpretation's own use of
    provider_mesh, K4.2.1), step proposal is model-assisted; matching
    candidates against CapabilityRegistry per proposed step reuses
    discover_capabilities() (Packet 02) directly -- no second retrieval
    or matching mechanism.

    Skill preconditions (this packet's task spec: "skill preconditions
    wired into decomposition") are NOT wired in here: no Skill or
    SkillRuntime implementation exists anywhere in this codebase
    (confirmed by repository-wide search during this packet's planning
    phase). There is nothing to wire into. Each PlanStep carries a
    capability_type a future precondition check could gate on, so
    decomposition is not structurally closed to this -- but nothing here
    fabricates a stand-in Skill system to have something to check
    against. Flagged, not silently dropped.

    Returns a list of (PlanStep, candidates) tuples -- not just the
    PlanSteps -- so callers (impasse detection, confidence estimation,
    alternative-plan generation) can inspect each step's full ranked
    candidate list without re-querying the registry. candidates is now
    (K4.2-H1 D4) a List[CapabilityMatch] -- the .matches unwrapped from
    discover_capabilities()'s CapabilityDiscoveryResult -- not a bare
    List[CapabilityContract]; CapabilityMatch carries capability_type as
    a top-level field (mirroring CapabilityContract), so existing
    .capability_type access in downstream consumers is unaffected.
    """
    description = (goal.structured_form or {}).get("description", "")
    prompt = _DECOMPOSITION_PROMPT_TEMPLATE.format(description=description)

    step_descriptions: List[str] = []
    try:
        completion = await generate_with_fallback(
            resolve_provider("planner_decompose"), prompt,
        )
        step_descriptions = _parse_decomposition(completion)
    except Exception:
        step_descriptions = []

    if not step_descriptions:
        # Degrade to a single step covering the whole goal description --
        # the same "open-category fallback" spirit as Intent Interpretation's
        # degrade-to-novel path (K4.2 §2): a plan with one broad step is a
        # more useful, still-deterministic outcome than no plan at all.
        step_descriptions = [description or "unspecified"]

    results: List[tuple] = []
    for i, step_description in enumerate(step_descriptions):
        request = CapabilityDiscoveryRequest(
            subgoal_ref=f"{goal.resource_id}:{i}",
            description=step_description,
        )
        # min_score=0.01 (not discover_capabilities' own permissive
        # default of 0.0): a score of exactly 0.0 means zero token
        # overlap between the step and a NON-general-purpose capability's
        # description -- no relevance signal at all, not a weak-but-real
        # match. Without this, any registered non-general-purpose
        # capability with at least one adapter would count as a
        # "candidate" for every step regardless of relevance, which would
        # make impasse detection (below) fire only when the registry is
        # completely empty -- not the "no *matching* capability" signal
        # K4.2 §5/§14 actually describe. This is decomposition-side
        # filtering, not a change to discover_capabilities itself
        # (Packet 02's own conservative "rank, don't filter, by default"
        # choice is unchanged and still correct for its own direct
        # callers). K4.2-H1 D2 (ADR-K4.2-H-02, fixes K42-002): a
        # general-purpose capability (CapabilityContract.
        # is_general_purpose=True, e.g. LLM_COMPLETION) is the one
        # deliberate exception -- discover_capabilities() includes it
        # regardless of this min_score, because "usable by any
        # text-shaped subgoal even with zero lexical overlap" is what
        # is_general_purpose means. That is what fixes the previously
        # spurious impasse when LLM_COMPLETION is the only capability
        # registered.
        discovery_result = await discover_capabilities(
            request, registry, event_stream=event_stream, min_score=0.01,
            operation_id=operation_id,
        )
        candidates = discovery_result.matches
        step = PlanStep(
            step_id=f"step-{i}",
            description=step_description,
            capability_type=candidates[0].capability_type if candidates else "",
        )
        results.append((step, candidates))

    return results


def _sequence(steps_with_candidates: List[tuple],
              constraints: List[Constraint]) -> List[PlanStep]:
    """Orders steps for execution.

    Architecture: K4 §5's pseudocode -- "ordering =
    self._sequence(candidate_steps, constraints)." No sequencing
    algorithm is specified anywhere read in K4/K4.2 beyond naming the
    step's existence and its inputs -- implementation judgment, same
    category as _capability_match_score's scoring formula (K4.2.4), not
    a cited formula.

    Decomposition's own proposed order is preserved as the default: the
    model was asked for an ORDERED list, and reordering without a
    specified algorithm risks discarding real ordering information it
    inferred (e.g. "download the file, then summarize it") for no
    architecturally justified reason. constraints is accepted, matching
    the cited signature, but does not currently reorder steps: as with
    capability matching (K4.2.4), hard constraints are frequently
    negative ("must not do X before Y"), and no architecture section
    specifies how constraint text should translate into a reordering
    rule. Flagged as a conservative choice, not silently decided.
    """
    return [step for step, _ in steps_with_candidates]


def _fallback_paths(steps: List[PlanStep]) -> List[PlanStep]:
    """Assigns each step's error_branch.

    Architecture: K4 §5 -- "fallbacks = self._fallback_paths(ordering) #
    per-step error_branch candidates." No fallback-selection algorithm
    is specified. Left as a documented no-op for this packet: same-step
    retry is already RetryPolicy's job (K4 §6, an existing, separate
    WorkflowNode field this type deliberately doesn't duplicate), and
    assigning a DIFFERENT step as a fallback target requires a selection
    rule this packet has no architectural basis for inventing.
    error_branch stays None; a future packet with an actual
    fallback-selection specification can populate it without changing
    this function's signature or PlanStep's shape.
    """
    return list(steps)


def _estimate_confidence(steps_with_candidates: List[tuple]) -> float:
    """Estimates overall plan confidence.

    Architecture: K4 §5 -- "confidence =
    self._estimate_confidence(ordering, capabilities)." No formula is
    specified. Deterministic and auditable: the plan's confidence is the
    match score of its WEAKEST step's best candidate -- a plan is only
    as strong as its least-supported step, consistent with K4.2 §9's
    general confidence-propagation philosophy of not letting one strong
    step mask a genuinely weak one. A step with zero candidates
    contributes 0.0 (in practice this is caught by impasse detection
    before confidence is ever estimated, but the formula stays correct
    if called on its own).

    K4.2-H1 D4: candidates is now a List[CapabilityMatch] (see
    _decompose()). candidates[0].relevance_score is read directly rather
    than rebuilding a CapabilityDiscoveryRequest and re-calling
    _capability_match_score() as before H1 -- mathematically identical
    (relevance_score already IS that exact computation, made against
    this same step.description, at discovery time in
    discover_capabilities()), just without redundantly recomputing it.
    """
    if not steps_with_candidates:
        return 0.0
    step_scores = []
    for step, candidates in steps_with_candidates:
        if not candidates:
            step_scores.append(0.0)
            continue
        step_scores.append(candidates[0].relevance_score)
    return round(min(step_scores), 3)


def _is_general_purpose_only(steps_with_candidates: List[tuple]) -> bool:
    """True iff every step's top-ranked candidate is the general-purpose
    fallback -- i.e. no step in this plan found even one non-general-
    purpose candidate that cleared discover_capabilities()'s min_score
    gate.

    ADR-K4.2-H-13: a companion signal to _estimate_confidence(), computed
    independently rather than derived from it -- that function answers
    "how low was the weakest step's score", this one answers "was there
    ever a *specific* alternative anywhere in the plan to be uncertain
    between at all". Because discover_capabilities()'s specificity-
    dominance ordering (K4.2-H1 D2, ADR-K4.2-H-02) already guarantees any
    cleared non-general-purpose candidate outranks every general-purpose
    one for its step, checking candidates[0].is_general_purpose is
    sufficient -- a better-ranked specific candidate silently losing to a
    general-purpose one is not a case that ordering can produce.

    A step with zero candidates is NOT counted as general-purpose-only
    (returns False for the whole plan): that is a materially different,
    more concerning situation than "found only the fallback" -- in
    practice it is caught by impasse detection before this is ever
    called (see _estimate_confidence's identical note), but this
    function stays conservative if ever invoked on its own.

    An empty plan (no steps at all) also returns False, matching
    _estimate_confidence's own explicit handling of the same input:
    consistent, not coincidental -- both treat "nothing to reason about"
    as the more cautious of their two possible defaults (False/0.0)
    rather than a vacuous True that would silently exempt something from
    downstream governance.
    """
    if not steps_with_candidates:
        return False
    for _step, candidates in steps_with_candidates:
        if not candidates or not candidates[0].is_general_purpose:
            return False
    return True


def _alternative_plans(goal: Goal, steps_with_candidates: List[tuple],
                        *, top_n: int = 2) -> List[str]:
    """Generates up to top_n alternative ExecutionPlans, returning
    references to their resource_id only.

    Architecture: K4 §5 -- "alternatives =
    self._alternative_plans(goal, top_n=2) # generated, not necessarily
    compiled." K4 §6 -- alternatives are "references to alternative
    ExecutionPlan.resource_id, not embedded copies."

    Minimal, honestly-scoped: for each step that has a second-ranked
    capability candidate (already available from _decompose's own
    discovery pass -- no second registry query), constructs one
    alternative ExecutionPlan substituting that step's second-best
    candidate for its top-ranked one. This is a real, if narrow, notion
    of "a genuinely different plan," grounded in what discovery actually
    found, rather than a second LLM decomposition pass -- which would
    double this function's provider calls and add a second source of
    non-determinism with no clearer specification to justify it. Returns
    fewer than top_n, or none, when the primary plan's steps each have
    at most one candidate -- an honest short list rather than a
    fabricated one.

    K4.2-H1 D4: candidates is now a List[CapabilityMatch]. No logic
    change needed here -- CapabilityMatch.capability_type is a
    top-level field (mirroring CapabilityContract), so
    candidates[N].capability_type continues to work unchanged.
    """
    alternatives: List[str] = []
    base_steps = [step for step, _ in steps_with_candidates]
    for i, (step, candidates) in enumerate(steps_with_candidates):
        if len(alternatives) >= top_n:
            break
        if len(candidates) < 2:
            continue
        alt_steps = list(base_steps)
        alt_steps[i] = dataclasses.replace(
            alt_steps[i], capability_type=candidates[1].capability_type,
        )
        alt_plan = ExecutionPlan(
            goal_id=goal.resource_id,
            steps=alt_steps,
            justification=(
                f"Alternative: {step.step_id} using "
                f"{candidates[1].capability_type} instead of "
                f"{candidates[0].capability_type}"
            ),
            derived_from=[goal.resource_id],
        )
        alternatives.append(alt_plan.resource_id)
    return alternatives


def _justify(steps: List[PlanStep], constraints: List[Constraint]) -> str:
    """Produces a human-readable justification for the plan's ordering
    and capability choices.

    Architecture: K4 §6 -- ExecutionPlan.justification: "why this
    ordering, why these capabilities"; K4 §5's pseudocode calls
    self._justify(ordering, constraints). No format is specified beyond
    "why" -- a deterministic, templated summary is used rather than an
    LLM call, keeping this seam auditable and matching the determinism
    this document family favors wherever a choice is not otherwise
    forced (K4.2.1's normalize_request is the precedent for this same
    judgment call).
    """
    if not steps:
        return "No steps were produced for this goal."
    step_summary = "; ".join(
        f"{s.step_id}: {s.description} "
        f"(via {s.capability_type or 'no matching capability'})"
        for s in steps
    )
    constraint_summary = (
        f" Constrained by {len(constraints)} requirement(s)."
        if constraints else ""
    )
    return f"{len(steps)} step(s) in decomposition order: {step_summary}.{constraint_summary}"


def _detect_impasse(steps_with_candidates: List[tuple]) -> Optional[ImpasseRecord]:
    """Detects whether decomposition has hit an impasse: one or more
    steps for which no capability candidate was found at all.

    Architecture: K4.2 §12 -- "impasse_detail: Optional[ImpasseRecord] --
    present iff status == impasse." K4.2 §14 -- "Planner impasse
    (status: 'impasse') | Soar-derived impasse->subgoaling... routes
    through Capability Discovery and, if nothing resolves it, Skill
    Runtime delegation."

    This implements the detection and the ImpasseRecord it produces
    (K4.2.1's own ImpasseRecord shape: reason, unresolved_subgoals,
    attempted_capabilities). It does NOT implement Skill Runtime
    delegation as a further fallback after impasse: no Skill or
    SkillRuntime exists anywhere in this codebase (confirmed by
    repository-wide search during this packet's planning). An impasse
    here is a genuine, final "no capability could be found" outcome for
    this packet's scope, not yet followed by a skill-delegation retry --
    a documented gap, not silently treated as fully resolved impasse
    handling.

    K4.2-H1 D4: candidates is now a List[CapabilityMatch]. No logic
    change needed here -- `if not candidates` (empty check) and
    `c.capability_type` both work unchanged, since CapabilityMatch
    carries capability_type as a top-level field.
    """
    unresolved = [
        step.description for step, candidates in steps_with_candidates
        if not candidates
    ]
    if not unresolved:
        return None
    attempted = sorted({
        c.capability_type
        for _, candidates in steps_with_candidates
        for c in candidates
    })
    return ImpasseRecord(
        reason=(
            f"No matching capability found for {len(unresolved)} of "
            f"{len(steps_with_candidates)} step(s)."
        ),
        unresolved_subgoals=unresolved,
        attempted_capabilities=attempted,
    )


async def plan(
    request: PlannerRequest,
    registry: CapabilityRegistry,
    *,
    event_stream: Optional[EventStream] = None,
) -> PlannerResult:
    """Top-level Planner entry point: Goal -> PlannerResult.

    Architecture: K4 §5's illustrative signature ("async def
    plan(self, goal, context) -> ExecutionPlan"), formalized by K4.2 §5
    as "Planner.plan(request: PlannerRequest) -> PlannerResult." Reuses
    _extract_constraints, check_precheck_rejection (Packet 01) and
    discover_capabilities (Packet 02) directly -- no new precheck,
    extraction, or discovery logic.

    Module-level function, not a Planner class method: consistent with
    every other function already established in this file
    (build_planner_request, build_capability_discovery_request,
    discover_capabilities), rather than introducing a class construct
    nothing else here uses. K4 §5's "Planner.plan(...)" dot-notation is
    read as informal/illustrative -- this document family consistently
    marks its schemas "illustrative," and no section mandates a class
    specifically.

    Does not call governance: K4.2 §2 places the ClarificationPolicy /
    OrchestrationGovernor confidence check "at the Plan Compilation
    gate" (K4 §15) -- a later, not-yet-built stage, not inside
    Planner.plan() itself. K4's own pseudocode for plan() does not call
    governance either. This function produces an ExecutionPlan with a
    correctly estimated confidence; a future Plan Compilation packet is
    what invokes ClarificationPolicy/OrchestrationGovernor against it.
    ClarificationPolicy and the corresponding OrchestrationGovernor
    extension are built and tested standalone in this same packet (see
    core/governance/orchestration_governor.py) precisely so that future
    integration point exists without this function needing to change.

    operation_id (K4.2-H1 D8, ADR-K4.2-H-08): generated fresh on every
    call -- plan() is one of exactly two top-level cognitive-stage
    entrypoints (with compile()) that own operation_id generation.
    trace_id (via get_trace_id(), core/observability/tracer.py) is a
    ContextVar that is already stable across an entire request/trace by
    construction, so a re-plan loop that calls plan() repeatedly within
    the same async context naturally gets the same trace_id and a fresh
    operation_id each time, with no special-case code needed for that
    distinction. discover_capabilities() does NOT get its own
    operation_id -- it shares this one, distinguished by stage_tag
    (D8: "discover_capabilities() shares the parent operation_id with a
    stage_tag discriminator").
    """
    event_stream = event_stream or get_event_stream()
    goal = request.goal
    operation_id = str(uuid.uuid4())

    constraints = await _extract_constraints(
        goal, event_stream=event_stream, operation_id=operation_id,
    )

    precheck_rejection = check_precheck_rejection(constraints)
    if precheck_rejection is not None:
        return dataclasses.replace(precheck_rejection, operation_id=operation_id)

    steps_with_candidates = await _decompose(
        goal, registry, event_stream=event_stream, operation_id=operation_id,
    )

    impasse = _detect_impasse(steps_with_candidates)
    if impasse is not None:
        return PlannerResult(
            status=PlannerStatus.IMPASSE, impasse_detail=impasse,
            operation_id=operation_id,
        )

    ordered = _sequence(steps_with_candidates, constraints)
    with_fallbacks = _fallback_paths(ordered)
    confidence = _estimate_confidence(steps_with_candidates)
    general_purpose_only = _is_general_purpose_only(steps_with_candidates)
    alternatives = _alternative_plans(goal, steps_with_candidates)
    justification = _justify(with_fallbacks, constraints)

    execution_plan = ExecutionPlan(
        goal_id=goal.resource_id,
        steps=with_fallbacks,
        confidence=confidence,
        general_purpose_only=general_purpose_only,
        alternatives=alternatives,
        justification=justification,
        derived_from=[goal.resource_id],
    )

    return PlannerResult(
        status=PlannerStatus.READY_FOR_COMPILATION,
        execution_plan=execution_plan,
        operation_id=operation_id,
    )
