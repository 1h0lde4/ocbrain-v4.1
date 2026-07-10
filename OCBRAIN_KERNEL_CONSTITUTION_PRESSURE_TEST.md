# OCBrain Kernel Constitution — Pressure Test

**Companion to:** `OCBRAIN_KERNEL_CONSTITUTION.md`, `OCBRAIN_KERNEL_CONSTITUTION_RATIONALE.md`
**Role assumed:** Chief Systems Architect / Kernel Engineer / Critical Reviewer
**Status:** Audit findings and recommendations only. Nothing in this document has been applied to the Constitution. A consolidated diff is provided at the end for that decision to be made deliberately.
**Date:** July 8, 2026

The core holds. Five sections below, and the two-new-laws proposal in particular, are real findings, not manufactured ones — including one place (§6) where the right answer is to reject the review's own suggested structure rather than fill it in.

---

## 1. Constitutional Audit — Summary

Eleven laws survive this pass in some form: the original nine plus two genuine gaps closed below (Contract Stability, Failure Containment). Six real internal tensions were found, all resolvable without contradiction once resolved explicitly — none required abandoning a principle. The most consequential finding is that the Constitution, as drafted, would produce unsafe behavior if deployed into a real-time control domain (robotics, industrial automation — both explicitly in this review's own target-domain list) unless the Law of Bounded Autonomy is clarified. That's addressed in §3.

---

## 2. Internal Consistency — Six Real Tensions

**1. Determinism vs. Learning.** The Law of Determinism says the same intent, given the same state, should produce a reproducible path. But if OCBrain is meant to self-improve (skill evolution, learned routing), does "state" include the kernel's own evolved capability definitions? As worded, this is exploitable both ways — trivially "deterministic" if you count enough state, or read strictly enough to forbid learning outright.
*Resolution:* distinguish **execution determinism** (same compiled plan + same inputs → same scheduling decisions) from **capability determinism** (a capability's behavior may evolve via governed learning, but each evolution is itself a versioned, event-logged, replayable transition — see the Law of Contract Stability, §5). Not a contradiction once split; it was previously one law doing two jobs.

**2. Explainability vs. Autonomous Optimization.** As optimization logic grows more sophisticated (learned routing scores, multi-factor scheduling), does the kernel's explanation of "why X" stay human-legible, or does it degrade into "the model said so"?
*Resolution:* the Law of Explainability should be read as committing to **mechanistic** explainability — a faithful trace of the actual decision process — not **interpretive** explainability — an explanation a layperson finds satisfying. These are different bars. The Constitution should be explicit it's committing to the weaker, achievable one; the stronger one may become impossible as sophistication grows, and pretending otherwise would make the Law unkeepable.

**3. User Sovereignty vs. Collective Knowledge.** "Never self-executing" (Invariant 8) handles the blunt violation — an external recommendation can't act on its own. It doesn't handle the subtler one: repeated advisory-only suggestions, sourced from aggregate behavior across many users, can still homogenize a single user's behavior over time through pure repetition, without ever crossing the auto-execution line.
*Resolution:* no clean structural fix exists for this one — it's a genuine, open risk, not a solved tension. Flagged honestly in §10 (Decade Risks) rather than papered over here.

**4. Replaceability vs. Persistent Identity.** If every implementation is replaceable, what makes "the same kernel" the same thing across a total implementation swap?
*Resolution:* identity persists at the level of continuous causal history (the event record) plus adherence to this Constitution — not any technology. Worth stating explicitly in Part I rather than left implicit; exact proposed text in §12.

**5. Bounded Autonomy vs. Real-Time Domains.** The most consequential finding. "No capability may exceed the governance wrapped around it" reads naturally as requiring approval before action. In a robotics or industrial-automation deployment — both named in this review's own scope — a governance gate that blocks a control loop waiting for synchronous approval is not safe, it's a new hazard. Latency from governance becomes a physical-world risk.
*Resolution:* governance can be **pre-authorized as a bounded envelope at design time**, rather than requiring a live checkpoint per action. The envelope is governed; actions inside it aren't each individually re-approved. Exact amendment text in §5.

**6. Contract Stability vs. Evidence over Assumption.** (Found while stress-testing my own new proposal, not the original nine — see §5.) If evidence later shows a contract was badly designed, does "don't break existing dependents" trap the system into perpetuating a known-bad contract forever?
*Resolution:* the same pattern the Linux kernel uses for exactly this problem — deprecate alongside the replacement, with an explicit migration path and sunset horizon, never an instant cut. Built directly into the new law's Implications in §5, not left as an unresolved tension.

Tensions 5 and 6 both resolve via envelope/deprecation-window mechanisms rather than by weakening either law — a good sign that the eleven laws are compatible under precise reading, not just compatible by accident of vague wording.

---

## 3. Missing Principles

Not everything on the suggested list is actually missing. Honest accounting:

| Suggested | Verdict | Disposition |
|---|---|---|
| Fault Isolation | Genuinely missing | → new Law of Failure Containment (§5) |
| Version / Backward Compatibility | Genuinely missing | → new Law of Contract Stability (§5) |
| Dependency Management | Genuinely missing | → folded into Contract Stability (§5) |
| Time (as a source of non-determinism) | Genuinely missing | → amendment to Law of Determinism (§5) |
| Trust (as distinct from Provenance) | Genuinely missing | → new Resource field, Invariant 4 (§5) |
| Identity (persistence across replacement) | Needed clarification, not a new law | → Part I addition (§12) |
| Reliability | Emergent, not independent | Produced by Failure Containment + Explicit State jointly — see §6 |
| Observability | Substantially covered | Law of Explicit State already produces the traces observability needs |
| Resource Ownership | Mostly covered | Invariant 4 (provenance) + Law of User Sovereignty; closed further by adding Trust |
| State Consistency | Already covered | Law of Single Source of Truth |
| Recovery | Already covered | Folds into Failure Containment |
| Lifecycle | Already explicit | Invariant 4, unchanged |

Five genuine gaps, seven already handled. Treating all twelve as equally missing would have been the less rigorous answer.

---

## 4. Missing Laws — Full Proposed Text

Two new laws, in the same Purpose / Reasoning / Implications / Example format as the original nine, plus two amendments to existing laws.

**Law of Contract Stability**
*Purpose:* Once a Capability or Resource contract is published, changes to it must not silently break what already depends on it.
*Reasoning:* A kernel whose promises can change without notice cannot be built on with confidence — every dependent would have to re-verify its assumptions constantly, defeating the point of having stable abstractions at all.
*Implications:* Contract changes are additive and versioned by default. Where a contract genuinely must break, the old version is deprecated alongside the new one, with an explicit migration path and sunset horizon — never removed instantly. This does not freeze contracts forever; it requires that evidence of a bad contract (Law of Evidence over Assumption) be resolved through deprecation, not silent breakage.
*Example:* A capability's output schema gains a new optional field without breaking existing consumers; removing a field goes through a deprecation window, never an immediate cut.

**Law of Failure Containment**
*Purpose:* A failing capability's failure must not cascade beyond a describable, bounded blast radius, and the kernel must continue operating in a reduced, honestly-described form around it.
*Reasoning:* A system that assumes nothing ever fails isn't resilient, it's untested. A kernel that can't isolate and describe a failure can only lie about being healthy, or stop entirely — neither is acceptable for anything mission-critical.
*Implications:* Every capability's failure modes are declared as part of its contract, not discovered in production. Containment decisions — suspending a misbehaving capability, falling back to a degraded mode — may act within a pre-governed envelope without a synchronous approval step, because the envelope itself was already governed at design time (Law of Bounded Autonomy, amended below).
*Example:* An adapter starts returning malformed data; the kernel suspends it and reports degraded capability, rather than propagating the malformed data or halting the whole system.

**Amendment to Law of Bounded Autonomy** *(new sentence, appended to Implications):*
"In domains where synchronous approval is itself unsafe — real-time control, robotics, industrial automation — governance is expressed as a pre-authorized envelope defined at design time. The bounds are governed; that does not mandate a live checkpoint for every action inside them."

**Amendment to Law of Determinism** *(new sentence, appended to Implications):*
"Genuinely non-replayable inputs — wall-clock time, external randomness, hardware sensor readings — are captured as events at the moment they're consumed, not re-derived during replay. Replay reproduces the decision made given that captured input, not the input itself."

**Fix to Invariant 4** *(replaces existing text)*:
Current: *"Every resource the kernel manages carries identity, lifecycle, and provenance."*
Proposed: *"Every resource the kernel manages carries identity, lifecycle, version, dependencies, trust, and provenance."*
This is a real correction, not an enhancement: the original Directive specified seven Resource fields; drafting compressed them to three for brevity, and that compression silently dropped the exact fields the Version-Compatibility and Dependency-Management gaps above needed. Worth naming plainly as an error introduced in the first draft, not a stylistic choice.

---

## 5. Kernel Properties — Recommendation Against the Requested Structure

The request asks for a full fourth taxonomic layer — Determinism, Explainability, Replaceability, Extensibility, Composability, Observability, Resilience, Security, and others, each with Definition / Purpose / Measurement / Trade-offs / Interactions.

Recommending against this, specifically. Most of the listed items are either already-named Laws (Determinism, Explainability, Replaceability, User Sovereignty), or emergent consequences of the Laws rather than independent things (Extensibility, Composability, Portability, Maintainability are all downstream of Replaceability + Separation of Concerns; nothing new is said by giving them their own five-field write-up). Building this out in full would duplicate ~80% of Part III in different field names — precisely the redundancy-drift risk already flagged in the Rationale document's self-critique.

What's genuinely missing from the Laws — measurement criteria and honest trade-offs — is real and worth keeping. Lighter version, as an annotation table rather than a parallel structure:

| Property | Produced by | How to measure it | Real trade-off |
|---|---|---|---|
| Determinism | Law of Determinism, Law of Explicit State | Do two runs of the same compiled plan against the same state diff to identical scheduling decisions? | Costs latency/flexibility — needs the real-time envelope clarification (§3, #5) |
| Explainability | Law of Explainability, Law of Explicit State | Can the kernel produce a plain account of what it understood and why, without operator reconstruction from raw logs? | Trades against optimization sophistication (§3, #2) |
| Replaceability | Law of Replaceability, Part VII (Adapters) | Can a capability's implementation be swapped with zero change to dependents' contracts? | Costs some abstraction overhead; doesn't apply to the Constitution's own Laws (Part VIII excludes that by design) |
| Auditability | Law of Explicit State, Law of Single Source of Truth | Can any past decision be traced to the state and event(s) that produced it? | Costs storage/retention; retention policy itself needs a bounded envelope |
| Security | Law of Bounded Autonomy, Law of Separation of Concerns | Can a compromised capability's blast radius be described and bounded in advance? | Same latency tension as Determinism above |
| Resilience | Law of Failure Containment *(new)* | Does the kernel continue operating, in a described reduced form, when a depended-on capability fails? | Was a genuine gap before §5's new law |
| Portability / Extensibility / Composability / Scalability / Maintainability | Emergent — Replaceability + Separation of Concerns jointly | No independent test; these are consequences, not independently measurable | Treating them as independent is exactly the redundancy this table avoids |

---

## 6. Architectural Drift Protection

Part VI (Non-Goals) states what OCBrain isn't. That's a declaration, not a mechanism — nothing currently checks the declaration against reality over time.

**Fix, at low cost — extend, don't add:** the Admission Test's existing retrospective-reapplication clause (Part V) already re-checks kernel contents against Gate 1 on a regular cadence. Extend that same clause to also check accumulated direction against Part VI's Non-Goals, not just against the Invariants.

**A concrete, checkable heuristic**, not just a restated warning: *if what was just built could be accurately described using only the vocabulary of a Non-Goal — "it's basically a workflow engine now" — and not the vocabulary of Part I/II — Kernel, Resource, Capability, Adapter — that's the drift signal.* This gives future contributors something to actually test against rather than a vague instinct to remember.

---

## 7. Canonical Glossary

The riskiest cluster for ambiguity was Observation/Evidence/Memory/Knowledge/Context and Intent/Goal/Task — both resolved below with an explicit ordering, not just five separate definitions.

**Intent → Goal → Task** (a pipeline, not synonyms): **Intent** is the raw, possibly ambiguous expression of what a user wants, prior to verification. **Goal** is the verified, disambiguated target state Intent compiles down to once verification succeeds. **Task** is a single schedulable unit of work that's part of achieving a Goal. One direct consequence: the step currently named "Goal Verification" is a category error — you verify Intent to *produce* a Goal, you don't verify a Goal that doesn't exist yet. See §8.

**Observation → Evidence → Memory → Knowledge → Context** (increasing processing, in order): **Observation** — a raw, timestamped record of something perceived or that occurred. **Evidence** — Observation(s) evaluated as relevant and reliable enough to justify a claim (this is what the Law of Evidence over Assumption actually operates on). **Memory** — the kernel's persistent store of Observations, Evidence, and derived facts over time. **Knowledge** — the subset of Memory that has crossed a validation threshold sufficient to be treated as reliable background fact. **Context** — a transient, task-scoped view assembled from Memory and Knowledge for one specific execution; not itself a persistent store.

**Full glossary:**

| Term | Canonical definition |
|---|---|
| Kernel | The smallest set of responsibilities that must be centralized and governed for everything built on OCBrain to remain coherent, safe, and explainable. Coordinates; does not perform. |
| Resource | A named, identified thing the kernel manages, carrying identity, lifecycle, version, dependencies, trust, and provenance. |
| Capability | An abstract, schedulable unit of work, defined by its contract, independent of what satisfies it. |
| Adapter | A concrete implementation satisfying a Capability's contract by wrapping exactly one external system. |
| Plugin | A packaged bundle of Capabilities, Adapters, and Workflows, installed as one unit. |
| Intent | The raw, unverified expression of what a user wants. |
| Goal | The verified target state an Intent compiles to. |
| Task | A single schedulable unit of work toward a Goal. |
| Workflow | A reusable, versioned template composing Capabilities to satisfy a class of Goals. |
| Execution Plan | The specific, compiled, inspectable artifact produced for one verified Goal at one moment — an instantiated Workflow with resolved Adapters and bound Resources. |
| Observation | A raw, timestamped record of something perceived or that occurred. |
| Evidence | Observation(s) evaluated as relevant and reliable enough to justify a claim. |
| Memory | The kernel's persistent store of Observations, Evidence, and derived facts. |
| Knowledge | The subset of Memory validated past a confidence threshold. |
| Context | A transient, task-scoped view assembled from Memory/Knowledge for one execution. |
| Policy | A specific, declared rule constraining what a capability or resource may do. |
| Governance | The system of actors, processes, and enforcement points keeping Capability bounded by Policy. |
| State | The current condition of a Resource at a given moment. |
| Event | An immutable record of a specific state transition. |
| Identity | The persistent reference letting the same Resource be referred to across time, independent of implementation. |
| Lifecycle | The sequence of stages a Resource passes through from creation to retirement. |
| Scheduler | The function deciding when and in what order schedulable units execute, within governed bounds. |
| Registry | The authoritative index of which Capabilities, Adapters, and Resources exist and are available. |
| Trust | A Resource's evaluated reliability — distinct from Provenance, which records origin, not reliability. |
| Provenance | The recorded origin and transformation history of a Resource. |

---

## 8. Naming Review

**Renames recommended:**
- **Intent Interpreter → Intent Compiler.** Already flagged in the companion rationale; reconfirmed here. The pipeline compiles to a fixed representation before execution — it doesn't interpret step by step.
- **Goal Verification → Intent Verification.** New finding, emerging directly from the glossary work in §7: you verify the Intent in order to produce a Goal; you can't verify a Goal that doesn't exist yet. The current name is a category error, not just a stylistic one.
- **Collective Intelligence → Cross-Instance Advisory Layer.** Upgraded from "flagged as risky" (companion rationale) to a concrete proposal. The word "Advisory" belongs in the name itself — it's much harder to accidentally over-trust something explicitly named for the constraint that protects against over-trusting it.

**Reviewed and kept, with reasons** (not skipped — deliberately confirmed):
- **Kernel** — correct OS-lineage term, evokes the right mental model.
- **Capability** — industry-convergent term (confirmed independently across the research corpus); no better alternative found.
- **Resource, Adapter, Plugin, Workflow, Context** — each is fine once disambiguated from its neighbors (§7); the ambiguity was in the *boundaries*, not the *names*.
- **Memory, Scheduler, Registry** — standard, correct terminology; no ambiguity found.

Renaming without a demonstrated ambiguity is itself unjustified churn — the Law of Evidence over Assumption applies to naming, not only to architecture.

---

## 9. Constitutional Hierarchy — Six Layers

The prior rationale document proposed three layers (Constitution / Architecture / Roadmap). This review's request separates six. Worth the finer grain, but not worth six separate document types existing today:

| Layer | Distinct job | Exists today? |
|---|---|---|
| Kernel Constitution | Timeless principle | Yes — this document set |
| Architecture Specification | Current best answer to how principles are realized | Yes — `PROJECT_INSTRUCTIONS.md`, `OCBRAIN_FUTURE_ARCHITECTURE.md` |
| Architecture Decision Records | The audit trail of *why* the Specification changed, and when | Partially — `ARCHITECTURE_DECISIONS.md` is planned (PI §18.5), not yet created |
| Implementation Specifications | Precise, detailed interface contracts one level more concrete than Architecture Spec | No, and doesn't need its own document type yet — currently belongs as detail sections within existing architecture docs or code-level interface definitions |
| Roadmap | Sequences implementation work over time | Partially — `IMPLEMENTATION_ROADMAP.md` / `CURRENT_STATE.md` planned (PI §18.2.1), not yet created |
| Developer Documentation | Onboarding/reference for an external audience, distinct from the architecture team | No, and appropriately absent — this project doesn't yet have the contributor base that would justify it |

Applying the Admission Test's own logic reflexively: creating all six as literal, separate document types right now would itself fail Gate 1 (Necessity) for the last two — a document type without a distinct near-term audience isn't earning its existence yet. Recommend keeping the conceptual six-layer distinction for reasoning about *where new content belongs*, without forcing two premature documents into existence today.

---

## 10. North Star — Stress-Tested

Original: **"The kernel coordinates; it does not own."**

Genuinely re-examined against the two new laws, not just re-asserted. Neither Contract Stability nor Failure Containment maps obviously onto "own" — worth checking whether a broader phrase would serve better now that the law set has grown from nine to eleven.

Seriously considered alternative: **"The kernel keeps its promises."** This one is arguably more comprehensive — nearly every law can be read as a specific kind of promise (a promise about state visibility, about not exceeding governance, about contracts not silently breaking, about degrading honestly instead of lying about being healthy). But it's vaguer as a *decision procedure*: "does this increase what the kernel owns" is a crisp yes/no test; "is this keeping a promise" requires more interpretation per use.

**Verdict: keep the original.** Its job is orientation, not comprehensiveness — a North Star that tried to cover all eleven laws equally would stop being a fast heuristic and become a summary. And on inspection, Contract Stability isn't actually orthogonal to it: *because* the kernel doesn't own an implementation, it has no right to unilaterally change the terms other things depend on either. Contract Stability is close to a corollary of non-ownership, not a competing concern. The North Star survives contact with the new laws; it doesn't need to be rewritten to accommodate them.

---

## 11. Future-Proofing — Five Scenarios

| Scenario | Survives? | Why |
|---|---|---|
| LLMs disappear | Yes | No Law or Invariant references models by name; every reference is to "an inference call," "a capability," generically |
| Reasoning models become deterministic | Yes, and it gets easier | The Law of Determinism's non-determinism hedge becomes unnecessary rather than wrong — a sign it was worded to accommodate uncertainty, not assume it |
| New programming paradigms emerge | Yes | The Constitution deliberately avoids implementation-flavored language (no "async," "class," "function") — a discipline exercised at drafting time, confirmed here under stress |
| Entirely new computing architectures appear | Yes | Part VII's Substrate layer exists precisely to absorb this — a new architecture is just a new Adapter target |
| Human-computer interaction changes dramatically | Yes | Part VI already explicitly denies "conversation" as a kernel primitive — defensively worded against exactly this before this review asked for it |

**One residual risk found, not zero:** Part V Gate 2's placement options (Adapter / Capability / Workflow / Plugin / External Service) implicitly assume a software-service-shaped world. A sufficiently novel future paradigm might not fit any of the five cleanly.
*Fix, exact text, appended to Gate 2:* "This list names the current shapes such placements take, not a closed set. If a genuinely new category emerges that fits the same pattern — something outside the kernel performing or holding the thing — it belongs in that new category, not forced into an existing one or pulled inside the kernel by default."

Four of five scenarios survive cleanly because the discipline was already exercised while drafting; the fifth needed one concrete textual fix, now specified.

---

## 12. Decade Risks

1. **Kernel scope creep**, unchecked by anything except good intentions over a long enough timeline — already partially addressed by the Admission Test's retrospective clause, but worth naming as a standing risk rather than a solved one.
2. **Draft status never actually pressure-tested against real implementation** before being treated as settled — the same sequencing risk flagged in the companion rationale, restated here because it's the precondition for everything else in this document meaning anything.
3. **The amendment process gets bypassed under real deadline pressure.** This is how most real constitutions actually fail — not through bad principles, but through "just this once" exceptions that become precedent. No structural fix exists for this beyond the process already defined in Part VIII; naming it is the honest thing to do, not solving it with more process.
4. **Sovereignty erosion through repeated advisory nudging** (§2, tension 3) — no clean fix found, flagged as open.
5. **Succession and continuity of amendment authority.** Part VIII says amendments require "explicit approval" but doesn't say by whom beyond the obviously-implied current owner. A ten-year horizon is long enough that this stops being obvious. This isn't something I can resolve — it depends on facts about the project's future governance only its owner can determine — but a constitution silent on succession is incomplete by the standards real constitutions are held to, and it's worth deciding deliberately rather than by default.

---

## 13. Strengthening Without Increasing Complexity — Honest Accounting

Not every recommendation here is complexity-neutral, and claiming otherwise would be dishonest. Net accounting:

**Adds real content:** two new Laws (9 → 11), one Invariant expanded from three fields to six, two law amendments. Each was independently justified by a specific, named gap — not added for symmetry or thoroughness theater.

**Removes or prevents complexity:** rejecting the full Kernel Properties taxonomy (§5) in favor of a lighter annotation table; rejecting two premature document types in the hierarchy (§9); the Gate 2 catch-all (§11) prevents future enumeration bloat by design rather than requiring the list to keep growing.

Fair summary: the Constitution gets modestly longer and meaningfully more precise. That's a defensible trade, not a free one, and it should be described that way rather than claimed as strengthening-without-cost.

---

## 14. Final Assessment

**Would this Constitution still make sense ten years from now?**

Qualified yes — and the qualification matters more than the yes.

The core survives the future-proofing scenarios cleanly (§11), largely because the discipline of avoiding implementation-flavored language was exercised at drafting time rather than retrofitted now. The eleven laws (nine original, two added here) resolve internally under precise reading, with two recurring resolution patterns — pre-authorized envelopes for real-time domains, deprecation windows for contract evolution — doing real, load-bearing work rather than papering over conflicts.

The "yes" is conditional on three things actually happening, not just being written down: the Draft-status pressure-testing continuing past this single pass (risk #2); the amendment process holding under real deadline pressure rather than being quietly bypassed (risk #3); and the succession question (risk #5) getting a deliberate answer instead of an accidental one. A constitution that's correct on paper and unenforced in practice doesn't survive ten years — it survives until the first moment enforcing it is inconvenient.

One open problem was found with no clean resolution: sovereignty erosion through repeated, technically-compliant advisory nudging (§2, tension 3; §12, risk 4). That one doesn't get a manufactured fix here. Flagging it honestly is more useful than resolving it unconvincingly.

---

## 15. Consolidated Diff — If Approved

For applying in one pass, once reviewed:

1. Invariant 4 — replace three-field version with the six-field version (§4).
2. Add Law 10 — Contract Stability (§4, full text given).
3. Add Law 11 — Failure Containment (§4, full text given).
4. Amend Law of Bounded Autonomy — append the real-time envelope clause (§4).
5. Amend Law of Determinism — append the non-replayable-input clause (§4).
6. Amend Part V, Gate 2 — append the catch-all clause (§11).
7. Extend Part V's retrospective clause to explicitly cover Part VI Non-Goals, not just the Invariants (§6).
8. Add to Part I — the identity-as-continuity clarification (§2, tension 4): *"What persists when every implementation has been replaced is not any particular technology — it is the continuous causal history recorded in the kernel's own event record, and adherence to this Constitution. Identity is continuity, not substrate."*
9. Architecture-spec-level renames (not Constitution text, but should propagate wherever these terms appear): Intent Interpreter → Intent Compiler; Goal Verification → Intent Verification; Collective Intelligence → Cross-Instance Advisory Layer.
10. Adopt the §7 glossary as the canonical terminology reference, as a companion document, not inline in the Constitution — consistent with Part VIII's existing separation principle.
11. Explicitly decide the succession question from risk #5 — this one needs a decision, not a text edit.

North Star, Non-Goals, Part VII layers, and seven of the original nine Laws survive this review unchanged.

---

*Pressure test complete. No implementation touched, no new features proposed, no redesign attempted — per instruction.*
