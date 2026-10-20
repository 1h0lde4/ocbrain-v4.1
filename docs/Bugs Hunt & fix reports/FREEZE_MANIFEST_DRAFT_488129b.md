# Kernel v1.0 Freeze Manifest — DRAFT v0.1

**Pinned SHA: `488129b8768a88a3d21dfd80b1f5407d50aba908`** (`origin/main`, Oct 16, 2026) · drafted 2026-10-17 17:46 UTC
**Status: DRAFT. NO FREEZE VERDICT IS RENDERED.** Per the owner's decision record, three steps stay separate: (1) drafting this manifest, (2) accepting individual decisions, (3) declaring the Kernel freeze-ready. This document is step (1) only. It does **not** apply the criteria in §3 to the evidence in §4 — that happens after the owner ratifies §3.

Evidence labels: **VERIFIED** (I ran it / read live API data at the pin) · **READ** (seen in a file or PR body; not exercised) · **REPORTED** (a record asserts it; I did not re-verify) · **NOT CHECKED**.

Historical baselines referenced: `ecddbff` (the Oct 1 audit's baseline) · `3f8ef97` (my scoping memo's pin). \1 **As of Oct 18, `origin/main` is `ef426e9` (2 commits ahead of the pin); the pin is unchanged.**

---

## 1. Reproducibility

Evidence at the pin was produced in a throwaway `git worktree` of exactly this SHA, in a sandbox **without** `torch`/`sentence-transformers` (with `trafilatura`); the repository's own CI (full dependencies) is recorded separately. Commands: `pytest -q`, `pytest <the five files that name FZ items>`, `python3 scripts/check_drift.py`, plus live GitHub REST reads (`check-runs`, `code-scanning/alerts`, `dependabot/alerts`, `branches/main/protection`, PR bodies).

---

## 2. Sources and their authority

| Source | Role | Caveat |
|---|---|---|
| `OCBRAIN_KERNEL_CONSTITUTION.md`, `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` | **Normative** — the engineering contract | The architecture spec is a contract, **not** a current acceptance checklist |
| **Oct 1, 2026 Kernel v1.0 freeze audit** (baseline `ecddbff`; verdict *NOT FREEZE READY*, valid for that SHA only; named FZ-01..FZ-04 as blockers) | **Latest baseline-specific verdict and blocker record** (owner decision) | **The original document was not recovered.** A scan of every file ever added on any fetched ref and of all issue/PR titles finds only September audits. Its content is *reconstructed* from the register and PRs #51, #53, #55, #57, #67, #71, #83 (baseline, blocker designation, measured repros, defect descriptions, the B1–B10 remediation plan). **Its full verdict criteria therefore cannot be verified** |
| `docs/studies/OCBRAIN_KERNEL_V1_FREEZE_AUDIT_SEPT_2026.md` | Prior verdict record; its **§7 eleven-question gate** is the question set reused in §5 | Predates October. Its §8 verdict (*NOT_FREEZE_READY*, solely `DEBT-020`) concerned an item **resolved the same day** |
| `KNOWN_ISSUES.md` | Status register | **Can lag merged code** (§6 G1) |
| `CURRENT_STATE.md` | "What is built now" | Its Sept 23 verdict wording ("down to REM-004 and CTX-EXPORT-001's freeze classification") **predates the Oct 1 audit and was explicitly left unreconciled** (PR #57) |
| Owner decision record, PR #83 (dated 2026-10-16) | FZ-D1, FZ-D2 | **PR #83 is open, not merged** — decisions are recorded there, not yet on `main` |

---

## 3. Verdict criteria — PROPOSED, requires owner ratification *before* §4 is applied

**Scope.** Kernel v1.0 proper, per the frozen architecture. Control-plane and supply-chain risks appear in §7 as a *separate, explicit* disposition; a Kernel verdict must **not** imply the wider deployed product is secure.

**Verdict classes.** `FREEZE_READY` · `CONDITIONALLY_FREEZE_READY` (conditions enumerated, each needing an owner decision) · `NOT_FREEZE_READY` · `UNDETERMINED` (evidence for a blocker cannot be obtained).

| # | Criterion | Passes when |
|---|---|---|
| C1 | **Blocker closure** | Every blocker (the Sept 6 blockers; the Oct 1 audit's FZ-01..FZ-04; any item the owner designates) is **VERIFIED closed** by the closure standard — fix present, regression test exists *and was run*, its result supports the claim, residual scope documented, code/tests/docs consistent — **or** explicitly accepted by the owner as a scoped deferral |
| C2 | **Non-blocker findings** | Each (FZ-05, FZ-06, FZ-07, DEBT-0xx…) has a recorded disposition: VERIFIED / owner-accepted deferral / OPEN. OPEN items that the owner has not accepted as non-blocking become **conditions** |
| C3 | **Executable baseline** | At the pinned SHA: full suite has no failures/errors, drift check passes, required CI checks green, and every open CodeQL alert is dispositioned |
| C4 | **Eleven-question gate** | Each Sept 6 §7 question is re-answered at the pin; no answer may rest solely on an older document |
| C5 | **Contract conformance** | Evidence — stated with its scope and what is *not* verified — that the Constitution/architecture invariants checked by `check_drift.py` hold, plus a list of invariants that no check covers |
| C6 | **Register ↔ code consistency** | No registered status contradicts merged code at the pin; known mismatches are listed (§6) |
| C7 | **Decisions recorded** | Every owner decision a finding depends on is recorded on `main`; any still open is a named condition |
| C8 | **Scope statement** | §7 exists and the verdict text states its non-implication |

**Rules.** `FREEZE_READY` requires C1–C8. `CONDITIONALLY_FREEZE_READY` requires C3 and C8, C1 for every blocker, and the failures of every other criterion listed as conditions. `NOT_FREEZE_READY` if any blocker is neither VERIFIED closed nor owner-accepted, or C3 fails. `UNDETERMINED` if a criterion cannot be assessed (e.g. the Oct 1 audit's own criteria — see §2).

**Open for ratification:** (a) whether FZ-05/06/07 are blockers (the register names FZ-01..04); (b) the owner has said the two pinned FZ-02 outcomes are **not accepted** — treated here as *open components of FZ-02*; (c) whether C5 should require more than the drift check.

---

## 4. Evidence inventory at the pin (facts only — **criteria not applied**)

| Item | Registered status | Evidence at the pin | Label |
|---|---|---|---|
| **FZ-01** K4.2 path has no failure channel | OPEN; FZ-D1=(a) accepted Oct 16; implementation pending (batches B3/B4) | `core/orchestrator.py` K4.2 branch (lines ~526–556) reads `answer = wf_result.output or ""` and handles only `constraint_violations`; its **own comment (lines 547–555)** says genuine node errors are "deliberately left … still not checked on this branch. That is a real, separate gap." The legacy branch (line 715) does check `wf_result.success`. **This is the gap `DEBT-020`'s Sept 6 fix explicitly declined to close** — not a new discovery. **Repro not re-run:** no orchestrator-level harness exists — the Sept 6 `test_genuine_node_failure_is_not_relabeled_as_a_constraint_violation` exercises only `WorkflowRuntime.execute()` (a failed node ⇒ `success is False`), and `tests/core/cognitive/test_k42_completion.py` covers intent/language propagation. The gap is in how the *orchestrator consumes* that result | READ |
| **FZ-02** ModelRouter false completion | **Register on `main`: "OPEN — BLOCKED on D2 (not started)"** (stale — §6 G1). PR #83: "implemented + verified for provider-failure and stalled/deadline classes; residual outcome policy OPEN" | B2a (#67) and B2b (#71) merged; `test_fz02_provider_failure.py` fakes only the HTTP client (`httpx.ConnectError`) against the real router+adapter and asserts `success is False`; both FZ-02 test files pass. **Residual:** `EMPTY_RESPONSE`, `COMPLETED_WITH_PARTIAL_OUTPUT` remain `success=True` ("pinned") — **owner: not accepted** | VERIFIED (tests) / READ (test content) |
| **FZ-03** scheduler import failure killed `main.py` | FIXED + VERIFIED (PR #53) | `test_scheduler_failure_containment.py` passes. Residuals listed in PR #57 (`cleaner.run_all` still blocks the loop, etc.) | VERIFIED (tests) |
| **FZ-04** `AdaptiveSemaphore` permit loss | FIXED + VERIFIED (PR #51) | `test_adaptive_semaphore_permit_conservation.py` passes | VERIFIED (tests) |
| **FZ-05** unbounded growth (a: registry; b: EventStore) | OPEN — blocked (a: B6 after FZ-01/06; b: B7, needs FZ-D3) | **FZ-05a re-measured at the pin** (TestClient, `GET /executions/<random uuid>`): every unknown ID returns `200` and creates state in **both** `execution_registry._graphs` and `._queues`; after +1,000 IDs both = 1,000 (5.17 MB retained, ≈5,171 B/request), after +4,000 more both = **5,000** (+16.98 MB, ≈4,246 B/request) — **linear, no cap or eviction observed through 5,000 entries**. Extrapolating at ≈4.2–5.2 kB/request gives ≈85–100 MB per 20,000 IDs, consistent with the audit's reported +89.7 MB, but 20,000 itself was **not** run (a cap above 5,000 cannot be excluded). FZ-05b (EventStore retention) not re-measured | VERIFIED (5a, to 5,000) / REPORTED (20,000-scale, 5b) |
| **FZ-06** identity not joinable (4 namespaces) | OPEN | **Same defect as my Packet C `C-1` / `DEBT-030`** (`CapabilityRequest.trace_id` is a fresh random UUID); the two register rows **do not cite each other** | REPORTED |
| **FZ-07** CI gate discarded pytest's exit code | FIXED + VERIFIED (PR #55); residual R-1 open | `test_ci_test_gate.py` passes. Supersedes part of `DEBT-031` (the register says so) | VERIFIED (tests) |
| `DEBT-020` false completion | **Resolved Sept 6** (ADR-KERNEL-04) | Resolved section of the register; documented residual = FZ-01 (above) | READ |
| `DEBT-016`, `DEBT-003`, Scope/identity, `WorkerContext` | Resolved per Sept 6 §8 | Suite green; **not individually re-verified at the pin** | REPORTED |
| `CTX-AUTH-001b` | Implemented (ADR-KERNEL-06) | `TestCtxAuth001ParserAcceptance` reformulated and in the green suite | READ |
| `REM-004` (`docs/reports/context-compiler-remediation-register.md`) | `AuthorityLevel` taxonomy now exists | **Whether it is *sufficient as a Kernel v1.0 contract* has not been re-assessed since Sept 23** — needs an owner disposition | NOT CHECKED |
| `CTX-EXPORT-001` freeze classification | Named open in the Sept 23 `CURRENT_STATE.md` note | Export-side fix landed upstream; **classification not re-read** | NOT CHECKED |
| `DEBT-042` (my R6) | Open as PR #79, **synced to the pin's baseline** (head `bcbe574`, 0 behind `main`, full suite 2082 passed / 1 xfailed, drift 15/15) | Latent deletion sink; no production caller; **CI on the synced head (observed 2026-10-18 09:16 UTC): CodeQL=success, tests=success, drift-and-ownership=success, Analyze (actions)=success, Analyze (python)=success** | VERIFIED (local gates) |

### 4.1 Executable baseline

| Check | Result | Label |
|---|---|---|
| Full suite @ pin | **2072 passed, 1 xfailed** (the xfail: strict, ADR-KERNEL-07 slice, `test_creative_content_anchor.py:677`) | VERIFIED |
| FZ-item tests (5 files) | **146 passed** | VERIFIED |
| `check_drift.py` | **15/15 PASS** | VERIFIED |
| CI @ pin | `tests`, `drift-and-ownership`, both `Analyze` jobs: success | VERIFIED |
| CodeQL | 37 alerts: **33 fixed, 4 dismissed, 0 open** (the repo's text says 34 fixed — §6 G4) | VERIFIED / mismatch |
| Dependabot | 7 open; chromadb decision recorded by the owner (`DEBT-032`, Oct 6; #65/#70; PR #73) — see §7 | VERIFIED |
| Branch protection on `main` | required `tests` + `drift-and-ownership`, strict, **`enforce_admins: true`**, no required reviews, no force-push/deletion | VERIFIED |

---

## 5. The Sept 6 eleven-question gate — answers **pending** (C4)

To be answered at the pin *after* ratification of §3. Evidence that already bears on each:

| Q | Question | Evidence to weigh (not an answer) |
|---|---|---|
| 1–2 | What can it guarantee / verify? | Drift check (15), governance-before-mutation (`DEBT-001`), identity stability (ADR-KERNEL-01), watchdog (ADR-KERNEL-02); FZ-03/04/07 fixes |
| 3–4, 9 | What can it *not* verify / where can it hallucinate / cannot determine correctness? | FZ-01, FZ-02 residuals — a failed or empty generation can still read as success |
| 5 | Where can it fail silently? | FZ-01, FZ-02 residuals, FZ-05, FZ-06 (identity not joinable) |
| 6, 8 | Verification fails / evidence conflicts? | Verification/Critic/Evidence still not integrated (Sept 6: "not applicable") — **not re-checked** |
| 7 | Watchdog fails? | ADR-KERNEL-02; stalled/deadline classes now `success=False` (FZ-D2, B2b) |
| 10 | P2/P3 debt remaining? | `KNOWN_ISSUES.md` at the pin — **inventory not yet reconciled** |
| 11 | Deliberately deferred? | Sept 6 list; FZ-D3; REM-004 sufficiency — **needs reconciling** |

---

## 6. Register ↔ code reconciliation gaps (C6)

| # | Gap | Evidence |
|---|---|---|
| G1 | Register says FZ-02 "OPEN — BLOCKED on D2" and "Open maintainer decisions (none taken)"; B2a/B2b are merged and tests cite D1=(a), D2=(i) | PR #83 (open, CI 5/5 green) would correct it |
| G2 | `CURRENT_STATE.md`'s Sept 23 verdict wording is unreconciled with the Oct 1 audit | PR #57 states it |
| G3 | **`DEBT-033`'s text is stale**: it records an admin-exemption scope limit; the live setting is `enforce_admins: true` | live API; **PR #87 opened** (CI: CodeQL=success, drift-and-ownership=success, tests=success, Analyze (python)=success, Analyze (actions)=success) |
| G4 | CodeQL fixed-count: docs say 34, API lists 33 | one-alert mismatch, cause unknown |
| G5 | FZ-06 ≡ `DEBT-030`, unlinked | both rows read; **`DEBT-030` now cites FZ-06 in PR #87**; the FZ-06 row itself is untouched (PR #83 edits that block) |
| G6 | The Oct 1 audit's original document is missing | §2 |
| G7 | Decision IDs (D1..Dn) are reused across tracks (FZ, K4.2-H, `/import` issue #54, H2 packets) — qualify as *FZ-D2* etc. | register text |
| G8 | `DEBT-031` partly superseded by FZ-07 | register says so |
| G9 | Two test files say "this repository has no xfail convention"; one slice uses a strict xfail | READ |
| G10 | **17 compiled `.pyc` files are tracked in git** (`tests/__pycache__`: 10; `tests/core/cognitive/__pycache__`: 7; CPython 3.14 / pytest 9.0.3 bytecode) although `.gitignore` covers `__pycache__/`. Long-standing, not new (first added in commit 00386ea 2026-08-06). Harmless to behaviour; noise in diffs and `git grep` output | hygiene; owner call |

---

## 7. Control-plane and supply-chain disposition — SEPARATE from the Kernel scope (no verdict implied)

| Item | State | Label |
|---|---|---|
| `DEBT-025` `interface/api.py` has no authentication on any endpoint (loopback-bound; CSRF-header middleware real) | Open; disposition is the owner's | REPORTED |
| `DEBT-033` branch protection | **Live: required checks, strict, `enforce_admins: true`** → the admin-bypass residual recorded earlier no longer holds; the register row needs updating | VERIFIED |
| `DEBT-035` supply chain | Actions SHA-pinned, Dependabot configured (verified: its PRs exist). `pip-audit` and a release Environment still open | READ |
| `DEBT-032` / Dependabot | Owner decision (Oct 6; #65/#70; PR #73): keep `chromadb==0.5.3`, **embedded-only** security boundary, explicit reopen trigger; the three chromadb advisories list no patched version, ranges run through 1.5.9. Pin is provisional pending a compatibility study | READ |
| `DEBT-042` privacy deletion sink | Latent (no caller); fix in PR #79 | VERIFIED |
| Destructive-sink sweep (R7) | 133 call sites / 197 files; **no second unguarded, externally reachable sink found** — heuristic, recall validated on one known site (see `R7_DESTRUCTIVE_SINK_SWEEP_OCT2026.md`) | VERIFIED (scoped) |
| `PUT /config` | mutable keys: `ollama_host, debug, log_level, web_ui_port, auto_update` — none path-valued | READ |
| `DEBT-028`/`DEBT-029`/`DEBT-036` runtime concurrency/retry items | Latent/narrow per the register; not re-assessed at the pin | REPORTED |

**A Kernel freeze does not imply the deployed product is secure.**

---

## 8. Owner decisions — recorded vs. pending

Recorded (PR #83, Oct 16): **FZ-D1 = (a)** keep `handle() -> str`, add a structured internal result consumed by the API (no return-type change, no exception as primary channel) — a decision, *not* a claim it is implemented · **FZ-D2 = (i)** stalled/hard-deadline ⇒ `success=False`, partial text in `metadata["partial_output"]`. **Not accepted:** `EMPTY_RESPONSE`, `COMPLETED_WITH_PARTIAL_OUTPUT`. Other: PR #25 closed; chromadb pin (#65/#70); scope = Kernel v1.0 proper (this draft's reading of the owner's recommendation).
**Pending:** FZ-D3 (FZ-05b: which EventStream classes are audit-durable; archival acceptable?) · `REM-004` sufficiency · `CTX-EXPORT-001` classification · whether FZ-05/06/07 are blockers · merge of PR #83 and PR #79.

---

## 9. What this manifest cannot claim

The Oct 1 audit's own criteria are unverifiable (original not recovered) · FZ-01 and FZ-06 repros were **not re-run** (code inspection and the audit's recorded measurements only; there is no orchestrator-level harness for FZ-01); FZ-05a **was** re-measured at the pin, to 5,000 entries · the evidence is at one SHA that will move · the sandbox lacks the heavy ML stack (CI has it; both green) · the destructive-sink sweep is a heuristic · the Sept 6 resolved blockers were not individually re-verified at the pin.

## 10. To complete the manifest

1. Owner ratifies or amends §3. 2. FZ-05a is re-measured at the pin (done, §4). An FZ-01 repro needs an orchestrator-level harness that does not exist — decide whether building one is worth it, since the code comment, the register and the audit already agree. 3. Answer the §5 gate. 4. Reconcile §6 (merge #83; update `CURRENT_STATE.md`; update `DEBT-033`; link FZ-06 ↔ `DEBT-030`). 5. Obtain owner dispositions for §8's pending items. 6. **Re-pin**, re-run §4.1, then — and only then — apply §3 and write the verdict.
