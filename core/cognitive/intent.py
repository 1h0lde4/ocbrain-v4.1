"""
core/cognitive/intent.py — K4.2.1 Intent Interpreter + K4.2.2 Goal Formation.

Architecture:
    OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md §1 (interpret()
    public entrypoint), §2 (Intent Interpreter behavior), §4 (Goal Formation),
    §9 (Confidence Lifecycle), §10 (Provenance), §11 (Event Integration),
    §12 (Data Contracts), §13 (State Machines), §15 (K4.2.1 + K4.2.2 roadmap).
    OCBRAIN_K4_1_FINAL_CONSOLIDATED_ARCHITECTURE.md Part IV (CognitiveArtifact).
Packet:
    IMPLEMENTATION_PACKET_K4_2_1_INTENT_INTERPRETER.md.

Scope:
    K4.2.1 (Input Normalization + multi-hypothesis Intent inference) and
    K4.2.2 (Goal Formation: Intent -> one or more Goal objects).
    K4.2 §15 K4.2.2: "Modules: core/cognitive/intent.py (Goal Formation
    logic). Interfaces: Goal dataclass (§12), interpret() public
    entrypoint (§1)."

    K4.2 §1: "interpret(raw_request) -> Goal, covering Input
    Normalization → Intent Interpretation → Goal Formation."

Boundary (K4 §1): produces Cognitive Artifacts only. Never executes
workflows, never invokes a Capability/Adapter through the governed
WorkflowRuntime/AdapterRuntime path, never writes to UnifiedMemory.

Governance: none invoked directly. Per K4.2 §4, Goal validation is
schema-validation only at this stage; governance evaluation is reserved
for Plan Compilation (K4 §15, a later milestone).

Learning: none invoked. Neither K4.2.1 nor K4.2.2 produces
LearningCandidates or proposes promotions.
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from core.events.event_stream import EventStream, get_event_stream
from core.memory.assembly import ContextAssemblyEngine
from core.memory.unified_memory import UnifiedMemory, get_unified_memory
from core.provider_mesh import generate_with_fallback, resolve_provider


# ─────────────────────────────────────────────────────────────────────────
# CognitiveArtifact — K4.1 Final Consolidated Architecture, Part IV
# ─────────────────────────────────────────────────────────────────────────

@runtime_checkable
class CognitiveArtifact(Protocol):
    """Structural contract every Cognitive Runtime output satisfies.

    Architecture: OCBRAIN_K4_1_FINAL_CONSOLIDATED_ARCHITECTURE.md Part IV --
    "Cognitive Artifact (a specialization of the K1.6 Resource Protocol):
    resource_id, produced_by, derived_from, lifecycle_state."

    Implemented as a Protocol, not an ABC or dataclass base, matching the
    reasoning K1.6 gave for Resource itself: structural satisfaction lets a
    concrete dataclass (Intent, below) satisfy the contract without a forced
    inheritance chain. No existing importable Resource base class was found
    in the repository to inherit from -- core/capabilities/resource.py
    implements the unrelated K2.3 HTTPClientResource/ModelResource pair for
    Adapter resource binding, not a general Resource Protocol -- so this
    defines the contract standalone, matching K4.1 Part IV's field list
    exactly and no further.
    """
    resource_id: str
    produced_by: str
    derived_from: List[str]
    lifecycle_state: str


class IntentLifecycle:
    """Intent lifecycle states from K4.2 §13:

    "draft → interpreted → [clarification_pending → clarified] → superseded"

    K4.2.1/K4.2.2 scope: Intent Interpretation produces Intents in DRAFT
    and transitions them to INTERPRETED once inference completes.
    clarification_pending/clarified belong to ClarificationPolicy
    escalation (K4.2 §2/§9, later milestones). superseded is set once
    the Intent's Goal(s) are formed and the Intent is no longer current.
    """
    DRAFT = "draft"
    INTERPRETED = "interpreted"
    CLARIFICATION_PENDING = "clarification_pending"
    CLARIFIED = "clarified"
    SUPERSEDED = "superseded"


# ─────────────────────────────────────────────────────────────────────────
# IntentHypothesis — K4.2 §12
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class IntentHypothesis:
    """One candidate interpretation of a request.

    Architecture: K4.2 §12 -- "IntentHypothesis: label, embedding_ref
    (optional), score." An embedded field-set, not independently
    identified -- K4.2 §12's own closing note places Constraint/PlannerHint
    in this category for the same reason (no resource_id, no derived_from,
    no lifecycle_state of its own): it only ever exists inside
    Intent.hypotheses.
    """
    label: str
    score: float
    embedding_ref: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────
# Intent.dimensions — K4.2 §2 ("deliberately small")
# ─────────────────────────────────────────────────────────────────────────

class IntentModality:
    """The four values K4.2 §2 enumerates for Intent.dimensions.modality:
    "task_request | information_query | feedback_on_prior_interaction |
    clarification_response". Distinct from Input Normalization's own,
    separate "modality detection" responsibility (input channel/format,
    e.g. text vs. voice) -- see normalize_request() once added in the next
    implementation step.
    """
    TASK_REQUEST = "task_request"
    INFORMATION_QUERY = "information_query"
    FEEDBACK_ON_PRIOR_INTERACTION = "feedback_on_prior_interaction"
    CLARIFICATION_RESPONSE = "clarification_response"


@dataclass
class IntentDimensions:
    """Architecture: K4.2 §2 -- "Intent.dimensions is deliberately small:
    category (matched ontology entry, or 'novel'), modality (one of four
    enumerated values, IntentModality above), complexity_estimate (a cheap,
    coarse signal Planner may consume as a PlannerHint, K4.1 Final
    Consolidated Part III/§5)." complexity_estimate's exact type is not
    pinned by the architecture (§12's schemas are "illustrative... not
    frozen"); a float in [0, 1] is used here for consistency with every
    other confidence/score value in this document family.
    """
    category: str
    modality: str
    complexity_estimate: float


# ─────────────────────────────────────────────────────────────────────────
# Intent — K4.2 §12, specializes CognitiveArtifact (K4.1 Part IV)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class Intent:
    """A ranked, confidence-scored interpretation of one request.

    Architecture: K4.2 §12 -- "Intent (CognitiveArtifact): resource_id,
    raw_request, hypotheses: List[IntentHypothesis], selected:
    IntentHypothesis, confidence: float, dimensions: {category, modality,
    complexity_estimate}, ontology_ref: Optional[str], derived_from:
    List[str], lifecycle_state: str."

    Field note (flagged, not silently decided): K4.2 §12 headers this type
    "Intent (CognitiveArtifact)", declaring it a specialization of the base
    contract K4.1 Part IV defines with four fields, including produced_by.
    §12 re-lists three of those four (resource_id, derived_from,
    lifecycle_state) alongside Intent's own fields and does not re-list
    produced_by. Read here as an omission in what §12 itself calls an
    "illustrative... not frozen" list, not as an instruction to drop a
    field the cited base contract requires -- produced_by is included.

    raw_request is stored as normalized text (str) rather than an embedded
    RawRequest object: RawRequest (added in the next implementation step)
    is an ephemeral parameter object with no identity of its own, so there
    is nothing to reference by ID (K1.6 §6) -- its content is captured
    directly instead.
    """
    resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    produced_by: str = "IntentInterpreter"
    raw_request: str = ""
    hypotheses: List[IntentHypothesis] = field(default_factory=list)
    selected: Optional[IntentHypothesis] = None
    confidence: float = 0.0
    dimensions: Optional[IntentDimensions] = None
    ontology_ref: Optional[str] = None
    derived_from: List[str] = field(default_factory=list)
    lifecycle_state: str = IntentLifecycle.DRAFT

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# RawRequest — canonical output of Input Normalization
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class RawRequest:
    """Canonical, normalized request text.

    Architecture: K4.2 §2 names this type ("Output: a canonical
    RawRequest") but gives it no field-level schema in §12 the way
    Intent/IntentHypothesis get. Consistent with K1.6's "ephemeral
    parameter object" category (constructed, consumed, discarded within
    one invocation; no resource_id, no persisted identity -- the same
    category K4.1 Part III/§5 places PlannerRequest/PlannerResult in),
    this is kept to the one field every description of normalization
    supports, rather than speculating further ones.
    """
    text: str


class NormalizationRejected(Exception):
    """Raised by normalize_request() when input fails the malformed/
    injection screen.

    Architecture: K4.2 §2's failure-mode table -- "Rejected at Input
    Normalization, before Intent inference runs at all; logged as a
    distinct failure category, never reaches [inference]."

    Ordinary Python control flow, not a new Kernel-level contract: no
    event is emitted on this path. The packet's own Events line (§6)
    authorizes exactly two events, neither a rejection event, and Input
    Normalization is explicitly "ordinary, deterministic code... not
    model-assisted reasoning" (K4.2 §2) -- it does not carry the
    Worker-level governance/event ceremony reserved for inference.
    """
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


_MAX_REQUEST_LENGTH = 8000

_INJECTION_PATTERNS = (
    re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I),
    re.compile(r"disregard (all |any )?(previous|prior|above) instructions", re.I),
    re.compile(r"you are now (in )?(dan|developer mode|jailbreak)", re.I),
    re.compile(r"reveal (your |the )?system prompt", re.I),
)


def normalize_request(raw_text: Optional[str]) -> RawRequest:
    """Deterministic Input Normalization.

    Architecture: K4.2 §2 -- "Input Normalization... deliberately ordinary,
    deterministic code, not model-assisted reasoning. Responsibilities:
    encoding/whitespace normalization, modality detection, and a
    lightweight prompt-injection/malformed-input screen, reusing the same
    screening discipline already adopted for the Knowledge Acquisition
    pipeline (OCBRAIN_EXTERNAL_REPO_STUDY.md §5, Skill_Seekers-derived),
    now applied at the front door instead of only the knowledge-ingestion
    door. Output: a canonical RawRequest. Rejected input never reaches
    Intent inference."

    "Modality detection" here is Input Normalization's own responsibility
    (input channel/format) and is distinct from Intent.dimensions.modality
    (a semantic-act classifier computed later during inference -- see
    _detect_modality() and IntentModality, added in the next implementation
    step). No reusable, directly-importable screening utility for
    front-door user input was found in the repository during the
    Repository Audit (the only "injection"/"malformed" hits under core/
    were unrelated dependency-injection and validation code inside the
    memory/retrieval modules), so this is new, minimal, narrowly-scoped
    infrastructure -- authorized because K4.2 §2 explicitly requires it,
    and "lightweight" is honored by keeping the check narrow rather than
    building a general-purpose classifier.

    Raises:
        NormalizationRejected: if raw_text is empty/whitespace-only,
            exceeds a sane length bound, or matches an injection pattern.
    """
    if raw_text is None or not raw_text.strip():
        raise NormalizationRejected("empty_or_whitespace_only")

    text = raw_text.strip()
    # Encoding normalization: drop control characters other than tab/newline.
    text = "".join(ch for ch in text if ch in ("\n", "\t") or ord(ch) >= 0x20)
    # Whitespace normalization.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if not text:
        raise NormalizationRejected("empty_after_normalization")

    if len(text) > _MAX_REQUEST_LENGTH:
        raise NormalizationRejected("exceeds_max_length")

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise NormalizationRejected("injection_pattern_match")

    # Modality (input-channel) detection: OCBrain has no live input channel
    # other than text today -- voice/multimodal workers are a later,
    # unbuilt phase. Kept a deliberate single-value pass-through rather
    # than building unused multimodal detection ahead of any channel that
    # would actually produce one (Future Compatibility Review: does not
    # hard-code future assumptions, does not consume future
    # responsibilities).

    return RawRequest(text=text)


# ─────────────────────────────────────────────────────────────────────────
# Intent inference — K4.2 §2
# ─────────────────────────────────────────────────────────────────────────

_HYPOTHESIS_PROMPT_TEMPLATE = """You are the Intent Interpreter of a governed cognitive runtime.
Given a user request and retrieved context, produce up to {n} ranked
candidate interpretations of what the user wants.

Output one candidate per line, in the exact form:
label | score

score is a number between 0.00 and 1.00, highest confidence first.

Known intent categories (may be empty on a fresh system): {categories}
If a candidate does not match a known category, prefix its label with
"novel:".

Context:
{context}

Request:
{request}

Candidates:"""


def _build_hypothesis_prompt(raw_request: RawRequest, context: str,
                              known_categories: List[str]) -> str:
    return _HYPOTHESIS_PROMPT_TEMPLATE.format(
        n=5,
        categories=", ".join(known_categories) if known_categories else "(none yet)",
        context=context or "(no retrieved context)",
        request=raw_request.text,
    )


_CANDIDATE_LINE = re.compile(
    r"^[ \t]*(?P<label>[^|\n]+?)[ \t]*\|[ \t]*(?P<score>[01](?:\.\d+)?)[ \t]*$",
    re.MULTILINE,
)


def _parse_hypotheses(completion: Optional[str]) -> List[IntentHypothesis]:
    """Parses the provider's raw completion into IntentHypothesis objects.

    Malformed or unparseable lines are skipped rather than raised on --
    inference degrading to fewer (or zero, handled by the caller) parsed
    hypotheses is the documented open-category fallback path (K4.2 §2),
    not a new failure mode requiring its own handling.
    """
    hypotheses: List[IntentHypothesis] = []
    for match in _CANDIDATE_LINE.finditer(completion or ""):
        label = match.group("label").strip()
        if not label:
            continue
        score = max(0.0, min(1.0, float(match.group("score"))))
        hypotheses.append(IntentHypothesis(label=label, score=score))
    return hypotheses


def _detect_modality(text: str) -> str:
    """Minimal heuristic for Intent.dimensions.modality. K4.2 §2 mandates
    the four possible values (IntentModality); it does not mandate a
    classification method, so this is a deliberately simple, replaceable
    heuristic over the normalized text -- the four VALUES it chooses among
    are architecture-cited, the heuristic itself is not."""
    stripped = text.strip()
    lowered = stripped.lower()

    feedback_starts = (
        "thanks", "thank you", "that's wrong", "that is wrong", "no,",
        "actually,", "that didn't", "that did not", "not quite",
        "that's not", "that is not",
    )
    if any(lowered.startswith(w) for w in feedback_starts):
        return IntentModality.FEEDBACK_ON_PRIOR_INTERACTION

    question_starts = (
        "what", "who", "when", "where", "why", "how", "which",
        "is ", "are ", "does ", "do ", "can ", "could ", "would ",
    )
    if stripped.endswith("?") or any(lowered.startswith(w) for w in question_starts):
        return IntentModality.INFORMATION_QUERY

    if len(stripped) <= 40 and not stripped.endswith("."):
        return IntentModality.CLARIFICATION_RESPONSE

    return IntentModality.TASK_REQUEST


def _estimate_complexity(text: str, hypothesis_count: int) -> float:
    """Cheap, coarse complexity signal (K4.2 §2: "a cheap, coarse signal
    Planner may consume as a PlannerHint"). Deliberately simple: length
    and hypothesis-count are the two signals already available for free
    at this point in the pipeline with no additional model call. Bounded
    to [0, 1] for consistency with the rest of this document family's
    confidence/score conventions -- §12 gives no explicit type or formula.
    """
    length_signal = min(1.0, len(text) / 500.0)
    ambiguity_signal = min(1.0, max(0, hypothesis_count - 1) / 4.0)
    return round(min(1.0, 0.6 * length_signal + 0.4 * ambiguity_signal), 2)


async def generate_hypotheses(
    raw_request: RawRequest,
    *,
    memory: Optional[UnifiedMemory] = None,
    known_categories: Optional[List[str]] = None,
) -> List[IntentHypothesis]:
    """Multi-hypothesis Intent inference.

    Architecture: K4.2 §2 -- "Not a classifier. A governed cognitive
    subsystem... Intent inference produces a ranked N-best list of
    IntentHypothesis, not a single label... reusing the existing
    context_assembler/RetrievalFusionEngine path for context -- no new
    retrieval mechanism... hypotheses [are] scored against the Intent
    Ontology's structured categories where a match exists, degrade to a
    looser, lower-confidence open-category hypothesis where none does."

    Reuses core.memory.assembly.ContextAssemblyEngine ("the existing
    context_assembler" -- confirmed live at core/memory/assembly.py, the
    canonical Retrieval Runtime per KERNEL_ARCHITECTURE_v1.0.md §13.1) and
    core.provider_mesh.generate_with_fallback ("provider routing", packet
    §6's explicit dependency) -- no new retrieval or provider-selection
    logic. generate_with_fallback already health-ranks providers, retries
    on failure, and routes through the existing prompt cache and
    safe_llm_call semaphore/timeout -- reusing it rather than calling
    Provider.generate() directly avoids duplicating that machinery.

    known_categories represents the Intent Ontology's current L3 entries
    (K4.2 §2's "Intent memory" paragraph). Looking those up is not part of
    this packet's scope (normalization and inference only); an empty/None
    list is the correct, expected input on a system where nothing has
    been promoted yet, and a caller that has access to the ontology may
    supply it.
    """
    memory = memory or get_unified_memory()

    try:
        context = await ContextAssemblyEngine(memory).assemble_context(raw_request.text)
    except Exception:
        # assemble_context() already degrades to "" on no results; a hard
        # failure in retrieval should not block inference -- proceed with
        # no context rather than propagate.
        context = ""

    prompt = _build_hypothesis_prompt(raw_request, context, known_categories or [])

    hypotheses: List[IntentHypothesis] = []
    try:
        completion = await generate_with_fallback(
            resolve_provider("intent_interpreter"), prompt,
        )
        hypotheses = _parse_hypotheses(completion)
    except Exception:
        hypotheses = []

    if not hypotheses:
        # Open-category degrade path (K4.2 §2) -- every provider failed,
        # or none produced a parseable candidate.
        hypotheses = [IntentHypothesis(label="novel", score=0.1)]

    hypotheses.sort(key=lambda h: h.score, reverse=True)
    return hypotheses


# ─────────────────────────────────────────────────────────────────────────
# Goal — K4.2 §4, §12, §13 (K4.2.2)
# ─────────────────────────────────────────────────────────────────────────

class GoalLifecycle:
    """Goal lifecycle states from K4.2 §13:

    "draft → verified → [refinement_pending → refined] → compiled → superseded"

    K4.2.2 scope: Goal Formation produces Goals in DRAFT and transitions
    them to VERIFIED upon successful schema validation (or graceful
    fallback). refinement_pending/refined belong to SupervisorWorker-driven
    revision (K4.2 §4, later milestones). compiled belongs to Plan
    Compilation (K4.3). superseded belongs to re-interpretation.
    """
    DRAFT = "draft"
    VERIFIED = "verified"
    REFINEMENT_PENDING = "refinement_pending"
    REFINED = "refined"
    COMPILED = "compiled"
    SUPERSEDED = "superseded"


@dataclass
class Goal:
    """A verified, disambiguated target state derived from an Intent.

    Architecture: K4.2 §12 -- "Goal (CognitiveArtifact): resource_id,
    intent_id, structured_form: dict, sub_goals: List[str], alternatives:
    List[str], confidence: float, lifecycle_state: str."

    CognitiveArtifact inherited fields (K4.1 Part IV): resource_id,
    produced_by, derived_from, lifecycle_state. The same field-note from
    Intent applies: §12's "illustrative... not frozen" list omits
    produced_by and derived_from from the Goal-specific listing, but
    headers Goal as "(CognitiveArtifact)", so the base contract's fields
    are included.

    K4.2 §4: "structured_form is schema-validated against the matched
    Intent Ontology category, never a bare NL string internally; degrades
    to a looser structure with lower confidence when no match exists."

    K4.2 §4: "Goal.sub_goals: List[str], references only" -- string IDs
    of sibling Goals from compound-request splitting.

    K4.2 §10: "Goal provenance: intent_id (§4) + derived_from."
    """
    resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    produced_by: str = "IntentInterpreter"
    intent_id: str = ""
    structured_form: Dict[str, Any] = field(default_factory=dict)
    sub_goals: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 0.0
    derived_from: List[str] = field(default_factory=list)
    lifecycle_state: str = GoalLifecycle.DRAFT

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ─────────────────────────────────────────────────────────────────────────
# Goal Formation — K4.2 §4 (K4.2.2)
# ─────────────────────────────────────────────────────────────────────────

# Confidence penalty applied when no ontology schema is available for
# validation (K4.2 §4: "degrades to a looser structure with lower
# confidence when no match exists"). This is an implementation choice for
# the penalty magnitude -- K4.2 does not specify an exact value.
_SCHEMA_VALIDATION_PENALTY = 0.1


def _validate_structured_form(
    intent: Intent,
    ontology_schemas: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple:
    """Validate structured_form against ontology schema if available.

    Architecture: K4.2 §4 -- "structured_form is schema-validated against
    the matched Intent Ontology category... degrades to a looser structure
    with lower confidence when no match exists."

    K4.2 §15 K4.2.2 validation: "schema-validation failure correctly
    lowers confidence rather than hard-failing."

    Returns:
        (structured_form, confidence_adjustment, validated) where
        confidence_adjustment is the amount to subtract from the inherited
        confidence (0.0 if validated, _SCHEMA_VALIDATION_PENALTY if not).
    """
    category = "novel"
    if intent.dimensions:
        category = intent.dimensions.category

    # Build the structured_form from the Intent's selected hypothesis.
    # K4.2 §4: "never a bare NL string internally" -- even without an
    # ontology, the form carries structured fields.
    structured_form: Dict[str, Any] = {
        "description": intent.selected.label if intent.selected else "unknown",
        "category": category,
        "raw_request": intent.raw_request,
    }

    # If an ontology schema exists for this category, validate against it.
    if ontology_schemas and category in ontology_schemas:
        schema = ontology_schemas[category]
        # Check required fields from the ontology schema are present.
        # Implementation choice: a simple required-fields check. The
        # architecture does not specify a schema language.
        required = schema.get("required_fields", [])
        missing = [f for f in required if f not in structured_form]
        if missing:
            # Schema validation failure: lower confidence, do not fail.
            return structured_form, _SCHEMA_VALIDATION_PENALTY, False
        return structured_form, 0.0, True

    # No ontology schema available: graceful degradation.
    # K4.2 §4: "degrades to a looser structure with lower confidence"
    return structured_form, _SCHEMA_VALIDATION_PENALTY, False


# Patterns for compound-goal detection (K4.2 §4).
_COMPOUND_SEPARATORS = re.compile(
    r"\b(?:and then|then|after that|also|additionally)\b",
    re.IGNORECASE,
)


def _split_compound_goals(text: str) -> List[str]:
    """Detect independently-plannable pieces in a compound request.

    Architecture: K4.2 §4 -- "A single compound request may mint more
    than one Goal at Goal Formation time... when the request is already
    recognizable as independently-plannable pieces -- e.g., 'audit the
    memory system and then propose a migration plan' is two Goals before
    Planner ever runs."

    K4.2 §4 also: "Planner's own decomposition (K4 §5, unchanged)
    operates within one Goal, breaking it into ordered PlanSteps.
    Conflating these two levels was a real risk worth naming explicitly
    and closing."

    Implementation choice: the architecture does not specify the exact
    detection method. A deliberately simple heuristic using known compound
    separators is used here. This is not Planner decomposition -- it only
    separates obviously compound requests at the syntactic level.
    """
    parts = _COMPOUND_SEPARATORS.split(text)
    parts = [p.strip() for p in parts if p.strip()]
    # Only split if we get multiple substantive parts.
    if len(parts) > 1:
        return parts
    return [text]


def form_goals(
    intent: Intent,
    *,
    ontology_schemas: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Goal]:
    """Goal Formation: Intent → one or more Goal objects.

    Architecture: K4.2 §4 -- "One Intent mints one or more Goals (via the
    hierarchy split); every Goal carries intent_id provenance back to the
    Intent that produced it."

    K4.2 §9 (Confidence Lifecycle): "Goal.confidence (adjusted by
    schema-validation outcome, §4)" -- confidence is inherited from
    Intent.confidence and then reduced if schema validation fails.

    K4.2 §10 (Provenance): "Goal provenance: intent_id (§4) +
    derived_from."

    This function is deterministic given the same Intent and ontology
    state: the compound-splitting heuristic and schema-validation are
    both pure, non-model-assisted code (consistent with K4.2 §2's design
    principle that non-model-assisted steps are preferred at boundary
    seams for auditability).

    Does NOT invoke Planner, Governance, Learning, or any Kernel execution
    path.
    """
    # 1. Detect compound requests (K4.2 §4).
    parts = _split_compound_goals(intent.raw_request)

    goals: List[Goal] = []
    for part_text in parts:
        # Create a lightweight Intent-like view for each part if compound,
        # or use the original Intent for single requests.
        # Implementation choice: for compound goals, we use the same
        # selected hypothesis and category since the compound split is
        # syntactic, not semantic -- each sub-goal shares the parent
        # intent's interpretation context.
        structured_form, confidence_penalty, validated = _validate_structured_form(
            intent, ontology_schemas,
        )

        # For compound goals, adjust the structured_form description
        # to reflect the specific part.
        if len(parts) > 1:
            structured_form = dict(structured_form)  # copy
            structured_form["description"] = part_text

        # K4.2 §9: confidence inherited from Intent, adjusted by validation.
        goal_confidence = max(0.0, intent.confidence - confidence_penalty)

        goal = Goal(
            intent_id=intent.resource_id,
            structured_form=structured_form,
            confidence=goal_confidence,
            derived_from=[intent.resource_id],
            lifecycle_state=GoalLifecycle.VERIFIED if validated else GoalLifecycle.DRAFT,
        )
        goals.append(goal)

    # Wire sub_goals cross-references (K4.2 §4: "references only").
    if len(goals) > 1:
        all_ids = [g.resource_id for g in goals]
        for goal in goals:
            goal.sub_goals = [gid for gid in all_ids if gid != goal.resource_id]

    # Carry alternatives from the Intent's non-selected hypotheses
    # (K4.2 §2: "Multiple competing hypotheses... carried, never
    # discarded before Plan Compilation").
    alternative_labels = [
        h.label for h in intent.hypotheses
        if intent.selected and h.label != intent.selected.label
    ]
    for goal in goals:
        goal.alternatives = alternative_labels

    return goals


# ─────────────────────────────────────────────────────────────────────────
# Top-level entry point — K4.2 §1, §15 (K4.2.1 + K4.2.2)
# ─────────────────────────────────────────────────────────────────────────

async def interpret_request(
    raw_text: str,
    *,
    memory: Optional[UnifiedMemory] = None,
    event_stream: Optional[EventStream] = None,
    known_categories: Optional[List[str]] = None,
    ontology_schemas: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Goal]:
    """Input Normalization → Intent Inference → Goal Formation.

    Architecture: K4.2 §1 -- "interpret(raw_request) -> Goal, covering
    Input Normalization → Intent Interpretation → Goal Formation."

    K4.2 §15, K4.2.2 entry -- "Interfaces: Goal dataclass (§12),
    interpret() public entrypoint (§1)."

    Returns a list of Goal objects because K4.2 §4 specifies that
    compound requests may produce multiple Goals ("One Intent mints one
    or more Goals"). A single-goal request returns a list of length 1.

    Events: emits cognitive.intent_hypotheses_generated and
    cognitive.intent_interpreted (K4.2.1, unchanged), then
    cognitive.goal_formed (K4.2.2, K4.2 §11 / K4 §12).

    Raises:
        NormalizationRejected: propagated from normalize_request() --
            malformed/adversarial input never reaches inference (K4.2 §2).
    """
    event_stream = event_stream or get_event_stream()

    # ── K4.2.1: Input Normalization ──────────────────────────────────
    raw_request = normalize_request(raw_text)

    # ── K4.2.1: Intent Inference ─────────────────────────────────────
    hypotheses = await generate_hypotheses(
        raw_request, memory=memory, known_categories=known_categories,
    )

    await event_stream.append(
        "cognitive.intent_hypotheses_generated",
        source="IntentInterpreter",
        payload={
            "hypothesis_count": len(hypotheses),
            "labels": [h.label for h in hypotheses],
        },
    )

    selected = hypotheses[0] if hypotheses else None
    dimensions = IntentDimensions(
        category=selected.label if selected else "novel",
        modality=_detect_modality(raw_request.text),
        complexity_estimate=_estimate_complexity(raw_request.text, len(hypotheses)),
    )

    intent = Intent(
        raw_request=raw_request.text,
        hypotheses=hypotheses,
        selected=selected,
        confidence=selected.score if selected else 0.0,
        dimensions=dimensions,
        lifecycle_state=IntentLifecycle.INTERPRETED,
    )

    await event_stream.append(
        "cognitive.intent_interpreted",
        source="IntentInterpreter",
        payload={
            "intent_id": intent.resource_id,
            "selected_label": selected.label if selected else None,
            "confidence": intent.confidence,
        },
    )

    # ── K4.2.2: Goal Formation ───────────────────────────────────────
    goals = form_goals(intent, ontology_schemas=ontology_schemas)

    for goal in goals:
        await event_stream.append(
            "cognitive.goal_formed",
            source="IntentInterpreter",
            payload={
                "goal_id": goal.resource_id,
                "intent_id": goal.intent_id,
                "confidence": goal.confidence,
                "sub_goal_count": len(goal.sub_goals),
            },
        )

    return goals
