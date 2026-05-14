import asyncio
import sqlite3
import logging
import time
from collections import deque
from contextlib import closing
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("ocbrain.runtime.state")


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that closes when leaving a context manager."""

    def __exit__(self, exc_type, exc_value, traceback):
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


_ORIGINAL_SQLITE_CONNECT = getattr(sqlite3, "_ocbrain_original_connect", sqlite3.connect)
sqlite3._ocbrain_original_connect = _ORIGINAL_SQLITE_CONNECT


def _connect_closing(*args, **kwargs):
    kwargs.setdefault("factory", ClosingConnection)
    return _ORIGINAL_SQLITE_CONNECT(*args, **kwargs)


sqlite3.connect = _connect_closing


class StateQueue(deque):
    """Deque with a Queue-like qsize() used by diagnostics and tests."""

    def qsize(self) -> int:
        return len(self)


class StateStore:
    """
    Manages runtime state (maturity scores, training data) in SQLite.
    Implements an async write queue to batch I/O and prevent blocking.
    """
    def __init__(self, db_path: str = ".data/runtime_state.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        self._queue = StateQueue()
        self._queue_lock = asyncio.Lock()
        self._flush_task = None
        self._cache = {} # In-memory cache for fast reads
        self._current_batch_size = 100
        self._max_batch_size = 500
        self._load_cache()

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maturity (
                    module_name TEXT PRIMARY KEY,
                    score REAL,
                    query_count INTEGER,
                    updated_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_name TEXT,
                    query TEXT,
                    answer TEXT,
                    timestamp REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tp_module ON training_pairs(module_name)")

    def _load_cache(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute("SELECT module_name, score, query_count FROM maturity")
            for row in cursor:
                self._cache[row[0]] = {"score": row[1], "query_count": row[2]}

    def get_maturity(self, module_name: str) -> Dict[str, Any]:
        return self._cache.get(module_name, {"score": 0.0, "query_count": 0})

    async def update_maturity(self, module_name: str, score: float, query_count: int):
        # Update cache immediately for consistent reads
        self._cache[module_name] = {"score": score, "query_count": query_count}
        async with self._queue_lock:
            self._queue.append(("maturity", (module_name, score, query_count, time.time())))

    async def record_training_pair(self, module_name: str, query: str, answer: str):
        async with self._queue_lock:
            self._queue.append(("training", (module_name, query, answer, time.time())))

    async def start(self):
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            # Final flush
            await self._flush_batch()
            try:
                with closing(sqlite3.connect(self.db_path, timeout=20.0)) as conn:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    conn.execute("PRAGMA journal_mode=DELETE")
            except Exception as e:
                logger.debug("StateStore shutdown checkpoint skipped: %s", e)
            self._flush_task = None
            import gc
            gc.collect()

    async def _flush_loop(self):
        while True:
            try:
                # If the queue is large, we flush more frequently (Adaptive Flushing)
                q_size = len(self._queue)
                if q_size > 500:
                    wait_time = 0.5 # Backlog mode
                elif q_size > 0:
                    wait_time = 1.0 # Active mode
                else:
                    wait_time = 5.0 # Idle mode
                
                await asyncio.sleep(wait_time)
                await self._flush_batch()
            except Exception as e:
                logger.error(f"Error in StateStore flush loop: {e}")

    async def _flush_batch(self):
        batch = []
        async with self._queue_lock:
            # Pull up to current batch size from the head
            while self._queue and len(batch) < self._current_batch_size:
                batch.append(self._queue.popleft())
        
        if not batch:
            return

        # --- OPTIMIZATION: Event Coalescing ---
        # Maturity updates are 'state-overwrite'. Only the newest in a batch matters.
        # Training pairs are 'append-only'. All must be preserved.
        coalesced_maturity = {} # module_name -> latest_data
        training_to_write = []
        
        for msg_type, data in batch:
            if msg_type == "maturity":
                # data is (module_name, score, query_count, timestamp)
                coalesced_maturity[data[0]] = data
            elif msg_type == "training":
                training_to_write.append(data)

        try:
            # Measure flush duration for future congestion control
            start_flush = time.perf_counter()
            
            # Increase timeout to 20s for production resilience
            with closing(sqlite3.connect(self.db_path, timeout=20.0)) as conn:
                # 1. Flush Coalesced Maturity (Deduplicated)
                if coalesced_maturity:
                    conn.executemany("""
                        INSERT INTO maturity (module_name, score, query_count, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(module_name) DO UPDATE SET
                            score=excluded.score,
                            query_count=excluded.query_count,
                            updated_at=excluded.updated_at
                    """, list(coalesced_maturity.values()))
                
                # 2. Flush Training Pairs (Bulk Insert)
                if training_to_write:
                    conn.executemany("""
                        INSERT INTO training_pairs (module_name, query, answer, timestamp)
                        VALUES (?, ?, ?, ?)
                    """, training_to_write)
                
                conn.commit()
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            
            flush_time = time.perf_counter() - start_flush
            
            # Adaptive Congestion Control (AIMD)
            if flush_time < 0.1: # Fast DB
                self._current_batch_size = min(self._max_batch_size, self._current_batch_size + 20)
            elif flush_time > 0.5: # Slow DB
                self._current_batch_size = max(50, self._current_batch_size - 50)
                logger.warning(f"[StateStore] DB Congestion: shrinking batch to {self._current_batch_size}")
                
        except Exception as e:
            logger.error(f"Failed to flush state batch: {e}. Re-queueing {len(batch)} items at FRONT.")
            # Critical: Re-queue items at the FRONT to preserve ordering
            async with self._queue_lock:
                for item in reversed(batch):
                    self._queue.appendleft(item)
            await asyncio.sleep(2.0) # Longer backoff on DB pressure

# Singleton instance
state_store = StateStore()
