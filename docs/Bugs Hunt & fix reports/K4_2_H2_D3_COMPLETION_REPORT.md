# K4.2-H2-D3 Completion Report — Capability Discrimination Acceptance Suite

**Repository:** `1h0lde4/ocbrain-v4.1`
**Branch:** `h2/d3-capability-discrimination`
**HEAD (implementation commit):** `8423d829b5564f2bf999e497fdaba954a71173b7`
**Packet scope:** `docs/architecture/h2_packets/D3_CAPABILITY_DISCRIMINATION.md` — one of four zero-contact parallel H2 packets (D3/D7/D11/D12), created from the same base commit `85e3d88`.
**Final status:** **COMPLETE**

This report follows the project's nine-step packet process (`docs/architecture/K4_2_CONTRACT_EVOLUTION_AND_DIAGNOSTIC_ARCHITECTURE_SPECIFICATION.md` §30): reality audit → compliance matrix → change plan → implementation → tests → interface stability audit → documentation sync → architecture compliance audit → merge-readiness audit.

---

## 1. Reality Audit

Read, in order, before writing anything:

1. `CURRENT_STATE.md` — confirmed K4.2-H1 is `FROZEN` (Aug 17, 2026, independent 16-gate freeze review, Moncif sign-off) and K4.2-H2 is the active milestone, with D3/D7/D11/D12 explicitly set up as the four parallel packets. No discrepancy from what the brief assumed — proceeded per the brief's own instruction for that case.
2. `docs/architecture/h2_packets/D3_CAPABILITY_DISCRIMINATION.md` — the authoritative, self-contained D3 brief. Treated as authoritative over the higher-level task prompt's own (slightly less precise) restatement of the same six cases, per "packet file + repository authority wins."
3. `docs/architecture/h2_packets/README.md` — cross-packet coordination guide; recorded baseline (1174 passed / 34 failed, `check_drift.py` 9/9) and the shared-files-off-limits list.
4. `docs/architecture/h2_packet_ownership.json` — machine-readable ownership manifest; D3's `allowed_files` and the single `allowed_files_conditional` entry for `core/cognitive/planner.py`.
5. `docs/Bugs Hunt & fix reports/K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md` §8 — the fuller D3 packet description with the cross-milestone dependency graph.
6. `tests/core/cognitive/test_planner.py::TestGeneralPurposeFallback` — H1's existing Case A/B coverage (`test_general_purpose_bypasses_min_score`, `test_specificity_dominance_ranks_specific_above_general`), read in full before writing anything new, to extend the established pattern rather than invent a third style. Also read `TestDiscoverCapabilities`, `TestCapabilityDiscoveryArchitectureCompliance`, and the `_make_registry`/`_real_code_identifiers` helpers for construction and verification idioms.
7. `core/cognitive/planner.py` — `discover_capabilities()`, `CapabilityMatch`, `CapabilityDiscoveryResult`, `_capability_match_score()`, `_classify_specificity_tier()`, and the ranking sort, read in full.
8. `core/capabilities/registry.py` — confirmed `CapabilityRegistry` has no class-level or module-level shared state (`_contracts`/`_adapters` dicts are created fresh in `__init__`), and that `list_capabilities()` returns `self._contracts.keys()` in insertion (registration) order — the fact that makes Case D's tie-break question reachable at all.
9. `core/capabilities/capability.py` — confirmed only `llm_completion` is a registered production capability; the other nine `CapabilityType` names are declared, not registered. Repository-wide search confirmed none of this suite's five synthetic capability_type strings (`calendar_scheduling`, `document_translation`, `general_purpose_assistant`, `torque_calibration_procedure`, `sequence_verification_procedure`) appear anywhere else in the codebase.

Pre-work checks:
- `python3 scripts/check_packet_ownership.py --packet D3` → `PASS` ("no changes on this branch relative to main yet").
- Branch confirmed correct: `h2/d3-capability-discrimination`, tracking `origin/h2/d3-capability-discrimination`, both at `85e3d88` before any change.

## 2. Compliance Matrix

| Frozen contract | Requirement | Status |
|---|---|---|
| `min_score=0.01` | Never weakened | Preserved — passed explicitly on every `discover_capabilities()` call in the new suite; never omitted, never changed. Unchanged in `planner.py` itself. |
| `CapabilityMatch` evidence fields | Existing fields (`lexical_score`, `specificity_tier`, `general_fallback`) unchanged | Preserved — no field added, removed, or renamed. Case F asserts on all three by name. |
| `is_general_purpose` semantics | Fallback, not override (H1 Decision 2 / ADR-K4.2-H-02) | Preserved and re-verified — Case B explicitly confirms the specific capability outranks the fallback, not the reverse. |
| Discovery/selection split | Discovery never ranks to a single winner, never invokes adapters | Preserved — no change to this behavior; `CapabilityDiscoveryResult.matches` remains a ranked list in every test. |
| Registry "no global state" design | No singleton lookups | Preserved — every test constructs its own local `CapabilityRegistry()`; `TestRegistryIsolationBoundary` proves this behaviorally. |

## 3. Change Plan

- **Test-only capabilities:** two genuinely distinct domains unrelated to each other and to `llm_completion` — calendar scheduling (`calendar_scheduling`) and document translation (`document_translation`) — plus a test-only general-purpose fallback (`general_purpose_assistant`), none reusing production wording. A second, deliberately-engineered pair (`torque_calibration_procedure` / `sequence_verification_procedure`) was added specifically to probe the Case D open question's edge case (exact score tie) — clearly documented in that test's own docstring as a boundary probe, not a naturalistic request, unlike every other case in the file.
- **Six cases → tests:** A (general-purpose rescue) → `TestGeneralPurposeFallbackDiscrimination`; B (specificity dominance) → `TestSpecificityDominanceDiscrimination`; C (unsupported request) → `TestUnsupportedRequestDiscrimination`; D (registration-order independence) → `TestRegistrationOrderIndependence` (two tests: realistic non-tied case, exact-tie edge case); E (dynamic registration) → `TestDynamicCapabilityRegistration` (two tests: behavioral proof, source-hardcoding check); F (evidence) → `TestCapabilityMatchEvidence`. Plus the required boundary test → `TestRegistryIsolationBoundary`.
- **Case D plan, explicitly:** write the test first, run it against the unmodified implementation, do not assume the result. If it passes, stop. If it fails on a trivial deterministic tie-break, apply the smallest safe correction. If it needs more, write the ADR first. (Executed exactly this way — see §5 and §6.)
- **Scoring pre-verification:** before writing any assertion, every candidate request/description pair's actual `_capability_match_score()` output was computed via a throwaway script against the real function, to avoid hand-derived Jaccard arithmetic errors ending up baked into test assertions. The exact-tie pair was constructed by symmetric token-set design (equal overlap-with-request count, equal total token count) and confirmed float-identical before being used in a test.

## 4. Implementation

**New file:** `tests/test_capability_discrimination.py` — 9 tests across 7 classes (`TestGeneralPurposeFallbackDiscrimination`, `TestSpecificityDominanceDiscrimination`, `TestUnsupportedRequestDiscrimination`, `TestRegistrationOrderIndependence`, `TestDynamicCapabilityRegistration`, `TestCapabilityMatchEvidence`, `TestRegistryIsolationBoundary`). Local `_register()` and `_planner_source_text()` helpers only — deliberately not imported from `tests/core/cognitive/test_planner.py`, keeping this packet's ownership scope self-contained in the one file it owns. Every test calls the real, unmocked `discover_capabilities()`; nothing about the discovery mechanism itself is mocked anywhere in the file.

**Production change (conditional file, condition met):** `core/cognitive/planner.py` — one line inside `discover_capabilities()`'s ranking sort, plus docstring/comment updates explaining it (see §5 for why the condition was met, and the ADR for the full reasoning):

```diff
- scored.sort(key=lambda m: (m.is_general_purpose, -m.relevance_score))
+ scored.sort(key=lambda m: (m.is_general_purpose, -m.relevance_score, m.capability_type))
```

**New ADR:** `docs/architecture/decisions/ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md` — context, decision, consequences, alternatives considered, per house ADR format (matched against `ADR_K4_2_H_02_GENERAL_PURPOSE_FALLBACK.md`'s structure).

**Detected and reverted, not committed:** running the full suite (§5) twice had the side effect of rewriting `config/models.toml` and `config/sources.toml` (CRLF → LF line-ending changes only, zero content difference) — some test's fixture handling writes those files in place rather than to `tmp_path`. This is unrelated to D3's scope; both occurrences were reverted (`git checkout -- config/models.toml config/sources.toml`) before committing, per this project's established "detect and revert unrelated churn" convention. Flagged in the status stub for whoever does the integration pass, since this packet does not own `KNOWN_ISSUES.md`.

## 5. Tests

**New suite, run in isolation, before the fix (unmodified `planner.py`, via `git stash`):**

```
tests/test_capability_discrimination.py — 8 passed, 1 failed
FAILED TestRegistrationOrderIndependence::test_exact_score_tie_does_not_depend_on_registration_order
  AssertionError: an exact relevance_score tie must resolve identically regardless of registration order
  assert 'torque_calibration_procedure' == 'sequence_verification_procedure'
```

Every other case — A, B, C, the realistic (non-tied) half of D, E, F, and the registry-isolation boundary test — **passed unmodified**. Confirmed both capabilities' `relevance_score` was float-identical (`0.23076923076923078 == 0.23076923076923078`) before treating the failure as meaningful, not a near-tie artifact.

**Case D result, explicitly:** the open question resolved to *partially yes* — registration order does not affect the winner when scores differ (unmodified, no gap), but does affect the winner under an exact score tie (a real, if currently dormant, gap; production registers only one capability today, so no live tie is currently reachable). This is a trivial, clearly-deterministic tie-break per the packet's decision tree (does not touch `CapabilityMatch` semantics, scoring semantics, the public API, or the discovery architecture) — corrected directly rather than escalated. Full reasoning in `ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md`.

**Unsupported-request behavior (Case C):** a registry containing only the two specific (non-general-purpose) test capabilities, given a request with zero lexical overlap with either, returns `result.matches == []` and `result.top_match is None` — capabilities are not falsely selected merely because they exist. (A general-purpose capability was deliberately *not* included in this registry: it would always appear regardless of request, by design — Case A already proves that separately — so its presence here would have made this test unable to distinguish "correctly unsupported" from "rescued by the fallback, as intended.")

**Registration-order behavior (Case D):** see above — order-independent when scores differ (unmodified); was order-dependent under an exact tie (fixed).

**Evidence behavior (Case F):** the winning match's `evidence["general_fallback"]` is `False` and `specificity_tier` is `weak_specific`/`strong_specific`; the fallback's `evidence["general_fallback"]` is `True` and `specificity_tier` is `general_fallback`; both match's `evidence["lexical_score"]` equals `round(relevance_score, 4)` exactly, i.e. evidence is a faithful record of the value that actually drove ranking, not a second, independently-computed source of truth.

**New suite, after the fix — full pass:**

```
9 passed in 1.68s
```

**Regression — `tests/core/cognitive/test_planner.py` (all 123 pre-existing planner/discovery tests):**

```
123 passed in 0.77s
```

Zero regressions, including every `TestDiscoverCapabilities` and `TestGeneralPurposeFallback` case that exercises the exact sort line this packet changed.

**Full suite comparison against the documented baseline** (`docs/architecture/h2_packets/README.md`: 1174 passed / 34 failed):

| | Unmodified branch (`git stash`, this session) | After D3's change |
|---|---|---|
| Passed | 1174 | 1183 (1174 + 9 new D3 tests) |
| Failed | 34 | 34 |

The two 34-item failure lists were extracted (`grep '^FAILED'`, sorted) and diffed byte-for-byte both ways (`diff before_failures.txt after_failures.txt`) — **empty diff, i.e. the exact same 34 test IDs fail in both runs.** This is the rigorous form of "any new failure needs an explanation, not a shrug": there were zero new failures to explain. 8 of the 34 show an explicit `OSError: We couldn't...` (Hugging Face Hub connectivity) signature directly in the pytest short summary; the remaining 26 (in `test_k2_2_runtime_migration.py`, `test_orchestrator_memory_migration.py`, `test_planner_capability_migration.py`, `test_planner_worker.py`, `test_session4b_memory_hardening.py`, `test_session4c_architecture.py`) do not show that signature in the one-line summary but are confirmed identical, by exact test ID, to the unmodified branch's own failures — i.e. this packet did not need to independently re-diagnose their root cause to know they are unrelated to this change, only to confirm the set is unchanged, which the diff does unambiguously. (Separately, on a bare fresh clone with no `pip install` yet run, four files — `test_break_concurrency.py`, `test_break_empty_db.py`, `test_break_security.py`, `test_system_ctrl.py` — fail to *collect* at all with `ModuleNotFoundError: No module named 'chromadb'`; installing `requirements.txt` resolves this and is what produces the 34/1174 baseline. Noted in the status stub as environment setup, not a defect.)

**Drift check:**

```
check_drift.py --quiet, unmodified: 9/9 PASS
check_drift.py --quiet, after fix:  9/9 PASS
```

`DRIFT-06` ("No hard-coded capability type strings in Planner routing") passing both before and after is an independent, tool-based confirmation of this suite's own Case E finding.

**Ownership check** (run post-commit, against the real diff): `PASS` — see §9.

## 6. Interface Stability Audit

- `discover_capabilities()`'s signature (`request`, `registry`, `event_stream`, `min_score`, `operation_id`) — unchanged.
- `CapabilityMatch`'s fields (`capability_type`, `contract`, `relevance_score`, `subgoal_ref`, `is_general_purpose`, `evidence`) — unchanged.
- `CapabilityDiscoveryResult`'s fields and properties (`matches`, `subgoal_ref`, `.contracts`, `.top_match`) — unchanged.
- `CapabilityRegistry`'s public methods — unchanged (read-only usage throughout this packet).
- Ranking behavior — unchanged for every case where two candidates' `(is_general_purpose, relevance_score)` differ (i.e., every ranking any pre-existing test, production code path, or this suite's own cases A/B/C/E/F exercises). Changed *only* for the exact-tie edge case, which no pre-existing code path reaches (production registers one capability) and no pre-existing test exercised (confirmed by the full-suite regression run).

## 7. Documentation Sync

- `ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md` — created (the reserved slot named in the ownership manifest).
- `core/cognitive/planner.py` — `discover_capabilities()`'s docstring gained a D3/ADR-K4.2-H-03 paragraph, and the ranking-sort comment block was extended, matching the file's existing per-decision documentation convention (D2/D4/D8 paragraphs already present).
- `docs/architecture/h2_status/D3_STATUS.md` — overwritten from its `NOT STARTED` placeholder with the real status stub.
- This completion report.
- Deliberately **not** touched, per the ownership manifest's `shared_files_deferred_to_integration` list: `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md`, `docs/architecture/decisions/ADR_INDEX.md`, `PROJECT_INDEX.md`, `tests/conftest.py`. `ADR_INDEX.md` will need a new row for ADR-K4.2-H-03 at the integration step — not this packet's job.

## 8. Architecture Compliance Audit

- `scripts/check_drift.py` — 9/9 PASS, before and after (§5).
- `scripts/check_packet_ownership.py --packet D3` — PASS (§9).
- No forbidden file touched: `core/cognitive/intent.py`, `core/cognitive/compiler.py`, `core/orchestrator.py`, `core/capabilities/*` production registrations, `core/governance/*`, `core/workers/*`, `core/workflow/*` — none appear in this branch's diff from `main` (verified via `git status`/`git diff --name-only` throughout, and mechanically via the ownership check).
- No H1-frozen contract changed (§2).
- No capability-selection logic introduced (Discovery still returns a ranked list; `TestCapabilityDiscoveryArchitectureCompliance::test_returns_ranked_list_not_a_single_winner`, unmodified, still passes).

## 9. Merge-Readiness Audit

- **Ownership check, run against the real commit diff** (post-commit, `git diff main...HEAD --name-only`): `python3 scripts/check_packet_ownership.py --packet D3` → **PASS**.
- **Parallel-session impact:** D7's allowed files (`docs/architecture/h2_status/D7_STATUS.md`, `ADR_K4_2_H_07_TERMINAL_IMPASSE_CLOSEOUT.md`), D11's (`core/cognitive/intent.py`, `tests/core/cognitive/test_intent.py`, `docs/architecture/h2_status/D11_STATUS.md`, its completion report, `ADR_K4_2_H_11_LANGUAGE_SUPPORT.md`), and D12's (`docs/architecture/h2_status/D12_STATUS.md`, `ADR_K4_2_H_10_DRIFT_TOOLING_RECORD.md`, `ADR_K4_2_H_12_TRACKING_HARDENING.md`, `IMPLEMENTATION_TRACKER.md`) — cross-checked against this branch's changed-file list; zero overlap.
- **Unrelated churn:** none in the final commits (the `config/*.toml` line-ending churn from running the full suite was detected and reverted before committing — see §4).
- **Unresolved / deferred issues:**
  1. `config/models.toml` / `config/sources.toml` line-ending rewrite side effect from running the full suite — worth a `KNOWN_ISSUES.md` entry; out of this packet's ownership scope to add directly.
  2. `ADR_INDEX.md` needs a new row for ADR-K4.2-H-03 — deferred to the integration packet by design (shared-file rule).
  3. The exact-tie tie-break rule (alphabetical `capability_type`) is dormant in production until a second capability is registered — worth re-confirming behaviorally once a real second production capability exists, though the current test coverage already exercises the mechanism directly and does not depend on production registration state.
- **Rollback:** trivial if ever needed — this packet is one commit (`8423d82`) touching exactly `core/cognitive/planner.py` (a 9-line net addition: 1 code line + 8 comment/docstring lines) plus two new files (test suite, ADR); reverting the single commit fully restores pre-D3 state.

---

## Final Status

**COMPLETE**
