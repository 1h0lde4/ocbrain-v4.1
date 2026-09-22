"""
core/cognitive/intent_acceptance.py -- REM-004 / ADR-KERNEL-06 acceptance
boundary for Intent hypotheses (CTX-AUTH-001b, Mechanism A).

Architecture: docs/architecture/decisions/ADR_KERNEL_06_VERIFIABLE_HYPOTHESIS_PROVENANCE.md
(ACCEPTED -- the governing design) and, for the implementation-level choices
that ADR leaves open, ADR_KERNEL_07_HYPOTHESIS_PROVENANCE_ENVELOPE.md (DRAFT).

Pipeline this module is the middle stage of:

    raw completion --(intent._parse_hypotheses: SYNTAX only)--> ParsedProposal[]
        --(accept_proposals: THIS module)--> AcceptedHypothesis[] + ProposalRejection[]
        --> ranked by score --> Intent.selected

What it does (deterministic, dependency-free, no I/O, no LLM, no global state):

  * Citation verification -- the heart of ADR-KERNEL-06. The model supplies
    only a POINTER: either the fixed token "request" (the user's own current-
    turn words) or a bracketed index like "[2]" naming one of the numbered
    context sources enumerated in the prompt. The system resolves that
    pointer against THIS request's actual citation table
    (InferenceLineage.citable, which always includes "request" and, when
    context was assembled, its real blocks) and derives the provenance
    authority from the source it finds -- USER for "request", or a context
    block's own authority (RETRIEVED today) -- or finds nothing. Authority is
    inherited from a verified source, never inferred: from a label, a score,
    an ordering, a keyword, a prefix, or the model's word.
  * Fail closed, uniformly: no citation, a malformed one, an unresolvable
    one, or contradictory ones all give the same outcome -- the proposal
    EXISTS, with no verified provenance. There is no path from an unverified
    citation to a verified one, and no carve-out for an UNCITED proposal: the
    ADR is explicit that even a candidate plausibly synthesized purely from
    the request is not promoted to USER authority merely for existing --
    USER authority requires the model to actually cite "request" and that
    citation to verify (which it always does, since the request always
    exists -- see the module-level residual-risk note this implies).
  * Bounded-resource hygiene: invalid scores, over-long/empty labels and
    duplicates are rejected as auditable records; the candidate set is
    capped.

RESIDUAL RISK, stated plainly (ADR-KERNEL-06 names this as the trigger
condition for evaluating Option C, and live_citation_check.py measures it
operationally, not this module): because "request" always resolves, a model
that is *told* (e.g. by injected content) to cite "request" on fabricated
content will have that citation verify. This module cannot distinguish an
honest "this really came from the user" from a fabricated one -- Mechanism A
verifies that a citation POINTS somewhere real, not that the model's claim
about WHY it cited that source is true. See TestResidualRisk.

What it deliberately does NOT do:

  * It does not remove a proposal for the SHAPE of its label. ADR-KERNEL-06
    rules out structural/lexical heuristics as authority proxies, and the
    owner's CTX-AUTH-001b test forbids shape/cap/order enforcement from
    standing in for the provenance check. (An earlier draft of this work
    used a label-form contract; it was removed for exactly that reason.)
  * It does not rank by verification. A proposal that cites a retrieved
    block is attributed to retrieved material -- that is attribution, not
    trust -- so verification is metadata for policy, not a ranking tier.
  * It does not authorize any action and does not import GovernanceKernel
    (DRIFT-10): "Cognitive reasoning proposes. Kernel governance authorizes."

Duplicate labels collapse to the LOWEST claimed score and to the provenance
they all agree on; any disagreement between occurrences (verified vs. not,
or different sources) is AMBIGUOUS_CITATION -- deterministic and independent
of completion order.
"""
import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.cognitive.authority import (
    MAX_LABEL_LENGTH,
    REQUEST_REF,
    AcceptedHypothesis,
    CategoryClass,
    InferenceLineage,
    Origin,
    ProposalRejection,
    ProvenanceStatus,
    ReasonCode,
    VerifiedProvenance,
    authority_for,
    content_digest,
    mint_model_proposal,
    mint_policy_default,
)

POLICY_VERSION = "intent-acceptance/2"

OPEN_CATEGORY_TOKEN = "novel"
FALLBACK_SCORE = 0.1          # K4.2 §2 open-category degrade path (unchanged)
MAX_STORED_REJECTIONS = 16    # audit records are bounded; counts stay exact

_CITATION_TOKEN = re.compile(r"request|\[[1-9][0-9]{0,2}\]")


@dataclass(frozen=True)
class ParsedProposal:
    """Syntax-level output of the parser: a claim by the model, nothing more.
    `citation` is the token the model WROTE -- a pointer to be verified, not a
    fact. Carries no origin, authority or provenance; those are assigned
    here, from trusted state."""
    label: str
    score: float
    position: int
    source: Optional[str] = None


@dataclass(frozen=True)
class AcceptanceReport:
    accepted: Tuple[AcceptedHypothesis, ...]        # ranked by score, stable
    rejections: Tuple[ProposalRejection, ...]       # bounded audit records
    parsed_count: int
    rejected_total: int                             # exact, even if records omitted
    omitted_rejections: int
    verified_total: int                             # accepted proposals with verified provenance


def verify_citation(
    source: Optional[str], lineage: InferenceLineage,
) -> Tuple[ProvenanceStatus, Optional[VerifiedProvenance]]:
    """Mechanism A's verification step. Pure function of (claimed pointer,
    this request's citation table). Anything short of an exact, resolvable
    pointer -- "request" or a bracketed block index -- yields no provenance.
    "request" always resolves (InferenceLineage always carries it); see the
    module docstring's residual-risk note for what that does and does not mean.
    """
    if source is None:
        return ProvenanceStatus.UNCITED, None
    if not isinstance(source, str) or _CITATION_TOKEN.fullmatch(source) is None:
        return ProvenanceStatus.MALFORMED_CITATION, None
    block = lineage.resolve(source)
    if block is None:
        return ProvenanceStatus.UNRESOLVED_CITATION, None
    return ProvenanceStatus.VERIFIED, VerifiedProvenance.from_block(block)


def _score_ok(score: object) -> bool:
    return (isinstance(score, (int, float)) and not isinstance(score, bool)
            and math.isfinite(score) and 0.0 <= score <= 1.0)


def _label_ok(label: object) -> bool:
    return isinstance(label, str) and 0 < len(label) <= MAX_LABEL_LENGTH


def accept_proposals(
    parsed: Sequence[ParsedProposal],
    *,
    known_categories: Iterable[str],
    lineage: InferenceLineage,
    max_candidates: int,
    policy_version: str = POLICY_VERSION,
) -> AcceptanceReport:
    """Admission + provenance verification for one model invocation's parsed
    proposals. Every accepted proposal gets origin INTENT_MODEL and the
    authority derived from it (GENERATED) plus the invocation's lineage;
    neither is influenced by the label, the score, or anything the model
    wrote. Only a citation that resolves in THIS request's table yields
    verified provenance.
    """
    known = frozenset(known_categories)
    origin = Origin.INTENT_MODEL
    authority = authority_for(origin)

    records: List[ProposalRejection] = []
    rejected = 0
    omitted = 0

    def reject(p: ParsedProposal, reason: ReasonCode) -> None:
        nonlocal rejected, omitted
        rejected += 1
        if len(records) >= MAX_STORED_REJECTIONS:
            omitted += 1
            return
        label = p.label if isinstance(p.label, str) else ""
        records.append(ProposalRejection(
            position=p.position, reason_code=reason, origin=origin,
            authority=authority, label_digest=content_digest(label),
            label_length=len(label),
            score_claim=float(p.score) if _score_ok(p.score) else None))

    # 1. Admission + provenance verification + duplicate collapse. Each
    #    entry: [position, label, score, status, provenance], first-seen order.
    kept: List[list] = []
    index_by_label: Dict[str, int] = {}
    for p in parsed:
        if not _score_ok(p.score):
            reject(p, ReasonCode.SCORE_INVALID)
            continue
        if not _label_ok(p.label):
            reject(p, ReasonCode.LABEL_INVALID)
            continue
        status, provenance = verify_citation(p.source, lineage)
        if p.label in index_by_label:
            # Conservative and order-independent: repetition can never raise
            # a proposal's confidence or upgrade its provenance.
            entry = kept[index_by_label[p.label]]
            entry[2] = min(float(entry[2]), float(p.score))
            if (entry[3], entry[4]) != (status, provenance):
                entry[3], entry[4] = ProvenanceStatus.AMBIGUOUS_CITATION, None
            reject(p, ReasonCode.DUPLICATE_LABEL)
            continue
        index_by_label[p.label] = len(kept)
        kept.append([p.position, p.label, float(p.score), status, provenance])

    # 2. Bound the candidate set by completion position (score is untrusted,
    #    so it does not decide who survives the cap).
    for pos, label, score, _status, _prov in kept[max_candidates:]:
        reject(ParsedProposal(label=str(label), score=float(score), position=int(pos)),
               ReasonCode.CANDIDATE_LIMIT)
    kept = kept[:max_candidates]

    # 3. Mint envelopes (origin/authority/lineage from trusted state) ...
    accepted = [
        mint_model_proposal(
            label=str(label), score=float(score),
            category_class=(CategoryClass.KNOWN_CATEGORY if label in known
                            else CategoryClass.OPEN_CATEGORY),
            provenance_status=status, provenance=provenance,
            lineage=lineage, policy_version=policy_version, position=int(pos))
        for pos, label, score, status, provenance in kept
    ]
    # 4. ... then rank by the (untrusted) score. Stable: ties keep completion order.
    accepted.sort(key=lambda a: a.score, reverse=True)

    return AcceptanceReport(
        accepted=tuple(accepted), rejections=tuple(records),
        parsed_count=len(parsed), rejected_total=rejected,
        omitted_rejections=omitted,
        verified_total=sum(1 for a in accepted if a.has_verified_provenance))


def policy_default(lineage: InferenceLineage) -> AcceptedHypothesis:
    """The K4.2 §2 open-category fallback, minted by trusted code. Contains
    only the fixed token 'novel' -- never any rejected content."""
    return mint_policy_default(label=OPEN_CATEGORY_TOKEN, score=FALLBACK_SCORE,
                               lineage=lineage, policy_version=POLICY_VERSION)
