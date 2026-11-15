STAGE S7: COMPLETE
SUBSTANTIVE FINDINGS: yes (item I only; three findings, all FALSE PASS of check_addendum4.py; no credential or URL output observed; the REV3 block was not exercised in this stage)

# REPORT S7 - criterion I (check_addendum4.py and its governing status line)

Date: 2026-11-14 (UTC). Reviewer: Claude (model "Sonnet 5.5", id claude-sonnet-5-5) sub-agent, independent context, same model family as the author, not a human.

## 1. Package integrity
- Zip full SHA-256 computed on the original and on my copy: 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286 = the authoritative value (full-value compare). Original not modified (copied to stage_S7/zipcopy/pkg.zip, extracted to stage_S7/pkg/).
- SHA256SUMS.txt inside the package: all 7 listed files OK. Files used: optional_item_I/check_addendum4.py (sha256 60d59bf53f63a39d6a37081b3d8b9e13fd0abe2ea32ced15ced5f63b6953a308), the addendum report in the same folder (sha256 d619b7c87b4b3d242adc6922bbaa9fb770ad7025196db5b45a162c476fa637f8); copies in my work directory are byte-identical.

## 2. Acceptance condition for item I (as I read it)
Brief item I: judge, by reading and by testing mutated copies, whether check_addendum4.py "rejects incorrect statuses (for example 'G4 CLOSED'), ambiguous statements and duplicate or conflicting status lines elsewhere in the text", and report what it does not catch. Task prompt: a false PASS (the checker accepts a document whose governing status line `G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.` is missing, altered or contradicted) is substantive. Status-relevant code: S1 = line 24-25 (last non-empty line == the status string, exact); S2 = line 26 (`"**Governing statuses, unchanged:** " + status in txt`, substring anywhere); gate table = lines 27-42 (first table only; allowed words PASS/FAIL/BLOCKED/NOT RUN; one Overall row; Overall PASS iff all gates PASS; Overall row contains SELF-REVIEW ONLY); needles = lines 43-44 (bare substring presence of F7..F12, OPEN, "not VERIFIED", "not done").

## 3. Method and its limits (stated plainly)
- The checker takes 11 arguments, including an evidence directory, a git repository, a bundle zip and other files that are not in the package. The unmodified checker therefore cannot run to a PASS exit here: with dummy arguments it prints its early output, then dies at line 69 (zipfile) - exit 1 for every row, the unmodified baseline included (88 of 90 rows end in BadZipFile at line 69; two rows crash earlier, see minor findings). The exit status of the full run cannot discriminate between variants. NOT RUN: the checker's tail (lines 45-167, incl. the live `git ls-remote` at lines 161-164, which I did not execute).
- Instruments (both run with `python3 -I`, proxies unset, GIT_CONFIG_GLOBAL/SYSTEM=/dev/null; no network, none needed): (FULL) the unmodified copy with dummy arguments; (GATES) `front_gates.py` = lines 1-44 of the copy verbatim (cmp verified, evidence/front_gates_identity.txt) plus 2 appended lines (print, exit by `ok`). Verdict per row = GATES exit status (0 = checker accepts the status handling, 1 = rejects). The FAIL lines before "ids cited:" in FULL equal the FAIL lines of GATES in 90 of 90 rows. For every FALSE PASS row except T15 the FULL stdout is byte-identical to the baseline FULL stdout (evidence/I_full_vs_baseline.txt), so nothing else reachable in the checker reacted to my mutation. DERIVED (not observed): by reading, lines 69-167 test other substrings of the text (cited hashes, "9,007", the scenario table, `bsha in txt`, "must not be applied") and not the status wording, so I expect the complete checker to give the same verdict as GATES; I could not confirm it.
- Expectation per row is my reading of the brief. Rows where the brief does not decide (pure whitespace changes, status text quoted or hidden by markdown structure) are marked "undecided"; they are not counted as substantive.
- 90 variants were built from the addendum copy by one script and run in one loop (scripts/run_variants_I.py); raw output per row in evidence/.

## 4. Criteria table
| Criterion | Status | Evidence | Reasoning |
|---|---|---|---|
| I - how check_addendum4.py handles the governing status line, and robustness against the weaknesses named in the brief | **FAIL** | evidence/I_summary.tsv, I_summary_table.md, <ID>.out/.rc; findings I-1, I-2, I-3 | All 30 alterations of the governing line or of the last line that the contract says must fail were rejected (one character, dash and dot variants, case, whitespace, tab, NBSP, homoglyph, CLOSED, deletion). But 18 variants with a contradicted, masked or duplicated status were accepted (FALSE PASS): conflicting or ambiguous status statements elsewhere, an altered governing line hidden by an intact copy in a code fence or comment, and conflicting gate tables. Every required check ran. |

## 5. What the checker catches and does not catch (observed)
Catches (every case rejected): governing line deleted or altered by one word/character/dash/dot/case/space/tab/NBSP/homoglyph/hard line break (S2); last line deleted, altered, followed by other text, zero-width-space line, tab/homoglyph/zero-width variant (S1); gate table absent, unknown or lower-case status words, Overall PASS with a non-PASS gate, Overall not PASS with all gates PASS, missing or duplicate Overall row, missing SELF-REVIEW ONLY, status only in a heading with no table.
Does not catch (observed FALSE PASS): see section 7. It tests that the required text is present once or more somewhere; it never tests that nothing else in the document contradicts it, that it is the only governing line, or that it is a live statement rather than quoted, fenced, commented or struck-through text. Only the first gate table is read.

## 6. All variants tested (GATES verdict; FULL run agrees on every FAIL line)

| ID | Variant (mutation of the addendum text) | Contract expects | Checker | Classification | Check that fired |
|---|---|---|---|---|---|
| B00 | unmodified addendum | PASS | PASS | correct PASS | - |
| A01 | GOV line deleted (last line intact) | FAIL | FAIL | correct FAIL | S2 substring |
| A02 | GOV: G4 OPEN -> G4 CLOSED | FAIL | FAIL | correct FAIL | S2 substring |
| A03 | GOV: High -> Low | FAIL | FAIL | correct FAIL | S2 substring |
| A04 | GOV: freeze-blocking -> not freeze-blocking | FAIL | FAIL | correct FAIL | S2 substring |
| A05 | GOV: NOT DECLARED -> DECLARED | FAIL | FAIL | correct FAIL | S2 substring |
| A06 | GOV: HELD -> RELEASED | FAIL | FAIL | correct FAIL | S2 substring |
| A07 | GOV: Cyrillic O (U+041E) in OPEN | FAIL | FAIL | correct FAIL | S2 substring |
| A08 | GOV: hyphen in freeze-blocking -> U+2011 | FAIL | FAIL | correct FAIL | S2 substring |
| A09 | GOV: freeze-blocking -> 'freeze blocking' | FAIL | FAIL | correct FAIL | S2 substring |
| A10 | GOV: middle dots -> U+2022 bullet | FAIL | FAIL | correct FAIL | S2 substring |
| A11 | GOV: middle dots -> U+22C5 dot operator | FAIL | FAIL | correct FAIL | S2 substring |
| A12 | GOV: middle dots -> ASCII hyphen | FAIL | FAIL | correct FAIL | S2 substring |
| A13 | GOV: en dash -> hyphen-minus (G5-G8) | FAIL | FAIL | correct FAIL | S2 substring |
| A14 | GOV: en dash -> em dash | FAIL | FAIL | correct FAIL | S2 substring |
| A15 | GOV: en dash -> U+2212 minus | FAIL | FAIL | correct FAIL | S2 substring |
| A16 | GOV: all lower case | FAIL | FAIL | correct FAIL | S2 substring |
| A17 | GOV: 'Freeze Readiness' capital R | FAIL | FAIL | correct FAIL | S2 substring |
| A18 | GOV: double space after OPEN | FAIL | FAIL | correct FAIL | S2 substring |
| A19 | GOV: NBSP (U+00A0) instead of space in 'Freeze readiness' | FAIL | FAIL | correct FAIL | S2 substring |
| A20 | GOV: two spaces after the bold prefix | FAIL | FAIL | correct FAIL | S2 substring |
| A21 | GOV: status hard-wrapped (newline after 'freeze-blocking.') | undecided | FAIL | undecided by brief (checker FAIL) | S2 substring |
| A22 | GOV: two spaces after final period of the status (before 'No implementation') | PASS | PASS | correct PASS | - |
| A23 | GOV: prefix 'Governing status, unchanged:' (singular) | FAIL | FAIL | correct FAIL | S2 substring |
| A24 | GOV: prefix without bold markers | undecided | FAIL | undecided by brief (checker FAIL) | S2 substring |
| A25 | GOV: all wrong (G4 CLOSED / Low / not freeze-blocking / RELEASED / DECLARED) | FAIL | FAIL | correct FAIL | S2 substring |
| L01 | last line deleted | FAIL | FAIL | correct FAIL | S1 last line |
| L02 | last line: G4 CLOSED | FAIL | FAIL | correct FAIL | S1 last line |
| L03 | last line + trailing space | undecided | FAIL | undecided by brief (checker FAIL) | S1 last line |
| L04 | last line with leading space | undecided | FAIL | undecided by brief (checker FAIL) | S1 last line |
| L05 | CRLF line endings throughout | PASS | PASS | correct PASS | - |
| L06 | CRLF on the last line only | PASS | PASS | correct PASS | - |
| L07 | extra non-empty line 'G4 CLOSED.' after the last line | FAIL | FAIL | correct FAIL | S1 last line |
| L08 | blank and whitespace-only lines after the last line | PASS | PASS | correct PASS | - |
| L09 | zero-width-space-only line after the last line | FAIL | FAIL | correct FAIL | S1 last line |
| L10 | form feed (U+000C) appended to the last line | undecided | PASS | undecided by brief (checker PASS) | - |
| L11 | no newline at end of file | PASS | PASS | correct PASS | - |
| L12 | empty file | FAIL | FAIL | correct FAIL | headings, then crash |
| L13 | last line duplicated (two identical final lines) | PASS | PASS | correct PASS | - |
| L14 | last line inside an unclosed code fence (``` before it) | undecided | PASS | undecided by brief (checker PASS) | - |
| L15 | last line inside an unclosed HTML comment (<!-- before it) | undecided | PASS | undecided by brief (checker PASS) | - |
| L16 | last line as a blockquote ('> ' prefix) | undecided | FAIL | undecided by brief (checker FAIL) | S1 last line |
| L17 | UTF-8 BOM at start of file | PASS | PASS | correct PASS | - |
| L18 | last line: Cyrillic O in OPEN | FAIL | FAIL | correct FAIL | S1 last line |
| L19 | last line: zero-width space inside | FAIL | FAIL | correct FAIL | S1 last line |
| L20 | last line + trailing NBSP | undecided | FAIL | undecided by brief (checker FAIL) | S1 last line |
| A26 | GOV: tab instead of space in 'G5–G8 HELD' | FAIL | FAIL | correct FAIL | S2 substring |
| L21 | last line hard-wrapped over two lines | undecided | FAIL | undecided by brief (checker FAIL) | S1 last line |
| L22 | last line: tab instead of space | FAIL | FAIL | correct FAIL | S1 last line |
| T01 | gate table deleted | FAIL | FAIL | correct FAIL | gate table |
| T02 | gate table header renamed to 'Gate / Result' | FAIL | FAIL | correct FAIL | gate table |
| T03 | a gate status 'PASSED' | FAIL | FAIL | correct FAIL | gate table |
| T04 | a gate status 'Pass' | FAIL | FAIL | correct FAIL | gate table |
| T05 | one gate FAIL, overall PASS | FAIL | FAIL | correct FAIL | gate table |
| T06 | one gate FAIL, overall FAIL with SELF-REVIEW ONLY (internally consistent) | PASS | PASS | correct PASS | - |
| T07 | overall row without 'SELF-REVIEW ONLY' | FAIL | FAIL | correct FAIL | gate table |
| T08 | overall row removed | FAIL | FAIL | correct FAIL | gate table |
| T09 | two overall rows | FAIL | FAIL | correct FAIL | gate table |
| T10 | all gates PASS, overall FAIL | FAIL | FAIL | correct FAIL | gate table |
| T11 | overall status 'PASS (provisional)' | FAIL | FAIL | correct FAIL | gate table |
| T12 | table removed, status only in a level-3 heading '### Overall: PASS' | FAIL | FAIL | correct FAIL | gate table |
| T13 | second gate table (gate FAIL, overall PASS) after the real one | FAIL | PASS | **FALSE PASS** | - |
| T14 | orphan row 'Late gate FAIL row' after a blank line below the table | FAIL | PASS | **FALSE PASS** | - |
| T15 | fenced all-PASS decoy table first; real table inconsistent (FAIL gate, overall PASS) | FAIL | PASS | **FALSE PASS** | - |
| T16 | separator row with alignment colons (:---, :---:) | PASS | FAIL | false FAIL | gate table |
| T17 | overall row indented by one space | undecided | FAIL | undecided by brief (checker FAIL) | gate table |
| T18 | gate row named 'overall ...' lower-case replaced; no 'Overall' row left | FAIL | FAIL | correct FAIL | gate table |
| T19 | malformed one-cell row 'stray' directly after the overall row | undecided | FAIL | undecided by brief (checker FAIL) | crash (IndexError) |
| C01 | body sentence 'G4 CLOSED.' appended to result item 7 | FAIL | PASS | **FALSE PASS** | - |
| C02 | body sentence 'Freeze readiness DECLARED.' appended to item 7 | FAIL | PASS | **FALSE PASS** | - |
| C03 | item 7 rewritten: G4 CLOSED / Low / not freeze-blocking / RELEASED / DECLARED | FAIL | PASS | **FALSE PASS** | - |
| C04 | second, conflicting governing line inserted after the real one | FAIL | PASS | **FALSE PASS** | - |
| C05 | second, conflicting governing line inserted before the real one | FAIL | PASS | **FALSE PASS** | - |
| C06 | conflicting status as a blockquote after the real line | FAIL | PASS | **FALSE PASS** | - |
| C07 | conflicting status as a level-3 heading '### G4 CLOSED' | FAIL | PASS | **FALSE PASS** | - |
| C08 | conflicting row 'G4 CLOSED' in the findings table | FAIL | PASS | **FALSE PASS** | - |
| C09 | retraction after the required text on the GOV line itself | FAIL | PASS | **FALSE PASS** | - |
| C10 | 'Retracted: ' before the GOV line on the same line | FAIL | PASS | **FALSE PASS** | - |
| C11 | GOV line struck through (~~...~~), conflicting line below it | FAIL | PASS | **FALSE PASS** | - |
| C12 | identical duplicate of the GOV line elsewhere | PASS | PASS | correct PASS | - |
| C13 | 'G4 CLOSED' only inside a fenced code block (quotation) | undecided | PASS | undecided by brief (checker PASS) | - |
| C14 | adjacent: finding F7 status OPEN -> CLOSED (not the governing line) | undecided | PASS | undecided by brief (checker PASS) | - |
| C15 | ambiguous hedge: 'Whether G4 remains OPEN is undecided; G4 may be CLOSED.' | FAIL | PASS | **FALSE PASS** | - |
| M01 | line 5 altered to G4 CLOSED; intact required line inside a fenced code block elsewhere | FAIL | PASS | **FALSE PASS** | - |
| M02 | line 5 altered to G4 CLOSED; intact required line inside an HTML comment elsewhere | FAIL | PASS | **FALSE PASS** | - |
| M03 | line 5 deleted; required line only as a blockquote elsewhere | undecided | PASS | undecided by brief (checker PASS) | - |
| M04 | line 5 deleted; required line only inside a table cell elsewhere | undecided | PASS | undecided by brief (checker PASS) | - |
| M05 | line 5 deleted; required line only inside an HTML comment (final line still asserts the status) | undecided | PASS | undecided by brief (checker PASS) | - |
| M06 | line 5 deleted; required line only in a level-3 heading | undecided | PASS | undecided by brief (checker PASS) | - |
| M07 | line 5 replaced by conflicting line; real required line only inside an HTML comment (no visible status) | FAIL | PASS | **FALSE PASS** | - |

Totals (90 rows): correct FAIL 43; correct PASS 10; **FALSE PASS 18**; false FAIL 1; undecided by brief 18 (checker PASS 9: L10, L14, L15, C13, C14, M03, M04, M05, M06; checker FAIL 9: A21, A24, L03, L04, L16, L20, L21, T17, T19). In the table, "GOV" is line 5, `**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This addendum changes no repository, no pull request and no decision item.`; "last line" is the final line of the file, the status string alone.

## 7. Findings register (substantive)

### I-1 FALSE PASS: conflicting, contradicting or ambiguous status text elsewhere is not detected
1. Id: I-1. 2. Location: check_addendum4.py line 24-26 (S1, S2) and 43-44; nothing in the file scans the rest of the text for other status statements. 3. Conditions: the addendum copy with GOV and the last line intact, plus any added conflicting text. 4. Commands: `python3 scripts/run_variants_I.py <W>` (rows C01-C11, C15); one row by hand: `python3 -I work/front_gates.py work/variants/C01.md work/dummy_ev work/dummy_repo work/dummy_bundle.bin work/rev3.patch work/rev2_stub.txt work/addendum_base.md work/addendum_base.md work/addendum_base.md work/addendum_base.md work/addendum_base.md`. 5. Output (C01.out): `last non-empty line ok: True`, all 8 gates PASS, `non-PASS gates: [] | overall: ['PASS']`, `FRONT-GATES RESULT: ok`, exit 0; the diff against the baseline is one appended sentence ` G4 CLOSED.` in result item 7. FULL stdout for C01 is byte-identical to the baseline FULL stdout. Same acceptance for: ` Freeze readiness DECLARED.` (C02); item 7 rewritten to G4 CLOSED / Low / not freeze-blocking / RELEASED / DECLARED (C03); a second, conflicting governing line before or after the real one (C04, C05); `> G4 CLOSED. Freeze readiness DECLARED.` as blockquote (C06); `### G4 CLOSED` heading (C07); a findings-table row `G4 | CLOSED` (C08); a retraction appended on the GOV line itself after the required text (C09); `Retracted: ` in front of the GOV line (C10); the GOV line struck through with ~~ and a conflicting line below it (C11); a hedge "Whether G4 remains OPEN is undecided; G4 may be CLOSED." (C15). 6. Expected: the brief's own example "G4 CLOSED" and conflicting or ambiguous status text should be rejected; actual: accepted (exit 0, no FAIL line). 7. Severity: Medium for the tooling (high for the property it is meant to protect: the governing statuses). The checker gives no assurance that the document does not contradict G4 OPEN; it only proves that the required strings are present. Nothing else in the package is changed by this. 8. OBSERVED (12 of 12 rows). 9. Limits: verdict from the instrument that runs lines 1-44; the complete checker cannot run with the package contents (section 3); the claim that the tail does not react is DERIVED. 10. Substantive: yes (false PASS under the item I contract).

### I-2 FALSE PASS: an altered or replaced governing line is accepted if an intact copy exists anywhere (code fence, comment)
1. Id: I-2. 2. Location: line 26, `"**Governing statuses, unchanged:** " + want not in txt` - plain `in` on the whole text, with no position, count, or structure rule. 3. Conditions: line 5 changed, an intact copy of the required line placed elsewhere. 4. Commands: rows M01, M02, M07 of the same script. 5. Output: M01 (line 5 = `... G4 CLOSED · High ...`; the intact line inside a ``` fence after section 1): `last non-empty line ok: True`, `non-PASS gates: [] | overall: ['PASS']`, exit 0; M02 (intact copy in an HTML comment): same; M07 (line 5 replaced by a conflicting line `G4 CLOSED · Low · not freeze-blocking ... DECLARED.`, the intact line only inside `<!-- ... -->`): same; FULL stdout byte-identical to the baseline. 6. Expected: the visible governing line says G4 CLOSED; this must fail. Actual: accepted. 7. Severity: Medium (an edit can be masked by pasting the old line into a fence or a comment). 8. OBSERVED (3 of 3). 9. As I-1. 10. Substantive: yes.

### I-3 FALSE PASS: only the first gate table is read; a second table, an orphan row or a decoy table is not seen
1. Id: I-3. 2. Location: lines 29-34: `in_gate` is set by the first `| Gate | Status` line and the loop `break`s at the first line not starting with `|` (line 32), which ends the whole scan. 3. Conditions: a second table, a row below a blank line, or a fenced decoy table before the real table. 4. Commands: rows T13, T14, T15. 5. Output: T13 (second table `Decoy gate | FAIL`, Overall PASS, after the real table): `non-PASS gates: [] | overall: ['PASS']`, exit 0, FULL stdout identical to the baseline; T14 (`| Late gate | **FAIL** |` after a blank line below the table): identical; T15 (a fenced all-PASS decoy table above the real table, whose gate F9... is FAIL with Overall PASS): the output lists only `PASS Decoy` and `PASS Overall result`, `FRONT-GATES RESULT: ok`, exit 0. 6. Expected: an inconsistent or conflicting gate table (FAIL gate with Overall PASS) must be rejected; actual: accepted because only the first table is evaluated. 7. Severity: Medium-low (needs a deliberately placed table; an honest edit would not do it). 8. OBSERVED (3 of 3). 9. As I-1. 10. Substantive: yes.

Incidental findings per the acceptance contract in the verification block (false PASS of the REV3 block, printed credential or URL): none observed; the REV3 block was not run in this stage and no credential, token or URL appeared in any output of this stage (dummy values only).

## 8. Minor findings and undecided observations (not substantive)
- m1 false FAIL (T16): a separator row with alignment colons `|:---|:---:|` is read as a gate row; output "status word not allowed" and "overall PASS with a non-PASS gate".
- m2 uncaught exceptions: an empty file (L12) raises IndexError at line 24 and a one-cell table row such as `| stray |` (T19) raises IndexError at line 34, i.e. traceback and exit 1, with no FAIL line. Rejection by exit status only.
- m3 inconsistent whitespace policy: CRLF line endings (L05, L06) and a BOM (L17) are accepted (`open(..., encoding="utf-8")` normalises newlines), blank and whitespace-only trailing lines are accepted (L08), but a trailing space (L03), a leading space (L04), a trailing NBSP (L20) and a hard-wrapped status (L21, A21) are rejected; a form feed (U+000C) appended to the last line is accepted (L10, `splitlines()` treats it as a line break). No case in which a changed status word passes.
- m4 structure-blind, undecided by the brief: the required last line inside an unclosed code fence (L14) or an unclosed HTML comment (L15); the required GOV line as the only copy in a blockquote, table cell, heading or HTML comment (M03-M06); a "G4 CLOSED" quotation in a code fence (C13); finding F7 changed to CLOSED (C14, outside the governing line). All accepted by the checker.
- m5 identical duplicates (C12, L13) accepted; no count of governing lines.
- m6 the needle tests (lines 43-44) are bare substring tests; "OPEN" is satisfied by any occurrence of the word.
- m7 the unmodified checker cannot be run to completion from the package alone (section 3); its documented usage needs 11 inputs of which 8 are not in the package.

## 9. Unreviewed, not run, not verified
- Items A to H: not assessed (other stages). The REV3 block and patch were not read for this stage beyond using rev3.patch as an argument file.
- Checker lines 45-167 (evidence ids, hashes, bundle manifest, scenario table, patch hunks, claims table, live `git ls-remote` of lines 161-164): not run; the live-state lines would contact `origin` (network); not exercised.
- A full-checker verdict for each variant: not obtainable (section 3).
- Invalid UTF-8 input, very large files, other Python versions (only 3.13.18), Windows paths: NOT RUN.
- More exotic contradiction forms (other languages, images, base64) not tried; the list of FALSE PASS rows is a lower bound on what is not caught, not a complete list.
- The expectation column is my reading of the brief; the 18 undecided rows need an owner decision on what the checker should do with fenced, quoted or hidden status text.

## 10. Environment
Python 3.13.18 (`python3 -I` for every run that reads package or variant files); GNU bash 5.2.21(1)-release; git 2.43.0 (the checker calls git only for 40-hex ids; the working directory was an empty non-repository; no ls-remote was reached); Linux 6.18.44-fc-v470 x86_64. Proxy variables unset for every run; no network traffic.

## 11. Declaration
I am a Claude model sub-agent (Sonnet 5.5, claude-sonnet-5-5) in an independent context; same model family as the author; not a human. Tools: shell (bash, python3), file read/write/edit. Phase A blinded: I read only the package, the common preamble and my prompt; I did not open any other scratchpad directory, any repository, any author report or evidence record outside the package. Contact with the author's results: none. The session context contained automatically attached project and memory text (project instructions, a memory listing) which I did not use or read further; it held no results of this review series.

## 12. Reproducibility (all in stage_S7/)
- `bash scripts/reproduce_I.sh <NEW_EMPTY_DIR>`: copies the zip, checks the full SHA-256 and SHA256SUMS, extracts, copies out the checker and addendum, builds `work/front_gates.py` (lines 1-44 + 2 lines), and runs `python3 scripts/run_variants_I.py <DIR>` (90 rows, both instruments, `<DIR>/evidence/I_summary.tsv`). I ran it into `repro_check/`; the first ten columns of its I_summary.tsv are identical to evidence/I_summary.tsv.
- Files: scripts/run_variants_I.py, scripts/reproduce_I.sh, evidence/INDEX.txt, evidence/PROGRESS_I.txt, evidence/I_summary.tsv, evidence/I_summary_table.md, evidence/I_full_vs_baseline.txt, evidence/front_gates_identity.txt, evidence/<ID>.{out,err,rc} and <ID>.full.{out,err,rc} for 90 IDs, work/variants/<ID>.md.

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
