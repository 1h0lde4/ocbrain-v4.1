# Addendum — 2026-10-28 — Search of the REV3 branch for the REV3 ZIP

Addendum to `OCBRAIN_G4_FTS_AUTHENTICATION_RECONCILIATION_REPORT.md` (sha256 `a331f6b2b242b2c031b7a84c66ef178d64b940df228545483ed15a0e8abc8318`). The report is not edited; this addendum records one new request and what changed in the world since the report. Evidence: `H01`–`H04` (commands, UTC times, exit status, unaltered output). All reads were read-only GitHub API / `git ls-remote` calls; nothing was written, cloned over, fetched into, or executed.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized.

## 1. Result: the REV3 ZIP is not on the branch

Branch `docs/g4-fts-correctness-handoff-rev3-oct2026`, tip `2dd2e7bb05db949a6156266cfa3430c58de09922` (unchanged since 2026-10-23T10:30:25Z) [H01]:

| Check | Result |
|---|---|
| Recursive tree of the tip | 634 entries, `truncated=false` (complete listing) |
| Any blob whose size is exactly 254,581 bytes | none |
| Any path named `REV3`, `D2_D5` or `FETCH_HEADER` | four documents already known: `G4_FTS_CORRECTNESS_CONTINUATION_REV3.md`, `NEXT_SESSION_PROMPT_REV3.md`, `decision_ledger_1d813bd_OPEN_D2_D5_REV2.md`, `fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md`. The fifth REV3 file, `doc_fetch_quotations_as_returned_HEADER_REV2.md`, does not match that name pattern but is in the branch's 6-file diff. |
| Any archive extension (`zip tar tgz gz 7z rar bz2 xz`) | exactly one: `docs/studies/evidence/live-check-draft-plan-batch-20261012T121543Z.zip`, 21,632 bytes, git blob `c378715fcd3519899470183c900c008bdd1dc301`. The same blob is on `main` [H02]. Different name, different size, a different (older) study artifact. It is not the REV3 ZIP and I did not open it. |
| Git LFS | `.gitattributes` contains only `* text=auto`; 0 LFS lines; so no ZIP is hiding behind an LFS pointer |
| What the branch adds beyond `main` | 1 commit, 6 files, all documents (`IMPLEMENTATION_ROADMAP.md` +1 line and the five files above) [H01] |

This matches what the branch itself says: the continuation (line 11) states "The evidence ZIP remains outside Git, as required by the original evidence-preservation note."

**Scope of this search (a negative result is only as wide as this):** the tip tree of this one branch, plus its single commit beyond `main`. Not searched: other branches, release assets, GitHub Actions artifacts, issue/PR attachments, or anything outside GitHub.

**Effect on the report's gates:** none. *Original ZIP authentication* and *Archive integrity and contents* stay **BLOCKED**. The two digest records (`…0893c336…` and `…0893f336…`) remain unresolved; neither is selected.

## 2. What changed since the report (the report's time-bound statements)

The report is a record as of its stated times. These time-bound facts are now stale [H02, H03, H04]:

| Report statement | Now (2026-10-28 ~14:10 UTC) |
|---|---|
| `main` is `f13bfdefcdd197ed1f966de0b1f93037a4168af4` | `main` is **`6e411877e426646f3c40892c75f407991b4d235b`**, the merge of PR #89 (merged 2026-10-28T10:24:19Z); 51 commits ahead of `f13bfde`. I read ten of the 51 commit titles (the first six and last four): they are DEBT-029 / DEBT-044 context-persistence work, a register-identifier fix, a comment restoration and the PR #89 merge. I did not read the other 41 titles; the changed-file list below is complete. |
| REV3 branch 0 behind, 1 ahead of `main` | **51 behind, 1 ahead** (diverged); PR #90 is still open, draft, head `2dd2e7bb…`, `mergeable_state=behind`, base still `f13bfde…` |
| REV2 branch tip `51564e34…` | unchanged; no PR for it |
| 16 open PRs including #89, #29 closed | open PRs are now 94, 93, 92, 91, 90, 88, 87, 86, 83, 81, 79, 77, 76, 33, 32, 30, 27 (17): **#89 merged; #93 and #94 are new** |
| No open PR touches the FTS source files | still true: a path scan of all 17 found no match for `sqlite_storage`, `unified_memory`, `knowledge_entry`, `core/memory/` (#93 touches `core/cognitive/*`, tracking files and docs; #94 touches `interface/*`, `core/event_bus.py`, `.gitignore`, `KNOWN_ISSUES.md`, docs and tests) |
| The three FTS source blobs are `ed0cbae6…`, `0d5e0716…`, `eb2bbe17…` | **unchanged on `main`**; none of the 51 commits touched them. Files changed on `main` since `f13bfde`: `KNOWN_ISSUES.md`, `core/context.py`, `core/orchestrator.py`, `core/workers/planner.py`, `interface/api.py`, `tests/test_debt_044_context_persistence.py` (added), `tests/test_workflow_failure_disclosure.py` |
| DEBT-042 (`_fts_escape`) is OPEN in `KNOWN_ISSUES.md` | the DEBT-042 row is still on `main` at line 56 (Medium); `KNOWN_ISSUES.md` now also has DEBT-043 (line 57) and DEBT-044 (line 58). I did not re-read the register beyond these rows. |
| REV3 continuation: PR #89 "does not change `sqlite_storage.py`" | still true; PR #89 is now merged |

Net: nothing in the study's substance moved (the FTS source blobs are identical; the stale-posting trigger condition is not touched), but the REV3 documents' "current `main`" references and the report's PR list are now historical. A fresh session should re-check `main` and the open PRs rather than reuse either snapshot, which is what the REV3 prompt already tells it to do.

## 3. What would unblock the two BLOCKED gates

Unchanged: the actual REV3 ZIP attached to a session, or an unaltered `sha256sum` line for it plus how it was produced. Hashing it would settle which digest string is right, and `P2_digest_discrepancy_erratum_TEMPLATE_CONDITIONAL.md` says what to record.

No file in the repository was changed, and no commit, push or PR was made by this request.
