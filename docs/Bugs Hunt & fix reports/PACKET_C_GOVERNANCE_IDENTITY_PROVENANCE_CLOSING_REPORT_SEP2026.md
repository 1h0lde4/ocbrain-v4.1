# Packet C — Governance / Identity / Provenance Trace: Closing Report

**Date:** September 16, 2026
**Scope:** `docs/Bugs Hunt & fix reports/PACKET_C_EXECUTION_PROMPT_SEP2026.md`
**Full evidence:** `docs/Bugs Hunt & fix reports/PACKET_C_GOVERNANCE_IDENTITY_PROVENANCE_WORKING_NOTES_SEP2026.md`
**Branch:** `audit/packet-c-governance-identity-provenance-sep2026`, off `main` at `977ebcc`. No push, no merge, `main` untouched throughout.

---

## A. Process note — read before the findings

Four of this packet's seven findings — not two, as an earlier version of this report and its accompanying commit claimed — were arrived at by tracing fresh from source and then presented as new before checking whether `KNOWN_ISSUES.md` already tracked them. It did, in every case: C-5 as `DEBT-007`, C-7 as `DEBT-025`, C-4 as `DEBT-024`, and C-6 as an already-resolved `DEBT-003`'s own documented behavior. The source tracing itself was correct and not wasted — Packet C's method is explicitly "verify the live path, don't trust documentation" — but presenting the results as novel without the register check first was not.

This is worth being precise about rather than smoothing over: the first attempt at this correction, itself, only caught two of the four (C-5, C-7), declared the reconciliation complete, and was wrong to. What caught the other two (C-4, C-6) was not further incidental grep hits — it was deliberately, systematically checking every remaining finding's subject matter against the register on the assumption that if the pattern held twice, it likely held more than twice. That is the actual, operative lesson for Packets D through G: **incidental discovery during unrelated tracing is not a substitute for a deliberate register check, performed as a first step, before a new attention area is investigated — not after, and not stopped at the first correction found.**

All four have been reconciled in `KNOWN_ISSUES.md` — updated in place with dated addenda, not duplicated — cross-referenced below with corrected attribution. The upside worth naming honestly alongside the correction: independent convergence is itself evidence. Four findings, each arrived at from a different trace than the one that originally found them, reaching the same conclusion, is corroborating — and each pass added genuine refinements the original didn't have (detailed in each register entry). That is a different, and arguably more valuable, outcome than either "novel finding" or "wasted duplicate work" — but it is not the same thing as new coverage, and the freeze manifest should credit it accurately as re-confirmation, not discovery.

---

## B. Findings summary

| Finding | Disposition | Relationship to prior tracking |
|---|---|---|
| **C-1 — `CapabilityRequest`/`Result` identity gap** | UNPROVEN as a control | Genuinely new — checked deliberately against the register before filing, not just by absence of accidental discovery. No prior entry existed; now added as `DEBT-030`, cross-referenced to the related but distinct `DEBT-015` sub-item (1). |
| **C-2 — Governance granularity gap** | PARTIAL | Genuinely new; checked against the register, no match. |
| **C-3 — Retry/resume authorization** | LIVE-ENFORCED | Genuinely new (negative result); checked against the register, no match. |
| **C-3a — Hardcoded `recursion_depth`** | DOCUMENT-ONLY / NOT BYPASSABLE | Genuinely new (negative result, investigated per Moncif's explicit constraint not to escalate a dormant governor into a defect without evidence of exploitability); checked against the register, no match. |
| **C-4 — `failed_worker_result` reachability** | TEST-ONLY BY DESIGN | **= `DEBT-024`, pre-existing.** Not a fresh discovery and not simply a correction to this engagement's own Session 1 — `DEBT-024` already existed, already independently re-confirmed once (Sept 12). This pass resolves its previously-open "wire vs. deprecate" disposition with evidence; see `KNOWN_ISSUES.md`'s updated row. |
| **C-5 — BudgetGovernor caller-attestation** | PARTIAL | **= `DEBT-007`, pre-existing.** Independently re-confirmed and refined; see `KNOWN_ISSUES.md`'s updated row. |
| **C-6 — Resume/checkpoint provenance** | LIVE-ENFORCED | **= behavior already documented in `DEBT-003`'s Sept 5, 2026 resolved entry.** Not a fresh discovery — a valid re-verification, four sessions later, of a resolution that still holds, now directly answering Packet C's specific authority-substitute framing and adding two new caveats; recorded as an addendum on that resolved entry, not standalone. |
| **C-7 — Control-plane authority (`interface/api.py`)** | PARTIAL | **= `DEBT-025`, pre-existing** (itself originally from this engagement's Session 1). Independently re-confirmed and refined, with one self-correction (browser-CSRF vector overstated on first pass, then checked and revised); see `KNOWN_ISSUES.md`'s updated row. |

**Corrected count: three of seven findings (C-1, C-2, C-3/C-3a) are genuinely new. Four (C-4, C-5, C-6, C-7) independently re-confirm pre-existing tracked items.**

---

## C. The key distinction for the freeze manifest

> **The cognitive execution authorization boundary holds. The control-plane boundary is separately weaker.**

This is the load-bearing distinction of the whole packet, and it is what prevents C-7/DEBT-025 from being incorrectly recorded as an execution-governance bypass. Nothing traced in this packet lets a request, plan, cached result, or persisted event that entered through the governed cognitive path reach `interface/api.py`'s unauthenticated endpoints, and nothing traced lets those endpoints reach `AdapterRuntime`/capability execution. They are two separate authority planes, not one plane with a hole in it. The severity of the control-plane plane's weakness is deployment-topology-dependent — loopback-only single-user operation is a materially different threat model from exposed, proxied, or multi-user operation — which is why its disposition is PARTIAL with a named revisit trigger rather than an open defect.

---

## D. Closing invariant

> **No persisted event, receipt, compiled plan, cached result, reconstructed context, caller-supplied metadata, direct worker internals, or external interface path was found that can cause a privileged adapter invocation without the canonical governed execution path.**

This holds, established by attempting to falsify it across six independent attacks (full detail and evidence in the working notes):

| Attack | Result |
|---|---|
| Direct `worker._run()` call bypassing governed `execute()` | Fails — sole production call is inside `execute()` itself |
| `ExecutionRuntime.invoke()` skipping governance | Fails — routes to `worker.execute()` |
| HTTP/API surface reaching an adapter directly | Fails — zero occurrences in `interface/` |
| Persisted event/receipt used to gate a decision | Fails — zero code branches on event content to authorize |
| Reconstructed context / cached result as authorization | Fails — resume loads internally by `instance_id`; executing nodes re-enter governed `execute()` |
| Both live adapter call sites | Both inside workers, both downstream of a governed `execute()` |

One precise qualification, carried from C-5/DEBT-007: **caller-supplied metadata can influence the content of a governance decision — it cannot cause the decision not to happen.** It can weaken what the decision sees (as DEBT-007 documents); it cannot skip the decision (as C-3/C-6 establish). C-2's granularity gap sits in the same place: the decision always occurs, but at times is coarser than the action it authorizes.

**C-1 sits outside this invariant's scope, deliberately.** The `CapabilityRequest`/`Result` identity gap is a provenance/correlation absence, not an authorization control — there is nothing there to be bypassed, which is exactly why it is classified UNPROVEN rather than BYPASSABLE. It remains open as a finding; it does not weaken the invariant above, which is specifically about authorization, not correlation.

---

## E. Residuals carried to the freeze manifest

Two substantive residuals, both PARTIAL, both with concrete revisit triggers — full text now lives in `KNOWN_ISSUES.md`:

**DEBT-007 (C-5).** Governance-layer budget enforcement (`BudgetGovernor`) is caller-attested, not independently measured, and fails open on absence. This is separate from, and must not be conflated with, the genuinely measured `ExecutionBudget`/`GraphExecutionWatchdog` mechanism, which is real. Revisit trigger: any future path where governance budget metadata is expected to represent measured consumption rather than caller attestation, or where a cumulative cross-retry/resume limit becomes a security invariant rather than a reliability one.

**DEBT-025 (C-7).** `interface/api.py`'s privileged control-plane endpoints have no authentication and no governance evaluation, mitigated today by loopback binding and (for the browser-specific vector) CSRF header middleware — not by a governance boundary. Revisit trigger, now explicit where the row previously just said disposition had not been made: any off-loopback binding, proxy-mediated exposure, multi-user deployment, or another actor capable of reaching these endpoints.

**C-1 remains unresolved but is now reconciled into `KNOWN_ISSUES.md` as `DEBT-030`**, added during this closing pass rather than left as a flagged-but-untracked item in this report alone.

---

## F. What Packet C corrects in prior audit work

Session 1 of this engagement's freeze audit recorded SupervisorWorker's `_attempt_retry()` as an untracked gap with "dual uncoordinated recovery authorities." That "untracked" characterization was itself already inaccurate by the time Packet C ran: `DEBT-024` existed, had been independently re-confirmed once already (Sept 12, 2026), and Session 1's framing simply wasn't checked against it. C-4 (itself a third independent re-confirmation of the same reachability fact, this time via Packet C's trace) found the characterization wrong regardless of tracking status: the code documents both retry paths as deliberately independent, with a defined result when neither is supplied, and the unreachability of the test-only path is itself asserted under test. Session 1's "uncoordinated" framing is superseded and should not enter the freeze manifest as originally written. `DEBT-024`'s own previously-open disposition ("wire a real caller, or formally deprecate the unreachable path") is now resolved with evidence: neither — it's a documented, contractually-specified, deliberately-deferred capability, requiring no code change.

---

## G. Status

Packet C is closed with this report. Of its seven findings, three are new coverage (`DEBT-030`, and C-2/C-3/C-3a which remain findings within this report without register entries of their own, being negative/clean results rather than open debt) and four are independent re-confirmations of pre-existing tracked items — `DEBT-007`, `DEBT-024`, `DEBT-025`, and `DEBT-003`'s resolved entry — each updated in place with genuine refinements, none duplicated. Two substantive residuals carry forward to the freeze manifest with named revisit triggers: `DEBT-007` and `DEBT-025`. `DEBT-024` and `DEBT-003` are fully resolved, not residuals. The provenance and authorization boundary of the governed cognitive execution path was tested by falsification, not merely reviewed, and held.
