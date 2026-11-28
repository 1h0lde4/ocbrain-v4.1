"""Child process for tests/test_workflow_instance_guard.py (not a test module: no ``test_`` prefix).

argv: <repo_root> <claim_db_path> <instance_id> <lease_ttl_seconds>

Takes a durable (host-scope) claim on ``instance_id`` through the real
``InstanceGuard`` + ``SqliteClaimStore``, prints ``CLAIMED`` once it holds it, then
holds it (renewing the lease through the guard's heartbeat) until the parent
kills it.  The parent uses this to prove that a claim held by ANOTHER PROCESS
refuses a second claimant, stays valid while the holder lives, and frees itself
after the holder is hard-killed (no cleanup runs: ``SIGKILL`` on POSIX,
``TerminateProcess`` on Windows).
"""
import asyncio
import sys

sys.path.insert(0, sys.argv[1])
DB, INSTANCE, TTL = sys.argv[2], sys.argv[3], float(sys.argv[4])

from core.workflow.instance_guard import InstanceGuard, SqliteClaimStore  # noqa: E402


async def main() -> None:
    guard = InstanceGuard(SqliteClaimStore(DB), ttl_s=TTL)
    async with guard.claim(INSTANCE, operation="resume"):
        print("CLAIMED", flush=True)
        await asyncio.sleep(3600)


asyncio.run(main())
