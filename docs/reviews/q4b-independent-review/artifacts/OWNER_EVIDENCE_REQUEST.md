# Owner evidence request: Q4-b review, blocker resolution

Review disposition remains OPEN - NO PASS. This request asks for files and statements only. It asks you to make no decision unless you choose to (section 4 is yours to answer or leave open). **Please do not paste or send any token or credential**, in chat or in any file.

## 1. Exports of the three Claude Docs (ME-01 to ME-03)
Unblocks: D6 consistency, criteria 12 and 23, the section 22 byte-level check, the 26-criteria matrix.

| Document | Link | Revision I expect |
|---|---|---|
| Q4-b brief | https://claude.ai/artifact/MpmCtTRoaiHKQiQkJNCJLG | 19 |
| Q2/Q5 decision pack | https://claude.ai/artifact/PNJZ381PjSfzMiKeYcaAvg | 28 |
| Q4 brief (section 10.3 ledger) | https://claude.ai/artifact/HYVpzUxz9PspA4hmUcPLHS | 13 |

How: download each document with the document's own download or export option and send the file exactly as downloaded. Please do not open and re-save it, copy the text into a new file, print to PDF, or convert it. If Markdown, Word and PDF are all offered, send each that exists as a separate file; if a format is not offered, tell me which ones are.
Please note for each file: the filename as downloaded, the revision the document shows at that moment, and the date, time and time zone. If the revision differs from the table, send it anyway and say so. Please avoid editing the three documents between your download and my receipt.
For cross-checking only (a different size is not a problem, I record both): the platform reported these sizes through its export tool, in bytes. Q4-b brief: Markdown 71,911 (rev 19), Word 36,774, PDF 1,336,013. Pack: Markdown 26,238, Word 15,843, PDF 472,480. Q4 brief: Markdown 54,262, Word 26,408, PDF 805,476.
On receipt I will record the filename, byte count and SHA-256 of the bytes exactly as received plus the receipt time, keep the original untouched, and make any inspection copy separately with its own hash. I will not change line endings or formatting before hashing.

## 2. Surviving original evidence (ME-05 to ME-08)
Unblocks: the section 22 raw-evidence check, comparison of original and reproduced probe results, the 170-test baseline, the carry-forward of the `4a4783c` revalidation.
Please ask the original author or check your own records for any of these, and send whatever exists exactly as saved:
- the revision 17 outline output and the revision 10 change views, or any file, log or screenshot from the section 22 integrity check (a screenshot will be recorded as a screenshot, not as the output);
- the probe outputs (stdout or JSON) for commits `4a4783c` and `f13bfde`, with the run environment if recorded (operating system, Python version, command);
- the pytest output for the six-file selection at both commits, including whether the embedding model was available;
- the `git diff` output behind "ten of twelve audited files byte-identical" (`f13bfde` to `4a4783c`).
For each item, give the original filename, the file's creation date and where it was kept. If something never existed or was lost, a one-line dated statement per item is enough ("never saved", "lost", "not applicable"). I will not treat silence as non-existence and will not mark any item NOT RECOVERABLE without such a statement.

## 3. GitHub records without sharing a credential (ME-07, ME-13)
Unblocks: CI evidence for both commits and the open/closed state of PRs. My unauthenticated requests were refused (HTTP 403, rate limit). Please run these read-only commands on your own machine with your own GitHub CLI login and send the output files unmodified (they contain response headers and bodies, not your token; please glance at them before sending). I could not test the commands with your authentication; tell me if any fails.
```
S1=4a4783c47ac37971a7d51ab3d7ab6fc904a37106
S2=f13bfdefcdd197ed1f966de0b1f93037a4168af4
R=repos/1h0lde4/ocbrain-v4.1
for s in $S1 $S2; do
  gh api --include $R/commits/$s/check-runs > check_runs_$s.txt
  gh api --include $R/commits/$s/status > status_$s.txt
  gh api --include "$R/actions/runs?head_sha=$s" > actions_runs_$s.txt
done
gh api --include "$R/actions/artifacts?per_page=100" > actions_artifacts.txt
gh api --include $R/pulls/81 > pr81.txt
gh api --include $R/issues/105 > issue105.txt
gh api --include "$R/pulls?state=all&per_page=100&page=1" > pulls_page1.txt
gh api --include "$R/pulls?state=all&per_page=100&page=2" > pulls_page2.txt
```
If any workflow run exists for either commit, please also download its log archive from the Actions page and send it unmodified.

## 4. Statements only you can give (optional; I will not infer any of them)
- **4a.** Which of the three documents is the "ledger" that the Q4-b material refers to, or whether a separate ledger file exists. One line is enough.
- **4b.** How the exported copies should be kept: outside the repository, committed on a documentation-only branch as your 2026-10-29 direction described, or held as an external dependency. Your choice; I will follow it and make no repository change without separate authorization.
- **4c.** For the FZ-freeze decision series: the dated, exact wording of D1 and D2 (and D3 if it exists), labelled with the series name, or "undecided".
- **4d.** Whether regenerated platform views of revisions 17 and 10 may be recorded as clearly labelled new supporting records if no originals exist. They would never be presented as the original evidence.

## 5. What happens after you send
I hash everything on receipt, report any discrepancy individually, map each file to its ME item, and update only the acquisition status. No probe or test is run, no finding or inventory status changes, and items you do not send stay recorded as INACCESSIBLE, LOCATED or NOT FOUND as in Batch 1. The environment-dependent runs (ME-14, ME-15) stay in a separately authorized stage after this evidence is in hand.

## Reply checklist
| Item | Sent (yes / no / none exists) | Filename as sent | Revision or date | Notes |
|---|---|---|---|---|
| 1 Q4-b brief | | | | |
| 1 pack | | | | |
| 1 Q4 brief | | | | |
| 2 rev 17 / rev 10 / section 22 captures | | | | |
| 2 probe outputs (two commits) | | | | |
| 2 pytest logs (two commits) | | | | |
| 2 diff output | | | | |
| 3 GitHub command outputs | | | | |
| 4a ledger identity | | | | |
| 4b custody choice | | | | |
| 4c D1 / D2 wording | | | | |
| 4d regenerated views allowed | | | | |
