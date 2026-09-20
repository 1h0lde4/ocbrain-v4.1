"""
core/cognitive/authority.py -- REM-004: instruction-authority taxonomy and the
immutable proposal envelope used at the Intent -> Goal boundary.

Architecture:
    docs/architecture/decisions/ADR_KERNEL_06_INSTRUCTION_AUTHORITY_TAXONOMY.md
    (status: DRAFT -- see that ADR's own lifecycle section; this module
    implements the decision it proposes, it does not approve it).
    docs/reports/context-compiler-remediation-register.md (REM-004).
    docs/research/context-engineering/context-authority-threat-model.md
    (CTX-AUTH-001).

Four concepts, deliberately kept apart (never collapsed into one scalar):

    Authority   Who may issue/authorize an *instruction*?  (InstructionAuthority)
    Origin      Where did a value come from?               (Origin -- provenance)
    Trust       How reliable is it as *information*?       NOT modelled here.
                trust_score / truth_status (core/memory/retrieval/context)
                are reliability signals. A retrieved entry with
                trust_score 1.0 is still RETRIEVED_DATA: reliability never
                converts data into an instruction.
    Taint       Was a value influenced by untrusted material? (lineage)

Rules this module enforces (AUTH-1 .. AUTH-16 in the task statement):

    * Authority is DERIVED from Origin by a trusted table, never read from
      content. A label/score/JSON field that *says* it is SYSTEM_POLICY or
      USER_INSTRUCTION is just a string.
    * Authority can never increase implicitly. No promotion API exists;
      assert_no_escalation() is the executable statement of that rule.
    * An accepted proposal can only be minted by the acceptance gate
      (mint_model_proposal / mint_policy_default), is immutable, and
      re-derives its own authority and integrity digest on construction and
      on deserialization -- serialized authority is never trusted.
    * Serialized trusted tokens are UPPER_SNAKE_CASE. Model-controlled labels
      are validated (intent_acceptance.py) to live in a disjoint lowercase
      namespace, so a model string can never be textually confused with an
      authority/origin/reason token in a log, event, or replayed payload.

Information authority is NOT action authorization. Nothing here calls, wraps
or replaces GovernanceKernel; DRIFT-10 keeps Intent/Planner from calling
evaluate_action() at all. "Cognitive reasoning proposes. Kernel governance
authorizes. Execution enforces."

Honest limits (also in the ADR): the mint token is a module-private object,
not a cryptographic capability -- code that deliberately imports a private
symbol is outside this module's threat model (model text and retrieved text
cannot do that). The binding digest detects inconsistency and naive
tampering; it is not authentication of persisted state.
"""
import hashlib
import json
import math
from dataclasses import InitVar, dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────
# Errors -- every one of these is a fail-closed signal, never a soft warning
# ─────────────────────────────────────────────────────────────────────────

class AuthorityError(Exception):
    """Base class for authority-boundary violations."""


class AuthorityEscalationError(AuthorityError):
    """A derivation would have raised authority above its source."""


class AuthorityForgeryError(AuthorityError):
    """An envelope was constructed outside the acceptance gate, or claims an
    authority its origin does not carry."""


class AuthorityIntegrityError(AuthorityError):
    """Serialized/replayed state is malformed, inconsistent, or unknown."""


class StaleAcceptanceError(AuthorityIntegrityError):
    """State was accepted under a different acceptance-policy version."""


# ─────────────────────────────────────────────────────────────────────────
# Taxonomy -- the smallest set the live system needs (REM-004)
# ─────────────────────────────────────────────────────────────────────────

class InstructionAuthority(str, Enum):
    """Who is allowed to *instruct*.

    SYSTEM_POLICY     Trusted runtime policy/configuration. May instruct.
    USER_INSTRUCTION  The end user's own request channel. May instruct.
    MODEL_PROPOSAL    An LLM output. May PROPOSE options; never binds.
    RETRIEVED_DATA    Retrieved/memory/external content. May INFORM; never
                      instructs and never proposes.

    Extension rule: a new class (e.g. a future TOOL_RESULT) is added by ADR,
    with an explicit precedence and origin mapping below. Nothing infers a
    class from content.
    """
    SYSTEM_POLICY = "SYSTEM_POLICY"
    USER_INSTRUCTION = "USER_INSTRUCTION"
    MODEL_PROPOSAL = "MODEL_PROPOSAL"
    RETRIEVED_DATA = "RETRIEVED_DATA"


class Origin(str, Enum):
    """Provenance origin: where a value actually came from. Assigned only by
    trusted runtime code observing the real request/context/model call."""
    SYSTEM = "SYSTEM"
    USER = "USER"
    INTENT_MODEL = "INTENT_MODEL"
    RETRIEVED_SOURCE = "RETRIEVED_SOURCE"
    # Trusted code standing in for a failed/absent model proposal (e.g. the
    # K4.2 §2 open-category fallback). See _AUTHORITY_OF_ORIGIN.
    RUNTIME_DEFAULT = "RUNTIME_DEFAULT"


class CategoryClass(str, Enum):
    """How a proposal's label relates to the trusted category vocabulary.
    Derived by the gate from known_categories membership -- the model's own
    'novel:' prefix is a claim, not evidence."""
    KNOWN_CATEGORY = "KNOWN_CATEGORY"
    OPEN_CATEGORY = "OPEN_CATEGORY"
    POLICY_DEFAULT = "POLICY_DEFAULT"


class Disposition(str, Enum):
    """ACCEPTED   eligible for ranking and selection.
    REJECTED   violates the admission contract; kept only as a bounded
               audit record (reason code + digest + length), no content.
    QUARANTINED shaped like a trusted-runtime token (reserved namespace):
               forensically interesting, so a bounded escaped preview is
               retained. Never enters ranking, selection, prompts or Goals.
    """
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


class ReasonCode(str, Enum):
    LABEL_GRAMMAR = "LABEL_GRAMMAR"
    RESERVED_NAMESPACE = "RESERVED_NAMESPACE"
    DUPLICATE_LABEL = "DUPLICATE_LABEL"
    CANDIDATE_LIMIT = "CANDIDATE_LIMIT"
    SCORE_INVALID = "SCORE_INVALID"


class InferenceOutcome(str, Enum):
    """Why an inference did/did not yield model proposals. A security
    rejection (ALL_REJECTED) is deliberately distinct from 'the model had no
    answer' (NO_OUTPUT / PARSE_FAILURE) and from infrastructure failure."""
    ACCEPTED = "ACCEPTED"
    NO_OUTPUT = "NO_OUTPUT"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    PARSE_FAILURE = "PARSE_FAILURE"
    ALL_REJECTED = "ALL_REJECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ─────────────────────────────────────────────────────────────────────────
# Trusted tables -- read-only views; nothing mutates them at runtime
# ─────────────────────────────────────────────────────────────────────────

_AUTHORITY_OF_ORIGIN: Mapping[Origin, InstructionAuthority] = MappingProxyType({
    Origin.SYSTEM: InstructionAuthority.SYSTEM_POLICY,
    Origin.USER: InstructionAuthority.USER_INSTRUCTION,
    Origin.INTENT_MODEL: InstructionAuthority.MODEL_PROPOSAL,
    Origin.RETRIEVED_SOURCE: InstructionAuthority.RETRIEVED_DATA,
    # ADR decision: a runtime default that replaces a failed/absent model
    # proposal inherits the class of the path it replaces. Recovery may
    # preserve or reduce authority, never raise it.
    Origin.RUNTIME_DEFAULT: InstructionAuthority.MODEL_PROPOSAL,
})

# Precedence is used ONLY to resolve conflicts between sources. It is not a
# score, is never computed from content, and is never compared with a
# confidence value.
_PRECEDENCE: Mapping[InstructionAuthority, int] = MappingProxyType({
    InstructionAuthority.SYSTEM_POLICY: 3,
    InstructionAuthority.USER_INSTRUCTION: 2,
    InstructionAuthority.MODEL_PROPOSAL: 1,
    InstructionAuthority.RETRIEVED_DATA: 0,
})

_INSTRUCTION_BEARING = frozenset({
    InstructionAuthority.SYSTEM_POLICY,
    InstructionAuthority.USER_INSTRUCTION,
})

# Which origins each recorded prompt-input role may legitimately have.
_ROLE_ORIGINS: Mapping[str, frozenset] = MappingProxyType({
    "request": frozenset({Origin.USER}),
    "context": frozenset({Origin.RETRIEVED_SOURCE}),
    # The promoted ontology is read back through memory retrieval, so by
    # channel it is RETRIEVED_DATA. Its use as a matching vocabulary does
    # not change that (no retrieved->system promotion is defined).
    "known_categories": frozenset({Origin.RETRIEVED_SOURCE}),
})

# Origins an AcceptedHypothesis may ever carry. There is intentionally no way
# to mint a hypothesis envelope with USER, SYSTEM or RETRIEVED_SOURCE origin.
_HYPOTHESIS_ORIGINS = frozenset({Origin.INTENT_MODEL, Origin.RUNTIME_DEFAULT})


def authority_for(origin: Origin) -> InstructionAuthority:
    """Authority is a function of trusted origin. Unknown origin fails closed
    (raises); it never defaults to some authority."""
    try:
        return _AUTHORITY_OF_ORIGIN[origin]
    except (KeyError, TypeError):
        raise AuthorityForgeryError("unknown origin has no authority mapping") from None


def outranks(a: InstructionAuthority, b: InstructionAuthority) -> bool:
    return _PRECEDENCE[a] > _PRECEDENCE[b]


def may_instruct(authority: InstructionAuthority) -> bool:
    """Only SYSTEM_POLICY and USER_INSTRUCTION can instruct. A MODEL_PROPOSAL
    proposes; RETRIEVED_DATA informs."""
    return authority in _INSTRUCTION_BEARING


def resolve_conflict(a: InstructionAuthority,
                     b: InstructionAuthority) -> InstructionAuthority:
    """Sources disagree -> the higher-precedence source wins outright. There
    is no averaging, no min()/max() over trust or score, no aggregate."""
    return b if outranks(b, a) else a


def may_influence_interpretation(influencer: InstructionAuthority,
                                 target: InstructionAuthority) -> bool:
    """A lower-authority source must not change how higher-authority content
    is interpreted (retrieved text cannot reinterpret the user's request; a
    model proposal cannot reinterpret system policy)."""
    return not outranks(target, influencer)


def assert_no_escalation(source: InstructionAuthority,
                         derived: InstructionAuthority) -> None:
    """AUTH-5: authority cannot increase implicitly. No trusted promotion
    transition exists in ADR-KERNEL-06, so any increase is an error."""
    if outranks(derived, source):
        raise AuthorityEscalationError(
            f"derivation would raise authority {source.value} -> "
            f"{derived.value}; no trusted transition is defined")


# ─────────────────────────────────────────────────────────────────────────
# Small deterministic helpers
# ─────────────────────────────────────────────────────────────────────────

def content_digest(text: str, *, length: int = 16) -> str:
    """Stable, bounded fingerprint. 'surrogatepass' keeps this total (never
    raises) on odd input while staying deterministic."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:length]


def safe_preview(text: str, limit: int = 48) -> str:
    """Bounded, escaped rendering of untrusted text for audit records: only
    printable ASCII survives verbatim, everything else becomes \\uXXXX."""
    return "".join(
        c if 32 <= ord(c) < 127 else "\\u%04x" % ord(c) for c in text[:limit]
    )


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorityIntegrityError(message)


def _enum(cls, value: Any, what: str):
    if not isinstance(value, str):
        raise AuthorityIntegrityError(f"{what} must be a string token")
    try:
        return cls(value)
    except ValueError:
        raise AuthorityIntegrityError(f"unknown {what}") from None


def _is_real_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _check_keys(data: Mapping[str, Any], expected: frozenset, what: str) -> None:
    _require(isinstance(data, Mapping), f"{what} must be a mapping")
    keys = frozenset(data.keys())
    _require(keys == expected,
             f"{what} has missing or unknown fields (fail closed)")


# ─────────────────────────────────────────────────────────────────────────
# Lineage -- a small, explicit contract; not a universal taint framework
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LineageInput:
    """One prompt input, as recorded by trusted code at the moment the prompt
    was built. Each input keeps its OWN origin/authority; inputs are never
    merged into an aggregate authority."""
    role: str
    origin: Origin
    authority: InstructionAuthority
    digest: str
    size: int

    def __post_init__(self) -> None:
        if self.role not in _ROLE_ORIGINS:
            raise AuthorityForgeryError("unknown lineage input role")
        if self.origin not in _ROLE_ORIGINS[self.role]:
            raise AuthorityForgeryError("origin not permitted for this input role")
        if self.authority is not authority_for(self.origin):
            raise AuthorityForgeryError("authority does not match origin")
        if not (isinstance(self.digest, str) and 0 < len(self.digest) <= 64):
            raise AuthorityIntegrityError("lineage digest must be a bounded string")
        if not (isinstance(self.size, int) and not isinstance(self.size, bool)
                and self.size >= 0):
            raise AuthorityIntegrityError("lineage size must be a non-negative int")

    @classmethod
    def from_text(cls, role: str, origin: Origin, text: str) -> "LineageInput":
        """Authority is derived from origin here -- callers never pass it."""
        return cls(role=role, origin=origin, authority=authority_for(origin),
                   digest=content_digest(text), size=len(text))

    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "origin": self.origin.value,
                "authority": self.authority.value,
                "digest": self.digest, "size": self.size}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LineageInput":
        _check_keys(data, frozenset({"role", "origin", "authority", "digest", "size"}),
                    "lineage input")
        origin = _enum(Origin, data["origin"], "origin")
        claimed = _enum(InstructionAuthority, data["authority"], "authority")
        derived = authority_for(origin)
        if claimed is not derived:
            raise AuthorityForgeryError(
                "serialized authority disagrees with origin; authority is "
                "derived from origin and never trusted from a payload")
        if not isinstance(data["role"], str):
            raise AuthorityIntegrityError("role must be a string")
        return cls(role=data["role"], origin=origin, authority=derived,
                   digest=data["digest"], size=data["size"])


@dataclass(frozen=True)
class InferenceLineage:
    """Everything the trusted runtime observed about ONE model invocation.

    scope_id is the existing request-scope identity (tracer trace_id,
    ADR-K4.2-H-08) -- no second identity system. prompt_digest binds the
    proposal to the exact prompt that produced it (it is also what the
    prompt cache keys on, so a cached completion can never be attributed to
    a different input set).

    Provider identity is intentionally NOT recorded: generate_with_fallback()
    does not expose which provider served a completion, and the prompt cache
    is provider-agnostic, so any recorded provider could be false provenance.
    Provider identity is provenance, not authority, and never affects it.
    """
    scope_id: str
    route: str
    template_version: str
    prompt_digest: str
    inputs: Tuple[LineageInput, ...]

    def __post_init__(self) -> None:
        for name in ("scope_id", "route", "template_version", "prompt_digest"):
            value = getattr(self, name)
            if not (isinstance(value, str) and 0 < len(value) <= 128):
                raise AuthorityIntegrityError(f"lineage {name} must be a bounded string")
        if not isinstance(self.inputs, tuple) or not all(
                isinstance(i, LineageInput) for i in self.inputs):
            raise AuthorityIntegrityError("lineage inputs must be a tuple of LineageInput")

    @property
    def retrieved_data_influence(self) -> bool:
        """TAINT, for this subsystem: True iff retrieved data was part of the
        prompt that produced the proposal. It is conservative on purpose --
        'may have been influenced', never 'was hijacked'. It does not change
        the proposal's authority; it makes the influence auditable."""
        return any(i.authority is InstructionAuthority.RETRIEVED_DATA
                   for i in self.inputs)

    def to_dict(self) -> Dict[str, Any]:
        return {"scope_id": self.scope_id, "route": self.route,
                "template_version": self.template_version,
                "prompt_digest": self.prompt_digest,
                "inputs": [i.to_dict() for i in self.inputs]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InferenceLineage":
        _check_keys(data, frozenset({"scope_id", "route", "template_version",
                                     "prompt_digest", "inputs"}), "lineage")
        raw_inputs = data["inputs"]
        _require(isinstance(raw_inputs, (list, tuple)), "lineage inputs must be a list")
        return cls(scope_id=data["scope_id"], route=data["route"],
                   template_version=data["template_version"],
                   prompt_digest=data["prompt_digest"],
                   inputs=tuple(LineageInput.from_dict(i) for i in raw_inputs))


# ─────────────────────────────────────────────────────────────────────────
# AcceptedHypothesis -- immutable, mint-guarded, self-verifying
# ─────────────────────────────────────────────────────────────────────────

# Module-private mint capability. See the module docstring's honest limits.
_MINT = object()

_MAX_LABEL_LENGTH = 80
_ACCEPTED_KEYS = frozenset({"label", "score", "origin", "authority",
                            "category_class", "policy_version", "position",
                            "binding", "lineage"})


def _binding(label: str, score: float, origin: Origin,
             authority: InstructionAuthority, category_class: CategoryClass,
             lineage: InferenceLineage, policy_version: str, position: int) -> str:
    return content_digest(_canonical_json({
        "label": label, "score": score, "origin": origin.value,
        "authority": authority.value, "category_class": category_class.value,
        "policy_version": policy_version, "position": position,
        "lineage": lineage.to_dict(),
    }), length=32)


def _binding_or_raise(label: Any, score: Any, origin: Origin,
                      authority: InstructionAuthority, category_class: CategoryClass,
                      lineage: Any, policy_version: Any, position: Any) -> str:
    """Mint-path wrapper: a field that cannot be canonically serialized is an
    integrity failure (fail closed), never a raw TypeError."""
    try:
        return _binding(label, score, origin, authority, category_class,
                        lineage, policy_version, position)
    except (TypeError, ValueError, AttributeError):
        raise AuthorityIntegrityError(
            "proposal fields are not canonically serializable") from None


@dataclass(frozen=True)
class AcceptedHypothesis:
    """A model proposal that crossed the acceptance boundary.

    Immutable: label/score/origin/authority/lineage cannot be changed in
    place (frozen), cannot be rebuilt through dataclasses.replace() (the
    mint token is not carried), and re-verify themselves on construction.
    Self-contained: it carries its own authority and lineage, so consumers
    need no ambient state and there is no time-of-check/time-of-use gap.

    Its authority is ALWAYS MODEL_PROPOSAL (or an inherited-not-raised
    MODEL_PROPOSAL for the runtime default). It is never USER_INSTRUCTION or
    SYSTEM_POLICY, whatever its label says.
    """
    label: str
    score: float
    origin: Origin
    authority: InstructionAuthority
    category_class: CategoryClass
    lineage: InferenceLineage
    policy_version: str
    position: int
    binding: str
    _mint: InitVar[Any] = None

    def __post_init__(self, _mint: Any) -> None:
        if _mint is not _MINT:
            raise AuthorityForgeryError(
                "AcceptedHypothesis may only be minted by the acceptance gate")
        if not (isinstance(self.label, str) and 0 < len(self.label) <= _MAX_LABEL_LENGTH):
            raise AuthorityIntegrityError("label must be a bounded non-empty string")
        if not (_is_real_number(self.score) and 0.0 <= self.score <= 1.0):
            raise AuthorityIntegrityError("score must be a finite number in [0, 1]")
        if self.origin not in _HYPOTHESIS_ORIGINS:
            raise AuthorityForgeryError("origin is not permitted for a hypothesis")
        if self.authority is not authority_for(self.origin):
            raise AuthorityForgeryError("authority does not match origin")
        if not isinstance(self.lineage, InferenceLineage):
            raise AuthorityIntegrityError("lineage must be an InferenceLineage")
        if (self.origin is Origin.RUNTIME_DEFAULT) != (
                self.category_class is CategoryClass.POLICY_DEFAULT):
            raise AuthorityForgeryError("category_class inconsistent with origin")
        if not (isinstance(self.policy_version, str) and 0 < len(self.policy_version) <= 64):
            raise AuthorityIntegrityError("policy_version must be a bounded string")
        if not (isinstance(self.position, int) and not isinstance(self.position, bool)
                and self.position >= -1):
            raise AuthorityIntegrityError("position must be an int >= -1")
        expected = _binding(self.label, self.score, self.origin, self.authority,
                            self.category_class, self.lineage,
                            self.policy_version, self.position)
        if self.binding != expected:
            raise AuthorityIntegrityError("binding digest mismatch")

    @property
    def retrieved_data_influence(self) -> bool:
        return self.lineage.retrieved_data_influence

    def assert_scope(self, scope_id: str) -> None:
        """Opt-in consuming-boundary check that this proposal belongs to the
        expected request scope."""
        if self.lineage.scope_id != scope_id:
            raise AuthorityIntegrityError("proposal belongs to a different request scope")

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "score": self.score,
                "origin": self.origin.value, "authority": self.authority.value,
                "category_class": self.category_class.value,
                "policy_version": self.policy_version, "position": self.position,
                "binding": self.binding, "lineage": self.lineage.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *,
                  expected_policy_version: Optional[str] = None) -> "AcceptedHypothesis":
        """Strict, fail-closed reconstruction for replay/inspection.

        This is CONSISTENCY VERIFICATION, not an authority grant: authority is
        re-derived from origin and a disagreeing payload is rejected; unknown
        fields/values are rejected; the binding digest is recomputed; a
        different policy version is rejected as stale. An authoritative
        decision on replayed data must re-run the deterministic gate.
        """
        _check_keys(data, _ACCEPTED_KEYS, "accepted hypothesis")
        origin = _enum(Origin, data["origin"], "origin")
        claimed = _enum(InstructionAuthority, data["authority"], "authority")
        derived = authority_for(origin)
        if claimed is not derived:
            raise AuthorityForgeryError(
                "serialized authority disagrees with origin; authority is "
                "derived from origin and never trusted from a payload")
        policy_version = data["policy_version"]
        if expected_policy_version is not None and policy_version != expected_policy_version:
            raise StaleAcceptanceError(
                "accepted under a different acceptance-policy version")
        return cls(
            label=data["label"], score=data["score"], origin=origin,
            authority=derived,
            category_class=_enum(CategoryClass, data["category_class"], "category_class"),
            lineage=InferenceLineage.from_dict(data["lineage"]),
            policy_version=policy_version, position=data["position"],
            binding=data["binding"], _mint=_MINT,
        )


def mint_model_proposal(*, label: str, score: float, category_class: CategoryClass,
                        lineage: InferenceLineage, policy_version: str,
                        position: int) -> AcceptedHypothesis:
    """The only constructor for a model-derived envelope. Origin is fixed to
    INTENT_MODEL and authority is derived -- there is no parameter through
    which a caller (or a model string) can choose either."""
    if category_class not in (CategoryClass.KNOWN_CATEGORY, CategoryClass.OPEN_CATEGORY):
        raise AuthorityForgeryError("model proposals are KNOWN_CATEGORY or OPEN_CATEGORY")
    origin = Origin.INTENT_MODEL
    authority = authority_for(origin)
    return AcceptedHypothesis(
        label=label, score=score, origin=origin, authority=authority,
        category_class=category_class, lineage=lineage,
        policy_version=policy_version, position=position,
        binding=_binding_or_raise(label, score, origin, authority, category_class,
                                  lineage, policy_version, position),
        _mint=_MINT)


def mint_policy_default(*, label: str, score: float, lineage: InferenceLineage,
                        policy_version: str) -> AcceptedHypothesis:
    """Trusted-code stand-in used when no model proposal is eligible. It
    carries only a fixed policy token -- no rejected content is ever copied
    into it -- and inherits (does not raise) the failed path's authority."""
    origin = Origin.RUNTIME_DEFAULT
    authority = authority_for(origin)
    category_class = CategoryClass.POLICY_DEFAULT
    return AcceptedHypothesis(
        label=label, score=score, origin=origin, authority=authority,
        category_class=category_class, lineage=lineage,
        policy_version=policy_version, position=-1,
        binding=_binding_or_raise(label, score, origin, authority, category_class,
                                  lineage, policy_version, -1),
        _mint=_MINT)


# ─────────────────────────────────────────────────────────────────────────
# ProposalDisposition -- bounded audit record for rejected/quarantined input
# ─────────────────────────────────────────────────────────────────────────

_DISPOSITION_KEYS = frozenset({"position", "disposition", "reason_code", "origin",
                               "authority", "label_digest", "label_length",
                               "score_claim", "label_preview"})
_MAX_PREVIEW = 48
# safe_preview() escapes each non-printable-ASCII source character as \uXXXX, up
# to \u10ffff (8 chars) for the highest code point. Found by adversarial
# self-review: the bound used to be 6/char, tighter than the producer's worst
# case. Unreachable today (quarantined labels are ASCII by construction) but it
# would have broken as soon as a quarantine reason covered non-ASCII input.
_MAX_PREVIEW_ESCAPED = _MAX_PREVIEW * 8


@dataclass(frozen=True)
class ProposalDisposition:
    """Evidence of a decision, not a source of authority. Holds no raw label
    (REJECTED) or a bounded escaped preview (QUARANTINED); never re-enters a
    prompt, ranking, or a Goal."""
    position: int
    disposition: Disposition
    reason_code: ReasonCode
    origin: Origin
    authority: InstructionAuthority
    label_digest: str
    label_length: int
    score_claim: Optional[float]
    label_preview: Optional[str] = None

    def __post_init__(self) -> None:
        if self.disposition not in (Disposition.REJECTED, Disposition.QUARANTINED):
            raise AuthorityIntegrityError("a disposition record is REJECTED or QUARANTINED")
        if self.origin is not Origin.INTENT_MODEL or \
                self.authority is not InstructionAuthority.MODEL_PROPOSAL:
            raise AuthorityForgeryError("dispositions describe MODEL_PROPOSAL input only")
        if not (isinstance(self.position, int) and not isinstance(self.position, bool)
                and self.position >= 0):
            raise AuthorityIntegrityError("position must be a non-negative int")
        if not (isinstance(self.label_digest, str) and 0 < len(self.label_digest) <= 64):
            raise AuthorityIntegrityError("label_digest must be a bounded string")
        if not (isinstance(self.label_length, int) and not isinstance(self.label_length, bool)
                and self.label_length >= 0):
            raise AuthorityIntegrityError("label_length must be a non-negative int")
        if self.score_claim is not None and not (
                _is_real_number(self.score_claim) and 0.0 <= self.score_claim <= 1.0):
            raise AuthorityIntegrityError("score_claim must be None or a number in [0, 1]")
        if self.label_preview is not None:
            if self.disposition is not Disposition.QUARANTINED:
                raise AuthorityIntegrityError("only QUARANTINED records carry a preview")
            if not (isinstance(self.label_preview, str)
                    and len(self.label_preview) <= _MAX_PREVIEW_ESCAPED):
                raise AuthorityIntegrityError("label_preview must be bounded")

    def to_dict(self) -> Dict[str, Any]:
        return {"position": self.position, "disposition": self.disposition.value,
                "reason_code": self.reason_code.value, "origin": self.origin.value,
                "authority": self.authority.value, "label_digest": self.label_digest,
                "label_length": self.label_length, "score_claim": self.score_claim,
                "label_preview": self.label_preview}

    def to_event_dict(self) -> Dict[str, Any]:
        """Bounded, content-free view for EventStream payloads: no label text
        and no preview -- only reason, digest, length, position, score claim."""
        return {"position": self.position, "disposition": self.disposition.value,
                "reason_code": self.reason_code.value,
                "label_digest": self.label_digest,
                "label_length": self.label_length, "score_claim": self.score_claim}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProposalDisposition":
        _check_keys(data, _DISPOSITION_KEYS, "disposition")
        origin = _enum(Origin, data["origin"], "origin")
        claimed = _enum(InstructionAuthority, data["authority"], "authority")
        if claimed is not authority_for(origin):
            raise AuthorityForgeryError("serialized authority disagrees with origin")
        return cls(
            position=data["position"],
            disposition=_enum(Disposition, data["disposition"], "disposition"),
            reason_code=_enum(ReasonCode, data["reason_code"], "reason_code"),
            origin=origin, authority=claimed,
            label_digest=data["label_digest"], label_length=data["label_length"],
            score_claim=data["score_claim"], label_preview=data["label_preview"])
