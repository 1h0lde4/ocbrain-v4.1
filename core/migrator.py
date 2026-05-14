"""
core/migrator.py — Schema migration runner.
Runs automatically on startup if brain schema < app expected schema.
Each migration is a numbered function — never destructive, always additive.
Trained data is NEVER deleted during migration.
"""
import logging
import sqlite3
from pathlib import Path

from core.brain_version import brain_version_manager

log = logging.getLogger(__name__)

ROOT    = Path(__file__).parent.parent
DATA    = ROOT / "data"
MODULES = ROOT / "modules"


def run_migrations():
    """
    Entry point — called from main.py before anything else starts.
    Runs all pending migrations in order.
    """
    current = brain_version_manager.schema_version
    pending = [m for m in _MIGRATIONS if m["version"] > current]

    if not pending:
        log.info(f"[migrator] Schema v{current} — no migrations needed.")
        return

    log.info(f"[migrator] Running {len(pending)} migration(s) "
             f"from schema v{current}...")

    for migration in sorted(pending, key=lambda m: m["version"]):
        v    = migration["version"]
        name = migration["name"]
        log.info(f"[migrator] → v{v}: {name}")
        try:
            migration["fn"]()
            brain_version_manager.bump_schema(v)
            log.info(f"[migrator] ✓ v{v} complete")
        except Exception as e:
            log.error(f"[migrator] ✗ v{v} FAILED: {e}")
            log.error("[migrator] Stopping — fix migration before retrying.")
            raise


# ── Individual migrations ─────────────────────────────────────

def _migrate_v2():
    """
    V2 migration: add brain_state.json, add evals dir,
    ensure all modules have weights subdirs, ensure __init__.py files.
    Safe to run on V1 installs.
    """
    # 1. Create data/evals if missing
    (DATA / "evals").mkdir(parents=True, exist_ok=True)

    # 2. Ensure all module weight dirs exist
    for mod_dir in MODULES.iterdir():
        if not mod_dir.is_dir() or mod_dir.name.startswith("_"):
            continue
        if mod_dir.name in {"__pycache__"}:
            continue
        for sub in ["weights/active", "weights/previous", "weights/pending"]:
            (mod_dir / sub).mkdir(parents=True, exist_ok=True)

    # 3. Add schema_version to context.sqlite if missing
    ctx_db = DATA / "context.sqlite"
    if ctx_db.exists():
        try:
            conn = sqlite3.connect(str(ctx_db))
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta "
                "(key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_meta VALUES ('schema_version', '2')"
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning(f"[migrator] context.sqlite schema update skipped: {e}")

    # 4. Ensure all __init__.py exist
    for pkg in [ROOT/"core", ROOT/"modules", ROOT/"learning", ROOT/"interface"]:
        init = pkg / "__init__.py"
        if not init.exists():
            init.touch()


_MIGRATIONS = [
    {"version": 2, "name": "V2 brain state + dirs + schema", "fn": _migrate_v2},
    # Future: {"version": 3, "name": "...", "fn": _migrate_v3},
]
