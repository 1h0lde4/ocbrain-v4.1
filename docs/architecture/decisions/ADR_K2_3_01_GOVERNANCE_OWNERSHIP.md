# ADR-K2.3-01: Governance Evaluation Ownership Across the Kernel Runtime

**Status:** DRAFT
**Date:** July 12, 2026
**Author:** K2.3 session (Capability Runtime, Adapter Layer & Resource Binding)
**Scope:** Discussion only, per the K2.3 session prompt's explicit instruction: *"Do NOT change this behavior during K2.3... Architecture changes belong to K3."* This ADR changes no code and no runtime behavior.

---

## 1. Context

The current production request path evaluates governance **twice**:

```
Orchestrator.handle()
    │
    ├─ Governance check #1 (ORCHESTRATOR_ACTION_TYPE) ── before WorkflowRuntime is even reached
    │
    ▼
WorkflowRuntime.execute()
    │
    ▼
ExecutionRuntime.invoke(worker_type="PlannerWorker")
    │
    ▼
PlannerWorker.execute()  ←  AbstractCognitiveWorker's template method
    │
    ├─ Governance check #2 (worker_execute) ── structurally guaranteed, can't be bypassed
    │
    ▼
PlannerWorker._run()
```

This was identified in the K2.2 Cutover Report (§3) and confirmed by direct code read: `RecursionGovernor` and `BudgetGovernor` are stateless per call — all state lives in the caller-supplied `GovernanceAction`, not in the governor object (see the `BUG-03` fix comment in `core/governance/governance_kernel.py`, which documents exactly why this statelessness was made explicit). Two evaluations of the same logical request therefore do not double-count budget or recursion depth against each other; they are two independent checks against two independently-constructed `GovernanceAction`s.

K2.3 adds a **candidate third touchpoint**: `AdapterRuntime.invoke()`, which selects and executes a capability Adapter. This ADR was written specifically because K2.3 needed to decide whether to add governance evaluation there — and decided not to, pending this review (§5).

---

## 2. Current Ownership

| Layer | Governance call | `action_type` | Triggered by |
|---|---|---|---|
| `Orchestrator.handle()` | `governance.evaluate_action()` | `orchestrator_handle` (`ORCHESTRATOR_ACTION_TYPE`) | Every incoming query, before any dispatch |
| `AbstractCognitiveWorker.execute()` | `governance.evaluate_action()` | `worker_execute` | Every Worker invocation via `ExecutionRuntime.invoke()`, structurally guaranteed by the template method — cannot be bypassed by a Worker subclass |
| `AdapterRuntime.invoke()` (new, K2.3) | **None** | — | Not evaluated. See §5. |

Both existing checks use `GovernanceKernel.evaluate_action()`, which iterates registered governors (`RecursionGovernor`, `BudgetGovernor`, `EvolutionGovernor`) and terminates on the first `REJECT`/`ESCALATE` (per that method's own docstring).

---

## 3. Advantages of the Current (Dual) Ownership

- **Defense in depth, not redundancy.** The two checks answer different questions at different points in the causal chain: "should this request be admitted at all" (Orchestrator, before any resource is committed) vs. "should this specific worker execution proceed" (Worker template method, immediately before the governed unit of work runs). A future workflow with multiple nodes would have the second check fire once per node, which is the correct granularity — governance visibility scales with capability, per Kernel Constitution Law of Bounded Autonomy ("Governance visibility must grow at least as fast as capability").
- **Structural guarantee, not convention.** Because the Worker-level check lives inside `AbstractCognitiveWorker.execute()`'s template method, no Worker subclass — including ones written by future sessions or by SkillCreator-style autonomous authoring — can accidentally skip it. Removing the Orchestrator-level check would leave only this one, which is fine for compliance but removes the fast-fail benefit below.
- **Fail-fast at low cost.** The Orchestrator-level check runs before `BackpressureGuard` and before any WorkflowRuntime/ExecutionRuntime object is touched — a rejected request costs one governor evaluation, not a partially-constructed execution context.
- **Statelessness makes duplication safe.** Because governors hold no cross-call state (§1), evaluating twice has no correctness cost — only a (small, unmeasured) latency cost of one extra governor pass.

## 4. Disadvantages of the Current (Dual) Ownership

- **No single source of truth for "was this request governed."** An event-log reader (or a future auditor) sees two separate governance-evaluation events per request with different `action_type`s and has to know both exist to reconstruct the full picture — this is a mild violation of the spirit of Law of Single Source of Truth, even though it's not a correctness bug.
- **Latent scaling risk if a future governor is *not* stateless.** §1's safety argument depends entirely on `RecursionGovernor`/`BudgetGovernor`/`EvolutionGovernor` staying stateless. Nothing currently enforces that a future governor must be. A stateful governor (e.g., a true sliding-window rate limiter keyed by wall-clock time rather than caller-supplied counters) would silently double-count under the current dual-evaluation design, and nothing in the codebase would catch this at review time — it is a convention, not an invariant.
- **Cost scales linearly with layers, not with actual risk.** K2.3 already had to explicitly decide *not* to add a third check in `AdapterRuntime` (§5) specifically because the existing two-layer pattern, if mechanically repeated at every new layer, would keep growing the number of evaluations per request without a clear stopping rule.
- **Two `action_type` strings to keep in sync mentally** (`orchestrator_handle`, `worker_execute`) when reasoning about what a given governor rule actually applies to — a governor rule scoped by `action_type` string matching has to be written and tested against both, or explicitly against one, and that scoping isn't visible from either call site alone.

---

## 5. K2.3's Own Decision: No Third Touchpoint in AdapterRuntime

`AdapterRuntime.invoke()` was built this session with **no** governance evaluation of its own. This was a deliberate choice, not an oversight, made for two reasons:

1. **The K2.3 prompt's explicit instruction** — *"Do NOT change this behavior during K2.3... Architecture changes belong to K3"* — reads most naturally as "don't touch governance ownership this session," and adding a new evaluation point inside a brand-new runtime service is exactly the kind of change that should be reviewed deliberately (this ADR) before being adopted, not introduced as a side effect of building the service.
2. **It's ambiguous, on the evidence available this session, whether adapter-level governance is even the right grain.** `AdapterRuntime.invoke()` may try 2-3 adapters in sequence per call (the fallback chain) — should governance evaluate once per capability *request*, or once per *adapter attempt*? The Worker-level precedent (§2) evaluates once per Worker invocation, which is a cleaner analogy to "once per request" than to "once per attempt." Deciding this without evidence from real adapter-fallback traffic would be exactly the kind of preference-driven change the Kernel Constitution's Law of Evidence over Assumption warns against.

**Recommendation for K3, not decided here:** if adapter-level governance is added, it should evaluate once per `AdapterRuntime.invoke()` call (i.e., once per capability request), not once per adapter attempt within the fallback loop — matching the Worker-level grain, and avoiding a rejected request being evaluated 2-3 times as it cycles through fallback adapters.

---

## 6. Recommended Future Consolidation

Not a proposal to act on now (K3+ only, per the prompt's own deferral). Two credible directions, presented as alternatives rather than a single recommendation, since choosing between them needs evidence this session doesn't have:

**Option A — Keep dual evaluation, formalize it.** Document `orchestrator_handle` and `worker_execute` as the two canonical governance checkpoints in the Kernel Architecture spec itself (they currently exist in code but aren't named as a deliberate two-checkpoint design anywhere). Add a lightweight invariant check (e.g., a governor-authoring guideline, enforced by review or a simple static check) that any new governor must declare whether it is safe to evaluate more than once per request — turning §4's "latent risk if a future governor isn't stateless" from an implicit assumption into an explicit, checkable contract.

**Option B — Consolidate into a single, request-scoped governance evaluation, threaded through `ExecutionContext`.** Evaluate once, at the earliest point a request is fully formed (arguably `Orchestrator.handle()`, after parsing but before dispatch), attach the resulting `GovernanceResult` to `ExecutionContext`, and have `AbstractCognitiveWorker.execute()` (and, if adopted, `AdapterRuntime.invoke()`) *consult* that attached result rather than re-evaluating from scratch. This would give genuinely single-source-of-truth governance per request, at the cost of a real design question: what happens when a nested Worker's own risk profile differs from the outer request's (e.g., a `SupervisorWorker` delegating to a higher-risk `CoderWorker` sub-task)? Flattening to one evaluation risks under-governing exactly the case (delegation depth, per Constitution Invariant 1) governance exists to catch.

**Migration strategy, either option:** whichever direction K3 chooses, the migration should be additive-then-subtractive (Law of Contract Stability, deprecation-window pattern already established in this project's Kernel Constitution) — introduce the new mechanism alongside the existing dual-check behavior, verify parity on real traffic, then remove the redundant check. Not a single-PR cutover.

---

## 7. Non-Decision

This ADR does not choose between Option A and Option B, does not add or remove any governance evaluation point, and does not change `AdapterRuntime`, `Orchestrator.handle()`, or `AbstractCognitiveWorker.execute()`. It exists to make the current state, its trade-offs, and the specific new question K2.3 encountered (§5) explicit and reviewable, per the K2.3 session prompt's instruction. Status remains `DRAFT` pending human review; promotion to `REVIEW`/`APPROVED` follows the project's existing five-status ADR lifecycle.
