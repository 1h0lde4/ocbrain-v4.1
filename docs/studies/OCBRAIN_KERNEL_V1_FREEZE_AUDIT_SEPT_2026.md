# OCBrain Kernel v1.0 — Freeze Audit (September 6, 2026)

**Audited against:** commit `7375cc0` on `main`. **Method:** direct source reading and fresh test execution throughout — no claim below rests on a prior report's word alone where the underlying code was available to check directly. Where something wasn't independently re-verified this session, it's marked as such rather than presented as confirmed.

**Sequencing note:** per Moncif, this Kernel-completion sequence followed the existing roadmap (Watchdog → DEBT-003 → this audit), not the alternative ordering (Verification/Critic/Evidence first) proposed at the start of this session. Verification/Critic/Evidence integration remains explicitly post-freeze/post-C-MoE, as it has been throughout this project's history — this audit does not revisit that decision.

---

## 1. Baseline

Full suite: **1,367 passed / 39 failed**, run fresh at the start of this audit. All 39 failures classified by hand, not assumed from a prior count:
- 34 → `huggingface.co` unreachable (outside this sandbox's network allowlist — an environmental constraint, independently confirmed earlier this session by isolating a failing file and observing the literal `OSError`).
- 5 → intentionally-red security-regression tests: CTX-AUTH-001 (2 tests), CTX-SCOPE-001, CTX-CACHE-001, CTX-DELETE-001. All still red exactly as designed.
- 0 unexplained.

Working tree clean, `main` at `7375cc0`, matches `origin/main` (confirmed via fetch immediately before this audit began).

## 2. Status of every previously-identified blocker

| Blocker | Status | Evidence |
|---|---|---|
| Scope/identity linkage (`WorkflowNode`/`WorkflowDefinition` ↔ `operation_id`) | **Resolved** | `ADR-KERNEL-01` (Aug 29), re-confirmed Aug 31, unaffected by any work since — confirmed by direct grep this session: `root_operation_id`/`attempt_id` still present and threaded as that ADR describes. |
| Embedded ADR-001 (`WorkerContext` deprecated) vs. all workers taking `WorkerContext` | **Resolved** | Same ADR. `ExecutionRuntime.invoke()` passes `ExecutionContext` directly; confirmed no regression to this by this session's own two large `core/workflow/runtime.py` changes (DEBT-016, DEBT-003), neither of which touched `execution_runtime.py`. |
| DEBT-016 — two unreconciled watchdog/progress-monitor implementations | **Resolved this session** | `ADR-KERNEL-02`. Two real bugs found and fixed during the work itself (budget-construction bug, self-feedback bug), both caught by this session's own tests before commit. |
| DEBT-003 — no checkpoint/resume, no workflow durability across restart | **Resolved this session** | `ADR-KERNEL-03`. One real bug found and fixed during the work itself (traversal short-circuit conflating "already visited" with "already done"), caught by this session's own tests before commit. Cross-process durability proven with two genuinely separate `WorkflowRuntime`/`SQLiteEventStore` instances sharing only a file. |

All four of the items this and prior sessions have treated as Kernel v1.0 blockers are now resolved. This is not, by itself, sufficient for a `FREEZE_READY` verdict — see §5.

## 3. Full current debt triage

Every item currently open in `KNOWN_ISSUES.md`, classified P0–P3. This is the first time this exact table has had every open item passed through this specific framework in one pass, rather than only the items a given session happened to be working on.

**P0 (Kernel blocker — would need to be fixed before freeze):**
- *(see §5 — DEBT-020, false completion, is the one live candidate; not placed in this list unilaterally, per its own report's own recommendation)*

**P1 (required before freeze, or an explicit, recorded decision to accept as-is):** none found beyond DEBT-020.

**P2 (real, tracked, non-blocking):**
- DEBT-002 (AgentGovernor delegation dormancy), DEBT-006 (L2 memory volatility), DEBT-007 (BudgetGovernor accumulation gap), DEBT-011 (`ContentDomain`/K4.1-L reconciliation, blocks K4.2.6+ specifically, not Kernel v1.0), DEBT-015 (proposed-only future execution architecture), DEBT-018 (Verification contracts, explicitly gated on freeze+C-MoE by the project's own existing roadmap), DEBT-019 (5 confirmed security regressions — see §4, gates *Context Compiler and C-MoE adoption* per its own remediation register's tiering, not Kernel v1.0 freeze).

**P3 (deferred / low severity / cosmetic):**
- DEBT-004, DEBT-005 (event-mechanism naming, not fragmentation — both correctly separate concerns per their own entries), DEBT-008 (EventStream test coverage gap, not a defect), DEBT-010 (config-watcher race, timing-dependent test flakiness, no production data-loss risk), DEBT-012 (test-hygiene config churn), DEBT-014 (DRIFT-10 partial coverage, no live gap today), DEBT-017 (streaming bypasses K4.2 pipeline — confirmed-intentional architectural boundary, not a defect).

Nothing in the P2/P3 set changed classification as a result of this pass — this confirms the project's own prior severity ratings hold up under an explicit P0–P3 pass, rather than surfacing anything that had been mis-rated.

## 4. Security regression check

The five Context Engineering Security Audit findings (`KNOWN_ISSUES.md` DEBT-019, `docs/reports/context-compiler-remediation-register.md`) were re-confirmed unchanged by this session's own full-suite runs throughout (same 5 red tests, start to finish, across every run this session made). None were touched, weakened, or accidentally fixed by DEBT-016 or DEBT-003's work — neither touched `core/context.py`, `core/prompt/cache.py`, `core/memory/unified_memory.py`, or `core/brain_export.py`.

**These do not gate Kernel v1.0 freeze**, by the remediation register's own tiering, independently checked this session:
- Tier 1 (REM-001–004, includes CTX-AUTH-001/CTX-CACHE-001) explicitly gates **Context Compiler adoption** — a future subsystem, not part of Kernel v1.0's own scope.
- Tier 2 (REM-005) explicitly gates **C-MoE parallel-worker integration** — already-established post-freeze work.
- Tier 3 (REM-006–011, includes CTX-SCOPE-001/CTX-DELETE-001/CTX-EXPORT-001) is explicitly "real, tracked, not blocking" by the register's own words.

CTX-EXPORT-001 (`core/brain_export.py`'s `import_module()`, no signature/content validation, destructive `overwrite=True`) is the most severe-sounding of the five in isolation — a real gap, and it doesn't yet have a regression test the way the other four do (`REM-008`'s own row says "None yet"). It's bounded today by localhost-only bind + CSRF middleware per the register, and Tier 3 (non-blocking) per the same register's own classification. Flagging that it's the one Tier-3 item without a red test protecting it, in case that changes anyone's view of its tier — not overriding the register's own classification unilaterally.

## 5. The one open question: DEBT-020 (false completion)

`docs/Bugs Hunt & fix reports/FALSE_COMPLETION_KERNEL_AUDIT_PRE_IMPLEMENTATION_REPORT.md` (Sept 2, 2026) traced a live chain and found a partial, non-conforming output can reach `success=True` all the way to the user-facing response. Independently re-verified against current `main` (post this session's own two large changes to the exact file this centers on) rather than trusting the Sept 2 report as still accurate:

- `core/workflow/runtime.py` line 530 (moved from line 280 pre-refactor; same logic, preserved deliberately during this session's own DEBT-016 work, without at the time knowing this report existed): `success = last_result.success if last_result is not None else True` — success means only "the last node didn't error," checked against nothing about the request's actual scope.
- `core/runtime/execution_outcome.py`: `is_success` still returns `True` for `FailureType.COMPLETED_WITH_PARTIAL_OUTPUT`, confirmed unchanged.
- `core/workers/evaluator.py`: still zero references to `Constraint` — confirmed via fresh grep, zero hits.
- `core/cognitive/planner.py`'s `Constraint` dataclass: still no quantitative field (`kind`/`relation`/`source`/`rationale`/`validated_by` only) — confirmed by direct read.

Every load-bearing claim in that report holds on the current codebase, independently checked, not merely re-asserted.

**This is not classified as P0, P1, P2, or P3 above** because the report itself, and `KNOWN_ISSUES.md`'s DEBT-020 entry, both explicitly route the blocker-or-not decision to Moncif rather than assuming an answer — consistent with how every other genuine architectural fork this session and prior sessions have encountered has been handled (surfaced, not silently resolved). I'm not overriding that pattern here.

**What I can add, independently, to inform the decision:**
- The mechanism is real and confirmed, not theoretical — re-verified above, not merely re-cited.
- The recommended fix is scoped as minimal by the report that found it: give `Constraint` an actual checkable value, stop `is_success` from treating partial as full success, insert a scope check before the response is finalized. Explicitly *not* recommended: the general work-unit/coverage/resumability infrastructure DEBT-015 already tracks separately — that would be its own milestone, not a Kernel-correctness patch.
- Three items the report itself flagged **OPEN** (not yet traced) would need to be closed before implementation could safely start regardless of the blocker decision: what calls `ExecutionOutcome.partial_output` today, whether resume-from-partial exists anywhere (this session's own DEBT-003 work answers part of this — `resume()` restarts an interrupted *workflow*, which is a different question from restarting *partial output within one node*, and does not touch this), and exactly where `WorkflowRuntime`'s return value becomes literal response text.
- My own reading: this maps directly onto the founding concern of this entire Kernel-completion effort — "a task is not COMPLETE because the model produced an answer" is close to verbatim what this finding demonstrates is currently possible. That's a real argument for treating it as a third blocker. Against: Kernel v1.0's own scope, as this project has consistently drawn it across many prior sessions, has been the execution/governance substrate — not output-quality verification, which is Verification/Critic/Evidence's explicitly-deferred territory. A case exists either way; I'm presenting it rather than picking one.

## 6. Concurrency and idempotency

Focused on this session's own new code (DEBT-016, DEBT-003) as the freshest, least battle-tested parts of the Kernel, rather than attempting a full-Kernel sweep in one pass:

- **Checkpoint writes**: duplicate writes (a retried call whose first attempt actually succeeded) and concurrent writes (two racing writers to the same checkpoint name) both proven, not assumed, not to corrupt retrieval — `tests/test_workflow_runtime.py::TestWorkflowRuntimeCheckpointResume::test_duplicate_checkpoint_write_does_not_corrupt_retrieval` / `test_concurrent_checkpoint_writes_do_not_corrupt_retrieval`, added this session. Structural, not incidental: `EventStream.create_checkpoint()` is a plain atomic append; `get_checkpoint()` is latest-sequence-wins. Nothing partially overwrites.
- **Watchdog stall/extension**: `watchdog_decision.decide()` is a pure function with no shared mutable state across calls; `ExecutionBudget.grant_extension()`'s own internal clamping (already covered by pre-existing tests, unmodified by this session) is what prevents a race from granting more than `max_extension_s` total.
- **Known, accepted, pre-existing (not new) limitation**: nothing prevents two concurrent callers from calling `resume()` (or `execute()`) on the same `instance_id` at the same time — no instance-level lock exists anywhere in `WorkflowRuntime`, for either fresh or resumed execution. This is a general property of the runtime as a whole, not something DEBT-003 introduced or made worse; `execute()` had the identical property before this session's work. Not fixed here — flagging it as a real, if narrow, gap for the debt ledger rather than silently accepting it without a record.

## 7. Kernel Freeze Gate — the eleven questions

1. **What can OCBrain currently guarantee?** That governance evaluation runs before persistent memory mutation (DEBT-001, resolved). That a workflow execution's identity is stable across recovery attempts (`root_operation_id`/`attempt_id`, ADR-KERNEL-01). That a stalled workflow node gets one bounded recovery attempt before the execution is actually cancelled, not left silently stalled (ADR-KERNEL-02). That workflow state durably survives a process restart and can resume without re-running completed work (ADR-KERNEL-03). That the security-regression suite for context/memory handling stays red until each finding is actually fixed, not silently passing.
2. **What can it verify?** Whether an operation errored. Whether a node reached a terminal status. Whether a checkpoint's stored state matches what's read back. Governance rule violations (permission/recursion/budget checks that exist).
3. **What can it not verify?** Whether completed work actually satisfies what was asked (§5 — the open question). Whether Verification/Critic/Evidence's claims are correct — that whole subsystem is explicitly not integrated (contracts only, unwired, on a separate branch), by design, per the existing roadmap this session followed.
4. **Where can it still hallucinate?** Same answer as #3 — a confidently-wrong or incomplete output that doesn't error is currently indistinguishable, at the Kernel level, from a correct one.
5. **Where can it still fail silently?** DEBT-019's Tier 3 items (real but non-blocking security gaps) fail silently by design until fixed — they're intentionally-red tests, not silent, but the underlying behavior in production is silent. The `resume()`/`execute()` concurrent-call gap noted in §6.
6. **What happens when Verification fails?** Not applicable — not integrated into this Kernel's live path.
7. **What happens when Watchdog fails?** Now well-defined and tested (ADR-KERNEL-02): stall detected → bounded extension attempted once → cancellation with a typed reason if exhausted. Hard-deadline expiry cancels unconditionally regardless of stall state.
8. **What happens when evidence conflicts?** Not applicable — no evidence-model subsystem is live.
9. **What happens when the system cannot determine correctness?** It currently doesn't try to determine correctness of output content at all (§5) — only whether execution completed without erroring.
10. **What P2/P3 debt remains?** See §3 — nine items, none reclassified by this pass, none blocking.
11. **What future work is deliberately deferred?** Verification/Critic/Evidence integration (explicit, per roadmap). C-MoE / Neural Cognitive System (explicit, per this Kernel-completion sequence's own scope). DEBT-015's broader execution-reliability architecture. DEBT-011's learning-domain reconciliation. DEBT-019's Tier 1/2 remediation (gates Context Compiler/C-MoE specifically, not this freeze).

## 8. Kernel Readiness — explicit decision

**NOT_FREEZE_READY — but for a different, narrower reason than every prior audit in this project's history.**

Every blocker every previous audit identified is now resolved: the two original (Scope/identity, `WorkerContext`), plus the two this project's own history separately escalated to blocker status (DEBT-016, DEBT-003). The remaining open item is not a rediscovery of old debt — it's a new, independently-confirmed, unclassified finding (DEBT-020) whose own originating report explicitly declined to call it a blocker or not, asking for this project's owner to decide instead of assuming an answer either way. Declaring `FREEZE_READY` while a live, confirmed, previously-unaddressed false-completion path sits explicitly unclassified would be exactly the kind of vague "looks good" conclusion this whole effort exists to prevent. Declaring it a hard blocker unilaterally would be deciding something this project has consistently, deliberately routed to Moncif instead.

## 9. Deferred work (unchanged, reaffirmed)

Neural Cognitive System / C-MoE: explicitly out of scope for this Kernel-completion sequence, referenced only for compatibility, not touched. Verification/Critic/Evidence: post-freeze/post-C-MoE per the existing roadmap and this session's own sequencing decision; the Phase C contract branch remains untouched, unmerged, unwired. DEBT-011, DEBT-015, DEBT-019 Tier 1/2: all correctly non-blocking, all correctly still open.

## 10. One recommended next step

**Decide DEBT-020's classification.** Everything else this audit checked is either resolved or correctly non-blocking. This is the single item standing between "NOT_FREEZE_READY" and an actual freeze decision — not a list, one question: does the Kernel need the minimal fix described in §5 (checkable `Constraint` values, `is_success` no longer treating partial as full, a scope check before response finalization) before v1.0 freezes, or is it accepted as explicitly deferred, fast-follow work? Either answer lets this sequence conclude; no further audit work changes what's actually needed to decide it.
