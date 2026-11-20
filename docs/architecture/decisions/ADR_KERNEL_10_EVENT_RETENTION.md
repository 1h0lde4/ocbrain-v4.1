# ADR-KERNEL-10: Event Retention for FZ-05

**Status:** Implemented in this remediation; not yet promoted to `main`
**Date:** November 2026
**Context:** FZ-05b identifies unbounded growth in the SQLite EventStream.

## Decision

Retain all SQLite EventStream events for 90 days by default, with no event-type
exemptions. This includes checkpoints and lifecycle, progress, capability, and
governance events. Expired events are deleted rather than archived; the
EventStream is replayable only within the configured retention window.

`SQLiteEventStore` accepts a `retention_seconds` override for deployments with
a different approved retention requirement. It prunes expired events during
initialization, when the hourly maintenance interval elapses on an append, or
when `prune_expired()` is called explicitly. SQLite incremental auto-vacuum
reclaims freed pages, and the WAL is checkpointed after a deletion batch.
Sequence numbers remain monotonic after pruning.

## Rationale

A uniform retention boundary avoids silently classifying some event types as
non-audit data while retaining an unbounded SQLite file. The 90-day default
provides a practical operational investigation window while making the
storage policy finite and explicit. Deployments that require a longer audit
period must configure a longer retention interval before enabling this
default.

## Consequences

- Queries, counts, and replay omit events older than the retention cutoff.
- Checkpoint/resume is available only while its required checkpoint and
  associated events remain within the configured window.
- This policy intentionally does not create an archive or claim indefinite
  audit retention.
- `KNOWN_ISSUES.md` remains a `main`-based freeze register and must be
  synchronized only after this implementation is reviewed and promoted.
