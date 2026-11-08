# ADR-KERNEL-09 — Control-plane authorization through the GovernanceKernel (DEBT-025)

**Status:** PROPOSED. Nothing here is ACCEPTED. Acceptance is the owner's call; the open decisions are in §9.
**Date:** Nov 2026.
**Origin:** the owner's decision of Nov 2, 2026 on the review of PR #94: control-plane governance is a **mandatory
follow-up**, with its own design and work item, **not** part of PR #94, and **required before DEBT-025 can close**.
**Related:** PR #94 (authentication boundary; unmerged at the time of writing), `docs/reports/api-exposure-and-auth-boundary-oct2026.md`
(on that PR's branch), DEBT-025 (stays OPEN), LAW 1 "Governance Before Capability".

Evidence tags: `[FACT]` verified by reading or running the code at `main` `2491ae4` (line numbers are for that
commit); `[INFER]` reasoning from verified facts; `[UNKNOWN]` not traced; `[PROPOSED]` a design choice.

> **Claim discipline.** This ADR designs an authorization boundary. It does not implement one, and it does not close
> DEBT-025. Authentication (PR #94) establishes that the caller holds a credential. This ADR is about whether that
> caller may perform a particular operation on a particular resource.

## 1. The owner's requirements (the acceptance criteria)

R1. Every sensitive control-plane operation receives an explicit `GovernanceKernel` authorization decision.
R2. Authorization happens **before any side effect**.
R3. Missing policy, missing identity, or unavailable governance **fails closed**.
R4. Decisions identify the **actor, operation, resource and outcome**.
R5. Tests prove unauthorized requests cannot modify **configuration, modules, imports, training state or update state**.
R6. The first implementation may use a local-owner principal but must be a **genuine authorization boundary**, not a
    pass-through that approves every authenticated request.

## 2. What the code does today

| # | Fact | Evidence |
|---|---|---|
| F1 | The kernel's entry point is synchronous: `evaluate_action(GovernanceAction) -> GovernanceResult` with verdict `APPROVE`, `REJECT` or `ESCALATE`. An exception raised inside a governor is caught and turned into a rejection. | `core/governance/governance_kernel.py:367`, `except Exception` at `:389` `[FACT]` |
| F2 | **The kernel is open by default.** The base `Governor.evaluate` returns `APPROVE` (`:107`-`:117`), and the kernel returns `APPROVE` when no governor objects (`:412`). An action type that no governor recognises is therefore **approved**. This is the opposite of R3. | `:94`-`:117`, `:412` `[FACT]` |
| F3 | `GovernanceAction` has `action_type`, `worker_id` and a free-form `metadata` dict. It has **no actor and no resource field**, so R4 cannot be met without either adding fields or an undocumented metadata convention. | `:49`-`:74` `[FACT]` |
| F4 | The kernel does not write decisions to the `EventStream`. A grep of `core/governance/` for `EventStream` finds only documentation. Decisions are logged through Python logging only. | grep `[FACT]` |
| F5 | The only production caller of `evaluate_action` outside the kernel is `core/orchestrator.py` (`:227` builds the action, `:241` evaluates, `:243` and `:254` handle `REJECT` and `ESCALATE`), plus workers through `AbstractCognitiveWorker`. `interface/api.py` **never** calls the kernel. | grep, `core/orchestrator.py` `[FACT]` |
| F6 | Drift rules restrict who may call the kernel directly: DRIFT-05 (SupervisorWorker) and DRIFT-10 (`core/cognitive/intent.py`, `core/cognitive/planner.py`). The API layer is not restricted by them. | `scripts/check_drift.py:353`, `:573`-`:600` `[FACT]` |
| F7 | `EventStream.append(event_type, *, source, payload)` is async and durable (SQLite, WAL). A database error **propagates to the caller**; subscriber errors are swallowed. The default store path is `.data/events/stream.db`, **relative to the working directory**, not anchored to the project root. | `core/events/event_stream.py` `[FACT]` |
| F8 | After PR #94 the authentication middleware knows only that a valid bearer token was presented. It does not attach an identity to the request, and the handlers do not read one. | `interface/auth.py` on PR #94 `[FACT]` |
| F9 | Nothing in the HTTP layer distinguishes "may read" from "may reconfigure the system". Every authenticated caller reaches every control-plane endpoint. | route table, §3 `[FACT]` |

Consequence `[INFER]`: simply calling `evaluate_action()` from the API would **not** satisfy R3 (F2) and would not record
an actor or resource (F3, F4). A new governor with a default-deny rule for control-plane actions, an explicit identity,
and durable decision records are all required.

## 3. Inventory of control-plane operations

Line numbers: `interface/api.py` and `core/brain_api.py` at `main` `2491ae4` (they shift once PR #94 merges).
"Side effect" is what the handler does after any validation it already has.

| Operation (proposed id) | Route | Handler | Side effect (verified unless marked) | Tier |
|---|---|---|---|---|
| `config.write` | `PUT /config` | `api.py:569` | `config.set(k, v)` for each key in `MUTABLE_CONFIG_KEYS` (includes `global.ollama_host`, `global.web_ui_port`); each call rewrites `config/settings.toml` (`core/config.py:124`-`:133`) | T3 |
| `module.create` | `POST /modules/new` | `api.py:445` | `factory_create(...)` writes a new module directory; `reload_module` loads it. (This route produced RCE-001 / DEBT-026.) | T3 |
| `module.train` | `POST /train/{module_name}` | `api.py:457` | `_scheduler.trigger_module(name)` starts the learning pipeline (internals `[UNKNOWN]`, not traced) | T2 |
| `module.distill` | `POST /distill`, `POST /brain/v2/distill` | `api.py:467`, `brain_api.py:129` | `distill_topic(...)` calls the model and writes training data under `data/` | T2 |
| `brain.export` | `POST /export`, `POST /brain/v2/export` | `api.py:478`, `brain_api.py:145` | `export_module(...)` builds a bundle from a module's weights and data | T3 (data leaves the system) |
| `brain.import` | `POST /import`, `POST /brain/v2/import` | `api.py:485`, `brain_api.py:151` | `import_module(...)` extracts a bundle and registers the module | T3 |
| `update.install` | `POST /update/install` | `api.py:598` | `asyncio.create_task(_do_install_async)`: installs a new version | T3 |
| `update.restart` | `POST /update/restart` | `api.py:624` | schedules `interface/updater.py` `restart()`, which calls `os.execv(sys.executable, ...)` (`updater.py:289`-`:292`) and so replaces the process without a graceful shutdown | T3 |
| `update.rollback` | `POST /rollback` | `api.py:632` | `do_rollback(...)` restores a previous version | T3 |
| `evolve.plan` | `POST /evolve/plan` | `api.py:278` | `upgrade_planner.propose_upgrades()` and `prioritize_upgrades()`; whether these persist anything is `[UNKNOWN]` (not traced) | T2 |
| `execute.query` | `POST /query`, `POST /brain/v2/query` | `api.py:161`, `brain_api.py:107` | runs the orchestrator; **already governed downstream** per worker action (`core/orchestrator.py:227`-`:254`) | T2, see O2 |
| (reads) | `GET /config`, `/debug`, `/dashboard`, `/introspection`, `/events`, `/executions/*`, `/status`, `/health`, `/modules`, `/updates`, `/brain/version`, `/brain/v2/status`, `/brain/v2/version`, `/openapi.json` | various | read-only; `/config` and `/debug` disclose configuration; `/events` streams every bus event | T1 |

Tiers `[PROPOSED]`: **T0** public (`GET /`, `/static/*`, defined in `interface/auth.py`); **T1** read-only, authentication
required; **T2** side-effecting or compute-consuming; **T3** high impact (changes configuration, code, version, or moves
data out). The route-coverage test in §6 makes the table enforceable: a route cannot be added without a tier.

## 4. Proposed design

### 4.1 Principal `[PROPOSED]`
After the bearer token verifies, `ApiAuthMiddleware` attaches an immutable principal to the ASGI scope
(`scope["state"]["principal"]`): `Principal(id="local-owner", kind="bearer-token", auth_mode="required")`. Handlers never
construct a principal. Under the explicit auth opt-out the principal is `Principal(id="unauthenticated-local", kind="none",
auth_mode="disabled")`; what policy applies to it is decision **O1**. A request that reaches a governed handler **without** a
principal is rejected (R3).

### 4.2 `GovernanceAction` gains an actor and a resource `[PROPOSED]`
Add two optional fields with empty-string defaults, `actor: str = ""` and `resource: str = ""`, so existing call sites are
unchanged (F5) and R4 is expressed in the type rather than in a metadata convention (F3). Decision **O4** records the
alternative (metadata keys only).

### 4.3 A new `ControlPlaneGovernor`, default-deny `[PROPOSED]`
A new governor registered with the kernel. It is the answer to F2: for any `action_type` that starts with `control.` it
**rejects unless** the operation is in its policy registry **and** the actor is non-empty **and** the actor is permitted for
that operation **and** the operation's resource check passes. An unknown `control.*` action, an empty actor, or a missing
registry entry is a rejection with a reason code (`no_policy`, `no_identity`, `not_permitted`, `bad_resource`). It has no
opinion (approves) on other action types, so existing behaviour is untouched.
The registry maps operation id to `(tier, permitted principals, resource validator)`. The initial table lives in code.
Config may only **tighten** it (a deny list); config can never grant.

### 4.4 One authorization service, one call site `[PROPOSED]`
`core/governance/control_plane.py` is the only module the API calls. It owns `authorize(principal, operation, resource,
request_id)`, which, in this order:
1. rejects an operation that is not in the registry (`no_policy`) and a missing principal (`no_identity`);
2. builds the `GovernanceAction` (`action_type="control.<operation>"`) and calls `kernel.evaluate_action` inside a guard:
   any exception, or an unavailable kernel, is `governance_unavailable` (R3);
3. **persists the decision to the `EventStream` before returning approval**; if persistence fails the answer is
   `audit_unavailable` and the operation does not run (the same rule the owner set for auth events);
4. returns the decision, or raises `ControlPlaneDenied(code, reason)`.
Keeping the kernel call inside this module means `interface/api.py` still never calls `evaluate_action` directly, which
respects the spirit of DRIFT-05/-10 (F6). Decision **O5** proposes a new drift rule that makes that a checked property.

### 4.5 Enforcement point `[PROPOSED]`
Each governed handler calls `await authorize(...)` as its **first statement that can matter**, before any validation that
touches state and before any task is scheduled, so R2 holds. For background work (`/update/install`, `/update/restart`) the
authorization happens before `create_task` / `call_later`. The call is explicit in the handler (LAW 4: no hidden
dependency injection). Approval for one request is not reusable: nothing is cached across requests.

### 4.6 Decision record `[PROPOSED]`
Every decision, approve or reject, is a `control.decision` event: `decision_id`, `operation`, `resource` (see below),
`actor`, `actor_kind`, `auth_mode`, `tier`, `verdict`, `governor`, `reason_code`, `request_id`, `timestamp`.
`resource` is recorded as identifiers, never contents: for `config.write` the **keys** (not values, which may be URLs or
secrets); for `brain.import` the bundle's base name; for `module.*` the module name. Bearer tokens, `Authorization`
headers and credentials are never recorded.

### 4.7 HTTP mapping `[PROPOSED]`
`REJECT` -> `403 {"detail": {"code": ..., "reason": ...}}` (a reason code, not the policy text). `ESCALATE` -> `403`
`approval_required` (there is no approval channel yet, so it is a denial). Governance or audit unavailable -> `503`
`governance_unavailable` / `audit_unavailable`. All are generic enough not to reveal policy internals.

### 4.8 Initial policy `[PROPOSED]`
`local-owner` is permitted every registered operation, **but only through this boundary**: unknown operations, missing
identity, unavailable governance and unavailable audit are all denied (R3), resource validators apply (for example the
`config.write` key must be in `MUTABLE_CONFIG_KEYS`, a module name must pass the existing identifier checks), and every
decision is durable. No T3 operation escalates by default. This is a real boundary because the failure modes and the
registry are real, not because the first policy is restrictive; R6 is met by the registry, the default-deny governor and
the coverage test, and the table can be tightened without code changes.

## 5. Alternatives considered

| Alternative | Why not |
|---|---|
| Call `evaluate_action()` from each handler and use the existing governors | F2: unknown action types are approved, so a typo or a new operation would be silently allowed |
| A FastAPI dependency (`Depends`) per route | hidden coupling (LAW 4), easy to forget on a new route, and it cannot see the resource before the handler parses it |
| One middleware that authorizes by path | it does not know the resource (config keys, module name, bundle) and runs before the handler's validation |
| Put checks inside the module functions (`config.set`, `factory_create`, ...) | scatters policy, misses direct callers, and the actor is not available there |
| Treat authentication as authorization (status quo after #94) | the very gap DEBT-025 records: any holder of the token can reconfigure, import code and install updates |

## 6. Test plan (maps to R1-R6)

| # | Test | Requirement |
|---|---|---|
| T1 | **Route coverage.** Walk the real route table (`app`, `app.openapi()`, `core/brain_api`): every protected route is either listed as T1 read-only or maps to a registered operation; an unmapped route fails the test. | R1, F9 |
| T2 | **No side effect on denial, per area.** With a deny-all kernel, call each governed route with a valid token and spy on `config.set`, `factory_create`, `reload_module`, `import_module`, `export_module`, `distill_topic`, `trigger_module`, the update installer, restart and rollback. Assert HTTP 403 and **zero** calls. | R2, R5 |
| T3 | **Ordering.** Assert the authorize call happens before the first side effect (call-order recorder), including before `create_task` / `call_later` in the update routes. | R2 |
| T4 | **Missing policy.** An operation absent from the registry, and an unknown `control.*` action, are rejected (`no_policy`). | R3 |
| T5 | **Missing identity.** A governed handler reached without a principal is rejected. | R3 |
| T6 | **Governance unavailable.** Kernel raising, kernel missing, governor raising: all deny with 503/403 and no side effect. | R3 |
| T7 | **Audit unavailable.** An `EventStream` that raises on `append` makes an otherwise approved operation fail with `audit_unavailable` and no side effect. | R2, R3 |
| T8 | **Decision content.** Each decision event carries actor, operation, resource, verdict, governor, reason code, request id; `config.write` records keys but never values; no token or `Authorization` value appears in any persisted payload (searched for the live token). | R4 |
| T9 | **Not a pass-through.** A principal that is not permitted (a test principal, and the opt-out principal under O1's chosen policy) is rejected for the operations the policy withholds. | R6 |
| T10 | **Durability round trip.** Decisions written with a real `SQLiteEventStore` in a temp path are read back by sequence. | R4 |
| T11 | **Fail-before.** Each new test is run against the unmodified code and must fail there. | all |
| T12 | **Mutation review.** Mutants for: governor default flipped to approve, authorize call removed from one handler, authorize moved after the side effect, registry entry removed, audit failure swallowed. All must be killed. | all |

## 7. Compatibility, migration, rollback
- **Compatibility:** `GovernanceAction` gains two defaulted fields (O4); no existing call site changes. The kernel gains a
  governor that approves everything outside `control.*`. Existing clients keep working because the initial policy permits
  the local owner; the visible changes are the `403`/`503` error shapes and the new `control.decision` events.
- **Migration:** none for data. The new events are append-only.
- **Rollback:** revert the implementing PR; no schema or stored state depends on it.
- **Sequencing:** the principal comes from the authentication middleware (PR #94), and durable decision records depend on
  the `EventStream` write path; the owner has approved durable *authentication* events as a separate item (stacked on
  PR #94). This ADR's implementation should follow PR #94, or be stacked on it, and is its own PR.

## 8. Non-goals
Authentication itself (PR #94); a same-user process reading the token file (accepted local-user trust boundary,
documented separately); CSP hardening; a human-approval channel for `ESCALATE`; per-user accounts; moving the event store's
default path to an absolute location (noted in F7, a separate defect).

## 9. Decisions the owner must make
- **O1. Opt-out principal.** With `OCBRAIN_API_AUTH=disabled` there is no credential. (a) The opt-out principal
  `unauthenticated-local` is permitted the same operations as `local-owner`, so the opt-out keeps its meaning and every
  decision is recorded with `auth_mode=disabled`; or (b) it is denied the T3 operations, so the opt-out cannot reconfigure,
  import code or update. R3 says missing identity fails closed; (a) is the more literal reading of "explicit opt-out",
  (b) the stricter one. Recommendation: **(b) for T3, (a) for T1/T2**, so an unauthenticated API can still be used but cannot
  change code, configuration or version.
- **O2. Reads and `execute.query`.** Are T1 reads governed or authentication-only? Recommendation: authentication-only,
  covered by the route-coverage test, with `brain.export` and `/events` treated as T3/T2 respectively. For `/query`,
  authorize the HTTP entry as `execute.query` (cheap, records the actor) in addition to the existing downstream governance.
- **O3. T3 initial verdict.** Allow with audit for `local-owner` (recommended; there is no approval channel), or `ESCALATE`
  (which today means "deny").
- **O4. Actor and resource as fields or metadata.** Recommendation: fields.
- **O5. A new drift rule** forbidding `interface/` from importing the kernel or calling `evaluate_action`, so the single
  call site in §4.4 is a checked property.

## 10. Status
PROPOSED. Not implemented. Nothing in this ADR changes DEBT-025's status: **DEBT-025 stays OPEN** until the requirements
in §1 are implemented and verified, which is outside this document.
