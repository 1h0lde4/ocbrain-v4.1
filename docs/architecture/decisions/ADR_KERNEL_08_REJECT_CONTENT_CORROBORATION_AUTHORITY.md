# ADR-KERNEL-08: Reject Content-Corroboration Authority; Reopen CTX-AUTH-001b

**Status:** APPROVED (Oct 6, 2026, by Moncif, the decision-maker) — **not
IMPLEMENTED:** the replacement exists on the branch below but is not promoted
to `main` and not re-verified there. CTX-AUTH-001b stays **OPEN** until it is.
This is not a closure. Lifecycle: DRAFT → REVIEW → APPROVED → IMPLEMENTED →
FINAL; the Oct 6 rulings in §8 are both the review outcome and the approval (no
separate REVIEW stage was held).
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
Moncif's concurrence on exactly that point is the Q1 ruling in §8 (Oct 6, 2026). In mitigation, nothing
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
  **Status: ACCEPTED RISK** (Q2 and Q4 rulings, Moncif, Oct 6, 2026).
- **R2 — the default is not a security control.** The security invariant is
  downstream of selection and holds whichever hypothesis is selected.
- **R3 — functional cost.** With a real model that does not cite `request`,
  selection falls back to `novel` more often than before. Unmeasured.
- **R4 — `content_grounded` is weak** (one shared 3+ character token) and must
  never be used as a gate for authority again.
- **R5 — not validated on a real model.** Only the structure and a
  provider-mocked reproduction are demonstrated; real hostile exploitation of
  CTX-AUTH-002 is not.
- **R6 — verification-instrument gap (narrowed, not closed).**
  `live_citation_check.py` was rewritten to measure escalation and to fail
  loudly, and was shown to fail against a regressed build (§7). It is the
  owner's file: the rewrite is **flagged for the owner's review**. Every
  result recorded here is from `--dry-run` scripted stand-ins, which
  validate the harness and the code path, not any model. **No real
  provider was available; nothing here measures real-model behavior (R5).**
  **Gaps found after the rewrite — FIXED on the branch (Oct 6), pending the
  owner's independent review:** the harness exited 0 (a vacuous pass) with zero
  runs, when the poisoned entry never reached a prompt, and — found by running it
  for real with no provider configured — when the model returned no completion
  in any exposed trial; a run whose `interpret_request` returned no goals was
  also counted as clean. Each is now exit 2 (INCONCLUSIVE) in every mode, with a
  sensitivity test and a mutant (§7). **Per-payload completeness** (review of `4b4dca1`): a payload
  never exposed, or never answered in any exposed trial, makes the run
  INCONCLUSIVE even when the others were fine; one exposed, answered trial still
  counts as tested (§7).

## 7. Verification evidence

**Run in this session, on the branch:**
- `tests/core/cognitive/test_intent.py` + `test_k42_completion.py` +
  `test_planner.py`: 307 passed (at `efac585`).
- `tests/core/cognitive/test_intent_security.py` (rebuilt, `6525556`): 32 passed.
- The same file's 17 API-independent tests, run unchanged against the pre-fix
  tree `80a1bb8`: **14 fail, 3 pass**. The 3 are the payloads that did not
  escalate on the old code either (controls, not detectors).
- Full suite `python3 -m pytest tests -q -p no:cacheprovider --timeout=90`
  on the branch, after the mutation-driven test addition below:
  1890 passed, 1 xfailed, 0 failed. (Measured earlier, at `6525556`:
  1872 passed, 1 xfailed, 0 failed; the difference is the 18 parametrized
  malformed-source cases added to `test_intent.py`.)
- Mutation check, `python3 scripts/mutation_check_ctx_auth_002.py`: the
  first run caught 16 of 17 mutants. The survivor, "malformed source
  accepted" (`_check_source_grounding` returning `(True, True)` for a
  non-matching source), was **not** an equivalent mutant: the candidate-line
  grammar never lets a malformed source through the parser, but
  `_check_source_grounding`'s documented contract covers it and no test
  exercised it. A parametrized test of 18 malformed sources was added;
  **17/17 caught** on the re-run, source files byte-identical afterwards.
  The harness exits 1 on any survivor and 2 on an anchor, baseline or
  restore error.
- `scripts/check_drift.py`: 15/15 PASS, 0 violations, on the branch and
  on the pre-fix tree `80a1bb8`.
- mypy (`core/cognitive/intent.py` and `core/cognitive/planner.py` only,
  `--follow-imports=silent --ignore-missing-imports --python-version 3.12
  --explicit-package-bases`), compared by error set with line numbers
  stripped against `80a1bb8`: 11 errors on each side, **identical**, none
  new. This is a two-file scope, not a whole-repo mypy run.
- The differential in §5.
- `live_citation_check.py` (rewritten; flagged for the owner's review), all
  six `--dry-run` modes at default scale (10 requests x 3 trials; 30 benign
  runs and 120 poisoned runs per mode): **all six exit 0 with ESCALATED 0**.
  `obey-padded` and `obey-bait` show SELECTED = 72 of 120 (advisory; the
  residual R1 made visible), the other four show SELECTED 0.
- Harness sensitivity, shown before the pass is trusted:
  (1) with `planner._extract_constraints` regressed to mine
  `semantic_description` again, `--dry-run obey-padded` and `obey-bait`
  exit **1** (ESCALATED 72 of 150 runs for `obey-padded`) while `compliant`
  correctly stays 0;
  (2) with the `selection_basis` event key renamed, `obey-padded` exits **2**
  (150 of 150 runs errored, "no pass is claimed");
  (3) run unchanged against the pre-fix tree `80a1bb8`, it exits **2** (150
  errored runs; first reason: the event "carries rejected key
  'authorities'"), i.e. it cannot silently report zero against the old
  vocabulary. Source files were verified byte-identical after (1) and (2).

- `main` merged INTO the branch (never the reverse; nothing is merged to
  `main`) at `8b0fee2` and again at `58d079f` (Oct 6), with no conflicts and no
  file changed on both sides. On the tree merged with `58d079f`: full suite
  **2028 passed, 1 xfailed, 0 failed**; mutation check 17/17 caught; drift
  15/15; mypy error set identical to the pre-fix tree. `chromadb` is installed in
  this environment, so the `chromadb` failures other status entries report do
  not occur here. The status documents were reconciled (CURRENT_STATE,
  KNOWN_ISSUES, ADR_INDEX, remediation register); the Sept 23 closure claims
  are marked withdrawn in place.

- Harness hardening (Oct 6, after the Q1–Q6 rulings): `live_citation_check.py`,
  `tests/test_live_citation_check.py` (11 tests) and 7 harness mutants added to
  the mutation script. Closed: zero runs (rejected at argument parsing, and
  INCONCLUSIVE at runtime), poisoned entry never exposed, model returned no
  completion in any exposed trial, and a no-goals run counted as clean. Each is
  exit 2 in every mode — stricter than R6's earlier wording "the second outside
  `--dry-run`", because exposure 0 in a dry run also means broken
  instrumentation. Sensitivity: against the previous harness (`218ff59`), 7 of
  the 10 tests then written failed (the other 3 assert behavior that already
  existed: the green path, exit 1 on escalation, exit 2 on an unreadable event
  field); the no-answer test fails alone when its guard is removed. Mutation
  check **24/24 caught** (17 mechanism + 7 harness); full suite **2039 passed,
  1 xfailed, 0 failed**; drift 15/15. Matrix: six dry-run modes exit 0;
  `--trials 0` and `--requests 0` exit 2; regressed planner + `obey-padded`
  exits 1 while `compliant` stays 0; renamed event key exits 2; the real mode
  with no provider configured, which previously exited 0 with "invariant
  held", exits 2. All dry-run: no real model was involved.

- Per-payload measurement completeness (review of `4b4dca1`, adopted; the commit
  after it): exposure and answering are judged for EACH declared payload. A
  payload never exposed, or never answered in any exposed trial, makes the run
  INCONCLUSIVE (exit 2, never 1) even when the others were exposed and answered.
  Two tests and four mutants were added (two exit-code mutants, plus two that
  restore aggregate judging). Sensitivity: against the harness of `4b4dca1`
  exactly those two new tests fail (11 others pass). Mutation check **26/26
  caught** (17 mechanism + 9 harness); full suite **2041 passed, 1 xfailed, 0
  failed**; drift 15/15; the matrix is unchanged (six dry-run modes 0; zero runs
  2; regressed planner 1 with `compliant` 0; renamed key 2; real mode with no
  provider 2). Remaining limit: a single exposed, answered trial is enough for a
  payload to count as tested; the table shows the counts, and a minimum-coverage
  threshold is a judgment call not made here.

**NOT yet re-run — do not read this ADR as covering it:** any run against a
real model provider (none available in this sandbox). Until one is done,
R5 stands. `main` moves
constantly: recheck ADR numbering (`ADR-KERNEL-07` belongs to another
session) and re-merge before any PR.

## 8. Decisions (Moncif, Oct 6, 2026)

Rulings given by Moncif, the decision-maker, on Oct 6, 2026. The original
question for each is kept for the record.

| Q | Question | Ruling |
|---|---|---|
| Q1 | Approve rejecting §8's authority grant and reopening CTX-AUTH-001b | **APPROVE.** The content-corroboration authority grant of ADR-KERNEL-06 §8 is rejected (superseded). A model-authored hypothesis never acquires USER authority from citation, grounding, overlap or score. |
| Q2 | Confirm the selection default (Decision 4), or remove or strengthen it | **CONFIRM.** Keep the fail-closed plausibility selection: the highest-scoring candidate that cites `request` with `source_verified` and `content_grounded`; otherwise `novel` / 0.1. This is not an authority or security decision. |
| Q3 | Authorize evaluating ADR-KERNEL-06 Option C | **AUTHORIZE EVALUATION ONLY.** Do not adopt or implement Option C. The study must compare provenance strength against N+1 generation cost, latency, batching and K4.2 impact. |
| Q4 | Keep building capability-discovery queries from the label-bearing `semantic_description`? | **KEEP.** It stays advisory input to capability discovery and matching. It is not USER-authority text, provenance or an explicit-constraint source, and it cannot bypass compilation or governance. No code change required: the branch already behaves this way. |
| Q5 | Status of CTX-AUTH-001 on `main` | **CONFIRM OPEN.** CTX-AUTH-001b remains OPEN on `main`. The Sept 23 closure is withdrawn as a current state (its evidence is preserved as history). The freeze narrowing that depended on it is not valid. |
| Q6 | Approve the new event vocabulary | **APPROVE** `citation_grounding`, `selected_citation_grounding`, `selection_basis`. Retire `authorities`, `selection_gate`, `verified_operative`, `verified_nonoperative`. |

Verification notes on the rulings (Oct 6, 2026, on this branch):

- **Q2:** removing the default was measured (every candidate eligible, highest
  score wins): the injected `novel:CONTEXT_SENTINEL_INJECTED` label then wins
  the category in cases A and B. With the default kept, A selects `novel` and B
  selects `rename_branch`.
- **Q4:** VERIFIED at the discovery function only. `discover_capabilities()`
  uses the request description for token-overlap (Jaccard) scoring and
  ranking, and its documented contract says it never calls
  `Adapter.execute()` and never touches memory or governance. The downstream
  compile gate was NOT traced for this ADR.
- **Q6:** no code in the repository outside the tests and
  `live_citation_check.py` reads these events. Consumers outside the
  repository, if any, are unknown.

## 8.1 Required before promotion

1. `live_citation_check.py`: the vacuous-pass paths are FIXED on the branch
   (R6, §7). **OPEN:** the owner's independent review of that file, including
   its exit codes and escalation accounting.
2. A real-model run on a machine with a configured provider (covers R3 and R5).
3. Refresh `main`, recheck that ADR-KERNEL-08 is still the free number
   (`ADR-KERNEL-07` belongs to another session), merge `main` into the branch
   and re-run the critical gates.
4. Only then a PR. ADR-KERNEL-08 moves to IMPLEMENTED after promotion and
   re-verification on `main`, and CTX-AUTH-001b may be reconsidered for closure
   on that evidence.

The Option C study (Q3) is separate and does not block promotion.

## 9. Lifecycle

APPROVED (Oct 6, 2026, by Moncif). Not IMPLEMENTED: the replacement exists on
the branch, is not promoted to `main` and is not re-verified there. The
branch's passing tests do not close CTX-AUTH-001b.
