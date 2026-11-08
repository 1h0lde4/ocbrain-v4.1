# P2 — Conditional erratum text for the REV3 archive-digest discrepancy

**Status: TEMPLATE. NOT APPLICABLE. NOT A PATCH. NOT APPLIED.** It cannot be completed until the actual REV3 ZIP has been hashed and its provenance recorded (report §4, gate "Original ZIP authentication" = BLOCKED). It is a category 2 change (historical erratum/addendum) on files owned by draft PR #90, whose branch is not the declared target of this task. Applying it needs the PR owner's authorization and the measurement below.

Intended location, if later authorized: a new file `docs/reports/g4-fts-correctness/DIGEST_DISCREPANCY_ERRATUM_REV3.md` on the REV3 branch (or wherever the user decides). The four existing digest-bearing files stay unedited; the erratum refers to them.

---

## What was recorded (verified in the live files at `2dd2e7bb05db949a6156266cfa3430c58de09922`, evidence B04)

| Value | String | Recorded in |
|---|---|---|
| A | `f9ee626551e5175a7ba0893c336a77917b8be1b4078903cc6ac5853ad7e509cc` | `IMPLEMENTATION_ROADMAP.md` line 2; `docs/reports/g4-fts-correctness/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` line 16; `docs/reports/g4-fts-correctness/NEXT_SESSION_PROMPT_REV3.md` line 16 |
| B | `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc` | `docs/reports/g4-fts-correctness/fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md` line 4 |

They differ only at zero-based character offset 23 (24th character, one-based): `c` in A, `f` in B. All four files give the size 254,581 bytes.

## What was measured — to be filled from the actual ZIP only

- Artifact: `fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip`
- Path / source / how obtained: `<FILL>`
- Size in bytes: `<FILL>`
- Command and unaltered output: `sha256sum <file>` → `<FILL: full line>`
- Provenance linking these bytes to the packaging run that produced the verification report: `<FILL or "none established">`

## Outcome (delete the rows that do not apply)

| Measured digest | Recorded disposition |
|---|---|
| equals A | The verification report's digest (B) is a transcription error at offset 23. The three other records are correct for the measured bytes. The report is not rewritten; this erratum is the correction. |
| equals B | The roadmap, continuation and next-session prompt digests (A) are a transcription error at offset 23. The verification report is correct for the measured bytes. The roadmap line must be corrected in the same change that merges it. |
| equals neither | The recorded claims and the measured bytes refer to different archives, or the artifact is not the one packaged. Authentication stays unresolved; neither value is endorsed; the provenance of the measured file must be investigated before any edit. |

A digest identifies the bytes measured. It does not by itself show that those bytes are the historically intended artifact, and a passing internal manifest check does not authenticate the archive.

## Unchanged by this erratum

Evidence content, D-1…D-11 (all OPEN), G4 OPEN · High · freeze-blocking, G5–G8 HELD, freeze readiness NOT DECLARED, and the absence of any implementation authorization.
