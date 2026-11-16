# Historical evidence report (Workstream B)

Review disposition remains OPEN - NO PASS. Categories used in every row: (1) original recovered; (2) original located but inaccessible; (3) original searched for but not found; (4) cannot be established; (5) new supporting records (never historical evidence). No original historical artifact was recovered. Nothing was generated to replace a missing artifact. All searches are in `manifests/SOURCE_SEARCH_REGISTER.tsv`.

| Target | Result | Category | What exists instead | Extent it establishes the claimed origin |
|---|---|---|---|---|
| Revision 17 outline output | NOT FOUND (no preserved output). Platform serves durable revision 17 (`atRev: 17` returned rev 17, latest 19) | 3, with platform source located | transcription T03 (new supporting record, one block at rev 17, per-block hash `7a20e1a0`) | none for the original output; shows the underlying revision is readable |
| Revision 10 change views | NOT FOUND. Readability of revision 10 INCONCLUSIVE (probe block did not exist then) | 3 | transcription T05 (refusal) | none |
| Raw evidence for the section 22 claim | NOT FOUND. The claim (block `.66124`, rev 18) and the section 17 hash table (`.15771`) are inside the brief | 3; claim itself REPORTED | none preserved | the brief states the claim; nothing independent supports it here. The sentence that edits after revision 17 added only section 22 predates the revision-19 Late note (block `.67927`) and is not treated as proof of the full history |
| Revision 19 activity or change metadata | NOT FOUND (node `history` returned no rows) | 3 | T06 | none |
| 4a4783c probe outputs | NOT FOUND | 3 | the five scripts and README in `files.zip` (original, previously supplied); four script SHA-256s recomputed and equal to the full hashes the brief records (VERIFIED, original-to-original) | scripts match the brief's record; no output ties them to a run on this commit |
| 4a4783c test logs | NOT FOUND locally; GitHub CI search INACCESSIBLE (API rate limit) | 3 and 2 | the six-file selection and "170 passed" statement in the brief (REPORTED) | none |
| 4a4783c diff output | NOT FOUND | 3 | the twelve-file list and "ten of twelve identical" statement (REPORTED) | none |
| f13bfde probe outputs / test logs / diff output | NOT FOUND; CI search INACCESSIBLE | 3 and 2 | brief statements (REPORTED) | none |

## Observations
- Searches covered: the sandbox filesystem and uploads; repository references on `main` and the Verification branch (secondary mentions only in `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, `handoff.md`); GitHub CI via API (HTTP 403 on all eight calls) and via static pages (no run or check data for either commit in the captured HTML, whose dynamic parts were not captured).
- A GitHub Actions index page and both commit pages were captured byte-exact (new supporting records, 2026-11-08T20:17Z) so the next operator can inspect what the static pages show.
- The two commits are merge commits of PR #95 (`4a4783c`) and PR #82 (`f13bfde`) per the captured commit page titles (VERIFIED from the captured pages).
- No relationship between any recovered artifact and an original execution on either commit could be established, because no execution output was recovered.
