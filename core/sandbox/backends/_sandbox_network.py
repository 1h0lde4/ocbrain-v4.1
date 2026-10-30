"""core/sandbox/backends/_sandbox_network.py -- capacity and IPv6 guard
primitives for per-sandbox networks.

Workstream ``sandbox-network-isolation``, batch B03. Governing text:
docs/architecture/sandbox-network-isolation-master-specification.md,
section 8 (capacity), section 9 (IPv6), invariants INV-7 and INV-8, test
TC-14. Evidence record: reconciliation document section 22 (OD-6).

STATUS: INERT. Nothing imports this module. ``DockerBackend.create()`` does
not call it and neither does the admission path; a test pins that. It holds
two guards that every per-sandbox-network design needs, built first and with
no dependence on a firewall so that the wiring batch (B11, only after the
user's decision DG-1) cannot silently reuse an assumption. Because it is not
wired, INV-7 and INV-8 are NOT enforced by the product yet: what exists is
two primitives with unit tests, not a security gate, and no ``SandboxCapability``
changes because of it.

What is here
------------
* ``MAX_CONCURRENT_SANDBOX_NETWORKS`` -- the product ceiling, 29 (ruling
  OD-5). It is a ceiling, not a guarantee on every host.
* ``CapacityProbe`` -- the interface a start-up or provisioning probe
  implements. There is deliberately no implementation here: measuring
  capacity means creating networks, which is out of scope for B03.
* ``effective_limit`` / ``resolve_effective_limit`` -- the effective limit is
  ``min(29, probe result)``. A probe that fails or returns something that is
  not a non-negative integer is an error: the ceiling is never assumed.
* ``NetworkSlotLimiter`` -- a counting limiter. A slot is reserved before a
  network is created and released only after the network's removal is
  confirmed. If removal cannot be confirmed the caller keeps the slot held
  (the handle is retained, spec section 10). It is a single lock-protected
  counter (D11); critical sections are O(1) and do no I/O, and the log calls
  run outside the lock. The lock is therefore safe to take from async code;
  the log handlers attached to ``ocbrain.sandbox.network`` are not under this
  module's control and may block.
* ``Ipv6Sources`` / ``evaluate_ipv6`` / ``enforce_ipv6_guard`` -- IPv6 is
  treated as off only if ``/proc/sys/net/ipv6`` is absent or ``disable_ipv6``
  is 1 for ``all`` and ``default``; anything else is on or unknown and is
  refused. The kernel facts are read through injectable callables.

What is NOT here (out of scope for B03)
---------------------------------------
Network creation, firewall rules, the canary, wiring into ``create()``, the
capacity probe implementation, TC-13 and TC-15 (real-host tests), and any
claim that IPv6 isolation works (it is UNVERIFIED, spec section 9).

Design decisions the wiring batch must know
-------------------------------------------
* Leaf module: standard library only. ``DockerBackendError`` lives in
  ``docker_backend.py``, which B11 will import this module from; importing it
  here would make an import cycle the moment the guards are wired. The errors
  below therefore derive from ``RuntimeError`` (as ``DockerBackendError``
  does) under ``SandboxNetworkGuardError``, and ``create()`` is expected to
  surface them as ``DockerBackendError`` at the wiring boundary (spec section
  8 asks for a defined error in that family). This is recorded as an
  interpretation in reconciliation section 22.
* ``proc_ipv6_sources()`` does three small synchronous procfs reads. In an
  async path call the guard through ``asyncio.to_thread``. The same holds for
  a ``CapacityProbe``: ``probe()`` is synchronous, and an ``async def probe``
  returns a coroutine, which is refused as a probe error (and leaves an
  un-awaited coroutine behind); run a blocking probe through
  ``asyncio.to_thread`` and pass the integer.
* ``/proc/sys/net/ipv6`` being absent only counts as "IPv6 off" when
  ``/proc/sys/net`` itself is present. If procfs is not readable the absence
  proves nothing, and that case is UNKNOWN (refused). This narrows the
  specification's wording in the refusing direction only.
* The IPv6 rule is a conservative precheck of the network namespace this
  process runs in: ``proc_ipv6_sources()`` reads that namespace's
  ``/proc/sys/net/ipv6`` and no sandbox's. A pass says only that the
  controller's own namespace reports IPv6 off. It does not show that any
  sandbox network is isolated for IPv6, and ``enforce_ipv6_guard`` is not by
  itself enforcement of INV-8 (spec section 9: IPv6 isolation is UNVERIFIED).
  Which mechanism enforces INV-8, and over what scope, is not decided here.
  Two limits of that reading follow. It is a point-in-time fact: an absent
  ``/proc/sys/net/ipv6`` is what ``ipv6.disable=1`` produces, but on a kernel
  where IPv6 is a loadable module that is not loaded yet, whether the first
  IPv6 socket loads it is unverified here, so the reason text states what the
  kernel exposes, not that IPv6 cannot appear. And the controller may run in a
  container whose network namespace is not the one in which the Docker daemon
  creates bridges; a pass read there says nothing about the daemon's.
* The refusals are picklable and copyable (``__reduce__``): the worker pool,
  the webhook process and the task runner are separate processes, so a refusal
  must survive crossing one.
"""
from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Final, Protocol

logger = logging.getLogger("ocbrain.sandbox.network")

__all__ = [
    "MAX_CONCURRENT_SANDBOX_NETWORKS",
    "CapacityProbe",
    "Ipv6Decision",
    "Ipv6Sources",
    "Ipv6State",
    "NetworkSlot",
    "NetworkSlotLimiter",
    "SandboxIPv6RefusedError",
    "SandboxNetworkCapacityError",
    "SandboxNetworkCapacityProbeError",
    "SandboxNetworkGuardError",
    "effective_limit",
    "enforce_ipv6_guard",
    "evaluate_ipv6",
    "proc_ipv6_sources",
    "resolve_effective_limit",
]

#: The product ceiling for concurrent sandbox networks (ruling OD-5). Measured
#: once as the number of additional internal networks Docker accepted under its
#: default address pools (study F8); a property of the pool configuration, not a
#: Docker constant. Raising it needs a new ruling, so the limiter refuses to be
#: built above it.
MAX_CONCURRENT_SANDBOX_NETWORKS: Final[int] = 29

_SYSCTL_NET: Final[str] = "/proc/sys/net"
_IPV6_SCOPES: Final[tuple[str, str]] = ("all", "default")


def _emit(level: int, event: str, **fields: object) -> None:
    """One structured log record per guard decision (INV-9): a readable
    message plus the same facts as a dict on the record for JSON formatters."""
    detail = " ".join(f"{key}={value!r}" for key, value in fields.items())
    logger.log(
        level,
        "%s %s",
        event,
        detail,
        extra={"sandbox_network_event": {"event": event, **fields}},
    )


def _describe_error(error: BaseException) -> str:
    """``TypeName: message`` for a reason or a log field. An injected source or
    probe is outside this module's control, so the text of its exception is not
    trusted: an exception whose own ``__str__`` raises must not turn into a
    second, unrelated exception inside a guard."""
    try:
        return f"{type(error).__name__}: {error}"
    except Exception:  # noqa: BLE001 - fail closed: the text of a foreign exception is not trusted
        return f"{type(error).__name__}: <its message could not be rendered>"


# --------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------


class SandboxNetworkGuardError(RuntimeError):
    """Base of every refusal raised by this module. A ``RuntimeError`` like
    ``DockerBackendError``, but defined here so this module stays a leaf."""


class SandboxNetworkCapacityError(SandboxNetworkGuardError):
    """No slot is free: ``in_use`` of ``limit`` are held (INV-7). A refused
    reservation changes no state."""

    def __init__(self, *, limit: int, in_use: int, owner: str) -> None:
        super().__init__(
            f"sandbox network capacity exhausted: {in_use} of {limit} slots in use; "
            f"refusing a new networked sandbox for {owner!r}"
        )
        self.limit = limit
        self.in_use = in_use
        self.owner = owner

    def __reduce__(self) -> tuple[object, ...]:
        # ``args`` holds only the message, so the default reduction would call
        # ``__init__`` with the wrong arguments on copy or unpickle. Rebuild
        # from the real fields and carry ``__dict__`` (``add_note`` notes).
        return (_rebuild_capacity_error, (type(self), self.limit, self.in_use, self.owner), dict(vars(self)))


def _rebuild_capacity_error(
    cls: type[SandboxNetworkCapacityError], limit: int, in_use: int, owner: str
) -> SandboxNetworkCapacityError:
    """Module-level so it can be pickled by reference; used by ``__reduce__``."""
    return cls(limit=limit, in_use=in_use, owner=owner)


class SandboxNetworkCapacityProbeError(SandboxNetworkGuardError):
    """The capacity probe raised, or returned something that is not a
    non-negative integer. Fail closed: the ceiling is not assumed instead."""


# --------------------------------------------------------------------
# Capacity (spec section 8, INV-7)
# --------------------------------------------------------------------


class CapacityProbe(Protocol):
    """Interface of the start-up or provisioning capacity probe."""

    def probe(self) -> int:
        """Return how many concurrent sandbox networks this host's Docker
        daemon can actually hold (a non-negative integer), or raise."""
        ...


def effective_limit(probe_result: object) -> int:
    """The ruled effective limit, ``min(29, probe result)`` (OD-5).

    A host that can hold none yields 0 (every networked sandbox is refused).
    A result that is not a plain non-negative integer is a probe error."""
    if isinstance(probe_result, bool) or not isinstance(probe_result, int):
        raise SandboxNetworkCapacityProbeError(
            f"capacity probe returned {probe_result!r} ({type(probe_result).__name__}), "
            "not an integer; not assuming the ceiling"
        )
    if probe_result < 0:
        raise SandboxNetworkCapacityProbeError(
            f"capacity probe returned {probe_result}, which is negative; not assuming the ceiling"
        )
    return min(MAX_CONCURRENT_SANDBOX_NETWORKS, probe_result)


def resolve_effective_limit(probe: CapacityProbe) -> int:
    """Run ``probe`` once and return ``effective_limit`` of its result. Any
    failure of the probe is a ``SandboxNetworkCapacityProbeError`` (chained),
    never a silent fallback to the ceiling."""
    try:
        result = probe.probe()
    except Exception as exc:
        description = _describe_error(exc)
        _emit(logging.ERROR, "sandbox_network_capacity_probe_failed", error=description)
        raise SandboxNetworkCapacityProbeError(
            f"capacity probe failed ({description}); not assuming the ceiling"
        ) from exc
    limit = effective_limit(result)
    _emit(
        logging.INFO,
        "sandbox_network_capacity_resolved",
        probe_result=result,
        ceiling=MAX_CONCURRENT_SANDBOX_NETWORKS,
        effective_limit=limit,
    )
    return limit


@dataclass(frozen=True, eq=False)
class NetworkSlot:
    """A held capacity slot, returned by ``NetworkSlotLimiter.reserve``.

    Compared by identity on purpose: two reservations by the same owner are two
    slots. Create it only through ``reserve``. Do not copy or pickle a slot: a
    copy is a different object, so ``release(copy)`` returns False and the
    original stays held (a deep copy or a pickle fails outright, as the limiter
    holds a lock). Keep the one object ``reserve`` returned."""

    owner: str
    limiter: NetworkSlotLimiter = field(repr=False)


class NetworkSlotLimiter:
    """Counting limiter for concurrent sandbox networks (INV-7, D11).

    Usage contract for the wiring batch: ``reserve`` before the network is
    created; ``release`` only after the network's removal is confirmed; if
    removal cannot be confirmed, keep the slot held. ``release`` is idempotent
    per slot, so a double ``destroy()`` cannot return one slot twice and open
    the limit."""

    def __init__(self, limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError(f"limit must be an int, got {limit!r} ({type(limit).__name__})")
        if not 0 <= limit <= MAX_CONCURRENT_SANDBOX_NETWORKS:
            raise ValueError(
                f"limit must be between 0 and {MAX_CONCURRENT_SANDBOX_NETWORKS} "
                f"(the product ceiling; raising it needs a new ruling), got {limit}"
            )
        self._limit = limit
        self._lock = threading.Lock()
        self._held: set[NetworkSlot] = set()

    @classmethod
    def from_probe(cls, probe: CapacityProbe) -> NetworkSlotLimiter:
        """A limiter whose limit is ``min(29, probe result)``."""
        return cls(resolve_effective_limit(probe))

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def in_use(self) -> int:
        with self._lock:
            return len(self._held)

    @property
    def available(self) -> int:
        with self._lock:
            return self._limit - len(self._held)

    def reserve(self, owner: str) -> NetworkSlot:
        """Take a slot or raise ``SandboxNetworkCapacityError``. A refusal
        changes no state. ``owner`` only labels the log records.

        If the log call that follows the reservation raises (a logging filter
        or hook can; ``logging`` itself only swallows failing handlers), the
        slot is given back before the exception propagates: the caller never
        received it and so could never release it."""
        with self._lock:
            in_use = len(self._held)
            slot: NetworkSlot | None = None
            if in_use < self._limit:
                slot = NetworkSlot(owner=owner, limiter=self)
                self._held.add(slot)
                in_use += 1
        if slot is None:
            _emit(
                logging.WARNING,
                "sandbox_network_capacity_refused",
                owner=owner,
                limit=self._limit,
                in_use=in_use,
            )
            raise SandboxNetworkCapacityError(limit=self._limit, in_use=in_use, owner=owner)
        try:
            _emit(
                logging.DEBUG,
                "sandbox_network_slot_reserved",
                owner=owner,
                limit=self._limit,
                in_use=in_use,
            )
        except BaseException:
            with self._lock:
                self._held.discard(slot)
            raise
        return slot

    def release(self, slot: NetworkSlot) -> bool:
        """Return ``slot``; True if this call released it, False if it was not
        held (already released). A slot of another limiter is a ``ValueError``
        and changes nothing. The slot is freed before the log call, so a log
        call that raises cannot keep it held."""
        if slot.limiter is not self:
            raise ValueError("slot belongs to a different limiter")
        with self._lock:
            released = slot in self._held
            if released:
                self._held.discard(slot)
            in_use = len(self._held)
        _emit(
            logging.DEBUG,
            "sandbox_network_slot_released" if released else "sandbox_network_slot_release_ignored",
            owner=slot.owner,
            limit=self._limit,
            in_use=in_use,
        )
        return released


# --------------------------------------------------------------------
# IPv6 (spec section 9, INV-8)
# --------------------------------------------------------------------


class Ipv6State(Enum):
    OFF = "off"
    ON = "on"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Ipv6Decision:
    """The result of reading the IPv6 facts. Only ``OFF`` is supported in v1;
    ``ON`` and ``UNKNOWN`` are both refused (fail closed)."""

    state: Ipv6State
    reason: str

    @property
    def supported(self) -> bool:
        return self.state is Ipv6State.OFF


class SandboxIPv6RefusedError(SandboxNetworkGuardError):
    """A networked sandbox is refused because IPv6 is on or unknown (INV-8)."""

    def __init__(self, decision: Ipv6Decision) -> None:
        super().__init__(
            f"networked sandbox refused: IPv6 is {decision.state.value} on this host "
            f"({decision.reason}); IPv6 isolation is unverified, so networked sandboxes "
            "are refused unless IPv6 is disabled for 'all' and 'default'"
        )
        self.decision = decision

    def __reduce__(self) -> tuple[object, ...]:
        # ``args`` holds only the message, not the ``Ipv6Decision`` the
        # constructor takes; rebuild from the decision and carry ``__dict__``.
        return (type(self), (self.decision,), dict(vars(self)))


@dataclass(frozen=True)
class Ipv6Sources:
    """Injectable view of the kernel facts the guard reads.

    ``sysctl_net_present``: the net sysctl directory (``/proc/sys/net``) is
    readable, which is what makes the absence of ``ipv6`` beneath it mean
    something. ``ipv6_dir_present``: ``/proc/sys/net/ipv6`` exists.
    ``read_disable_ipv6(scope)``: the text of ``conf/<scope>/disable_ipv6``
    for scope ``all`` or ``default``. Each may raise; any exception is read as
    UNKNOWN, never as off. The two presence checks must return a real ``bool``
    and the read a ``str``: a value of any other type is a source that broke
    its contract, and is UNKNOWN too, whether or not it is falsy."""

    sysctl_net_present: Callable[[], bool]
    ipv6_dir_present: Callable[[], bool]
    read_disable_ipv6: Callable[[str], str]


def proc_ipv6_sources(sysctl_net: str = _SYSCTL_NET) -> Ipv6Sources:
    """The real sources: synchronous reads of procfs (use ``asyncio.to_thread``
    from async code). Absence is ``FileNotFoundError`` only; every other
    failure propagates so the decision reads it as UNKNOWN."""
    ipv6_dir = os.path.join(sysctl_net, "ipv6")

    def _exists(path: str) -> bool:
        try:
            os.stat(path)
        except FileNotFoundError:
            return False
        return True

    def _read(scope: str) -> str:
        with open(os.path.join(ipv6_dir, "conf", scope, "disable_ipv6"), encoding="ascii") as fh:
            return fh.read()

    return Ipv6Sources(
        sysctl_net_present=lambda: _exists(sysctl_net),
        ipv6_dir_present=lambda: _exists(ipv6_dir),
        read_disable_ipv6=_read,
    )


def evaluate_ipv6(sources: Ipv6Sources) -> Ipv6Decision:
    """Classify IPv6 as OFF, ON or UNKNOWN from ``sources`` (spec section 9).

    OFF only when the ipv6 sysctl directory is absent (with the net sysctl
    directory present) or ``disable_ipv6`` is 1 for both ``all`` and
    ``default``. A 0 for either scope is ON. Anything else, including an
    unreadable or unrecognised value (a value that is not text is
    unrecognised), is UNKNOWN. ON takes precedence over UNKNOWN when both
    occur."""
    try:
        # Both answers are compared with ``is``, not truthiness. A real ``False``
        # from the first check means the net sysctl directory is unreadable
        # (UNKNOWN); a real ``False`` from the second means the ipv6 directory is
        # absent (OFF). Any other value, including one that merely happens to be
        # falsy (None, 0, "", []), is a source that broke its ``bool`` contract:
        # UNKNOWN, never OFF.
        net_present: object = sources.sysctl_net_present()
        if net_present is False:
            return Ipv6Decision(
                Ipv6State.UNKNOWN,
                "the net sysctl directory is not readable, so the absence of its ipv6 "
                "subdirectory proves nothing",
            )
        if net_present is not True:
            return Ipv6Decision(
                Ipv6State.UNKNOWN,
                f"the net sysctl check returned a {type(net_present).__name__}, not a bool",
            )
        ipv6_dir_present: object = sources.ipv6_dir_present()
        if ipv6_dir_present is False:
            return Ipv6Decision(Ipv6State.OFF, "the kernel exposes no ipv6 sysctl directory")
        if ipv6_dir_present is not True:
            return Ipv6Decision(
                Ipv6State.UNKNOWN,
                f"the ipv6 sysctl directory check returned a {type(ipv6_dir_present).__name__}, not a bool",
            )
    except Exception as exc:  # noqa: BLE001 - fail closed: any failure of an injected source is UNKNOWN
        return Ipv6Decision(
            Ipv6State.UNKNOWN,
            f"could not check for the ipv6 sysctl directory ({_describe_error(exc)})",
        )

    enabled: list[str] = []
    unknown: list[str] = []
    for scope in _IPV6_SCOPES:
        try:
            raw: object = sources.read_disable_ipv6(scope)
        except Exception as exc:  # noqa: BLE001 - fail closed: any failure of an injected source is UNKNOWN
            unknown.append(f"{scope}: unreadable ({_describe_error(exc)})")
            continue
        if not isinstance(raw, str):
            # A source that breaks its ``str`` contract is not a "1": UNKNOWN,
            # never OFF and never an exception outside this module's hierarchy.
            # The type name is used, not ``repr``, so an arbitrary object's own
            # ``__repr__`` cannot raise inside the guard.
            unknown.append(f"{scope}: unrecognised value of type {type(raw).__name__}")
            continue
        value = raw.strip()
        if value == "1":
            continue
        if value == "0":
            enabled.append(scope)
        else:
            unknown.append(f"{scope}: unrecognised value {raw!r}")
    if enabled:
        return Ipv6Decision(
            Ipv6State.ON, "disable_ipv6 is 0 for " + " and ".join(f"'{s}'" for s in enabled)
        )
    if unknown:
        return Ipv6Decision(Ipv6State.UNKNOWN, "; ".join(unknown))
    return Ipv6Decision(Ipv6State.OFF, "disable_ipv6 is 1 for 'all' and 'default'")


def enforce_ipv6_guard(sources: Ipv6Sources) -> Ipv6Decision:
    """Return the decision if IPv6 is off, else raise
    ``SandboxIPv6RefusedError`` (refuse by default). Meant to run before any
    resource of a networked sandbox exists (spec section 10, step 2)."""
    decision = evaluate_ipv6(sources)
    if not decision.supported:
        _emit(
            logging.WARNING,
            "sandbox_network_ipv6_refused",
            state=decision.state.value,
            reason=decision.reason,
        )
        raise SandboxIPv6RefusedError(decision)
    _emit(logging.DEBUG, "sandbox_network_ipv6_ok", state=decision.state.value, reason=decision.reason)
    return decision
