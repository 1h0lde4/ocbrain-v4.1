# ADR-CAP-02: Descriptor, Status, Lifecycle and Provenance Model

**Status:** DRAFT
**Date:** September 2026
**Author:** Capability Foundation mission ("mission 1"). Same branch and
review status as ADR-CAP-01 — **not reviewed, not merged.**
**Scope:** `core/capabilities/descriptors.py` (new),
`core/capabilities/capability.py`, `core/capabilities/registry.py`,
`core/capabilities/adapter_runtime.py`, `core/workflow/definition.py`,
`core/workflow/runtime.py`.

---

## 1. Context

ADR-CAP-01 establishes the taxonomy. This ADR is the mechanical decision:
how the existing K2.3 capability runtime (`CapabilityContract`,
`CapabilityRegistry`, `AdapterRuntime`, `CapabilityResult`) is extended to
carry that taxonomy, without breaking anything that already depends on it.

Three concrete gaps existed, verified by direct reading before any code was
written:

1. **`CapabilityResult.success: bool`, `error: str` was the entire failure
   vocabulary.** A capability could not distinguish "the input was
   unsupported", "the input was malformed", "a dependency is missing", "the
   result is legitimately empty", or "a resource limit was hit" from a plain
   adapter fault — all of which the mission prompt's §24 requires to be
   distinguishable, and none of which should count against an adapter's
   health the way a real fault should (`AdapterRuntime._mark_failure`/
   `_mark_success` already existed and already influences adapter ranking).
2. **`CapabilityRegistry` had no lifecycle.** An adapter, once registered,
   could not be marked unavailable/deprecated/retired without physically
   removing it, and there was no `deregister_adapter` at all — replacing an
   implementation meant either leaving the old one registered alongside the
   new one or hand-mutating the registry's private dict from outside.
3. **`WorkflowRuntime` never handed a node its predecessors' results.**
   Verified directly in `_execute_node_with_retry`'s call site and the
   `WorkerContext`/`ExecutionContext` construction: `node_results` was
   collected by the runtime for its own bookkeeping (retry decisions,
   `WorkflowResult.outputs`) but never passed to the next node. A multi-step
   `ExecutionPlan` therefore executed as N independent single-step calls,
   not a pipeline — verified against `tests/test_runtime_integration.py`'s
   own multi-step fixtures, none of which asserted on cross-step data flow.
   Composition (mission §28) is impossible without this.

## 2. Decision

Everything below is **additive**: every new field has a default that
reproduces pre-existing behavior exactly, so no code written before this
branch changes behavior. The one exception (adapter registration can now
raise `CapabilityRegistrationError`) is scoped to fail *only* when an
adapter *explicitly declares* an incompatibility — an adapter that declares
nothing is unaffected (§2.2).

### 2.1 Status vocabulary (`descriptors.CapabilityStatus`)

A closed set of machine-readable outcome strings:
`ok`, `partial`, `degraded`, `empty` (success); `unsupported`, `malformed`,
`unreadable`, `dependency_unavailable`, `invalid_request`, `limit_exceeded`,
`unavailable`, `timeout`, `cancelled`, `failed` (not success).
`CapabilityResult` gains `status: str = ""`; when unset, `__post_init__`
derives it from `success` (`ok`/`failed`), so `CapabilityResult(success=True)`
— every pre-existing construction site — is unaffected. When set, `success`
and `status` are cross-checked at construction (`ValueError` on
disagreement) so the two can never silently diverge. `CapabilityResult.of(
status, ...)` is the new preferred constructor: it derives `success` from
`status`, so a caller cannot accidentally write a status/success pair that
disagrees.

**Request-level vs. adapter-fault statuses** (`REQUEST_LEVEL_STATUSES` /
`FALLTHROUGH_STATUSES` in `descriptors.py`): `unsupported`, `malformed`,
`unreadable`, `dependency_unavailable`, `invalid_request` and
`limit_exceeded` describe *the request*, not a fault of the adapter that
answered it. `AdapterRuntime.invoke()` never applies a health penalty for
these. Of those, only `unsupported` and `dependency_unavailable` fall
through to the next registered adapter (a different implementation might
still handle it); the rest are returned immediately, because a
malformed/oversized/invalid request will not become valid by trying a
different implementation of the same capability.

This distinction exists specifically so one hostile or malformed input
cannot degrade a shared adapter's health ranking for every other caller —
verified by
`tests/capability_foundation/test_file_reading.py`'s malformed-artifact
cases and the conformance suite's
`test_the_checker_actually_catches_violations::BadRequestIsFault`, which
asserts the checker *fails* an implementation that reports a bad request as
a plain `success=False` adapter fault.

### 2.2 Contract, operation and adapter identity (`CapabilityContract`,
`OperationSpec`, `BaseAdapter`)

- `CapabilityContract` gains `operations: Tuple[OperationSpec, ...] = ()`,
  `default_operation: str = ""`, `side_effects: str = UNSPECIFIED`.
  `get_operation(name="")` resolves the named operation, or the declared
  default, or (for a legacy contract with no declared operations) `None` —
  a legacy contract with `operations=()` behaves exactly as before it had
  this field, because `AdapterRuntime.invoke()` only performs operation
  resolution/validation when `contract.operations` is non-empty.
  `structural_problems()` validates the descriptor set itself (duplicate
  operation names, a `default_operation` that names nothing declared,
  invalid `side_effects`) and is checked at `register_capability()` time —
  a malformed contract fails at registration, not silently at first
  invocation.
- `BaseAdapter` gains three **optional** attributes read only via
  `getattr()` with a default that reproduces "declares nothing":
  `adapter_version`, `implements_contract` (the contract major/minor this
  adapter targets), `supported_operations`. None is added to the `Adapter`
  Protocol itself — doing so would break `isinstance()` for every existing
  structural (duck-typed) Adapter that doesn't happen to define them.
- `CapabilityRegistry.register_adapter()` now checks, **only when an
  adapter declares** `implements_contract`, that its major matches the
  contract's major (`descriptors.contract_major`/`implements_contract_
  major`) — a version-incompatible adapter is refused at registration with
  a `CapabilityRegistrationError`, not silently paired with a contract its
  author never targeted. When an adapter declares `supported_operations`,
  those names must be a subset of the contract's declared operations. An
  adapter that declares neither (every adapter written before this branch)
  is accepted exactly as before — confirmed by
  `tests/test_capabilities.py`/`test_capability_discrimination.py` passing
  unmodified (42/42).
- `deregister_adapter(capability_type, adapter)` (by `adapter_name` string
  or by instance) removes exactly one registered implementation, leaving
  the capability's contract and identity untouched. Replacing an
  implementation is `register_adapter(new)` + `deregister_adapter(old)` —
  no other path exists or is needed (mission §10, §52).

### 2.3 Lifecycle (`descriptors.CapabilityLifecycle`,
`CapabilityRegistry._lifecycle`)

Four states — `active`, `deprecated`, `disabled`, `retired` — held in the
registry (runtime state) rather than on `CapabilityContract` (declarative
metadata), so setting a capability's lifecycle never mutates a contract
object some other code may already be holding a reference to. Absent entry
= `active` (today's only behavior). `disabled`/`retired` are not
discoverable and not invocable (`AdapterRuntime.invoke()` returns
`unavailable` before touching any adapter); `retired` is terminal —
`set_lifecycle()` refuses to move a retired capability to any other state.
`discover_capabilities()` (`core/cognitive/planner.py`) skips a
non-discoverable capability, guarded by `getattr(registry,
"is_discoverable", None)` so a test double with no lifecycle support
(reporting every capability `active` implicitly) is unaffected.

### 2.4 Provenance (`CapabilityResult.provenance`)

A dict `AdapterRuntime.invoke()` stamps on every result — success, decline,
or failure with enough information to be useful
(`capability_type`, `operation`, `contract_version`, `trace_id`, and, once
an adapter actually ran, `adapter: {name, version}`). Stamped **after** an
adapter's own `execute()` returns, overwriting any of those same keys the
adapter set, so a capability implementation cannot spoof its own identity
in provenance — the runtime is the sole authority on which adapter and
contract version actually served a request. An adapter may add its own
*implementation* facts (reader identity, model/provider, source locators)
under other keys; those are never overwritten.

### 2.5 Machine-readable discovery surface (`CapabilityRegistry.describe()`
/ `describe_all()`, `find_consumers()`/`find_producers()`)

`describe(capability_type)` assembles a JSON-serializable projection
(identity, contract version, operations with structured I/O, lifecycle,
registered implementations and their declared versions/availability) purely
from existing registry state — no second store. `find_consumers(value_type)`
/ `find_producers(required_type)` answer "which operations can structurally
accept/produce this `TypeSpec`" using `TypeSpec.accepts()` (semantic-type
match, overlapping media types, matching schema major) — structural
compatibility only, never ranking, scoring or selection (verified by
`test_descriptors_and_structured_queries_rank_and_select_nothing`, which
scans every key `describe_all()`/`find_consumers()` produce for
ranking-shaped vocabulary and asserts none exists). This exists so a future
selector (C-MoE) or UX has something other than prose to query — mission
§30, §31 — without this branch becoming that selector.

### 2.6 Direct-predecessor result handoff
(`WorkflowDefinition.get_predecessors`, `WorkflowRuntime`)

`WorkflowDefinition.get_predecessors(node_id)` — direct predecessors only,
edge order, no duplicates, mirroring the existing `get_successors()`.
`WorkflowRuntime._execute_node_with_retry()` gains an `upstream_results`
parameter: the `WorkerResult`s of the node's direct predecessors that both
completed and **succeeded** (a failed predecessor's result is not handed
forward — a downstream node sees only trustworthy inputs or none). Delivered
to the worker via `context.metadata["upstream_results"]`, assigned **after**
`**metadata` is spread, so a node's own run-level metadata cannot spoof what
"upstream" contains — the runtime alone decides which predecessor results a
node receives, sourced from the DAG it is actually executing, never from
caller-supplied metadata. A node that ignores `upstream_results` (every node
type that existed before this branch) behaves exactly as before.

## 3. Consequences

- `tests/test_capabilities.py`, `test_capability_discrimination.py`,
  `test_workflow_runtime.py`, `test_runtime_integration.py`,
  `test_integration_full_pipeline.py`, `test_k2_4_governance.py`,
  `test_planner_capability_migration.py`, `test_execution_runtime.py`,
  `test_check_drift.py`, `test_supervisor_worker.py`,
  `test_evaluator_worker.py`, `test_debt_020_false_completion.py`,
  `test_model_router.py`, and `tests/core/` all pass unmodified on this
  branch (827 passed / 1 pre-existing, unrelated CTX-AUTH-001b failure —
  confirmed present on `main` before this branch, see the closing report).
  `scripts/check_drift.py`: 15/15 PASS.
- A future capability with real operations, versioned contracts and
  multiple implementations has a place to declare all of that without
  inventing new mechanism — it reuses exactly this.
- `WorkflowRuntime` now does more work per node (predecessor lookup +
  filtering) — O(edges) per node, the same order as the existing
  `get_successors()` call already on this path; no new async boundary, no
  new failure mode introduced (a node with zero eligible predecessors
  simply receives `{}`, identical to before this branch).
- `deregister_adapter` and lifecycle transitions are new *capabilities* of
  the registry that nothing in production calls yet — they exist for the
  replace-an-implementation and disable-without-losing-history stories the
  mission prompt requires (§35, §36, §52), not because any current adapter
  needs replacing today.

## 4. Alternatives considered

- **A separate `CapabilityFailureReason` enum layered on top of
  `core/runtime/execution_outcome.py`'s existing `FailureType`**, rather
  than a new `CapabilityStatus` vocabulary — rejected: `FailureType` is a
  *worker*-level concept (it already covers things capabilities don't need,
  like recursion-depth and budget failures) and has no way to express
  "unsupported" or "legitimately empty" at all. Mapping capability outcomes
  onto worker-level `FailureType` at the `capability_steps.py` boundary
  (which does happen — see ADR-CAP-01's step-worker note) was judged
  cleaner than trying to extend `FailureType` itself, which is shared,
  frozen-adjacent vocabulary this mission has no mandate to change.
- **Mutating `CapabilityContract` in place for lifecycle** instead of a
  separate registry-held record — rejected: a contract object is meant to
  be a stable, comparable, potentially-shared value; mutating it after
  other code has already read/cached it is exactly the kind of hidden
  mutable state PROJECT_INSTRUCTIONS.md's Forbidden Practices list warns
  against.
- **Passing every ancestor's results (not just direct predecessors)**
  downstream — rejected: this would let a node see sibling-branch or
  unrelated results never declared as its own dependency, breaking the
  "data flow follows the declared DAG" property replay and observability
  depend on. Direct predecessors only, exactly as the DAG declares.
- **A capability-level cache keyed by `read_key`** — deferred, not built:
  `FileReadingAdapter._prov()` already computes and records a
  content-hash-derived `read_key` in provenance for exactly this future use,
  but no cache exists yet (mission §21's "do not build a general cache...
  unless the capability work genuinely requires a minimal extension" — it
  does not, yet).
