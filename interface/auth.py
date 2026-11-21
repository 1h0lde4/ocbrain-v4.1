"""
interface/auth.py -- authentication boundary for the HTTP API (DEBT-025).

Design (see docs/reports/api-exposure-and-auth-boundary-oct2026.md):

* Default-on, fail-closed.  Every HTTP request must carry
  ``Authorization: Bearer <token>`` unless its method and path are in the
  explicit public allowlist below.  A route added later is protected by default;
  it becomes public only by an edit to this file.
* One per-installation secret, never derived from request content.  Source, in
  order: the ``OCBRAIN_API_TOKEN`` environment variable, else the token file,
  created on first start with mode 0600 (owner-only ACL on Windows).  The token
  is never logged, never placed in an event and never put on a command line.
* Comparison is constant-time (``hmac.compare_digest``).
* Implemented as a pure ASGI middleware, not a per-route dependency: the check
  is explicit, sits in front of routing (so unknown paths do not reveal which
  routes exist), and does not buffer streaming (SSE) responses.
* In required mode the ``Host`` header must name this machine (``localhost``,
  ``127.0.0.1``, ``::1`` or an explicitly configured name).  That closes the DNS
  rebinding route to the public shell and its token prompt.
* The token file is re-checked on every request (one ``stat``): replacing or
  deleting it revokes the old token at once, without a restart
  (``ocbrain token --rotate``).
* Denials are audited, with a bounded rate: a structured WARNING and an
  ``api.auth_denied`` event carrying the reason code, method and a sanitised
  path, never the credential.  Every transition of the opt-out, in both
  directions, is logged and emitted.
* Authentication is not authorisation.  Authenticated control-plane requests are
  still outside GovernanceKernel (DEBT-025's second finding); this module does
  not change that.

Opting out is explicit and loud: ``OCBRAIN_API_AUTH=disabled`` or
``global.api_auth = "disabled"``.  Any other value, including a typo, resolves to
"required".
"""
from __future__ import annotations

import asyncio
import getpass
import hmac
import json
import logging
import ntpath
import os
import posixpath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Mapping, MutableMapping, Optional

from interface import auth_audit
from interface.headers import SECURITY_HEADERS

log = logging.getLogger(__name__)

MODE_REQUIRED = "required"
MODE_DISABLED = "disabled"

ENV_MODE = "OCBRAIN_API_AUTH"
ENV_TOKEN = "OCBRAIN_API_TOKEN"
ENV_TOKEN_FILE = "OCBRAIN_API_TOKEN_FILE"
ENV_ALLOWED_HOSTS = "OCBRAIN_API_ALLOWED_HOSTS"

MIN_TOKEN_LENGTH = 32
# Token location for a source checkout.  Frozen (PyInstaller) builds use a per-user
# directory instead: see default_token_path().
DEFAULT_TOKEN_PATH = Path(__file__).resolve().parent.parent / "data" / "api_token"

_IS_WINDOWS = os.name == "nt"  # a module constant so tests can exercise both branches

# ── Public allowlist ─────────────────────────────────────────────────────────
# Deny by default.  Everything not listed here needs the bearer token.
# Only GET/HEAD may be public.  What is public, and why:
#   "/"        the static HTML shell (no data; the page then authenticates its calls)
#   "/static/" static assets (settings page, auth.js, icons)
# The interactive API docs (/docs, /redoc) are disabled: they load third-party
# scripts from a CDN into the same origin as the UI (and its sessionStorage) and
# cannot work offline.  The OpenAPI schema (/openapi.json) needs the token.
PUBLIC_METHODS = frozenset({"GET", "HEAD"})
PUBLIC_EXACT_PATHS = frozenset({"/"})
PUBLIC_PATH_PREFIXES = ("/static/",)

# Hostnames accepted in the Host header (required mode).  Names only; the port is
# not compared: DNS rebinding changes the name, not the port.
DEFAULT_ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Denial reason codes (what is logged and emitted; the HTTP body is always generic).
REASON_MISSING = "missing"
REASON_MALFORMED = "malformed"
REASON_AMBIGUOUS = "ambiguous"
REASON_INVALID = "invalid"
REASON_HOST = "host"
REASON_THROTTLED = "throttled"

EVENT_DENIED = "api.auth_denied"
EVENT_DISABLED = "api.auth_disabled"
EVENT_ENABLED = "api.auth_enabled"

# Denial logging is bounded: at most THROTTLE_BURST logged/emitted denials per
# THROTTLE_WINDOW_S seconds.  Requests are still rejected; only the noise is capped.
THROTTLE_WINDOW_S = 10.0
THROTTLE_BURST = 20


class AuthConfigError(RuntimeError):
    """The authentication configuration is unusable.  Callers must fail closed."""


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    token: Optional[bytes]  # None only when mode == MODE_DISABLED
    source: Optional[str] = None       # "env" | "file" | None
    signature: Optional[tuple] = None  # token-file identity when source == "file"


# ── Mode resolution ──────────────────────────────────────────────────────────

def resolve_mode(configured: Optional[Any] = None) -> str:
    """Environment overrides config; only the exact value 'disabled' disables."""
    raw = os.environ.get(ENV_MODE)
    if raw is None:
        raw = configured
    if raw is None:
        return MODE_REQUIRED
    value = str(raw).strip().lower()
    if value == MODE_DISABLED:
        return MODE_DISABLED
    if value != MODE_REQUIRED:
        log.warning("Unrecognised API auth mode %r; failing closed to %r.", value[:32], MODE_REQUIRED)
    return MODE_REQUIRED


# ── Token location ───────────────────────────────────────────────────────────

def default_token_path(frozen: Optional[bool] = None, platform: Optional[str] = None,
                       env: Optional[Mapping[str, str]] = None, home: Optional[str] = None) -> Path:
    """Where the token file lives when OCBRAIN_API_TOKEN_FILE is not set.

    A source checkout keeps it in ``data/``.  A frozen ``--onefile`` build must not:
    there ``__file__`` sits in a per-run temporary directory, so the token would
    change on every start and a separate CLI process could never find it.  Frozen
    builds use a persistent per-user directory instead.
    """
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not frozen:
        return DEFAULT_TOKEN_PATH
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = home or str(Path.home())
    if platform.startswith("win"):
        base = env.get("LOCALAPPDATA") or ntpath.join(home, "AppData", "Local")
        return Path(ntpath.join(base, "OCBrain", "api_token"))
    if platform == "darwin":
        return Path(posixpath.join(home, "Library", "Application Support", "OCBrain", "api_token"))
    base = env.get("XDG_DATA_HOME") or posixpath.join(home, ".local", "share")
    return Path(posixpath.join(base, "ocbrain", "api_token"))


def token_path() -> Path:
    override = os.environ.get(ENV_TOKEN_FILE)
    return Path(override) if override else default_token_path()


# ── Token file protection ────────────────────────────────────────────────────

def _validate_token(value: str, source: str) -> str:
    value = value.strip()
    if len(value) < MIN_TOKEN_LENGTH:
        raise AuthConfigError(
            f"API token from {source} is shorter than {MIN_TOKEN_LENGTH} characters; "
            "refusing to use it. Delete the file (or unset the variable) to generate a new one."
        )
    return value


def _run_tool(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=20)


def _windows_current_sid() -> str:
    """SID of the current user, via ``whoami``.  Locale-independent, unlike names."""
    out = _run_tool(["whoami", "/user", "/fo", "csv", "/nh"]).stdout.strip()
    fields = [f.strip().strip('"') for f in out.split('","')]
    if len(fields) < 2 or not fields[-1].startswith("S-1-"):
        raise AuthConfigError("could not determine the current user's SID (whoami output unexpected)")
    return fields[-1]


# SDDL trustee codes that may appear in the token file's ACL.  SYSTEM, Administrators and
# OWNER RIGHTS cannot be kept out of a file (administrators can take ownership), so they
# are not "other principals"; the invariant is that nobody else is granted anything.
_WINDOWS_ALWAYS_ALLOWED_TRUSTEES = frozenset({"SY", "BA", "OW"})
_WINDOWS_TRUSTEE_NAMES = {
    "WD": "Everyone", "BU": "BUILTIN\\Users", "AU": "Authenticated Users", "IU": "Interactive",
    "AN": "Anonymous", "BG": "BUILTIN\\Guests", "S-1-5-32-546": "BUILTIN\\Guests", "NU": "Network",
    "CO": "Creator Owner", "PU": "Power Users", "RC": "Restricted Code",
}


def _windows_acl_sddl(path: Path) -> str:
    """The file's DACL as SDDL (SIDs, so independent of the Windows display language)."""
    workdir = tempfile.mkdtemp(prefix="ocb-sddl-")
    out = os.path.join(workdir, "acl.txt")
    try:
        res = _run_tool(["icacls", str(path), "/save", out])
        if res.returncode != 0 or not os.path.exists(out):
            raise AuthConfigError(f"could not read the ACL of {path} (icacls /save exit {res.returncode})")
        raw = open(out, "rb").read()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    for encoding in ("utf-16", "utf-8"):  # icacls writes UTF-16 with a BOM
        try:
            return raw.decode(encoding)
        except UnicodeError:
            continue
    return raw.decode("latin-1")


def _sddl_trustees(sddl: str) -> list[str]:
    """Trustees of the *allow* entries in the DACL: ['SY', 'BA', 'S-1-5-21-...', ...]."""
    dacl = re.search(r"D:[A-Z]*((?:\([^()]*\))+)", sddl)
    if dacl is None:
        raise AuthConfigError("could not parse the ACL of the token file (no DACL found)")
    trustees = []
    for ace in re.findall(r"\(([^()]*)\)", dacl.group(1)):
        fields = ace.split(";")
        if len(fields) >= 6 and fields[0] in ("A", "OA"):
            trustees.append(fields[5])
    return trustees


def _restrict_to_owner_windows(path: Path) -> None:
    """Grant the current user full control, drop inherited entries, then verify that no
    OTHER principal (Everyone, Users, Authenticated Users, another account, ...) has access.

    SYSTEM, Administrators and OWNER RIGHTS stay: they cannot be excluded in practice, and
    on a freshly created file they are explicit entries that /inheritance:r does not touch.
    Raises AuthConfigError if anything else remains.
    """
    sid = _windows_current_sid()
    # /reset first: /grant:r only replaces the entry for the named SID, so an explicit entry for
    # another principal (e.g. "Everyone: read" added later) would otherwise survive.  Then drop the
    # inherited entries and grant the current user.
    for step in (["/reset"], ["/inheritance:r"], ["/grant:r", f"*{sid}:(F)"]):
        res = _run_tool(["icacls", str(path), *step])
        if res.returncode != 0:
            raise AuthConfigError(
                f"could not restrict {path} to the current user (icacls {step[0]} exit {res.returncode})")
    trustees = _sddl_trustees(_windows_acl_sddl(path))
    allowed = set(_WINDOWS_ALWAYS_ALLOWED_TRUSTEES) | {sid}
    if sid.endswith("-500"):  # SDDL prints the built-in Administrator account as "LA"
        allowed.add("LA")
    extra = sorted(set(trustees) - allowed)
    if extra or not (set(trustees) & ({sid} | ({"LA"} if sid.endswith("-500") else set()))):
        named = ", ".join(_WINDOWS_TRUSTEE_NAMES.get(t, t) for t in extra) or "none"
        raise AuthConfigError(
            f"API token file {path} is not private after restriction: other principals with access: {named}; "
            f"current user present: {bool(set(trustees) & {sid, 'LA'})}. "
            "Delete it (a new private file is created on the next start)."
        )


def _enforce_private_mode(path: Path) -> None:
    """The token file must be private: POSIX 0600, Windows owner-only ACL."""
    if _IS_WINDOWS:
        _restrict_to_owner_windows(path)  # idempotent; also repairs a loosened ACL
        return
    mode = stat.S_IMODE(path.stat().st_mode)  # follows symlinks: the mode of the real file
    if not mode & 0o077:
        return
    if path.is_symlink():
        # Never chmod through a symlink: that would change a file this module does not own.
        raise AuthConfigError(
            f"API token file {path} is a symlink to a file accessible to other users (mode {oct(mode)}); "
            "tighten the target's permissions."
        )
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        raise AuthConfigError(
            f"API token file {path} is accessible to other users (mode {oct(mode)}) "
            f"and could not be tightened: {type(exc).__name__}"
        ) from exc
    log.warning("API token file %s was mode %s; tightened to 0600.", path, oct(mode))


def _file_signature(path: Path) -> Optional[tuple]:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size, st.st_ino)


def read_token() -> Optional[str]:
    """Client-side lookup (CLI): env, else an existing file.  Never creates one."""
    env = os.environ.get(ENV_TOKEN)
    if env is not None and env.strip():
        return env.strip()
    path = token_path()
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _ensure_token_dir(path: Path) -> None:
    """Create the token file's directory.

    The frozen-build per-user default is created 0700, whichever of first start and
    ``ocbrain token --rotate`` runs first.  A directory that already exists is never
    chmod-ed, and a directory the user chose with OCBRAIN_API_TOKEN_FILE keeps the
    default mode: this module only owns the location it picked itself.
    """
    default = default_token_path()
    if default != DEFAULT_TOKEN_PATH and path == default:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)


def _token_from_file(path: Path) -> str:
    if path.is_symlink() and not path.exists():
        raise AuthConfigError(f"API token file {path} is a dangling symlink.")
    if path.exists():
        if not path.is_file():
            raise AuthConfigError(f"API token path {path} exists but is not a regular file.")
        _enforce_private_mode(path)
        return _validate_token(path.read_text(encoding="utf-8"), f"the token file {path}")

    _ensure_token_dir(path)
    token = secrets.token_urlsafe(32)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:  # lost a creation race: use the winner's token
        _enforce_private_mode(path)
        return _validate_token(path.read_text(encoding="utf-8"), f"the token file {path}")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    _enforce_private_mode(path)  # Windows: owner-only ACL on the new file
    log.info("Generated a new API token and stored it at %s.", path)
    return token


def _resolve_token() -> tuple[str, str, Optional[tuple]]:
    """(token, source, signature).  Env var wins over the token file."""
    env = os.environ.get(ENV_TOKEN)
    if env is not None:
        return _validate_token(env, f"the {ENV_TOKEN} environment variable"), "env", None
    path = token_path()
    try:
        token = _token_from_file(path)
    except AuthConfigError:
        raise
    except OSError as exc:  # directory, dangling symlink, unreadable, ...: fail closed, not 500
        raise AuthConfigError(
            f"API token file {path} is unusable ({type(exc).__name__}); refusing to run unauthenticated."
        ) from exc
    return token, "file", _file_signature(path)


def load_or_create_token() -> str:
    """Server-side: env var, else the token file (created private on first use)."""
    return _resolve_token()[0]


def rotate_token() -> tuple[str, Path]:
    """Replace the token file atomically with a fresh private one.

    A running server notices on its next request (the file is re-checked each time)
    and the old token stops working immediately.  Not available when the token comes
    from the environment or when the token path is a symlink.
    """
    if os.environ.get(ENV_TOKEN) is not None:
        raise AuthConfigError(f"The token comes from {ENV_TOKEN}; rotate it where it is set.")
    path = token_path()
    if path.is_symlink():
        raise AuthConfigError(f"{path} is a symlink; rotate the token at its source.")
    _ensure_token_dir(path)
    token = secrets.token_urlsafe(32)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
        _enforce_private_mode(tmp)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return token, path


# ── Settings cache and opt-out transitions ───────────────────────────────────

_cached: Optional[AuthSettings] = None
_last_mode: Optional[str] = None


def _note_mode(mode: str) -> None:
    """Log, emit and queue for persistence every change of the resolved mode, in both directions."""
    global _last_mode
    if mode == _last_mode:
        return
    previous, _last_mode = _last_mode, mode
    if mode == MODE_DISABLED:
        log.warning(
            "API AUTHENTICATION IS DISABLED (%s / global.api_auth). Every endpoint, including "
            "config writes, updates, import/export and /query, is open to anything that can "
            "reach the port. (It takes effect only once this transition's audit record is persisted.)",
            ENV_MODE,
        )
        _emit(EVENT_DISABLED, {"mode": mode, "previous": previous})
        _enqueue(EVENT_DISABLED, _transition_payload(mode, previous), kind="transition")
    elif previous == MODE_DISABLED:
        log.warning("API authentication is REQUIRED again (was disabled).")
        _emit(EVENT_ENABLED, {"mode": mode, "previous": previous})
        _enqueue(EVENT_ENABLED, _transition_payload(mode, previous), kind="transition")


def get_settings(configured_mode: Optional[Any] = None) -> AuthSettings:
    """Resolve (and cache) the settings.  Raises AuthConfigError when unusable."""
    global _cached
    mode = resolve_mode(configured_mode)
    _note_mode(mode)
    if mode == MODE_DISABLED and _disable_audit_pending():
        # Fail closed: the opt-out takes effect only once its audit record is durable.
        mode = MODE_REQUIRED
    cached = _cached
    if mode == MODE_DISABLED:
        if cached is None or cached.mode != mode:
            cached = _cached = AuthSettings(mode=mode, token=None)
        return cached
    if cached is not None and cached.mode == mode:
        if cached.source != "file" or _file_signature(token_path()) == cached.signature:
            return cached
        # the token file changed (rotation, deletion, tampering): re-resolve
    token, source, signature = _resolve_token()
    _cached = AuthSettings(mode=mode, token=token.encode("utf-8"), source=source, signature=signature)
    return _cached


def reset_cache_for_tests() -> None:
    global _cached, _last_mode
    _cached = None
    _last_mode = None
    _throttle.update(start=0.0, count=0, suppressed=0, warned=False, total=0, reasons={}, start_wall=0.0, window_id=0)
    _pending.clear()
    _audit_state.update(next_attempt=0.0, flushing=False, dropped_aggregates=0, dropped_denials=0, last_error_log=-1e9)


# ── Host allowlist ───────────────────────────────────────────────────────────

def allowed_hosts(configured: Optional[Any] = None) -> frozenset[str]:
    """Accepted Host-header names: the defaults plus ``OCBRAIN_API_ALLOWED_HOSTS``
    and ``global.api_allowed_hosts`` (comma-separated string or list)."""
    names = set(DEFAULT_ALLOWED_HOSTS)
    extra: list[str] = []
    for raw in (os.environ.get(ENV_ALLOWED_HOSTS), configured):
        if raw is None:
            continue
        extra.extend(raw if isinstance(raw, (list, tuple)) else str(raw).split(","))
    for item in extra:
        name = _hostname(str(item).strip())
        if name:
            names.add(name)
    return frozenset(names)


def _hostname(value: str) -> Optional[str]:
    """Hostname part of a Host header value, lower-cased: 'LocalHost:7437' -> 'localhost',
    '[::1]:7437' -> '::1'.  None when it cannot be parsed."""
    value = value.strip().lower()
    if not value:
        return None
    if value.startswith("["):
        end = value.find("]")
        if end == -1:
            return None
        return value[1:end] or None
    if value.count(":") == 1:
        host, _, port = value.partition(":")
        if not port.isdigit():
            return None
        value = host
    return value.rstrip(".") or None


def _host_allowed(scope: Mapping[str, Any], allowed: frozenset[str]) -> bool:
    values = [v for k, v in scope.get("headers", []) if k.lower() == b"host"]
    if len(values) != 1:  # missing, or ambiguous
        return False
    try:
        name = _hostname(values[0].decode("latin-1"))
    except UnicodeError:  # pragma: no cover - latin-1 decodes any byte
        return False
    return name is not None and name in allowed


# ── Auditing ─────────────────────────────────────────────────────────────────

def _emit(event: str, payload: dict) -> None:
    """Fire-and-forget audit event.  Never raises into the request path."""
    try:
        from core.event_bus import bus  # lazy: clients importing this module stay light
        bus.emit_sync(event, dict(payload))
    except Exception:  # pragma: no cover - audit must not break the boundary
        log.exception("Could not emit %s", event)


def _safe_path(path: str) -> str:
    return ascii(path[:200])


_clock: Callable[[], float] = time.monotonic
_wall: Callable[[], float] = time.time
_WINDOW_TIMER = True  # tests with a fake clock turn the real-time timer off
_throttle: dict[str, Any] = {
    "start": 0.0, "count": 0, "suppressed": 0, "warned": False,
    "total": 0, "reasons": {}, "start_wall": 0.0, "window_id": 0,
}

# ── Durable audit records ────────────────────────────────────────────────────
_pending: list[dict[str, Any]] = []  # records not yet persisted, oldest first
_audit_state: dict[str, Any] = {
    "next_attempt": 0.0, "flushing": False, "dropped_aggregates": 0, "dropped_denials": 0, "last_error_log": -1e9,
}
_tasks: set = set()  # strong references to background flush tasks


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _transition_payload(mode: str, previous: Optional[str]) -> dict[str, Any]:
    return {
        "schema": auth_audit.SCHEMA_VERSION, "transition_id": uuid.uuid4().hex,
        "mode": mode, "previous": previous,
        "source": "env" if ENV_MODE in os.environ else "config",
        "pid": os.getpid(), "at": _iso(_wall()),
    }


def _enqueue(event_type: str, payload: dict[str, Any], *, kind: str) -> None:
    _pending.append({"event_type": event_type, "payload": payload, "kind": kind})
    if kind != "aggregate":
        return
    aggregates = [r for r in _pending if r["kind"] == "aggregate"]
    while len(aggregates) > auth_audit.MAX_PENDING_AGGREGATES:  # bounded; the loss is counted, not hidden
        dropped = aggregates.pop(0)
        _pending.remove(dropped)
        _audit_state["dropped_aggregates"] += 1
        _audit_state["dropped_denials"] += int(dropped["payload"].get("total", 0))


def has_pending_audit() -> bool:
    return bool(_pending)


def _disable_audit_pending() -> bool:
    """True while any api.auth_disabled record is unpersisted: the opt-out must not take effect."""
    return any(r["event_type"] == EVENT_DISABLED for r in _pending)


def _log_audit_failure(record: dict[str, Any], exc: BaseException) -> None:
    now = _clock()
    if now - _audit_state["last_error_log"] < 30.0:
        return
    _audit_state["last_error_log"] = now
    gate = (" Authentication STAYS REQUIRED until the disable record is stored."
            if _disable_audit_pending() else " It will be retried.")
    log.error("Authentication audit record %s could not be persisted (%s).%s",
              record["event_type"], type(exc).__name__, gate)


async def flush_audit() -> bool:
    """Persist pending records in order.  True if nothing is left pending.

    Never raises (except task cancellation).  Single-flight, time-boxed per append, and after a
    failure it backs off, so a broken store cannot add latency to every request.
    """
    state = _audit_state
    if not _pending:
        return True
    if state["flushing"] or _clock() < state["next_attempt"]:
        return False
    state["flushing"] = True
    try:
        sink = auth_audit.get_sink()
        while _pending:
            record = _pending[0]
            try:
                await asyncio.wait_for(sink.append(record["event_type"], record["payload"]),
                                       timeout=auth_audit.AUDIT_TIMEOUT_S)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # storage error or timeout: never propagate into request handling
                state["next_attempt"] = _clock() + auth_audit.AUDIT_RETRY_BACKOFF_S
                _log_audit_failure(record, exc)
                return False
            _pending.pop(0)
        return True
    finally:
        state["flushing"] = False


def schedule_flush() -> None:
    """Start a background flush on the running loop (a no-op without one)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(flush_audit())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _close_window() -> None:
    """Turn the finished window's counters into one aggregate record and reset them."""
    st = _throttle
    if st["total"]:
        payload = {
            "schema": auth_audit.SCHEMA_VERSION, "kind": "aggregate",
            "window_start": _iso(st["start_wall"]), "window_end": _iso(_wall()),
            "window_seconds": THROTTLE_WINDOW_S, "total": st["total"],
            "by_reason": dict(sorted(st["reasons"].items())),
            "logged": st["count"], "suppressed": st["suppressed"], "pid": os.getpid(),
            "dropped_aggregates": _audit_state["dropped_aggregates"],
            "dropped_denials": _audit_state["dropped_denials"],
        }
        _audit_state.update(dropped_aggregates=0, dropped_denials=0)
        _enqueue(EVENT_DENIED, payload, kind="aggregate")
    st.update(count=0, suppressed=0, warned=False, total=0, reasons={})


def _window_timer_fired(window_id: int) -> None:
    st = _throttle
    if st["window_id"] != window_id or not st["total"]:
        return  # a later window is already running (or it was closed by a newer denial)
    _close_window()
    schedule_flush()


def _schedule_window_timer(window_id: int) -> None:
    if not _WINDOW_TIMER:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.call_later(THROTTLE_WINDOW_S + 0.05, _window_timer_fired, window_id)


def _admit_denial(reason: str = REASON_INVALID) -> bool:
    """Count every denial; True if this one may be logged and emitted (bounded rate)."""
    now = _clock()
    st = _throttle
    if now - st["start"] >= THROTTLE_WINDOW_S:
        if st["suppressed"]:
            log.warning("api.auth_denied: %d further denials were suppressed in the previous %.0f s window.",
                        st["suppressed"], THROTTLE_WINDOW_S)
            _emit(EVENT_DENIED, {"reason": REASON_THROTTLED, "count": st["suppressed"]})
        _close_window()
        st["start"] = now
    if st["total"] == 0:  # first denial of this window
        st["start_wall"] = _wall()
        st["window_id"] += 1
        _schedule_window_timer(st["window_id"])
    st["total"] += 1
    st["reasons"][reason] = st["reasons"].get(reason, 0) + 1
    if st["count"] < THROTTLE_BURST:
        st["count"] += 1
        return True
    st["suppressed"] += 1
    if not st["warned"]:
        st["warned"] = True
        log.warning("api.auth_denied: more than %d denials in %.0f s; suppressing further log lines "
                    "and events for this window (requests are still rejected).",
                    THROTTLE_BURST, THROTTLE_WINDOW_S)
    return False


def _audit_denied(reason: str, scope: MutableMapping[str, Any]) -> None:
    if not _admit_denial(reason):
        return
    method = str(scope.get("method", "WS" if scope.get("type") == "websocket" else "?"))
    path = _safe_path(str(scope.get("path", "")))
    client = scope.get("client")
    host = ascii(str(client[0])) if client else "unknown"
    payload = {"reason": reason, "method": method, "path": path, "client": host}
    extra = ""
    if reason == REASON_HOST:
        hosts = [v for k, v in scope.get("headers", []) if k.lower() == b"host"]
        shown = ascii(hosts[0].decode("latin-1")[:100]) if len(hosts) == 1 else f"<{len(hosts)} Host headers>"
        payload["host"] = shown
        extra = f" host={shown}"
    log.warning("api.auth_denied reason=%s method=%s path=%s client=%s%s", reason, method, path, host, extra)
    _emit(EVENT_DENIED, payload)


# ── Middleware ───────────────────────────────────────────────────────────────

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]


def route_path(scope: Mapping[str, Any]) -> str:
    """The path the router matches on: ``scope["path"]`` without ``root_path``.

    Mirrors Starlette's own rule.  Servers started with ``--root-path`` put the
    prefix in ``scope["path"]``; comparing the raw value would make the public
    shell look protected (and, in principle, let the two views of the path drift).
    """
    path = str(scope.get("path", ""))
    root = str(scope.get("root_path", "") or "")
    if not root or not path.startswith(root):
        return path
    if path == root:
        return ""
    if path[len(root)] == "/":
        return path[len(root):]
    return path


def is_public(method: str, path: str,
              exact: Iterable[str] = PUBLIC_EXACT_PATHS,
              prefixes: Iterable[str] = PUBLIC_PATH_PREFIXES) -> bool:
    if method not in PUBLIC_METHODS:
        return False
    return path in exact or any(path.startswith(p) for p in prefixes)


def _extract_bearer(scope: Scope) -> tuple[Optional[bytes], Optional[str]]:
    """Return (credential, None) or (None, reason)."""
    values = [v for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
    if not values:
        return None, REASON_MISSING
    if len(values) > 1:
        return None, REASON_AMBIGUOUS
    scheme, _, credential = values[0].strip().partition(b" ")
    credential = credential.strip()
    if scheme.lower() != b"bearer" or not credential:
        return None, REASON_MALFORMED
    return credential, None


class ApiAuthMiddleware:
    """Pure-ASGI bearer-token gate.  Add it LAST so it is the outermost middleware."""

    def __init__(self, app: Callable[..., Awaitable[None]],
                 settings_provider: Callable[[], AuthSettings] = get_settings,
                 hosts_provider: Optional[Callable[[], frozenset[str]]] = None) -> None:
        self.app = app
        self._settings_provider = settings_provider
        self._hosts_provider = hosts_provider or allowed_hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):  # lifespan etc.
            await self.app(scope, receive, send)
            return

        try:
            settings = self._settings_provider()
            if _disable_audit_pending():
                await flush_audit()                  # bounded by AUDIT_TIMEOUT_S and the retry backoff
                settings = self._settings_provider() # required until the record is durable
            elif has_pending_audit():
                schedule_flush()                     # aggregates / enable records never delay a request
        except AuthConfigError:
            log.exception("API authentication is misconfigured; refusing the request.")
            await self._reject(scope, send, 503, "API authentication is misconfigured")
            return

        if settings.mode == MODE_DISABLED:
            await self.app(scope, receive, send)
            return

        if not _host_allowed(scope, self._hosts_provider()):
            _audit_denied(REASON_HOST, scope)
            await self._reject(scope, send, 400, "Invalid host header")
            return

        if scope["type"] == "http" and is_public(scope.get("method", ""), route_path(scope)):
            await self.app(scope, receive, send)
            return

        credential, reason = _extract_bearer(scope)
        if credential is None:
            _audit_denied(reason or REASON_MALFORMED, scope)
            await self._reject(scope, send, 401, "Authentication required")
            return
        if settings.token is None or not hmac.compare_digest(credential, settings.token):
            _audit_denied(REASON_INVALID, scope)
            await self._reject(scope, send, 401, "Authentication required")
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, send: Send, status: int, detail: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"detail": detail}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
            # This middleware is outermost, so a rejection never reaches SecurityHeadersMiddleware:
            # add the same set here so 400/401/503 responses carry it too.
            *SECURITY_HEADERS,
        ]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
