# G4 / FTS-correctness documentation study — work-save checkpoint (2026-11-08)

**What this is.** A temporary branch that saves the work products of the OCBrain v4.1 Kernel v1.0 Phase G4 documentation and audit study, so they survive the end of the working session. It adds files under `wip/g4-work-save-2026-11-08/` only. It changes no existing file.

**What this is not.** It is not a `handoff.md` under PROJECT_INSTRUCTIONS section 18.4.8 and does not claim `TRANSFER READY`. It is not a statement that any work is complete or verified, and it is not meant to be merged. Delete the branch when the files have been moved somewhere permanent.

Base: `main` at `2491ae469edd6ef1267a14604c4f8f40d698f7ea`. Everything is a copy of a file that was delivered to the owner during the session, plus the scripts used to produce and check them.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized.

## Repository state at this checkpoint (observed 2026-11-08)

| Ref | Commit | Note |
|---|---|---|
| REV2 branch `docs/g4-fts-errata-handoff-oct2026` | `d963daa502de4220411d0d0c2f19f67b3ec2682b` | pushed earlier (P1 and P1b); unchanged |
| REV3 branch `docs/g4-fts-correctness-handoff-rev3-oct2026` | `9407db5a01acea9684f158caa8107fb71611a102` | pushed earlier (P2, P3); unchanged |
| PR #90 | open, draft, 3 commits, 7 files, head `9407db5a…` | unchanged |
| `main` | `2491ae469edd6ef1267a14604c4f8f40d698f7ea` | unchanged |

## Where things stand

- **Revision 3 of the verification block (patch P1d rev3) is PROPOSED, not applied, and not acceptable as it stands.** An independent-context reviewer's partial report (Addendum 6, evidence I78) reported two substantive findings, and the author reproduced the mechanism on loopback (I77):
  - **F14**, false PASS: the identity check cuts the URL authority only at `/`, so an `origin` such as `https://127.0.0.1:18443?@github.com/1h0lde4/ocbrain-v4.1` is accepted as canonical while git connects to the other host.
  - **F15**, secret output: git's own error messages print a token that is part of the `origin` URL.
- **The independent review is not complete.** Five reviewer launches ended on the plan's usage limit; the fifth reached items A, B and E only. Items C, D, F, the prose claims in G, H and I are not reviewed. A report marked `IN PROGRESS` does not satisfy the review gate.
- **F7 stays OPEN.** No application, push to the REV2 or REV3 branches, merge or closure is authorized.
- Decisions that are the owner's and are still open: whether to allow one bounded correction of revision 3; who performs the next independent review; whether to adopt the stronger status checker (v2); D-1…D-11; the next-session entry point and ledger wording; the PR #90 rebase (the PR owner's call). An assistant's written assessment given to the owner on 2026-11-08 recommends: leave revision 3 unchanged, finish the review first with a human or a different model family, then one bounded correction and one more review, and adopt v2. That is a recommendation, not an owner decision.

| Finding | Status |
|---|---|
| F1–F5 (pushed wording residuals) | OPEN |
| F6 (metadata only) | not changed |
| F7 | OPEN |
| F8 (the Addendum 2 P1d must not be applied) | OPEN |
| F9–F12 (rev2 block weaknesses, addressed in the rev3 proposal) | FIXED in the proposal; not VERIFIED |
| F13 (status checker v1 too weak; v2 added) | FIXED in tooling (v2); not VERIFIED by anyone else |
| F14, F15 (found in rev3) | OPEN |

## Contents

| Path | What it is |
|---|---|
| `reports/` | The consolidated reports and addenda, in order: the reconciliation report, P1/P2/P3 execution report, Addendum 1 to 6, and the earlier dated addenda. **Start with `CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_6_…`**, then Addendum 5. |
| `evidence_records/` | Every recorded command and output (records A01 to A03, H01 to H04 and I01 to I81), as written by the recorder `tooling/ev.sh`. Descriptive names; I73 and I80 are kept as first runs that failed or preceded edits. |
| `evidence_bundles/` | The zip bundles delivered with each addendum, unchanged. |
| `review_package/g4_rev3_independent_review_package.zip` | The unchanged package for the independent review of revision 3 (sha256 `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`). It carries none of the author's results. Give it to the next reviewer as it is. |
| `proposed_patches/` | Every proposed patch (P1 to P1d rev3, P3) and the P2 erratum text. All are PROPOSED. Only P1, P1b, P2 and P3 were applied, on the REV2 and REV3 branches. P1c and every P1d variant were not applied; the P1d variants before revision 3 contain known weaknesses; `superseded/` holds a withdrawn candidate. |
| `verification_blocks_and_tests/` | The verification block variants (rev2, rev3 drafts, rev3 final) and the scenario and unit test scripts. Revision 2 gives false PASS in six cases and revision 3 has F14 and F15: do not use any of them to verify a checkpoint. |
| `tooling/` | Builders, mechanical checkers (`check_addendum1.py` to `check_addendum6.py`, the v2 status checker, the mutation test), reproduction scripts and the evidence recorder. Scripts contain session-specific scratch paths and are saved for reference. |

## How to resume

1. Verify the refs in the table above (`git ls-remote origin`) before changing anything; resolve any mismatch first.
2. Read Addendum 6, then Addendum 5, then the findings table above.
3. Get the one independent review of the unchanged review package completed (all of items A to I with explicit dispositions), then consolidate every substantive finding, then ask the owner for the next decision. Do not start another rewrite automatically.
4. Never run anything extracted from an archive; read it. Run the block variants only against throw-away synthetic repositories.

## Not saved here

Scratch working directories (synthetic repositories, reviewer scratch directories), the original REV3 ZIP and the owner's `handoff(1).md`, the third-party reviews that the owner attached, and the download page. Their hashes and the findings drawn from them are recorded in the reports.

The repository is publicly readable, so this branch is too. The files were scanned before commit for tokens, private keys, credentialed URLs and e-mail addresses; the only credential-like strings are dummy values used in tests (for example `SECRETTOKEN`).

Rollback: delete the branch (`git push origin --delete wip/g4-work-save-checkpoint-nov2026`, owner's decision). Nothing else depends on it.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
