STAGE S7: COMPLETE

Note on files: the harness refuses report files from subagents, so there is no new REPORT_S7.md. This message is the report. The earlier run's file is kept as REPORT_S7_prior_1.md (criterion I NOT RUN).

## Package integrity
- The full SHA-256 of both package/g4_rev3_independent_review_package.zip and my copy pkgcopy.zip is 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286. It equals the preamble value.
- Inner SHA256SUMS.txt "7 of 7 OK" comes from the earlier run. I did not re-check it. `cmp` shows work/check_addendum4.py and work/addendum_orig.md are byte-identical to pkg/review_package/optional_item_I/.

## Material reused from the earlier run (run 1)
- pkg/ (extracted package), pkgcopy.zip, work/check_addendum4.py, work/addendum_orig.md, and work/stub/* (dummy attachment, bundle, patches, add1-3, report) with empty work/ev and work/repo.
- baseline_probe.out, which I confirmed by re-running M00.
- Everything else (the harness, 62 runs, the evidence) is from this run.

## Criterion I: FAIL
Checker accepts texts with a wrong, conflicting or hidden governing status.

Why the checker passes these texts:
1. **Governing-status line (line 26):** `"**Governing statuses, unchanged:** " + want not in txt` is an unanchored substring test. Anything may come before or after the match, and the match may sit in a comment, quote, code block or indented block.
2. **Last-line test (lines 7 and 24):** it uses `str.splitlines()` and Python's universal-newline `open()`. These split at U+2028, U+0085, form feed and lone CR, so `tail -n1` and `grep -Fx` see a different "last line" than the checker.
3. **No conflict scan:** nothing looks for other status statements anywhere in the text. The only content checks are the two status lines, the gate-table word set and consistency, a few required words (F7-F12, OPEN, "not VERIFIED", "not done"), and the forbidden tokens (PLACEHOLDER, REVIEW_, TODO etc.).
4. **Gate table (lines 27-42):** it only checks that status words come from {PASS, FAIL, BLOCKED, NOT RUN} and that the Overall row is consistent. It has no required rows, and the table has no row that states the G4/G5-G8 statuses.

Exit-code limitation (applies to all 62 runs):
- Every run exits 1, including the unmodified text (M00), because the evidence-file, repository and hash checks fail with the stubs.
- A true exit 0 is unreachable in this package, so I classified each run by its status-check output. Every status-line and gate-table check prints before the `ids cited:` line. A run counts as "rejected" if a `FAIL:` line appears before that marker, or the script crashes before it.
- For all 22 FALSE ACCEPT runs, the complete set of `FAIL:` lines is identical to the unmodified baseline M00. The status checks add no failure, so I classify the 22 as FALSE ACCEPT (OBSERVED per-check, but exit 0 is DERIVED). Judged only from the exit code, these runs would not look different from the unmodified text.

Results of 62 runs (61 mutations plus the M00 control):
- 35 correct reject.
- 22 FALSE ACCEPT.
- 5 correct accept (M00, M28, M57, M59, M60).
- 0 false reject.

Table: SUMMARY_TABLE.tsv. Raw outputs: evidence/Mxx.stdout and evidence/Mxx.stderr. Mutated inputs: work/mut/Mxx.md.

What the checker correctly rejects:
- **Wrong status on the governing line (M01-M06):** "G4 CLOSED", "G4 RESOLVED", Low, "G5-G8 RELEASED", "DECLARED" and "non-blocking" all give `FAIL: governing-status line missing`.
- **Wrong status on the last line (M07-M11):** each gives `FAIL: final line`.
- **Near-misses on the last line (M14-M23):** lower case, hyphen instead of en dash, a different separator, double space, NBSP, a trailing space, a trailing or interior U+200B, a hedged suffix and a negated prefix are all rejected.
- **Near-misses inside the governing line's label and status text (M29-M31):** lower case, hyphen and interior U+200B are rejected.
- **A wrong line appended after the correct last line (M43), and deletion of either line (M47, M48)**.
- **Gate table (M49, M50, M53, M54, M56):** FAIL in the G4/freeze invariants row with Overall PASS, status word CLOSED, lower-case "pass", Overall FAIL with every gate PASS, and the missing SELF-REVIEW ONLY label.

## Findings (all substantive under the package contract; classification OBSERVED unless noted)
Common to all findings:
- Command: `cd work/ev; env -i PATH=/usr/bin:/bin GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 HOME=/nonexistent python3 -I work/check_addendum4.py work/mut/Mxx.md work/ev work/repo work/stub/{bundle.zip,rev3.patch,rev2.patch,att.txt,add1.txt,add2.txt,add3.txt,report.txt}`. Mutations are made by run_mutations.py on copies only.
- Severity: Low in absolute terms (optional item I). Impact: a checker run could report no status problem on a text that contradicts the governing status.
- Reproduction limits: stub evidence, so overall exit is 1 in every run (see above). Expected for each finding: some `FAIL:` line before `ids cited:`. Actual: none.

**S7-F1: unanchored governing-line substring (check_addendum4.py:26).** Accepted with no status FAIL:
- M32: the correct line plus " Note: G4 was closed in a later review."
- M33: "It is not true that " before `**Governing statuses...`
- M34: the correct line plus " G4 CLOSED. Freeze readiness DECLARED."
- M35: a trailing U+200B after the final period.
- M46: the line indented four spaces (a code block).
- M44: the correct line wrapped in an HTML comment, with a visible paragraph "G4 CLOSED · … DECLARED." after it.

**S7-F2: no duplicate or conflicting-status scan (absence of any check beyond lines 23-26 and 27-42).** With line 5 and the last line intact, all of these are accepted:
- M36: a body paragraph "G4 CLOSED · High · freeze-blocking. G5-G8 RELEASED. Freeze readiness DECLARED."
- M37: the same text in a table cell.
- M38: in a code fence.
- M39: in a blockquote.
- M40: line 17 ("Statuses unchanged") changed to "G4 CLOSED".
- M41: a second, wrong "Governing statuses, unchanged:" line before the correct one.
- M42: the wrong line placed before the correct last line.
- M45: an unclosed `<!--` inserted before the correct last line, which hides that line when rendered.

**S7-F3: last-line test uses splitlines and universal newlines (lines 7 and 24).** Each is accepted with `last non-empty line ok: True`:
- M25: wrong status + U+2028 + correct text on one physical line. `tail -n1 work/mut/M25.md` shows the wrong status first; `grep -Fxc` finds 0 matches.
- M26: the same with U+0085.
- M27: the same with form feed.
- M61: the same with a lone CR.
- M24: an invisible trailing U+2028.
- Contrast: a trailing U+200B (M19) is rejected, so the test is strict only for characters Python does not treat as line breaks.

**S7-F4: gate-table test is a word-set and consistency check only (lines 36-42).** Accepted:
- M51: the G4/freeze invariants row stays PASS but its reason cell says "G4 CLOSED; freeze readiness DECLARED".
- M52: the G4/freeze invariants row deleted.
- M55: an extra row "| G4 CLOSED | PASS | x | y |".

## Minor findings
- M58: a malformed gate row "| G4 |" makes the script crash with `IndexError` at line 34. It fails closed, but as an uncontrolled traceback.
- Accepted as neutral, not counted as false accepts: CRLF line endings (M59), a UTF-8 BOM (M60), a trailing NBSP-only line (M28), and consistent BLOCKED statuses (M57).

## Unreviewed / not verified
- A true exit 0 on a mutated text was not shown (see the limitation above). I did not synthesise the missing evidence files, and I did not modify the checker.
- Not tested: other Unicode normalisation forms, multi-megabyte inputs, invalid UTF-8, the checker's non-status checks (evidence, hashes, patches, bundle) beyond how they interact with exit status, and rendering in a real Markdown viewer (M44/M45 hiding is DERIVED from Markdown semantics).
- M52 and M55 rest on a weak expectation: the checker has no stated requirement for those rows.

## Environment
Python 3.13.18 (`python3 -I`), GNU bash 5.2.21, Linux 6.18.44. No network, no repository, no package file modified. The checker's own `git -C repo` calls fail with 128 as in the baseline.

## Declaration
- I am a Claude model sub-agent (Sonnet 5.5) in an independent context, the same model family as the author, not a human.
- Tools: Bash, Read, Write (the harness, not a report).
- I had no contact with author results, apart from the leftover files of my own earlier run (described above). I did not open any other stage directory, reports/, handoff_work/ or any repository.
- Date: 2026-11-23 (UTC).

## Reproducibility
- Harness and table: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a9/stage_S7/run_mutations.py (run `python3 -I run_mutations.py`) and SUMMARY_TABLE.tsv.
- Evidence: evidence/INDEX.txt, evidence/Mxx.stdout, evidence/Mxx.stderr, and the re-runs evidence/rerun_M36.out and evidence/rerun_M25.out (both exit 1, zero status FAIL lines).
- Mutated inputs: work/mut/Mxx.md.
- Baseline: baseline_probe.out and evidence/M00.stdout.

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
