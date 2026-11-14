# Session 2 addendum — Stage S6 result (2026-11-14)

**What this adds.** The Phase A stage S6 (criteria F, G part 4, H) of the staged review of REV3, on top of the unchanged bundle one directory up. Nothing in `../handoff.md` or its `SHA256SUMS.txt` was edited. Files here are covered by `SHA256SUMS_session2.txt` (this note included).

| File | What it is |
|---|---|
| `REPORT_S6.md` | The S6 reviewer's final report, extracted byte-for-byte from the conversation record with `tools/extract_handback.py` (26,922 bytes, sha256 `f8968821a01aa6bdb716babc193adcac806a8a9fbf17786b9ef9ff6b92eb4d58`). Not edited. |
| `REPORT_S6_prior_1.md`, `REPORT_S6_prior_2.md` | The reviewer's earlier provisional stubs (package integrity only, all criteria NOT RUN). Kept for the record; not results. |
| `stage_S6_scripts_and_evidence.zip` | The reviewer's scripts, row tables and raw per-row output (503 entries). Excluded: `work/` (throw-away synthetic repositories), the package copies, and `tls/` (a throw-away self-signed key). |
| `author_spot_check/` | My own independent re-runs of three S6 findings (below): script, output, the loopback 401 server used. |

## How S6 ran
Two launches of a fresh reviewer were cut off by the account's 5-hour usage limit (the first after ~6 min with only the package-integrity step done, the second after ~12 s). A third run resumed the second agent (`a3bdfa536086985ae`) with `SendMessage`; it was cut off once more after about 13 minutes, with F, H and G(4) rows and summaries already on disk, and a fourth resume produced the final report. Limit resets seen: 2pm, 9:10pm, 4:10am UTC. The reviewer is an independent-context sub-agent of the same model family as the author, not a human (same limitation as S1, S2, S4, S5).

## Result (as reported by the reviewer: [REPORTED] unless marked)
| Criterion | Status | Basis |
|---|---|---|
| F | PASS | race is real and unavoidable, prose states it accurately (rows F01–F09); the reviewer notes its "verified" wording depends on the H findings |
| G part 4 | **FAIL** | five patch-prose claims contradicted or overstated (S6-G4-01…05) |
| H | **FAIL** | three reproduced false-PASS mechanisms (S6-H-01…03) |

Interim A–I matrix with S6 added (not final): A PASS · B **FAIL** · C PASS (caveats) · D PASS · E **FAIL** · F PASS · G **FAIL** (G1–3 PASS from S1, G4 FAIL from S6; combined = the worse) · H **FAIL** · I NOT RUN. Phase B (S3, S8) NOT RUN. The overall verdict cannot be PASS; the review is IN PROGRESS, not a completed review.

New findings, stage-local ids (F-numbers are to be assigned in Addendum 7; F1–F15 are not renumbered):
- S6-H-01 false PASS through local `refs/replace/*` (e.g. from `git clone --mirror` of a remote carrying replace refs); S6-H-02 false PASS through `.git/info/grafts`; S6-H-03 false PASS and false FAIL when the block is run from a subdirectory of the clone. In each the block reads local objects, not the remote's real objects.
- S6-G4-01 git itself prints a token that is the URL user name (corroborates F15); S6-G4-02 `#@` / `?@` look-alikes accepted by the identity check while git contacts another host (corroborates F14; the end-to-end printed PASS was not obtained by S6); S6-G4-03 "against the remote branch, not against local objects" contradicted (same evidence as H-01…03); S6-G4-04, S6-G4-05 wording overstated (minor in practice).
- S6-O-01 (incidental, not substantive under the contract): a follow-up commit subject is printed raw, so control characters can disguise output on a terminal.

## What I checked myself ([OBSERVED] by the author, 2026-11-14 ~12:16 UTC, git 2.43.0, synthetic local repositories, loopback only, dummy token only, pristine block with only CANON/T/H substituted; `author_spot_check/spot_check_output.txt`)
- **S6-H-01 reproduced:** remote tip is a two-parent merge commit; clean clone → FAIL (exit 1); clone with `git replace <merge> <single-parent twin>` → `PASS at …`, exit 0, "each a single-parent child"; same clone with `GIT_NO_REPLACE_OBJECTS=1` → FAIL.
- **S6-H-02 reproduced:** same remote with `.git/info/grafts` mapping the merge to its first parent → PASS, exit 0. My first attempt did not reproduce it (my merge kept the side branch's file, which the diff-tree check catches); it reproduces when the merge's tree differs from its first parent only in `handoff.md`, as in the reviewer's rows. The false PASS therefore needs that crafted shape as well as the local graft.
- **S6-G4-01 reproduced in one form:** loopback server answering 401, remote `http://DUMMYTOKEN-xyz@127.0.0.1:PORT/…` → git prints `fatal: could not read Password for 'http://DUMMYTOKEN-xyz@127.0.0.1:PORT': terminal prompts disabled` (http, not https; the reviewer's https rows were not re-run).
- Reviewer footprint audited: nothing changed outside its stage directory; package and preamble hashes intact; REV2, REV3, `main`, PR #90 head and the save branch unchanged on the remote; the reviewer's 19 shell commands contain no curl/wget/pip/npm. That it sent nothing outside loopback is the reviewer's declaration plus the sandbox's proxy-only egress, not something I can prove.

**Not re-run by me (remain [REPORTED]):** F01–F09, the other H rows, S6-H-03 (raw rows H39b/H39c read, not re-executed), S6-G4-02 end-to-end, the https token rows, the G(4) claim table. The safety classifier was unavailable when the hand-back was delivered; the checks above are my substitute.

## Next (unchanged from the handoff, section 17)
S7 (criterion I, may open `optional_item_I/`), then Phase B: S3 (loopback-TLS reproduction of F14 and the HTTPS username-token case) and S8 (comparison with Addendum 6), then consolidate, apply the verdict rule, write Addendum 7. No correction of rev3 is authorized; nothing here proposes one.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
