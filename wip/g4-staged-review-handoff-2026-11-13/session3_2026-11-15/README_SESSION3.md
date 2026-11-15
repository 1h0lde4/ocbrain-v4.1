# Session 3 addendum — Stage S7 result (2026-11-15)

**What this adds.** The Phase A stage S7 (criterion I) of the staged review of REV3. It sits beside `../session2_2026-11-14/` and the unchanged bundle; nothing earlier was edited. Files here are covered by `SHA256SUMS_session3.txt` (this note included).

| File | What it is |
|---|---|
| `REPORT_S7.md` | The S7 reviewer's final report, extracted byte-for-byte from the conversation record with `tools/extract_handback.py` (25,556 bytes, sha256 `7122049d8724f1a2823aa73ccacc8b8a885e047abb9eb4e7a98848e0c765605c`). This is the canonical text. Not edited. |
| `REPORT_S7_agent_written_file.md` | The file the reviewer itself wrote into its directory (25,164 bytes). It differs from its final hand-back in wording and line breaks (checked with `diff`); the hand-back is the canonical one. Kept so that nothing is silently discarded. |
| `stage_S7_scripts_and_evidence.zip` | The reviewer's scripts, row tables, raw per-row output and the 90 variant documents (644 entries). Excluded: the package copies and a duplicate re-run directory (`repro_check/`). |
| `author_spot_check_I/` | My own independent re-run of three S7 findings with my own harness: `front.py` (lines 1–44 of `check_addendum4.py`, verbatim, plus one exit line), `spot_check_I.py`, its output. |

## How S7 ran
The first launch (2026-11-14 12:18 UTC) was cut off by the usage limit before it did anything (empty directory, no agent id returned). The relaunch at 18:48 UTC completed in about nine minutes. Reviewer: independent-context sub-agent of the same model family as the author, not a human (same limitation as S1, S2, S4, S5, S6). It reports that its context held the project's attached instructions and memory listing, which it did not use; no review results.

## Result (reviewer's report; [REPORTED] unless marked)
**Criterion I = FAIL**: three false PASSes of `check_addendum4.py` (stage-local ids; F-numbers to be assigned in Addendum 7):
- **I-1** a conflicting, contradicting or ambiguous status statement anywhere else in the document is not detected (12 of 12 rows: e.g. an added "G4 CLOSED.", a second conflicting governing line, a retraction on the governing line, a struck-through governing line);
- **I-2** an altered governing line is accepted if an intact copy of the required line exists anywhere, e.g. in a code fence or an HTML comment (3 of 3 rows);
- **I-3** only the first gate table is read; a second table, an orphan row, or a fenced decoy table is not seen (3 of 3 rows).
Of 90 variants: 43 correct FAIL, 10 correct PASS, 18 FALSE PASS, 1 false FAIL, 18 "undecided by the brief" (owner decision needed on how fenced, quoted or hidden status text should be treated). Every alteration of the governing line itself that the contract says must fail was rejected. The REV3 block was not exercised in S7; no credential or URL was printed.

**Method limit that matters.** The checker takes 11 inputs, 8 of which are not in the package, so the unmodified checker cannot run to a result here (it dies at line 69 on a missing zip, exit 1 for every row, baseline included). The verdicts come from an instrument made of lines 1–44 of the checker (the status handling) verbatim plus an exit line. That the rest of the checker (lines 45–167, including a live `git ls-remote`) would not react is DERIVED by reading, not observed.

## What I checked myself ([OBSERVED] by the author, 2026-11-15 ~02:01 UTC, python 3.13.18; `author_spot_check_I/spot_check_I_output.txt`)
With my own harness (checker lines 1–44, verbatim, run with `python3 -I` on mutated copies of the addendum): unmodified → PASS; governing line changed to "G4 CLOSED" → FAIL (correct); an added line "Status update: G4 CLOSED. Freeze readiness DECLARED." → **PASS** (I-1); a second, conflicting governing line → **PASS** (I-1); governing line altered with the intact line pasted into a code fence → **PASS** (I-2); a second gate table with a FAIL gate and Overall PASS after the real table → **PASS** (I-3). So I-1, I-2 and I-3 reproduce on the status-handling section of the checker.
Reviewer footprint audited: nothing changed outside its directory; package and preamble hashes intact; remote tips unchanged; its 17 shell commands contain no network tool use (two grep hits were prose inside a script).
**Not re-run by me (remain [REPORTED]):** the other 84 variant rows, the minor findings, and any full-checker verdict.

## Interim A–I matrix after Phase A (not final; Phase B not run)
A PASS · B **FAIL** · C PASS (caveats) · D PASS (four ambiguous rows) · E **FAIL** · F PASS · G **FAIL** (G1–3 PASS from S1, G4 FAIL from S6) · H **FAIL** · I **FAIL**.
Phase B: S3 (loopback-TLS reproduction of the F14 printed PASS and the HTTPS username-token case) and S8 (comparison with Addendum 6) NOT RUN. The overall verdict cannot be PASS. The review is IN PROGRESS, not a completed review, until S3 and S8 run and the stage reports are consolidated.

## Next (handoff section 17, steps 5–10)
S3 and S8 (Phase B, which may read Addendum 6 and the S2/S5 reports), then consolidation with the verdict rule applied mechanically, then Addendum 7 (assign F-numbers to S2/S5/S6/S7 findings; decisions for the owner in handoff Q3–Q5, Q9 plus the 18 undecided I rows). No correction of rev3 or of the checker is authorized, and nothing here proposes one.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
