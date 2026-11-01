# API exposure and authentication boundary (DEBT-025)

**Dates:** first written Oct 27, 2026; revised Oct 31, 2026 after the PR #94 review.
**Status of this document:** the exposure facts below were established against the live code (VERIFIED = traced
or executed, as marked). The design decisions are IMPLEMENTED on the branch that carries this file.
**A1 (default-on authentication) was ACCEPTED by the owner on Oct 28, 2026.** Decisions A2-A14 were
authorised as a remediation plan on Oct 31, 2026 and remain open to the owner's review.
**DEBT-025 is not closed** (section 7).

## Corrections to the first version of this report
Review of the first version found three statements that were wrong or incomplete; they are corrected here and
the fixes are below.
1. "The docs trio is schema only." Wrong: `/docs` and `/redoc` loaded scripts from `cdn.jsdelivr.net` into the
   same origin as the UI and its `sessionStorage` token. They are now disabled (A2).
2. "A page using DNS rebinding needs the token, which it cannot know." Incomplete: the `Host` header was never
   validated, so after rebinding the genuine shell and its token prompt loaded under the attacker's origin, and a
   user who typed the token into that prompt gave it to the attacker's page. Closed by A9.
3. "The tray hands the token over in the URL fragment, never sent to the server." True of HTTP, but the whole URL is
   an argument of the browser launcher process, readable by every local user (`/proc/<pid>/cmdline`, `ps`).
   Reproduced with an unprivileged uid; removed by A11.

## 1. Exposure, as established

| # | Fact | Evidence | Status |
|---|---|---|---|
| E1 | The only server launch path binds `127.0.0.1`, hard-coded; only the port is configurable (`global.web_ui_port`). There is no host setting. | `main.py` (uvicorn call) | VERIFIED (read) |
| E2 | The repository ships no Dockerfile or compose file, and no listener other than that uvicorn call exists outside tests and docs. | `grep -rn "uvicorn\|start_server\|HTTPServer\|socket.bind"` | VERIFIED (grep) |
| E3 | `interface.api:app` is an importable ASGI app. It can be served on any address (`uvicorn interface.api:app --host 0.0.0.0`), put behind a proxy, or forwarded. The hard-coded bind is a property of one launcher, **not** a boundary of the API. | code structure; E2 | VERIFIED (reasoning from E1/E2) |
| E4 | Before this change there was no authentication on any route. The only request gate was `CSRFHeaderMiddleware`: non-safe methods need the header `X-OCBrain-Local`. Its value is not checked and is the same constant in the CLI and the web UI: anti-CSRF, not authentication. | `interface/api.py`, `interface/cli.py`, `interface/web/*.html` | VERIFIED (read) |
| E5 | No CORS middleware is installed, so cross-origin browser pages cannot read responses; a cross-origin preflight is rejected. | `grep -rn CORSMiddleware`; real-browser run | VERIFIED (grep, executed) |
| E6 | Runtime route table at this revision: 31 (method, path) pairs: 30 protected and 1 public (`GET /`), plus the `/static/` mount. Enforced by a test that walks the real route table and the `/brain/v2` router. | `app`, `app.openapi()`, `core/brain_api.register()` | VERIFIED (executed) |
| E7 | `web/wizard.html` calls `/api/wizard/*`. No such route exists in the Python code. | `grep -rn wizard --include=*.py` | VERIFIED (grep); out of scope, flagged |
| E8 | The `Host` header was not validated: `Host: evil.example:7437` got 200 for `/`, `/static/auth.js` and `/openapi.json`. | live request, pre-fix | VERIFIED (executed) |
| E9 | In a PyInstaller `--onefile` build the default token path (`Path(__file__)/../data/api_token`) resolved inside the per-run `_MEI…` temp directory: a new token each start, invisible to a separate process. | throwaway Linux build, run twice | VERIFIED (executed, Linux only) |
| E10 | In a packaged install the binary named `ocbrain` is the server (`main.py`), not the CLI; in a pip install `ocbrain` is the click CLI. | `install/build.py`, the deb/service file, `pyproject.toml` | VERIFIED (read) |
| E11 | The CLI group's optional `QUERY` argument swallowed the first token under click 8.5: `ocbrain status` posted the text "status" to `/query`. Pre-existing on `main`. | pristine `main`, `CliRunner` | VERIFIED (executed) |

### Who can reach the port, and what the boundary changes

| Actor | Before | After |
|---|---|---|
| Remote host | Unreachable only because of E1. Reachable through E3 with full control-plane access. | Needs the token, and a `Host` that names this machine (or an explicitly allowed name). |
| Another OS user on the same machine | Full access (loopback is not per-user). | Needs the token; the token file is owner-only (0600; owner-only ACL on Windows), and the token is never on a command line. |
| A web page via DNS rebinding to `127.0.0.1` | Same-origin after rebinding: full access, and the shell and token prompt reachable. | Refused by the `Host` allowlist before anything is served (A9); the token is still required for every API route. |
| A cross-origin page, ordinary CSRF | Blocked by the custom header (E4/E5). | Unchanged, and now also needs the token. |
| A process running as the **same user** as OCBrain | Full access. | **Unchanged in effect:** it can read the token file. Not defended against. |

## 2. Decisions
All IMPLEMENTED. "Owner ruling" is the state of the owner's own decision.

| ID | Decision | Owner ruling |
|---|---|---|
| A1 | **Default-on bearer token on every route that is not explicitly public.** Loopback binding alone is not an adequate boundary. `/health` stays protected. The opt-out stays explicit and auditable. | **ACCEPTED** (Oct 28) |
| A2 | **Deny by default, pinned allowlist: `GET`/`HEAD` of `/` and `/static/*` only.** The interactive docs are disabled; the schema at `/openapi.json` needs the token. | authorised plan (Oct 31); docs-disabled was chosen over self-hosting the docs UI, reversible |
| A3 | **Pure-ASGI middleware, outermost.** Runs before routing (unknown paths give 401, not 404) and does not buffer SSE. Rejection happens before CSRF, routing or any handler. | authorised plan |
| A4 | **One per-installation secret**: `OCBRAIN_API_TOKEN`, else the token file; `secrets.token_urlsafe(32)`, `O_EXCL`, owner-only; under 32 characters refused; constant-time compare; never logged, never in an event, never on a command line. | authorised plan |
| A5 | **Opt-out is explicit, loud and audited on every transition:** `OCBRAIN_API_AUTH=disabled` or `global.api_auth = "disabled"`; any other value, a typo included, means required; `PUT /config` cannot change it. Disable and re-enable are each logged and emitted (`api.auth_disabled`, `api.auth_enabled`). | authorised plan |
| A6 | **Denials are audited with a bounded rate:** WARNING log + `api.auth_denied` (reason, method, sanitised path, client; never the credential), at most 20 per 10 s then a suppressed-count summary. The HTTP body is a generic 401; every request is still rejected. | authorised plan |
| A7 | **Misconfiguration fails closed:** startup abort, or 503 at request time; never open. A directory, dangling symlink, unreadable or short token file is a 503, not a 500. | authorised plan |
| A8 | **Clients carry the token:** the CLI reads env or the token file; `web/auth.js` keeps it in `sessionStorage` only and prompts once per tab; the one SSE stream uses a `fetch`-based reader because `EventSource` cannot send headers. | authorised plan |
| A9 | **`Host` allowlist in required mode:** `localhost`, `127.0.0.1`, `::1`, plus `OCBRAIN_API_ALLOWED_HOSTS` / `global.api_allowed_hosts` for a proxied deployment. Names only, port ignored. Checked before the public allowlist. Not applied under the explicit opt-out. | authorised plan |
| A10 | **Token location and lifecycle:** frozen builds use a per-user directory (`%LOCALAPPDATA%\OCBrain`, `~/Library/Application Support/OCBrain`, `$XDG_DATA_HOME/ocbrain`); the file is re-checked on every request, so `ocbrain token --rotate` or deleting it revokes the old token without a restart. | authorised plan |
| A11 | **The tray never puts the token on a command line.** The page asks once per tab; `ocbrain token --show` prints it. A one-time-code scheme was rejected: a local attacker could win the race to redeem it and obtain the full token. | authorised plan |
| A12 | **Windows:** owner-only ACL set with `icacls` on create, load and rotate, verified to leave exactly one entry; validated by a Windows CI job (`scripts/check_token_acl_windows.py`), not by the stubbed unit tests. | authorised plan |
| A13 | **Baseline security headers** (CSP with no external origin, `nosniff`, `DENY`, `no-referrer`). `'unsafe-inline'` stays because the shipped pages use inline script and `onclick`. | authorised plan |
| A14 | **`ocbrain token [--show|--rotate]`** in both entry points (the pip CLI, and `main.py` for packaged installs); the CLI group now runs a known subcommand before treating text as a query (E11). | authorised plan |

Rejected: cookie sessions (more state, a CSRF surface, no gain on one machine); a `?token=` query parameter (logs,
history); a one-time bootstrap code in the launcher URL (race, see A11); relying on the bind address alone (E3);
partial protection of only the mutating routes (reads such as `/config`, `/debug`, `/executions/*` are sensitive);
a middleware that fails open when unconfigured (the direct-`uvicorn` case in E3).

## 3. Route table (the test is the authority)
Public (1, plus the `/static/` mount): `GET /`.
Token required (30): `GET /status`, `/health`, `/modules`, `/config`, `/debug`, `/dashboard`, `/introspection`,
`/events`, `/updates`, `/openapi.json`, `/executions/{id}`, `/executions/{id}/events`, `/brain/version`,
`/brain/v2/status`, `/brain/v2/version`; `PUT /config`; `POST /query`, `/train/{module}`, `/distill`, `/export`,
`/import`, `/modules/new`, `/evolve/plan`, `/rollback`, `/update/install`, `/update/restart`, `/brain/v2/query`,
`/brain/v2/distill`, `/brain/v2/export`, `/brain/v2/import`.

## 4. Operating it
* **Show the token:** `ocbrain token --show` (prints only the token; safe in `$(...)`). `ocbrain token` alone prints where
  it lives. In a packaged install the binary `ocbrain` answers the same command before starting anything.
* **Where it lives:** a source checkout, `data/api_token`; a frozen build, the per-user directory in A10; or
  `OCBRAIN_API_TOKEN_FILE`; or the `OCBRAIN_API_TOKEN` environment variable (wins over the file).
* **Use it:** `curl -H "Authorization: Bearer $(ocbrain token --show)" http://127.0.0.1:7437/status`.
* **Rotate or revoke:** `ocbrain token --rotate`, or delete the file. A running server notices on its next request.
  (Not available for an environment-variable token.)
* **Browser:** open the UI and paste the token once per tab. There is no token in the launcher URL.
* **Behind a proxy:** add the public name with `OCBRAIN_API_ALLOWED_HOSTS` or `global.api_allowed_hosts`.
  `uvicorn --root-path` is supported.
* **Monitors** that hit `/health` need the bearer token.
* Tests opt out through one autouse fixture in `tests/conftest.py`; `tests/test_api_auth_boundary.py` re-enables it.

## 5. Interaction with other work
* Control-plane **authorization** stays open (section 7): an authenticated caller can still reach `/update/*`,
  `/config`, `/import`, `/export`, `/distill` and `/rollback`, none of which call `GovernanceKernel`.
* CTX-EXPORT-001 / `import_module()` was bounded only by localhost-bind + CSRF. It is now also behind the token and
  the `Host` allowlist. The path-containment fixes are unchanged.
* Dependabot PRs that bump the pinned actions in `ci.yml` will not touch the new Windows job's pins; bump them together.

## 6. Residual scope (explicit)
1. **Same-user processes can read the token file.** Not defended against. A different mechanism (OS keyring,
   per-process credentials) would be a separate decision.
2. **`'unsafe-inline'` remains in the CSP**, so an injected inline script still runs and can read `sessionStorage`.
   The CSP removes third-party loads and cross-origin `connect`, not XSS itself. Module names and stage text are
   inserted unescaped via `innerHTML` in `index.html` (pre-existing; not exploited).
3. **No lockout.** Denial logging is bounded; a flood is still answered, at about 400 requests per second measured.
4. **The `Host` allowlist does not apply under the explicit opt-out.**
5. **Whether a browser keeps the `#token=` URL in its history** is no longer relevant to the tray (it sends none),
   but a user can still paste a `#token=` fragment by hand; `auth.js` adopts it.
6. **Windows evidence comes only from the CI job.** It lists ACL entries; it does not attempt a read as a second
   account. macOS and a frozen build on Windows/macOS were not run.
7. **A real desktop launcher** (`xdg-open`, Chrome, Firefox, Safari) was not exercised; the no-token-on-a-command-line
   property is tested with a stand-in launcher plus a positive control that shows the detector sees a leak.
8. **Multi-user hosts** were simulated with an unprivileged uid in one container.
9. **`web/wizard.html` targets routes that do not exist** (E7).
10. **The CLI parsing fix (E11) is a minimal change to the group, not a CLI redesign.**
11. The web helpers (`web/auth.js`) are executed under Node against a live server (`tests/test_web_auth_js.py`) and,
    separately and outside CI, in headless Chromium on Linux. The Node run is not browser evidence.

## 7. Open findings that this change does not close
* **Authenticated-but-unauthorized control-plane operations.** Authentication establishes who is calling, not
  whether the call is permitted. `/update/install`, `/update/restart`, `PUT /config` (including the mutable
  `global.ollama_host` and `global.web_ui_port`), `/import`, `/export`, `/distill`, `/rollback`, `/modules/new`,
  `/evolve/plan` and `/train/*` have no `GovernanceKernel` evaluation. **Open.**
* **Durable authentication events.** `api.auth_denied`, `api.auth_disabled` and `api.auth_enabled` reach the log and
  in-memory bus subscribers only, not the persistent `EventStream`. **Open decision for the owner.**
