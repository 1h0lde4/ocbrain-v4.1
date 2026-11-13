# G4 staged-review handoff bundle — preservation copy (2026-11-13)

**What this is.** A byte-for-byte copy of the owner's downloaded bundle `g4_staged_review_handoff_bundle_2026-11-13.zip` (sha256 `329e88db585e68ee1ada64fcf30142d94e1864dfd1e116d91d7724aab9b74bd6`), extracted unchanged into this directory so that the stage reports survive a sandbox reset. `SHA256SUMS.txt` (from the bundle) covers every file here except this note.

**Why a separate branch.** The owner chose on 2026-11-13 to push to a new branch rather than the "immutable" save branch `wip/g4-work-save-checkpoint-nov2026` (tip `8fd8f4da1caf966e550774e8e06bfe13822d55ea`, untouched). The review assignment otherwise forbids commits and pushes; this push is an explicit owner-authorized exception for preservation only.

**What this is not.** It is a WIP checkpoint. It is not a completed review, not a verification result, and not an authority (PROJECT_INSTRUCTIONS 18.4.9). The stage reports inside are [REPORTED]; the raw evidence of S1, S2 and S5 is lost (handoff section 15, Q1). Nothing in the repository's code, tests, configuration or governance documents changed. REV2, REV3, `main` and PR #90 were not modified.

**Status of `handoff.md` inside.** It is byte-identical to the file the owner received, so its hash in `SHA256SUMS.txt` stays valid. Its section 19 ("TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED") described the state when it was written; this commit now holds a copy of it, but it was written and verified outside the repository, and the review it hands over is still IN PROGRESS (S6, S7, S3, S8 not run).

**Checked on resume (2026-11-13 ~09:20 UTC, git 2.43.0).** Remote tips `main` `2491ae469edd6ef1267a14604c4f8f40d698f7ea`, REV2 `d963daa502de4220411d0d0c2f19f67b3ec2682b`, REV3 `9407db5a01acea9684f158caa8107fb71611a102`, save branch `8fd8f4da1caf966e550774e8e06bfe13822d55ea` all equal the handoff; `refs/pull/90/head` is `9407db5a…`. Bundle `SHA256SUMS.txt` 17/17 OK; every hash recorded in handoff section 8 matches. Save branch: 200/200 listed blobs OK; its review package has full sha256 `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`, equal to the assignment's value. Not verified: PR #90 open/draft state (REST API not available without credentials); equality of the preamble's content (only its size, 6,711 bytes, matches). Secret scan over the bundle and the 804 files of the S4 zip: only the synthetic `DUMMYTOKEN-xyz` strings already described in the handoff; no real credential.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
