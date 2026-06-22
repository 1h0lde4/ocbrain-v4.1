"""
modules/system_ctrl/module.py — System control expert module.
LLM parses intent → structured action → safe OS call via allowlist.
The LLM NEVER executes shell directly.
"""
import json
import logging
import platform
import subprocess
import time
from pathlib import Path

from modules.base import BaseModule, ModuleResult
from core.provider_mesh import resolve_provider, generate_with_fallback, graceful_generate_with_fallback

log = logging.getLogger(__name__)

# ── Safe action allowlist ──────────────────────────────────────
# Maps action names to OS-safe handler functions.
# Anything NOT in this dict is rejected — no arbitrary execution.

SYSTEM = platform.system()  # "Linux" | "Darwin" | "Windows"

# V3.0.1 SECURITY: Sandbox root directory
SAFE_ROOT = (Path.cwd() / "workspace").resolve()
SAFE_ROOT.mkdir(exist_ok=True)


def _safe_path(target: str) -> Path:
    """Ensures the target path is strictly within the SAFE_ROOT sandbox."""
    root = SAFE_ROOT.resolve()
    # Resolve the target path relative to the root
    p = Path(target).expanduser()
    if p.is_absolute():
        requested = p.resolve()
    else:
        requested = (root / p).resolve()

    try:
        # Check if the requested path is a child of the root
        requested.relative_to(root)
    except ValueError:
        raise PermissionError(f"Access denied: {target} is outside workspace.")
    
    return requested


def _open_app(target: str) -> str:
    cmds = {
        "Linux":   ["xdg-open", target],
        "Darwin":  ["open", target],
        "Windows": ["start", target],
    }
    cmd = cmds.get(SYSTEM)
    if cmd:
        subprocess.Popen(cmd, shell=(SYSTEM == "Windows"))
        return f"Opened: {target}"
    return "Unsupported OS for open action."


def _write_file(path: str, content: str = "") -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"File created: {p.relative_to(SAFE_ROOT)}"


def _read_file(path: str) -> str:
    try:
        p = _safe_path(path)
    except PermissionError as e:
        return f"File not found or access denied: {path} ({e})"
    if not p.exists():
        return f"File not found: {path}"
    return p.read_text(errors="replace")[:4000]  # cap at 4k chars


def _delete_file(path: str) -> str:
    try:
        p = _safe_path(path)
    except PermissionError as e:
        return f"File not found or access denied: {path} ({e})"
    if not p.exists():
        return f"File not found: {path}"
    p.unlink()
    return f"Deleted: {p.relative_to(SAFE_ROOT)}"


def _list_dir(path: str = ".") -> str:
    p = _safe_path(path)
    if not p.is_dir():
        return f"Not a directory: {path}"
    items = sorted(p.iterdir())
    lines = [f"{'[DIR] ' if i.is_dir() else '      '}{i.name}" for i in items[:50]]
    return "\n".join(lines)


def _get_cwd() -> str:
    return str(Path.cwd())


ACTION_HANDLERS = {
    "open":       lambda a: _open_app(a.get("target", "")),
    "launch":     lambda a: _open_app(a.get("target", "")),
    "write_file": lambda a: _write_file(a.get("path", ""), a.get("content", "")),
    "read_file":  lambda a: _read_file(a.get("path", "")),
    "delete_file":lambda a: _delete_file(a.get("path", "")),
    "list_dir":   lambda a: _list_dir(a.get("path", ".")),
    "get_cwd":    lambda a: _get_cwd(),
}


class Module(BaseModule):
    name = "system_ctrl"

    async def run(self, task: str, context) -> ModuleResult:
        t0     = time.monotonic()
        action = await self._parse_intent(task, context)
        result = self._execute(action)
        self.save_training_pair(task, json.dumps(action))
        return ModuleResult(
            answer=result, source="external",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def run_own(self, task: str, context) -> ModuleResult:
        # Same execution path — own model only changes the parser
        t0     = time.monotonic()
        action = await self._parse_intent_own(task, context)
        result = self._execute(action)
        return ModuleResult(
            answer=result, source="native",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def _parse_intent(self, task: str, context) -> dict:
        """LLM returns structured JSON via ProviderMesh."""
        providers = resolve_provider(self.name)
        allowed   = list(ACTION_HANDLERS.keys())
        prompt = (
            f"Parse the user request into a JSON action object.\n"
            f"Allowed actions: {allowed}\n"
            f"Return ONLY valid JSON like: "
            f'{{\"action\": \"open\", \"target\": \"spotify\"}}\n'
            f"User request: {task}\nJSON:"
        )
        try:
            text = await generate_with_fallback(providers, prompt)
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            log.error(f"[system_ctrl] Intent parsing failed: {e}")
        return {"action": "unknown", "raw": task}

    async def _parse_intent_own(self, task: str, context) -> dict:
        # Same as external but uses own model if configured in resolve_provider (future)
        return await self._parse_intent(task, context)

    def _execute(self, action: dict) -> str:
        name    = action.get("action", "unknown")
        handler = ACTION_HANDLERS.get(name)
        if handler is None:
            return (
                f"Action '{name}' is not in the allowed list. "
                f"Allowed: {list(ACTION_HANDLERS.keys())}"
            )
        try:
            return handler(action)
        except Exception as e:
            return f"Action '{name}' failed: {e}"
