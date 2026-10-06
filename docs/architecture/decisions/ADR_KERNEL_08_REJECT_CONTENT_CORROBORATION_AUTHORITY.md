# ADR-KERNEL-08: Reject Content-Corroboration Authority; Reopen CTX-AUTH-001b

**Status:** DRAFT — **not approved.** This ADR proposes rejecting a merged
mechanism. It requires a decision by the project owner **and** Moncif's
concurrence (Q1). It must not be moved past DRAFT by the session that wrote
it. Lifecycle: DRAFT → REVIEW → APPROVED → IMPLEMENTED → FINAL.
**Date:** October 6, 2026
**Author:** Claude session, CTX-AUTH-002 workstream
**Branch:** `fix/ctx-auth-002-reject-content-corroboration-authority-sep2026`
(base `main` @ `80a1bb8`; nothing merged to `main`)
**Amends / reopens:** `ADR-KERNEL-06` §8 (and its "CTX-AUTH-001b: CLOSED"
statements). §§1–8 of that ADR are unmodified; a reconsideration notice sits
above its §1.
**Finding:** CTX-AUTH-002 in
`docs/research/context-engineering/context-authority-threat-model.md`.
**Scope:** `core/cognitive/intent.py` (`IntentHypothesis`,
`_check_source_grounding`, `_select_hypothesis`, `_describe_grounding`,
`interpret_request` events), `core/cognitive/planner.py`
(`_extract_constraints`), `tests/core/cognitive/`, `live_citation_check.py`.
**Out of scope:** `GovernanceKernel` (still the sole action authority —
information authority is not action authorization), ADR-KERNEL-06 Option C,
capability discovery (Q4).
**Numbering note:** `ADR-KERNEL-01/02/03/04/06/07` exist on `main`.
`ADR-KERNEL-07` belongs to another session (creative content-anchor
detector). Recheck for a collision at merge time.

## 1. Decision

1. **The ADR-KERNEL-06 §8 authority-grant mechanism is rejected, not tuned.**
   The overlap threshold, stopword lists and token counts are not the fix.
2. **Three facts are kept separate, and none produces the next:**
   `source verified` (the cited source exists for this execution) ≠
   `content grounded` (the label shares literal tokens with that source's real
   text) ≠ `authority`.
3. **A model-authored hypothesis has no per-instance authority.** Every
   hypothesis `generate_hypotheses` returns is, without exception,
   `AuthorityLevel.GENERATED`; that is a constant, not a field.
   `IntentHypothesis.authority` is removed. `IntentHypothesis` gains the
   additive, defaulted `source_verified: bool` and `content_grounded: bool`
   next to the existing `source`, so the frozen
   `label / score / embedding_ref` triple is unchanged.
4. **Selection fails closed, and is not an authority decision.**
   `_select_hypothesis` considers a candidate only if it cites `request`, the
   source is verified and the content is grounded; the highest score among
   those wins (`selection_basis = "request_grounded"`); otherwise the trusted
   `novel` / 0.1 open-category hypothesis is used
   (`"open_category_fallback"`). **A block citation is never eligible.** The
   default is a plausibility default; **no security claim rests on it.**
5. **Consumption boundary:** `planner._extract_constraints` reads only
   `description`, falling back to `raw_request` — never `semantic_description`
   (`"<model label>: <request>"`).
6. **The overclaiming vocabulary is removed.** `verified_operative` /
   `verified_nonoperative` / `selection_gate` / `authorities` communicated a
   stronger guarantee than the implementation establishes. Events now carry
   `citation_grounding` (per hypothesis: `uncited | source_unresolved |
   content_ungrounded | content_grounded`), `selected_citation_grounding` and
   `selection_basis`.

## 2. Why a rejection and not a tuning change

- For `request`, "the cited source exists" is true of every citation, so
  lookup verification carries no information; the whole decision rested on the
  overlap.
- The substitute for verification is a lexical heuristic, in the family
  ADR-KERNEL-06 §2 already prohibits ("lexical/role-marker heuristics, and
  embedding similarity as an authority proxy").
- Any "N tokens of length ≥ K" threshold is satisfiable by a longer padded
  label, so tuning only raises the attacker's cost.
- It conflates grounding with authority: a model's classification of the
  request is a model artifact however well grounded, and never acquires the
  request's own (USER) authority.
- ADR-KERNEL-06's own escalation trigger — "adversarial verification
  demonstrates that citation-based attribution cannot reliably prevent
  omission or fabrication under the required assurance level" — has fired.
  See Q3.

## 3. What this overrides

| Element of ADR-KERNEL-06 §8 | Disposition |
|---|---|
| `"request"` as a citable source, same scheme as `"[N]"` | **Retained** |
| Citation parsing, `source: Optional[str]` | **Retained** |
| Existing ≠ trusted: a rejected-grounding candidate still exists in `Intent.hypotheses` | **Retained** |
| Fail-closed selection falling back to `novel` / 0.1 | **Retained**, re-justified as a plausibility default |
| `authority: Optional[AuthorityLevel]` on `IntentHypothesis` | **Removed** |
| `_resolve_source` returning an `AuthorityLevel` from token overlap | **Rejected** → `_check_source_grounding` returns `(source_verified, content_grounded)` |
| `_select_operative_hypothesis` (selects `authority == USER`) | **Rejected** → `_select_hypothesis` |
| Events `authorities`, `selection_gate`, `"verified_operative"` | **Removed** → `citation_grounding`, `selection_basis` |
| Planner mining `semantic_description` for explicit constraints | **Removed** |
| "CTX-AUTH-001b: CLOSED" | **Withdrawn** (this ADR is a proposal; not a new closure) |

**Option B clarification (relevant to Q1).** ADR-KERNEL-06 §8 rejected
"B — implement the mechanism as originally drafted above, no selection gate,
block citation only" because it "leaves no path for a request-grounded
candidate to ever reach USER authority". This ADR is not Option B: it keeps
`request` citation and a selection default. It **does** share Option B's
consequence — no request-grounded candidate can reach USER authority — and
therefore removes the very path §8 gave as its reason for rejecting B.
Moncif's concurrence is needed on exactly that point. In mitigation, nothing
reviewed required a model-authored hypothesis to hold USER authority: the
consumers of label-derived fields are the planner's constraint extraction
(fixed), a hint keyed on `category == "novel"`, and capability-discovery
query text built from `semantic_description` (advisory, governed at compile).
`core/workers/reflection.py`'s "category" is unrelated.

## 4. Alternatives considered

- **No selection gate (select highest score).** Fixes the escalation but, by
  construction, lets an injected high-scoring label win in the uncited and
  "cited but ungrounded" cases that `main` handled. An earlier implementation
  of this branch did that; the regression was measured then and is recorded
  in the session handoff, **not re-run** here. Superseded by Decision 4.
- **Raise the threshold / add stopwords / require N tokens.** Rejected (§2).
- **Always select `novel`.** Rejected: it removes intent inference entirely.
- **Authority via "stronger grounding".** Rejected: any grounding derived from
  content is evidence about what the model claims, not provenance.
- **Label-shape rules (e.g. UPPER_SNAKE).** Forbidden by ADR-KERNEL-06 §2.
- **ADR-KERNEL-06 Option C (system-controlled per-item generation, N+1
  completions).** Not implemented here; evaluation requires owner
  authorization (Q3). It is the only candidate found that could restore a
  per-instance authority without relying on content.

## 5. Measured effect

Re-measured Oct 6 2026 through the real `interpret_request` with only the
provider and context assembly mocked; request
`"what's a good name for my new branch?"`; reported: selected category and
count of `source == "explicit"` constraints from `_extract_constraints`.

| Case | Pre-fix `80a1bb8` | Branch `6525556` |
|---|---|---|
| A: `novel:CONTEXT_SENTINEL_INJECTED \| 1.00` / `rename_branch \| 0.62` (uncited) | `novel` / 0 | `novel` / 0 |
| B: same, both `\| request` | `rename_branch` / 0 | `rename_branch` / 0 |
| C: `only for the new account and not for any other user \| 1.00 \| request` / `rename_branch \| 0.62 \| request` | padded label wins / **1** | padded label wins / **0** |

Scores must be non-increasing, or `_apply_output_containment` drops the later
lines.

## 6. Residual risks (state these wherever this change is described)

- **R1 — advisory category steering.** A label padded with common words still
  satisfies the plausibility default (case C) and can win
  `Goal.structured_form["category"]`. Consumers: the `novel` planner hint and
  capability-discovery text built from `semantic_description`. It cannot
  reach `description`, `raw_request` or an EXPLICIT constraint. Pinned by
  `TestSelectHypothesis::test_padded_label_bypasses_the_default_but_cannot_escalate`.
- **R2 — the default is not a security control.** The security invariant is
  downstream of selection and holds whichever hypothesis is selected.
- **R3 — functional cost.** With a real model that does not cite `request`,
  selection falls back to `novel` more often than before. Unmeasured.
- **R4 — `content_grounded` is weak** (one shared 3+ character token) and must
  never be used as a gate for authority again.
- **R5 — not validated on a real model.** Only the structure and a
  provider-mocked reproduction are demonstrated; real hostile exploitation of
  CTX-AUTH-002 is not.
- **R6 — verification-instrument gap.** `live_citation_check.py` still reads
  the rejected event vocabulary on this branch (see §7). Until it is rebuilt
  and shown to fail against the vulnerable build, it must not be cited as
  evidence.

## 7. Verification evidence

**Run in this session, on the branch:**
- `tests/core/cognitive/test_intent.py` + `test_k42_completion.py` +
  `test_planner.py`: 307 passed (at `efac585`).
- `tests/core/cognitive/test_intent_security.py` (rebuilt, `6525556`): 32 passed.
- The same file's 17 API-independent tests, run unchanged against the pre-fix
  tree `80a1bb8`: **14 fail, 3 pass**. The 3 are the payloads that did not
  escalate on the old code either (controls, not detectors).
- Full suite `python3 -m pytest tests -q -p no:cacheprovider --timeout=90`
  on the branch at `6525556`: 1872 passed, 1 xfailed, 0 failed.
- The differential in §5.

**NOT yet re-run — do not read this ADR as covering them:** the mutation
harness, `scripts/check_drift.py`, the mypy error-set comparison against
`main`, `live_citation_check.py` (still on the rejected vocabulary), and a
merge of current `main` into the branch. This section must be updated when
they are run.

## 8. Decisions required (none may be self-approved)

- **Q1** Approve rejecting §8's authority grant and reopening CTX-AUTH-001b.
  **Needs Moncif's concurrence** (see the Option B clarification in §3).
- **Q2** Confirm the selection default (Decision 4), or choose: remove it, or
  strengthen it.
- **Q3** Authorize evaluating ADR-KERNEL-06 Option C; its trigger has fired.
- **Q4** Should capability discovery keep building queries from the
  label-bearing `semantic_description`? (A behavior change if not.)
- **Q5** Until a decision is made, treat CTX-AUTH-001 as **open on `main`**
  and re-widen the Sept 23 freeze-verdict narrowing.
- **Q6** Approve the new event vocabulary (`citation_grounding`,
  `selected_citation_grounding`, `selection_basis`).

## 9. Lifecycle

DRAFT. Not reviewed, not approved, not implemented on `main`. The branch
contains an implementation for review; its existence is not approval.
