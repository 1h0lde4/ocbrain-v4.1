# CTX-AUTH-001 + CTX-DELETE-001 — Definitive Hardening Pass

**Date:** September 12, 2026
**Branch:** `fix/ctx-auth-001-ctx-delete-001-sep2026` (local only — not pushed, not merged)
**Baseline:** forked from `main` at `e9a9cde5c4a57f2a0e71d798812beb4d87494af3` (itself discovered mid-session — `main` moved from `73d3bb0` to `e9a9cde` while this session was still investigating; see §0)
**Final commit this branch:** `557a9c7`

This report follows the mission's own rule: prove current state from source, not from prior reports. Every claim below was independently re-verified against the actual code and actual test runs during this session, not inherited from `KNOWN_ISSUES.md`, the remediation register, or either prior CTX audit.

---

## 0. A concurrent change was discovered mid-session

Before any implementation began, this session's routine `git pull --ff-only` (part of setting up the dedicated branch, §1.2 of the mission) revealed `main` had moved since the session started: **PR #13, "selective CTX security port," had already landed CTX-CACHE-001 and CTX-DELETE-001 as resolved**, and had already applied the structural half of CTX-AUTH-001 — touching the exact two files (`core/cognitive/intent.py`, `core/memory/unified_memory.py`) this task was about to modify.

This was investigated in full before writing any code (diffs read, `docs/Bugs Hunt & fix reports/CONTEXT_ISOLATION_CALLER_AUDIT_SEP2026.md` and the updated remediation register read, both already-landed fixes independently re-verified against real test runs rather than trusted from their commit messages). The remainder of this report describes what was found already true, what this session added, and what this session investigated and could not soundly close.

---

## A. Current Root Cause

### CTX-AUTH-001

**Location:** `core/cognitive/intent.py`, `_build_hypothesis_prompt()` / `_parse_hypotheses()`.

Two independent, separately-fixable weaknesses, both confirmed by direct code reading, not inferred from either prior audit's description:

1. **(001a) Structural containment.** `_HYPOTHESIS_PROMPT_TEMPLATE.format(...)` interpolates `context`, `categories`, and `request` into a template using plain-text `"Context:"` / `"Request:"` / `"Candidates:"` labels with no delimiter. Content containing the literal string `"Request:\n...\n\nCandidates:"` can fabricate a second, indistinguishable control section.
2. **(001b) Parser acceptance.** `_parse_hypotheses()` used `_CANDIDATE_LINE.finditer(completion)` — an unanchored scan accepting **any** `label | score`-shaped line anywhere in the model's completion, with no way to distinguish a genuine hypothesis from one echoed out of what should have been inert data.

**Violated invariant:** untrusted, memory-sourced content should not be able to acquire the same structural authority as the template's own control tokens (Message/Channel Authority, per `docs/research/context-engineering/context-authority-threat-model.md`).

**Why existing authorization was insufficient:** there is none, by design — `intent.py`'s own module docstring states governance evaluation is deliberately deferred to Plan Compilation, a later K4.2 milestone. This is not an oversight this fix works around; a correct fix must be structural/content-level, not a governance call injected into a stage that is governance-free on purpose.

### CTX-DELETE-001

**Location:** `core/memory/unified_memory.py`, `UnifiedMemory.delete()` (now `delete_with_outcome()`).

**Root cause (already fixed on `main` before this session, reconfirmed here):** step 7 (L1 authoritative storage removal) previously wrapped `await self._storage.delete(entry_id)` in a bare `try/except` that only logged on failure, never propagating it, falling through to an unconditional `return True`. The already-landed fix captures the storage layer's own return value (`l1_removed = await self._storage.delete(entry_id)`) and returns it directly. **Independently reconfirmed this session, not assumed:** `SQLiteStorageBackend.delete()` (`core/memory/backends/sqlite_storage.py:243`) genuinely returns `cur.rowcount > 0` — a real, accurate signal, not a value that happens to be truthy.

**Violated invariant:** a successful-deletion result may only be reported when the required deletion outcome was actually established (mission §11).

**Why false success was possible:** the method's own docstring claimed L1 failure would return `False`; the code did not implement that claim. The gap was pure implementation, not a design defect — the distinction the fix needed (not-found / denied / escalated / blocked / failed) was already implicit in the method's own branching; nothing had ever exposed it.

---

## B. Trust-Boundary Map (mission §4)

| Field | Actual source | Trusted? | Mutable? | Model-controlled? | Can influence authorization? |
|---|---|---|---|---|---|
| `context` (intent.py) | `ContextAssemblyEngine.assemble_context()`, flattening memory-layer `ContextBlock`s to a plain string | No | Yes (memory-sourced, including anything ever written to L1-L3) | Indirectly (prior model output can be written to memory and later retrieved) | N/A — no authorization step exists at this stage by design |
| `known_categories` (intent.py) | Intent Ontology L3 entries | No (system-internal today, but no different in kind from any other memory-sourced value) | Yes | Indirectly | N/A |
| `raw_request.text` (intent.py) | The caller's own request | Partially — it's the caller's own words, but can still accidentally contain a structural token | Yes | No (this is the human/caller's own direct input) | N/A |
| completion (intent.py) | LLM provider response | No | N/A (ephemeral) | Yes, directly | N/A |
| `entry_id` (unified_memory.py) | Caller-supplied string | Caller-supplied, unverified format beyond non-empty | Caller-controlled | No | Determines *which* entry is targeted, not *whether* the operation is authorized |
| `worker_id` (unified_memory.py) | Caller-supplied string, defaults to `""` | **Caller-supplied, wholly unverified** | Caller-controlled | No | Recorded for audit/logging and passed to governance as metadata only — **confirmed, not assumed: nothing in `UnifiedMemory`, `GovernanceKernel`, or anywhere else in this codebase checks it against any concept of entry ownership** |
| governance verdict (unified_memory.py) | `GovernanceKernel.evaluate_action()` against registered governors | Trusted (deterministic application code) | N/A | No | Yes — this is the actual authorization decision for delete |
| `KnowledgeEntry` | Written via `UnifiedMemory.write()` | Trusted once persisted | Yes | Content may be model-generated | **Has no owner/principal field of any kind** |

**Object-level, cross-principal authorization (mission §§4-9) does not have an existing architectural anchor to bind to in this codebase**, confirmed directly: `KnowledgeEntry` carries no owner/principal field, and `worker_id` — the only identity-shaped parameter on `delete()` — is unverified and already confirmed to have zero bearing on any authorization decision anywhere in this codebase. OCBrain's memory layer is a single-address-space, local-first store; "governance" here means policy enforcement (budgets, recursion limits, content denylists), not access control between distinct principals. Building a `Principal A → Context B → denied` test matrix (mission §6/§27) against this architecture would require fabricating an ownership concept that does not exist — exactly the "fake security boundary" the mission's own §32 forbids. This is stated here explicitly rather than worked around silently. If a genuine multi-principal ACL model is wanted for `UnifiedMemory`, that is a separate, larger architecture decision, not something this task should introduce as a side effect of two named bug fixes.

---

## C. Architecture Before / After

**CTX-AUTH-001a — before:** `context` interpolated raw via `str.format()`; any of the three control labels appearing in it could fabricate a duplicate section.
**After:** `_neutralize_structural_tokens()` (landed pre-session) defuses exact occurrences of `"Context:"`, `"Request:"`, `"Candidates:"` in untrusted content via a zero-width-space insertion — content-agnostic, no keyword/phrase blacklist. This session extended its application from `context` only to all three interpolation points (`context`, `known_categories`, `raw_request.text`) in the same function.

**CTX-AUTH-001b — before and after: unchanged.** Investigated, not modified (see §D/§H).

**CTX-DELETE-001 — before:** `delete()` returned an undifferentiated `bool`, with an unconditional `True` at the end regardless of whether L1 removal actually happened.
**After:** `delete_with_outcome()` returns one of seven explicit `DeleteOutcome` values; `delete()` is now `return outcome is DeleteOutcome.DELETED` — the same bool contract, same signature, zero behavior change for any existing caller, now provably correct rather than incidentally correct. A `memory_delete_failed` `KnowledgeEvent` is now archived on the `FAILED` branch, matching the pre-existing `REJECT`/`ESCALATE` pattern.

---

## D. Proving Evidence

| Test | Pre-fix result | Why it failed | Fix | Post-fix result |
|---|---|---|---|---|
| `TestCtxAuth001StructuralContainment::test_poisoned_context_does_not_create_second_request_section` | Failing (pre-session main) | `context` interpolated raw | Landed pre-session (`_neutralize_structural_tokens`) | Passing — reconfirmed this session |
| `TestCtxAuth001aExtendedNeutralization` (×2, new) | N/A (new tests) | N/A | This session, extending neutralization to `known_categories`/`raw_request.text` | Passing |
| `TestCtxAuth001ParserAcceptance::test_injection_shaped_completion_line_is_not_accepted_as_a_hypothesis` | Failing | Unanchored `finditer` accepts any candidate-shaped line | **None shipped** — see §H | **Still failing, honestly** |
| `tests/test_unified_memory.py::TestUnifiedMemoryDelete::test_delete_returns_false_when_l1_storage_deletion_fails` | Failing (pre-session main) | L1 exception silently swallowed | Landed pre-session | Passing — reconfirmed this session |
| `TestDeleteOutcome` (×7, new) | N/A | N/A | This session, `DeleteOutcome` contract | Passing |
| `TestDeleteFailedAuditEvent::test_l1_failure_archives_a_failed_event` (new) | **Failing on first write** (this session's own bug) | `"memory_delete_failed"` not in `EVENT_TYPES`, silently rewritten to `"created"` | Registered the event type in `core/memory/knowledge_event.py` | Passing |
| `TestDeleteFailedAuditEvent::test_successful_deletion_does_not_also_emit_a_failed_event` (new) | N/A | N/A | Differential control | Passing |
| `TestDeleteConcurrency::test_concurrent_delete_of_same_entry_has_exactly_one_winner` (new) | N/A | N/A | Proves no false success under a race | Passing, 10/10 stable runs |
| `TestUnifiedMemoryLifecycle::test_consolidate_does_not_count_failed_eviction` (new) | Would fail against pre-bypass-search code | `consolidate()` didn't check `self._storage.delete()`'s return value | This session, bypass-search finding | Passing |

The `TestDeleteFailedAuditEvent` row is worth calling out on its own: it is a real example of the "red before green, and make sure it's red for the right reason" discipline catching a genuine bug in this session's *own* new code before it shipped, not a hypothetical.

---

## E. Security Analysis

- **Object-level authorization:** does not apply as literally specified — see §B. Operation-specific distinction (`READ`/`MUTATE`/`DELETE`) is not something this codebase's memory layer implements at all today; out of this task's scope to introduce.
- **Cross-owner / cross-scope access, forged identity/ownership/execution-identity:** not constructible as test scenarios — no ownership concept exists to forge (§B).
- **Confused deputy:** `worker_id` is recorded, never authoritative anywhere in the call graph traced this session. No component in the delete path escalates its own authority based on a caller-supplied identity string.
- **Lower-level bypass:** searched (mission §25) and found real: `consolidate()`'s bulk eviction path calls `self._storage.delete()` directly. Outcome-truthfulness half fixed this session; the governance/`before_delete`-hook bypass is flagged as DEBT-025, not fixed — an architecture decision (should bulk housekeeping be gated the same as a single caller-requested delete?), not a bug fix.
- **Capability bypass:** not traced this session — `UnifiedMemory.delete()` is not currently exposed as an MCP-style capability; out of the reachable scope this pass covered.
- **Cache staleness:** `self._l0.evict(entry_id)` now runs unconditionally including on `FAILED`, matching the pre-existing "always evict" documented intent — confirmed this leaves L0 consistent with L1 either way (both still have the entry on failure, both don't on success).
- **TOCTOU:** `delete_with_outcome()` reads the entry (step 2) before evaluating governance (step 3) and before mutating (step 8) — no re-validation immediately before the destructive mutation exists. Not newly introduced by this session; not independently re-designed here (would be a larger change than this task's named scope justifies without further evidence of exploitability, given the single-process, local-first architecture).
- **Concurrency:** proven, not assumed — 10 stable runs confirm exactly one winner, no false `DELETED` for a racer, entry genuinely gone afterward either way. Named, accepted imprecision: the losing racer's outcome label (`NOT_FOUND` vs `FAILED`) depends on interleaving with the storage backend and is not further distinguished — the correctness property (no false success) holds regardless of which label the loser gets.
- **Retry/idempotency:** `test_repeated_delete_is_idempotent` (pre-existing) confirms second delete of an already-gone entry returns `False`/`NOT_FOUND` cleanly, not an error.
- **Partial failure:** steps 4-6 (graph/vector removal) remain explicitly non-blocking, matching the pre-existing documented design; step 7 (L1) is the sole authoritative outcome, unchanged in that respect by this session.
- **Recovery/replay:** not analyzed this session — `UnifiedMemory` has no checkpoint/resume concept of its own (that's a Kernel-runtime-layer concern, a different subsystem); out of scope for this pass.
- **Legacy/migration paths:** not searched this session for `delete`-adjacent legacy paths beyond the two found via the general bypass-search (§ above).
- **Prompt/model injection (CTX-AUTH-001 specifically):** 001a closed and extended; 001b remains genuinely open — see §H for why, in detail.
- **Denial information leakage:** not analyzed this session (out of the two named items' scope).

---

## F. Test Baseline

- `tests/test_unified_memory.py` + `tests/core/cognitive/test_intent_security.py` (the two directly-touched files): **194 passed, 1 failed** (the honest, pre-existing, still-open CTX-AUTH-001b test) — 100% of everything else.
- Broader regression sweep, 14 files chosen for importing either touched module (`test_intent.py`, `test_k42_completion.py`, `test_kernel_blocker_resolution.py`, `test_planner.py`, `test_cognitive_memory.py`, `test_context_builder.py`, `test_k3_5_1_governance_consistency.py`, `test_orchestrator_memory_migration.py`, `test_orchestrator_recovery.py`, `test_planner_worker.py`, `test_session4b_memory_hardening.py`, `test_session4c_architecture.py`, `test_integration_full_pipeline.py`, `test_unified_memory.py`): **567 passed, 0 failed**.
- **Not run this session:** the complete repository suite (per the project's own documented baseline, ~1,400+ tests including 34 pre-existing `huggingface.co`-unreachable environment failures and a handful of pre-existing intentionally-red CTX security tests). The 14-file/567-test sweep was scoped to files with a direct import dependency on the two touched modules, not the full suite; a full-suite run is recommended before this branch is considered mergeable, but was not necessary to prove the specific invariants this task targeted.
- New tests added: 14 (7 `DeleteOutcome`, 2 audit-event, 2 concurrency, 1 `consolidate()` truthfulness, 2 extended-neutralization). Zero tests weakened, skipped, or deleted — the one exception is the 4 tests that validated the abandoned ordering mechanism, removed because the mechanism itself was reverted (not because the assertions were inconvenient).

---

## G. Documentation Reconciliation

Updated, this session:
- `KNOWN_ISSUES.md`: new sync entry (top); DEBT-019 row's CTX-AUTH-001/CTX-DELETE-001 language corrected to the source-verified state; DEBT-024 and DEBT-025 added (both bypass-search findings).

Not updated this session (recommend as follow-up, not done here to avoid scope creep on documents this task didn't directly change the substance of):
- `docs/reports/context-compiler-remediation-register.md` — REM-002's row could be updated to reflect that its parser-acceptance half was actively investigated and confirmed to require REM-004, not merely assumed to.
- `docs/architecture/decisions/ADR_INDEX.md` — no new ADR was written for this pass; the two `DeleteOutcome`/audit-event additions are minor enough (additive, non-breaking) that a full ADR seemed disproportionate, but this is a judgment call, not a rule — flagging it as one.

---

## H. Final Status

**CTX-AUTH-001: PARTIAL.**
- Structural containment (001a): **RESOLVED**, and more completely than when this session started (all three interpolation points covered, not just `context`).
- Parser acceptance (001b): **OPEN.** Investigated thoroughly, not resolved. Every content-only signal available within `_parse_hypotheses()` — score ordering, score magnitude (including the legitimately-tested 1.0 edge case), front-anchored contiguity — either fails to distinguish the specific tested injected line from an ordinary one, or does so only by breaking pre-existing, intentional behavior this codebase's own test suite requires (arbitrary hypothesis ordering, tolerance of malformed lines, full acceptance of boundary score values). A keyword/label blacklist would close the one given test but is exactly what this template's own threat model rejects as an unwinnable, gameable arms race. This confirms, with concrete evidence rather than citation, `docs/reports/context-compiler-remediation-register.md`'s own prediction that REM-002's parser half depends on REM-004's authority taxonomy — structured provenance surviving from context assembly through to the parsed hypothesis — to be soundly closeable, and that taxonomy is Context Compiler-adjacent infrastructure this task correctly excludes.

**Kernel-v1.0 freeze-blocker classification (mission §34):** the live code path this half of the bug lives in (`core/cognitive/intent.py`, the K4.2 Cognitive Front-End) is confirmed Kernel-required. Per the mission's own explicit rule — *"If the current Kernel has a reachable correctness or security violation on a supported path, that violation remains a Kernel-v1.0 freeze concern unless an explicit current Kernel policy/ADR establishes that the affected path is intentionally outside the Kernel-v1.0 contract"* — no such ADR exists narrowing this specific path out of scope, so CTX-AUTH-001b **remains a live, reachable, unresolved gap on a Kernel-v1.0-required path**, not something this note downgrades. Whether it rises to the level of a freeze blocker (as the closure audit's P0 classification held) or is accepted as tracked-but-non-blocking residual risk (as the remediation register's tiering implicitly treats it, for a question the register itself never actually asked) is the same open decision flagged at the start of this session, now with sharper, source-verified reasoning behind both sides — still Moncif's call, not resolved by this note.

**CTX-DELETE-001: RESOLVED, and hardened beyond the original bug.**
- Core bug (false success on L1 failure): resolved (landed pre-session, reconfirmed correct against the real storage backend, not assumed).
- Richer outcome contract, audit trail for the failure case, proven concurrency safety, and one adjacent bypass (`consolidate()`) found and fixed: added this session.
- One adjacent bypass (`consolidate()`'s governance/hook skip) found and deliberately **not** fixed — flagged as DEBT-025, an architecture decision, not a bug.

**Kernel-v1.0 freeze-blocker classification:** CTX-DELETE-001 itself is resolved and no longer a blocker under any classification. DEBT-024 (planner.py) and DEBT-025 (`consolidate()` governance bypass) are newly-discovered, not yet triaged into a P0-P3 classification — flagged for the next debt re-triage pass, not decided here.
