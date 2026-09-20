# Packet F Execution Prompt — Dependency / CI / Release Governance

**Issued:** September 18, 2026, against `audit/tracking-integration` (commit `1dfc2f4`, `main` state `2192b93`).
**Method:** same evidence-first standard as Packets C/D/E — register checked first (confirmed clean: no prior entry covers CI enforcement, branch protection, dependency-pinning discipline, or packaging/build integrity specifically), source traced fresh, findings classified rather than assumed.

## 1. Scope, as originally set for this packet

Dependency pinning/vulnerability posture, CI enforcement, required checks, branch/release protections, reproducibility, packaging/build integrity, whether the repo can actually enforce its claimed kernel baseline.

## 2. Carried forward from Packet E, per Moncif's explicit instruction — not re-litigated, built on

- The chromadb `<1.0` pin is stale relative to the committed fixtures it's meant to govern (classified: broken migration compatibility, disposition undecided). This packet's dependency-pinning-discipline angle should establish *how* a pin/fixture mismatch like this could ship unnoticed — i.e., does CI ever actually run against these fixtures, and would it catch this class of drift.
- `trafilatura`'s unguarded top-level import in `modules/web_search/module.py` — currently safe only because nothing collected reaches it. Worth checking whether CI's own dependency set would ever exercise this path.
- Packet E's baseline (1,501 passed / 6 failed / 0 skipped, minimal-dependency sandbox) stays the reference point; not modified, not re-run from scratch here.

## 3. Particular attention, per Moncif's framing

Look for anything that affects the kernel/capability boundary established in Packet C — i.e., not just "does CI exist" in the abstract, but whether a dependency/build/release governance gap could have consequences for the governed cognitive path, the capability admission boundary, or the control-plane trust assumptions (`DEBT-025`) already on record.

## 4. Classification taxonomy

Unchanged: LIVE-ENFORCED / PARTIAL / DOCUMENT-ONLY / TEST-ONLY / BYPASSABLE / UNPROVEN.

## 5. Operating rules

Continuing on `audit/tracking-integration`, no new branch. No push mid-packet; push happens as a deliberate step, as established. Register check before treating any sub-finding as new, applied per sub-thread, not once at the start only — the lesson from Packet C's own two-pass correction.
