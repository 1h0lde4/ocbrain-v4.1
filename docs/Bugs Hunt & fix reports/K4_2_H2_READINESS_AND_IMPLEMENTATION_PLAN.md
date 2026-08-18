# K4.2-H2 READINESS & IMPLEMENTATION PLAN

**Author:** independent session, Aug 17–18, 2026. **Method:** every claim below traces to a specific file/line/command run this session — the D10 baseline capability was actually implemented, run, bug-fixed, tested, and captured (not merely planned); D3/D7/D11/D12 are planning-only, per this task's own Outcome-A boundary (§20 of the task prompt: "Do NOT begin D3/D7/D11/D12 implementation... unless the repository's documented milestone process explicitly authorizes implementation in the same packet" — it doesn't, for these four).

---

## 1. H1 Approval Verification

**Outcome A applies.** Per Phase 0's explicit instruction not to infer approval from an AI report, a completion report, a passing suite, or a commit merely existing, this checks for an *explicit statement* of human approval, persisted in the repository's own established convention for recording sign-off (prose in the relevant tracking file — the same convention already used repo-wide, e.g. `K4_2_H1_COMPLETION_REPORT.md`'s "H1 proceeded only after explicit sign-off on scope"; no separate formal "approval ledger" file exists anywhere in this repository — confirmed by grepping the whole tree for `APPROVAL|sign-off|signed off` before concluding this).

Found in commit `6ff604c` (current `HEAD`, `main`):
- `CURRENT_STATE.md`, H1 row: *"**FROZEN Aug 17, 2026** following an independent 16-gate freeze review ... and Moncif's sign-off."*
- `IMPLEMENTATION_ROADMAP.md` sync header: *"K4.2-H1 FROZEN — independent freeze review passed all 16 gates, Moncif signed off."*

This is the repository's own record, in its own established convention, not an inference from anything AI-generated. **H1 human freeze approval: PRESENT.**

---

## 2. Frozen H1 Baseline

| Field | Value |
|---|---|
| Repository | `github.com/1h0lde4/ocbrain-v4.1`, branch `main` |
| HEAD at start of this task | `6ff604c` |
| H1 commit | `72a5498` |
| Freeze approval reference | `6ff604c` (this commit *is* the approval record — see §1) |
| Working tree | Clean at task start; confirmed via fresh `git fetch` |
| Known test baseline | 1156 passed / 34 failed (environment-only, `huggingface.co` unreachable) |
| Architecture spec revision | `implementation_plan - K42 v1-0 FINAL PRE-FREEZE ARCHITECTURE SPECIFICATION frozen.md` (840 lines, the corrected version) |

Frozen contracts H2 must not silently modify (from the freeze review, §15, re-affirmed here): `RawRequest` immutability, `CapabilityMatch`/`CapabilityDiscoveryResult` shape (incl. `.contracts` compatibility projection), `OperationRecoveryBudget`'s `consume()`/`remaining`/`exhausted` contract, the `derived_from`/`caused_by` separation, `trace_id`/`operation_id`/`stage_tag` semantics, the three-entrypoint signatures, and the `cognitive.planner_impasse_terminal` event shape.

---

## 3. D10 Pre-H2 Baseline — **implemented and captured this session**

`scripts/check_drift.py` did not exist (confirmed absent in the freeze review and re-confirmed at the start of this task). Per this task's §5 ("if the D10 tooling does not yet exist, implement ONLY the minimum D10 baseline capability... strictly according to the authoritative H2 specification"), it was implemented directly from the canonical spec's §9 "Final Drift Verification Contract (Corrected)" table (DRIFT-01 through DRIFT-09, including the DRIFT-08 ownership table and the DRIFT-07 Orchestrator exception) — not invented independently.

**What exists now:**
- `scripts/check_drift.py` — all 9 checks, AST-based, JSON output, the one documented DRIFT-07 exception encoded explicitly (not silently whitelisted — see the `DRIFT_07_EXCEPTIONS` set and its inline comment requiring a spec citation for any future entry).
- `tests/test_check_drift.py` — 18 tests. Unit-level tests hit the pure per-tree detection helpers directly (via `ast.parse()` on synthetic snippets, not temp files) because the top-level check functions close over module-level `REPO_ROOT`/`CORE`; two integration-level tests run `run_all()` against the real repository.
- `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json` — the actual captured baseline, generated *before* any D3/D7/D11 code change in this task (correct ordering, per this task's own §5 diagram).

**A real bug was found and fixed during this work, not just during design:** the first version of DRIFT-07 matched only `.append("cognitive....", ...)` calls. The actual codebase emits these events through a wrapper (`core/orchestrator.py`'s `self._emit_event("cognitive.planner_impasse_terminal", {...})`), which that version silently missed entirely — a **false PASS caused by an implementation bug**, not a real clean result. Caught by testing against the one known-positive case that had to exist (the Orchestrator's own terminal-impasse emission), not by re-reading the code. Fixed by keying the check to the `cognitive.`-prefixed string-literal argument itself, regardless of which method carries it, and pinned in place by `test_cognitive_event_violations_catches_wrapper_method_not_just_append`. This is recorded here because it's exactly the kind of failure mode §6 of this task warns about ("Do NOT force the baseline to zero violations by modifying H1") — the risk runs the other way too: a checker that's silently blind produces a false-clean baseline just as dangerously as one that's silenced by editing the target code.

**Baseline result — classified per §6's required categories:**

| Check | Status | Classification | Evidence |
|---|---|---|---|
| DRIFT-01 | PASS | PASS | No `core.workflow.runtime` import anywhere in `core/cognitive/*.py` |
| DRIFT-02 | PASS | PASS | No `core.capabilities.adapter_runtime` import anywhere in `core/cognitive/*.py` |
| DRIFT-03 | PASS | PASS | `supervisor.py` imports neither `plan` nor `compile` from their owner modules |
| DRIFT-04 | PASS | PASS | `RawRequest(...)` constructed only in `core/cognitive/intent.py` |
| DRIFT-05 | PASS | PASS | No `.evaluate_action(...)` call site in `supervisor.py` |
| DRIFT-06 | PASS | PASS (heuristic) | No `<expr>.*type* == "literal"` pattern found in `planner.py` routing |
| DRIFT-07 | PASS | **EXPECTED EXCEPTION applied** | `core/orchestrator.py:333` emits `cognitive.planner_impasse_terminal` — the one documented exception, applied explicitly, not silently |
| DRIFT-08 | PASS | PASS | None of the six canonical contracts constructed outside their declared owner file |
| DRIFT-09 | PASS | PASS (heuristic, lower confidence — see script docstring) | No foreign-file function declares a canonical contract as its return type |

**Zero KNOWN BASELINE VIOLATIONS, zero NEW/UNEXPECTED VIOLATIONS.** The one EXPECTED EXCEPTION is the single one the spec itself names — nothing was whitelisted beyond that. Per this task's H2 Stop Condition #1 ("STOP if any DRIFT check fails on current repo before H2 changes"): **not triggered — D3/D7/D11 may proceed once separately authorized.**

Full regression suite re-run after adding this code: **1174 passed / 34 failed** (1156 + 18 new drift tests = 1174, exact arithmetic match; 34 failures unchanged in count, and spot-checked — not just counted — to confirm they're the same `huggingface.co`-connectivity class, e.g. `test_planner_capability_migration.py::TestCompositionRootShape::test_full_chain_planner_to_model_router_adapter` fails with the literal `"Check your internet connection ... huggingface.co"` message). **Zero regressions from adding this code.**

---

## 4. Current H2 Authority

Re-verified this session (not assumed from the freeze review): `ADR_INDEX.md`, `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, and the canonical spec's own §12 "Corrected H2 Implementation Specification" all agree: **H2 = D3, D7, D10, D11, D12.** No item has changed since the freeze review. The task prompt's assumed list (§7) matches the repository exactly — confirmed, not assumed.

---

## 5. H2 Scope

| Item | One-line scope | Exact deliverable(s), from canonical spec §12 |
|---|---|---|
| D3 | Capability discrimination | `[NEW] tests/test_capability_discrimination.py` |
| D7 | Terminal impasse diagnostics | `[MODIFY] core/orchestrator.py` — **already done in H1**, this session verified it directly (§8 below) |
| D10 | Architecture drift tooling | `[NEW] scripts/check_drift.py` (done, this session) + `[NEW] tests/test_architecture_drift.py` (not yet — see §10) |
| D11 | Language support | `[MODIFY] core/cognitive/intent.py` |
| D12 | Tracking hardening | 3 new ADRs (H-10–H-12) + tracker/roadmap/state doc updates |

---

## 6. H2 Dependency Graph

```
D10 baseline capability (DONE, this session)
  └── unblocks: D3, D7, D11 may now safely be diffed against a real "before" snapshot

D3 (capability discrimination)
  ├── depends on: H1's frozen CapabilityContract/CapabilityMatch/discover_capabilities() (available now)
  └── establishes: H2-G1, H2-G2

D7 (terminal impasse diagnostics)
  ├── depends on: H1's recovery budget + event foundation (available now, already emitting)
  └── establishes: H2-G3 — verification/closeout, not net-new build (§8)

D11 (language support)
  ├── depends on: H1's frozen RawRequest contract — MUST detect before construct, not mutate after
  ├── affects: capability matching only if a future change explicitly wires detected_language into
  │     discovery scoring — confirmed NOT true today (canonical spec §16 Q3: "Planner consumes Goal,
  │     not RawRequest.detected_language")
  └── establishes: H2-G4

D12 (tracking hardening)
  └── no code dependencies — pure documentation, fully parallel

D10 full packet (test_architecture_drift.py + CI wiring)
  ├── depends on: D3/D7/D11's file changes existing, so the DRIFT-08/09 ownership scan has
  │     something meaningful to check beyond the current baseline
  └── establishes: H2-G5, H2-G9 (ongoing, not just at freeze time)

H2 integration packet
  └── depends on: all of the above landing — establishes H2-G6, H2-G7, H2-G8
```

---

## 7. Parallelization Matrix

| Packet | Depends on | Files touched | Contract deps | Parallel-safe? | Integration requirement |
|---|---|---|---|---|---|
| D10 baseline capability | — | `scripts/check_drift.py`, `tests/test_check_drift.py`, `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json` | Reads all H1 frozen contracts; writes none | N/A — already done, must run before the rest | This document is that integration point |
| D3 | D10 baseline (informational only, not a code dependency) | `tests/test_capability_discrimination.py` (new); possibly `core/cognitive/planner.py` if D3's own tests reveal `discover_capabilities()` doesn't yet satisfy ordering-independence — see §8 | `CapabilityContract`, `CapabilityMatch`, `discover_capabilities()` (read/exercise only, extend only if a real gap is found) | **Yes**, parallel with D7, D11, D12 | Full suite + D10 re-run at integration |
| D7 | D10 baseline (informational) | `core/orchestrator.py` (closeout only — base event already exists) | `cognitive.planner_impasse_terminal` payload (extend only if H2-G3's "full payload" bar isn't already met — it appears to be, §8) | **Yes** | Full suite + D10 re-run |
| D11 | D10 baseline (informational); H1's frozen `RawRequest` | `core/cognitive/intent.py` | `RawRequest` (additive field only — `detected_language: Optional[str] = None`) | **Yes**, with one coordination note below | Full suite + D10 re-run |
| D12 | None | `docs/architecture/decisions/ADR_K4_2_H_10..12_*.md`, `IMPLEMENTATION_TRACKER.md` (does not exist yet — see §11), `IMPLEMENTATION_ROADMAP.md`, `CURRENT_STATE.md` | None (documentation only) | **Yes, fully** | None beyond normal doc-sync |
| D10 full packet (`test_architecture_drift.py` + CI wiring) | D3/D7/D11 landing (so there's something to have checked "after H2") | `tests/test_architecture_drift.py` (new) | Reads the same 9 checks | **No — run last**, alongside integration | Is itself part of the integration packet's evidence |
| H2 integration packet | D3, D7, D10 full, D11, D12 all landed | None new — verification only | All of the above | **No — must run last** | This is the terminal gate: H2-G6 through H2-G9 |

**One coordination note (not automatically enforced by file separation alone):** if a D11 session or a D3 session unilaterally decides to wire `detected_language` into capability-discovery scoring, that's a `CapabilityMatch` evidence-shape change both packets would need to agree on. Confirmed not planned today (§6) — flagging so two parallel sessions don't independently invent it.

---

## 8. D3 Packet — Capability Discrimination

- **Packet ID:** K4.2-H2-D3
- **Title:** Capability Discrimination Acceptance Suite
- **Objective:** Prove, with a genuinely distinct second capability class, that discovery discriminates correctly — not just that it fails to crash.
- **Scope:** New test file. Production code change only if this packet's own tests reveal a real gap (see "Open question" below) — not a foregone conclusion.
- **Owner:** `tests/test_capability_discrimination.py` (new)
- **Dependencies:** D10 baseline capability (informational — run it before and after). Not blocked by D7/D11/D12.
- **Blocking packets:** none
- **Allowed files:** `tests/test_capability_discrimination.py`; `core/cognitive/planner.py` *only if* the open question below resolves to "yes, a real gap exists"
- **Forbidden files:** everything else, in particular `core/cognitive/intent.py`, `core/cognitive/compiler.py`, `core/capabilities/*` production registrations
- **Contracts consumed:** `CapabilityContract`, `CapabilityMatch`, `CapabilityDiscoveryResult`, `discover_capabilities()`
- **Contracts extended:** none expected
- **Frozen contracts that MUST NOT change:** `min_score=0.01` (H1 explicitly kept this un-weakened — do not touch it here either), `CapabilityMatch`'s existing evidence fields
- **Required invariants:** specific evidence outranks general-purpose fallback when both are present; a general-purpose capability is a fallback, never a semantic override (H1's Decision 2 invariant, D3 verifies it more thoroughly, does not redefine it)

**Six required behaviors** (three source documents label these slightly differently — the original H1 packet's "Test 1–6", this task's own §8 "Cases A–F", and the canonical spec's "Cases A–E + dynamic registration test" — noted so a future session isn't confused by the mismatch; substance is identical across all three):

| This task's label | Behavior | Notes for the implementer |
|---|---|---|
| A — General-purpose fallback | A broad request with no specific match is rescued by the general-purpose capability | H1's existing `test_general_purpose_bypasses_min_score` already covers this against the real `LLM_COMPLETION` capability — D3 should use a **test-only** general-purpose capability instead, to keep this suite independent of production capability wording |
| B — Specificity dominance | A genuinely distinct specific capability outranks the general-purpose fallback | H1's `test_specificity_dominance_ranks_specific_above_general` already does this with a test-only `flight_booking` contract — reuse that pattern rather than inventing a third one |
| C — Unsupported request | Neither capability is selected for a request outside both their semantics | **Not covered by any existing H1 test.** This is the one case H1 didn't build, per the freeze review §7's negative finding — genuinely new coverage needed |
| D — Registration-order independence | Registering the two test capabilities in the opposite order does not change which one wins | **Not covered by any existing H1 test.** Also genuinely new — and worth treating as an *open question*, not a foregone PASS (see below) |
| E — Dynamic registration | Adding the second capability requires zero changes to `planner.py` | Should follow naturally from registry-based discovery (DRIFT-06 in the D10 baseline already confirms no hard-coded type strings exist in routing today) — write the test as a genuine proof, not an assumption |
| F — Evidence | The winning `CapabilityMatch` exposes *why* it won | H1's tests already assert on `evidence["specificity_tier"]`/`evidence["general_fallback"]` inline — D3 should do the same as an explicit, named test, not just inline within another test |

**Open question for the implementing session, not resolved here:** does the current `discover_capabilities()` scoring already guarantee order-independence (Case D), or does it have an implicit "first capability at max score wins" tie-break that's registration-order-dependent? This wasn't testable during this planning pass without writing the actual test, and guessing the answer would violate this task's own "Do not weaken min_score as a shortcut" / "do not silently choose" discipline. **The D3 packet's first job is to write Case D's test and find out — only then decide whether `planner.py` needs a change.**

- **Tests:** the six above, each independently named and assertable; **boundary test:** confirm the test-only capabilities are registered in a scope-local `CapabilityRegistry`, never touching the production registry; **integration test:** run the six against the real `discover_capabilities()` function (not a mock of it).
- **Diagnostic requirements:** none new — this packet consumes existing `CapabilityMatch` evidence, doesn't add a new failure type.
- **Acceptance criteria:** all six cases pass; `min_score` unchanged; zero new DRIFT violations (re-run `check_drift.py`).
- **Stop conditions:** if Case D fails and requires a `planner.py` scoring change beyond a trivial deterministic tie-break, STOP and write an ADR before proceeding — that would be extending a frozen-adjacent contract's *behavior*, not just adding a test.
- **Rollback:** trivial — new test file only, unless the open question triggers a `planner.py` change, in which case standard revert.
- **Expected completion report:** `docs/Bugs Hunt & fix reports/K4_2_H2_D3_COMPLETION_REPORT.md`, following this project's nine-step packet template.

---

## 9. D7 Packet — Terminal Impasse Diagnostics

- **Packet ID:** K4.2-H2-D7
- **Title:** Terminal Impasse Diagnostic Closeout
- **Objective:** Confirm (not build) that H2-G3 is satisfied; enrich only if a real gap is found.
- **Scope:** Verification-first. **This session already did the verification** — see below. What's left is formal closeout.

**Verified this session, directly against the code (not inferred from H1's own claims):** `core/orchestrator.py`'s re-plan loop emits `cognitive.planner_impasse_terminal` via `self._emit_event(...)` with `trace_id`, `operation_id`, `interaction_id`, `goal_id`, `impasse_detail`, and (per the freeze review's earlier read) `recovery_budget_state`. `check_drift.py`'s DRIFT-07 explicitly whitelists this exact emission site as the one declared exception. **H2-G3 ("Terminal impasse diagnostic: `cognitive.planner_impasse_terminal` emitted with full payload") is already satisfied by the existing H1 commit.**

- **Owner:** `core/orchestrator.py` (no changes expected; verification lands in documentation, not code)
- **Dependencies:** none
- **Allowed files:** none for code; `docs/architecture/decisions/ADR_K4_2_H2_D7_CLOSEOUT.md` (or equivalent, per D12's convention) to record the closeout
- **Forbidden files:** `core/orchestrator.py` — do not add per-attempt (non-terminal) event emission here; that would be new scope beyond what D7's own canonical spec entry authorizes (the spec's own language is "terminal impasse", singular, not "every impasse")
- **Frozen contracts that MUST NOT change:** the `cognitive.planner_impasse_terminal` payload shape H1 already shipped and tested
- **Tests:** none new required — H1's `TestTerminalImpasseEvent` (in `tests/test_orchestrator_recovery.py`) already covers this
- **Acceptance criteria:** a one-paragraph closeout record citing the exact code (file/line) and test that satisfy H2-G3, so a future session doesn't re-open this
- **Stop conditions:** if a future session decides per-attempt diagnostics genuinely are needed, that's new scope requiring its own ADR and roadmap entry — not a silent extension of D7
- **Expected completion report:** short — this is closeout, not implementation. Fold into D12's tracking updates rather than a standalone report.

---

## 10. D10 Packet — Architecture Drift Tooling (full packet, beyond this session's baseline capability)

- **Packet ID:** K4.2-H2-D10
- **Title:** Architecture Drift CI Integration
- **Objective:** Wire the already-built `scripts/check_drift.py` into the normal pytest run, per the canonical spec's own `[NEW] tests/test_architecture_drift.py` — "Pytest wrapper importing check_drift. One test per DRIFT check" — item, which this session deliberately did not build (out of the authorized "minimum baseline" scope).
- **Scope:** `tests/test_architecture_drift.py` (new) — nine thin tests, one per `DRIFT-0N`, each asserting `result.status == "PASS"` by calling `check_drift.check_drift_0N()` directly (reusing the already-tested detection logic from `tests/test_check_drift.py` — this file's job is CI wiring, not re-testing detection correctness).
- **Owner:** `tests/test_architecture_drift.py`
- **Dependencies:** D3/D7/D11 having landed, so there's a genuine "after H2" state to check, not just a repeat of this session's baseline
- **Allowed files:** `tests/test_architecture_drift.py`; `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json` superseded by (or diffed against) a new post-H2 capture
- **Forbidden files:** `scripts/check_drift.py` itself, unless a genuine detection bug is found the same way this session found the DRIFT-07 one — in which case fix it the same way (with a regression test), don't just adjust the target code to dodge it
- **Contracts consumed:** the `CheckResult`/`Violation` dataclasses `check_drift.py` already exports
- **Required invariants:** DRIFT-06 and DRIFT-09 (the two heuristic checks) should assert `status == "PASS"` too, but if either legitimately trips on a real D3/D7/D11 change, that's a signal to read the heuristic's own documented limitation (in `check_drift.py`'s docstrings) before assuming it's a real violation
- **Acceptance criteria:** H2-G5 ("DRIFT-01 through DRIFT-09 pass") — this becomes a real, CI-enforced gate for the first time, not just a one-off script run
- **Stop conditions:** per this task's own §6 — if a check fails because the *rule itself* is wrong (too broad, or a legitimate new architectural pattern it doesn't yet know about), STOP and correct the rule via ADR before forcing the check to pass by touching unrelated code
- **Rollback:** trivial, test-file-only
- **Expected completion report:** fold into the H2 integration packet (§13) rather than standalone, since this packet's whole purpose is closing the loop on the others

---

## 11. D11 Packet — Language Support

- **Packet ID:** K4.2-H2-D11
- **Title:** Request Language Detection
- **Objective:** Add best-effort language metadata without touching capability-matching semantics.
- **Scope:** `core/cognitive/intent.py` only, per canonical spec §12's exact pattern:
  - `RawRequest` gains `detected_language: Optional[str] = None`
  - `normalize_request()`: `language = _detect_language(text); return RawRequest(text=text, detected_language=language)` — detection happens **before** construction, respecting `RawRequest.frozen=True` (H1's contract — do not work around it with `dataclasses.replace()` or a post-hoc mutation; DRIFT-04/08 would (correctly) flag a second construction site if this is done wrong)
- **Owner:** `core/cognitive/intent.py`
- **Dependencies:** H1's frozen `RawRequest` (read-only dependency — this is an additive field, not a redefinition)
- **Allowed files:** `core/cognitive/intent.py`; its test file
- **Forbidden files:** `core/cognitive/planner.py` — do not wire `detected_language` into `discover_capabilities()` scoring unless a future, separately-authorized change explicitly calls for it (§6's coordination note)
- **Contracts extended:** `RawRequest` (additive field only — existing consumers unaffected)
- **Frozen contracts that MUST NOT change:** `RawRequest.text` semantics, `frozen=True`, all six DRIFT-08 ownership declarations (this change must not create a second `RawRequest(...)` construction site)
- **Required invariants:** unknown-language input must fall back to `None`, never raise — H2's own stop condition #2 says exactly this: "STOP if language detection dependency unavailable — fall back to `None`"
- **Tests:** unit tests for `_detect_language()` itself (known-language input, unknown/gibberish input, empty string); a construction test confirming `RawRequest.detected_language` is populated and the frozen contract still holds; a negative test confirming `discover_capabilities()`'s behavior is *unchanged* by this field's presence (guards the §6 coordination note mechanically, not just by convention)
- **Diagnostic requirements:** none new
- **Acceptance criteria:** H2-G4 ("`detected_language` field present; frozen construction pattern works; no silent output language change")
- **Stop conditions:** the dependency-unavailable fallback above; also STOP if implementing this reveals `normalize_request()` has more than one call site (would itself be a pre-existing DRIFT-04-adjacent question worth flagging, not silently working around)
- **Rollback:** additive field, `None` default — safe to revert without touching other consumers
- **Expected completion report:** `docs/Bugs Hunt & fix reports/K4_2_H2_D11_COMPLETION_REPORT.md`

---

## 12. D12 Packet — Implementation Tracking Hardening

- **Packet ID:** K4.2-H2-D12
- **Title:** Tracking & Documentation Hardening
- **Objective:** Let a future Claude session answer "what's complete/active/blocked/deferred, by which commit, under which ADR, with what verification" without re-deriving it from scratch.
- **Scope:** Documentation only — reuses existing tracking files, per this task's own explicit instruction ("Do not create a new tracking system").
- **Deliverables (per canonical spec §12):**
  1. Three new ADRs: `ADR-K4.2-H-10` through `ADR-K4.2-H-12`, covering the D10/D11/D12 decisions the same way `ADR-K4.2-H-01..09` covered H1's.
  2. `IMPLEMENTATION_TRACKER.md` — **note: this file does not currently exist in the repository.** Both the H1 completion report and this session's own repo search confirm it. Every referencing document (this task's own §2 reading list, the original H1 packet) assumes it exists. **This is worth its own explicit decision, not a silent creation**: either (a) create it now, as part of D12, with a clear scope so it doesn't duplicate `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`, or (b) formally note in `KNOWN_ISSUES.md` that this file is referenced but intentionally not created, and those two existing files serve its purpose. Flagged here rather than decided — matches the standing project rule of not silently resolving a discrepancy multiple sessions have now independently noticed.
  3. `IMPLEMENTATION_ROADMAP.md`/`CURRENT_STATE.md` updates recording D3/D7/D10/D11 completion, matching the same style used for H1's freeze (§1–2 above).
  4. `PROJECT_INDEX.md`'s report chronology — already flagged as lagging since ~July 2026 (this session's H1-freeze commit `6ff604c` noted it, didn't fix it). D12 is the natural place to actually catch it up, if authorized.
- **Owner:** documentation files only
- **Dependencies:** ideally runs after D3/D7/D10/D11 land, so it records real outcomes rather than placeholders — but nothing prevents drafting the ADR skeletons earlier
- **Contracts touched:** none — pure documentation
- **Acceptance criteria:** a future session, given only `CURRENT_STATE.md` + `IMPLEMENTATION_ROADMAP.md` + `KNOWN_ISSUES.md` + `ADR_INDEX.md`, can correctly state H2's status without reading any code
- **Stop conditions:** none — lowest-risk packet in H2
- **Expected completion report:** fold into the H2 integration packet, since D12's entire job is documentation synchronization

---

## 13. H2 Integration Packet

- **Packet ID:** K4.2-H2-INTEGRATION
- **Title:** Cross-Packet H2 Verification
- **Objective:** Confirm D3 + D7 + D10(full) + D11 + D12 are mutually consistent, not just individually correct.
- **Runs:** last, after all five packets above land.
- **Steps:**
  1. `git fetch` + re-verify no untracked upstream drift (this session's own established discipline — twice caught real parallel commits this way).
  2. Re-run `scripts/check_drift.py` — compare against `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json` (this session's artifact). Any *new* violation is scoped to exactly the H2 diff, by construction — H2-G9.
  3. Full regression suite — compare against **1174 passed / 34 failed** (this session's post-D10-baseline number, itself compared against the 1156/34 H1 number) — H2-G6, H2-G7.
  4. Spot-check, don't just count, any failure whose test name wasn't in the known 34 — same discipline used throughout this whole engagement.
  5. `trace_id` → event → `caused_by` → failure-chain reconstruction test — H2-G8. Not yet exercised by anything built this session; the integration packet is where it should first be proven end-to-end across D3's new discrimination paths and D7's existing terminal event.
- **Acceptance criteria:** the canonical H2-G1 through H2-G9 table (§18 below), all passing.
- **Stop conditions:** any A (regression) or E (ambiguous) finding, same classification discipline as the H1 freeze review — blocks K4.2 v1.0 freeze, not just H2.
- **Expected completion report:** `docs/Bugs Hunt & fix reports/K4_2_H2_FINAL_INTEGRATION_REPORT.md`, structured the same way `K4_2_H1_FINAL_FREEZE_REVIEW.md` was.

---

## 14. Cross-Milestone Contract Rules

Restated with the specific contracts this session actually touched or read, not just the generic list from §21 of the task prompt:

| Contract | May H2 packets extend it? | May they redefine it? |
|---|---|---|
| `RawRequest` | Yes — additive field (`detected_language`), D11 only | No — `frozen=True`, single construction site (`normalize_request()`), enforced by DRIFT-04/08 |
| `Goal` semantics | No | No — D1's raw→Goal→derived-views layering is untouched by any H2 item |
| `CapabilityMatch` | Only if D3's Case D forces a real scoring change (open question, §8) — and only via ADR | No |
| `OperationRecoveryBudget` | No H2 item touches this | No |
| `trace_id`/`operation_id`/`stage_tag` | D3/D7 may *read* these for evidence; no H2 item redefines them | No |
| `derived_from`/`caused_by` | H2-G8's causal-chain test reads these; no H2 item redefines them | No |
| `interpret_request`/`plan`/`compile` boundaries | No | No |
| Governance boundary | No H2 item introduces a governance call anywhere new | No |
| Capability/Adapter boundary | No H2 item touches `AdapterRuntime` | No |
| Kernel execution boundary | No | No |

If any H2 packet discovers it genuinely needs to change one of these: stop, write the ADR, identify affected consumers and migration requirements, get explicit approval — exactly the task prompt's §13 process, restated here against this repository's actual contracts rather than a generic list.

---

## 15. Diagnostic Requirements

No H2 packet invents a new failure object, retry counter, event transport, or recovery authority — confirmed nothing in §8–12 above requires one:
- D3 produces test assertions, not runtime failures.
- D7 is verification of an existing failure/event path, adds nothing new.
- D10 produces `CheckResult`/`Violation` (already built, already tested) — a static-analysis report, not a runtime diagnostic object, and explicitly not something `core/` production code depends on.
- D11's only new failure mode ("language detection unavailable") is explicitly required to degrade to `None`, not raise or produce a new failure record.
- D12 is documentation.

Diagnostic reason codes, recovery ownership, and terminal-state semantics all remain exactly what H1 established (§2, §14 above) — H2 hardens observability around that foundation, it doesn't add a second one.

---

## 16. Test Baseline & Verification Strategy

| Point in time | Passed | Failed | Source |
|---|---|---|---|
| H1 baseline (pre-existing, before H1) | 1112 | 34 | Cited in H1 completion report, independently reproduced in the freeze review |
| H1 complete | 1156 | 34 | Independently reproduced twice in the freeze review |
| **This session, after D10 baseline capability** | **1174** | **34** | Run directly this session; 1156 + 18 new drift tests = 1174, exact match; 34-count unchanged, spot-checked not just counted |

**Strategy for each remaining H2 packet:** run the full suite before and after; any new failure gets the same five-way classification the freeze review used (A regression / B pre-existing / C environment / D unrelated existing / E ambiguous). Never claim "all tests pass" — the 34 environment failures are a known, standing fact of this sandbox (no `huggingface.co` egress), not something any H2 packet is expected to fix.

---

## 17. Risks

Canonical spec §15's R1–R5, plus R6 from the freeze review, plus two new ones surfaced by actually building D10 this session:

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1–R5 | (unchanged from canonical spec / freeze review — Orchestrator loop complexity, Supervisor dual-path, `.contracts` compat property, language-detection availability, DRIFT-07 exception whitelisting) | — | See freeze review §19 |
| R6 | D10's baseline-first ordering isn't mechanically enforced, only documented | Low–Medium | This document *is* the enforcement mechanism until `test_architecture_drift.py` exists — a future session skipping straight to D3 without reading this loses nothing technically (the baseline is already captured), but should still read §3 first |
| **R7** *(new)* | Heuristic checks (DRIFT-06, DRIFT-09) can produce false positives on legitimate H2 code the checker's author (this session) didn't anticipate | Low | Documented explicitly in `check_drift.py`'s own docstrings as lower-confidence; the D10 full packet's stop condition (§10) already routes a heuristic trip to "read the limitation, don't force a workaround" |
| **R8** *(new)* | A checker with a silent detection bug is *more* dangerous than no checker — it produces false confidence | Medium, actively mitigated | This is exactly what happened during this session's own DRIFT-07 implementation (see §3) — mitigated by testing against a known-positive case before trusting any PASS result; the same discipline should apply to any future modification of `check_drift.py` |

---

## 18. H2 Acceptance Gates

The task prompt's own §17 offers a 10-gate template and explicitly says "verify the exact repository-defined gate list and adjust it where necessary." The repository already has one — the canonical spec's §13 "Corrected H2 Acceptance Gate" — which is more specific than the template (e.g. the template's generic "H2-G2 Unsupported requests terminate correctly" is actually the canonical spec's "H2-G2 Dynamic registration discovered without code change"; Case C, unsupported-request, is folded into H2-G1's "all 5 discrimination cases"). Per repository authority (this task's own §2), the canonical table below supersedes the template:

| Gate | Description | Type | Pass condition | Status (this session) |
|---|---|---|---|---|
| H2-G1 | Cases A–E | Integration | All 5 discrimination cases pass | Not yet built (D3) |
| H2-G2 | Dynamic registration | Integration | New capability discovered without code change | Not yet built (D3) |
| H2-G3 | Terminal impasse diagnostic | Integration | `cognitive.planner_impasse_terminal` emitted with full payload | **Already satisfied by H1** — verified directly this session (§9) |
| H2-G4 | Language preservation | Unit | `detected_language` field present; frozen construction pattern works; no silent output language change | Not yet built (D11) |
| H2-G5 | Architecture drift CI | Static | DRIFT-01 through DRIFT-09 pass | Baseline capability built + captured this session (§3); CI wiring not yet built (D10 full) |
| H2-G6 | Complete regression | Suite | All pre-existing + H1 + H2 tests pass | Currently 1174/34, unchanged failure class (§16); H2 packets' own tests not yet added |
| H2-G7 | H1 contracts preserved | Suite | All H1-G1 through H1-G11 still pass | Confirmed unbroken this session (§3's regression re-run) |
| H2-G8 | Diagnostic causal tracing | Integration | `trace_id` → events → `caused_by` → failure chain queryable | Not yet exercised end-to-end (§13) |
| H2-G9 | No boundary violations | Static + Review | No DRIFT failures; diff is H2-scoped only | Zero violations in this session's baseline (§3); becomes an ongoing gate once D3/D7/D11 land |

**H2 FREEZE requires all 9. K4.2 v1.0 FREEZE = H1 FREEZE + H2 FREEZE** (canonical spec §13) — H1 side of that is done (see the freeze review); H2 side is not yet.

---

## 19. Stop Conditions

Consolidated from the canonical spec, this task's prompt, and this session's own findings:

1. Any DRIFT check fails on the *current* (pre-H2) repo → checker or rule is wrong, fix before proceeding. **Checked this session: does not trigger.**
2. Language-detection dependency unavailable → fall back to `None`, never raise (D11).
3. D3's Case D reveals `discover_capabilities()` needs more than a trivial deterministic tie-break → write an ADR before changing it; do not silently extend the scoring contract.
4. Any H2 packet needs to change a §14 frozen contract → full stop-document-request-approve cycle, no exceptions.
5. Any regression (Category A) or ambiguous finding (Category E) at the integration packet → blocks K4.2 v1.0 freeze, same discipline as the H1 freeze review.
6. `IMPLEMENTATION_TRACKER.md`'s existence question (§12) → explicit decision required, not silent creation or silent continued absence.

---

## 20. Final Authorization Status

**D10 minimum baseline capability: IMPLEMENTED, TESTED, CAPTURED.** `scripts/check_drift.py` + `tests/test_check_drift.py` (18 tests, all passing) + `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json`, all pending commit alongside this document.

**D3, D7, D11, D12, and D10's own full CI-wiring packet: DEFINED, NOT IMPLEMENTED.** Per this task's own §20 boundary, none of these begin in this task. Each packet spec above (§8–12) is written to be independently understandable by a Claude session that has never seen this conversation, per §14's requirement.

**Recommendation:** commit this document + the D10 baseline capability now (documentation and a static-analysis tool with its own tests — no H1/H2 frozen contract touched). Then authorize packets individually or in the parallel-safe group (D3 + D7 + D11 + D12 together, §7) — each is scoped tightly enough that a separate Claude session, or a separate conversation turn, can pick one up using only this document.
