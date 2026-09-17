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