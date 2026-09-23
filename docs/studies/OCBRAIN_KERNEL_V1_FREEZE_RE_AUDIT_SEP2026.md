# OCBrain Kernel v1.0 — Comprehensive Freeze Re-Audit Report

**Date:** September 18, 2026
**Author:** OCBrain Kernel Engineering Audit
**Target:** OCBrain Kernel v1.0 Freeze Determination

---

## Executive Summary & Freeze Verdict

**Verdict:** **`NOT_FREEZE_READY`**

While all core execution and durability blockers previously identified in historical audits—such as Root Operation Identity (`root_operation_id`), `WorkerContext` migration, Checkpoint/Resume (`DEBT-003`), Watchdog Unification (`DEBT-016`), False Completion (`DEBT-020`), L1 deletion truthfulness (`CTX-DELETE-001`), Prompt Cache identity (`CTX-CACHE-001`), and Context Scope Caller Wiring (`CTX-SCOPE-001`)—have been successfully implemented and verified on `main`, the OCBrain Kernel cannot be formally declared frozen.

Crucially, a comprehensive audit of all remote repository branches revealed that **an implementation for CTX-AUTH-001b exists on an unmerged branch (`origin/fix/ctx-auth-001b-verified-provenance-sep2026`)**, implementing `ADR-KERNEL-06` (Verifiable Hypothesis Provenance). However, because this branch has not yet been merged into `main`, the issue remains open on the primary release branch.

The remaining freeze readiness is gated on **three critical unresolved blockers/decisions**:

1. **CTX-AUTH-001b (Parser / Authority Acceptance):** On `main`, `_parse_hypotheses()` in `core/cognitive/intent.py` accepts context-injected hypothesis lines (e.g. `novel:CONTEXT_SENTINEL_INJECTED | 0.55`) with no machine-verifiable authority check or provenance tracing. `origin/fix/ctx-auth-001b-verified-provenance-sep2026` (commit `fae9af9`) contains a complete, verified implementation of `ADR-KERNEL-06` that resolves this gap, but **must be merged into `main`**.
2. **CTX-EXPORT-001 (Module Bundle Import Validation & Reversibility):** `import_module()` in `core/brain_export.py` performs unauthenticated extraction and destructive replacement of module knowledge bases with zero checksum, signature, or content validation, and no transactional rollback on partial failure.
3. **DEBT-025 (Unauthenticated API Boundary):** `interface/api.py` exposes 24 HTTP routes with zero authentication middleware or API-key verification, directly exposing sensitive state and control endpoints (including `import_module`).

Until explicit governance decisions or technical merges/remediations close these three gaps, Kernel v1.0 cannot be certified as frozen.

---

## 1. Primary Freezing Blockers Detail

### 1.1 CTX-AUTH-001b — Parser / Authority Acceptance Gap
* **Location:** `core/cognitive/intent.py:202-235` (`_parse_hypotheses`), tested in `tests/core/cognitive/test_intent_security.py:254` (`TestCtxAuth001ParserAcceptance`).
* **Current State on `main`:** **OPEN (Intentionally Red Test)**.
* **Unmerged Fix Branch:** `origin/fix/ctx-auth-001b-verified-provenance-sep2026` (commit `fae9af9`).
* **Empirical Evidence:**
  - On `main`, running `pytest tests/core/cognitive/test_intent_security.py` fails on `test_injection_shaped_completion_line_is_not_accepted_as_a_hypothesis`.
  - On `origin/fix/ctx-auth-001b-verified-provenance-sep2026`, `ADR-KERNEL-06` (Verifiable Hypothesis Provenance) is fully implemented: hypotheses carry an `authority` field (`AuthorityLevel.USER`, `RETRIEVED`, etc.), citations are deterministically resolved against `Context.blocks`, and `_select_operative_hypothesis()` gates selection on verified `USER` authority.
* **Required Resolution:**
  - Merge `origin/fix/ctx-auth-001b-verified-provenance-sep2026` into `main` to close CTX-AUTH-001b completely.

---

### 1.2 CTX-EXPORT-001 — Unvalidated & Destructive Module Import
* **Location:** `core/brain_export.py:120-180` (`import_module`), HTTP routers `interface/api.py:456` and `core/brain_api.py:142`.
* **Current State:** **PARTIALLY MITIGATED (Path traversal fixed, validation open)**.
* **Empirical Evidence:** Path traversal via `module_name` (`../../etc`) was fixed on Sept 15, 2026 by enforcing `.isidentifier()` validation (`test_brain_export_security.py` passes). However, `import_module()` still accepts arbitrary `.zip` bundles with no cryptographic signature, checksum, or schema validation. `shutil.rmtree(mod_dir)` destructively wipes existing knowledge before import completes, offering no rollback on failure.
* **Required Decision / Resolution:**
  - Classify whether CTX-EXPORT-001 is a strict Kernel v1.0 freeze blocker or Tier 3 fast-follow debt.
  - Implement bundle manifest checksum/signature verification and transactional rollback (import to temporary directory before atomic swap).

---

### 1.3 DEBT-025 — Unauthenticated Public API Boundary
* **Location:** `interface/api.py:1-500` (24 route handlers).
* **Current State:** **OPEN**.
* **Empirical Evidence:** Direct code inspection confirms zero `Depends()`, API key checks, or bearer token middleware anywhere in `interface/api.py`.
* **Impact:** Any client reaching the API port can invoke arbitrary management operations, trigger module reloads, run cognitive queries, and execute module imports.
* **Required Decision / Resolution:**
  - Explicit decision by Moncif: Is local-only (127.0.0.1) single-user binding sufficient for Kernel v1.0 freeze, or is a minimal bearer-token/API-key middleware required before tagging `v1.0.0`?

---

## 2. Status of Unmerged Branches & PR Triage

A complete sweep of all 18 remote branches was conducted:

| Branch Name | Primary Content | Status relative to Kernel Freeze |
|---|---|---|
| `origin/fix/ctx-auth-001b-verified-provenance-sep2026` | Implements `ADR-KERNEL-06` verifiable hypothesis provenance for CTX-AUTH-001b. | **Ready to Merge.** Fully resolves CTX-AUTH-001b once merged into `main`. |
| `origin/feature/verification-critic-evidence-phase-c` | Verification/Critic/Evidence contracts (~60/90 types). | **Post-Freeze.** Explicitly scoped as post-Kernel-freeze and post-C-MoE. |
| `origin/sandbox-fabric` | Execution Fabric Phase 1 & 2 research & DockerBackend prompt. | **Post-Freeze / Additive.** Namespace/seccomp backends (DEBT-022, DEBT-023) are already on `main`. |
| `origin/docs/workspace-architecture-final-consistency-pass` | Resolves Workspace Decision #19 (DEBT-027). | **Merged/Updated.** Banner added to `core/workspace/domain.py`. |
| `origin/fix/debt-020-completion-semantics-sep2026` | Alternative `CompletionStatus` design for DEBT-020. | **Superseded.** Moncif decided `main`'s DEBT-020 fix (`ADR_KERNEL_04`) is canonical. |
| `origin/security/rce-001-modules-new-hotfix` | RCE-001 hotfix for `POST /modules/new`. | **Merged.** Already resolved on `main` (DEBT-026). |

---

## 3. Status of Previously Resolved Blockers on `main`

All major blockers from prior audit sessions have been re-verified on `main`:

| Item / DEBT | Description | Resolution Details | Verification Status |
|---|---|---|---|
| **Root Identity** | `root_operation_id` threading | Threaded across `Goal`, `ExecutionPlan`, `WorkflowDefinition`, and `ExecutionContext`. | ✅ Verified (`tests/core/cognitive/test_kernel_blocker_resolution.py`) |
| **WorkerContext** | Migration to `ExecutionContext` | All 7 workers accept `ExecutionContext` directly. | ✅ Verified |
| **DEBT-003** | Checkpoint / Resume | `WorkflowRuntime.resume()` resumes execution using durable WAL checkpoints (`ADR_KERNEL_03`). | ✅ Verified (`tests/test_workflow_runtime.py`) |
| **DEBT-016** | Watchdog Unification | `GraphExecutionWatchdog` and model router watchdog unified around `watchdog_decision.py` (`ADR_KERNEL_02`). | ✅ Verified (`tests/test_execution_watchdog.py`) |
| **DEBT-020** | False Completion Gate | `Constraint` verification & output satisfaction enforced in `WorkflowRuntime` & `Orchestrator` (`ADR_KERNEL_04`). | ✅ Verified (`tests/test_debt_020_false_completion.py`) |
| **CTX-DELETE-001** | UnifiedMemory delete outcome | `delete()` propagates true L1 storage deletion outcome. | ✅ Verified (`tests/test_unified_memory.py`) |
| **CTX-CACHE-001** | Prompt cache key identity | `cached_generate()` hashes uncompressed full prompt. | ✅ Verified (`tests/test_prompt_cache_security.py`) |
| **CTX-SCOPE-001** | Context isolation caller wiring | `ContextMemory` scope threaded across `PlannerWorker`, `ModelRouter`, and streaming endpoints. | ✅ Verified (`tests/test_planner_worker.py`) |

---

## 4. Comprehensive Active Technical Debt Triage (DEBT-002 to DEBT-028)

| ID | Category | Severity | Description | Freeze Classification |
|---|---|---|---|---|
| **DEBT-002** | Governance | Medium | `AgentGovernor` delegation matrix checks unpopulated `delegating_worker_type`. | Non-Blocking (P2) |
| **DEBT-004** | Events | Low | `KnowledgeEvent` vs `EventStream` dual logging paths. | Non-Blocking (P3) |
| **DEBT-005** | Events | Low | `EventBus` in-process pub/sub vs `EventStream` WAL persistence. | Non-Blocking (P3) |
| **DEBT-006** | Memory | Medium | `InMemoryVectorBackend` recalculates embeddings on startup. | Non-Blocking (P2) |
| **DEBT-007** | Governance | Medium | `BudgetGovernor` step/token accumulation metadata missing. | Non-Blocking (P2) |
| **DEBT-008** | Tests | Low | `EventStream` lacks dedicated unit test file for replay. | Non-Blocking (P3) |
| **DEBT-010** | Config | Low | `Config` watcher thread race condition in test patching. | Non-Blocking (P3) |
| **DEBT-011** | Learning | Medium | `ContentDomain` closed enum vs K4.1-L open domain model. | Non-Blocking (P2 - Post-C-MoE) |
| **DEBT-012** | Tests | Low | Full suite run causes line-ending churn in `config/*.toml`. | Non-Blocking (P3) |
| **DEBT-014** | Drift | Low | `check_drift.py` checks specific files by name rather than directory sweep. | Non-Blocking (P3) |
| **DEBT-015** | Runtime | Medium | Operation/ExecutionAttempt/ExecutionSnapshot proposed architecture. | Non-Blocking (P2 - Post-Freeze) |
| **DEBT-017** | Interface | Low | Direct streaming API bypasses K4.2 Cognitive Front-End. | Non-Blocking (P3) |
| **DEBT-018** | Verification | Medium | Verification/Critic/Evidence system contract completeness (~60/90 types). | Non-Blocking (P2 - Post-C-MoE) |
| **DEBT-019** | Security | Medium | Context Engineering audit remediation register tracking (REM-001 to REM-015). | Partially Blocking (CTX-AUTH-001b on `main`; fix ready on unmerged branch) |
| **DEBT-021** | Sandbox | Low | Lack of Docker-backed Sandbox Fabric implementation (only namespace backend exists). | Non-Blocking (P3) |
| **DEBT-024** | Workers | Medium | `SupervisorWorker._attempt_retry()` unreachable from production callers. | Non-Blocking (P2) |
| **DEBT-025** | Security | Medium-High | `interface/api.py` lacks authentication middleware. | **Freeze Blocker Candidate** |
| **DEBT-027** | Workspace | Medium | `core/workspace/domain.py` non-conformant draft flagged with non-authoritative banner. | Non-Blocking (P2) |
| **DEBT-028** | Runtime | Low-Medium | No instance-level lock on `WorkflowRuntime` concurrent `execute()` / `resume()`. | Non-Blocking (P2) |

---

## 5. Test Suite Execution & Environment Health

* **Environment Pins:**
  - `chromadb==0.5.3`
  - `numpy==1.26.4`
  - `scipy==1.13.1`
* **Execution Results:**
  - Total tests executed: **1,507**
  - **Passed:** **1,503**
  - **Skipped:** 14
  - **Failures:** **4**
    1. `tests/core/cognitive/test_intent_security.py::TestCtxAuth001ParserAcceptance` (Expected security invariant failure for CTX-AUTH-001b on `main`; fixed on `origin/fix/ctx-auth-001b-verified-provenance-sep2026`).
    2. `tests/core/sandbox/test_seccomp.py::test_apply_denylist_blocks_most_syscalls_on_this_arch` (Sandbox container environment restriction on `seccomp_load`).
    3. `tests/core/sandbox/test_seccomp.py::test_ptrace_is_blocked_after_apply` (Sandbox container environment restriction on `seccomp_load`).
    4. `tests/core/sandbox/test_seccomp.py::test_getpid_unaffected_after_apply` (Sandbox container environment restriction on `seccomp_load`).

---

## 6. Required Action Items for Kernel v1.0 Freeze Sign-Off

To achieve official Kernel v1.0 Freeze (`FREEZE_READY`), the following explicit actions/decisions are required:

1. **Merge CTX-AUTH-001b Fix:** Merge `origin/fix/ctx-auth-001b-verified-provenance-sep2026` into `main` to activate `ADR-KERNEL-06` hypothesis authority verification and turn `TestCtxAuth001ParserAcceptance` green.
2. **Decision on CTX-EXPORT-001:** Implement manifest validation and atomic rollback in `brain_export.py`, OR formally certify CTX-EXPORT-001 as Tier 3 non-blocking for Kernel v1.0.
3. **Decision on DEBT-025:** Accept local 127.0.0.1 bind as sufficient deployment security for Kernel v1.0, OR add a minimal API-key / bearer-token auth check in `interface/api.py`.
4. **Tagging:** Retag `v1.0.0` on `main` once steps 1–3 are finalized.

---
*Report compiled and verified against live codebase.*
