"""
interface/updater.py — OCBrain update system.
Update path: git pull → pip install -e . → restart.
Works for git clone installs (primary) and pip-URL installs (fallback).
"""
import asyncio
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("ocbrain")

GITHUB_REPO   = "1h0lde4/OCBrain"
PROJECT_ROOT  = Path(__file__).parent.parent
VERSION_FILE  = PROJECT_ROOT / "version.txt"
ROLLBACK_FILE = PROJECT_ROOT / ".rollback_commit"


# ── Version helpers ───────────────────────────────────────────────────────────

def current_version() -> str:
    """Always read from version.txt — never hardcode."""
    try:
        return VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


def current_git_commit() -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def is_git_repo() -> bool:
    return (PROJECT_ROOT / ".git").exists()


def _version_gt(a: str, b: str) -> bool:
    try:
        return (
            tuple(int(x) for x in a.split("."))
            > tuple(int(x) for x in b.split("."))
        )
    except Exception:
        return False


def _pip() -> list[str]:
    """
    Return pip command as a list safe for subprocess.run().
    Prefers the venv pip; falls back to 'python -m pip'.
    NEVER returns a space-joined string — that breaks subprocess list args.
    """
    venv_pip = PROJECT_ROOT / ".venv" / "bin" / "pip"
    if venv_pip.exists():
        return [str(venv_pip)]
    bin_pip = Path(sys.executable).parent / "pip"
    if bin_pip.exists():
        return [str(bin_pip)]
    return [sys.executable, "-m", "pip"]


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class UpdateResult:
    available:    bool
    version:      str  = field(default_factory=current_version)
    current:      str  = field(default_factory=current_version)
    changelog:    str  = ""
    download_url: str  = ""
    check_failed: bool = False
    check_error:  str  = ""


@dataclass
class InstallResult:
    success:          bool
    message:          str
    restart_required: bool = False


# ── Check ─────────────────────────────────────────────────────────────────────

def check() -> UpdateResult:
    cv = current_version()
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=10,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code == 404:
            return _check_via_commits(cv)
        resp.raise_for_status()
        data   = resp.json()
        latest = data.get("tag_name", "v0.0.0").lstrip("v")
        if _version_gt(latest, cv):
            return UpdateResult(
                available=True,  version=latest, current=cv,
                changelog=data.get("body", "")[:500],
                download_url=data.get("html_url", ""),
            )
        return UpdateResult(available=False, version=latest, current=cv)
    except requests.RequestException as e:
        return UpdateResult(
            available=False, current=cv,
            check_failed=True, check_error=f"Could not reach GitHub: {e}",
        )
    except Exception as e:
        return UpdateResult(
            available=False, current=cv,
            check_failed=True, check_error=str(e),
        )


def _check_via_commits(cv: str) -> UpdateResult:
    """Fallback: compare local vs remote main when no GitHub releases exist."""
    try:
        subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=PROJECT_ROOT, capture_output=True, timeout=15,
        )
        local  = current_git_commit() or ""
        r      = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5,
        )
        remote = r.stdout.strip()
        if remote and local != remote:
            return UpdateResult(
                available=True, version="latest", current=cv,
                changelog="New commits available on main branch.",
                download_url=f"https://github.com/{GITHUB_REPO}/commits/main",
            )
    except Exception:
        pass
    return UpdateResult(available=False, current=cv)


# ── Install ───────────────────────────────────────────────────────────────────

def install(version: str) -> InstallResult:
    if not is_git_repo():
        return _install_via_pip(version)
    return _install_via_git(version)


def _install_via_git(version: str) -> InstallResult:
    # 1. Save rollback point
    commit = current_git_commit()
    if commit:
        ROLLBACK_FILE.write_text(commit)
        log.info(f"[updater] Rollback saved: {commit[:12]}")

    # 2. git fetch
    r = subprocess.run(
        ["git", "fetch", "origin"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return InstallResult(False, f"git fetch failed:\n{r.stderr}")

    # 3. git pull or checkout tag
    if version and version not in ("latest", "") and version[0].isdigit():
        cmd = ["git", "checkout", f"v{version}"]
    else:
        cmd = ["git", "pull", "origin", "main"]

    log.info(f"[updater] {' '.join(cmd)}")
    r = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        return InstallResult(False, f"git pull failed:\n{r.stderr}")

    # 4. pip install -e . to pick up new deps
    log.info("[updater] Updating dependencies...")
    subprocess.run(
        _pip() + ["install", "-e", ".", "--quiet", "--timeout", "120"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=180,
    )  # non-fatal if this has warnings

    return InstallResult(
        success=True,
        message=f"Updated to {current_version()}. Restart OCBrain to apply.",
        restart_required=True,
    )


def _install_via_pip(version: str) -> InstallResult:
    if version and version != "latest":
        url = f"git+https://github.com/{GITHUB_REPO}.git@v{version}"
    else:
        url = f"git+https://github.com/{GITHUB_REPO}.git"

    log.info(f"[updater] pip install --upgrade {url}")
    r = subprocess.run(
        _pip() + ["install", "--upgrade", url, "--quiet", "--timeout", "120"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        return InstallResult(False, f"pip upgrade failed:\n{r.stderr}")

    return InstallResult(
        success=True,
        message="Updated via pip. Restart OCBrain to apply.",
        restart_required=True,
    )


# ── Async wrapper ─────────────────────────────────────────────────────────────

async def install_async(version: str) -> InstallResult:
    """Non-blocking install for FastAPI — git/pip run in executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, install, version)


# ── Rollback ──────────────────────────────────────────────────────────────────

def rollback() -> InstallResult:
    if not is_git_repo():
        return InstallResult(False, "Rollback only works for git-cloned installs.")
    if not ROLLBACK_FILE.exists():
        return InstallResult(
            False,
            "No rollback point found. No update has been applied via OCBrain yet."
        )
    prev_commit = ROLLBACK_FILE.read_text().strip()
    if not prev_commit:
        return InstallResult(False, "Rollback file is empty.")

    log.info(f"[updater] Rolling back to {prev_commit[:12]}...")
    r = subprocess.run(
        ["git", "checkout", prev_commit],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return InstallResult(False, f"git checkout failed:\n{r.stderr}")

    subprocess.run(
        _pip() + ["install", "-e", ".", "--quiet"],
        cwd=PROJECT_ROOT, timeout=120,
    )
    ROLLBACK_FILE.unlink(missing_ok=True)

    return InstallResult(
        success=True,
        message=f"Rolled back to {prev_commit[:12]}. Restart OCBrain to apply.",
        restart_required=True,
    )


# ── Restart ───────────────────────────────────────────────────────────────────

def restart():
    """Re-exec the current process in-place — applies updated code immediately."""
    log.info("[updater] Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)
