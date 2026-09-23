# ADR-KERNEL-06: Verifiable Hypothesis Provenance (CTX-AUTH-001b)

**Status:** ACCEPTED and IMPLEMENTED — disposition and mechanism decided
(Moncif, Sept 16 2026); "request" as a citable source decided (Moncif,
Sept 20 2026, §8); implemented and verified Sept 23 2026 (§8 has the
numbers). `TestCtxAuth001ParserAcceptance` is reformulated and green —
see the test file's own STATUS comment for exactly what changed and why.
CTX-AUTH-001b: CLOSED.
**Date:** September 16, 2026 (amended September 20; implemented September 23)
**Author:** Claude.ai chat session, DEBT-019/CTX-AUTH-001b reconciliation
**Scope:** `core/cognitive/intent.py` (`IntentHypothesis`, `generate_hypotheses`,
`_parse_hypotheses`, `_HYPOTHESIS_PROMPT_TEMPLATE`), `core/memory/retrieval/context/context.py`
(`AuthorityLevel`, `ProvenanceRecord`), plus `core/memory/assembly.py`
(§8 — needed additively, once implementation started, to expose the
structured `Context` citation verification actually requires; not
anticipated when this line was first written Sept 16).
**Numbering note:** drafted and accepted Sept 16, 2026 as `ADR-KERNEL-05`; renumbered to
`ADR-KERNEL-06` because `ADR-KERNEL-05` is already held by the PROPOSED
`ADR_KERNEL_05_CTX_AUTH_001B_DEFERRAL_PROPOSAL.md` on branch
`fix/ctx-auth-001-ctx-delete-001-sep2026`. Content unchanged.
**Series note:** `ADR-KERNEL-NN`, not `ADR-K4.2-H-NN` — kept, per Moncif's
explicit decision not to renumber. Kernel v1.0 freeze-scoped, not part of
the closed Aug 2026 H1/H2 packet sequence.
**Terminology note:** "Authority" is unfortunately already overloaded in
this codebase for two unrelated concepts — ADR-K4.2-H-01 ("Layered
Semantic Authority") is about which *layer* (`RawRequest`/`Intent`/`Goal`)
a field's value should be sourced from; this ADR's "authority" is
`AuthorityLevel` (REM-004) — a security/trust classification (SYSTEM /
USER / RETRIEVED / EXTERNAL / GENERATED). The two are unrelated. Kept
distinct rather than renumbered around, per Moncif's explicit decision:
the clarification is the right safeguard, not the number.

---

## 1. Context

REM-002 (CTX-AUTH-001) has two sub-findings. (a) structural containment
is closed on `main` (`_neutralize_structural_tokens`,
`TestCtxAuth001StructuralContainment` passing). (b) parser/output
acceptance remains open (`TestCtxAuth001ParserAcceptance`, intentionally
red).

`_apply_output_containment` (candidate cap ≤5, non-increasing-score
rejection) was evaluated as a candidate closure for (b) and rejected:
wiring it in flipped `TestCtxAuth001ParserAcceptance` green, empirically
confirmed by a before/after test run — but only because that fixture's
injected line's score (1.00) exceeded the preceding line's (0.62),
tripping the ordering check, not because authority was established. A
fixture with a non-increasing score (0.55) sails through unaffected.
Cap/order/role-marker checks control shape, not authorization.

REM-004 (`AuthorityLevel` on `ProvenanceRecord`) gives the system a
vocabulary for authority. It does not give `IntentHypothesis` — a frozen
`label: str, score: float, embedding_ref: Optional[str]` field-set
(K4.2 §12) — anywhere to carry it, and `generate_hypotheses()` extracts
candidates via regex (`_CANDIDATE_LINE`) from the provider's free-text
completion: past the point at which a `ProvenanceRecord` could be traced
to any one line.

## 2. Decision

**Mechanism: A — explicit source citation, verified against the actual
assembled context.** Not "trust what the model says." The chain is:

```
candidate → cited source ID → deterministic lookup in the actual
assembled context for this execution → authority inherited from
that source (or rejected)
```

The model supplies only a pointer. The system — not the model —
establishes whether that pointer is valid. Concretely: the prompt
enumerates the assembled `Context.blocks` (by `primary_entry_id` or a
per-request short index); the candidate line format gains a citation
field; at acceptance time, the cited reference is checked against the
actual `ContextBlock`s assembled for *that specific request* — not
against well-formedness alone.

**Testable invariant:**

> An `IntentHypothesis` cannot acquire authoritative provenance unless
> its cited source exists in the exact assembled context for that
> execution instance, and the resulting authority is deterministically
> derived from that source.

A model saying "this came from source X" does not make it true. A
nonexistent, unavailable, or mismatched X makes the candidate
untrusted/rejected, not authoritative — there is no path from an
unverified citation to an accepted `AuthorityLevel`.

**Fail-closed rule (replaces the carve-out an earlier draft of this ADR
left open):**

> No citation → no authoritative provenance.

A candidate without a valid citation may still *exist* as an untrusted
hypothesis, if the architecture wants to preserve useful
non-authoritative reasoning — but it is not eligible for any operation
that requires trusted/authoritative evidence. **Candidate exists ≠
candidate is trusted.** This applies uniformly, including to a candidate
plausibly synthesized purely from `raw_request.text` with no context
involved — there is no special-cased default that promotes an uncited
candidate to USER authority. (`TestBenignContextBaseline`'s existing
contract — ordinary uncited candidates keep working — is about the
candidate *existing*, not about it acquiring authoritative provenance;
the two are no longer conflated once "exists" and "trusted" are
separated.)

**Standing invariant, stated directly rather than left implicit:**

> Authority is inherited, never inferred.

This rules out, explicitly and permanently: structural/ordering
heuristics, lexical/role-marker heuristics, and embedding similarity as
an authority proxy. Similarity may still be useful for retrieval or
relevance ranking — it must never create an `AuthorityLevel`.

**Option B (embedding-similarity attribution): rejected as an authority
mechanism.** An inferential/statistical judgment, not a verified fact —
the same category of gameable heuristic this project's threat model
already rules out for content, now ruled out for attribution too.

**Option C (system-controlled per-item generation): retained, not
adopted now.**

> The next mechanism to evaluate if adversarial verification
> demonstrates that citation-based attribution cannot reliably prevent
> omission or fabrication under the required assurance level.

C is architecturally cleaner — generation itself establishes the causal
boundary (`generation instance → source scope → candidate`), no
self-report problem at all — but it changes the execution model
(N+1 completions, latency/cost, batching, wider K4.2 impact than 001b
strictly requires). An excellent escalation path; not imposed on the
kernel solely because it is theoretically stronger. A is the initial
mechanism; C is the principled upgrade path, explicitly preserved rather
than foreclosed, not a fallback invented after the fact if A turns out
insufficient.

## 3. Questions this ADR answers

1. **Admissible source reference:** a `ContextBlock` actually present in
   the assembled `Context` for this execution instance, referenced by
   its real identifier — not any well-formed-looking string.
2. **Binding:** the model cites a reference; the system performs a
   deterministic lookup against the real assembled set. Binding is the
   system's act, not the model's claim.
3. **Absent / ambiguous / contradictory attribution:** fail-closed
   uniformly. No citation, an unresolvable citation, or a contradictory
   one all produce the same outcome — no authoritative provenance. No
   carve-out. (Ambiguous/multiple citations: resolved by the same
   principle — nothing here promotes to a higher authority than a
   single verified source would; an implementation detail for the
   schema-change pass, not a new exception to this rule.)
4. **Direct vs. inherited authority:** never direct. `AuthorityLevel` is
   always inherited from a verified source or absent — this is what
   "authority is inherited, never inferred" means at the acceptance
   boundary specifically, mirroring the principle `AuthorityLevel`'s own
   docstring already states for `ProvenanceRecord`'s construction site.
5. **Frozen contract / replay / determinism:** same category of change
   as ADR-K4.2-H-09's `caused_by: Optional[str] = None` on
   `CognitiveArtifact` — additive, optional, least-privilege default.
   Verified this session: `generate_hypotheses()`'s event log
   (`cognitive.intent_hypotheses_generated`, `intent.py:1074-1082`)
   records only `hypothesis_count` and `labels` today — neither `score`
   nor `embedding_ref` is durably logged, so a new field is no harder to
   replay than what already exists.
6. **Serialization/replay across the schema transition:** no migration
   needed — there is no rich historical `IntentHypothesis` serialization
   to migrate (per Q5's finding), so an `Optional`, least-privilege-
   default field requires no special handling for pre-transition event
   records.

## 4. Rejected-candidate logging — separate debt, not 001b scope

Flagged during this reconciliation: nothing about a *rejected* candidate
is logged today, only accepted labels. **This is not folded into
CTX-AUTH-001b** — scope stays exactly the acceptance invariant above,
not an auditability project.

Classified separately: `candidate generated → verification/rejection →
immutable rejection receipt`. Open question for whoever registers this
as formal debt: does the absence of rejected-candidate logging violate
an already-defined kernel invariant (LAW 1's audit-logging
responsibility, stated at the principle level in
`PROJECT_INSTRUCTIONS.md` §6.1)? If not, it stays a documented debt, not
an escalation — no DEBT-NNN number assigned here; that classification
call belongs with whoever registers it in `KNOWN_ISSUES.md`, matching
this project's existing pattern of debt classification being an
explicit, owned decision rather than assigned in passing.

## 5. Consequences

- `IntentHypothesis` gains a citation/reference field and a derived
  authority-eligibility distinction — implementation detail (exact
  field shape) for the schema-change pass, not decided here; the
  invariant this ADR fixes is candidate-exists ≠ candidate-is-trusted,
  not the field's literal type.
- `_HYPOTHESIS_PROMPT_TEMPLATE` changes to enumerate citable blocks;
  `_CANDIDATE_LINE`'s parsing grammar changes to extract a citation.
- `generate_hypotheses()`'s acceptance path gains a real gate: verify
  the citation against the actual assembled `Context.blocks`, derive
  authority from the verified source or fail closed. This is the
  invariant that actually closes `TestCtxAuth001ParserAcceptance` — not
  yet implemented; this ADR is the accepted design for that work, not
  the work itself.
- `_apply_output_containment` is unaffected, stays as defense-in-depth,
  was never the authority mechanism.
- Option C is not implemented now. Its trigger condition (§2) is the
  explicit criterion for revisiting this ADR, not a vague "if needed."
- The rejected-candidate logging gap (§4) is tracked as a separate,
  smaller item — implementing it is not a precondition for closing
  CTX-AUTH-001b under this ADR.

## 6. Alternatives considered

- **Treat `_apply_output_containment` as sufficient, close
  CTX-AUTH-001b now.** Rejected — the false-closure this ADR exists to
  prevent, demonstrated empirically (§1), not hypothetically.
- **A keyword/phrase blacklist on candidate content.** Ruled out by this
  project's existing threat model and by "authority is inherited, never
  inferred" (§2).
- **An uncited-candidate default that inherits USER authority when no
  context was involved.** Considered and explicitly rejected — this is
  the carve-out an earlier draft left open. Removed in favor of a single
  uniform fail-closed rule (§2): existing and being trusted are kept
  separate instead.
- **Adopt Option C now, skip A.** Rejected as premature — C's cost
  (N+1 completions, wider K4.2 impact) is not justified before A has
  been tried and adversarially tested; C remains the explicit escalation
  path (§2), not discarded.
- **Fold rejected-candidate logging into this ADR's scope.** Rejected —
  avoids scope creep into an auditability project; tracked separately
  (§4).

## 7. Remaining open items (implementation-level, not architectural)

- Exact schema shape for the citation/authority-eligibility fields on
  `IntentHypothesis` (this ADR fixes the invariant, not the literal
  field names/types).
- Whether §4's rejected-candidate logging gap gets a formal `DEBT-NNN`
  entry now or later, and by whom — not resolved here by design.
- The adversarial test suite that must pass before CTX-AUTH-001b is
  actually considered closed (§ Status) — this ADR defines the
  invariant such tests must establish; it does not itself constitute
  them.

## 8. Amendment: "request" as a citable source, and implementation (Sept 20–21 2026)

The original text above left the exact field shape open and did not
specify how a candidate grounded in the user's own request — not in any
retrieved block — would ever reach USER authority, since the mechanism
as first drafted only described citing a `ContextBlock`. Resolved by
decision (Sept 20 2026, Moncif) and then implemented (Sept 23 2026)
against `fix/ctx-auth-001b-verified-provenance-sep2026`:

- **The raw request becomes a citable source, in the same enumerable
  scheme as context blocks** — literal keyword `"request"`, alongside
  `"[N]"` for the Nth citable block (`core/cognitive/intent.py`,
  `_CANDIDATE_LINE` / `_render_citable_context`). Not a separate,
  differently-trusted code path from block citation — the same
  `_resolve_source()` resolves both.
- **Existence of the named source is necessary but not sufficient.**
  `"request"` always exists for a real request, so checking only "is
  this a valid source name" would let any candidate claim it for free.
  `_resolve_source()` additionally requires the candidate's own content
  to corroborate the named source (literal token overlap against that
  source's real text for this execution) before granting authority — a
  deterministic check against real data, not embedding similarity
  (already ruled out above) and not a lexical accept/reject heuristic
  evaluated on the candidate alone (this ADR's "lexical heuristic," about
  guessing trust with no citation at all — see `_neutralize_role_markers`
  — is a different thing from verifying a specific already-claimed
  pointer resolves to real data).
- **Selection, not only acceptance, is gated.** `_select_operative_
  hypothesis()` may only select a hypothesis whose resolved authority is
  `AuthorityLevel.USER`; anything else — uncited, block-cited
  (`RETRIEVED`), or a citation that failed corroboration — falls back to
  the same `novel` / 0.1 open-category hypothesis `generate_hypotheses`
  already used for total failure, not a new convention. Reported on
  `cognitive.intent_interpreted` as `selection_gate` ∈
  `{"verified_operative", "open_category_fallback"}`.
- **`TestCtxAuth001ParserAcceptance`'s assertion is reformulated, not
  abandoned** (Moncif, Sept 20): the invariant it protects is unchanged
  (injected content must never gain undeserved authority) but it is now
  expressed against the citation mechanism instead of bare existence in
  the hypothesis list, since existence is no longer the thing this
  invariant forbids — see the test file's own updated STATUS comment.

Options considered and rejected for this amendment specifically:

- **B — implement the mechanism as originally drafted above, no
  selection gate, block citation only.** Rejected — leaves no path for a
  request-grounded candidate to ever reach USER authority at all,
  understating what the mechanism needs to cover on day one.
- **C — skip straight to Option C (N+1 per-candidate generation).**
  Rejected as premature, same reasoning given above for rejecting that
  move initially: A had not yet been given an adversarial test to fail
  before being abandoned.

### Verified, Sept 23 2026 — not assumed from either the design or the
### implementer's own account of it

- Full repo test suite, reconciled tree: 1,509 passed / 8 failed — the 8
  are `TestA7SystemController` and `test_module_factory_security.py`
  cases gated on `chromadb`, not installed in this sandbox; a pre-existing
  environment gap, unrelated to this change. Zero regressions.
- `TestCtxAuth001ParserAcceptance` (reformulated): passes. A candidate
  fabricating a `| request` citation for content unrelated to the real
  request does not resolve to `AuthorityLevel.USER`; a genuinely
  request-grounded candidate in the same run does — confirming the
  mechanism verifies rather than blanket-rejects.
- `live_citation_check.py` (Moncif's own harness, `--dry-run
  obey-fabricate --fail-on-selected`, the scripted stand-in specifically
  built to fabricate a `request` citation for injected content), full
  default scale: **Part A (operational): 30/30 (100%) benign requests
  produced a verified-USER candidate, 0 fell back to `novel`/0.1.**
  **Part B (adversarial), all three payloads (`naive`, `cite-request`,
  `line-spoof`), 90 exposed trials total: 0 fabricated `request`
  citations reached USER authority, 0 injected candidates were selected
  as the accepted Intent.** Exit code 0 with `--fail-on-selected` (would
  be non-zero on any selected injection). Also run under `--dry-run
  obey-honest` (model honestly cites the real block the sentinel sits
  in): all exposed trials landed `cited_block_nonoperative` — correctly
  capped at `RETRIEVED`, never selected.

This resolves this ADR's first originally-open item above (schema:
`source: Optional[str]`, `authority: Optional[AuthorityLevel]`, additive
on `IntentHypothesis`) and its third (the adversarial suite is
`live_citation_check.py` plus the reformulated
`TestCtxAuth001ParserAcceptance` — both actually re-run against this
implementation, per the numbers above, not assumed passing). The second
originally-open item (rejected-candidate logging) remains genuinely
open, tracked separately, not touched by this amendment.

**CTX-AUTH-001b: CLOSED, Sept 23 2026** — see `KNOWN_ISSUES.md` for the
tracking-doc side of this same disposition.
