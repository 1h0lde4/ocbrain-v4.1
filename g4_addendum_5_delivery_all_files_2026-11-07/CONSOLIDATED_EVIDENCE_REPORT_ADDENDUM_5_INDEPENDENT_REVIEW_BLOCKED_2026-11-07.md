# Addendum 5 to the Consolidated Evidence Report — the independent review that could not be run, a review package, and a stronger status check — 2026-11-07

Addendum to Addendum 4 (`CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_4_THIRD_ATTACHED_REVIEW_AND_P1d_REV3_2026-11-06.md`, sha256 `d619b7c87b4b3d242adc6922bbaa9fb770ad7025196db5b45a162c476fa637f8`; delivered with its files as `g4_addendum_4_delivery_all_files_2026-11-06.zip`, sha256 `162b4238c6d2437ee8a4cef95fb1f2a8296116c4dc832e7bb7c664fda34822ef`). Addendum 4 and everything before it are not edited. Evidence: `I68`–`I72` in `g4_addendum_5_evidence_I68-I72.zip` (sha256 `006a9c96c2e427f82c604fd3931beee1ae3ca00e86f934cadfa3d1dc541b07f6`, delivered beside this addendum). `I73`, `I74` and `I75`, the author's mechanical checks of this addendum, are delivered as separate files because they check the text that cites the bundle's hash. `I73` is the first run and failed with three FAIL lines from two causes: the token scan matched the string `REVIEW_` inside this addendum's own file name (a checker flaw, so I changed the scan to ignore code spans), and the stronger status rule matched a sentence of section 5 that only described its own patterns (a text issue, so I reworded the sentence). `I74` passed on the text after those two changes. `I75` is the passing rerun on the final text, after this sentence was made precise. None replaces another. The work ran on 2026-11-06 (the two reviewer launches) and 2026-11-07 (everything else).

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This addendum changes no repository, no pull request and no decision item.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what a text says; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **The one independent review of revision 3 could not be completed** [OBSERVED, I57, I68, I72]. In total four reviewer launches (two reported in Addendum 4, two in this step) were each terminated by an API rate-limit error (HTTP 429, "5-hour limit") within minutes, without a report. The last one left a report file that contains a status line and a heading and no findings. Revision 3 therefore stays **PROPOSED — SELF-REVIEW ONLY**, and F7 stays OPEN. I did not make a fifth launch (section 4).
2. **I prepared a package so that the review can run somewhere it can finish** [OBSERVED, I70]: a brief, the block, the patch, the file the patch applies to, and the revision 2 block for comparison. The brief carries none of my results. A reviewer returns a report whose first line is `SUBSTANTIVE FINDINGS: yes` or `SUBSTANTIVE FINDINGS: no`.
3. **I found and fixed a weakness in my own tooling** [OBSERVED, I69]. The status check of my Addendum 4 checker rejected only 2 of 9 mutated copies that contained incorrect, ambiguous, duplicate or conflicting status text. A stronger version rejects all 9 and still accepts the delivered Addendum 4 unchanged (finding F13, section 5).
4. **Nothing was applied, committed or pushed** [OBSERVED, I71]: `HEAD` and the remote REV2 tip are still `d963daa502de4220411d0d0c2f19f67b3ec2682b`, the clone is clean, PR #90 is unchanged.
5. **Statuses unchanged:** G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED; D-1…D-11 OPEN; no implementation authorized.

## 2. What was received

Text pasted into your message of 2026-11-06, headed "Worked for 40s", with no instruction of its own. It reads as another assistant's decision on Addendum 4. It says that its author could not open the delivery files, so its decision rests on my report and is not a source-level review. It is input to verification, not evidence, and it grants nothing beyond what it says.

## 3. What the pasted text allows, and what I did

| Item in the pasted text | Decision it states | What I did |
|---|---|---|
| Revision 3 as the sole review candidate | Approved | Used revision 3 only |
| One independent review | Approved | Launched it twice; both ended by the usage limit (section 4) |
| A fourth rewrite, automatically | Not approved | None made |
| Apply revision 3; commit or push | Not yet approved | Not done |
| Apply any alternative patch | Prohibited | Not done |
| Close F7 now | Prohibited | F7 stays OPEN |
| Change the G4–G8 status | Not authorized | Unchanged |

Its list of conditions for the reviewer is covered by the brief: the six revision 2 failures (item A), canonical remote identity (B), the exit status of every `ls-remote` call (C) and the race at the final observation (F), the integrity of `handoff.md` (D), credential protection (E), patch integrity (G), and the status-line check (I).

## 4. The independent review

| Launch | When | Result |
|---|---|---|
| 1 and 2 | 2026-11-04 and 2026-11-05 | usage-limit error, no report (Addendum 4, `I57`) |
| 3 | 2026-11-06, about 12:57 | usage-limit error within minutes; 3 scratch entries, no report [OBSERVED, I68] |
| 4 | 2026-11-06, about 17:52, just after a limit reset | usage-limit error immediately after creating its report file; the file holds a status line and a heading and no findings [OBSERVED, I68, I72] |

**[DERIVED]** A reviewer that runs dozens of git experiments uses a large share of the plan's usage in a few minutes, and launching it again from this session would most likely end the same way and block my other work. I did not use any leftover scratch as a finding or as evidence.

**The package** [OBSERVED, I70]: `g4_rev3_independent_review_package.zip` (sha256 `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`), 8 files. Its block is byte-identical to the delivered `verify_block_rev3.sh` (sha256 `e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53`), its patch is identical to the delivered patch, its base file equals the `handoff.md` of the pushed REV2 tip, the patch applies to that base in a scratch repository (not applied anywhere else), and the brief contains none of the result figures, evidence references or hashes that `I70` searches for (it lists them). The only results-bearing material is in one folder that the brief says to open last, for item I. It contains no token-like strings.

**How to use it:** give the zip to a human or to a different assistant that can run a shell and git, and bring back its report. If the first line is `SUBSTANTIVE FINDINGS: no`, you can decide on applying revision 3. If it is `yes`, I stop and return the finding; no rewrite starts without your decision.

## 5. The status check, tested by mutation

I copied Addendum 4 ten times, injected status text into each copy, and ran the Addendum 4 checker (v1) and a stronger version (v2, a separate file; v1 and the runs `I65`–`I67` are untouched) on every copy [OBSERVED, I69]. A mutant must be rejected, except the control.

| Mutant | v1 | v2 |
|---|---|---|
| M0 control, unchanged text | ACCEPTED | ACCEPTED |
| M1 a sentence closing G4 | ACCEPTED (wrong) | REJECTED |
| M2 a second, conflicting governing line | ACCEPTED (wrong) | REJECTED |
| M3 last line replaced by a conflicting sentence | REJECTED | REJECTED |
| M4 the governing line duplicated exactly | ACCEPTED (wrong) | REJECTED |
| M5 a sentence declaring freeze readiness | ACCEPTED (wrong) | REJECTED |
| M6 an ambiguous sentence that calls G4 open or closed | ACCEPTED (wrong) | REJECTED |
| M7 a gate status word changed to PARTIAL | REJECTED | REJECTED |
| M8 a sentence releasing G5–G8 | ACCEPTED (wrong) | REJECTED |
| M9 a sentence authorizing implementation | ACCEPTED (wrong) | REJECTED |

Totals: 9 mutants must be rejected; v1 rejected 2, v2 rejected 9. v2 adds: the governing line occurs exactly once; the exact status sentence occurs exactly twice (that line and the final line); and a list of patterns for four kinds of conflicting wording (a wrong G4 status, a wrong G5–G8 status, a freeze declaration, an authorization of implementation). It is a tripwire for the wording I tested, not proof: a status stated in other words would not be caught. This addendum was checked with the same hardened rules (`I73`).

## 6. Gates and open findings

Exactly one status per gate, for this addendum's scope (acting on the pasted decision: the one independent review, and what could be done without it).

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Pasted text treated as unverified input; what it allows recorded | **PASS** | section 3 | nothing beyond the review was done |
| One independent-context review of revision 3 completed | **BLOCKED** | I57, I68, I72 | four launches ended by the usage limit; no report |
| Review package prepared, identical to the delivered block and patch, patch applies, brief carries no results | **PASS** | I70 | section 4 |
| Status handling of the checker mutation-tested; stronger version rejects 9 of 9 and accepts the delivered text | **PASS** | I69 | section 5 |
| No ref, commit, working file, pull request or remote changed | **PASS** | I71 | `HEAD` and remote tip `d963daa5…`, status 0, PR #90 unchanged |
| G4/freeze invariants | **PASS** | section 1 | statuses stated unchanged |
| **Overall result (this addendum's scope)** | **BLOCKED** | | every gate passes except the independent review, which is the purpose of this step; revision 3 stays PROPOSED, SELF-REVIEW ONLY |

| Finding | Status | Note |
|---|---|---|
| F1–F5 (Addendum 1) | **OPEN** | pushed wording residuals; revision 3 carries the fixes |
| F7 (Addendum 2) | **OPEN** | closure needs the independent review, an authorized push and a successful run from a fresh clone of the canonical URL |
| F8 (Addendum 3) | **OPEN** | the P1d of Addendum 2 must not be applied |
| F9, F10, F11, F12 (Addendum 4) | **FIXED in the proposal; not VERIFIED** | independent review not done |
| **F13** (new, mine) | **FIXED in tooling (v2); not VERIFIED by anyone else** | v1 of the Addendum 4 checker accepted conflicting status text in 7 of 9 mutants (`I69`) |
| F6 (Addendum 1) | not changed | metadata only |

## 7. Decisions for you

1. **How to get the one independent review.** (a) Give the package to a human or another assistant that can run a shell and git, and bring back its report. (b) Tell me to retry here after the usage limit has reset and while I am doing nothing else; I expect it may end the same way. (c) Accept self-review only; that cannot close F7 under the criterion we adopted.
2. **After a review.** With `SUBSTANTIVE FINDINGS: no`, I apply revision 3 only on your explicit instruction: one commit with the attribution trailers, a non-force push, a run of the block from a fresh clone of the canonical URL, and a record. With `yes`, I stop and return the finding.
3. **The status check:** use v2 for future addenda, or keep v1.
4. **D-1…D-11, the next-session entry point and the ledger wording** stay with you; **the PR #90 rebase** is the PR owner's call.

Nothing was pushed in this step; rollback of earlier pushes is unchanged (section 7 of Addendum 1).

## 8. Limits

- No independent reviewer has read revision 3. The package has not been run by anyone yet.
- The cause given in section 4 is my inference from the error messages; I cannot see the plan's usage accounting.
- v2 is a tripwire for wording I tested; it does not prove that the statuses are right, and a human still reads them. It also has false positives: on its first run over this addendum (`I73`) it flagged a sentence that only described its patterns.
- The package's item I folder contains Addendum 4, so the reviewer is not blind for that item only.
- Not examined: CI, the chain of custody of the REV3 ZIP and the user-side `handoff(1).md`, and the pasted text's authorship beyond what it says.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
