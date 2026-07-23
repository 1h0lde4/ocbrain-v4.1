"""
core/cognitive/intent.py — K4.2.1 Intent Interpreter: Input Normalization + Intent Inference.

Architecture:
    OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md §2 (Intent
    Interpreter behavior), §12 (Data Contracts), §15 (K4.2.1 roadmap entry).
    OCBRAIN_K4_1_FINAL_CONSOLIDATED_ARCHITECTURE.md Part IV (CognitiveArtifact,
    cited by the Implementation Packet as "K4.1 §IV").
Packet:
    IMPLEMENTATION_PACKET_K4_2_1_INTENT_INTERPRETER.md.

Scope (K4.2 §15, K4.2.1 roadmap entry): Input Normalization and multi-hypothesis
Intent inference only. Converts raw request text into a canonical RawRequest,
then into a ranked, confidence-scored List[IntentHypothesis] carried on an
Intent artifact. Goal Formation (K4.2.2) and Planning are explicitly out of
scope for this packet (Implementation Packet §5) and are not implemented here.

Boundary (Implementation Packet §2; K4 §1): produces Cognitive Artifacts only.
Never executes workflows, never invokes a Capability/Adapter through the
governed WorkflowRuntime/AdapterRuntime path, never writes to UnifiedMemory.
The provider_mesh.py call in generate_hypotheses() is the Cognitive Runtime's
own reasoning -- Planner is described the same way ("already LLM-assisted",
K4.1 Part III) -- not a governed capability execution; it is the "provider
routing" dependency the packet's §6 explicitly authorizes for this packet.

Governance: none invoked directly. Per the Implementation Packet's own
Governance review line ("Only inferences are produced; no capabilities
executed"), K4.2.1 does not call GovernanceKernel.evaluate_action() -- that
gate is reserved for Plan Compilation (K4 §15), a later, out-of-scope
milestone.

Learning: none invoked. K4.2.1 produces no LearningCandidate and proposes no
promotion, so K4.1-L's VALIDATE/GOVERN/PROMOTE pipeline is never entered --
the packet's "Learning review: output does not bypass ValidationGate" is
satisfied because there is no learning-tier action in this packet's scope to
bypass anything with.
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
    """Lifecycle values for Intent. Per K1.6 §4, each Resource-shaped type
    owns its own lifecycle enum -- the architecture does not enumerate
    specific values for Intent, so this is the minimal set K4.2.1's own
    scope needs: an Intent is produced (DRAFT while being assembled,
    FINAL once returned). Promotion/supersession lifecycle states belong
    to Reflection/Evaluation (K4 §7/§13), not exercised by this packet.
    """
    DRAFT = "draft"
    FINAL = "final"


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
# Top-level entry point — K4.2 §15 roadmap, K4.2.1
# ─────────────────────────────────────────────────────────────────────────

async def interpret_request(
    raw_text: str,
    *,
    memory: Optional[UnifiedMemory] = None,
    event_stream: Optional[EventStream] = None,
    known_categories: Optional[List[str]] = None,
) -> Intent:
    """Input Normalization + Intent Inference, producing one Intent artifact.

    Architecture: K4.2 §15 roadmap, K4.2.1 entry -- "Objective: Implement
    K4.2.1 Intent Interpreter logic (Normalization and Inference) to
    convert RawRequest into IntentHypothesis objects." Scope stops here --
    Goal Formation (K4.2.2) and Planning are explicitly out of scope for
    this packet (Implementation Packet §5) and are not called from this
    function.

    Events (packet §6): emits exactly cognitive.intent_hypotheses_generated
    and cognitive.intent_interpreted, matching K4.2 §11's event names, via
    the existing EventStream.append() -- no new event-emission mechanism.

    Raises:
        NormalizationRejected: propagated from normalize_request() --
            malformed/adversarial input never reaches inference (K4.2 §2's
            failure-mode table). No event is emitted on this path (see
            NormalizationRejected's docstring).
    """
    event_stream = event_stream or get_event_stream()

    raw_request = normalize_request(raw_text)

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
        lifecycle_state=IntentLifecycle.FINAL,
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

    return intent
