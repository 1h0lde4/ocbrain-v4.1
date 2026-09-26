# Packet G Execution Prompt — Implementation/Readiness Against Packet F's Findings

**Issued:** September 19, 2026, against `audit/tracking-integration` (`9f549c7`), `main` at `4669e21`.

## 0. What this packet is, and isn't

Packets C through F were entirely read-only characterization — no application code, CI config, or release infrastructure was ever modified. Packet G is different in kind: real implementation against the debts F surfaced, while preserving the freeze boundary — scoped, targeted fixes to the specific issues already characterized, not architectural change to the kernel/capability boundary Packet C traced (F's own boundary cross-check already confirmed none of these findings touch that boundary). "Preserving the freeze boundary" here means exactly that scope discipline, per this project's own Architecture Freeze Principle.

Per Moncif's explicit instruction: four separate tracks, not one undifferentiated pass. Each track's goal is the same shape — go from "we know the weakness" to "exact implementation plan and verified enforcement" — but verification means different things per track, stated honestly per track below rather than assumed uniform.

## 1. Track: Dependency reproducibility (`DEBT-032`, sharpened by F-5)

Align `requirements.txt`'s chromadb (and scipy) constraints with what `release.yml` already proves works. Verification available and required: re-run Packet E's baseline before and after: the 5 chromadb failures should disappear.

## 2. Track: Required CI/branch enforcement (`DEBT-033`)

Enable branch protection on `main` requiring `ci.yml`'s `tests` and `drift-and-ownership` jobs to pass. Verification available: query the branch-protection API after, confirm it's active and lists the right required checks. **Flagged explicitly, not implemented silently:** this changes how push access to `main` works going forward for anyone, including Moncif himself — worth his awareness before it's live, not just in a summary after.

## 3. Track: Release artifact integrity (`DEBT-034`)

Remove `|| true`'s silent tolerance (or replace with an explicit, visible non-hard-fail signal) and add `fail_on_unmatched_files: true` to the release step. Verification honestly bounded: this environment cannot trigger an actual GitHub Actions run, so "verified enforcement" here means syntactic validity and logical correctness confirmed by inspection and, where possible, by reproducing the relevant shell/YAML logic locally — not an end-to-end run.

## 4. Track: Supply-chain controls (`DEBT-035`)

Add Dependabot configuration; pin third-party Actions by SHA with version as a trailing comment. Same verification bound as Track 3 — syntactic/logical correctness, not a live run.

## Operating rules

New dedicated branch (`packet-g-implementation-sep2026`, off fresh `main`), not a continuation of `tracking-integration` — this is code/config change, not documentation, and benefits from being independently reviewable and revertable per track. Commits kept strictly separated by track. Register updated to reflect implementation status per item as each track completes — "characterized" becomes "implemented, verified as described" or "implemented, verification bounded as described," never silently upgraded to "resolved" beyond what was actually proven.
