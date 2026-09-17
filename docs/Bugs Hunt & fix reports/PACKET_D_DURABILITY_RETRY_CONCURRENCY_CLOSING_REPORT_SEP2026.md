# Packet D — Durability / Retry / Concurrency: Closing Report

**Date:** September 16, 2026
**Scope:** `docs/Bugs Hunt & fix reports/PACKET_D_EXECUTION_PROMPT_SEP2026.md`
**Full evidence:** `docs/Bugs Hunt & fix reports/PACKET_D_DURABILITY_RETRY_CONCURRENCY_WORKING_NOTES_SEP2026.md`
**Branch:** `audit/tracking-integration` (Packet D began on its own branch off `main` at `c67187a`; consolidated mid-packet with Packet C's branch — see §A). No push, no merge, `main` untouched throughout.

---

## A. Branch consolidation, done once, early

Fixing D-3's `DEBT-003` entry surfaced that this packet's branch, created off fresh `main` per the standing methodology, didn't carry Packet C's own unmerged addendum to that same entry — the two packets' `KNOWN_ISSUES.md` edits had diverged onto separate local branches with no code changes to justify keeping them apart. Rather than let this compound across every remaining packet, both branches were merged into a new `audit/tracking-integration` branch; the one resulting conflict (both branches' addenda to `DEBT-003`) was resolved by keeping both in sequence, since they describe the same resolved mechanism from different angles (authorization-boundary safety vs. reachability/concurrency) and agree everywhere they overlap. Packet D continued on the consolidated branch from that point. Recommend Packets E/F/G branch from `audit/tracking-integration` going forward rather than fresh `main`, re-fetching `main` for source-code state as normal.

## B. Findings summary

| Finding | Disposition | Register entry |
|---|---|---|
| **D-1 — `DEBT-010` race pattern, sibling search** | LIVE-ENFORCED (negative result) | None — narrows `DEBT-010`'s isolation, no new row |
| **D-2 — Event-log idempotency infrastructure** | DOCUMENT-ONLY | Narrows `DEBT-015`(7) in place |
| **D-3 — `resume()` concurrency guard** | UNPROVEN (dormant, unreachable) | Sharpens `DEBT-003`'s resolved entry in place |
| **D-4 — SQLite write-lock contention** | UNPROVEN (real gap, empirically unreachable at tested scale) | New: `DEBT-028` |
| **D-5 — `PlannerWorker` duplicate-side-effect path** | Live-reachable, narrow trigger probability | New: `DEBT-029` |
| **D-6 — Crash-simulation tests (durability, atomicity)** | Both hold, confirmed empirically | Confirming test run for D-5; no separate row |

## C. Direct answer to the packet's closure question

Moncif scoped this packet's useful closure point explicitly: *whether checkpoint/resume can duplicate or lose externally meaningful work across failures.*

**Loses: no.** Two properties tested directly against the real implementation, not inferred from documentation. Durability after commit: a child process self-`SIGKILL`s the instant `commit()` returns, with no possible gap for anything else to run — a fresh process always found the write. Atomicity: a child killed at a randomized, uncoordinated point mid-write-loop, five independent trials — `integrity_check` always `ok`, raw storage count always matched the application's own replay count, sequences always contiguous with no gaps. No scenario traced loses checkpointed work.

**Duplicates: yes, one concrete live path, not gated on crash/resume at all.** `D-5`/`DEBT-029`: `PlannerWorker._run()` has one unguarded write (`context_memory.save()`) sitting after every real side effect has already succeeded, three lines below an identical write that *is* guarded. If it raises, the node reports failure and the already-confirmed-live retry loop (`C-3`) re-fires every capability call that already succeeded. This is an application-level ordering gap, not a SQLite defect — exactly the distinction Moncif's framing asked to preserve. The crash+`resume()` version of the same concern (`D-3`) is real in shape but currently unreachable, since `resume()` has zero production callers of any kind.

## D. Residuals carried to the freeze manifest

**`DEBT-028` (D-4).** No retry/backoff for SQLite lock contention. Real gap, empirically cleared at every tested scale up to 3,000-way concurrency — the protection is a side effect of the default bounded thread pool, not a deliberate guard. Revisit trigger: anything that removes that throttling (a custom unbounded executor, multiple worker processes sharing one SQLite file, a future non-WAL backend).

**`DEBT-029` (D-5).** Live duplicate-side-effect path via one missing `try/except`. Narrow trigger probability, real cost when it fires (a duplicated capability call). Fix is cheap and specific: guard Step 8 the way Step 7 already is.

**`DEBT-003`'s resume-reachability note (D-3).** Not a residual requiring action before freeze — `resume()` is unreachable today, so there is nothing to fix. Revisit trigger recorded: the day any caller of `resume()` is added, a concurrency guard must land in the same change.

## E. Status

Packet D is closed with this report. Two new debt items (`DEBT-028`, `DEBT-029`), both with named revisit conditions; three existing items sharpened in place (`DEBT-003`, `DEBT-015`, `DEBT-010`'s isolation confirmed) rather than duplicated. Every finding was checked against the register before being treated as new, per the precondition Packet C's own closure established — and this packet's closing check, done deliberately rather than incidentally, confirmed no duplicates slipped through this time. Kept to the scope set: no general SQLite-hardening review, no expansion beyond checkpoint/resume's actual duplicate-or-lose question.
