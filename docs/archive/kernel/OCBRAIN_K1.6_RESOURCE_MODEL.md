# OCBrain Kernel — K1.6: Canonical Resource Model & Kernel Object System

**Date:** July 8, 2026
**Status:** Architecture-only, per instruction. No repository files modified. Illustrative type signatures only, not implementation.
**Method:** Field-level inspection of the actual dataclasses in question — `KnowledgeEntry`, `Evidence`/`EvidenceSet`, `Context`/`ContextBlock`/`ContradictionGroup`/`ProvenanceRecord`, `WorkerContext` — read directly from source, not inferred from names. This matters: the central finding of this session only holds up because the fields turned out to say something different than the object *names* suggested.

---

## 0. Headline Finding, Before the Detail

The prompt's own framing worries that "many independent objects representing managed runtime entities" will "continue to diverge" without a common foundation. Reading the actual fields tells a different story: **most of these objects were already deliberately, explicitly designed *not* to share a common Resource shape, and the code says so in its own comments.** `ContextBlock`'s docstring: *"deliberately does NOT embed a raw KnowledgeEntry — ProvenanceRecord projects only the fields a consumer needs, independent of storage implementation, so nothing downstream ever depends on UnifiedMemory's internals through this object."* That's not accidental divergence. That's Separation of Concerns, already correctly applied, by whoever wrote Session 5.5/5.6.

This changes the shape of the answer. The real finding isn't "unify everything under one Resource base" — it's "there are two genuinely different categories here, and the existing code already sorted most objects into the right one without being told to." Sections 1–7 below establish this with evidence; §8 addresses the roadmap question the prompt raises directly, because the finding bears on it.

---

## 1. Repository Audit (Phase 1) — What's Actually There

| Object | File | Purpose | Owner | Lifecycle | Identity |
|---|---|---|---|---|---|
| `KnowledgeEntry` | `core/memory/knowledge_entry.py` | Canonical memory unit | `UnifiedMemory` | `TRUTH_STATUS`: unknown→candidate→verified→conflicted→deprecated — real, working, already in code | `entry_id` (UUID, own identity) |
| `Evidence` / `EvidenceSet` | `graphrag/evidence.py` | One retrieval result + provenance | `GraphRAGPipeline`, per-query | None — built fresh, discarded after use | `entry_id` **property that delegates to `self.entry.entry_id`** — no independent identity |
| `Context` / `ContextBlock` / `ContradictionGroup` / `ProvenanceRecord` | `retrieval/context/context.py` | Storage-independent projection for reasoning consumers | `RetrievalContextBuilder`, per-execution | None — assembled once, immutable | `primary_entry_id` (a *reference to* another object's identity, not its own) |
| `WorkerContext` | `workers/base.py` | Per-invocation execution parameters | `ExecutionRuntime` (once it exists) | None — created at invocation, discarded at completion | `task_id` (correlation ID, not a resource identity) |
| `SkillMetadata` / future `CapabilityMetadata` | `skill_interface.py` (partial) | Describes a registered Capability | `CapabilityRegistry` (once it exists) | Doesn't exist as code yet — proposed below | Would need one — proposed below |
| Governance verdicts | `governance_kernel.py` | Outcome of one evaluation | `GovernanceKernel` | None — computed fresh, logged as an Event | N/A — a decision record, not a managed entity |
| Graph nodes | `memory/graph/graph_engine.py` | Entity representation | `GraphEngine` | Tied 1:1 to the owning `KnowledgeEntry`'s graph-eligible status | Derived from `entry_id`, per the already-established "graph is an index, not a memory layer" principle |
| Workflow state / Task objects | Doesn't exist yet | DAG execution progress | `WorkflowRuntime` (once it exists) | Would need one — proposed below | Would need one — proposed below |
| Event objects | `events/event_stream.py` | Immutable record of a state transition | `EventStream` | Write-once; no transitions at all, not even one | `event_id` + causal ordering |

**Duplication found:** none, once the fields are actually read. What looks like duplication from the object *names* (Evidence, Context, ContextBlock, ProvenanceRecord, WorkerContext all "have fields") turns out, on inspection, to be one real Resource (`KnowledgeEntry`) with three purpose-built, non-overlapping views around it (a retrieval wrapper, a storage-decoupled projection, a per-call parameter bundle) — plus a handful of things that genuinely will need Resource treatment once they're built (Capability metadata, Workflow state) and haven't diverged yet because they don't exist yet.

**Missing concept found:** none of the existing objects independently prove the need for a *new* concept the Constitution doesn't already name. The gap is narrower than the prompt frames it: it's "does `KnowledgeEntry` cleanly satisfy the Constitution's Resource invariant," not "do we need to invent a taxonomy from scratch."

---

## 2. Pattern Extraction (Phase 2) — Every Field Proven or Rejected

Scoped to the **Resource category only** (§3 below explains why scoping matters). Each candidate field, checked against real evidence:

| Candidate | Verdict | Evidence |
|---|---|---|
| Identity / ID | **Keep** | `KnowledgeEntry.entry_id` — real, UUID-based, already load-bearing |
| Creation / modification time | **Keep** | Required by the existing recency-decay term in the memory-scoring formula (PI §8.4) |
| Ownership | **Keep** | Structural field: which Service is authoritative for mutation — not the same as trust |
| Lifecycle state | **Keep, but not a fixed enum** | `TRUTH_STATUS` proves the *concept*; the specific five values are `KnowledgeEntry`-specific, not universal (see §3) |
| Version | **Keep, optional** | Needed for Capability/Workflow resources (Law of Contract Stability); `KnowledgeEntry` has no version field today — don't invent one it doesn't need |
| Dependencies | **Keep, optional** | Needed for Capability resources; not meaningful for `KnowledgeEntry` (a fact doesn't "depend on" other facts the way a Capability depends on another Capability) |
| Relationships | **Keep** | `KnowledgeEntry.contradicts[]` / `.supports[]` already real, confirmed in source |
| Provenance source | **Keep, primitives only** | `ProvenanceRecord` already proves this works as primitives, not live references — copy that pattern, don't re-derive it |
| Trust | **Keep, optional** | Real on `ProvenanceRecord.trust_score`, but that's a *retrieval-time* computation, not stored on `KnowledgeEntry` itself today — field exists on the base, not every instance populates it |
| Metadata (free-form) | **Keep, with a warning** | Real precedent (`WorkerContext.metadata`) — but a free-form dict is exactly how a "smallest correct abstraction" quietly becomes a god object through the back door. Document it as an escape hatch, not a design tool. |
| Confidence | **Reject as a Resource field** | Real on `ProvenanceRecord.confidence`, but that's computed fresh at retrieval time from a specific query — it's not a property of the underlying `KnowledgeEntry` itself. Belongs on the projection type, not the Resource. |
| Labels | **Reject** | Zero evidence anywhere in the codebase that this is used |
| Capabilities (as a field *on* a resource) | **Reject** | No evidence, and conflates "Capability" the kernel concept with "things this resource can do" — confusing, unproven |
| Access policy (embedded) | **Reject — use a reference instead** | Embedding policy data duplicates the Governance/Policy model already defined in the Constitution; a Resource should reference a Policy, not carry one |
| Audit trail (as a field) | **Reject** | Already handled externally by `EventStream` — a Resource needs its transitions *evented*, it doesn't need to carry its own audit log as a field |
| Reference counting | **Reject** | No evidence of need; not idiomatic for this stack |
| Verification history | **Deferred, not designed** | `ProvenanceRecord.verification_history` is already in code, explicitly `None`, with a comment naming Session 5.9 directly. Respecting that boundary — see §6. |

---

## 3. Resource Taxonomy (Phase 3)

**Central decision: `Resource` is a `Protocol`, not an ABC, and definitely not a mixin.**

Reasoning: `KnowledgeEntry` already exists, is live, and is depended on by `Evidence`, `ContextBlock` (transitively), and the graph subsystem. Law of Contract Stability says an existing contract doesn't get broken to satisfy a new one. Requiring `class KnowledgeEntry(Resource):` would touch its class declaration and risk the dataclass machinery, existing serialization, and every current constructor call. A `Protocol` (structural typing — "anything with these fields/methods satisfies this shape") lets `KnowledgeEntry` satisfy `Resource` with zero changes to its inheritance, and lets future types (`CapabilityMetadata`, `Workflow` state) opt in explicitly. This is the "prefer composition over inheritance" instruction applied concretely, not just asserted.

**Does every object inherit/satisfy Resource?** No — and this is the load-bearing decision of the whole session:

| Object | Satisfies `Resource`? | Why |
|---|---|---|
| `KnowledgeEntry` | **Yes** | The clear, proven case — has independent identity, a real lifecycle, persists |
| Future `CapabilityMetadata` | **Yes** | Identity, lifecycle, version, dependencies, trust, provenance — literally the Constitution's own Invariant 4 language |
| Future `Workflow` state | **Yes** | Genuinely needs identity and lifecycle tracked over a potentially long-running execution (durable execution, per K1.5) |
| `Evidence` | **No** | Wraps a Resource; forcing it to independently satisfy `Resource` would duplicate identity/lifecycle tracking that already lives on the wrapped `KnowledgeEntry` — a second source of truth, which Law of Single Source of Truth exists to prevent |
| `Context` / `ContextBlock` / `ProvenanceRecord` | **No** | Deliberately storage-independent projections, by the existing code's own explicit design rationale — forcing Resource shape onto them would undo the decoupling they were built for |
| `WorkerContext` | **No** | Ephemeral per-call parameters; `task_id` is a correlation ID for tracing, not a resource identity meant to be looked up later |
| Event objects | **No** | Immutable, write-once, causally ordered rather than lifecycle-ordered — a category error to force a "lifecycle_state" field onto something that never transitions |
| Graph nodes | **No** | Index entries pointing at a `KnowledgeEntry`'s identity, not independent resources — consistent with "graph is an index, not a memory layer" |

**Mutability:** `Resource` the Protocol takes no position on mutability — `KnowledgeEntry` is explicitly mutable (its own docstring says so), while `Context`/`ContextBlock` are explicitly immutable once built. `updated_at` exists on the Protocol specifically so mutable Resources can express "when did this last change"; immutable types simply never populate it after construction.

---

## 4. Lifecycle Model (Phase 4)

The prompt's example lifecycle (Created→Registered→Active→Referenced→Archived→Deprecated→Deleted→Recovered→Versioned→Snapshot→Fork→Merge — twelve states) doesn't survive the same "prove every field" discipline applied to §2. Zero evidence exists anywhere in this codebase for Fork, Merge, or Snapshot as resource operations. Recommending against a universal twelve-state machine for the same reason §2 rejected unproven fields: inventing structure ahead of a real need is exactly what this session's own instructions warn against.

**Actual recommendation:** the `Resource` Protocol requires that a `lifecycle_state` field exists and that every transition is evented (Law of Explicit State) — it does **not** mandate what the state values are. `KnowledgeEntry` keeps `TRUTH_STATUS` exactly as it is. A future `CapabilityMetadata` might use `draft → registered → active → deprecated`. A future `Workflow` instance might use `pending → running → completed | failed`. Each Resource *type* owns its own lifecycle enum; the Protocol only owns the guarantee that one exists and that transitions are observable.

---

## 5. Ownership Model (Phase 5)

Falls out cleanly from §1's taxonomy — no circular ownership found:

| Resource type | Owner |
|---|---|
| `KnowledgeEntry` | `UnifiedMemory` |
| `CapabilityMetadata` (future) | `CapabilityRegistry` |
| `Workflow` state (future) | `WorkflowRuntime` |

No resource type currently has, or is proposed to have, more than one canonical owner. The non-Resource objects (`Evidence`, `Context`, `WorkerContext`) don't need an ownership entry — they're owned by whichever call constructed them and die with that call.

---

## 6. Identity Model (Phase 6)

Standard convention, already established by `KnowledgeEntry.entry_id` (`field(default_factory=lambda: str(uuid.uuid4()))`) — extend this exact pattern to every future Resource type rather than inventing a second ID scheme. **Rule going forward, made explicit because it wasn't written down anywhere before this session: cross-resource references are always by ID, never by embedding a live object.** `ContextBlock.primary_entry_id` and `Evidence`'s delegating `entry_id` property both already follow this; it should become the standard, not stay implicit tribal knowledge in two files' docstrings.

**Provenance integration (Phase 7):** `ProvenanceRecord.verification_history` is explicitly reserved and explicitly unpopulated in the current code, with a comment naming Session 5.9 by number. This session respects that boundary rather than re-deciding it — the structural slot already exists on the projection type; nothing about the Resource Protocol needs to anticipate its shape further than "a Resource may eventually carry a verification history," which is already true of the field as written.

---

## 7. Serialization, Relationships, Compatibility (Phases 8–10)

**Serialization:** dataclasses already support `dataclasses.asdict()` / JSON serialization natively, and every object audited in §1 already uses `@dataclass`. Recommend the `Resource` Protocol require `to_dict()`/`from_dict()` as the contract, implemented via existing dataclass introspection — not a new serialization framework. Minimal, and matches what's already there.

**Relationships:** generalize `KnowledgeEntry.contradicts[]`/`.supports[]` into a standard shape — a typed list of `(relation_type, target_id)` pairs. Note: "avoid cycles," as stated in the prompt's Phase 9, is actually wrong for this specific case and worth flagging as exactly the kind of assumption the prompt itself invited challenging — contradiction detection is *explicitly about* finding cycles (A contradicts B, B contradicts C, C contradicts A is a valid, meaningful state a Memory Curator needs to detect, not an error condition). Recommend: no cycles in *ownership* or *dependency* edges, cycles explicitly allowed and meaningful in *contradicts/supports* edges.

**Compatibility Review — every object, one verdict each:**

| Object | Verdict |
|---|---|
| `KnowledgeEntry` | Extend Resource (align field names to the Protocol; likely already close, minor renaming at most) |
| `Evidence` / `EvidenceSet` | Leave independent — wraps a Resource, isn't one |
| `Context` / `ContextBlock` / `ContradictionGroup` / `ProvenanceRecord` | Leave independent — deliberately decoupled projections, by design |
| `WorkerContext` | Leave independent — ephemeral parameter object |
| `SkillMetadata` / future `CapabilityMetadata` | Extend Resource when built |
| Future `Workflow` state | Extend Resource when built |
| Event objects | Leave independent — own category, already well-specified |
| Graph nodes | Leave independent — index entries, not resources |

**Migration cost:** small. One existing object (`KnowledgeEntry`) needs field alignment, not restructuring. Everything else needs no change at all. This is itself evidence relevant to §8.

---

## 8. On the Proposed K1.7–K1.11 Sequence

The prompt frames this session as the first of six pure-design sessions (K1.6 through K1.11) before any implementation. Worth stating plainly, because the prompt's own closing instruction explicitly invites challenging its assumptions: **this session's actual finding argues against that sequence, not for it.**

Two concrete reasons, not a general vibe:

**First**, the specific worry motivating K1.6 — divergent objects needing a unifying model — turned out, on inspection of the real fields, to be a small problem. One object (`KnowledgeEntry`) needs alignment. Everything else was already correctly *not* unified, on purpose, by the engineers who built it. If the flagship concern behind pausing for six design sessions resolves to "one dataclass needs some field renaming," that's weak evidence for five more sessions of the same kind before touching code.

**Second**, and more concretely: K1.7 ("Execution Runtime Specification"), K1.8 ("Capability Model"), K1.9 ("Workflow Model"), and K1.10 ("Worker Model") substantially overlap with sections K1.5 *already wrote* — §4 (Execution Model), §5 (Capability Architecture), and §7 (Worker Architecture) respectively. Re-running those as separate, deeper sessions before any of them has touched real implementation repeats the exact pattern both K1 and K1.5 independently identified as this repository's primary failure mode: sophisticated work produced in isolation, never brought into contact with the running system, while more sophisticated work gets produced on top of it. Applying that finding to the roadmap itself, not just to code, is the honest reading of "re-evaluate everything, don't assume previous conclusions remain valid."

**Recommendation:** treat K1.6 (this session) as closing the Resource Model question — it's answered, with evidence, above. Don't pre-schedule K1.7–K1.11 as a fixed sequence. Instead, let K2.1 (Execution Context + Worker invocation, already identified in both K1 and K1.5 as the single unblocking piece, and untouched by anything found in this session) proceed next. If building K2.1 surfaces a genuine open question that this session's Resource Model, or K1.5's Execution/Capability/Worker sections, didn't anticipate, that's real evidence — exactly what Law of Evidence over Assumption asks for — and it should be resolved as a targeted follow-up at that point, not pre-designed now against a hypothetical. This isn't a recommendation to skip rigor. It's a recommendation to let implementation contact be the source of the next real question, rather than manufacturing five more questions from continued paper review of a specification that's already twice been through exactly that process.

If there's a specific concern behind K1.7–K1.11 that isn't captured in this document or in K1.5, naming it directly would let it get resolved as a focused addendum rather than a full separate session.

---

## 9. Deliverables Summary

1. **Resource Architecture Document** — §§1–7 above.
2. **Resource Taxonomy** — §3: `Resource` as `Protocol`; four categories (Resource, wrapper, projection, ephemeral parameter object), not one universal base.
3. **Ownership Matrix** — §5.
4. **Lifecycle Specification** — §4: field required, values domain-specific per type, twelve-state universal machine explicitly rejected as unproven.
5. **Identity Specification** — §6: UUID convention, ID-reference-not-embedding rule made explicit.
6. **Provenance Integration Plan** — §6: existing `verification_history` slot respected, not redesigned, pending Session 5.9.
7. **Migration Plan** — §7: one object needs field alignment; everything else is already correctly shaped.
8. **Risk Analysis** — Advantage: minimal churn (Protocol-based, one object touched). Tradeoff: a `Protocol` gives weaker compile-time guarantees than an ABC — accepted deliberately, because the alternative (ABC inheritance) would force a change to `KnowledgeEntry`'s declaration that Law of Contract Stability argues against. Alternative considered: a shared `Resource` dataclass with composition (`KnowledgeEntry.resource: Resource` as a field) — rejected because it would require touching every existing call site that constructs a `KnowledgeEntry` positionally, a larger migration for no clear gain over the Protocol approach. §8 above is itself a risk finding: the proposed six-session sequence, evaluated against evidence, is the single largest identified risk to this session's own stated goal of minimizing future redesign.
9. **Updated Roadmap** — see §8: recommend K1.6 close the design question, K1.7–K1.11 not be pre-scheduled as a fixed block, K2.1 proceed next with any genuinely new question handled as a targeted follow-up if and when implementation surfaces one.

---

*K1.6 complete. No repository files modified. No implementation written beyond illustrative field lists. The Resource Model is specified; the roadmap recommendation in §8 is a finding of this session, not a refusal to continue it — the six-session sequence is a proposal worth deciding on explicitly rather than defaulting into.*
