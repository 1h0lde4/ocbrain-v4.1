# OCBrain K4.1-L — Cognitive Learning Architecture (Final)

**Date:** July 19, 2026
**Status:** Architecture Only. Zero code, zero implementation, zero repository modifications, zero interface freezing, zero placeholder APIs.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md`, `PROJECT_INSTRUCTIONS.md`, K4, and `OCBRAIN_K4_1_FINAL_CONSOLIDATED_ARCHITECTURE.md` ("K4.1"). A peer to K4.1, not a subordinate part of it. Neither redefines the other; nothing in K4.1's Runtime Architecture, Governance, `UnifiedMemory`, Delegation, or `CognitiveService` design is touched here.
**Supersedes:** `OCBRAIN_K4_1_L_COGNITIVE_LEARNING_ARCHITECTURE.md`, in full. That document should be archived once this is accepted — the same reasoning already applied to the four documents K4.1 itself superseded applies again here, and repeating the omission a second time would be a worse failure than the first.

---

## Part 0 — What Changed, and Why

Five refinements, each checked against the required test: why the prior form becomes insufficient, why the refinement preserves every existing principle, why it increases decade-scale stability. Everything not listed here — the pipeline's overall shape, the Experience Model, Learning Memory, Learning Sources, Ontology Evolution, and Governance Integration — was re-examined and found sound; it is restated below, not re-argued.

**1. "Instinct" is replaced by "Learning Candidate," throughout.**
*Insufficient because:* "instinct" connotes something pre-rational and unexamined, which is a real mismatch with what was actually specified — a provenance-tracked, confidence-scored, evidence-grounded claim. The mismatch isn't cosmetic: a reader taking the word at face value could reasonably under-build the provenance and confidence machinery the architecture actually requires.
*Preserves principles because:* "Learning Candidate" is defined in terms of the Truth Framework's own existing `candidate` status rather than coining a parallel vocabulary — it strengthens Single Source of Truth by removing a redundant term, not by adding one.
*More stable because:* a term defined against an already-frozen concept can't drift independently from it the way an unrelated coinage could over a decade.

**2. The learning surface is generalized: any cognitive component may emit a `LearningCandidate`, present or not yet imagined, through one explicit contract — not six named, implicitly closed categories.**
*Insufficient because:* presenting Intent/Goal/Planner/Reflection/Evaluation/Supervisor as the learning surface, even with one shared pipeline underneath, reads as a closed taxonomy — precisely the mistake K4.1 already found and fixed once, when "Cognitive Runtime Extension" (six named categories) became "Cognitive Service" (one generic, open contract). Leaving the identical mistake standing here, one document later, would teach two different lessons about the same underlying problem.
*Preserves principles because:* the generalization lives entirely at "who may produce a candidate" — it touches nothing in `GovernanceKernel`, `UnifiedMemory`, Delegation, or `CognitiveService`, all explicitly out of scope.
*More stable because:* a genuinely new future component — Memory Retrieval, Capability Selection, Trust Calibration, Service Ranking, Context Construction, or something with no name yet — gains learning by choosing a `domain` string and emitting a candidate. Zero architectural change, the same "extension, not redesign" property already proven at the Runtime layer.

**3. A new invariant: promoted Learning Candidates are retrievable evidence, never executable rules.**
*Insufficient because:* this was previously true only by implication (learned patterns were described as "just better evidence"), not stated as a standing, checkable rule — leaving room for a future implementation to quietly degrade into matching against promoted patterns instead of reasoning, without anything in the architecture flagging the drift.
*Preserves principles because:* it mechanizes a distinction the Kernel Constitution's own Pressure Test already endorsed in principle (execution determinism vs. capability determinism, Part I below) rather than introducing a new one.
*More stable because:* a concrete, checkable rule survives implementation contact; a narrative property does not.

**4. Part VIII states explicitly that no centralized aggregator, broker, or authority is assumed.**
*Insufficient because:* the absence of this statement left room to infer some shared central store, especially given language like "candidates accumulate" — an ambiguity, not a design, but one worth closing rather than leaving to be caught later.
*Preserves principles because:* it directly reinforces Law 5 (local-first by default) and Constitution Invariant 8 (never self-executing), which an unstated topology assumption could otherwise erode by omission.
*More stable because:* stating it costs nothing and forecloses a misreading before an implementation has a chance to build on it.

**5. The stable candidate→validate→govern→promote contract is explicitly distinguished from recurrence-clustering, the mechanism this document currently specifies for producing consolidated candidates — not conflated with it.**
*Insufficient because:* presenting recurrence-clustering as *the* learning mechanism, rather than as *a* currently-specified way of producing candidates, would make a future, more sophisticated technique (LoRA fine-tuning, DPO — already adopted, Phase 7/8 of the project's own roadmap) look like a competing architecture instead of a compatible producer feeding the same governed gate.
*Preserves principles because:* it strengthens Law of Replaceability, applied to the production step specifically, without touching Governance, `UnifiedMemory`, Delegation, or `CognitiveService`.
*More stable because:* whatever learning technique OCBrain uses a decade from now, it still has to produce governed candidates before affecting runtime behavior — this framing keeps that true regardless of which specific technique eventually wins.

---

## Part I — Governing Principle

Unchanged in substance from the prior version, restated with the new vocabulary: judgment and mechanism are never the same component (K4.1's own governing principle); this document's parallel is that **experience produces candidates, and only governance produces change.** This resolves the Pressure Test's own "Determinism vs. Learning" tension — *"distinguish execution determinism (same compiled plan + same inputs → same scheduling decisions) from capability determinism (a capability's behavior may evolve via governed learning, but each evolution is itself a versioned, event-logged, replayable transition)"* (Pressure Test §2) — by giving it concrete mechanics: replaying the same request against the same promoted state still produces the same decision; what changes over time is the state, openly, through governance, never the decision procedure itself.

---

## Part II — The Learning Pipeline

**The `LearningCandidate` contract — new, explicit, where it was previously implicit.** Any cognitive component, named here or not yet imagined, constructs one to propose something worth considering:

```text
LearningCandidate (a Cognitive Artifact subtype, K4.1 Part IV):
    resource_id:       str
    produced_by:        str     # which component/worker emitted it — any, not a fixed set
    domain:             str     # open-ended, free-form — "intent_pattern", "planning_heuristic",
                                  # or a domain that doesn't exist yet; never a closed enum
    derived_from:       list[str]   # the Experience(s) this observes
    confidence:          float
    evidence_count:      int    # independent recurrences supporting it (Part VI)
    lifecycle_state:     str    # reuses Truth Framework values directly: candidate -> verified
                                  # -> superseded/deprecated — not a parallel status system
```

`domain` is the whole of the generalization: nothing downstream — harvesting, clustering, validation, governance, promotion, retrieval — inspects it for anything beyond grouping and namespacing. A component that doesn't exist yet participates by choosing a string.

```text
ONE SESSION (already fully captured by K4.1 — nothing new required to observe it):
  Intent → Goal → ExecutionPlan → [Delegation / Execution] → ReflectionRecord + EvaluationRecord
                                                                     │
                                                                     ▼
                      Any component reasoning over this session — Reflection, most commonly,
                      but not exclusively — may emit zero or more LearningCandidates, each
                      stored as an ordinary KnowledgeEntry at candidate truth_status
                                                                     │
                  ... candidates accumulate across many independent sessions, over time,
                      from this instance's own components and (Part VIII) from candidates
                      received elsewhere — no centralized store, no shared authority ...
                                                                     ▼
HARVEST / MINE — MemoryCuratorWorker, its existing active-memify role extended:
  Query accumulated candidates, cluster for recurrence within each domain, consolidate one
  higher-confidence candidate per cluster that clears the recurrence threshold
                                                                     │
                                                                     ▼
VALIDATE — EvaluatorWorker, its existing scoring role extended:
  A domain-agnostic criterion, unaffected by the generalization: replay the candidate against
  held-out past Experiences (Part IV); promote only if it strictly improves predicted outcomes
  over current behavior, for that domain specifically
                                                                     │
                                                                     ▼
GOVERN — GovernanceKernel, EvolutionGovernor.SELF_MODIFYING_ACTIONS (existing action types)
  REJECT / ESCALATE / APPROVE. Capability- or service-gap candidates always ESCALATE (Part IX)
                                                                     │
                                                                     ▼  (approved)
PROMOTE — UnifiedMemory.write(), unchanged: candidate → verified
                                                                     │
                                                                     ▼
RUNTIME — K4.1, entirely unchanged, and now an explicit invariant (Part XI, #3):
  Any component's own reasoning retrieves verified entries through the existing hybrid
  retrieval path, as one input among others including the current request. A verified
  candidate is consulted, never mechanically applied — see Part XI.
```

**The stable contract versus the current production mechanism.** Everything above the "HARVEST / MINE" line — the `LearningCandidate` shape and the validate→govern→promote gate — is the durable architectural commitment. Recurrence-clustering is this document's currently-specified answer to *how* candidates get produced and consolidated; it is not the only one the architecture permits. A future trajectory-fine-tuning pipeline (already on this project's own roadmap, Phase 7/8: LoRA fine-tuning, self-instruct data generation, DPO/GRPO) would be a second, complementary producer of `LearningCandidate`s — still gated by the identical validate→govern→promote path — not a competing architecture requiring redesign.

---

## Part III — Learning Candidates From Any Component

The six components named throughout this document are illustrative, not exhaustive — the point worth stating plainly rather than leaving implicit a second time.

| Component | What a Learning Candidate looks like | Typical producer |
|---|---|---|
| Intent Interpretation | A recurring phrasing→meaning mapping; an ambiguity and its usual resolution; a calibration adjustment | Reflection |
| Goal Formation | A constraint-extraction pattern; a reusable goal archetype; a disambiguation resolution | Reflection |
| Planner | A decomposition heuristic; a capability/service selection preference; a recovery-strategy preference | Reflection, Supervisor |
| Reflection | Reflection's own calibration — over- or under-flagging | Evaluation |
| Evaluation | Predicted-vs-actual calibration (Brier-style) | Evaluation's own track record — already specified in K4 §8, unredesigned here |
| Supervisor | A recurring-failure pattern; a recovery-strategy preference | Supervisor |
| *(any future domain)* | Whatever that component's own reasoning judges worth proposing | That component itself |

Validation's own criterion — does applying this candidate to held-out past data improve predicted outcomes — is already domain-agnostic; it doesn't need to know what a "Trust Calibration" or "Service Ranking" candidate even means to evaluate whether it works. That genericity, already required for Evaluation's existing job, is additional evidence the generalization above costs nothing new to support.

---

## Part IV — Experience Model

Unchanged in substance. An Experience — request, intent, goal, planner decisions, delegation chain, selected capabilities, execution outcome, reflection, evaluation, feedback, lessons learned — is a reconstructable view over artifacts and events K4.1 already captures (`derived_from` chains, `EventStream`'s delegation events, `WorkflowDefinition` node configuration, worker-lifecycle events), not a new persisted object — the same resolution K4.1 already used for its own Delegation Graph. Held-out replay means a subset of accumulated Experiences deliberately excluded from a candidate's own derivation, so validation measures generalization rather than self-confirmation — the same discipline `open-thoughts`' verification-gate design validated for trajectory data, applied here to cognitive patterns.

---

## Part V — Learning Memory

Unchanged: views, not separate stores. "Intent Memory," "Planning Memory," and so on are the same `UnifiedMemory` L3 layer, distinguished by a namespacing convention on the existing `procedure_name` field — now more precisely, the `domain` value on a promoted `LearningCandidate` *is* that namespace. No sixth persistence system, no new one for any future domain either.

---

## Part VI — Learning Sources

Unchanged. Explicit feedback (corrections, confirmations, clarifications, edits) and implicit feedback (execution success/failure, replanning frequency, retries, abandoned tasks, usage patterns, long-term interaction history) both feed candidate production; they differ in confidence assigned, not in mechanism. A single implicit signal is noise; the same implicit pattern recurring across independent sessions is evidence — which is why Part II's clustering step requires recurrence before consolidating, regardless of which domain the signal concerns.

---

## Part VII — Ontology Evolution

Unchanged: not a separate mechanism, the natural result of Part II's pipeline when a cluster is broad enough to constitute a new category rather than a narrow correction. The Kernel's ontology is never a fixed enum; it is whatever is currently `verified`, discoverable through retrieval — the identical discipline already applied to `CognitiveService.domain_scope` and now, explicitly, to `LearningCandidate.domain` itself.

---

## Part VIII — Cross-Instance Knowledge Evolution

Grounded in the Kernel Constitution's own Invariant 8 ("recommendations sourced from outside a single instance are never self-executing") and the Pressure Test's Cross-Instance Advisory Layer naming, unchanged. What's added here, directly responding to this review's own instruction to verify no hidden centralized assumption remains:

**No aggregator, broker, or central authority is assumed anywhere in this architecture.** "A received candidate" means only that some `LearningCandidate`, from some other instance, via some exchange mechanism this document does not specify (per instruction — no networking protocol is designed here), has entered this instance's own pipeline as input. Whether that mechanism eventually turns out to be peer-to-peer, hub-and-spoke, or something else changes nothing about promotion, validation, or trust — which is precisely why the exchange mechanism is out of scope: nothing above it depends on its shape.

**What gets exchanged:** never raw Experience — only already-promoted, already-generalized `LearningCandidate`s, which by construction have already been stripped of request- and user-specific content as a structural property of having survived local promotion, not as a separate export-time step.

**How a received candidate is treated:** as one more input to the local clustering step, at a trust tier no higher than "externally-sourced, uncorroborated," promoted on this instance only once this instance's own held-out Experiences corroborate it — the same minimum-not-maximum trust composition K4.1 already established for delegation chains, applied here to knowledge provenance.

**Not solved here, carried forward honestly:** the Pressure Test's own identified risk — repeated advisory-only suggestions, aggregated across users, homogenizing behavior through pure repetition without ever crossing the auto-execution line — remains open. Nothing in this document resolves it; restating that is more honest than implying otherwise.

---

## Part IX — Governance Integration

Unchanged. Every promotion is a `GovernanceKernel.evaluate_action()` call using the existing `EvolutionGovernor.SELF_MODIFYING_ACTIONS` types, closing the gap K4 §15 already flagged. One asymmetry, reconfirmed under the generalization rather than weakened by it: capability- or service-gap candidates — regardless of which component's reasoning surfaces them — always `ESCALATE`, unconditionally, never silently auto-promoted regardless of validation score.

---

## Part X — Ownership Boundaries

| Layer | Owns | Never owns |
|---|---|---|
| Any cognitive component | Producing its own `LearningCandidate`s, namespaced by `domain` | Cross-session clustering, validation, or promotion of its own or any other candidate |
| `MemoryCuratorWorker` (extended) | Harvesting and clustering candidates into consolidated proposals, across all domains uniformly | Judging correctness (Evaluation) or permission (Governance) |
| `EvaluatorWorker` (extended) | Validating a candidate against held-out Experience, domain-agnostically | Approving or promoting anything |
| `GovernanceKernel` / `EvolutionGovernor` | The sole promotion decision, for every candidate regardless of domain or origin | Producing candidates or judging their quality |
| `UnifiedMemory` | Storing every learning artifact as a namespaced `KnowledgeEntry` | A second, parallel persistence path |
| Any component's own reasoning | Consulting verified entries through existing retrieval, as evidence | Mechanically applying a candidate without reasoning over current evidence |

---

## Part XI — Invariants

1. Learning never directly mutates runtime behavior — it produces candidates for governed promotion.
2. A candidate is invisible to retrieval, and therefore to any component's reasoning, until promoted.
3. **Promoted Learning Candidates are retrievable evidence, never executable rules.** Every reasoning step remains an active act of reasoning over currently-available evidence, of which promoted candidates are one input among others, always including the current request itself. A candidate is consulted exclusively through the same retrieval-then-reason path used for any other evidence — never a direct lookup-and-apply shortcut that bypasses reasoning. *(New this revision.)*
4. Every promotion is a versioned, event-logged, replayable transition.
5. A single implicit signal is never sufficient for promotion; recurrence across independent experiences is required, regardless of domain.
6. Explicit feedback may be trusted faster than implicit feedback, never the reverse.
7. Capability- or service-gap candidates always escalate to human review, regardless of validation score or which component surfaced them.
8. Externally-sourced candidates are never self-executing and never inherit trust above "uncorroborated" until locally corroborated.
9. Learning never bypasses `GovernanceKernel`.
10. No separate "learning memory" store exists for any domain, present or future.
11. A correction is a new fact, never an edit to the record being corrected.
12. No centralized aggregator, broker, or authority is assumed by this architecture, for any exchange mechanism.

---

## Part XII — Stress Test

- **Dozens of future cognitive components, new learning categories not yet imagined:** the `domain` field and the unchanged validate→govern→promote gate handle this by construction — participation requires choosing a string, nothing else. This is the concrete mechanism, not an assertion.
- **Hundreds of Cognitive Services, years of accumulated experience:** the pipeline scales by data volume; recency-decay and `prune_stale()` already prevent unbounded growth of *active-weight* candidates as raw history grows indefinitely.
- **AI-generated, third-party, community-created services:** learned patterns about their reliability are just more candidates, trust-tiered identically to any other.
- **New learning mechanisms not yet imagined** (beyond recurrence-clustering): Part II's stable-contract distinction is the direct answer — any future producer, however different its internal method, still emits a `LearningCandidate` and still passes the same gate.
- **Enterprise deployments:** not designed here, consistent with the position already taken in the Delegation Architecture — no evidence of need, and the Governor-extension pattern makes it cheap whenever evidence arrives.
- **Offline-first execution, optional knowledge exchange:** unchanged from the prior version — local operation is complete without cross-instance exchange, which degrades nothing by its absence.

---

## Part XIII — ADR Candidates

1. "Learning Candidate" replaces "Instinct," defined directly against the existing Truth Framework's `candidate` status rather than a parallel vocabulary.
2. The learning surface is generalized to any component via one `LearningCandidate` contract with an open `domain` field, rather than six named, implicitly closed categories.
3. Promoted candidates are retrievable evidence, never executable rules — codified as a standing invariant, not left implicit in retrieval-path prose.
4. This architecture assumes no centralized aggregator, broker, or authority for cross-instance exchange, stated explicitly.
5. The candidate→validate→govern→promote contract is the durable commitment; recurrence-clustering is the currently-specified, replaceable production mechanism — explicitly compatible with, not competing against, the project's own Phase 7/8 fine-tuning roadmap.
6. Capability/service-gap candidates always escalate, regardless of domain or validation score, unaffected by the generalization.

---

## Part XIV — Future Milestone Impact

Unchanged from the prior version. K4.2 should design each component's reasoning to consult verified L3 entries through existing retrieval from the outset. K4.4 should implement candidate production and held-out validation as extensions of the roles K4 §7–§8 already specify. K4.5 should adopt the `domain` namespacing convention when it wires promoted plans. K4.6 should implement the escalate-always rule for gap findings from the start. No impact on K4.3 beyond what K4.1 already specifies.

---

## Part XV — Closing Assessment

This revision earns its place: the five changes above are substantive, not stylistic, and three of them (generalization, the new invariant, the explicit non-centralization statement) close gaps that a careful future reader would eventually have found anyway — better closed now, at the architecture-only stage, than after K4.2 has already built against the narrower version. The fourth and fifth (terminology, the stable-contract framing) are precision improvements that cost nothing and remove two ways this document could have quietly drifted from its own stated principles.

With this document and K4.1, the two authoritative references this project asked for now exist. Recommend no further architecture-only work at this layer before implementation begins. The genuinely next open questions — whether the recurrence threshold is calibrated correctly, whether `LearningCandidate` production actually generalizes as cleanly to an unforeseen domain as this document claims it will — are exactly the kind that implementation contact answers and further specification cannot.

---

*Cognitive Learning Architecture (Final) complete. No implementation performed, no repository files modified, no interfaces frozen. Supersedes the prior Learning Architecture in full. Together with K4.1, this is the complete architectural reference for implementation beginning at K4.2.*
