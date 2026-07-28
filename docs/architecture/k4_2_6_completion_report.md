# Packet 04 — K4.2.6: Shared ValidationGate + Learning Wiring — Completion Report

**Status:** Completed
**Date:** July 28, 2026
**Architecture:** OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md §6 (Learning
Architecture), §7 (Cognitive Memory), §8 (Evolution), §11 (Event Integration), §12 (Data
Contracts), §13 (State Machines), §15 (K4.2.6 roadmap entry), §16 (Final Validation item 1).
**Module:** `core/cognitive/learning.py` (new)
**Dependencies:** Packet 03 (K4.2.5), completed and merged.

---

## §0. Architecture-vs-Repository Gap (documented, not silently resolved)

Following the precedent established in `k4_2_3_completion_report.md`, `k4_2_4_completion_report.md`,
and `k4_2_5_completion_report.md` — each of which found and recorded a gap between what the
architecture assumed already existed and what the repository actually contains, rather than
inventing around it — this packet found one:

**K4.2 §15's K4.2.6 roadmap entry lists "existing v4.3.9 Instinct->Skill pipeline" as a
dependency, and K4.2 §6 asserts Skills already reuse "the SkillOpt-style validation gate...
already adopted."** Neither claim holds:

- `grep -rn "SkillOpt"`, `grep -rln "instinct"`, and searches for `class SkillRegistry` /
  `class SkillOpt` across every `.py` file in `core/` returned nothing. The only hits anywhere in
  the repository are in `docs/archive/research/OCBRAIN_FUTURE_ARCHITECTURE.md`, an archived
  research document, where "Instinct -> Skill Learning" appears in a gap-analysis table as a
  **proposed future roadmap item** ("Add v4.3.9"), not built work.
- `core/learning/gate.py`'s `should_learn()` is a real, working gate — but it answers a different
  question. It scores *web-acquisition* chunks for the crawl → extract → normalize → score →
  quarantine → validate → consolidate → memory pipeline (semantic-similarity-to-topic plus an
  LLM-judge score). It has no held-out-improvement scoring, no contradiction check, and no
  `GovernanceKernel` integration. `core/learning/scorer.py`, `similarity.py`, and `evaluator.py`
  are its supporting pieces for that same pipeline, not a Skill-promotion gate.
- `core/skills/skill_interface.py` defines Skill *execution* (`BaseSkill`, `SkillMetadata`,
  input/output validation, retry/caching config) — there is no Skill promotion, creation, or
  registry path anywhere.

**Resolution:** `core/learning/gate.py` was deliberately **not** reused or merged into. It solves a
genuinely different problem (web-content quality, not candidate-vs-verified-entry promotion
gating), and force-merging two gates that answer different questions would itself introduce the
kind of hidden coupling this project's engineering standards (PI §20.4/§20.5) warn against.
Instead, `core/cognitive/learning.py` implements the promotion-gating policy K4.2 §6/§8 actually
specifies, from scratch, reusing only what's genuinely shared infrastructure
(`UnifiedMemory.write()`/`.search()`, `EventStream.append()`, `GovernanceKernel.evaluate_action()`
— all pre-existing, all unmodified except the one governance-vocabulary addition below).

`EvolutionGovernor.SELF_MODIFYING_ACTIONS` already contained `"skill_promote"`/`"skill_create"`
(pre-existing, unmodified by this packet) — meaning the *governance vocabulary* for Skill
promotion is real even though no production system produces those actions yet. This means
`ContentDomain.SKILL` is genuinely exercised by this packet's own tests (proving the shared gate
serves it identically to the other two domains — see `TestValidationGateSharedCodePath` and
`TestValidationGateEvolutionTier::test_skill_domain_already_registered`), but has no production
caller today. This is the same situation Packet 03 documented for Skill preconditions in
decomposition (`k4_2_5_completion_report.md`), and it is handled the same way: built correctly for
when a real caller arrives, not stubbed out or fabricated around.

This did not rise to a governance-directive-triggering "architectural deficiency" requiring a
citation-and-approval amendment (`OCBRAIN_IMPLEMENTATION_GOVERNANCE_DIRECTIVE.md` §14): the
packet's actual scope — one shared, domain-parameterized gate function — does not require a real
Skill Runtime to exist, only that the gate be *capable* of serving that domain, which it is and
which is now proven by test.

---

## 1. Architecture Compliance Matrix

| Architecture Requirement (K4.2 §) | Implementation Location | Status |
|---|---|---|
| §6/§16.1: one shared ValidationGate fn, parameterized by content-domain | `validation_gate()` | Implemented |
| §12: `CognitiveDecision` dataclass | `CognitiveDecision` | Implemented (fields exactly as specified) |
| §12: `LearningRecord` dataclass | `LearningRecord` | Implemented (+ `lifecycle_state`, see §3 below) |
| §13: Learning lifecycle (observed→accumulated→candidate→gated→[promoted\|rejected]) | `LearningLifecycle` + `lifecycle_state` transitions in `validation_gate()` | Implemented |
| §11: `cognitive.pattern_learned` event | Emitted in Learning-tier path | Implemented |
| §11: `cognitive.ontology_evolved` event | Emitted on Evolution-tier promotion | Implemented |
| §8: Learning tier — "existing memory_write gate only, routine" | Direct `memory.write()`, no held-out/contradiction check | Implemented |
| §8: Adaptation tier — "accept only on strict, held-out improvement" | `held_out_score`/`baseline_score`/`DEFAULT_SCORE_FLOOR` check | Implemented |
| §8 promotion criteria: contradiction-check against Graph Memory before write | `_find_contradiction()` (see §2 below re: what "Graph Memory" check was actually available) | Implemented |
| §8: Evolution tier — `EvolutionGovernor.SELF_MODIFYING_ACTIONS`, "never automatic" | `requires_approval=not hitl_approved` (always True absent explicit override); `EvolutionGovernor.evaluate_action()` | Implemented |
| §15 dependency: "existing v4.3.9 Instinct->Skill pipeline" | N/A — does not exist | Gap documented (§0 above), not fabricated |
| §6: "SkillOpt-style validation gate... already adopted" | N/A — does not exist; `core/learning/gate.py` is unrelated | Gap documented (§0 above) |
| Explicitly forbidden: three parallel gate implementations | Single `validation_gate()` function, tested across all 3 domains | Implemented (proven by `TestValidationGateSharedCodePath`) |
| Explicitly forbidden: new memory layers | No new layer introduced; L0-L4 untouched | Verified (`TestArchitectureCompliance::test_no_new_memory_layer_introduced`) |
| Explicitly forbidden: new governors | No new `Governor` subclass; one vocabulary addition to existing `EvolutionGovernor` | Verified (`TestArchitectureCompliance::test_no_new_governor_class_defined`) |
| Completion criterion: recurring-pattern fixture promotes only after clearing gate | `TestValidationGateAdaptationTier::test_promotes_only_after_clearing_gate` | Implemented & tested |
| Completion criterion: contradiction fixture blocked pre-promotion | `test_contradiction_fixture_blocked_pre_promotion` (Adaptation) + `test_contradiction_blocks_before_governance_is_consulted` (Evolution) | Implemented & tested |
| Completion criterion: same gate fn serves all 3 domains via one code path | `TestValidationGateSharedCodePath` (parametrized across all 3) | Implemented & tested |
| Completion criterion: all existing tests pass | Full regression: 924/924 (884 baseline + 40 new); see §5 | Verified |

---

## 2. Design Decisions Flagged as Implementation Judgment

Per this project's standing practice (see Packets 01-03's own "Design Decisions" sections), the
following required judgment beyond what §12's explicitly-illustrative data contracts specify, and
are recorded here rather than silently decided:

1. **`LearningRecord.lifecycle_state` is not in §12's illustrative field list, but is added.** §12's
   preamble states its fields are "illustrative only... not frozen implementation schemas," and
   §13 requires the Learning lifecycle to be tracked *somewhere* — `LearningRecord` is the only
   shape §13 attaches it to. The lifecycle *states themselves* are restated exactly as specified in
   `LearningLifecycle`, not renamed or redefined.

2. **No existing primitive checks an unwritten candidate against the graph before write.**
   `GraphEngine.find_contradictions()` and `UnifiedMemory.find_contradictions()` are both
   parameterless whole-graph sweeps over nodes *already indexed* in the graph (confirmed by
   reading both) — they detect contradictions the graph backend already flagged between existing
   entries, which is a different operation from "would this new candidate contradict something
   already verified." `MemoryGovernor.detect_contradiction()` is also not usable for this: it is an
   explicit placeholder (`# Logic to be expanded in Phase 5`) that always returns `False`. This
   packet implements the pre-write check K4.2 §8 requires directly in `_find_contradiction()`,
   reusing the existing hybrid `UnifiedMemory.search()` (K4.2 §7: "existing hybrid BM25 + semantic
   + RRF... unchanged" — no new retrieval built) plus a conservative negation-cue heuristic
   mirroring `core.cognitive.planner._detect_contradictions`' documented approach and stated
   limits (only clear, provable contradictions; subtler conflicts are out of scope for a
   deterministic check, exactly as that precedent frames its own limits).

3. **The contradiction check fails closed.** If `UnifiedMemory.search()` itself raises (as opposed
   to succeeding and returning no results), `_find_contradiction` raises `ContradictionCheckError`
   and `validation_gate` treats this as a rejection, not a pass-through. K4.2 §8 names the
   contradiction check as a precondition of promotion, not a best-effort courtesy; an inconclusive
   check should block, not silently permit, a write.

4. **Evolution-tier promotion never completes synchronously unless `hitl_approved=True` is
   explicitly supplied.** `EvolutionGovernor.evaluate()` only escalates when
   `action.requires_approval` is `True`; if a caller passed `False`, it would auto-approve (existing
   behavior, unmodified). Because K4.2 §8 states Evolution is "never automatic,"
   `validation_gate()` always computes `requires_approval=not hitl_approved` — never a bare,
   caller-supplied boolean — so every call that does not explicitly assert prior human approval is
   escalated, never silently promoted. `hitl_approved` is not a HITL-approval workflow (no queue,
   no persistence, no UI is built here); it is the single explicit seam a future approval surface
   would use once a human has actually approved a specific candidate. This mirrors Packet 03's own
   precedent of building a piece standalone and leaving the actual consuming workflow for a later,
   unnamed packet, rather than fabricating one now.

5. **Evolution-tier requests for an `action_type` not registered in
   `EvolutionGovernor.SELF_MODIFYING_ACTIONS` are rejected outright, not routed to governance.**
   Without this guard, an unrecognized action_type would fall through `EvolutionGovernor.evaluate()`
   to `APPROVE` regardless of `requires_approval` — a latent governance-bypass risk for any future
   fourth content-domain added without a matching vocabulary update. `ContentDomain.USER_MODEL` at
   Evolution tier is rejected today for exactly this reason (`"user_model_promote"` is not yet
   registered — that is Packet 05's addition to make once User Cognitive Model promotion is real),
   and this is verified by a dedicated test rather than left as an assumption.

6. **Adaptation-tier promotions emit no dedicated event.** K4.2 §11's Event Integration table names
   `cognitive.pattern_learned` (Learning) and `cognitive.ontology_evolved` (Evolution) — no third
   event is named for Adaptation. This packet's own Scope list names exactly these two events, so a
   third was not invented. Adaptation-tier writes remain event-sourced via
   `UnifiedMemory.write()`'s own existing archive-event mechanism at the memory layer.

7. **`action_type` is derived as `f"{content_domain}_{'promote'|'adapt'|'learn'}"`.** This exactly
   reproduces the pre-existing `"skill_promote"` string with no lookup table, and produces
   `"intent_ontology_promote"` for the domain this packet actually exercises — the one new entry
   added to `SELF_MODIFYING_ACTIONS`. `"user_model_promote"` is deliberately *not* added (see point
   5 and `k4_2_4_completion_report.md`'s precedent against unused speculative vocabulary).

---

## 3. Files Modified

### New
- `core/cognitive/learning.py` — `LearningTier`, `ContentDomain`, `LearningLifecycle`,
  `CognitiveVerdict`, `DEFAULT_SCORE_FLOOR`, `ContradictionCheckError`, `CognitiveDecision`,
  `LearningRecord`, `_is_textual_contradiction`, `_find_contradiction`, `validation_gate`.
- `tests/core/cognitive/test_learning.py` — 40 tests across dataclass shape, the contradiction
  heuristic (unit + integration), input validation, all three tiers, the cross-domain shared-path
  requirement, and architecture compliance.
- `docs/architecture/k4_2_6_completion_report.md` — this report.

### Modified
- `core/governance/governance_kernel.py` — added `"intent_ontology_promote"` to
  `EvolutionGovernor.SELF_MODIFYING_ACTIONS` (one line, plus an explanatory comment).
  `"skill_promote"`/`"skill_create"` pre-existed and are unchanged. No other change to this file.
- `docs/architecture/IMPLEMENTATION_TRACKER.md` — Packet 04 entry marked Completed with
  files/tests/notes; top-level summary block (Completed/Waiting lists, date, active-packet count)
  synchronized, since it had already drifted out of date before this packet (it still listed only
  Packet 01 as completed despite Packets 02-03's detailed sections below already saying
  Completed).
- `docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md` and its identical duplicate
  `docs/architecture/k4_3_implementation_transition.md` — Packet 04 status marker updated from
  `NOT STARTED` to `COMPLETED`, keeping both copies synchronized (per Packet 02's established
  precedent of treating these two files as a kept-in-sync pair).

### Deleted
- None.

---

## 4. Interface Stability Audit

All exported names are new (`core/cognitive/learning.py` did not exist before this packet), so
there is no backward-compatibility surface to preserve from a prior version. Checked instead for
internal consistency with Packets 01-03's conventions:

- Tier/domain/lifecycle/verdict constants use the plain-class-with-string-attributes style
  established by `ConstraintKind`/`ConstraintRelation`/`ExecutionPlanLifecycle`/`PlannerStatus` in
  `core/cognitive/planner.py`, not `enum.Enum` (which `core/skills/skill_interface.py` uses
  elsewhere in the codebase for a different module) — matching the closer, same-package precedent.
- `validation_gate()` is keyword-only (`*`), matching `plan()`'s calling convention in
  `planner.py`.
- Dependency injection (`memory`, `governance`, `event_stream`, each `Optional[...] = None`,
  falling back to `get_unified_memory()`/`get_governance_kernel()`/`get_event_stream()`) exactly
  mirrors the `event_stream = event_stream or get_event_stream()` pattern already used in
  `intent.py` and `planner.py`.
- `EvolutionGovernor.SELF_MODIFYING_ACTIONS` remains a plain `set[str]`; no test in
  `tests/test_k2_4_governance.py` asserts its exact contents (confirmed by search before editing),
  so the addition is non-breaking.
- `GovernanceAction`/`GovernanceResult`/`GovernanceVerdict`/`EvolutionGovernor`/`GovernanceKernel`
  field names and `evaluate_action()`'s signature were read directly from
  `core/governance/governance_kernel.py` before use, not assumed; all call sites in
  `core/cognitive/learning.py` match the real signatures exactly.
- `UnifiedMemory.write()`/`.search()` parameter names were likewise read directly before use.

---

## 5. Validation Results

- **`tests/core/cognitive/test_learning.py`:** 40/40 passing.
- **`tests/test_k2_4_governance.py`** (the suite most directly affected by the
  `governance_kernel.py` change): 48/48 passing — identical to the pre-change baseline.
- **`tests/core/cognitive/test_planner.py`** (unmodified; regression-checked since both modules
  live in the same package): 115/115 passing — identical to the pre-change baseline.
- **Full repository regression:** 924/924 passing. Pre-existing baseline was 884/884 with 4
  collection errors (`tests/test_break_concurrency.py`, `tests/test_break_empty_db.py`,
  `tests/test_break_security.py`, `tests/test_system_ctrl.py`, all failing at
  `modules/base.py: import chromadb`, `chromadb` not being installed in this sandbox — the exact
  same 4 files documented as a pre-existing, unrelated gap in `k4_2_3_completion_report.md`). Same
  4 errors, same cause, unrelated to this packet, present before any change in this session. 40 new
  tests, zero regressions: 884 + 40 = 924.
- **Lint:** `pyflakes` clean (zero warnings) on `core/cognitive/learning.py`,
  `tests/core/cognitive/test_learning.py`, and `core/governance/governance_kernel.py`.
- **Architecture verification:** see Compliance Matrix (§1) and Design Decisions (§2) above; three
  dedicated `TestArchitectureCompliance` tests assert no new `Governor` subclass, no new memory
  layer, and that `requires_approval` is always derived from `hitl_approved` (never a bare,
  independently-settable boolean) via direct source inspection, not just behavioral testing.
- **Governance verification:** `EvolutionGovernor.SELF_MODIFYING_ACTIONS`'s addition verified
  against the real `GovernanceKernel`/`EvolutionGovernor` (not a mock) in
  `TestValidationGateEvolutionTier`, including the "never automatic" default-escalation path, the
  HITL-approved completion path, and the unregistered-action-type rejection path for
  `ContentDomain.USER_MODEL`.
- **Documentation verification:** `IMPLEMENTATION_TRACKER.md`, both transition-doc copies, and this
  report are mutually consistent (all state Packet 04 Completed, July 28, 2026, same file list).

---

## 6. Cross-Packet Contract (for Packet 05 and later)

Packet 05 (K4.2.7, User Cognitive Model) depends on this packet and can rely on:

- `validation_gate(tier=..., content_domain=ContentDomain.USER_MODEL, ...)` is already
  domain-agnostic and requires no changes to `core/cognitive/learning.py` to accept
  `ContentDomain.USER_MODEL` at Learning or Adaptation tier — those paths never touch
  `EvolutionGovernor` and work identically to the other two domains today (proven by
  `TestValidationGateSharedCodePath`, which already exercises `ContentDomain.USER_MODEL`).
- At **Evolution** tier specifically, `ContentDomain.USER_MODEL` will be rejected until Packet 05
  adds `"user_model_promote"` to `EvolutionGovernor.SELF_MODIFYING_ACTIONS`
  (`core/governance/governance_kernel.py`) — a one-line addition following the exact precedent this
  packet set for `"intent_ontology_promote"`. No other change to `core/cognitive/learning.py` is
  required for this to start working; `action_type = f"{content_domain}_promote"` already computes
  the correct string.
- `LearningRecord`/`CognitiveDecision` are stable, importable data contracts
  (`from core.cognitive.learning import LearningRecord, CognitiveDecision, ...`).
- A genuine HITL-approval-completion workflow (turning an `ESCALATE`/`GATED` record into an
  actual approved promotion at scale, beyond this packet's single explicit `hitl_approved` seam) is
  not built by this packet and is not assigned to any packet in the current roadmap
  (`OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`) — flagged here as an open item for whichever future
  packet or human governance process ends up owning it, rather than silently assumed to already
  exist.

---

## 7. Final Checklist

```
Packet Review Result
Architecture Compliance         PASS
Implementation Completeness     PASS
Interface Stability             PASS
Documentation Synchronization   PASS
Test Suite                      PASS
Ready for Integration           YES
Architecture Drift Detected     NO
Breaking Changes Introduced     NO
```
