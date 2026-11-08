# Addendum 3 — 2026-10-31 — Check of an attached review (`cc2745a2-attachment.txt`)

Addendum to `OCBRAIN_G4_FTS_AUTHENTICATION_RECONCILIATION_REPORT.md` (sha256 `a331f6b2b242b2c031b7a84c66ef178d64b940df228545483ed15a0e8abc8318`), Addendum 1 (`cb4cd825b2046c68403a25874da7d203d171e922559392075d2af0aa903f76b6`) and Addendum 2 as delivered (`ADDENDUM_2_2026-10-29_REV3_ZIP_authentication.md`, sha256 `c451cf381ce1b2155212d0f9443d9ca9cb56b8963d6af144023abe9602ba02c0`). None of them is edited. Evidence: `I17`, `I18` (commands, UTC times, exit status, unaltered output; delivered beside this addendum). All reads were local `git`/file reads and read-only GitHub API calls; no file in the repository was changed, and no commit, push, PR update or merge was made.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what a document or the attachment says; **[DERIVED]** a conclusion from observations.

## 1. What was received

An 8,730-byte text file, `cc2745a2-attachment.txt` (sha256 `d33f34430bed688e503ac95eab2f96922a7f4346429fe4a23c3b0f6404e597c5`, I17), sent without instructions. It is the text of another assistant's review of the ZIP-authentication question. It cites records in the user's "ChatGPT Library" (an October 23 ZIP, the verification report, a later copy, an older handoff) that this session cannot reach. It is treated as input to verification, not as evidence: nothing in it was accepted because it was stated.

## 2. Its claims, and what could be checked here

| Claim in the attachment | Checkable here? | Result |
|---|---|---|
| The REV3 verification report has SHA-256 `dd77ace0e170c3367a8423d775a9fd091e4bfa8a813f1a4a6c366f107b15ecb5` and is 3,046 bytes [REPORTED] | The digest and size can be tested against bytes I hold | **Consistent, and new information about the in-repo copy.** The digest is the one REV3 itself records (continuation line 23), so repeating it adds nothing. The size is in no REV3 document. The in-repo copy is 3,045 bytes and ends with `.` (no final newline, no CR); that copy **plus one final LF is 3,046 bytes and hashes to `dd77ace0e170c3367a8423d775a9fd091e4bfa8a813f1a4a6c366f107b15ecb5`** [OBSERVED, I17, I18]. This is the same pattern as the ledger and the fetch header (Addendum 2 §4, I05). That a Library file exists with these properties cannot be checked. |
| The older handoff has SHA-256 `da162e71d6bd0b92650134eceb6af1ecfa430484ac08b179d7aaa48a97fa716d`, matching the hash attributed to `handoff(1).md` [REPORTED] | Only the digest string | The string equals the one in REV3 (continuation line 24) and in my own earlier evidence for the scratch copy [OBSERVED, I17, I18]. It is therefore not independent of what I already had. A Library file with this hash would be a second copy of the same content; the attachment itself says it does not show that the user's own attachment is identical, and I agree. |
| An original REV3 ZIP is retained in the Library (October 23, 10:32:27 UTC, 254,581 bytes), a later copy (October 29, 08:36:13 UTC) is byte-identical, and both hash to Value B [REPORTED] | **No** | **Unverified.** I measured one file, the one attached on 2026-10-29 (Value B, Addendum 2). I cannot see the October 23 copy or compare it. The two timestamps are two systems' records: my file time for the attached copy is 08:36:47Z (Addendum 2 §2), the attachment says 08:36:13 UTC. October 23 10:32:27 UTC is about two minutes after the REV3 branch commit (2026-10-23T10:30:25Z); that fits the story but is not evidence for it. |
| Independent re-check of the ZIP against REV2: B confirmed, 87 entries, 86/86 manifest, no unsafe paths, exactly three differing files, packet and audit-report hashes [REPORTED] | Already measured | Agrees with Addendum 2 §3 and §4 (I02–I04). It is a second report of results I already hold, not new evidence for me. |
| Addendum 1's negative search is not contradicted by Library records [REPORTED] | Yes | Agreed: Addendum 1 stated its scope (the tip tree of one branch) and said what it did not search. |
| Recommended status: qualified PASS; the gate table in the attachment is blank for *Original ZIP authentication*, *Archive integrity and contents* and *Overall result* [REPORTED] | Yes | Noted: the headline is "QUALIFIED PASS", but those three cells are empty in the file I received. |
| "Reconcile against the current main (`16d663ac…`) before applying anything"; P3 touches the roadmap and two REV3 documents [REPORTED] | Yes | **Checked, with a consequence.** `main` is still `16d663ac8449965f774033da46d5063506a772a7`. Value A occurs 0 times in `main`'s `IMPLEMENTATION_ROADMAP.md` (blob `42bf96c745374f963dd27228df3014d7b43b68f0`); the two REV3 documents that record A and the verification report return 404 on `main`; so does `handoff.md` [OBSERVED, I17]. The three records of A exist only on the REV3 branch (PR #90), and P1's target `handoff.md` only on the REV2 branch. P3 therefore applies to PR #90's files, not to `main`; PR #90 is 59 commits behind `main`, and whether to rebase it first is the PR owner's call. |
| P2 should record that the October 23 and October 29 archives are identical [REPORTED] | n/a | **Caution.** That identity is unverified (row 3). P2 as delivered records only what I measured, and says the verification report's own Value B equals the measurement. It should not assert the October 23/29 identity unless that is substantiated. |
| Authorize P2 and P3 together; P1 conditionally after refreshing its target [REPORTED] | n/a | A recommendation by another assistant, not a decision. Authorizing P1, P2 or P3, and choosing a target path, stays with the user. P2 and P3 remain withheld; P3 stays conditional on P2 or an equivalent record. |

## 3. Effect on Addendum 2

- **Gate statuses: no change.** All fourteen gates stay PASS and the overall result stays PASS exactly as Addendum 2 states it, still dependent on the flagged judgment call in its §2. Nothing in the attachment is accepted as a new basis for any status.
- **§4, verification-report row** ("Cannot be checked from the ZIP … the disk original was not supplied"): superseded in part. It still cannot be checked from the ZIP and the disk original is still not seen. But REV3's recorded digest `dd77ace0…` equals the in-repo copy plus one final LF (I17), so the recorded digest is reproducible from bytes in the repository and the only difference from the in-repo copy is one final newline [OBSERVED]. Whether a connector dropped that newline, as REV3 says, remains untestable.
- **§9, "Still unknown or unverified"**: the item "the disk original of the REV3 verification report (`dd77ace0…`)" shrinks to "the file itself was not seen; its recorded digest is reproducible from the in-repo copy plus one final LF". The other items stand.
- **The §2 judgment call**: unchanged. If the Library records the attachment describes are real, an earlier retained copy that is byte-identical to the attached ZIP would strengthen the chain of custody. This session cannot confirm it. What would: attach the October 23 ZIP (a byte comparison is then immediate), or give the `sha256sum` line the user computed for it, with when and where.

## 4. Not changed

D-A, D-B and D-1…D-11 stay with the user and OPEN. The attached review does not settle document authority or any architectural decision. Authenticating an archive is not authenticating the technical conclusions inside it. I15 (the first mechanical check of Addendum 2, kept as a recorded failure) and I16 (the passing rerun) are both kept; neither replaces the other.

## 5. Review

**SELF-REVIEW ONLY.** This addendum was written and checked by its author alone: the new facts are two mechanical observations (I17, I18) that anyone can reproduce from the recorded commands, and nothing was sent to an independent reviewer. An independent re-check can be requested.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
