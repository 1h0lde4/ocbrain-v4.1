"""core/workflow/instance_guard.py -- single-flight guard on a workflow ``instance_id``.

DEBT-028 / ADR-KERNEL-10 (PROPOSED).  ``WorkflowRuntime.execute()`` and
``resume()`` have no instance-level exclusion: two concurrent callers on one
``instance_id`` race on shared execution state.  This module is the guard.

Design (see ADR-KERNEL-10 for the full reasoning and the rejected alternatives):

* The guard is **reject-fast, never queueing**.  A second claimant on a held
  ``instance_id`` gets ``InstanceBusyError`` immediately.  Nothing waits, so
  there is no queue to grow, no lock-ordering to get wrong and no deadlock.
* Its scope is an **explicit deployment setting**, not a guess about the
  deployment (the register's Oct 28 requirement: "the guard must coordinate at
  the actual deployment boundary"):

  ``process``  in-process registry only.  Zero I/O.  Correct while exactly one
               process owns the checkpoint store -- today's deployment.
  ``host``     additionally a durable **lease** in a shared SQLite file, so
               several processes on one host that share a data directory cannot
               both run the same instance.  A holder renews its lease while it
               runs; a crashed holder's lease simply expires.  There is no PID
               liveness probing (``os.kill(pid, 0)`` terminates the process on
               Windows).  If the lease is ever lost mid-run the guard invokes
               ``on_lost`` so the runtime can cancel the work instead of letting
               it silently become a duplicate.
* ``host`` scope **fails closed**: if exclusivity cannot be established or
  stored, ``ClaimUnavailableError`` is raised and the caller must not run.
* No state is hidden: the in-process registry holds only instance ids that are
  in flight right now, and an entry is removed on every exit path.

Not a multi-host lock: a lease compares wall clocks, which is sound on one host
and not across hosts.  Cross-host coordination is out of scope (ADR-KERNEL-10).
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import os
import socket
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Protocol,
    Set,
    Union,
)

logger = logging.getLogger("ocbrain.workflow.instance_guard")

DEFAULT_CLAIM_DB_PATH = ".data/events/workflow_claims.db"
DEFAULT_LEASE_TTL_S = 60.0

OnLost = Callable[[], Union[None, Awaitable[None]]]


class ClaimScope(str, Enum):
    """Where exclusivity is enforced."""

    PROCESS = "process"
    HOST = "host"


@dataclass(frozen=True)
class ClaimInfo:
    """A durable claim as stored; returned to a loser so the error is specific."""

    holder_id: str
    host: str
    pid: int
    operation: str
    acquired_at: float
    lease_expires_at: float

    def describe(self) -> str:
        return f"{self.operation} by pid {self.pid} on {self.host}"


class InstanceBusyError(Exception):
    """Another caller holds this ``instance_id``.  Raised immediately, never after waiting."""

    def __init__(
        self,
        instance_id: str,
        *,
        scope: ClaimScope,
        operation_in_flight: str = "",
        holder: Optional[ClaimInfo] = None,
    ) -> None:
        self.instance_id = instance_id
        self.scope = scope
        self.operation_in_flight = operation_in_flight
        self.holder = holder
        who = holder.describe() if holder is not None else (operation_in_flight or "another caller")
        super().__init__(
            f"workflow instance '{instance_id}' is already in flight ({who}; scope={scope.value})"
        )


class ClaimUnavailableError(Exception):
    """``host`` scope could not establish or persist exclusivity -- the caller must not run."""

    def __init__(self, instance_id: str, cause: BaseException) -> None:
        self.instance_id = instance_id
        super().__init__(
            f"cannot establish exclusive claim on workflow instance '{instance_id}': "
            f"{type(cause).__name__}: {cause}"
        )


class ClaimStore(Protocol):
    """Durable claim backend.  All times come from the store's own clock."""

    async def acquire(
        self, instance_id: str, *, holder_id: str, operation: str, ttl_s: float
    ) -> Optional[ClaimInfo]:
        """Return ``None`` if the claim was taken, else the live holder's ``ClaimInfo``."""

    async def renew(self, instance_id: str, *, holder_id: str, ttl_s: float) -> bool:
        """Extend the lease; ``False`` if ``holder_id`` no longer holds the claim."""

    async def release(self, instance_id: str, *, holder_id: str) -> None:
        """Drop the claim if (and only if) ``holder_id`` still holds it."""


_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS workflow_instance_claims ("
    " instance_id TEXT PRIMARY KEY,"
    " holder_id TEXT NOT NULL,"
    " host TEXT NOT NULL,"
    " pid INTEGER NOT NULL,"
    " operation TEXT NOT NULL,"
    " acquired_at REAL NOT NULL,"
    " lease_expires_at REAL NOT NULL)"
)
_COLUMNS = "holder_id, host, pid, operation, acquired_at, lease_expires_at"


class SqliteClaimStore:
    """Lease claims in a small SQLite file shared by every process on the host.

    Every operation opens its own connection and runs in a worker thread
    (``asyncio.to_thread``), so no SQLite call ever blocks the event loop and
    no connection crosses a thread.  Writers are serialised by
    ``BEGIN IMMEDIATE`` plus a busy timeout; acquire is a single transaction,
    so two processes cannot both win.  Expired rows are purged inside the same
    transaction, so crash leftovers do not accumulate.
    """

    def __init__(
        self,
        db_path: str = DEFAULT_CLAIM_DB_PATH,
        *,
        clock: Callable[[], float] = time.time,
        busy_timeout_s: float = 5.0,
    ) -> None:
        if busy_timeout_s <= 0:
            raise ValueError("busy_timeout_s must be > 0")
        self._db_path = db_path
        self._clock = clock
        self._busy_timeout_s = busy_timeout_s
        self._host = socket.gethostname()
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with closing(self._connect()) as conn:  # fail at construction, not at first use
            conn.execute(_SCHEMA)

    @property
    def db_path(self) -> str:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        # isolation_level=None: autocommit; transactions are explicit below.
        return sqlite3.connect(self._db_path, timeout=self._busy_timeout_s, isolation_level=None)

    def _acquire_sync(
        self, instance_id: str, holder_id: str, operation: str, ttl_s: float
    ) -> Optional[ClaimInfo]:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = self._clock()
                conn.execute("DELETE FROM workflow_instance_claims WHERE lease_expires_at <= ?", (now,))
                row = conn.execute(
                    f"SELECT {_COLUMNS} FROM workflow_instance_claims WHERE instance_id = ?",
                    (instance_id,),
                ).fetchone()
                if row is not None:
                    conn.execute("ROLLBACK")
                    return ClaimInfo(*row)
                conn.execute(
                    "INSERT INTO workflow_instance_claims "
                    "(instance_id, holder_id, host, pid, operation, acquired_at, lease_expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (instance_id, holder_id, self._host, os.getpid(), operation, now, now + ttl_s),
                )
                conn.execute("COMMIT")
                return None
            except BaseException:
                with contextlib.suppress(sqlite3.Error):
                    conn.execute("ROLLBACK")
                raise

    def _renew_sync(self, instance_id: str, holder_id: str, ttl_s: float) -> bool:
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "UPDATE workflow_instance_claims SET lease_expires_at = ? "
                "WHERE instance_id = ? AND holder_id = ?",
                (self._clock() + ttl_s, instance_id, holder_id),
            )
            return cur.rowcount == 1

    def _release_sync(self, instance_id: str, holder_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "DELETE FROM workflow_instance_claims WHERE instance_id = ? AND holder_id = ?",
                (instance_id, holder_id),
            )

    async def acquire(
        self, instance_id: str, *, holder_id: str, operation: str, ttl_s: float
    ) -> Optional[ClaimInfo]:
        return await asyncio.to_thread(self._acquire_sync, instance_id, holder_id, operation, ttl_s)

    async def renew(self, instance_id: str, *, holder_id: str, ttl_s: float) -> bool:
        return await asyncio.to_thread(self._renew_sync, instance_id, holder_id, ttl_s)

    async def release(self, instance_id: str, *, holder_id: str) -> None:
        await asyncio.to_thread(self._release_sync, instance_id, holder_id)


class InstanceGuard:
    """Reject-fast single-flight claims on workflow instance ids."""

    def __init__(
        self,
        store: Optional[ClaimStore] = None,
        *,
        ttl_s: float = DEFAULT_LEASE_TTL_S,
        renew_interval_s: Optional[float] = None,
    ) -> None:
        if ttl_s <= 0:
            raise ValueError("ttl_s must be > 0")
        interval = ttl_s / 3.0 if renew_interval_s is None else renew_interval_s
        if not 0 < interval < ttl_s:
            raise ValueError("renew_interval_s must be > 0 and < ttl_s")
        self._store = store
        self._ttl_s = ttl_s
        self._renew_interval_s = interval
        self._active: Dict[str, str] = {}  # instance_id -> operation, in flight right now
        self._mutex = threading.Lock()
        self._release_tasks: Set["asyncio.Task[None]"] = set()

    @classmethod
    def from_scope(
        cls,
        scope: str,
        *,
        db_path: Optional[str] = None,
        ttl_s: float = DEFAULT_LEASE_TTL_S,
    ) -> "InstanceGuard":
        """Build the guard for a configured scope.  An unknown scope is an error, never a fallback."""
        try:
            parsed = ClaimScope(str(scope).strip().lower())
        except ValueError:
            valid = ", ".join(s.value for s in ClaimScope)
            raise ValueError(f"unknown workflow claim scope {scope!r}; expected one of: {valid}") from None
        if parsed is ClaimScope.PROCESS:
            return cls(None, ttl_s=ttl_s)
        return cls(SqliteClaimStore(db_path or DEFAULT_CLAIM_DB_PATH), ttl_s=ttl_s)

    @property
    def scope(self) -> ClaimScope:
        return ClaimScope.PROCESS if self._store is None else ClaimScope.HOST

    @property
    def active_count(self) -> int:
        with self._mutex:
            return len(self._active)

    @asynccontextmanager
    async def claim(
        self,
        instance_id: str,
        *,
        operation: str,
        on_lost: Optional[OnLost] = None,
    ) -> AsyncIterator[None]:
        """Hold exclusivity on ``instance_id`` for the duration of the ``async with`` body.

        Raises ``InstanceBusyError`` at once if it is held, and
        ``ClaimUnavailableError`` if ``host`` scope cannot prove exclusivity.
        """
        if not instance_id:
            raise ValueError("instance_id must be non-empty")
        with self._mutex:
            in_flight = self._active.get(instance_id)
            if in_flight is None:
                self._active[instance_id] = operation
        if in_flight is not None:
            raise InstanceBusyError(
                instance_id, scope=ClaimScope.PROCESS, operation_in_flight=in_flight
            )
        holder_id = uuid.uuid4().hex
        heartbeat: Optional["asyncio.Task[None]"] = None
        durable = False
        try:
            if self._store is not None:
                try:
                    holder = await self._store.acquire(
                        instance_id, holder_id=holder_id, operation=operation, ttl_s=self._ttl_s
                    )
                except asyncio.CancelledError:
                    self._spawn_release(instance_id, holder_id)  # the thread may have committed
                    raise
                except Exception as exc:
                    raise ClaimUnavailableError(instance_id, exc) from exc
                if holder is not None:
                    raise InstanceBusyError(instance_id, scope=ClaimScope.HOST, holder=holder)
                durable = True
                heartbeat = asyncio.create_task(self._renew_loop(instance_id, holder_id, on_lost))
            yield
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await heartbeat
            if durable:
                await self._release_shielded(instance_id, holder_id)
            with self._mutex:
                self._active.pop(instance_id, None)

    async def _renew_loop(self, instance_id: str, holder_id: str, on_lost: Optional[OnLost]) -> None:
        assert self._store is not None
        last_ok = time.monotonic()
        while True:
            await asyncio.sleep(self._renew_interval_s)
            lost = False
            try:
                if await self._store.renew(instance_id, holder_id=holder_id, ttl_s=self._ttl_s):
                    last_ok = time.monotonic()
                else:
                    lost = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # A transient store error is not yet a lost claim: the lease is
                # still valid until it would have expired without a renewal.
                logger.warning("instance claim renew failed for '%s': %s", instance_id, exc)
                lost = (time.monotonic() - last_ok) >= self._ttl_s
            if lost:
                logger.error("instance claim LOST for '%s'", instance_id)
                if on_lost is not None:
                    try:
                        outcome = on_lost()
                        if inspect.isawaitable(outcome):
                            await outcome
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.error("on_lost handler failed for '%s': %s", instance_id, exc)
                return

    async def _safe_release(self, instance_id: str, holder_id: str) -> None:
        """Never raises: a failed release only means the lease expires on its own."""
        assert self._store is not None
        try:
            await self._store.release(instance_id, holder_id=holder_id)
        except Exception as exc:
            logger.warning(
                "instance claim release failed for '%s' (lease will expire): %s", instance_id, exc
            )

    async def _release_shielded(self, instance_id: str, holder_id: str) -> None:
        # Shield so a cancellation of the caller cannot abandon the release.
        await asyncio.shield(self._safe_release(instance_id, holder_id))

    def _spawn_release(self, instance_id: str, holder_id: str) -> None:
        task = asyncio.ensure_future(self._safe_release(instance_id, holder_id))
        self._release_tasks.add(task)
        task.add_done_callback(self._release_tasks.discard)


__all__ = [
    "ClaimInfo",
    "ClaimScope",
    "ClaimStore",
    "ClaimUnavailableError",
    "DEFAULT_CLAIM_DB_PATH",
    "DEFAULT_LEASE_TTL_S",
    "InstanceBusyError",
    "InstanceGuard",
    "SqliteClaimStore",
]
