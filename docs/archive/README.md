# docs/archive/

Historical documentation, moved here during the Repository Cleanup &
Canonicalization Session. Nothing here is current guidance — for that, see
`OCBRAIN_FUTURE_ARCHITECTURE.md` (authoritative architecture), the
`SESSION*_REPORT.md` / `ARCHITECTURE_HARDENING_SESSION_REPORT.md` /
`REPOSITORY_CLEANUP_REPORT.md` files at the repo root (current audit
history), and `PROJECT_INSTRUCTIONS.md` (governing contract).

| File | Why archived |
|---|---|
| `ARCHITECTURE_ALIGNMENT_REPORT.md` | Point-in-time compliance snapshot, superseded by later sessions' more precise, code-verified findings. |
| `ARCHITECTURE_COMPLIANCE_REPORT.md` | Same — an earlier compliance-check methodology run, superseded. |
| `BUG_FIXES.md` | Documents 3 specific bugs fixed in v4.3.4, before Session 1's more comprehensive BUG-01→BUG-05 pass. Completed migration notes. |
| `MINIMUM_ARCHITECTURE_PATH.md` | Tier 1/2/3 implementation planning tied to an earlier "current phase" snapshot. Actual work since has gone well beyond this plan's scope. |
| `Update Unified Memory Migration Design.md` | The original design proposal for `KnowledgeEntry`/`KnowledgeEvent` separation, the Truth & Contradiction framework, L0 Working Memory, and Memory Curator lifecycle hooks. All of these have since been implemented — kept for the design rationale, not as a guide to what's still needed. |
| `REALITY_AUDIT.md` | **Contains claims now confirmed false** — states the orchestration/governance/worker frameworks are "completely missing or present as empty stubs." The Architecture Hardening Session's composition root review found these are fully built and individually tested, just not wired into the production request path — a materially different, more precise finding. Archived rather than left at the repo root specifically because it could mislead a future reader. |
| `RECOVERY_REPORT.md` | Same issue as `REALITY_AUDIT.md` — claims `core/workers/` is "missing" and must be "restored." It exists, is well-built, and simply isn't wired into `main.py`/`Orchestrator` yet. |
| `STATUS.md` | Claims "114 passing" tests. Actual count at time of archiving: 407+. Stale and actively misleading if left at the repo root. |
