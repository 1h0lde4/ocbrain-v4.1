"""
core/cognitive/intent_acceptance.py -- REM-004 acceptance boundary for Intent
hypotheses (CTX-AUTH-001b).

Architecture:
    docs/architecture/decisions/ADR_KERNEL_06_INSTRUCTION_AUTHORITY_TAXONOMY.md
    (DRAFT -- implemented here, not approved by this file).

Pipeline this module is the middle stage of:

    raw completion  --(intent._parse_hypotheses: SYNTAX only)-->  ParsedProposal[]
        --(accept_proposals: THIS module: admission + provenance)-->
    AcceptedHypothesis[] (eligible, ranked)  +  ProposalDisposition[] (audit)
        --> Intent.selected

Invariant: authority eligibility precedes confidence ranking. A candidate
that fails admission never reaches the sort, so a self-reported 1.00 cannot
win by score. Ranking then uses only the (untrusted) score, among eligible
candidates only, with completion position as the deterministic tie-break.

What this gate is -- and is not (see the ADR's threat-model honesty section):

  * It IS deterministic, dependency-free, and cheap: no LLM, no I/O, no
    global state. Same inputs -> same report, on any request, in any order of
    concurrent requests.
  * It enforces a CLOSED-WORLD LABEL CONTRACT, not a content blacklist.
    A category label is a short lowercase NAME: words of a-z/0-9 joined by
    single spaces or underscores ("code_review", "creative writing"), at most
    64 characters, optionally prefixed by "novel:". Everything else --
    uppercase, punctuation, quotes, markdown, delimiters, control or
    non-ASCII characters -- is not a category label. This is a whitelist by
    *form*; it never inspects what a label means, so there is no keyword list
    to evade. (Lowercase multi-word names are legitimate categories in the
    existing K4.2 evidence, so spaces are allowed; the planner no longer
    mines labels for constraints, so free text in a label has no path to a
    user-authority field.)
  * The contract carves out a RESERVED NAMESPACE: UPPER_SNAKE_CASE. Every
    trusted-runtime token that gets serialized (authority, origin, reason,
    outcome) lives there. A model-controlled string is therefore textually
    disjoint from every trusted token; it can never be mistaken for one in a
    log line, an event, or a replayed payload. Labels that *look like*
    trusted tokens are QUARANTINED (bounded escaped preview kept for audit),
    not repaired: lowercasing them would launder a spoofing attempt into a
    valid label.
  * It is NOT an authority model and does NOT detect a well-formed hijack
    (e.g. a lowercase `create_account | 1.00`). Such a proposal is accepted
    as an ordinary MODEL_PROPOSAL and stays exactly that: it cannot become
    USER_INSTRUCTION/SYSTEM_POLICY, cannot reach a user-authority field, and
    cannot bypass GovernanceKernel. That containment lives in authority.py,
    intent.py (Goal formation) and planner.py, and is what the tests prove.
  * It does not import GovernanceKernel (DRIFT-10) and authorizes no action.

Failure semantics: every rejection is a deterministic decision with a reason
code, retained as a bounded record. Nothing is swallowed with a bare
`except: continue`.
"""
import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.cognitive.authority import (
    AcceptedHypothesis,
    CategoryClass,
    Disposition,
    InferenceLineage,
    Origin,
    ProposalDisposition,
    ReasonCode,
    authority_for,
    content_digest,
    mint_model_proposal,
    mint_policy_default,
    safe_preview,
)

POLICY_VERSION = "intent-acceptance/1"

OPEN_CATEGORY_TOKEN = "novel"
NOVEL_PREFIX = OPEN_CATEGORY_TOKEN + ":"
MAX_CANDIDATES = 5            # mirrors the "up to n" the prompt asks for
MAX_LABEL_LENGTH = 64
MAX_STORED_DISPOSITIONS = 16  # audit records are bounded; counts stay exact
FALLBACK_SCORE = 0.1          # K4.2 §2 open-category degrade path (unchanged)

# Words of a-z/0-9 (first char a letter) joined by SINGLE spaces or underscores.
_LABEL_NAME = re.compile(r"[a-z][a-z0-9]*(?:[ _][a-z0-9]+)*")
# The reserved namespace: UPPER_SNAKE_CASE, the shape of every serialized
# trusted-runtime token (authority, origin, reason, outcome).
_RESERVED_SHAPE = re.compile(r"[A-Z][A-Z0-9_]*")


def _is_label_name(core: str) -> bool:
    return len(core) <= MAX_LABEL_LENGTH and _LABEL_NAME.fullmatch(core) is not None


@dataclass(frozen=True)
class ParsedProposal:
    """Syntax-level output of the parser: a claim by the model, nothing more.
    Carries no origin, authority or eligibility -- those are assigned here,
    from trusted state, never from this object."""
    label: str
    score: float
    position: int


@dataclass(frozen=True)
class AcceptanceReport:
    accepted: Tuple[AcceptedHypothesis, ...]        # eligible, ranked
    dispositions: Tuple[ProposalDisposition, ...]   # bounded audit records
    parsed_count: int
    rejected_total: int                             # exact, even if records omitted
    quarantined_total: int
    omitted_dispositions: int


def filter_known_categories(categories: Iterable[str]) -> Tuple[Tuple[str, ...], int]:
    """The trusted vocabulary must itself satisfy the label contract.

    known_categories is read back through memory retrieval (promoted L3
    entries), so by channel it is RETRIEVED_DATA. Requiring contract-form
    names keeps that vocabulary inert: it can neither be matched by a
    contract-compliant label unless it is itself compliant, nor carry
    markup/delimiter/instruction-shaped text into the prompt.
    Returns (kept, dropped_count).
    """
    kept: List[str] = []
    seen = set()
    dropped = 0
    for category in categories:
        if (isinstance(category, str) and _is_label_name(category)
                and category not in seen):
            seen.add(category)
            kept.append(category)
        else:
            dropped += 1
    return tuple(kept), dropped


def admit_label(label: str) -> Optional[Tuple[Disposition, ReasonCode]]:
    """None if `label` satisfies the label contract, else the deterministic
    (disposition, reason) that excludes it. Pure function of the string."""
    if label == OPEN_CATEGORY_TOKEN:
        return None
    core = label[len(NOVEL_PREFIX):] if label.startswith(NOVEL_PREFIX) else label
    if _is_label_name(core):
        return None
    if _RESERVED_SHAPE.fullmatch(core):
        return Disposition.QUARANTINED, ReasonCode.RESERVED_NAMESPACE
    return Disposition.REJECTED, ReasonCode.LABEL_GRAMMAR


def _score_ok(score: object) -> bool:
    return (isinstance(score, (int, float)) and not isinstance(score, bool)
            and math.isfinite(score) and 0.0 <= score <= 1.0)


def accept_proposals(
    parsed: Sequence[ParsedProposal],
    *,
    known_categories: Iterable[str],
    lineage: InferenceLineage,
    policy_version: str = POLICY_VERSION,
    max_candidates: int = MAX_CANDIDATES,
) -> AcceptanceReport:
    """Admission + provenance for one model invocation's parsed proposals.

    Every accepted proposal gets origin INTENT_MODEL and the authority
    derived from it (MODEL_PROPOSAL) plus the invocation's lineage. Neither
    is influenced by the label, the score, or anything the model wrote.
    """
    known = frozenset(known_categories)
    origin = Origin.INTENT_MODEL
    authority = authority_for(origin)

    records: List[ProposalDisposition] = []
    counts = {Disposition.REJECTED: 0, Disposition.QUARANTINED: 0}
    omitted = 0

    def record(p: ParsedProposal, disposition: Disposition, reason: ReasonCode) -> None:
        nonlocal omitted
        counts[disposition] += 1
        if len(records) >= MAX_STORED_DISPOSITIONS:
            omitted += 1
            return
        records.append(ProposalDisposition(
            position=p.position, disposition=disposition, reason_code=reason,
            origin=origin, authority=authority,
            label_digest=content_digest(p.label), label_length=len(p.label),
            score_claim=float(p.score) if _score_ok(p.score) else None,
            label_preview=(safe_preview(p.label)
                           if disposition is Disposition.QUARANTINED else None)))

    # 1. Admission (order-independent per candidate) + duplicate collapse.
    kept: List[Tuple[int, str, float]] = []   # (position, label, score), first-seen order
    index_by_label: Dict[str, int] = {}
    for p in parsed:
        if not _score_ok(p.score):
            record(p, Disposition.REJECTED, ReasonCode.SCORE_INVALID)
            continue
        verdict = admit_label(p.label)
        if verdict is not None:
            record(p, verdict[0], verdict[1])
            continue
        if p.label in index_by_label:
            # Conservative and order-independent: a repeated label can never
            # raise its own confidence; the lowest claimed score survives.
            idx = index_by_label[p.label]
            pos0, label0, score0 = kept[idx]
            kept[idx] = (pos0, label0, min(score0, float(p.score)))
            record(p, Disposition.REJECTED, ReasonCode.DUPLICATE_LABEL)
            continue
        index_by_label[p.label] = len(kept)
        kept.append((p.position, p.label, float(p.score)))

    # 2. Bound the candidate set by completion position (score is untrusted,
    #    so it is not used to decide who survives the cap).
    for pos, label, score in kept[max_candidates:]:
        record(ParsedProposal(label=label, score=score, position=pos),
               Disposition.REJECTED, ReasonCode.CANDIDATE_LIMIT)
    kept = kept[:max_candidates]

    # 3. Mint envelopes (origin/authority/lineage from trusted state) ...
    accepted = [
        mint_model_proposal(
            label=label, score=score,
            category_class=(CategoryClass.KNOWN_CATEGORY if label in known
                            else CategoryClass.OPEN_CATEGORY),
            lineage=lineage, policy_version=policy_version, position=pos)
        for pos, label, score in kept
    ]
    # 4. ... and only now rank. Stable sort: equal scores keep completion order.
    accepted.sort(key=lambda a: a.score, reverse=True)

    return AcceptanceReport(
        accepted=tuple(accepted), dispositions=tuple(records),
        parsed_count=len(parsed), rejected_total=counts[Disposition.REJECTED],
        quarantined_total=counts[Disposition.QUARANTINED],
        omitted_dispositions=omitted)


def policy_default(lineage: InferenceLineage) -> AcceptedHypothesis:
    """The K4.2 §2 open-category fallback, minted by trusted code. Contains
    only the fixed token 'novel' -- never any rejected content."""
    return mint_policy_default(label=OPEN_CATEGORY_TOKEN, score=FALLBACK_SCORE,
                               lineage=lineage, policy_version=POLICY_VERSION)
