# Addendum 6 to the Consolidated Evidence Report — the fifth reviewer launch left a partial report with two findings against revision 3, and I reproduced them — 2026-11-08

Addendum to Addendum 5 (`CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_5_INDEPENDENT_REVIEW_BLOCKED_2026-11-07.md`, sha256 `e3dd62cf8d6c6cd714367315d078e53dbc0fae899172c566c4894a608f2a6908`; delivered in `g4_addendum_5_delivery_all_files_2026-11-07.zip`, sha256 `4c27f3df727b7aec120dda822e624ba38c18e5467d50f8b8c4c0ce59cc67e099`). Addendum 5 and everything before it are not edited. Evidence: `I76`–`I79` in `g4_addendum_6_evidence_I76-I79.zip` (sha256 `2408280ca34eac9202ec04f29821035c1d9f7a0ea42a35afaace0b64ce6605b3`, delivered beside this addendum). `I80` and `I81` are the author's mechanical checks of this addendum and are delivered as separate files because they check the text that cites the bundle's hash: `I80` passed on the first draft; `I81` is the rerun on the final text, after the description of what I read in the reviewer's directory was made precise. Neither replaces the other. The reviewer launch ran on 2026-11-07 (about 22:22 to 22:35 UTC); everything else on 2026-11-08.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This addendum changes no repository, no pull request and no decision item.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what a text says, not reproduced by me; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **The fifth launch of the independent-context reviewer ran for about 13 minutes before the plan's usage limit ended it** [OBSERVED, I76, I78]. It did not finish. Its running report is marked `STATUS: IN PROGRESS`, so **the review is not complete** and I do not present it as one. Items it did not report: C, D, F, the prose check in G, H and I.
2. **The partial report contains two findings against revision 3** [REPORTED, I78], which I reproduced in part on loopback [OBSERVED, I77]:
   - **F14, false PASS (item B).** The identity check of the block accepts `https://127.0.0.1:18443?@github.com/1h0lde4/ocbrain-v4.1` and `https://evil.example#@github.com/…` as the canonical repository, while git and libcurl connect to the other host.
   - **F15, secret output (item E).** The block's own run prints a token that is in the `origin` URL, through git's own error messages.
3. **Under the rule in the pasted decision, a substantive finding stops the change.** I started no fourth rewrite, applied nothing, and F7 stays OPEN. Revision 3 stays PROPOSED and **is not acceptable as it stands**.
4. **Part of my earlier text overstated.** The sentence "credentials in the URL are ignored and never printed" in the patch prose, and the same claim in the block's comment, are not true for the whole run (section 4).
5. **Nothing was applied, committed or pushed** [OBSERVED, I79]: `HEAD` and the remote REV2 tip are still `d963daa502de4220411d0d0c2f19f67b3ec2682b`, the clone is clean, PR #90 is unchanged.

## 2. What the fifth launch produced

| Fact | Value | Evidence |
|---|---|---|
| Start and last write | 2026-11-07 about 22:22 and 22:35 UTC | I76 |
| End | rate-limit error, HTTP 429, "5-hour limit", no final message | I76 |
| Report file as left | 2,367 bytes, first line `STATUS: IN PROGRESS` | I78 |
| What it records | package hash verified; block in the patch equals the tested block; patch applies; three hunks only; item A; item B; item E | I78 |
| Not recorded | items C, D, F, the claim-by-claim check in G, H, I | I78 |

The reviewer is an independent-context sub-agent of the same model family as me, working only from the package, which carries none of my results. It is not a human review. I read its report file, listings of its directories and one stray 3-byte file (`handoff.md`, containing `f1`); I did not read its other scratch files.

## 3. The findings and what I reproduced

| ID | Finding | Class | What the reviewer reports | What I observed (I77) | Not reproduced by me |
|---|---|---|---|---|---|
| **F14** | The block's line 15 cuts the URL authority only at `/`. A `?` or `#` before an `@github.com` is read as user information, so the host test sees `github.com`. | FALSE PASS | With an origin `https://127.0.0.1:18443?@github.com/1h0lde4/ocbrain-v4.1`, a loopback TLS server with identical history, and only `T=` and `H=` changed, the block printed `PASS` and exited 0; the server log shows git contacted 127.0.0.1. | Line 15 applied unchanged accepts the `?@` form and the `#@` form as canonical and rejects the `/@` form and the `/x?@` form (R1). For the `?@` form git contacts `127.0.0.1` port 1, not `github.com` (R2). | The printed `PASS` itself. I did not build the TLS server. Also the reviewer's `\@` and `%2f@` forms. |
| **F15** | The block does not silence git's own messages. Git prints a user name or query string from the URL in its errors. | SECRET OUTPUT | With a token as the user name and a server answering 401, the output contains `could not read Password for 'https://TOKEN@github.com'`; with a token in a query string, `unable to access '…?token=TOKEN/'`. | Block run end to end: a token in a query string, dead loopback port, 3 output lines contain it (R3); a token as the user name, local server answering 401, 3 lines contain it (R4); git alone prints it (R5). Control: a string absent from the output matches 0 lines. | The canonical `https://TOKEN@github.com/…` form against a 401 from GitHub. My runs used loopback `http`, and in those runs the block's identity check failed before git printed. |

**[DERIVED] Why each matters.**

- **F14.** Revision 3 was written so that it prints `PASS` only for the canonical repository. A crafted `origin` defeats that. The attacker model is narrow (someone must set the clone's `origin` to such a URL), and the brief says the check guards against an accidental wrong remote, not a hostile environment. It is still a reproduced way to get a false `PASS`, which the brief defines as substantive.
- **F15.** A token in the URL appears in the terminal output whenever git needs a password and has none. That happens for a revoked or wrong token, which is when someone is most likely to paste the output into a chat or an issue. The `FAIL` line of the block does not print the URL, as I wrote; git's lines do.

**Also confirmed by the reviewer** [REPORTED, I78]: revision 2 gives a false PASS in the six cases of item A and revision 3 prints FAIL in all six. This matches my own earlier runs (Addendum 4, `I51`, `I60`); I did not repeat them here.

## 4. Correction of my earlier statements

- The block's comment on line 15 ("credentials in the host part are dropped, so they are neither compared nor printed") and the patch prose ("credentials in the URL are ignored and never printed") are accurate for the `FAIL` and `PASS` lines the block writes and **not** for the whole run, because of F15.
- My leak tests in Addendum 4 (`I59`, 0 leaks in 23 cases and an end-to-end run on dead ports) covered the shapes I tried: a user name with a password, ssh forms, and dead ports. They did not cover a token as the user name against a server that answers 401, or a token in a query string. The result "0 leaks" was true for those shapes and should not have been read as a general result.

## 5. Gates and open findings

Exactly one status per gate, for this addendum's scope (acting on the fifth reviewer launch under the stopping rule).

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Outcome of the fifth launch recorded with its report as left | **PASS** | I76, I78 | section 2 |
| One independent-context review of revision 3 completed | **BLOCKED** | I76, I78 | ended by the usage limit; items C, D, F, G (prose claims), H, I not reported |
| Mechanism of F14 and F15 reproduced by the author on loopback | **PASS** | I77 | R1 to R5; the controls behaved as expected |
| The printed PASS of F14 reproduced by the author | **NOT RUN** | I77 | needs a TLS git server; reported by the reviewer only |
| Revision 3 meets its own contract (no substantive finding) | **FAIL** | I77, I78 | F14 and F15 |
| No ref, commit, working file, pull request or remote changed | **PASS** | I79 | `HEAD` and remote tip `d963daa5…`, status 0, PR #90 open and draft, 3 commits, 7 files, head `9407db5a…` |
| G4/freeze invariants | **PASS** | section 1 | statuses stated unchanged |
| **Overall result (this addendum's scope)** | **FAIL** | | revision 3 fails; the stopping rule applies, so nothing else is done before your decision |

| Finding | Status | Note |
|---|---|---|
| F1–F5 (Addendum 1) | **OPEN** | pushed wording residuals |
| F7 (Addendum 2) | **OPEN** | closure needs a verification block that passes independent review, an authorized push and a run from a fresh clone of the canonical URL |
| F8 (Addendum 3) | **OPEN** | the P1d of Addendum 2 must not be applied |
| F9–F12 (Addendum 4) | **FIXED in the proposal; not VERIFIED** | revision 3 addresses them in the tested scenarios; the proposal itself now carries F14 and F15 |
| F13 (Addendum 5) | **FIXED in tooling (v2); not VERIFIED by anyone else** | unchanged |
| **F14** (new, from the reviewer) | **OPEN** | mechanism reproduced; printed PASS reported only |
| **F15** (new, from the reviewer) | **OPEN** | reproduced on loopback `http`; canonical `https` form derived |
| F6 (Addendum 1) | not changed | metadata only |

## 6. Decisions for you

I stopped, as the rule you approved requires. The choices are yours:

1. **Revision 3.** (a) Leave it as it is (PROPOSED, not applied). The pushed REV2 handoff keeps its current step 2, which Addendum 4 showed to be weaker. (b) Allow one bounded correction limited to F14 and F15 and the prose claims, with the same rule as before: one independent review afterwards, no automatic further rewrite, stop on a substantive finding.
2. **Before any correction, finish the review.** The fifth launch reached only items A, B and E and the patch checks in 13 minutes. A correction made now would be tested against two findings only; the remaining items C, D, F, G (prose claims), H and I are unreviewed. The package is unchanged and ready. I can start a sixth launch here when you say so, or you can give the package to a human or another assistant.
3. **Checker:** use the stronger status checker (v2) for future addenda, or keep v1.
4. **D-1…D-11, the next-session entry point and the ledger wording** stay with you; **the PR #90 rebase** is the PR owner's call.

Nothing was pushed in this step; rollback of earlier pushes is unchanged (section 7 of Addendum 1).

## 7. Limits

- The review is partial and from one independent-context sub-agent of my own model family. Its report is input to verification, not evidence of a finding. What I list as observed I ran myself on loopback; I did not run the reviewer's scripts.
- Tested with git 2.43.0 and curl 8.5.0 (libcurl/8.5.0). Other versions may print differently.
- The false PASS of F14 depends on a server that serves a matching history at the other host; that step is reported by the reviewer and was not rebuilt here.
- R4 and R5 use a local HTTP server. I did not send a dummy token to `github.com`, so the canonical `https` form of F15 is derived from git's behavior, not observed.
- The reviewer also lists `\@` and `%2f@` look-alike forms; whether libcurl reaches the other host for them is not tested.
- Not examined: CI, the chain of custody of the REV3 ZIP and the user-side `handoff(1).md`, and the reviewer's other scratch files.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
