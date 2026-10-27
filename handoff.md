# Session Handoff (v4) — Kernel v1.0 Freeze Remediation: Batch 0 → Batch 1

> Transfer record per `PROJECT_INSTRUCTIONS.md` §18.4.8. **Temporary record, not an authority** — verify against the live repo (§18.4.9). **Do not merge this file to `main`.** It supersedes handoff v3.2 *for this mission*; v3.2 (on `security/codeql-findings-sep2026`) still describes the earlier CodeQL/manifest workstream.

## 1. Handoff Metadata
- Version 4 · Created 2026-10-27 07:10 UTC (container clock) · Workstream: Kernel v1.0 freeze remediation under the owner-delivered mission prompt **v2** · Source purpose: execute Batch 0 (read-only) then Batch 1 (CI gate residual R-1), stop at the independent-review checkpoint; ended by the user's instruction "Push the finished work to the repo, then create a handoff file to resume the work in a fresh session".
- **Transfer status: §19 — `TRANSFER INCOMPLETE — PUSH FAILED`.**

## 2. Original starting prompt — FAITHFUL EXTRACTION (not verbatim)
The prompt ("Canonical Freeze Remediation and Certification Prompt", ~9,000 words; v2 supersedes v1 "…Evidence-Gated Closure Prompt") is too large to reproduce reliably here. **The user holds the original — re-paste it verbatim into the fresh session; this extraction is not a substitute.** Operative requirements:
1. **Posture** `NOT_FREEZE_READY`; evidence-first, controlled remediation; preserve existing work. Working language English.
2. **Prohibited remote operations:** merge PRs, modify `main`, force-push, change branch protection, **close PRs**, create/move tags. Publishing a *new, non-forced topic branch* is allowed if the workflow permits.
3. **Boundary:** Batch 0 (read-only, no source edits) then Batch 1 only; **stop at the independent-review checkpoint**; do not start Batch 2 even if R-1 turns out to be already fixed.
4. **Historical audit** `OCBRAIN_KERNEL_V1_FREEZE_AUDIT.md` (2026-10-01, final SHA `ecddbff6968c55ed50661ef28caaef5bb1270bf4`): historical, recheck everything. Its labels are audit-local — use **`OCT01-FZ-01…07`**: 01 K4.2 success despite failed execution · 02 model transport failure → text token → capability success · 03 optional scheduler-loop import failure kills the server · 04 `AdaptiveSemaphore` per-acquisition state leaks permits · 05 unbounded execution-registry **and** EventStream growth incl. state allocation on unknown GETs · 06 persisted event identity islands · 07 CI/pytest allowlist weakness (34 accepted failures; cannot detect stale/overbroad exceptions). **Never equate with a current `FZ-0x`/`DEBT-0x` by label**; build a path-by-path, invariant-by-invariant crosswalk (fields: historical source+ID; current ID(s) if proven; implementation paths; governing contract; historical vs current evidence+SHA; equivalent/overlapping/distinct with reasons; acceptance tests and decision dependency; status/next).
5. **Evidence hierarchy:** (1) verifiable owner decisions within their scope · (2) Constitution/accepted ADRs unless explicitly amended · (3) the prompt's rules · (4) live code/tests/experiments · (5) registers/state docs (may be stale) · (6) proposals, audits, PR text, recommendations (claims).
6. **Integrity rules:** a test double may replace only an external boundary (not the Orchestrator/runtime/adapter/semaphore/registry/persistence under test); reproduce the old failure on the base before fixing; a unit test ≠ an end-to-end contract; a finite stress run ≠ proof; local ≠ CI; **absent run = UNVERIFIED, failed = FAIL, unresolved owner decision = BLOCKED**; record commands, *actual* exit statuses, counts, versions, SHA; sanitize secrets; **`git status` before and after test runs** to detect test-generated changes (DEBT-012) and never discard a pre-existing user change.
7. **Minimal safe changes:** don't weaken tests, broaden an allowlist, duplicate runtime logic, add unbounded queues, infer authority from text/IDs, or mark closure by editing Markdown. Local-first; no mandatory paid AI.
8. **Batch 0 deliverables:** baseline report; finding crosswalk; decision/conflict register; PR/branch/check report; supported-environment statement; required-gate matrix; exact Batch 1 acceptance package. Separate facts / historical claims / inference / recommendations / owner decisions. Don't expand indefinitely.
9. **Gate IDs:** GATE-API-OUTCOME, -PROVIDER-OUTCOME, -SCHEDULER-ISOLATION, -ADAPTIVE-SEMAPHORE, -REGISTRY, -EVENT-RETENTION, -EVENT-LINEAGE, **-CI-ALLOWLIST**, -DEBT023, -REM004, -CTX-EXPORT, -DEBT025, -CROSS-DEBTS, -RELEASE-INTEGRITY, -TEST-HYGIENE, plus -REVIEW / -MANIFEST / -ADMISSION / -FINAL-VERDICT. Definitions live only in the prompt's §3.
10. **Batch 1 — current CI R-1 residual only** (`GATE-CI-ALLOWLIST`): verify R-1's exact state and register mapping; apply the owner-directed disposition (R-1 is a freeze blocker; keep it distinct from historical OCT01-FZ-07). *If open:* smallest safe parser/reporting fix + real-gate regressions. *If fixed:* verify against the base. *If partial:* fix only the residual. *If authority/state can't be established:* UNVERIFIED/BLOCKED, don't infer. Acceptance text is in the Batch 0 report §9. Preserve the allowlist semantics, the **strict ADR-KERNEL-07 D-4 xfail** and the drift check; record whether real CI ran.
11. **Review & stop:** freeze an immutable change SHA; a *separate* reviewer/session; self-review is not independent (→ UNVERIFIED). After Batch 1 report: result SHA, files, pre/post evidence, commands/counts/exit codes, local-vs-CI, reviewer package, status PASS/FAIL/UNVERIFIED/BLOCKED, risks, next-batch recommendation — then **wait for authorization**.
12. **Later (not authorized now):** scheduler → semaphore → provider → API outcome → identity → registry → retention → DEBT-023 → REM-004 → CTX-EXPORT/DEBT-025 → cross-debts → integration/scorecard/Admission Test. Manifest statuses: decision `OWNER_ACCEPTED|PROPOSED|OWNER_DECISION_REQUIRED|SUPERSEDED`; evidence `NOT_STARTED|IMPLEMENTED|VERIFIED|FAILED|UNVERIFIED|BLOCKED`; disposition `MANDATORY|DEFERRED_BY_APPROVED_SCOPE|OUTSIDE_REQUIRED_GATE`. No tags in this task.

## 3. Subsequent user instructions
"Continue/Continuer/أكمل" (repeatedly) · the v1 then **v2** mission prompts (v2 supersedes) · latest: **"Push the finished work to the repo, then create a handoff file to resume the work in a fresh session."**

## 4. Goal, scope, success
Goal: expose the real state and establish verifiable fixes; first pass may end PASS/FAIL/UNVERIFIED/BLOCKED. In scope now: finish the Batch 0 remainders *needed for Batch 1*, implement/verify R-1, stop. Out of scope: Batch 2+, merges, closing PRs, tags, `main`, protection. Success: §17 steps 1–7 done, reviewer package delivered, stopped.

## 5. Requirement ledger
| ID | Requirement | Status |
|---|---|---|
| L1 | Batch 0 deliverables | **INCOMPLETE** — report written; see its §10 for what is not done |
| L2 | Batch 1 (R-1) | **NOT STARTED.** State **OPEN** (register + source reading); no pre-fix measurement exists |
| L3 | Push finished work | **FAILED** — credential rejected (§7) |
| L4 | Independent review | **NOT POSSIBLE yet** (needs a result SHA and a separate reviewer) |
| L5 | Stop before Batch 2 | in force |

## 6. Current verified state
- **VERIFIED:** `origin/main` = `f13bfdefcdd197ed1f966de0b1f93037a4168af4` (2026-10-19 08:59 UTC); workspace was clean (0 uncommitted, 0 stashes, 0 local-only commits); the GitHub token is **dead** (HTTP 401); `v1.0.0` → `0efa222` is 353 commits behind `main`; the Oct 1 audit file is **not in the repo** (every fetched ref searched); DEBT-023's docs claim a mitigation (`_net_proxy.py`, AF_ALG/AF_VSOCK) that `main`'s code lacks; `DEBT-042`/`DEBT-043` already exist on `main` (so PR #79's `DEBT-042` collides); live `enforce_admins: true`.
- **READ (register line 131 + source):** R-1 OPEN — ` - ` truncation in `parse_failed_ids`; hand-truncated allowlist entries can tolerate a failing ` - ` id; the live gate matches by **node ID only**. 
- **NOT VERIFIED:** any pre-fix behaviour (the probe was lost to a container reset); PR checks/mergeability since the credential died; #39/#40 states; everything the prompt attributes to the Oct 1 audit.
- Full detail: `docs/Bugs Hunt & fix reports/FREEZE_REMEDIATION_BATCH0_REPORT_f13bfde.md`.

## 7. Git / repository checkpoint
- Repo `github.com/1h0lde4/ocbrain-v4.1` (**public**). Pinned base: `main` @ `f13bfde`.
- **New branch (docs only) `audit/freeze-remediation-batch0-oct2026`**: commit `84fe1a6` = the Batch 0 report; this handoff on top. **It exists only in the container and in the delivered `batch0-handoff.bundle` + files — it is NOT on the remote.** Push attempt 1: exit **128**, "could not read Password"; remote has 0 matching branches. Attempt 2: made after committing this file; its exit status is recorded in the follow-up commit and in the delivering message.
- **Already on the remote from earlier work (unchanged):** `security/codeql-findings-sep2026` @ `2d03b70` (handoff v3.2, manifest draft, R7 write-up, notes); PR #79 branch @ `bcbe574`; PR #87 branch @ `917bb37`.
- **To publish later:** with a fresh credential, `git push <https-url-with-token> audit/freeze-remediation-batch0-oct2026` (non-forced). **Importing the bundle:** `git fetch batch0-handoff.bundle audit/freeze-remediation-batch0-oct2026:audit/freeze-remediation-batch0-oct2026` inside a clone of the repo.

## 8. Active files
`docs/Bugs Hunt & fix reports/FREEZE_REMEDIATION_BATCH0_REPORT_f13bfde.md` (the deliverable) · `handoff.md` · the Batch 1 target `scripts/ci_test_gate.py` (244 lines), `tests/test_ci_test_gate.py` (18 test functions / 67 cases per the register), `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt` (34 entries; header documents the gate's contract), `.github/workflows/ci.yml` (`tests` job records pytest's real exit code, then the script decides).

## 9. Changes made
Documentation only. No source, test, CI or dependency file was modified.

## 10. Decisions & rationale
| ID | Decision | Why |
|---|---|---|
| D1 | Treat the v2 prompt as the owner's instruction | It was delivered as the user's instruction; authorship unverifiable |
| D2 | Record everything attributed to the Oct 1 audit as **CLAIM** | The file is not in the repo |
| D3 | Report R-1 scope as a **conflict (C2)**, not resolve it | The register's R-1 is parser-only; the prompt's acceptance adds a failure *signature* — owner's call |
| D4 | Claim **no** pre-fix measurements | The probe never ran |
| D5 | Withdraw my earlier "FZ-06 ≡ DEBT-030" and "register FZ-07 = audit FZ-07" | Under this prompt both are inference, not demonstrated equivalence |
| D6 | Deliver files + bundle when the push fails | A reset-prone container is not a safe sole copy |

## 11. Investigation performed / not performed
Performed: baseline, preservation, PR heads via `refs/pull/*`, tags, ADR-branch scan, env configuration, DEBT-023 docs-vs-code, a full read of `ci_test_gate.py`, the register's R-1 text. **Not performed:** the pre-fix probe, `tests/test_ci_test_gate.py` contents, the allowlist's real failure signatures, any research of pytest's documented exit codes/hooks, crosswalk rows for REM-004 / CTX-EXPORT-001 / DEBT-025 / DEBT-028/029/036/015 / DEBT-012 / DEBT-031/032.

## 12. Failed attempts and lessons
| What happened | Lesson |
|---|---|
| **Container reset three times this engagement** (twice within this mission) wiping repo, venv and `/tmp` | Only pushed work survives; write durable artifacts *first* |
| **A zero/empty result from a failed command was nearly read as a finding — again.** After a reset: `cd` failed, the gate copy came out empty, then `uncommitted entries = 0` printed | Verify the command could succeed (print the blob hash, assert the module exposes `evaluate`, show exit statuses) before trusting an empty or zero |
| The probe never ran (env gone) | Rebuild first (§14), then probe |
| The credential died mid-task | Test auth with a plain `curl` to `/user` first; unauthenticated API reads share an IP rate limit — use `refs/pull/*` over git instead |
| Bash-isms in `/bin/sh` (`${v:0:7}`), `$?` inside a string after a `$(...)`, reversed `git worktree add` arguments | Use `cut`, save `RC=$?` immediately, `git worktree add <path> <commit>` |
| Earlier overstatements (above, D5) | Label equivalence as proven or inferred |
| DEBT-id collisions with concurrent sessions (4 now, incl. `DEBT-042`) | Take the live max id at write time |

## 13. Verification evidence
`git push` attempt 1 → **exit 128**, branch absent from the remote (**FAIL**). Token check → HTTP 401. Gate script and register: **READ**. Pre-fix probe: **NOT RUN**. Suite/drift: **not run this mission**. No CI result claimed.

## 14. Environment and credentials
- Rebuild (the tool shell is `/bin/sh`): `mkdir -p /home/claude/audit && cd /home/claude/audit && git clone https://github.com/1h0lde4/ocbrain-v4.1.git repo && cd repo && git fetch origin '+refs/pull/*/head:refs/remotes/pr/*'; grep -vE "^sentence-transformers" requirements.txt > /tmp/req_minimal.txt; pip install --no-cache-dir --break-system-packages -r /tmp/req_minimal.txt`. **Never plain `pip install -r requirements.txt`** (pulls `torch`).
- Sandbox baseline class: Python 3.12, no `torch`, `chromadb==0.5.3`, `trafilatura` installed. A prior baseline: suite `2072 passed, 1 xfailed` at `488129b` — **re-measure at the new pin.**
- **Credential:** a GitHub PAT (repo scope) must be supplied by the user; never write it to a file or commit (public repo). The token previously pasted in chat is **revoked**; the one in the saved `userPreferences` is older and revoked too.

## 15. Unresolved questions / owner decisions
Q1 Supply `OCBRAIN_KERNEL_V1_FREEZE_AUDIT.md`. Q2 Provide a fresh credential (or push the bundle yourself). **Q3 R-1 scope:** parser-only (register) or parser **plus** failure signature (prompt) — and what *is* the approved signature for the 34 entries (their real failure types are unknown; in GitHub CI they likely pass, so the list may be dormant). Q4 Renumber PR #79's `DEBT-042`; PRs #79/#83 are 8 commits behind and `dirty`. Q5 Soften "FZ-06 ≡ DEBT-030" in PR #87 and in the manifest draft (§3 F4/§4). Q6 Who changed `enforce_admins` to true, and was it intended? Q7 PRs #89 (48 commits) and #81 (13) are stacked — which commits are the intended review scope? Q8 Is OCT01-FZ-07's stale-entry detection in scope later?

## 16. References
The Batch 0 report; `scripts/ci_test_gate.py`; `KNOWN_ISSUES.md` line 131 (R-1); the allowlist header; PR #55 (the FZ-07 primary fix); PRs #79/#81/#83/#86/#87/#88/#89; `premerge_guard.py` (merge authority pinned to a head SHA, per PR #88's text).

## 17. Next steps (in order)
1. Re-paste the v2 mission prompt; read this file and the report; verify the transfer (§18).
2. Obtain a credential; publish the branch non-forced (or import the bundle).
3. Rebuild the environment (§14); re-pin `main`; `git status`.
4. **Run the pre-fix probe** (report §9) — assert it is capable of producing output first; record exit statuses; this converts D1–D2 from READ to VERIFIED.
5. Finish only the Batch 0 remainders Batch 1 needs: read `ci_test_gate.py` + `tests/test_ci_test_gate.py` + allowlist header in full; research the 34 entries' failure signatures; consult pytest's documented exit codes/hooks; re-fetch PR checks if a credential exists. **Resolve or record Q3 before designing the signature.**
6. Implement Batch 1 in a *separate worktree* from the re-pinned `main`: `git worktree add <path> -b fix/ci-gate-r1-parser-hardening-oct2026 origin/main`; bracket every test run with `git status`; preserve the allowlist and the D-4 strict xfail; run the real gate tests and the drift check.
7. Freeze an immutable SHA, build the reviewer package, report in the prompt's format, **stop and wait.**

## 18. Resume instructions
1. Confirm the branch is reachable (bundle or remote) and read both files. 2. Compare this record with the live repo; **the repo wins.** 3. Resolve mismatches before changing code. 4. Begin at §17 step 2.

## 19. Transfer status
**TRANSFER INCOMPLETE — PUSH FAILED.** All material information is recorded here and in the report, and the commits are bundled for delivery, but the new branch is **not on the remote**: the only credential was rejected.
