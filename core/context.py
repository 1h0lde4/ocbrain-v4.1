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
        self._prompt_cache: dict[int, str] = {}   # n_turns → formatted string
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
                    answer       TEXT    NOT NULL
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
            self._conn.commit()

    def save(self, query: str, modules_used: list[str], answer: str,
             entities: Optional[dict] = None):
        from .privacy import privacy
        if not privacy.can_save_history():
            return
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO turns (timestamp, query, modules_used, answer) VALUES (?,?,?,?)",
                (time.time(), query, json.dumps(modules_used), answer),
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

    def last_n(self, n: int = 10) -> list[Turn]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id, timestamp, query, modules_used, answer "
                "FROM turns ORDER BY id DESC LIMIT ?", (n,)
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

    def format_for_prompt(self, n: int = 5) -> str:
        """
        V2.1: cached — returns the same string until a new turn is saved.
        Avoids a DB round-trip on every query in the same session.
        """
        with self._lock:
            if n in self._prompt_cache and not self._turns_cache_dirty:
                return self._prompt_cache[n]

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
            turns = self.last_n(n)
            if turns:
                lines.append("### RECENT CONVERSATION")
                for t in turns:
                    lines.append(f"User: {t.query}")
                    lines.append(f"Assistant: {t.answer}")
            
            result = "\n".join(lines)
            self._prompt_cache[n] = result
            self._turns_cache_dirty = False
            return result


context_memory = ContextMemory()
