# OCBrain K4.1 — Cognitive Service Architecture
## Revision: Replacing the Extension Model with a Generic Registry

**Date:** July 19, 2026
**Status:** Architecture Only — revises `OCBRAIN_K4_1_COGNITIVE_RUNTIME_FOUNDATION.md` ("K4.1"). Zero code, zero implementation, zero repository modifications, zero interface freezing, per instruction.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md` and `PROJECT_INSTRUCTIONS.md`; K4's core-pipeline design (`OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md`, "K4") is untouched. This document supersedes every part of K4.1 concerned with "Cognitive Runtime Extensions" — the contract, registry, admission test, trust, lifecycle, and delegation model. K4.1 sections not concerned with Extensions are unaffected and not repeated here — §10 lists them explicitly.

---

## 0. What Changes, and Why

| K4.1 term | Revised term | What actually changed |
|---|---|---|
| Cognitive Runtime Extension | **Cognitive Service** | Terminology only, but see §2 — the old name carried an implicit asymmetry the new one is chosen to remove |
| Extension Registry | **Cognitive Service Registry** | Mechanism unchanged, renamed |
| `domain_scope: str` (one field) | **`ServiceProfile`** (four fields: description, accepts, produces, requires) | Substantive redesign — one string couldn't carry the independent matching dimensions this session correctly identified. Full design in §4. |
| Extension Admission Test | **Service Admission Test** | Mechanism unchanged, renamed |
| Extension Trust | **Service Trust** | Mechanism unchanged (still the existing Truth Framework), renamed |
| Extension Lifecycle | **Service Lifecycle** | Mechanism unchanged, renamed |
| "Extension Model" (K4.1 §9) | **"Service Delegation Model"** | Renamed, and the discovery step inside it is rewritten to use `ServiceProfile` |
| Discovery / Workspace / Skill / Knowledge / Agent / Learning used repeatedly as the running examples | Same examples, but described only by what they'd claim in a `ServiceProfile`, never by a capitalized proper name | Closes a real residual gap: K4.1's *contract* was already generic (one Protocol, not six), but its *prose* still treated six names as the expected taxonomy. §7's walkthrough now uses undramatic, previously-unused examples specifically to demonstrate this. |

Two things are true at once, and it's worth being precise about which is which rather than blurring them: the rename (Extension → Service) is mostly cosmetic — it removes a connotation, not a mechanism. The `domain_scope` → `ServiceProfile` change is not cosmetic — it's a genuine redesign of how discovery works, prompted by a real gap in K4.1 that this session correctly identified.

**Recommendation on reconciling with K4.1 itself:** once accepted, `OCBRAIN_K4_1_COGNITIVE_RUNTIME_FOUNDATION.md` should be marked superseded (or directly replaced) rather than left standing alongside this document. The project already carries one unresolved instance of exactly this failure mode — the Constitution's own law-count discrepancy, where five downstream documents assert 11 laws against the checked-in 9-law file, still open as of this writing. Two documents disagreeing about the same architectural layer is how that happened; this document is written as a complete, self-sufficient replacement for K4.1's Extension-concerned sections specifically so that superseding is a clean swap, not a merge someone has to do by hand later.

---

## 1. Is This a Rename or a Redesign? — Answered Honestly

K4.1 already got some of this right, and it's worth saying so rather than implying the whole thing was wrong. `CognitiveExtension` was already a single generic Protocol, not six named contracts (K4.1 §5), specifically to avoid the closed-taxonomy problem. Invariant 4 already said "the Cognitive Runtime never hardcodes knowledge of a specific Extension's identity or type." Those decisions stand.

What K4.1 got only partway right: the *word* "Extension" implies something added onto a base system — asymmetric, secondary, optional in a way that subtly reads as "less core" than Planner or Plan Compiler. And the *discovery mechanism* — one free-form string — couldn't actually carry enough information for Planner to make a good delegation decision, which meant that in practice, richer information would have ended up encoded informally in a service's `name` or in prose Planner would have to parse, quietly reintroducing exactly the special-casing the contract was designed to prevent. Both of these are real gaps, not just style preferences, and both are fixed below.

---

## 2. The Governing Analogy, Tested

The StorageBackend comparison is the right one, and it's worth actually working through rather than just citing. In the current architecture: `UnifiedMemory` is a fixed, singleton Kernel service — it is not itself swappable. What *is* swappable underneath it are its backends: `SQLiteStorageBackend`, `SQLiteGraphBackend`, `SQLiteArchiveBackend`, `InMemoryVectorBackend`. `UnifiedMemory` knows exactly one thing about a backend — that it satisfies the backend contract — and nothing about whether it's SQLite or something else.

Followed rigorously, this analogy actually *confirms* something K4.1 already decided rather than overturning it: the core Cognitive Runtime components (Intent Interpreter, Planner, Plan Compiler, ReflectionWorker, EvaluatorWorker, SupervisorWorker) stay fixed, the same way `UnifiedMemory`, `GovernanceKernel`, and `WorkflowRuntime` are fixed — none of *those* are pluggable in the existing Kernel architecture, only their backends are. This document is not proposing that Planner itself become a registered, swappable thing. The swappable periphery is specifically the reasoning-domain layer that used to be called "Extensions."

One place the analogy needs sharpening rather than blind adoption: every `StorageBackend` implementation is interchangeable with every other one for the *same* job — swapping SQLite for Postgres changes performance, not what `UnifiedMemory` can do. Cognitive Services are not interchangeable with each other in that sense. A service that reasons about database schema compatibility and a service that reasons about clinical guideline lookup aren't two options for solving the same problem — they solve different problems. This is precisely why backend selection can be a simple typed interface (read/write/query) while service discovery needs something richer than "pick the best available implementation of the same interface." §4 is that richer mechanism. The analogy holds for the part that matters most here — generic contract, fixed core, zero hardcoded implementation names — and that's the part this revision is built on.

---

## 3. CognitiveService — The Renamed Contract

One naming check worth doing explicitly, in the spirit of K1.5's own vocabulary-freeze discipline: K1.5 §1 already uses "Service" as a generic term for Kernel-internal coordination components (`GovernanceService`, `EventService`, `MemoryService`, `ContextService` — §2.1's own heading is "The Real Service Set"). `CognitiveService` doesn't collide with any of those specific names, but the bare word is now doing double duty at two different layers. Rather than abandon the term you asked for over a mild, resolvable adjacency, the disambiguation rule is simple and stated once, here, rather than left to infer: **bare "Service," unqualified, always means one of K1.5's Kernel-layer services. This layer's concept is never referred to as bare "Service" — always "Cognitive Service," in full.** That's the whole rule; it costs nothing and removes the ambiguity.

**Revised shape** (illustrative fields, not a frozen schema — same convention K4 and K4.1 already used):

```text
CognitiveService (Protocol — structurally satisfied, not inherited):
    resource_id:      str    # identity, per the K1.6 Resource convention
    name:              str
    version:           str    # Law of Contract Stability
    profile:           ServiceProfile   # replaces domain_scope -- see §4
    lifecycle_state:   str    # registered -> active -> degraded -> deprecated
    trust_status:      str    # reuses the existing Truth Framework -- unchanged from K4.1
    dependencies:      list[str]   # declared Capability/Kernel-service needs, least privilege

    async def describe(self) -> ServiceProfile: ...   # the "Find" half
    async def reason(self, subgoal, context_view) -> CognitiveArtifact: ...  # the "Call" half
    async def health(self) -> ServiceHealth: ...  # see §4 for why operational signal lives here
```

Everything not called out above is unchanged from K4.1 §5: `CognitiveService` still satisfies the K1.6 `Resource` Protocol (identity, version, lifecycle); it is still distinct from the Kernel's `CapabilityContract` (a Capability is executed, a Cognitive Service is reasoned with); registration, versioning, and trust discipline are unchanged in substance.

---

## 4. Service Discovery — The Redesigned Mechanism

This is the one place this revision does real design work rather than renaming. The question worth answering honestly first: is a single free-form string actually insufficient, or would it have been enough with more careful phrasing? It's insufficient, and the reason is structural, not phrasing: a service's discoverability depends on several genuinely independent questions — what shape of problem does it take, what does it hand back, what does it need to do its job — and collapsing all three into one field forces Planner to either write increasingly overloaded strings or fall back on informally special-casing names it recognizes, which is exactly the failure mode this whole exercise exists to close.

**`ServiceProfile`** (returned by `describe()`, illustrative fields only):

```text
ServiceProfile:
    description:  str         # free-text, natural-language -- the primary matching substrate
    accepts:       list[str]   # short, open-ended descriptors of goal/task shapes this service
                                 # can act on (tags or phrases -- never a closed enum)
    produces:      list[str]   # which Cognitive Artifact subtype(s) this service can mint,
                                 # named/described in terms of the vocabulary already
                                 # established for Cognitive Artifacts (K4.1 §8) -- not a
                                 # parallel classification scheme
    requires:      list[str]   # declared CognitiveContext fields / Capability dependencies
                                 # needed to reason -- feeds directly into how the scoped
                                 # CognitiveContextView (K4.1 §6) gets constructed for this
                                 # service, and overlaps with `dependencies` above
    examples:      list[str]   # optional -- a few sample sub-goals this service would claim,
                                 # useful for few-shot matching, not required at registration
```

**Why four fields and not a "reasoning mode" taxonomy.** The session's own suggestion of "supported reasoning modes" was considered and rejected as its own field, on a specific ground: a fixed set of reasoning-mode values (exploratory search, constraint satisfaction, creative generation, verification, and so on) is a closed taxonomy wearing a new name — it relocates the exact problem being solved rather than solving it. Every field above that carries a list is explicitly open-ended (tags, not an enum); the only thing doing the actual heavy lifting is `description`, in free text, matched semantically. A structured taxonomy of "modes" would eventually need its own extension the same way `domain_scope` did.

**Why matching is semantic, not tag-lookup.** Planner already reasons over natural language when decomposing a Goal into steps (K4 §5 — decomposition is itself LLM-assisted). Discovery reuses that same reasoning rather than inventing a second matching algorithm: Planner reads the registered `ServiceProfile.description`/`accepts`/`examples` for services returned by the Cognitive Service Registry and judges fit as part of the decomposition it's already doing. This is not a new component — no dedicated "Service Matcher" is introduced, for the same reason K4.1 §9 already rejected a dedicated "Extension Orchestrator": Planner (at plan time) and Supervisor (at recovery time) already own the two moments delegation happens, and a third component duplicates that authority. The structured fields (`accepts`, `produces`, `requires`) exist as a cheap first-pass filter and as a way to tie a service's output directly to the already-established Cognitive Artifact vocabulary (§6) — they support the semantic match, they don't replace it.

**Why "reasoning characteristics" (cost, latency, track record) live in `health()`, not `ServiceProfile`.** This was the session's last suggested dimension, and it's the one place the right answer is neither "add it to the profile" nor "ignore it" — it's "put it somewhere else." `ServiceProfile` describes what a service *is*, fixed at registration; cost, latency, and calibration history describe how it's *currently performing*, which changes continuously and would stale-date a static profile the moment it's embedded there. `health()` already exists for exactly this kind of dynamic signal. When more than one registered service plausibly matches a sub-goal, K4.1 §9's existing decision stands unchanged: this is handled as parallel candidate sub-plans via Planner's own `alternatives`/`confidence` machinery, not a dedicated ranked resolver — and `health()`'s operational signal is precisely the input that machinery would weigh, without needing a new component to do the weighing.

**On scale.** At a handful of registered services, Planner reasoning over every returned profile is cheap. At dozens, that stops being free. This is a real, foreseeable cost — and deliberately not designed around now, per Law of Evidence over Assumption: there is no evidence yet of how many services a real OCBrain instance will register, and a pre-filter (embedding similarity over `description`, say) is a straightforward addition later if and when that evidence exists. Noted here so it isn't rediscovered as a surprise; not solved here because there's nothing to solve yet.

**Governance check.** Semantic matching over `ServiceProfile` data is pre-decision reasoning — the same category as Planner's own goal decomposition — and causes no real-world effect on its own. It does not need its own governance gate, for the same reason decomposition doesn't: the gate that matters is Plan Compilation (K4 §15), and nothing about how a delegation candidate was *found* changes what happens at that gate. Invariant 5 (§8) still holds without modification.

---

## 5. Ownership, Lifecycle, Trust, Admission — Renamed, Substance Preserved

These carry forward from K4.1 with terminology updated and no mechanism change; restated compactly rather than re-derived.

**Ownership boundary (K4.1 §3).** The "Cognitive Runtime Extensions" row becomes "Cognitive Services," with one addition worth making explicit rather than implicit: the core Cognitive Runtime's "never owns" column now explicitly includes *knowledge of which named services exist* — not just their internal reasoning (already stated in K4.1), but their identity as a category. Concretely: nothing in the core Cognitive Runtime's own logic should ever contain a literal reference to "discovery," "workspace," "skill," or any other domain name — those exist only as data inside registered `ServiceProfile` instances, never as branches in the core's own code or reasoning templates.

**Service Lifecycle.** Unchanged: `registered → active → degraded → deprecated`, one enum per K1.6 §4's "each Resource type owns its own lifecycle enum" — still not the Truth Framework (that's `trust_status`), still not a universal twelve-state machine.

**Service Trust.** Unchanged: reuses the existing Truth Framework (`unknown → candidate → verified → conflicted → deprecated`) rather than a parallel mechanism, per the same reasoning already adopted for skill trust tiers. Community-developed and user-created services — both named explicitly in this session's brief as expected future sources — are not exempt from this, and their real-world effects still execute inside the Kernel's existing sandboxing (PI §14.1) regardless of how they're discovered.

**Service Admission Test.** Unchanged in structure, renamed in label — still modeled on the Kernel's own three-gate Admission Test (Constitution Part V): Necessity (does this genuinely require domain judgment, not just execution of a defined task), Placement (could an ordinary Capability or an existing service's extended scope satisfy this instead), Durability (will this still be a coherent domain in ten years).

---

## 6. Cognitive Artifacts — One Tightened Connection

K4.1 §8's Cognitive Artifact category (a specialization of the K1.6 Resource Protocol; Intent, Goal, ExecutionPlan, ReflectionRecord, EvaluationRecord as known members; category open to new subtypes) is unchanged. The one addition: `ServiceProfile.produces` (§4) should be expressed in terms of this same vocabulary — a service declares what it produces as artifact subtypes or descriptions of them, not as a separate taxonomy invented for the registry. This wasn't stated explicitly in K4.1 and is worth making a standing rule now, since it's the kind of small consistency choice that's cheap to fix here and expensive to reconcile later.

---

## 7. Service Delegation Model

Supersedes K4.1 §9 ("The Extension Model"). Discovery and registration, invocation, and the rejected-alternatives list are unchanged in substance from K4.1 §9 beyond the rename — services register into the Cognitive Service Registry at composition-root time; invocation reuses `ExecutionRuntime`/`WorkflowRuntime` with zero new Kernel mechanism (§1's headline finding from K4.1 stands, restated: every real-world effect still flows through exactly one seam — Plan Compilation → `WorkflowDefinition` → Kernel execution); a dedicated Orchestrator, a parallel event bus, hot-reload, and a closed domain enum are all still explicitly rejected, for the same reasons given in K4.1 §9.

**Delegation, restated with the new mechanism.** During Planning (or Supervision's failure-recovery reasoning), the core Cognitive Runtime queries the Cognitive Service Registry, reasons semantically over the returned `ServiceProfile`s against the sub-Goal at hand (§4), hands the matched service a scoped `CognitiveContextView` built from its declared `requires`, and receives back a Cognitive Artifact that folds into the plan already being built.

**Illustrative walkthrough, deliberately using two fresh, undramatic examples rather than the original six** — neither is designed here; this is only to demonstrate that the mechanism doesn't care whether a domain is grand or mundane. A hypothetical registered service with `ServiceProfile.description` reading roughly "evaluates whether a proposed change to a stored schema stays backward-compatible with existing queries against it" would be found by Planner the same way, through the same registry, using the same semantic match, as a hypothetical service described as "proposes and validates new reusable Capabilities from repeated successful task patterns" — the second being where the SkillOpt-inspired mechanism already flagged in the research corpus (`OCBRAIN_EXTERNAL_REPO_STUDY.md` §1, §8) would eventually live, if and when that service is actually built. Neither carries a capitalized proper name anywhere in this document on purpose. Whatever a future service does — schema checking, clinical guideline lookup, structural constraint checking, music composition, or something with no name yet — it is found, delegated to, and folds its result back in through the identical path.

**Proposing versus registering (unchanged from K4.1).** Services may propose new Kernel Capabilities; only the Kernel, governed, may register one. This still traces to Constitution Invariant 8 ("recommendations sourced from outside a single instance are never self-executing") applied to recommendations from inside the instance but outside the Kernel's trust boundary.

---

## 8. Updated Invariants

Supersedes K4.1 §10. Renamed throughout; one invariant sharpened, none removed.

1. **Reasoning never executes.** The Cognitive Runtime and every registered Cognitive Service may only produce Cognitive Artifacts; only the Kernel executes anything with real-world effect.
2. **Execution never reasons.** A compiled `WorkflowDefinition` is fixed; a step revealing the need for more reasoning returns control to Supervisor for a new planning cycle, never reasons in place.
3. **Every real-world effect flows through exactly one seam:** Plan Compilation → `WorkflowDefinition` → Kernel execution. No Cognitive Service is granted, or may construct, a second door into `WorkflowRuntime`.
4. **The Cognitive Runtime never hardcodes knowledge of a specific service's identity, category, or domain name — in its code or in its reasoning templates.** *(Sharpened from K4.1's version: the original said "identity or type"; this makes explicit that a hardcoded category name inside a prompt template is exactly as much a violation as a hardcoded name inside control-flow code — this session's own core complaint about K4.1's residual taxonomy was precisely this gap.)*
5. **The Cognitive Runtime never bypasses Governance, including on a Cognitive Service's behalf.** Every consequential action a service's reasoning leads to re-enters through `evaluate_action()` exactly as any other action does.
6. **A `CognitiveContext`, or a scoped projection of one, is visible only for the duration of the request that created it.** No service, and no component of the core Cognitive Runtime, retains a reference past that boundary.
7. **Every delegation from the core Cognitive Runtime to a Cognitive Service is itself explainable** — which service, why, and what it returned are first-class facts in the artifact trail.
8. **A failing, unavailable, or low-trust Cognitive Service degrades capability in a bounded, describable way**, per Constitution Law 11, one layer up.
9. **No single Cognitive Service, current or future, is load-bearing for the Cognitive Runtime's own definition of itself** — direct mirror of Constitution Invariant 9, one layer up.

---

## 9. Updated ADR Candidates

Supersedes K4.1 §11. Enumerated only.

1. **ADR-K4.1-01** — (unchanged) Cognitive Runtime reasoning composes through the existing Plan Compilation seam; no new Kernel-facing mechanism.
2. **ADR-K4.1-02 (revised)** — `CognitiveService` is a single generic Protocol; the term "Service" is disambiguated from K1.5's Kernel-layer usage by always being qualified as "Cognitive Service" (§3).
3. **ADR-K4.1-03** — (unchanged) `CognitiveContext` renaming and scoped-projection visibility for services.
4. **ADR-K4.1-04** — (unchanged) Cognitive Runtime service-level lifecycle distinct from `CognitiveContext`'s per-request lifecycle.
5. **ADR-K4.1-05** — (unchanged) Cognitive Artifact as a Resource Protocol specialization; extended by ADR-09 below to require `ServiceProfile.produces` use the same vocabulary.
6. **ADR-K4.1-06** — (unchanged) Services propose, never directly register, new Kernel Capabilities.
7. **ADR-K4.1-07** — (unchanged) Service trust reuses the existing Truth Framework and SkillSpector-style validation.
8. **ADR-K4.1-08** — (unchanged) Service Admission Test structurally modeled on Constitution Part V.
9. **ADR-K4.1-09 (new)** — `ServiceProfile` replaces `domain_scope` as a four-field structure (description/accepts/produces/requires); reasoning-mode-style closed taxonomies are explicitly rejected as fields; operational signals (cost, latency, calibration) live in `health()`, not the static profile (§4).
10. **ADR-K4.1-10 (new)** — `ServiceProfile.produces` is expressed in the existing Cognitive Artifact vocabulary rather than a separate output taxonomy (§6).

---

## 10. What's Unchanged From K4.1 — Explicit List

For a reader reconciling this document against the original file: the following K4.1 sections are **not** affected by this revision and remain as written there:

- §0 — the K3-status carry-forward note and the roadmap-renumbering finding (old-vs-new K4.1–K4.7 mapping)
- §1's core insight (restated, not altered, in §7 above)
- §2 — the definition of what the Cognitive Runtime is, including the Intent-origin clarification against the layered diagram
- §6 — `CognitiveContext`'s ownership, lifecycle, mutability, persistence, and cleanup rules (only its *visibility to services* is touched, and only by relabeling "Extension" to "Cognitive Service" in that one paragraph)
- §7 — the three-state service-level lifecycle (`INITIALIZING`/`READY`/`SHUTTING_DOWN`) and the rejection of a fourth `DEGRADED` state
- §12 — the future-documentation recommendations (still gated on the same preconditions; none have been met by this revision)

---

## 11. Property Verification

Checked directly against the properties this session asked the resulting architecture to satisfy:

| Required property | Where satisfied |
|---|---|
| The Cognitive Runtime knows only generic Cognitive Services | §3 (single Protocol), Invariant 4 (§8) |
| The registry is completely open-ended | §7 (registration mechanism, unchanged from K4.1) |
| New reasoning systems are added through registration, not redesign | §7's mechanical answer (unchanged from K4.1 §9) |
| No service is special or built into the Cognitive Runtime | §5's ownership addition; no example anywhere in this document carries architectural weight |
| Planner reasons over service capabilities rather than predefined names | §4 (`ServiceProfile` + semantic matching, the core redesign) |
| Compatible with the Kernel Constitution and existing ownership boundaries | §2 (analogy tested against real Kernel structure); nothing in §3–§9 touches Kernel-owned responsibilities |
| Existing examples become illustrative, not architectural | §7's walkthrough deliberately avoids capitalized proper names |

---

## 12. Closing Assessment

Two things are genuinely open, not resolved here, and worth naming rather than smoothing over. First: whether a four-field profile plus semantic matching is actually sufficient discovery quality, or whether it degrades once there are enough real, overlapping services registered that Planner's matching starts guessing wrong — there is no evidence either way yet, and there won't be until a first real service exists to test against; this is exactly the kind of question implementation contact answers better than another design pass would. Second: this document only addresses delegation from Planner (at plan time) and Supervisor (at recovery time), matching K4.1's existing scope — whether a Cognitive Service could ever be relevant earlier, during Intent Interpretation itself, before a Goal has even formed, is a plausible future need that isn't designed here and shouldn't be inferred from anything above; if it turns out to matter, it's a new question for whoever is designing Intent Interpretation in K4.2, not something this revision has quietly answered by omission.

No further design pass is recommended before K4.2. This revision closes the specific gap it was asked to close — a name that implied a taxonomy, and a discovery field that couldn't carry what discovery actually needs — without reopening anything K4.1 already settled correctly.

---

*Revision complete. No implementation performed, no repository files modified, no interfaces frozen. K4.1's Extension-based sections are superseded by this document; K4.1's remaining sections stand as listed in §10. Ready for K4.2 once this revision, and the two open items carried forward from K4.1 §13 (Planner's delegation-matching mechanism now specified here in §4; the multi-candidate resolution lean, still deferred to Planner's own alternatives/confidence machinery), are accepted or deliberately amended.*
