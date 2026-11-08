# P2 (completed) — Erratum text for the REV3 archive-digest discrepancy

**Status: PROPOSED. NOT APPLIED. NOT AUTHORIZED.** This is the earlier conditional template (`P2_digest_discrepancy_erratum_TEMPLATE_CONDITIONAL.md`) with the measurement now filled in. It is a category 2 change (historical erratum) on files owned by draft PR #90, whose branch is not a target of this work. Applying it, or applying `P3_rev3_digest_value_A_to_B.patch` (which may be applied only together with this erratum, or with a commit message or erratum that records the same four elements: original claim, verified observation, affected file/revision, reason; see "Record required with any correction" below), needs the PR owner's authorization. This document changes no evidence content, no D-1…D-11 item, no G4–G8 status and no freeze status.

Intended location, if later authorized: a new file `docs/reports/g4-fts-correctness/DIGEST_DISCREPANCY_ERRATUM_REV3.md` on the REV3 branch (or wherever the owner decides). P3 corrects the three records of Value A in place and, on its own, would leave no record of the original values; it is therefore conditional on this erratum (or an equivalent record).

---

## What was recorded (verified in the live files at `2dd2e7bb05db949a6156266cfa3430c58de09922`; evidence B04, I09)

| Value | String | Recorded in |
|---|---|---|
| A | `f9ee626551e5175a7ba0893c336a77917b8be1b4078903cc6ac5853ad7e509cc` | `IMPLEMENTATION_ROADMAP.md` line 2; `docs/reports/g4-fts-correctness/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` line 16; `docs/reports/g4-fts-correctness/NEXT_SESSION_PROMPT_REV3.md` line 16 |
| B | `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc` | `docs/reports/g4-fts-correctness/fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md` line 4 |

They differ only at zero-based character offset 23 (`c` in A, `f` in B). All four files give the size 254,581 bytes.

## What was measured (evidence I01, I02)

- Artifact: `fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip`
- Source / how obtained: attached by the user to the session on 2026-10-29 (file time 08:36:47Z) as `b5f4720b-fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip`; the user described it as "the REV3.zip file". Read in place; not modified.
- Size in bytes: 254,581
- Command and unaltered output: `sha256sum <file>` → `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc`
- Exact comparison (Python `==` on the 64-character strings; positions of difference listed): equals Value B; does not equal Value A (differs from A at zero-based offset 23 only).
- Provenance linking these bytes to the packaging run that produced the verification report: the verification report (line 10) says the digest and size "were computed from the generated file", and its Value B equals the measured digest. Independent consistency checks that do not depend on the ZIP's own digest: size equals the recorded 254,581; 87 archive entries and 86 manifest entries as recorded; relative to the earlier bundle (my REV2 bundle, `e6910c0cc6eb1acefaaf369ce46599856a169228a3060b6492687c8fd70b9c3d`), exactly three files differ (`MANIFEST.sha256`, `report/decision_ledger_1d813bd_OPEN.md`, `docs/doc_fetch_quotations_as_returned.md`), as the verification report states; the inner ledger and fetch-header digests (`f6dda8a2515b4e91…`, `f9abc19929958da8…`) equal the values the REV3 continuation records at lines 21–22. Not established: that the attachment is byte-for-byte the file originally generated, beyond the user's description and these consistencies.

## Outcome

The measured digest equals **B**. Recorded disposition:

> The digest recorded in the verification report (B) matches the measured bytes. The three records of A (`IMPLEMENTATION_ROADMAP.md` line 2; the continuation line 16; the next-session prompt line 16) do not match the measured bytes: they differ from the measured digest at offset 23, `c` where the measured digest has `f`. If the measured file is the artifact REV3 describes, A is a transcription error at offset 23. The verification report is not rewritten; this erratum, or the in-place correction P3, records the discrepancy.

A digest identifies the bytes measured. It does not by itself show that those bytes are the historically intended artifact, and a passing internal manifest check does not authenticate the archive; the consistency checks above support, but do not prove, that they are.

## Record required with any correction (task rule: do not silently replace every occurrence of a wrong digest)

| Element | Content |
|---|---|
| Original claim | Value A, `f9ee626551e5175a7ba0893c336a77917b8be1b4078903cc6ac5853ad7e509cc`, recorded as the archive's SHA-256 at `IMPLEMENTATION_ROADMAP.md` line 2, `G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` line 16 and `NEXT_SESSION_PROMPT_REV3.md` line 16; Value B (the other string) is recorded at `fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md` line 4 |
| Verified observation | `sha256sum` of the supplied file (254,581 bytes) = Value B (section "What was measured") |
| Affected file / revision | the three files above and the verification report, REV3 branch `docs/g4-fts-correctness-handoff-rev3-oct2026`, tip `2dd2e7bb05db949a6156266cfa3430c58de09922` |
| Reason | the strings differ only at zero-based offset 23 (one-based 24), `c` in A and `f` in B; if the measured file is the artifact REV3 describes, A is a transcription error |

If P3 is applied, this table (or an equivalent commit message) must travel with it, so that Value A stays recorded as the originally recorded conflicting value even though the three lines are corrected.

## Unchanged by this erratum

Evidence content, D-1…D-11 (all OPEN), G4 OPEN · High · freeze-blocking, G5–G8 HELD, freeze readiness NOT DECLARED, the choice of next-session entry point (D-A), the choice between the REV2 and REV3 ledger wording (D-B), and the absence of any implementation authorization.
