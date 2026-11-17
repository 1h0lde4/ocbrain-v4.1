# Session Handoff (version 1, 2026-11-15): Q4-b independent review and missing-evidence recovery

> Branch `docs/q4b-independent-review-evidence-nov2026` (documentation only, based on `main` `2491ae4`). This file is new on this branch; other branches may carry their own `handoff.md` (for example the Verification branch's version 4 for the 3C-B work), and they are unrelated. The review disposition is **OPEN, NO PASS**. Nothing here is a decision, an acceptance or an authorization to implement.

## 1. Handoff Metadata
- Handoff version: 1
- Created at: 2026-11-15 (UTC)
- Workstream: independent adversarial review of the OCBrain Q4-b brief (revisions r1 to r9.1), then recovery of the missing primary evidence (ME-01 to ME-15)
- Task identifier: Q4-b / ME-01..ME-15 (repository `1h0lde4/ocbrain-v4.1`)
- Source session purpose: review, consolidate, inventory missing evidence, run Batch 1 recovery (plus authenticated GitHub addendum), prepare owner requests and intake tooling, preserve everything in Git
- Transfer status: see section 19

## 2. Original Starting Prompt
**Faithful extraction, NOT verbatim.** The original prompts were several thousand words each and exist only in the owner's chat and records, not in the repository. Per protocol 18.4.8.3 the operative requirements are preserved below; the owner may supply verbatim originals if wanted.

"Q4-b: Independent Adversarial Audit and Validation" (mission, 2026-10-31):
1. Role: independent reviewer verifying the original Q4-b audit's conclusions against the repository, runtime evidence, probe scripts and exported documents; adversarial, not polishing; may not declare the brief VALIDATED or the mission closed; optimize for correctness and evidentiary integrity, not agreement.
2. Inputs and provenance: Q4-b brief, decision pack, ledger (exported Markdown plus preserved DOCX or PDF); five probe scripts and README; available runtime evidence and probe outputs; repository access; the original revision-preservation evidence. For each document record filename and format, SHA-256 of the supplied bytes, size, content revision label and platform revision counter (kept separate). Never reconstruct or regenerate an export; record missing inputs explicitly.
3. Repository: review target `main` at `16d663a`; fetch, verify, inspect `4a4783c..16d663a` (including the new real-process kill-and-resume test and what it does not establish); the earlier revalidation was on `4a4783c`; no repository edits, branches, commits, pushes or merges.
4. Scope: (A) section 20 cancellation and reporting: F-15 event-store outage, F-16 cooperative deadline, F-17 timeout coverage; (B) F-01 amendment (structured `execution_detail`); (C) DEBT-015, all 12 sub-items (3, 7, 9, 10, 11 never examined); (D) F-14 correction (`core/verification` absent on main); (E) section 21 criterion 12 (multiple failures; introduce no rule, make no owner decision); (F) section 22 and revision-1 preservation (distinguish block-level, service-side and byte-level).
5. Runtime gaps: `handle()` and the HTTP layer under cancellation; `resume()` after a cancelled or deadlined run; checkpoint after asyncio cancellation; process-kill detection and recording; install the full dependency set in a clean environment or record the limitation; skipped or import-failed tests are not passes.
6. Existing claims to check: 170 tests on `4a4783c`; ten of twelve audited files byte-identical; eight probes reproduced; revision-1 preservation at platform revision 17 (49 blocks, 11 lists and tables); D6 wording consistency across brief, pack and ledger; criterion 23 moved from BLOCKED to ADDRESSED on one reader's judgment; 12 ADDRESSED / 14 PARTIALLY ADDRESSED matrix.
7. Method: evidence first; source over documentation; runtime over assertion; statuses VERIFIED, PARTIALLY VERIFIED, NOT VERIFIED, CONTRADICTED, ENVIRONMENTALLY BLOCKED; precise provenance; no false independence; adversarial counterexamples.
8. Deliverable: one report with 12 parts (provenance; executive disposition; findings register; DEBT-015 matrix; criterion 12 assessment; cancellation and reporting assessment; runtime gaps; cross-document consistency; revision-1 preservation; revised closure assessment of all 26 criteria; outstanding owner decisions; final recommendation: VALIDATION RECOMMENDED, WITH EXPLICIT RESIDUALS, or NOT RECOMMENDED).
9. Boundaries: do not modify the three documents or repository; no owner decisions; no new policy; no claim of independence without examining evidence; do not mark missing tests as passed.

## 3. Subsequent User Instructions / Corrections
Chronological; later items supersede earlier ones only where stated.
1. **Revision-3 addendum (sections 18 to 29).** Issue #105 (cancellation contract) is owned by another active session: do not duplicate, branch for, or write competing tests; capture any visible branch or PR head read-only. PR #81 (DEBT-028): source-based candidate review only (lock use around `resume()`, execute versus resume claim, instance id generation, in-process scope, cross-process gap, compatibility with #104, the cancellation test). PR #97 crash-restart test is established evidence, not exactly-once. DEBT-029 and DEBT-044 are not to be reopened without new proof. Audit the checkpoint-failure contract by deterministic injection. Reconcile the identity chain. Keep documentation PRs #83 and #87, API-security PRs #93 and #94, and OCBrain v2 proposal #103 in their own lanes. Provide a cross-reference table (FZ, F, DEBT numbering is not interchangeable) and a branch and PR inventory. Final gate: re-verify main, no duplicate #105 work, #81 untouched, evidence bundle with hashes. "No implementation, no merge, no new branch, no overall PASS."
2. **External assessments pasted by the owner** (several, from another assistant): treated as claims to verify, not instructions. Several were corrected by evidence (swapped commit-to-run pairing; "execution_id to request_id to instance_id" inference; flag-off probes; FZ-05 scope) and are recorded in r4 to r9.1.
3. **Recommendation to investigate the trace-ID discrepancy before authorizing identity remediation**, then identity corrections (r5 to r8).
4. **"Locate and reconcile the missing primary evidence identified by r9.1"** (inventory): preserve all artifacts and hashes; no probes, no repository or PR changes, no owner decisions, no finding changes; distinguish original, reproduced and derived evidence; return an exact inventory and stop (result: `Q4B_MISSING_EVIDENCE_INVENTORY.md`).
5. **"Independent Evidence Recovery Assignment, ME Recovery Batch 1"**: acquire genuine native exports of the three Claude Docs and historical evidence; preserve original bytes; SHA-256 over delivered bytes only; never retype or reconstruct; separate original, derivative and new records; vocabulary RECOVERED, PARTIALLY RECOVERED, LOCATED, NOT FOUND, INACCESSIBLE, NOT RECOVERABLE, NOT INVESTIGATED; map ME-01..ME-15 once each; no probes, tests, execution, repository change, document editing or credential use; do not start Batch 2; report PARTIALLY COMPLETE or BLOCKED honestly; status words PASS, CLOSED, ACCEPTED, RATIFIED not to be used for evidence activity.
6. **"Treat the next stage as a blocker-resolution and evidence-acquisition exercise"**, then **"Ok, do it"** (draft the owner request): result `OWNER_EVIDENCE_REQUEST.md`; later intake tooling.
7. **Upload of the r3 report and bundle** (2026-11-13): verified byte-identical to the delivered copies.
8. **"use the token to verify github outputs"** (2026-11-13): authenticated read-only GitHub verification; Batch 1's no-credential rule applied to Batch 1 and is superseded for this purpose by this explicit instruction. Result: the addendum folder.
9. **"You can use the token unlimitedly until it expires. Push the finished work to repo, then create the handoff to resume the remaining work on a fresh session"** (2026-11-15): authorizes token use until it expires (token expiry reported by GitHub: 2026-11-23 01:11:41 UTC) and a documentation-only push of the finished work plus this handoff. It supersedes the earlier "no repository change" boundary for this push only. It does not authorize a PR, a merge, implementation, owner decisions or any change to findings.
Standing rules from the project instructions that applied throughout: dedicated branch, no work on the primary branch, no destructive Git operations, checkpoint then handoff, `handoff.md` with the 19-section structure.

## 4. Goal, Scope & Success Criteria
### Goal
Resolve recoverable blockers for the Q4-b review without weakening the evidence standard: obtain and preserve the missing primary evidence (ME-01 to ME-15) so the blocked assessments can later be performed defensibly.
### In scope
Receiving, hashing and recording owner-supplied evidence; acquiring evidence the owner authorizes; maintaining ME status views as new files; keeping the OPEN, NO PASS disposition.
### Out of scope
Any implementation or remediation (including FZ-01 reporting, `root_operation_id` propagation, capability-bridge identity); any owner decision (D1, D2, D6 wording, which document is the ledger, custody of exports, #105 contract, hard-deadline authority); PRs or merges; execution verification (ME-14, ME-15) until separately authorized; duplicating #105 work.
### Success criteria
Every ME item has a recorded acquisition status with provenance; original, reproduced and derived evidence stay separate; the four dimensions (discovery, acquisition, integrity, sufficiency) are tracked per item; blocked assessments (decision D6 consistency across the three documents, criteria 12 and 23, section 22, the 26-criteria matrix) are re-attempted only after their inputs exist; disposition changes only by owner process.

## 5. Requirement Ledger
| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R-01 | Review is independent, read-only, evidence-first | mission | IN PROGRESS | r1 to r9.1 | |
| R-02 | Never declare PASS, VALIDATED or closed | mission, all assignments | IN PROGRESS | `artifacts/CONSOLIDATED_EVIDENCE_REGISTER_r9_1.md` | disposition OPEN, NO PASS |
| R-03 | Preserve all artifacts and hashes | inventory and Batch 1 assignments | VERIFIED (2026-11-15) | `ARCHIVE_MANIFEST_r9_1.tsv`, package SHA256SUMS, fresh-clone check | |
| R-04 | SHA-256 only over delivered bytes; never retype exports | Batch 1 | BLOCKED | `ME_RECOVERY_BATCH_1/reports/DOCUMENT_EXPORT_REPORT.md` | no export bytes preserved |
| R-05 | Distinguish original, reproduced, derived evidence | inventory, Batch 1 | IMPLEMENTED | manifests, `ME_STATUS_DIMENSIONS.tsv` | |
| R-06 | ME-01..ME-15 mapped once each | Batch 1 | VERIFIED | `ME_RECOVERY_BATCH_1/manifests/ME_RECOVERY_MAPPING.tsv` | |
| R-07 | Do not duplicate #105 work | addendum section 18 | IN PROGRESS | no asyncio-cancel tests written after the constraint | |
| R-08 | No probes or tests in recovery batches | Batch 1 | VERIFIED | final report section 10 | |
| R-09 | Token never stored, printed, or written to memory or files | owner handling rule | VERIFIED (token-shaped-string scans clean) | addendum report section 1 | token is the owner's, in preferences |
| R-10 | Owner-supplied files hashed on receipt | owner request | OPEN | `artifacts/ME_INTAKE_TOOLKIT/` | nothing received yet |
| R-11 | ME-07 acquired from owner-side `gh` commands | ME-07 instructions | OPEN | `artifacts/ME07_OWNER_ACQUISITION_INSTRUCTIONS.md` | sandbox cannot download (allowlist) |
| R-12 | Owner statements (ledger identity, custody, D1/D2, regenerated views) | owner request section 4 | OPEN | `artifacts/OWNER_EVIDENCE_REQUEST.md` | none inferred |
| R-13 | Blocked assessments re-attempted only after inputs exist | r9.1 section 5 | DEFERRED | | |
| R-14 | Environment-dependent verification (ME-14, ME-15) | inventory | DEFERRED | | separately authorized batch |

## 6. Current Verified State
**VERIFIED (2026-11-15):** `origin/main` is `2491ae469edd6ef1267a14604c4f8f40d698f7ea`; PR #81 head is `647b63e734792b8375c0f96593407ee651af5840` (open, `mergeable=false`, `mergeable_state=dirty`, 13 commits per the 2026-11-13 API record); issue #105 is open and unassigned (API record; one owner comment of 2026-11-02); this branch differs from `main` only under `docs/reviews/q4b-independent-review/` (plus this file); the pushed tree is byte-identical to the session's output folder and every package manifest verifies from a fresh clone; all probes give normalized-identical output on `16d663a`, `ed3d141`, `2491ae4`; CI runs exist for `4a4783c` (run 40781867485, artifact 12857857088, 1,164 bytes) and `f13bfde` (run 39226693573, artifact 12173949037, 893 bytes).
**Review findings (see r9.1 register, evidence class stated there):** deadline outcomes depend on DAG position and worker cooperation; progress-event and checkpoint write failures are handled asymmetrically and checkpoint failure is invisible in the event history; a killed attempt is not detected or recorded; execution registry reuses graphs for a repeated `execution_id`; identity is lost at `WorkflowDefinition` to run context (`root_operation_id`) and at `CapabilityExecutorWorker` to `CapabilityRequest`; FZ-01 outcome reporting (workflow failure reported as success by the orchestrator and HTTP layer) reproduced on the production K4.2 path.
**IMPLEMENTED BUT NOT VERIFIED:** none (no code was changed). The ME status views are derived from Batch 1 and the addendum.
**PROPOSED:** owner request, ME-07 acquisition instructions, intake procedure (all awaiting the owner).
**DEFERRED:** ME-14, ME-15; the blocked assessments.
**BLOCKED:** export bytes for the three Docs (platform responses cannot be preserved without retyping); CI log and artifact bytes (download hosts blocked by the sandbox allowlist); original probe outputs, pytest logs and diff output (NOT FOUND); D2 definition (NOT FOUND).
**UNKNOWN:** whether the original author kept any original outputs; whether revision 10 is readable for pre-existing blocks; real-model behaviour of the 43 model-blocked tests; production composition, voice, real client disconnect.
Status labels per item are in `artifacts/ME_STATUS_DIMENSIONS.tsv` and `artifacts/ME_RECOVERY_BATCH_1/manifests/ME_RECOVERY_MAPPING.tsv`; the addendum changes ME-07 to LOCATED (`ME_STATUS_ADDENDUM.tsv`).

## 7. Git / Repository Checkpoint
- Primary repository: `1h0lde4/ocbrain-v4.1`
- Remote: `origin` (https://github.com/1h0lde4/ocbrain-v4.1.git)
- Branch: `docs/q4b-independent-review-evidence-nov2026`
- Base branch: `main`
- HEAD before work: `2491ae469edd6ef1267a14604c4f8f40d698f7ea`
- Transfer commit: `8cce19c0a33dcbc67b71c7559e98732fbc9239db` (the implementation checkpoint being transferred)
- Earlier checkpoint commit: `9824d0d4dfba52093ecde4a47bac2b5017389304` (INCOMPLETE: omitted `ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/logs/AUTH_API_CALLS.tsv`, skipped by the repository's `logs/` ignore rule; corrected in the transfer commit, no history rewrite)
- Handoff commit: the commit that adds this file; its parent is the transfer commit
- Parent commit of the handoff commit: `8cce19c0a33dcbc67b71c7559e98732fbc9239db`
- Working tree status at handoff: clean apart from this file before its commit
- Relevant untracked/ignored files: none left (the ignored `logs/` file is force-added and a directory-level `.gitignore` re-includes `logs/`)
- Submodules or nested repositories: none
- Remote push status: transfer commit pushed (fast-forward `9824d0d..8cce19c`); handoff commit pushed after this file was written
- Remote verification: `git ls-remote` equalled the local SHA after each push; a fresh single-branch clone matched the output folder (`diff -rq` clean) and all package manifests verified
- No PR was opened and nothing was merged. The owner's token was supplied per command through a one-shot HTTP header, never written to git config, remotes or files.

## 8. Active Files / Modified Files / Artifacts
All under `docs/reviews/q4b-independent-review/` (added, none modified or deleted; no code, test, workflow or register file changed):
- `README.md`, `.gitattributes` (`* -text` so hashes verify; the repository root has `* text=auto`), `.gitignore` (re-includes `logs/`)
- `artifacts/`: byte-for-byte mirror of the session output folder (163 files): reports r1 to r9.1 (`INTERIM_REVIEW_REPORT*.md`, `REVIEW_NOTE_r5..r8`, `CONSOLIDATED_EVIDENCE_REGISTER_r9*.md`), bundles (`q4b_*.zip`, `ME_RECOVERY_BATCH_1.zip`), `Q4B_MISSING_EVIDENCE_INVENTORY.md`, `OWNER_EVIDENCE_REQUEST.md`, `ME07_OWNER_ACQUISITION_INSTRUCTIONS.md`, `ME_STATUS_DIMENSIONS.tsv`, `ME_RECOVERY_BATCH_1/`, `ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/`, `GITHUB_GOVERNANCE_SNAPSHOT_2026-11-13/`, `ME_INTAKE_TOOLKIT/`, manifests.
Key SHA-256 (checked at handoff creation): r9.1 register `fa4f7ca055401ce002216a3c3663dac1541910a0d85ee01eb5e28276998ad3a7`; r9.1 bundle `848c4c1c9842517f11ddd591eb5a4cf6e7337224d4af291a57a406498bdc3cd0`; `ARCHIVE_MANIFEST_r9_1.tsv` `81e03ec2eed815dd964b63645295ae65779cd9168d20ca9e9994e4cc70adccee`; inventory `761ca944d18d5b7c545e5ac5b9d3cd3ad83259a2f9aab28b9f3e0eabd0bb07b7`; owner request `eeb2c57bbdd2cefc32bb34100f3070e31a05e99cfe552dc11e01a2bb8b7299f0`; ME-07 instructions `3694e342e094d8dd2496ab8f1328fa05a57eaed294c3c7ce60c205f6e2ccc3bd`; status dimensions `bbeb83654802ef3ce8b9d80f6a218c347b526eee09cb75ffd03ab5f479210459`; Batch 1 acquisition manifest `38bb1b3e7ceee8a9811c0eebddc81026568e9b8529ad4b704f6a6f3fbfa6b5d8`; Batch 1 SHA256SUMS `68933e66075389e7fdf996edaf1847306bd040d06190387186d0ac3630e256dd`; Batch 1 zip `da28835a20a9311619a0a1b16dcdc484cc584a9558fd41e18ba3c76098430c90`; addendum manifest `5878cca914dbfe0b4fa63d3bee422aa2899ac37ba23736e05d9934296ef8d000`; governance README `626d47d48e4de4e06ee9143bc96db1b87764814f726d938ac3f715c6473b32c4`; intake tool `00428601d49f13a1b24948463caec459bccd22dc78c9184b08fd527a99ddc5d9`.
Non-repository state required for continuation (not committed; reacquire as noted): the owner's `files.zip` (SHA-256 `73c4e52440d018d86194e9ccb0db7feb72224263caf5754a5045b30c750d2222`; owner holds it; deliberately not committed because the original author recorded those probe scripts as outside the repository); the three source Claude Docs (Q4-b brief rev 19 `https://claude.ai/artifact/MpmCtTRoaiHKQiQkJNCJLG`; pack rev 28 `https://claude.ai/artifact/PNJZ381PjSfzMiKeYcaAvg`; Q4 brief rev 13 `https://claude.ai/artifact/HYVpzUxz9PspA4hmUcPLHS`); the owner's GitHub token (in the owner's preferences; do not store or reproduce).

## 9. Changes Made
Documentation only: the directory above. No behaviour, interface, schema, architecture, governance, security or test change. Documentation impact: a new review record; no existing document edited; the register (`KNOWN_ISSUES.md`) and other PRs' territory untouched.

## 10. Decisions & Rationale
| ID | Decision | Status | Authority | Evidence | Reopen Condition |
|---|---|---|---|---|---|
| D-01 | Review stays OPEN, NO PASS | settled | mission and every assignment | r9.1 | owner process with the missing evidence |
| D-02 | Do not retype or reconstruct exports; export bytes remain unrecovered | settled | Batch 1 rules | `EXPORT_CALL_LOG.md` | owner supplies unmodified exports or a capture mechanism exists |
| D-03 | Authenticated verification kept in a separate addendum; Batch 1 untouched | settled | hash preservation rule | addendum report | none |
| D-04 | Track discovery, acquisition, integrity and sufficiency separately per ME item | adopted (view only) | owner-pasted assessment, verified useful | `ME_STATUS_DIMENSIONS.tsv` | owner prefers another scheme |
| D-05 | Corrected commit-to-run pairing: `4a4783c` with run 40781867485, `f13bfde` with run 39226693573 | settled | run records (`head_sha`) | instructions section 1 | API record changes |
| D-06 | Mirror outputs byte-identically with a `-text` attribute | settled | hash verification | README, fresh-clone check | repository line-ending policy changes |
| D-07 | Branch from `main`, docs-only, no PR, no merge, never push to `main` | settled | project instructions and the owner's push instruction | git history | owner authorizes a PR |
| D-08 | Do not commit the owner's `files.zip` or the source Docs | settled | original author's statement that the probes are outside the repository | README | owner directs otherwise (custody question ME-04) |
| D-09 | Governance snapshot kept separate from recovery evidence; the 54 versus 65 merged-PR counts stay unreconciled | settled | assessment, verified | snapshot README | method reconciliation requested |
| D-10 | No decision made on D1, D2, D6 wording, ledger identity, custody, #105 contract, hard-deadline authority, FZ-01 | settled | mission boundary | owner request section 4 | owner decides |

## 11. Investigation Already Performed
| Area | Inspected | Result | Evidence | Revisit Trigger |
|---|---|---|---|---|
| Cancellation, deadline, event and checkpoint failures | source plus probes on three baselines | findings in r9.1 (RV-A1..B6) | r1 to r4 bundles | code changes in `core/workflow`, `core/workers`, `core/runtime` |
| Identity lineage on the production K4.2 path | source, probes J1 to J4, K, L | RV-D1..D6 | r5 to r8 | changes in compiler, runtime or capability executor |
| Execution registry | probe I | RV-C1 | r4 bundle | `execution_graph.py` changes |
| PR #81 candidate | source, snapshot probes E | lock covers `resume()` on one runtime object | r3, r9.1 | new commits on the PR |
| Missing evidence | filesystem, repo refs and history, Claude Docs reads and export probes, GitHub pages and authenticated API | inventory and Batch 1 results | `ME_RECOVERY_BATCH_1/`, addendum | owner-supplied files |
| CI evidence for the two commits | API metadata | located, bytes blocked | addendum report section 3 | owner-side downloads |
Items not investigated: real-model runs, `main.py` composition, voice, natural triggers of exceptional events, event-store retention, cancellation rows reserved to #105, the section 22 byte-level tier, D6/criterion 12/criterion 23/26-criteria assessments (inputs missing).

## 12. Failed Attempts / Dead Ends
- Full dependency install in one pass (and in the background): disk exhaustion and background processes killed between calls; worked only as a staged, foreground, guarded install after deleting leftover `/tmp/pip-*`. Do not retry the one-shot install.
- Unauthenticated GitHub API: HTTP 403 rate limit; superseded by the authorized token.
- Probe K3 first run: the capability registry appends adapters in priority order, so the fake adapter still handled calls; the run is kept labelled INVALID; rerun cleared the fake adapter first.
- Export of the Q4-b brief: delivered inline but cannot be written to disk without model retyping; do not attempt transcription. The platform's `create blob` route writes into the source document and is not authorized.
- CI log and artifact downloads: redirect to `results-receiver.actions.githubusercontent.com` and `productionresultssa*.blob.core.windows.net`, not on the sandbox allowlist; retrying does not help.
- `git add -A` silently skipped `logs/AUTH_API_CALLS.tsv` (repository `.gitignore` rule `logs/`): found by the fresh-clone check and fixed by a corrective commit. Always verify a pushed tree against the source folder.
- Earlier statements withdrawn or superseded (do not reuse): see r9.1 section 4 and the r3 to r8 correction lists; also the external assessment's swapped commit-to-run table.

## 13. Verification Evidence
- Full suite on `2491ae4` with the embedding model unavailable (`HF_HUB_OFFLINE=1`, system interpreter): 2139 passed, 43 failed, 1 skipped, 1 xfailed, 1 deselected; the same 43 failing test ids on `16d663a`, `ed3d141`, `2491ae4`; all 43 pass under a diagnostic embedding stub (not a real-model pass). `tests/test_workflow_crash_restart_subprocess.py` plus `tests/test_b2c_cancellation.py`: 8 passed.
- `compare_baselines.py` (in `artifacts/q4b_review_consolidated_register_r9_1.zip`): 8 of 8 probes normalized-identical for each commit pair.
- Archive integrity (2026-11-08 and 2026-11-15): `ARCHIVE_MANIFEST_r9_1.tsv` 19 of 19 rows match; four of six `files.zip` members match full hashes recorded in the brief; `files.zip` unchanged; r3 re-upload identical to delivered copies.
- Push verification: `git ls-remote` equals local HEAD after each push; fresh single-branch clone: `diff -rq` clean against the output folder; Batch 1, addendum, governance snapshot and toolkit manifests all verify; `git diff --name-only origin/main HEAD` outside the review directory is empty (this file aside).

## 14. Environment / Tooling Assumptions
- Sandbox resets between sessions: the scratch clone, venv and intermediate files were lost; only `/mnt/user-data/outputs` persisted. This branch is now the durable copy.
- Rebuilding the test environment (only for later authorized verification): Python 3.12; stage 1 `pip install -r requirements.txt` minus `sentence-transformers`; then `--no-deps` guarded installs of the CUDA wheels and torch; then `sentence-transformers`; roughly 10 GB free disk; foreground only; remove `/tmp/pip-*` leftovers. The namespace sandbox tests need the system interpreter as `sys.executable` (a venv path is invisible inside the sandbox).
- Network allowlist of the sandbox includes github.com, api.github.com, codeload.github.com, raw.githubusercontent.com, PyPI hosts; it blocks huggingface.co and the GitHub Actions log and artifact download hosts.
- Claude Docs tools: `read` works (outline, block views, `atRev` revision reads); `export` returns inline base64 only; revisions 17 readable; `history` returned no rows.
- GitHub token: owner-provided, valid to 2026-11-23 01:11:41 UTC, far broader scopes than needed (repo, workflow, delete:packages, write:packages, codespace, copilot, gist, notifications, project); a fresh session must be given authorization again and must never store or print it. Pushes use `git -c http.extraheader="Authorization: Basic <base64 x-access-token:TOKEN>"` for one command.
- Repository CI triggers only on pushes to `main`, `h2/**`, `integration/**` and PRs to `main`, so this branch push starts no workflow.
- The repository `.gitignore` ignores `logs/` directories; force-add evidence logs.

## 15. Unresolved Questions / Risks / Blockers
| Item | Evidence | Options | Disposition | Required verification | Continue without it? |
|---|---|---|---|---|---|
| Export bytes of the three Docs (ME-01 to ME-03) | export delivered inline only | owner downloads and uploads; or a harness that saves tool results; or owner-authorized write route | BLOCKED | hash on receipt via intake tool | yes for other items; blocks D6, criteria 12 and 23, section 22 byte tier, 26-criteria matrix |
| Which document is "the ledger" | inferred only | owner statement | OPEN (owner) | n/a | yes |
| Custody of exported copies | owner direction of 2026-10-29 not carried out | owner choice | OPEN (owner) | n/a | yes |
| D1 contract choice, D2 definition | register text only; D2 NOT FOUND | owner records | OPEN (owner) | n/a | yes |
| ME-07 CI bytes | digests reported; downloads blocked | owner runs `gh` commands | BLOCKED | digest comparison on receipt | yes |
| Original probe outputs, pytest logs, diff output | NOT FOUND | owner or original author supplies or states none | OPEN | intake | yes |
| #105 contract and ownership | API: open, unassigned; owner chat statement said another session owns it | owner | OPEN (owner) | n/a | yes; do not duplicate |
| Token breadth and exposure | scopes above; token pasted in chat and stored in preferences | owner revokes and replaces after use | RISK | n/a | yes |
| 54 versus 65 merged PRs | different methods and dates | reconcile if needed | UNRECONCILED | n/a | yes |
| Original prompts are extractions, not verbatim | protocol 18.4.8.3 | owner may supply verbatim | LIMITATION | n/a | yes |

## 16. Relevant Information / References
- Repository PRs/issues: #81 (DEBT-028 candidate), #83 and #87 (documentation, `KNOWN_ISSUES.md`), #93 (merged), #94 (auth candidate), #97 (merged, crash-restart evidence), #103 (v2 proposal), #104 (merged, `ed3d141`), #105 (cancellation contract issue), #106 (merged), #107 to #110 (open, new since the earlier inventories; not examined).
- Baselines: `4a4783c` (original revalidation), `f13bfde` (earlier baseline), `16d663a` (mission target), `ed3d141`, `2491ae4` (current main).
- Source documents: Claude Docs links in section 8; project handoff v4 on `feature/verification-critic-evidence-phase-c` (commit `5bb31aa`) holds the original Q4-b closure mission (Appendix A) and document identifiers.
- Where to start reading: `artifacts/CONSOLIDATED_EVIDENCE_REGISTER_r9_1.md`, then `artifacts/Q4B_MISSING_EVIDENCE_INVENTORY.md`, `artifacts/ME_RECOVERY_BATCH_1/reports/BATCH_1_FINAL_REPORT.md`, `artifacts/ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/ADDENDUM_REPORT.md`, `artifacts/ME_STATUS_DIMENSIONS.tsv`.
- Cautions: statuses are evidence-acquisition labels, not assessments; a successful CI run or matching digest does not satisfy the six-file, probe-output or diff-output requirements.

## 17. Next Steps
1. Verify the branch and transfer commit (section 18). Expected: this branch, parent chain `2491ae4 -> 9824d0d -> 8cce19c -> handoff`.
2. Check the uploads folder for owner-supplied files. If none arrived, report that and stop; do not manufacture progress.
3. For any received file: run `python3 artifacts/ME_INTAKE_TOOLKIT/me_intake.py --dest <dir outside the repo> --me <ME-xx> --label "..." [--expect-sha256 <digest>] <files>`; keep sender fields as asserted; make inspection copies separately.
4. For ME-07 archives: compare each raw artifact zip with the GitHub digests (`artifacts/ME07_OWNER_ACQUISITION_INSTRUCTIONS.md`); check member hashes against extracted files; check `run-metadata.json` `head_sha` against the commits; record what the evidence proves and does not prove.
5. Record results as new files (a new acquisition addendum and a refreshed dimension view); never edit Batch 1 files or earlier reports.
6. When the three export files exist and are hashed, plan (do not start without authorization) the blocked assessments: decision D6 consistency, criteria 12 and 23, section 22 tiers, the 26-criteria matrix.
7. Execution-dependent items (ME-14, ME-15) only in a separately authorized batch.
8. Prohibited without new authorization: implementation, PRs, merges, workflow re-runs, edits to the source Docs, resolving D1/D2/D6 or the ledger identity, using PASS or closed language.

## 18. Resume Instructions
First actions: (1) read `PROJECT_INSTRUCTIONS.md` and this file completely; (2) `git fetch`, check out `docs/q4b-independent-review-evidence-nov2026`, verify it contains `8cce19c0a33dcbc67b71c7559e98732fbc9239db` and this file; (3) `git ls-remote origin` to confirm the remote branch head; (4) re-verify `main` (`2491ae4` at handoff) and PR #81 head; (5) verify integrity: `(cd docs/reviews/q4b-independent-review/artifacts/ME_RECOVERY_BATCH_1 && sha256sum -c manifests/SHA256SUMS.txt)` and the other package lists named in the directory README; (6) resolve any mismatch before changing anything; (7) begin at the first uncompleted step in section 17. Do not reconstruct completed work. Do not trust this handoff over the repository or the owner: if they disagree, correct this file and say so.

## 19. Transfer Status
TRANSFER READY, with these recorded limitations: the original prompts are faithful extractions rather than verbatim (section 2); non-repository state exists as listed in section 8 (the owner's `files.zip`, the three source Claude Docs, the owner's token); several inputs are awaited from the owner (section 15). Conditions: transfer commit and this handoff are both on the remote branch (confirmed by `git ls-remote` after the final push, reported in the closing message of the session).
