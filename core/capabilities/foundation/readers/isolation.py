"""
core/capabilities/foundation/readers/isolation.py — run a reader out of process.

``IsolatedRunner`` is the seam. ``SubprocessRunner`` is the baseline
implementation: a fresh interpreter per artifact (``python -I``), scrubbed
environment, empty working directory, artifact bytes on stdin, one JSON
document on stdout, a wall-clock kill of the whole process group, and a hard
cap on how much output the host will buffer. Resource limits (address space,
CPU, no file writes, no new processes) are applied by the child itself before
it imports any parser (readers/isolated_entry.py).

What this baseline does NOT give: a network namespace, a filesystem read jail,
or a seccomp filter. Those belong to the Sandbox Fabric NamespaceBackend
(core/sandbox); pairing FILE_READING's isolated readers with it is the
documented hardening step (ADR-CAP-01 "Deferred") and needs only another
IsolatedRunner implementation -- the readers, adapter and contract do not
change.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Optional, Protocol

ENTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "isolated_entry.py")


@dataclass(frozen=True)
class IsolationLimits:
    timeout_sec: float = 20.0
    max_output_bytes: int = 24_000_000
    max_stderr_bytes: int = 2048


@dataclass
class IsolatedResult:
    # completed | timeout | output_limit | crashed | spawn_failed | cancelled
    termination: str
    exit_code: Optional[int] = None
    stdout: bytes = b""
    stderr_tail: str = ""
    duration_sec: float = 0.0


class IsolatedRunner(Protocol):
    name: str

    async def run(self, reader_id: str, opts_json: str, data: bytes,
                  limits: IsolationLimits) -> IsolatedResult: ...


class SubprocessRunner:
    name = "subprocess"

    def __init__(self, python: Optional[str] = None,
                 entry_path: str = ENTRY_PATH) -> None:
        self._python = python or sys.executable
        self._entry = entry_path

    async def run(self, reader_id: str, opts_json: str, data: bytes,
                  limits: IsolationLimits) -> IsolatedResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="ocbrain-read-") as cwd:
            try:
                proc = await asyncio.create_subprocess_exec(
                    self._python, "-I", self._entry, reader_id, opts_json,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={"OCBRAIN_ISOLATED_READER": "1", "LANG": "C.UTF-8",
                         "PATH": ""},
                    cwd=cwd, close_fds=True, start_new_session=True)
            except (OSError, ValueError):
                return IsolatedResult("spawn_failed",
                                      duration_sec=time.monotonic() - started)

            out = bytearray()
            err = bytearray()
            over = {"output": False}

            async def feed() -> None:
                try:
                    proc.stdin.write(data)
                    await proc.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass  # child exited early; its result is read below
                finally:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass

            async def drain(stream, sink: bytearray, cap: int, flag: bool) -> None:
                while True:
                    chunk = await stream.read(65536)
                    if not chunk:
                        return
                    if len(sink) + len(chunk) > cap:
                        sink.extend(chunk[: max(0, cap - len(sink))])
                        if flag:
                            over["output"] = True
                            self._kill(proc)
                        return
                    sink.extend(chunk)

            tasks = [asyncio.ensure_future(feed()),
                     asyncio.ensure_future(drain(proc.stdout, out,
                                                 limits.max_output_bytes, True)),
                     asyncio.ensure_future(drain(proc.stderr, err,
                                                 limits.max_stderr_bytes, False))]
            termination = "completed"
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, proc.wait()),
                                       timeout=limits.timeout_sec)
            except asyncio.TimeoutError:
                termination = "timeout"
                self._kill(proc)
            except asyncio.CancelledError:
                self._kill(proc)
                raise
            finally:
                for t in tasks:
                    t.cancel()
                self._kill(proc)  # no-op when already exited
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception:
                    pass
            if over["output"]:
                termination = "output_limit"
            elif termination == "completed" and proc.returncode not in (0, None):
                termination = "crashed"
            return IsolatedResult(
                termination=termination, exit_code=proc.returncode,
                stdout=bytes(out),
                stderr_tail=bytes(err[-limits.max_stderr_bytes:]).decode(
                    "utf-8", "replace"),
                duration_sec=time.monotonic() - started)

    @staticmethod
    def _kill(proc) -> None:
        if proc.returncode is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except Exception:
                pass
