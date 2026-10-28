# API exposure and authentication boundary (DEBT-025)

**Date:** Oct 27, 2026. **Baseline:** `main` `f13bfdefcdd197ed1f966de0b1f93037a4168af4`.
**Status of this document:** the exposure facts below were established against the live code at that baseline
(VERIFIED = traced or executed, as marked). The design decisions are IMPLEMENTED on the branch that carries this
file; none is an owner ruling yet (PENDING). DEBT-025 is **not closed** by this change (see section 6).

## 1. Exposure, as established

| # | Fact | Evidence | Status |
|---|---|---|---|
| E1 | The only server launch path binds `127.0.0.1`, hard-coded; only the port is configurable (`global.web_ui_port`). There is no host setting. | `main.py:456-461` | VERIFIED (read) |
| E2 | The repository ships no Dockerfile or compose file and no other `uvicorn.run`/`serve` call outside tests and docs. | `grep -rn "uvicorn\.\(run\|Config\|Server\)"`, file listing | VERIFIED (grep) |
| E3 | `interface.api:app` is an importable ASGI app. Anyone can serve it on any address (`uvicorn interface.api:app --host 0.0.0.0`), put a proxy in front of it, or forward the port. The hard-coded bind in E1 is therefore a property of one launcher, **not** a boundary of the API. | code structure; E2 | VERIFIED (reasoning from E1/E2) |
| E4 | Before this change there was no authentication on any route. The only request gate was `CSRFHeaderMiddleware`: non-safe methods need the header `X-OCBrain-Local`. Its value is not checked and is the same constant in the CLI and the web UI, so it is anti-CSRF, not authentication. | `interface/api.py` (middleware), `interface/cli.py`, `interface/web/*.html` | VERIFIED (read) |
| E5 | No CORS middleware is installed, so cross-origin browser pages cannot read responses. | `grep -rn CORSMiddleware` finds nothing | VERIFIED (grep) |
| E6 | The runtime route table has 34 (method, path) pairs: 29 behind the token, 5 public (see section 3), plus the `/static` mount. The table is below and is enforced by a test, not by this document. | runtime introspection of `app`, `app.openapi()` and `register()` from `core/brain_api.py` | VERIFIED (executed) |
| E7 | `web/wizard.html` calls `/api/wizard/*`. No such route exists in the Python code. Those calls cannot succeed today, with or without authentication. | `grep -rn wizard --include=*.py` | VERIFIED (grep); out of scope here, flagged |

### Who can reach the port, and what the boundary changes

| Actor | Before | After |
|---|---|---|
| Remote host | Unreachable only because of E1 (single launcher). Reachable through E3 with full control-plane access. | Needs the token. |
| Another OS user on the same machine | Full access (loopback is not per-user). | Needs the token; the token file is mode 0600, so a different user cannot read it (POSIX). |
| A web page in the user's browser, via DNS rebinding to `127.0.0.1` | Same-origin after rebinding, so the custom header is allowed: full access. | Needs the token, which the page cannot know. |
| A cross-origin page, ordinary CSRF | Blocked by the custom header (E4/E5). | Unchanged, and now also needs the token. |
| A process running as the **same user** as OCBrain | Full access. | **Unchanged in effect:** it can read the token file. This boundary does not defend against it. |

## 2. Decisions (all IMPLEMENTED on this branch; owner ruling PENDING)

| ID | Decision | Why | Reopen if |
|---|---|---|---|
| A1 | **Default-on bearer token on every route that is not explicitly public.** `Authorization: Bearer <token>`. | E3: the bind is not a boundary. Loopback does not separate local users or defeat DNS rebinding. Default-on keeps the safe case the zero-configuration case. | The owner rules loopback-only is the accepted trust model. Then flip the default and keep the code. |
| A2 | **Deny by default, with a pinned allowlist.** Public: `GET`/`HEAD` of `/`, `/static/*`, `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`. `/health` is **not** public. | A new route is protected without anyone remembering to protect it. `tests/test_api_auth_boundary.py` pins the allowlist and walks the real route table. | A liveness probe needs an unauthenticated endpoint. Add a minimal one deliberately. |
| A3 | **Pure ASGI middleware, outermost**, not a per-route `Depends`. | Explicit (LAW 4), runs before routing so unknown paths give 401 not 404, and does not buffer SSE streams. Rejection happens before CSRF, routing or any handler. | - |
| A4 | **One per-installation secret.** `OCBRAIN_API_TOKEN`, else `data/api_token` (or `OCBRAIN_API_TOKEN_FILE`), generated with `secrets.token_urlsafe(32)` and created `O_EXCL` mode 0600. A shorter-than-32 token is refused, not regenerated. A group/other-readable file is tightened to 0600 (or refused). Constant-time compare. | LAW 5: local, no external dependency. Never hard-coded, never logged, never in an event (section 14.2). | - |
| A5 | **Opt-out is explicit and loud:** `OCBRAIN_API_AUTH=disabled` or `global.api_auth = "disabled"`. Any other value, a typo included, means required. Announced by a WARNING and an `api.auth_disabled` event. `global.api_auth` is not in `MUTABLE_CONFIG_KEYS`, so `PUT /config` cannot turn it off. | The previous posture stays available to anyone who accepts it, without being the default. | - |
| A6 | **Denials are audited:** WARNING log and `api.auth_denied` event with reason (`missing`/`malformed`/`ambiguous`/`invalid`), method, sanitised path, client address. Never the credential. The HTTP body is a generic 401. | LAW 2 and the audit-logging requirement of LAW 1. | - |
| A7 | **Misconfiguration fails closed:** unusable token configuration aborts `setup()` at startup and returns 503 (never "open") if it arises at request time. | Fail closed. | - |
| A8 | **Clients carry the token:** CLI reads env or token file. The tray opens the UI with `#token=` in the URL fragment (never sent to the server). `web/auth.js` keeps it in `sessionStorage`, strips it from the address bar, prompts once on a 401. `EventSource` cannot send headers, so the page's one SSE stream uses a `fetch`-based reader (`ocEventStream`). | The product must keep working with the boundary on. | - |

Rejected: cookie sessions (more state and a CSRF surface for no gain on one machine); a `?token=` query parameter
(leaks into logs and history); relying on the bind address alone (E3); partial protection of only the mutating
routes (reads such as `/config`, `/debug` and `/executions/*` are sensitive too); an auth middleware that fails open
when unconfigured (the direct-`uvicorn` case in E3).

## 3. Route table (generated; the test is the authority)

Public (5, plus the `/static/` mount): `GET /`, `GET /docs`, `GET /docs/oauth2-redirect`, `GET /openapi.json`, `GET /redoc`.

Token required (29): `GET /status`, `/health`, `/modules`, `/config`, `/debug`, `/dashboard`, `/introspection`,
`/events`, `/updates`, `/executions/{id}`, `/executions/{id}/events`, `/brain/version`, `/brain/v2/status`,
`/brain/v2/version`; `PUT /config`; `POST /query`, `/train/{module}`, `/distill`, `/export`, `/import`, `/modules/new`,
`/evolve/plan`, `/rollback`, `/update/install`, `/update/restart`, `/brain/v2/query`, `/brain/v2/distill`,
`/brain/v2/export`, `/brain/v2/import`.

## 4. Operating it

* Find the token: `data/api_token` (created at first start; the path is logged, the value never is).
* Use it: `curl -H "Authorization: Bearer $(cat data/api_token)" http://127.0.0.1:7437/status`.
* CLI: works unchanged if it runs as the same user. Otherwise set `OCBRAIN_API_TOKEN`.
* Rotate: delete `data/api_token` and restart (the token is read once per process, so there is no hot rotation).
* Browser: open via the tray (supplies the token), or paste it at the prompt. Direct `uvicorn interface.api:app`
  users get the same boundary and read the token from the same file.
* Tests opt out through one autouse fixture in `tests/conftest.py`; `tests/test_api_auth_boundary.py` re-enables it.

## 5. Interaction with other work

* The control-plane **authorization** question is separate and stays open: an authenticated caller can still
  reach `/update/*`, `/config`, `/import`, `/export`, `/distill` and `/rollback`, none of which call
  `GovernanceKernel` (DEBT-025 item 1 of the Sept 16 addendum). Authentication is not authorisation.
* CTX-EXPORT-001 / `import_module()` was "bounded only by localhost-bind + CSRF middleware". It is now also behind
  the token. The path-containment fixes are unchanged.

## 6. Residual scope (explicit; DEBT-025 stays OPEN)

1. Same-user processes can read the token file (section 1). A different mechanism (OS keyring, per-process
   credentials) would be a separate decision.
2. The docs trio and the HTML shell are public by decision A2. They disclose the route inventory and nothing else.
3. No lockout or rate limit on failed attempts (a 256-bit token is not guessable; log volume is unbounded).
4. On Windows, POSIX modes do not apply: the 0600 property is not enforced there.
5. The tray's `#token=` URL may stay in the user's local browser history.
6. `sessionStorage` is readable by any script on the page; the UI's own XSS exposure was not audited here.
7. Control-plane governance (section 5) and `/health` for external monitors are unresolved by design.
8. `web/wizard.html` targets routes that do not exist (E7).
