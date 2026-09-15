# Packet C Execution Prompt — Governance / Identity / Provenance Trace

**Issued:** September 13, 2026, against `main` at `977ebcc` plus relevant branches.
**Method:** the same evidence-first standard established for CTX-AUTH-001/CTX-DELETE-001 — trace the live executable path, not the documented one; classify, don't assume; every claim gets a disposition, not a citation to an earlier report.

---

## 1. Scope

Repository-wide, execution-path-based audit of:

```
request → identity/context → planner/compiler → runtime →
capability admission → governance decision → adapter/tool execution →
emitted events/receipts → persisted state
```

## 2. Particular attention to

1. Authority escalation or privilege widening
2. Identity/context loss or substitution
3. Provenance loss between inputs, decisions, actions, and persisted records
4. Capability authorization bypasses
5. Governance decisions made on stale, incomplete, synthetic, or untrusted state
6. Forged or ambiguous actor/execution identity
7. Discrepancies between recorded governance decisions and the action actually executed
8. Retry/resume paths that could accidentally bypass an authorization boundary
9. Test-only enforcement versus enforcement on the production execution path

## 3. Classification taxonomy

Every claimed control gets exactly one of:

- **LIVE-ENFORCED** — proven on the actual production execution path, not just present in code.
- **PARTIAL** — enforced on some live paths, not others; the gap must be named.
- **DOCUMENT-ONLY** — described in architecture docs / ADRs / docstrings, no corresponding enforcement found.
- **TEST-ONLY** — a test exercises it; no production caller reaches it.
- **BYPASSABLE** — enforcement exists but a live, reachable path routes around it.
- **UNPROVEN** — insufficient evidence either way; not the same as LIVE-ENFORCED, and not asserted as broken either.

A finding is not resolved merely because it's documented. Every unresolved issue gets a concrete disposition before this packet is considered complete — not left as an open citation.

## 4. Non-negotiable operating rules (carried from the governing mission)

- Prove current state from source; a prior audit's claim is a hypothesis to check, not ground truth.
- Local branch only (`audit/packet-c-governance-identity-provenance-sep2026`, based on fresh `main`). No push, no merge, no modification of `main`.
- Distinguish DOCUMENTED / IMPLEMENTED / REACHABLE / ENFORCED / TESTED explicitly — the same discipline the overall freeze mission established.
- Re-verify anything main's recent movement (RCE-001, CVE-2026-31431, CTX-SCOPE-001 wiring, DEBT-020 supersession) might have changed, rather than assuming Session 1's or the CTX pass's findings still hold unmodified.

---

*Findings recorded in `PACKET_C_GOVERNANCE_IDENTITY_PROVENANCE_WORKING_NOTES_SEP2026.md`, this same directory, as they're produced.*
