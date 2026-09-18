# ADR-KERNEL-05: Verifiable Hypothesis Provenance (CTX-AUTH-001b)

**Status:** ACCEPTED — disposition and mechanism both decided (Moncif,
Sept 16 2026). **Not yet implemented.** CTX-AUTH-001b stays OPEN until
implementation and adversarial tests actually establish the invariants
below — this ADR is the accepted design, not a closure of the finding.
`TestCtxAuth001ParserAcceptance` remains intentionally red; 137 passed /
1 failed is the correct state until real code changes it.
**Date:** September 16, 2026
**Author:** Claude.ai chat session, DEBT-019/CTX-AUTH-001b reconciliation
**Scope:** `core/cognitive/intent.py` (`IntentHypothesis`, `generate_hypotheses`,
`_parse_hypotheses`, `_HYPOTHESIS_PROMPT_TEMPLATE`), `core/memory/retrieval/context/context.py`
(`AuthorityLevel`, `ProvenanceRecord`).
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
