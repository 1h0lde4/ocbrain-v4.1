# Freeze-manifest — scoping (Oct 2026)

**Status: read-only reconnaissance. No verdict is rendered and no manifest is drafted.** It exists so the manifest, when authorised, builds on what is already there instead of redoing it — and because three of my own working assumptions turned out to be wrong when I read the repo (§3).

Evidence labels: **VERIFIED** (ran it / read the live API) · **READ** (seen in a file, not exercised) · **INFERRED** · **NOT CHECKED**.

## 1. Pinned baseline — `main` @ `3f8ef97`

| Check | Result | Label |
|---|---|---|
| Full suite (throwaway worktree, sandbox: no torch/sentence-transformers, trafilatura installed) | **2072 passed, 1 xfailed**, exit 0 | VERIFIED |
| Tests naming the FZ items (`test_adaptive_semaphore_permit_conservation`, `test_ci_test_gate`, `test_fz02_provider_failure`, `test_fz02_stalled_deadline_failure`, `test_scheduler_failure_containment`) | **146 passed** | VERIFIED |
| `scripts/check_drift.py` | 15/15 PASS | VERIFIED |
| `main`'s own CI at that commit | `tests`, `drift-and-ownership`, `Analyze (python)`, `Analyze (actions)` all success | VERIFIED |
| CodeQL (live API) | 37 alerts: 33 fixed, 4 dismissed, 0 open. *The repo's text says 34 fixed — a one-alert docs-vs-API mismatch, unresolved* | VERIFIED / mismatch |
| The 1 xfail | `tests/core/cognitive/test_creative_content_anchor.py:677`, a **strict** xfail ("Test D (D-4)") in the ADR-KERNEL-07 slice — a tripwire. Two other test files still say "this repository has no xfail convention": small convention drift | READ |

`main` moves several times a day: **re-pin the SHA at the end**; a manifest is only valid for the SHA it names.

## 2. What already exists — the spine the manifest should follow

An **Oct 1, 2026 Kernel v1.0 freeze audit** (baseline `ecddbff`; verdict *NOT FREEZE READY, valid for that SHA only*; it named FZ-01..FZ-04 as blockers) produced a seven-item series, worked under an **Oct 2 remediation mission**, registered in `KNOWN_ISSUES.md` ("Kernel v1.0 Freeze Remediation (Oct 2026)", with a Oct 5 sync entry). *I did not locate the audit document itself by grepping for its baseline SHA under `docs/` — the register cites it; find it before the manifest.*

| Item | Finding (register's words, condensed) | Registered status (Oct 5) | Since |
|---|---|---|---|
| FZ-01 | K4.2 path has no failure channel — `/query` returns `success=True` with an empty answer | OPEN, blocked on **D1** (public result contract); depends on FZ-02 | — |
| FZ-02 | ModelRouter false completion: error text yielded as a normal token; `ModelRouterAdapter.execute()` hard-codes `success=True` | **OPEN — BLOCKED on D2 (not started; batch B2)** | **B2a (#67) and B2b (#71) merged — see §3 F1** |
| FZ-03 | A scheduler import failure terminated `main.py`, including the web server | FIXED + VERIFIED Oct 4 (PR #53, `80a1bb8`) | tests pass at `3f8ef97` |
| FZ-04 | `AdaptiveSemaphore` lost permits (shared instance state) | FIXED + VERIFIED Oct 3 (PR #51, `1a09941`) | tests pass |
| FZ-05 | Unbounded growth: `GET /executions/{id}` creates registry state for unknown IDs; `EventStore` append-only | OPEN | — |
| FZ-06 | Identity not joinable across events — four identity namespaces; `trace_id` separate | OPEN | — |
| FZ-07 | CI gate hole: the `tests` job discarded pytest's exit code, so collection errors/crashes/empty runs passed | FIXED + VERIFIED Oct 4; residual R-1 open | tests pass |

Open maintainer decisions, as the register words them: **D1** (FZ-01) public result contract; **D2** (FZ-02) stalled/deadline outcomes with partial output; D3 (not re-read here).

## 3. Findings so far

**F1 — The register lags merged code on FZ-02.** *VERIFIED:* the register says FZ-02 is "OPEN — BLOCKED on D2 (not started; batch B2)" and mentions `B2a`/`B2b` zero times; `main` contains `728bbfd` "FZ-02/B2a: a provider failure no longer completes as success" (PR #67) and `31d7745` "FZ-02/B2b: stalled and hard-deadline generations fail and keep their partial text" (PR #71), and `test_fz02_provider_failure.py` / `test_fz02_stalled_deadline_failure.py` pass. *INFERRED:* B2b's title matches one of D2's two options ("a failure carrying the partial"), so D2 may have been decided in practice while the register still says "none taken". *NOT CHECKED:* that B2a+B2b fully close the audit's exact FZ-02 finding, and FZ-01 (which depends on it). This is exactly the docs-vs-reality gap a manifest exists to reconcile.

**F2 — PR #25 is a stale automated PR, not a competing effort — and a hazard.** Opened Sept 24 by Google's "Jules" agent under the owner's account, untouched since. It changes `CURRENT_STATE.md` by **+17 / −185** (deleting the sync history of the file that calls itself the authoritative record of what is built) and asserts all core kernel blockers are closed, which contradicts the register. *Merging it as-is would be destructive.* Closing it is the owner's call.

**F3 — The chromadb/Dependabot question was already decided.** `DEBT-032` carries the owner's Oct 6 decision (keep `0.5.3`; embedded-only boundary; three server-side advisories; explicit reopen trigger) and #65/#70 (Oct 10) are recorded and pinned (PR #73). The fact I had presented as new — the affected ranges run through `1.5.9`, no patched version exists — is stated in that addendum. My earlier framing of this as "needs your decision" was wrong.

**F4 — FZ-06 and my `DEBT-030` are the same defect.** The audit independently rediscovered Packet C's `C-1` (`CapabilityRequest.trace_id` is a fresh random UUID, disconnected from the real identity chain). Neither row cites the other in the register today — the two records of the same defect are unlinked. The manifest should count it once.

**F5 — FZ-07 supersedes part of `DEBT-031`** (the register says so on that row): the CI gate's real hole was deeper than the allowlist mislabelling I found in Packet F.

## 4. What the manifest needs from the owner (not mine to decide)

1. **Which document defines "Kernel v1.0 freeze-ready"?** Several exist (the Sept 6 freeze audit, K4.2 pre-freeze specs, the pre-freeze debt reconciliation audit, the Oct 1 audit). The manifest must name its criteria.
2. **D1/D2/D3** — decided, pending, or superseded by merged work?
3. **Scope:** the kernel only, or also the control plane (`DEBT-025`, unauthenticated API; `DEBT-033`, admin bypass) — accepted risk, deferred, or blocking?
4. **PR #25** — close it?  **PR #79** (the privacy fix, CI green) — merge?
5. Open items from earlier sync entries whose current status I have **not** re-read: REM-004, `DEBT-020`'s classification.

## 5. Proposed method

1. Pin a SHA; run everything in §1 at it. 2. Build one inventory — `ID | source | claim | how verified (execution / trace / none) | status | evidence | owner decision needed` — across the FZ series, my Packet C–G items (`DEBT-024…036`, `042`), `DEBT-038…041`, CTX-AUTH-001b, REM-004, ADR-KERNEL-06/07, with the concordance FZ-06↔`DEBT-030`, FZ-07↔`DEBT-031`. 3. Use the register's own taxonomy (§0.3/§24.2: PROPOSED/ACCEPTED/IMPLEMENTED/VERIFIED/DEFERRED/…) — "fixed" and "verified" stay distinct. 4. **No `FREEZE READY` unless every blocker is VERIFIED and every deferral is explicitly accepted by the owner**; otherwise a *conditional* verdict that lists the exact conditions. 5. Reconcile the register against the code (F1 shows it can lag by days). 6. Re-pin and re-run before publishing.
