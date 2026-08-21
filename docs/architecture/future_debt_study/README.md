# future_debt_study

Architecture research and study documents for capabilities not yet implemented — the "what would this look like, what already exists to build on, what's the gap, what are the tradeoffs" analyses that precede a packet or milestone, not the packet/milestone work itself.

Per `PROJECT_INSTRUCTIONS.md` §1.1 and `OCBRAIN_KERNEL_CONSTITUTION.md`: these documents are architecture knowledge, not implementation specifications. They inform design; they don't authorize implementation on their own. A study landing here does not put its subject on the roadmap — that's a separate, explicit decision, tracked in `IMPLEMENTATION_ROADMAP.md` once made.

## Conventions

- One file per study, named `OCBRAIN_<TOPIC>_ARCHITECTURE_STUDY.md`.
- Each study states its own scope boundary up front (what it does *not* authorize) and, if it feeds a specific freeze/audit, says so explicitly.
- Findings are evidence-tagged (`[FACT]` / `[INFER]` / `[REC]`) rather than asserted, consistent with this project's Phase 0 audit discipline — code and current docs are ground truth, not the study itself.
- A study that finds a genuine, previously-untracked defect recommends it be added to `KNOWN_ISSUES.md`; it does not edit that file itself, since a study session isn't the place to unilaterally amend authoritative tracking docs without review.

## Contents

- `OCBRAIN_RELIABILITY_DURABLE_EXECUTION_ARCHITECTURE_STUDY.md` — durable execution, crash recovery, Work Unit reliability, and (Section S, added in a second pass) live system evolution / active-mission compatibility across Kernel, Capability, Model, Runtime, Memory, UI/Web, and Security-policy updates. Feeds the Kernel v1.0 Freeze & Contract Audit. Conclusion: no frozen H1 contract needs to change; 9 items classified Critical Pre-Freeze (contracts to specify, not build) — durable Work Unit state and update-path safety are scoped together, not sequentially, per Section S.6.
