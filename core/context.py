"""
core/context.py — V2.1: WAL journal mode + in-memory context cache.
WAL mode: 3-5× faster concurrent reads.
Memory cache: format_for_prompt() returns cached string for same session turn.
"""
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "context.sqlite"


class Turn:
    __slots__ = ("id", "timestamp", "query", "modules_used", "answer")

    def __init__(self, id, timestamp, query, modules_used, answer):
        self.id           = id
        self.timestamp    = timestamp
        self.query        = query
        self.modules_used = modules_used
        self.answer       = answer


class ContextMemory:
    def __init__(self):
        self._lock = threading.RLock()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)

        # V2.1 FIX: WAL mode — 3-5× faster for concurrent reads
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=10000")
        self._conn.execute("PRAGMA temp_store=MEMORY")
        self._conn.commit()

        self._init_db()

        # V2.1 FIX: in-memory prompt cache
        # CTX-SCOPE-001: keyed by (n, scope), not just n -- otherwise one
        # scope's cached formatted string would be served back to a
        # different scope requesting the same n.
        self._prompt_cache: dict[tuple, str] = {}   # (n, scope) → formatted string
        self._prompt_cache_turn: int = -1          # last turn id when cache was built
        self._turns_cache_dirty: bool = True
        self.long_term_memories = []
        self._long_term_memories_string = ""

    def set_long_term_memories(self, memories: list[dict]):
        self.long_term_memories = memories
        self._long_term_memories_string = ""
        self._turns_cache_dirty = True
        self._prompt_cache.clear()

    def _init_db(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS turns (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp    REAL    NOT NULL,
                    query        TEXT    NOT NULL,
                    modules_used TEXT    NOT NULL,
                    answer       TEXT    NOT NULL,
                    scope        TEXT    NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS entities (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    turn_id INTEGER NOT NULL,
                    type    TEXT    NOT NULL,
                    value   TEXT    NOT NULL,
                    FOREIGN KEY(turn_id) REFERENCES turns(id)
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO schema_meta VALUES ('schema_version','2');
            """)
            # CTX-SCOPE-001 migration: CREATE TABLE IF NOT EXISTS above does
            # not alter a `turns` table that already exists from before the
            # `scope` column was added. Add it explicitly for pre-existing
            # installations; existing rows get the same '' default new rows
            # get, so nothing existing changes scope retroactively.
            existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(turns)").fetchall()}
            if "scope" not in existing_cols:
                cur.execute("ALTER TABLE turns ADD COLUMN scope TEXT NOT NULL DEFAULT ''")
            self._conn.commit()

    def save(self, query: str, modules_used: list[str], answer: str,
             entities: Optional[dict] = None, scope: str = ""):
        """CTX-SCOPE-001: `scope` identifies which caller/task/session this
        turn belongs to, so a caller with a genuinely different scope can
        be excluded from it at read time (see last_n()/format_for_prompt()).
        Defaults to '' -- unchanged behavior for any caller that does not
        yet pass one; opting into isolation is per-caller, not automatic,
        since some callers legitimately want shared continuity within a
        single ongoing session (see tests/test_context.py) and this
        method has no way to know which case it's in on its own.
        """
        from .privacy import privacy
        if not privacy.can_save_history():
            return
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO turns (timestamp, query, modules_used, answer, scope) "
                "VALUES (?,?,?,?,?)",
                (time.time(), query, json.dumps(modules_used), answer, scope),
            )
            turn_id = cur.lastrowid
            if entities:
                for etype, values in entities.items():
                    vals = values if isinstance(values, list) else [values]
                    for v in vals:
                        cur.execute(
                            "INSERT INTO entities (turn_id, type, value) VALUES (?,?,?)",
                            (turn_id, etype, str(v)),
                        )
            self._conn.commit()
            # Invalidate caches on write
            self._turns_cache_dirty = True
            self._prompt_cache.clear()
            self._prompt_cache_turn = turn_id

    def last_n(self, n: int = 10, scope: Optional[str] = None) -> list[Turn]:
        """scope=None (default): unfiltered, matching every prior release's
        behavior exactly -- not a security boundary on its own. Pass an
        explicit scope to restrict results to turns saved with that same
        scope (CTX-SCOPE-001)."""
        with self._lock:
            cur = self._conn.cursor()
            if scope is None:
                cur.execute(
                    "SELECT id, timestamp, query, modules_used, answer "
                    "FROM turns ORDER BY id DESC LIMIT ?", (n,)
                )
            else:
                cur.execute(
                    "SELECT id, timestamp, query, modules_used, answer "
                    "FROM turns WHERE scope=? ORDER BY id DESC LIMIT ?", (scope, n),
                )
            rows = cur.fetchall()
        return [
            Turn(r[0], r[1], r[2], json.loads(r[3]), r[4])
            for r in reversed(rows)
        ]

    def get_entity(self, etype: str, limit: int = 5) -> list[str]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT value FROM entities WHERE type=? "
                "ORDER BY id DESC LIMIT ?", (etype, limit)
            )
            return [r[0] for r in cur.fetchall()]

    def boost_module(self, module_name: str, recent_turns: int = 3) -> float:
        for t in self.last_n(recent_turns):
            if module_name in t.modules_used:
                return 0.1
        return 0.0

    def set_long_term_memories_string(self, context_string: str):
        """Sets the pre-formatted long-term memory string (Phase 5)."""
        self._long_term_memories_string = context_string
        self.long_term_memories = []

    def format_for_prompt(self, n: int = 5, scope: Optional[str] = None) -> str:
        """
        V2.1: cached — returns the same string until a new turn is saved.
        Avoids a DB round-trip on every query in the same session.

        scope=None (default): unfiltered, matching every prior release's
        behavior exactly. Pass an explicit scope to restrict the "RECENT
        CONVERSATION" section to turns saved with that same scope
        (CTX-SCOPE-001) -- otherwise this section is the most recent N
        interactions system-wide, regardless of who produced them.
        """
        with self._lock:
            cache_key = (n, scope)
            if cache_key in self._prompt_cache and not self._turns_cache_dirty:
                return self._prompt_cache[cache_key]

            lines = []
            
            # 1. Long-Term Memory Injection (Phase 3/5)
            if hasattr(self, "_long_term_memories_string") and self._long_term_memories_string:
                lines.append(self._long_term_memories_string)
                lines.append("")
            elif self.long_term_memories:
                lines.append("### RELEVANT KNOWLEDGE")
                for mem in self.long_term_memories:
                    lines.append(f"- {mem.get('summary', mem.get('fact'))}")
                lines.append("")

            # 2. Short-Term History
            turns = self.last_n(n, scope=scope)
            if turns:
                lines.append("### RECENT CONVERSATION")
                for t in turns:
                    lines.append(f"User: {t.query}")
                    lines.append(f"Assistant: {t.answer}")
            
            result = "\n".join(lines)
            self._prompt_cache[cache_key] = result
            self._turns_cache_dirty = False
            return result


context_memory = ContextMemory()
