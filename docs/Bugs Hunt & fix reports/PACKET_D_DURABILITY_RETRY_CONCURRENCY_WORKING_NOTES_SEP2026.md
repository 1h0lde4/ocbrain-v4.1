# Packet D — Durability / Retry / Concurrency: Working Notes

Findings recorded as produced. Classification taxonomy per the execution prompt: LIVE-ENFORCED / PARTIAL / DOCUMENT-ONLY / TEST-ONLY / BYPASSABLE / UNPROVEN, applied here to durability/safety guarantees.

---

## Finding D-1: `DEBT-010`'s race pattern has no siblings — searched systematically, not incidentally

**Checked against `KNOWN_ISSUES.md` before tracing (per the standing precondition): no existing entry addresses this specific question — whether `DEBT-010`'s exact pattern recurs elsewhere. `DEBT-010` itself was found incidentally while verifying an unrelated fix, which is exactly why a systematic pass is worth doing once.**

Enumerated every background thread in the codebase: exactly three. `core/config.py:106` is `DEBT-010` itself (`Config`'s watcher, racing per-call `CONFIG_DIR` lookups against test-time patching). `interface/tray.py:93` runs a third-party system-tray icon's own blocking event loop (`_icon.run`) and touches only a module-local `global _icon` — no shared mutable runtime state in the pattern's shape. `interface/voice.py:100` runs a hotkey listener that invokes a caller-supplied callback (`on_query`) via a third-party `keyboard` library — callback-dispatch, not a per-call re-read of a patchable global.

**Classification: LIVE-ENFORCED as a negative result** — not "no race conditions exist," but specifically "`DEBT-010`'s pattern (background thread + fresh per-call lookup of mutable module-level state) does not recur." No `KNOWN_ISSUES.md` update needed; this narrows rather than adds to that entry, and is recorded here as the evidence for not re-opening it.

---

## Finding D-2: Event-log idempotency infrastructure exists at the storage layer, but no caller uses it — concretizes `DEBT-015` sub-item (7) rather than contradicting it

**Traced while investigating whether `EventStream.append()` gives any protection against a duplicate write on retry-after-ambiguous-crash** (did the append commit before the crash, or not — a caller that can't tell might retry).

The schema (`core/events/event_stream.py`'s `_init_db()`) declares `event_id TEXT UNIQUE NOT NULL` — a genuine storage-level safeguard. If a caller retried `append()` with the *same* `event_id`, SQLite would reject the second insert with an integrity error rather than silently duplicating the row. `self._sequence` is correctly rebuilt from `SELECT MAX(sequence) FROM events` on every startup (not naively reset), so sequence numbers don't collide or reset across a restart either — checked directly, not assumed.

**But the safeguard is pointed at a key nothing actually reuses.** `StreamEvent.event_id` defaults via `field(default_factory=lambda: str(uuid.uuid4()))` — a fresh random ID on every construction. Searching every production `event_id=` assignment outside `event_stream.py` itself found exactly one hit, in `core/memory/knowledge_event.py` (a *different* event mechanism, `DEBT-004`'s "KnowledgeEvent/EventStream duality"), and that one is deserialization (`d.get("event_id", ...)`, reconstructing an *existing* event), not fresh-event creation. No production code path that emits a *new* `EventStream` event supplies a stable, retry-derived `event_id` — every real call site relies on the random default.

**What this means, stated at the scope the evidence supports:** the UNIQUE constraint would work if exercised, but nothing exercises it — a retry after an ambiguous crash today produces a second event with a *different* random ID, indistinguishable in the log from two genuinely separate occurrences. This is a real gap, but its consequence is narrower than it might sound: it concretizes `DEBT-015` sub-item (7) ("retry/idempotency semantics for future side-effecting capabilities") rather than contradicting that item's own scoping. `DEBT-015`(7) already correctly frames this as a *future* concern because — per Packet C's C-2 finding — only `LLM_COMPLETION` has a registered capability today, and a duplicated *completion call* is wasteful, not unsafe, in the way a duplicated payment or email send would be. What's new here is narrower and more concrete than the standing architectural note: it's specifically the *event log itself* that has no duplicate-detection in practice today, separate from and prior to the question of duplicate *external* side effects, which remains correctly gated on side-effecting capabilities that don't exist yet.

**Classification: DOCUMENT-ONLY** for the idempotency mechanism specifically (the constraint exists and is correctly built, but nothing in production code activates it for its intended purpose) — not BYPASSABLE, since there's no live caller depending on it that could be routed around; the gap is that nothing currently relies on it, mirroring the same "declared but not yet activated" shape found repeatedly in Packet C (`CapabilityType`'s unregistered types, `SupervisorWorker`'s deferred retry path).

**Disposition:** worth a note added to `DEBT-015`'s existing sub-item (7) — not a new debt row — recording that the storage-layer half of an idempotency mechanism already exists and works, narrowing what (7)'s eventual implementation would need to build.

---

## Finding D-3: No concurrency guard on `resume()` — but the gap is currently unreachable, since `resume()` has zero production callers of any kind

**Checked `KNOWN_ISSUES.md` first: `DEBT-003`'s resolved entry already notes "automatic resume-on-startup discovery" as explicitly not attempted. What follows is narrower and more complete than that note, not a rediscovery of it.**

`WorkflowRuntime.resume(definition, instance_id)` has no lock, no "already running" registry, and no guard of any kind against two concurrent calls with the same `instance_id` — confirmed by reading the method and the class for any `Lock`/`_running_instances`/equivalent (none exist). Two concurrent `resume()` calls on the same instance would both load the same checkpoint, both see the same completed/pending node states, and both proceed to execute — a genuine race, if it could happen.

**It currently cannot.** A full search of production code (`interface/api.py`, `main.py`, `core/orchestrator.py`) for any caller of `.resume(` found none — not one. No API route, no startup routine, no CLI entrypoint. `execute()` is the only production path into `WorkflowRuntime`, and it always mints a fresh random `instance_id` per call (`str(uuid.uuid4())`), so two `execute()` calls cannot collide on identity either. `DEBT-003`'s checkpoint/resume mechanism is real, tested, and — per Packet C's own C-6 re-verification — correctly safe when exercised. But nothing in the live system currently exercises the *resume* half of it: checkpoints are written after every node boundary, and nothing ever reads one back in production. The durability capability exists; the recovery half of "crash recovery" is currently dormant, not because it doesn't work, but because there is no path that invokes it outside tests.

**Classification: UNPROVEN as a live concurrency risk** — there is no reachable trigger today, so this is not BYPASSABLE (nothing to bypass) and not quite DOCUMENT-ONLY (the underlying mechanism is real, not merely described) — closest to C-3a's shape in Packet C (a dormant-by-construction gap, not a live one), and per Moncif's standing instruction not to escalate a dormant mechanism into a defect without evidence of exploitability, it is recorded as such rather than as a race condition to be fixed.

**Disposition:** update `DEBT-003`'s resolved entry with this sharper fact — not "automatic discovery isn't built" but "no caller of any kind exists yet" — and name the concrete revisit condition: the day any caller (a startup recovery scan, an API-triggered manual resume, or anything else) is added, a concurrency guard on `instance_id` needs to be added in the same change, not after.

**Process note surfaced while making this edit:** this branch was created off fresh `main`, so its copy of `KNOWN_ISSUES.md` does not include Packet C's own unmerged addendum to this same `DEBT-003` entry (C-6, a different angle on the same RUNNING→PENDING behavior). Both addenda are compatible, not conflicting, but now exist on two different local branches, neither merged to `main`. Flagged to Moncif rather than resolved unilaterally — see the chat response for the proposed fix.

---

## Finding D-4: No retry/backoff for SQLite lock contention on concurrent writes — real gap, empirically unreachable at tested scale

**Checked `KNOWN_ISSUES.md` first: no existing entry addresses `EventStream`'s concurrent-writer behavior specifically.**

`SQLiteEventStore.append()` sets no `busy_timeout` pragma and passes no `timeout` to `sqlite3.connect()`. Verified empirically (not from memory of SQLite's documentation) that Python's `sqlite3` module's own default — 5 seconds — applies: a second connection contending for a write lock held by a first retries silently for 5 seconds, then raises `sqlite3.OperationalError: database is locked` if the lock is still held. Confirmed no code anywhere in `event_stream.py` or `runtime.py` catches or retries this specific exception — a lock-contention failure would propagate as an unhandled error.

**This is architecturally reachable, not a strawman.** `get_event_stream()` is explicitly documented ("FA §4.1 Layer 1 — Single EventStream per process") and implemented as a genuine process-wide singleton via a `global _stream` lazy-init pattern. `interface/api.py` runs FastAPI, which serves concurrent requests by default. Two `/query` requests arriving close together would run two separate workflow executions against the *same* underlying SQLite file — genuine cross-instance concurrent writers, not a hypothetical.

**But reproducing it against the real class, not just raw `sqlite3`, found no failure at any tested scale.** 50, 200, 1,000, and 3,000 simultaneous `append()` calls via `asyncio.gather` against a live `SQLiteEventStore` — all succeeded, sequence numbers unique and contiguous, worst case (3,000-way) completing in 1.7 seconds, comfortably inside the 5-second budget per call. The reason: `_append_sync` runs via `loop.run_in_executor(None, ...)`, the default bounded `ThreadPoolExecutor` — true SQLite-level lock contention is naturally throttled to that pool's actual thread count, not the async-level concurrency figure, and each write is fast enough (single INSERT + commit) that queued writers clear well within the timeout.

**Classification: UNPROVEN as a live risk, with the protection named as incidental rather than deliberate.** The gap (no explicit retry/backoff) is real. What prevents it from mattering today is a side effect of using the default executor, not a decision anyone made to protect this specific code path. That distinction matters for the revisit condition: **anything that removes the natural throttling — a custom unbounded executor, a move to multiple worker processes each with their own thread pool hitting the same SQLite file, or a future storage backend without WAL's writer-serialization behavior — would re-expose this gap without any code here having changed.** Recorded as a defense-in-depth item, not a defect to fix before freeze: add an explicit `busy_timeout` pragma and/or a bounded retry with backoff around `OperationalError` specifically, cheap to do, currently non-urgent given the empirical result.

**Disposition:** new debt row warranted — this is genuinely new territory, not a refinement of an existing item (checked `DEBT-008`, `DEBT-010`; neither covers concurrent-writer behavior specifically). Recommend low-to-medium severity given the empirical finding, with the incidental-protection caveat stated explicitly so it isn't mistaken for a deliberate guarantee.