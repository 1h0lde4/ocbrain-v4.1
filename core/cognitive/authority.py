"""
core/cognitive/authority.py -- REM-004 / ADR-KERNEL-06: the immutable proposal
envelope, per-request citation table and lineage used at the Intent -> Goal
boundary.

The authority TAXONOMY is not defined here. ``AuthorityLevel``
(core/memory/retrieval/context/context.py) is the repository's REM-004
taxonomy and this module uses it as-is -- no parallel enum, no new member.
This module adds only what ADR-KERNEL-06 (accepted design: "authority is
inherited, never inferred") leaves to the implementation pass:

    * CitableBlock / InferenceLineage.citable -- the per-request table of
      citable sources: the ACTUAL context blocks a prompt enumerated
      (recorded by trusted code, ref "[N]") plus the raw request itself
      (always present, ref "request", context.py's own AuthorityLevel.USER
      -- "the current turn's actual human instruction"). A model's citation
      is a pointer into this table; nothing else makes a source citable.
    * VerifiedProvenance -- what a model's citation resolves to, or nothing.
    * AcceptedHypothesis -- an immutable, mint-guarded, self-verifying record
      of a model proposal: its own authority (always GENERATED: a model can
      never produce USER/SYSTEM content), its verified provenance (or the
      reason it has none), and the lineage of the invocation that made it.

Four concepts, kept apart (never collapsed into one scalar):

    Authority   Who may issue an *instruction*?   AuthorityLevel
    Origin      Where did a value come from?      Origin (provenance origin)
    Trust       How reliable is it as *information*? ProvenanceRecord.trust_score
                / truth_status. Not modelled here and never converted into
                authority: a block with trust_score 1.0 is still RETRIEVED.
    Taint       Was it influenced by untrusted material? InferenceLineage

Rules enforced here:

    * Authority is DERIVED from trusted origin, or INHERITED from a verified
      source's own AuthorityLevel. It is never read from content, from a
      label, from a score, or from anything a model wrote.
    * "Candidate exists" is not "candidate is trusted": a proposal without a
      verified citation still exists, with provenance_status != VERIFIED and
      no verified provenance. There is no path from an unverified citation to
      a verified one.
    * Authority never increases implicitly. Only SYSTEM and USER can
      instruct; a proposal's own authority is GENERATED whatever it cites.
    * The three non-instructing levels (RETRIEVED, EXTERNAL, GENERATED) have
      NO defined precedence among themselves -- AuthorityLevel does not
      define one and this module does not invent one (owner decision, see the
      ADR). They are peers for the escalation check.

Information authority is NOT action authorization. Nothing here calls, wraps
or replaces GovernanceKernel; DRIFT-10 keeps Intent/Planner from calling
evaluate_action(). "Cognitive reasoning proposes. Kernel governance
authorizes. Execution enforces."

Honest limits: the mint token is a module-private object, not a cryptographic
capability -- code that deliberately imports a private symbol is outside this
threat model (model text and retrieved text cannot do that). The binding
digest detects inconsistency and naive tampering; it is not authentication of
persisted state.
"""
import hashlib
import json
import math
import re
from dataclasses import InitVar, dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from core.memory.retrieval.context.context import AuthorityLevel


# ─────────────────────────────────────────────────────────────────────────
# Errors -- every one of these is a fail-closed signal, never a soft warning
# ─────────────────────────────────────────────────────────────────────────

class AuthorityError(Exception):
    """Base class for authority-boundary violations."""


class AuthorityEscalationError(AuthorityError):
    """A derivation would have raised authority above its source."""


class AuthorityForgeryError(AuthorityError):
    """An envelope was constructed outside the acceptance gate, or claims an
    authority or provenance its trusted inputs do not carry."""


class AuthorityIntegrityError(AuthorityError):
    """Serialized/replayed state is malformed, inconsistent, or unknown."""


class StaleAcceptanceError(AuthorityIntegrityError):
    """State was accepted under a different acceptance-policy version."""


# ─────────────────────────────────────────────────────────────────────────
# Closed vocabularies (this module's own; the authority taxonomy is not one)
# ─────────────────────────────────────────────────────────────────────────

class Origin(str, Enum):
    """Provenance origin: where a value actually came from. Assigned only by
    trusted runtime code observing the real request/context/model call."""
    SYSTEM = "SYSTEM"
    USER = "USER"
    INTENT_MODEL = "INTENT_MODEL"
    RETRIEVED_SOURCE = "RETRIEVED_SOURCE"
    # Trusted code standing in for a failed/absent model proposal (K4.2 §2
    # open-category fallback).
    RUNTIME_DEFAULT = "RUNTIME_DEFAULT"


class CategoryClass(str, Enum):
    """How a proposal's label relates to the trusted category vocabulary --
    derived by the gate from known_categories membership; the model's own
    'novel:' prefix is a claim, not evidence."""
    KNOWN_CATEGORY = "KNOWN_CATEGORY"
    OPEN_CATEGORY = "OPEN_CATEGORY"
    POLICY_DEFAULT = "POLICY_DEFAULT"


class ProvenanceStatus(str, Enum):
    """Why a proposal does or does not carry verified provenance. Every
    status other than VERIFIED means the same thing to a consumer: no
    authoritative provenance (fail closed, uniformly)."""
    VERIFIED = "VERIFIED"
    UNCITED = "UNCITED"
    MALFORMED_CITATION = "MALFORMED_CITATION"
    UNRESOLVED_CITATION = "UNRESOLVED_CITATION"
    AMBIGUOUS_CITATION = "AMBIGUOUS_CITATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"        # trusted-code default: nothing was cited


class ReasonCode(str, Enum):
    """Contract rejections: bounded-resource / well-formedness hygiene. None of
    these establishes or denies authority."""
    SCORE_INVALID = "SCORE_INVALID"
    DUPLICATE_LABEL = "DUPLICATE_LABEL"
    CANDIDATE_LIMIT = "CANDIDATE_LIMIT"
    LABEL_INVALID = "LABEL_INVALID"


class InferenceOutcome(str, Enum):
    """Why an inference did/did not yield model proposals. A contract
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

_AUTHORITY_OF_ORIGIN: Mapping[Origin, AuthorityLevel] = MappingProxyType({
    Origin.SYSTEM: AuthorityLevel.SYSTEM,
    Origin.USER: AuthorityLevel.USER,
    Origin.INTENT_MODEL: AuthorityLevel.GENERATED,
    Origin.RETRIEVED_SOURCE: AuthorityLevel.RETRIEVED,
    # A runtime default that replaces a failed/absent model proposal inherits
    # the class of the path it replaces: recovery preserves, never raises,
    # authority.
    Origin.RUNTIME_DEFAULT: AuthorityLevel.GENERATED,
})

# Rank exists ONLY to state the escalation rule. SYSTEM > USER >
# {RETRIEVED, EXTERNAL, GENERATED}; the last three share one rank because
# AuthorityLevel defines no order among them and none is invented here.
_RANK: Mapping[AuthorityLevel, int] = MappingProxyType({
    AuthorityLevel.SYSTEM: 2,
    AuthorityLevel.USER: 1,
    AuthorityLevel.RETRIEVED: 0,
    AuthorityLevel.EXTERNAL: 0,
    AuthorityLevel.GENERATED: 0,
})

INSTRUCTION_BEARING = frozenset({AuthorityLevel.SYSTEM, AuthorityLevel.USER})

# Which origins each recorded prompt-input role may legitimately have.
_ROLE_ORIGINS: Mapping[str, frozenset] = MappingProxyType({
    "request": frozenset({Origin.USER}),
    "context": frozenset({Origin.RETRIEVED_SOURCE}),
    # The promoted ontology is read back through memory retrieval, so by
    # channel it is RETRIEVED. Its use as a matching vocabulary does not
    # change that (no retrieved->system promotion is defined).
    "known_categories": frozenset({Origin.RETRIEVED_SOURCE}),
})

# Origins an AcceptedHypothesis may ever carry. There is intentionally no way
# to mint a hypothesis envelope with USER, SYSTEM or RETRIEVED_SOURCE origin.
_HYPOTHESIS_ORIGINS = frozenset({Origin.INTENT_MODEL, Origin.RUNTIME_DEFAULT})

REQUEST_REF = "request"
_BLOCK_REF = re.compile(r"\[[1-9][0-9]{0,2}\]")


def _valid_citable_ref(ref: Any) -> bool:
    """The only two shapes a source may legitimately have: the fixed token
    naming the raw request, or a bracketed per-request block index."""
    return ref == REQUEST_REF or (isinstance(ref, str) and bool(_BLOCK_REF.fullmatch(ref)))


def authority_for(origin: Origin) -> AuthorityLevel:
    """Authority is a function of trusted origin. Unknown origin fails closed
    (raises); it never defaults to some level."""
    try:
        return _AUTHORITY_OF_ORIGIN[origin]
    except (KeyError, TypeError):
        raise AuthorityForgeryError("unknown origin has no authority mapping") from None


def may_instruct(level: AuthorityLevel) -> bool:
    """Only SYSTEM and USER can instruct. RETRIEVED / EXTERNAL / GENERATED
    inform or propose; they never bind."""
    return level in INSTRUCTION_BEARING


def outranks(a: AuthorityLevel, b: AuthorityLevel) -> bool:
    """True iff `a` strictly outranks `b` for the escalation rule. Peers among
    the non-instructing levels never outrank one another."""
    return _RANK[a] > _RANK[b]


def assert_no_escalation(source: AuthorityLevel, derived: AuthorityLevel) -> None:
    """Authority cannot increase implicitly. No trusted promotion transition
    exists in ADR-KERNEL-06 / -07, so any increase is an error."""
    if outranks(derived, source):
        raise AuthorityEscalationError(
            f"derivation would raise authority {source.value} -> "
            f"{derived.value}; no trusted transition is defined")


# ─────────────────────────────────────────────────────────────────────────
# Small deterministic helpers
# ─────────────────────────────────────────────────────────────────────────

def request_citable_block(request_text: str) -> "CitableBlock":
    """The user's own current-turn request is always citable, always
    AuthorityLevel.USER (context.py's definition: "the current turn's actual
    human instruction"). This is the ONE mechanism by which a model proposal
    can legitimately have USER-authority provenance (ADR-KERNEL-06 Mechanism
    A). Not assigned by the model: ref/entry_id/authority are fixed; only the
    digest depends on the (trusted) request text. Called once per inference,
    by trusted code, before the citable table is otherwise built.
    """
    return CitableBlock(ref=REQUEST_REF, entry_id=REQUEST_REF,
                        authority=AuthorityLevel.USER,
                        digest=content_digest(request_text))


def content_digest(text: str, *, length: int = 16) -> str:
    """Stable, bounded fingerprint. 'surrogatepass' keeps this total (never
    raises) on odd input while staying deterministic."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:length]


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorityIntegrityError(message)


def _enum(cls: Any, value: Any, what: str) -> Any:
    if not isinstance(value, str):
        raise AuthorityIntegrityError(f"{what} must be a string token")
    try:
        return cls(value)
    except ValueError:
        raise AuthorityIntegrityError(f"unknown {what}") from None


def _is_real_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _is_int(value: Any, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _bounded_str(value: Any, limit: int = 128) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit


def _check_keys(data: Mapping[str, Any], expected: frozenset, what: str) -> None:
    _require(isinstance(data, Mapping), f"{what} must be a mapping")
    _require(frozenset(data.keys()) == expected,
             f"{what} has missing or unknown fields (fail closed)")


# ─────────────────────────────────────────────────────────────────────────
# Citation table + verified provenance (ADR-KERNEL-06, Mechanism A)
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CitableBlock:
    """One block of the ACTUAL context assembled for one request, as the
    prompt enumerated it. Recorded by trusted code from the real
    ContextBlock -- never from anything a model wrote. `authority` is the
    block's own ProvenanceRecord.authority, assigned by its trusted
    construction site."""
    ref: str
    entry_id: str
    authority: AuthorityLevel
    digest: str

    def __post_init__(self) -> None:
        if not _valid_citable_ref(self.ref):
            raise AuthorityIntegrityError(
                'citable ref must be "request" or a bracketed index like "[2]"')
        if not _bounded_str(self.entry_id, 256):
            raise AuthorityIntegrityError("citable entry_id must be a bounded string")
        if not isinstance(self.authority, AuthorityLevel):
            raise AuthorityIntegrityError("citable authority must be an AuthorityLevel")
        if not _bounded_str(self.digest, 64):
            raise AuthorityIntegrityError("citable digest must be a bounded string")

    def to_dict(self) -> Dict[str, Any]:
        return {"ref": self.ref, "entry_id": self.entry_id,
                "authority": self.authority.value, "digest": self.digest}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CitableBlock":
        _check_keys(data, frozenset({"ref", "entry_id", "authority", "digest"}), "citable block")
        return cls(ref=data["ref"], entry_id=data["entry_id"],
                   authority=_enum(AuthorityLevel, data["authority"], "authority"),
                   digest=data["digest"])


@dataclass(frozen=True)
class VerifiedProvenance:
    """What a model's citation resolved to. Exists only when the cited ref is
    in THIS request's citation table; the authority is the source's own
    (inherited, never inferred) -- USER when the source is the raw request
    itself, or whatever a context block's own trusted-assigned authority is
    (RETRIEVED today; the taxonomy also defines SYSTEM/EXTERNAL/GENERATED for
    future construction sites)."""
    ref: str
    source_id: str
    authority: AuthorityLevel
    block_digest: str

    @classmethod
    def from_block(cls, block: CitableBlock) -> "VerifiedProvenance":
        return cls(ref=block.ref, source_id=block.entry_id,
                   authority=block.authority, block_digest=block.digest)

    def matches(self, block: CitableBlock) -> bool:
        return (self.ref == block.ref and self.source_id == block.entry_id
                and self.authority is block.authority
                and self.block_digest == block.digest)

    def to_dict(self) -> Dict[str, Any]:
        return {"ref": self.ref, "source_id": self.source_id,
                "authority": self.authority.value, "block_digest": self.block_digest}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VerifiedProvenance":
        _check_keys(data, frozenset({"ref", "source_id", "authority", "block_digest"}),
                    "verified provenance")
        return cls(ref=data["ref"], source_id=data["source_id"],
                   authority=_enum(AuthorityLevel, data["authority"], "authority"),
                   block_digest=data["block_digest"])


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
    authority: AuthorityLevel
    digest: str
    size: int

    def __post_init__(self) -> None:
        if self.role not in _ROLE_ORIGINS:
            raise AuthorityForgeryError("unknown lineage input role")
        if self.origin not in _ROLE_ORIGINS[self.role]:
            raise AuthorityForgeryError("origin not permitted for this input role")
        if self.authority is not authority_for(self.origin):
            raise AuthorityForgeryError("authority does not match origin")
        if not _bounded_str(self.digest, 64):
            raise AuthorityIntegrityError("lineage digest must be a bounded string")
        if not _is_int(self.size, 0):
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
        claimed = _enum(AuthorityLevel, data["authority"], "authority")
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
    proposal to the exact prompt that produced it (the prompt cache keys on
    the same prompt, so a cached completion cannot be attributed to a
    different input set). `citable` is the per-request citation table: the
    real blocks the prompt enumerated. A citation is verified ONLY against
    this table.

    Provider identity is intentionally NOT recorded: generate_with_fallback()
    does not expose which provider served a completion and the prompt cache is
    provider-agnostic, so any recorded provider could be false provenance.

    `citable` ALWAYS contains request_citable_block()'s entry (ref "request",
    AuthorityLevel.USER) -- a model citing it is not an escalation: it is
    verification that the model is telling the truth about a candidate
    genuinely tracing to the user's own words, which is exactly the invariant
    ADR-KERNEL-06 asks the acceptance gate to check. The residual risk this
    accepts -- a fabricated "request" citation on injected content, since
    "request" always resolves -- is named explicitly in the ADR (the trigger
    condition for evaluating Option C) and is not something this module can
    close; see TestResidualRisk and live_citation_check.py, which measures it
    operationally.
    """
    scope_id: str
    route: str
    template_version: str
    prompt_digest: str
    inputs: Tuple[LineageInput, ...]
    citable: Tuple[CitableBlock, ...] = ()

    def __post_init__(self) -> None:
        for name in ("scope_id", "route", "template_version", "prompt_digest"):
            if not _bounded_str(getattr(self, name)):
                raise AuthorityIntegrityError(f"lineage {name} must be a bounded string")
        if not isinstance(self.inputs, tuple) or not all(
                isinstance(i, LineageInput) for i in self.inputs):
            raise AuthorityIntegrityError("lineage inputs must be a tuple of LineageInput")
        if not isinstance(self.citable, tuple) or not all(
                isinstance(c, CitableBlock) for c in self.citable):
            raise AuthorityIntegrityError("lineage citable must be a tuple of CitableBlock")
        refs = [c.ref for c in self.citable]
        if len(set(refs)) != len(refs):
            raise AuthorityIntegrityError("citable refs must be unique within one request")

    @property
    def retrieved_data_influence(self) -> bool:
        """TAINT, for this subsystem: True iff retrieved data was part of the
        prompt that produced the proposal. Conservative on purpose ('may have
        been influenced', never 'was hijacked'); it does not change a
        proposal's authority, it makes the influence auditable."""
        return any(i.authority is AuthorityLevel.RETRIEVED for i in self.inputs)

    def resolve(self, ref: str) -> Optional[CitableBlock]:
        """Deterministic lookup of a cited ref in THIS request's table."""
        for block in self.citable:
            if block.ref == ref:
                return block
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"scope_id": self.scope_id, "route": self.route,
                "template_version": self.template_version,
                "prompt_digest": self.prompt_digest,
                "inputs": [i.to_dict() for i in self.inputs],
                "citable": [c.to_dict() for c in self.citable]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InferenceLineage":
        _check_keys(data, frozenset({"scope_id", "route", "template_version",
                                     "prompt_digest", "inputs", "citable"}), "lineage")
        raw_inputs, raw_citable = data["inputs"], data["citable"]
        _require(isinstance(raw_inputs, (list, tuple)), "lineage inputs must be a list")
        _require(isinstance(raw_citable, (list, tuple)), "lineage citable must be a list")
        return cls(scope_id=data["scope_id"], route=data["route"],
                   template_version=data["template_version"],
                   prompt_digest=data["prompt_digest"],
                   inputs=tuple(LineageInput.from_dict(i) for i in raw_inputs),
                   citable=tuple(CitableBlock.from_dict(c) for c in raw_citable))


# ─────────────────────────────────────────────────────────────────────────
# AcceptedHypothesis -- immutable, mint-guarded, self-verifying
# ─────────────────────────────────────────────────────────────────────────

# Module-private mint capability. See the module docstring's honest limits.
_MINT = object()

MAX_LABEL_LENGTH = 200
_ACCEPTED_KEYS = frozenset({"label", "score", "origin", "authority", "category_class",
                            "provenance_status", "provenance", "policy_version",
                            "position", "binding", "lineage"})


def _binding(label: str, score: float, origin: Origin, authority: AuthorityLevel,
             category_class: CategoryClass, status: ProvenanceStatus,
             provenance: Optional[VerifiedProvenance], lineage: InferenceLineage,
             policy_version: str, position: int) -> str:
    try:
        return content_digest(_canonical_json({
            "label": label, "score": score, "origin": origin.value,
            "authority": authority.value, "category_class": category_class.value,
            "provenance_status": status.value,
            "provenance": provenance.to_dict() if provenance is not None else None,
            "policy_version": policy_version, "position": position,
            "lineage": lineage.to_dict(),
        }), length=32)
    except (TypeError, ValueError):
        # A field that cannot be canonically serialized cannot be bound.
        raise AuthorityIntegrityError(
            "proposal fields are not canonically serializable") from None


@dataclass(frozen=True)
class AcceptedHypothesis:
    """A model proposal that crossed the acceptance boundary.

    Immutable: no field can be assigned after acceptance (frozen), the record
    cannot be rebuilt through dataclasses.replace() (the mint token is not
    carried), and it re-verifies itself on construction. Self-contained: it
    carries its own authority, provenance and lineage, so consumers need no
    ambient state and there is no time-of-check/time-of-use gap.

    `authority` is ALWAYS the class of a model-generated proposal (GENERATED)
    -- never USER or SYSTEM, whatever the proposal says or cites.
    `provenance` is the source authority the system VERIFIED for the cited
    block, or None; `provenance_status` says why. A proposal exists whether or
    not it is verified; only a verified one carries authoritative provenance.
    """
    label: str
    score: float
    origin: Origin
    authority: AuthorityLevel
    category_class: CategoryClass
    provenance_status: ProvenanceStatus
    provenance: Optional[VerifiedProvenance]
    lineage: InferenceLineage
    policy_version: str
    position: int
    binding: str
    _mint: InitVar[Any] = None

    def __post_init__(self, _mint: Any) -> None:
        if _mint is not _MINT:
            raise AuthorityForgeryError(
                "AcceptedHypothesis may only be minted by the acceptance gate")
        if not (isinstance(self.label, str) and 0 < len(self.label) <= MAX_LABEL_LENGTH):
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
        if not isinstance(self.provenance_status, ProvenanceStatus):
            raise AuthorityIntegrityError("provenance_status must be a ProvenanceStatus")
        if (self.provenance_status is ProvenanceStatus.VERIFIED) != (
                self.provenance is not None):
            raise AuthorityForgeryError("provenance present iff status is VERIFIED")
        if (self.origin is Origin.RUNTIME_DEFAULT) != (
                self.provenance_status is ProvenanceStatus.NOT_APPLICABLE):
            raise AuthorityForgeryError("NOT_APPLICABLE is for the runtime default only")
        if self.provenance is not None:
            # A verified provenance must be one of THIS request's real blocks.
            block = self.lineage.resolve(self.provenance.ref)
            if block is None or not self.provenance.matches(block):
                raise AuthorityForgeryError(
                    "verified provenance is not in this request's citation table")
        if not _bounded_str(self.policy_version, 64):
            raise AuthorityIntegrityError("policy_version must be a bounded string")
        if not _is_int(self.position, -1):
            raise AuthorityIntegrityError("position must be an int >= -1")
        expected = _binding(self.label, self.score, self.origin, self.authority,
                            self.category_class, self.provenance_status,
                            self.provenance, self.lineage, self.policy_version,
                            self.position)
        if self.binding != expected:
            raise AuthorityIntegrityError("binding digest mismatch")

    @property
    def retrieved_data_influence(self) -> bool:
        return self.lineage.retrieved_data_influence

    @property
    def has_verified_provenance(self) -> bool:
        return self.provenance_status is ProvenanceStatus.VERIFIED

    def assert_scope(self, scope_id: str) -> None:
        """Opt-in consuming-boundary check that this proposal belongs to the
        expected request scope."""
        if self.lineage.scope_id != scope_id:
            raise AuthorityIntegrityError("proposal belongs to a different request scope")

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "score": self.score,
                "origin": self.origin.value, "authority": self.authority.value,
                "category_class": self.category_class.value,
                "provenance_status": self.provenance_status.value,
                "provenance": (self.provenance.to_dict()
                               if self.provenance is not None else None),
                "policy_version": self.policy_version, "position": self.position,
                "binding": self.binding, "lineage": self.lineage.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *,
                  expected_policy_version: Optional[str] = None) -> "AcceptedHypothesis":
        """Strict, fail-closed reconstruction for replay/inspection.

        This is CONSISTENCY VERIFICATION, not an authority grant: authority is
        re-derived from origin and a disagreeing payload is rejected; unknown
        fields/values are rejected; a claimed provenance must be present in
        the payload's own citation table; the binding digest is recomputed; a
        different policy version is rejected as stale. An authoritative
        decision on replayed data must re-run the deterministic gate.
        """
        _check_keys(data, _ACCEPTED_KEYS, "accepted hypothesis")
        origin = _enum(Origin, data["origin"], "origin")
        claimed = _enum(AuthorityLevel, data["authority"], "authority")
        derived = authority_for(origin)
        if claimed is not derived:
            raise AuthorityForgeryError(
                "serialized authority disagrees with origin; authority is "
                "derived from origin and never trusted from a payload")
        policy_version = data["policy_version"]
        if expected_policy_version is not None and policy_version != expected_policy_version:
            raise StaleAcceptanceError(
                "accepted under a different acceptance-policy version")
        raw_prov = data["provenance"]
        return cls(
            label=data["label"], score=data["score"], origin=origin,
            authority=derived,
            category_class=_enum(CategoryClass, data["category_class"], "category_class"),
            provenance_status=_enum(ProvenanceStatus, data["provenance_status"],
                                    "provenance_status"),
            provenance=(VerifiedProvenance.from_dict(raw_prov)
                        if raw_prov is not None else None),
            lineage=InferenceLineage.from_dict(data["lineage"]),
            policy_version=policy_version, position=data["position"],
            binding=data["binding"], _mint=_MINT,
        )


def mint_model_proposal(*, label: str, score: float, category_class: CategoryClass,
                        provenance_status: ProvenanceStatus,
                        provenance: Optional[VerifiedProvenance],
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
        category_class=category_class, provenance_status=provenance_status,
        provenance=provenance, lineage=lineage, policy_version=policy_version,
        position=position,
        binding=_binding(label, score, origin, authority, category_class,
                         provenance_status, provenance, lineage, policy_version,
                         position),
        _mint=_MINT)


def mint_policy_default(*, label: str, score: float, lineage: InferenceLineage,
                        policy_version: str) -> AcceptedHypothesis:
    """Trusted-code stand-in used when no model proposal is eligible. It
    carries only a fixed policy token -- no rejected content is ever copied
    into it -- and inherits (does not raise) the failed path's authority."""
    origin = Origin.RUNTIME_DEFAULT
    authority = authority_for(origin)
    category_class = CategoryClass.POLICY_DEFAULT
    status = ProvenanceStatus.NOT_APPLICABLE
    return AcceptedHypothesis(
        label=label, score=score, origin=origin, authority=authority,
        category_class=category_class, provenance_status=status, provenance=None,
        lineage=lineage, policy_version=policy_version, position=-1,
        binding=_binding(label, score, origin, authority, category_class, status,
                         None, lineage, policy_version, -1),
        _mint=_MINT)


# ─────────────────────────────────────────────────────────────────────────
# ProposalRejection -- bounded audit record for a contract rejection
# ─────────────────────────────────────────────────────────────────────────

_REJECTION_KEYS = frozenset({"position", "reason_code", "origin", "authority",
                             "label_digest", "label_length", "score_claim"})


@dataclass(frozen=True)
class ProposalRejection:
    """Evidence of a decision, not a source of authority. Holds a digest and a
    length, never label text; never re-enters a prompt, ranking or a Goal."""
    position: int
    reason_code: ReasonCode
    origin: Origin
    authority: AuthorityLevel
    label_digest: str
    label_length: int
    score_claim: Optional[float]

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, ReasonCode):
            raise AuthorityIntegrityError("reason_code must be a ReasonCode")
        if self.origin is not Origin.INTENT_MODEL or \
                self.authority is not AuthorityLevel.GENERATED:
            raise AuthorityForgeryError("rejections describe model-generated input only")
        if not _is_int(self.position, 0):
            raise AuthorityIntegrityError("position must be a non-negative int")
        if not _bounded_str(self.label_digest, 64):
            raise AuthorityIntegrityError("label_digest must be a bounded string")
        if not _is_int(self.label_length, 0):
            raise AuthorityIntegrityError("label_length must be a non-negative int")
        if self.score_claim is not None and not (
                _is_real_number(self.score_claim) and 0.0 <= self.score_claim <= 1.0):
            raise AuthorityIntegrityError("score_claim must be None or a number in [0, 1]")

    def to_dict(self) -> Dict[str, Any]:
        return {"position": self.position, "reason_code": self.reason_code.value,
                "origin": self.origin.value, "authority": self.authority.value,
                "label_digest": self.label_digest, "label_length": self.label_length,
                "score_claim": self.score_claim}

    def to_event_dict(self) -> Dict[str, Any]:
        """Bounded, content-free view for EventStream payloads."""
        return {"position": self.position, "reason_code": self.reason_code.value,
                "label_digest": self.label_digest,
                "label_length": self.label_length, "score_claim": self.score_claim}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProposalRejection":
        _check_keys(data, _REJECTION_KEYS, "rejection")
        origin = _enum(Origin, data["origin"], "origin")
        claimed = _enum(AuthorityLevel, data["authority"], "authority")
        if claimed is not authority_for(origin):
            raise AuthorityForgeryError("serialized authority disagrees with origin")
        return cls(position=data["position"],
                   reason_code=_enum(ReasonCode, data["reason_code"], "reason_code"),
                   origin=origin, authority=claimed,
                   label_digest=data["label_digest"], label_length=data["label_length"],
                   score_claim=data["score_claim"])
