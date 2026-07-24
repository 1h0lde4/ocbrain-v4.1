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

from core.cognitive.intent import Goal
from core.events.event_stream import EventStream, get_event_stream


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
    """
    status: str = PlannerStatus.READY_FOR_COMPILATION
    execution_plan: Optional[Any] = None
    impasse_detail: Optional[ImpasseRecord] = None
    constraints: List[Constraint] = field(default_factory=list)

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
    """
    constraints: List[Constraint] = []
    seen_rationales: set = set()

    for pattern, kind, rationale_type in _EXPLICIT_CONSTRAINT_PATTERNS:
        for match in pattern.finditer(text):
            # Extract context around the match for the rationale.
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 60)
            context = text[start:end].strip()

            # Deduplicate by context to avoid multiple constraints
            # from overlapping patterns on the same text fragment.
            if context in seen_rationales:
                continue
            seen_rationales.add(context)

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


async def extract_constraints(
    goal: Goal,
    *,
    event_stream: Optional[EventStream] = None,
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
            constraints=constraints,
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
