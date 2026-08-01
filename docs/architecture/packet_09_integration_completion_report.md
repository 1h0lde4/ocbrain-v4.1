# Packet 09 — Integration: Full Cognitive Pipeline — Completion Report

**Packet:** Packet 09 — Integration: Full Cognitive Pipeline
**Architecture References:** `OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md` — Packet 09 section;
`OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §16 (all 9 Runtime Invariants)
**Status:** Completed
**Date:** July 30, 2026
**Dependencies:** Packets 01–08 (all complete)

---

## §0 — Discrepancies Found

One genuine, previously-undiscovered bug was found in already-reviewed, already-merged code, surfaced only by genuine end-to-end testing. Reported here per this project's own "document first, smallest correction necessary" rule; fixed, not worked around.

**For the historical record: this is a pre-existing defect in Packet 03's implementation (July 2026, K4.2.5), not a defect introduced by or attributable to Packet 09.** Packet 09 contributed the end-to-end test methodology that was capable of detecting it — a category of testing no earlier packet's own unit tests performed — and, having found it, fixed it under this project's "document first, smallest correction necessary" rule rather than leaving it in place or working around it in the test.

**`plan()` (`core/cognitive/planner.py`, Packet 03/K4.2.5) did not forward `event_stream` to `_extract_constraints()`.**

```python
constraints = await _extract_constraints(goal)               # before: event_stream silently dropped
decomposition = await _decompose(goal, registry, event_stream=event_stream)  # correct, one line below
```

`_extract_constraints()`'s own default (`event_stream = event_stream or get_event_stream()`) meant `cognitive.constraints_extracted` was silently emitted to the global singleton `EventStream` instead of whatever explicit, isolated stream a caller passed to `plan()` — while the very next line does the correct thing for the same parameter. This is a plain propagation oversight, not a design choice (no comment or rationale accompanies the omission, and it's inconsistent with the adjacent, correct line).

**Why no existing test caught this:** confirmed by direct inspection, not assumed. `tests/core/cognitive/test_planner.py`'s `TestPlan` class exercises `plan()` with `event_stream=AsyncMock()` but never asserts on which events were appended to it. The dedicated `cognitive.constraints_extracted` test calls `_extract_constraints()` directly, passing `event_stream` straight to it — which bypasses this exact call site and therefore this exact bug, by construction. Only a test that runs `plan()` as part of a longer chain, through a real `EventStream`, and asserts on the complete ordered event trail — precisely this packet's own "event trail complete and replayable" completion criterion — would surface it.

**Fix:** the smallest possible change — `_extract_constraints(goal, event_stream=event_stream)`, one added keyword argument. Verified safe against the full 1093-test suite (no existing test depends on the buggy behavior; none inspect this specific event's destination). Not a redesign of Packet 03's work, and Packet 03's own tests, contracts, and public interface are entirely unchanged.

---

## §1 — Scope Confirmed

From `OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`'s Packet 09 section — deliberately a test packet, not a new production module (that document's own "Future Architectural Placeholders" note: C-MoE / Execution Runtime / etc. get "no implementation packets produced"):

- End-to-end: `raw_text → interpret() → plan() → compile() → WorkflowDefinition`
- Verify all events emitted in correct order
- Verify all lifecycle transitions
- Verify governance gates at Plan Compilation
- Verify clarification bounded-retry
- Verify SupervisorWorker recovery path
- **Completion criteria:** full pipeline fixture passes; event trail complete and replayable; all 9 K4 §16 invariants verified by test; all existing tests pass

All items delivered. No new `core/` production module was created — the one code change (§0 above) is a bugfix discovered while satisfying this packet's own completion criteria, not new functionality.

---

## §2 — Key Implementation Decisions

1. **Real objects at every stage, LLM calls mocked using the established convention — not a new one.** `tests/core/cognitive/test_intent.py`'s `TestInterpretRequest` and `tests/core/cognitive/test_planner.py`'s decomposition tests both already patch their own module's `generate_with_fallback` binding (two separate patches, since Python's `patch()` targets the name as imported into each module's namespace, not the underlying function once). This packet's fixtures do the same, reusing the identical technique rather than inventing a new mocking strategy or a fake pipeline.

2. **`CapabilityRegistry` construction mirrors `tests/core/cognitive/test_planner.py`'s own `_make_registry()` helper exactly** ("matching the live composition root, `main.py`" per that helper's own docstring) — not reinvented for this packet.

3. **A real, SQLite-backed `EventStream` (via `tmp_path`), not the lightweight fakes used in per-module unit tests.** The "event trail complete and replayable" criterion specifically requires exercising real persistence and `EventStream.replay()`, which a fake stream (used throughout Packets 06–08's own unit tests, appropriately, for speed and isolation there) cannot demonstrate. This is a deliberate, documented choice to use heavier test infrastructure only where the completion criterion specifically calls for it.

4. **Governance-gate and clarification-bound tests apply a `confidence_override` to a genuinely pipeline-produced `ExecutionPlan`** rather than engineering a raw-text input that happens to make the mocked hypothesis path compute a specific number indirectly. `ExecutionPlan` is not frozen, so directly setting `.confidence` on an otherwise real, decomposition-produced plan is the practical way to deterministically exercise REJECT/ESCALATE/APPROVE against real plan structure without fragile, indirect engineering of the mock inputs.

5. **All 9 K4 §16 invariants are individually enumerated as separate tests**, each citing the invariant's exact wording. Where an invariant was already unit-tested in an earlier packet (1, 6, 7, 9), this suite adds a fresh assertion at the *integration* level (a genuinely pipeline-produced object, or a targeted structural check complementing rather than duplicating the earlier packet's test) instead of re-deriving the same isolated test a second time. Invariant 9's entry in `TestRuntimeInvariants` is a structural AST check on `SupervisorWorker._surface_compilation_outcome` specifically (no retry-capable call in that function, independent of any test input) — complementary to, not a copy of, the full runtime test in `TestSupervisorRecoveryPath` that exercises the same invariant against a real rejected `CompilationResult`.

6. **`Goal.lifecycle_state` correctly stays `DRAFT`, not `VERIFIED`, in this suite's tests — confirmed to be correct behavior, not a gap.** `core/cognitive/intent.py` sets `lifecycle_state=GoalLifecycle.VERIFIED if validated else GoalLifecycle.DRAFT`; `validated` requires a matching Intent Ontology category, and no such category exists anywhere in this repository yet. The mocked "novel:..." hypothesis is deliberately the open-category degrade path. An initial version of this test incorrectly assumed `VERIFIED`; corrected after reading `core/cognitive/intent.py` directly rather than assumed, and the reasoning is now documented in the test's own docstring so a future reader doesn't mistake this for a bug.

---

## §3 — Files Modified

**New:**
- `tests/test_integration_full_pipeline.py` — 20 tests
- `docs/architecture/packet_09_integration_completion_report.md`

**Modified:**
- `core/cognitive/planner.py` — one-line bugfix (§0 above)
- `docs/architecture/IMPLEMENTATION_TRACKER.md`, `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md` — documentation only

**Not modified:** `core/cognitive/intent.py`, `core/cognitive/compiler.py`, `core/cognitive/learning.py`, `core/cognitive/user_model.py`, `core/workers/*.py`, `core/workflow/runtime.py`, `core/runtime/*.py`, `core/governance/*.py`, `core/memory/*.py`, `main.py` — all consumed unchanged; `main.py` in particular is confirmed still unwired, per this packet's own explicit non-scope.

---

## §4 — Validation Results

- `pytest tests/test_integration_full_pipeline.py -v` → **20/20 passing**
- `pytest tests/ --continue-on-collection-errors` → **1093/1093 passing**, 4 errors (pre-existing `chromadb` import failures, identical to the baseline immediately before this packet — verified both before and after the `plan()` bugfix)
- Full event trail verified in order (`cognitive.intent_hypotheses_generated` → `cognitive.intent_interpreted` → `cognitive.goal_formed` → `cognitive.constraints_extracted` → `cognitive.capabilities_discovered` → `cognitive.plan_compiled`/`cognitive.plan_rejected`) and independently verified replayable via `EventStream.replay()` against a real SQLite-backed store, with gapless monotonic sequence numbers
- Governance gates (APPROVE/ESCALATE/REJECT) and the clarification bounded-retry progression (ESCALATE × `max_escalations`, then REJECT) both demonstrated against a genuinely pipeline-produced `ExecutionPlan`
- `SupervisorWorker`'s recovery path demonstrated against a real, pipeline-produced, governance-escalated and governance-rejected `CompilationResult`, including confirming no retry is attempted even when a retry-capable input is also present
- All 9 K4 §16 Runtime Invariants individually verified (`TestRuntimeInvariants`, 9 tests)
- No TODO/FIXME/placeholder code; no debug code; no temporary implementations

---

## §5 — Explicitly Not Done (Out of Scope, Per This Packet's Own Definition)

- `main.py` composition-root wiring of `interpret()`/`plan()`/`compile()` — confirmed still absent
- Automatic invocation of `WorkflowRuntime.execute()` after `compile()`, or of `EvaluatorWorker`/`ReflectionWorker`/`SupervisorWorker` after an execution — no autonomous trigger exists anywhere in this repository for any worker or runtime call, and this packet does not add one
- C-MoE capability selection, Execution Runtime hardening/observability, Adaptive Learning — all explicitly marked "architectural placeholders only" in `OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`, not this campaign's job
- This is the last packet in the 01–09 campaign; all dependencies are now satisfied and there is no Packet 10 defined anywhere in the current architecture documents
