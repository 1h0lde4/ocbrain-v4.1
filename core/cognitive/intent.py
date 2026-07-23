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
