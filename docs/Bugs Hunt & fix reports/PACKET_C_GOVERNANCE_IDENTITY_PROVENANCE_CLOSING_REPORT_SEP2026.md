# Packet C — Governance / Identity / Provenance Trace: Closing Report

**Date:** September 16, 2026
**Scope:** `docs/Bugs Hunt & fix reports/PACKET_C_EXECUTION_PROMPT_SEP2026.md`
**Full evidence:** `docs/Bugs Hunt & fix reports/PACKET_C_GOVERNANCE_IDENTITY_PROVENANCE_WORKING_NOTES_SEP2026.md`
**Branch:** `audit/packet-c-governance-identity-provenance-sep2026`, off `main` at `977ebcc`. No push, no merge, `main` untouched throughout.

---

## A. Process note — read before the findings

Two of this packet's seven findings (C-5, C-7) were arrived at by tracing fresh from source, per the packet's own mandate to verify the live execution path rather than trust documentation. That tracing was correct and not wasted — Packet C's method is explicitly "verify from source, don't assume a prior claim holds." What was not correct: presenting those two as new findings without first checking whether `KNOWN_ISSUES.md` already tracked them. It did, as `DEBT-007` and `DEBT-025` respectively, both pre-existing this session.

This is recorded here rather than silently fixed, for the same reason this whole audit records its own corrections in place: it's a genuine process gap — this project's own `PROJECT_INSTRUCTIONS.md` §18.4.6 ("Audit Reuse") specifically calls for reviewing `KNOWN_ISSUES.md` before launching a new investigative thread, and that step was skipped for C-5 and C-7. Both entries have been reconciled — updated in place with dated addenda, not duplicated — and are cross-referenced below with their corrected attribution. **Packets D through G should check `KNOWN_ISSUES.md` for relevant existing entries before source-tracing a subsystem, not after**, as the concrete fix going forward.

The upside worth naming: independent convergence is itself evidence. C-5 and C-7 being rediscovered by an unrelated trace, from a different starting point, arriving at the same conclusion as the original finding, is corroborating — and both traces added genuine refinements the originals didn't have (detailed below). That is a different, and arguably more valuable, outcome than either "novel finding" or "wasted duplicate work."

---

## B. Findings summary

| Finding | Disposition | Relationship to prior tracking |
|---|---|---|
| **C-1 — `CapabilityRequest`/`Result` identity gap** | UNPROVEN as a control | Genuinely new to this packet. No `KNOWN_ISSUES.md` entry existed; now added as `DEBT-027`. |
| **C-2 — Governance granularity gap** | PARTIAL | Genuinely new to this packet. |
| **C-3 — Retry/resume authorization** | LIVE-ENFORCED | Genuinely new to this packet (negative result). |
| **C-3a — Hardcoded `recursion_depth`** | DOCUMENT-ONLY / NOT BYPASSABLE | Genuinely new to this packet (negative result, investigated per Moncif's explicit constraint not to escalate a dormant governor into a defect without evidence of exploitability). |
| **C-4 — `failed_worker_result` reachability** | TEST-ONLY BY DESIGN | Corrects Session 1 of this same engagement's "dual uncoordinated recovery authorities" framing — that framing is superseded. |
| **C-5 — BudgetGovernor caller-attestation** | PARTIAL | **= `DEBT-007`, pre-existing.** Independently re-confirmed and refined; see `KNOWN_ISSUES.md`'s updated row. |
| **C-6 — Resume/checkpoint provenance** | LIVE-ENFORCED | Genuinely new to this packet (negative result, direct answer to the packet's sharpest question). |
| **C-7 — Control-plane authority (`interface/api.py`)** | PARTIAL | **= `DEBT-025`, pre-existing** (itself originally from this engagement's Session 1). Independently re-confirmed and refined, with one self-correction (browser-CSRF vector overstated on first pass, then checked and revised); see `KNOWN_ISSUES.md`'s updated row. |

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

**C-1 remains unresolved but is now reconciled into `KNOWN_ISSUES.md` as `DEBT-027`**, added during this closing pass rather than left as a flagged-but-untracked item in this report alone.

---

## F. What Packet C corrects in prior audit work

Session 1 of this engagement's freeze audit recorded SupervisorWorker's `_attempt_retry()` as an untracked gap with "dual uncoordinated recovery authorities." C-4 found this reachability fact still true but the characterization wrong: the code documents both retry paths as deliberately independent, with a defined result when neither is supplied, and the unreachability of the test-only path is itself asserted under test. Session 1's framing is superseded and should not enter the freeze manifest as originally written; the residual is a one-line `KNOWN_ISSUES.md` note recording the deferral as intentional, not a code change.

---

## G. Status

Packet C is closed with this report. Two residuals (DEBT-007, DEBT-025) carried forward with named revisit triggers, consistent with every other open item in this register. One finding (C-1) still needs register reconciliation. The provenance and authorization boundary of the governed cognitive execution path was tested by falsification, not merely reviewed, and held.
