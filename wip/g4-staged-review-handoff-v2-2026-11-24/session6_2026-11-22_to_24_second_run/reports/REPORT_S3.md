STAGE S3: COMPLETE

## 1. Package integrity
- The full SHA-256 of my copy of the zip is 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286. This matches the preamble value.
- All 7 entries of the package's SHA256SUMS.txt are OK.
- I extracted the zip into stage_S3/pkg/ and copied rev3/verify_block_rev3.sh out to work/block_orig.sh. I ran only the copy.
- Diff of my block copy against the original: lines 6 and 7 only. The values of `T=` and `H=` changed to the synthetic hashes 7ebd8c5a…050f and 85de9df5…d83b. The follow-up c1 is 16dee1c4…e868. CANON and every other line are unchanged (evidence/block_diff_vs_original.txt).

## 2. Status
- **F14 (false PASS): FAIL.** The unmodified block printed `PASS` with rc 0 while git was connected to another host. This was reproduced with a real loopback TLS git server.
- **F15 (secret output): FAIL.** Git's own stderr, passed through by the block, printed the dummy token in three of the six case shapes. It is never in stdout.

## 3. Harness
All of it runs offline in a network namespace.
- I ran `unshare -rn`, brought `lo` up with a SIOCSIFFLAGS python snippet, and bound 127.0.0.1:443.
- I unset the proxy variables and set NO_PROXY=127.0.0.1, GIT_CONFIG_GLOBAL=/dev/null, GIT_CONFIG_SYSTEM=/dev/null and GIT_TERMINAL_PROMPT=0.
- The certificate is self-signed with SAN DNS:github.com, DNS:evil.test and IP:127.0.0.1, passed as GIT_SSL_CAINFO. TLS verification stayed ON.
- Names were mapped to loopback with two `http.curloptResolve` entries passed through GIT_CONFIG_COUNT/KEY/VALUE.
- The server is python `ssl` plus `http.server`, calling `/usr/lib/git-core/git-http-backend`. It serves any path containing `/info/refs` or `/git-upload-pack`.
- It logs the Host header, SNI, client address, request line and whether Authorization was present (never the value).
- Server modes: normal; lenient (a hostile server that also answers GET or POST on any path); 401 (always Basic challenge); 404; auth (401 until an Authorization header is sent, then serve).
- For each case I made a fresh clone from `https://github.com/1h0lde4/ocbrain-v4.1` (mapped to the local server) and ran `git remote set-url origin <URL>`.
- I then ran the block from the clone root, with stdout and stderr captured separately. I also ran `git fetch` and `git ls-remote` alone to attribute any output.
- A full re-run of everything gave identical verdicts.

## 4. F14 case results
"Parsed" is what block line 15 produces from `git remote get-url origin`. "Idok" is whether line 16 accepts it. Every F14 row has token count 0 in both streams.

| Case | URL | Parsed | Idok | Server saw | Block rc | Verdict |
|---|---|---|---|---|---|---|
| 1 | canonical | `https://github.com/1h0lde4/ocbrain-v4.1` | yes | Host github.com, SNI github.com | 0, PASS | positive control OK |
| 2 | `https://evil.test?@github.com/1h0lde4/ocbrain-v4.1` | `https://github.com/1h0lde4/ocbrain-v4.1` | yes | Host evil.test, SNI evil.test | 0, PASS | FALSE PASS |
| 3 | `https://evil.test#@github.com/…` | same | yes | Host evil.test, `GET / HTTP/1.1` | 1 | FAIL on strict server (404); no false PASS |
| 3L | same, hostile lenient server | same | yes | Host evil.test | 0, PASS | FALSE PASS |
| 4 | `https://127.0.0.1?@github.com/…` | same | yes | Host 127.0.0.1, no SNI (IP) | 0, PASS | FALSE PASS |
| 5 | `https://user:DUMMYTOKEN-xyz@evil.test?@github.com/…` | same, userinfo dropped | yes | Host evil.test, no Authorization | 0, PASS | FALSE PASS |
| 5A | same, server challenges with 401 | same | yes | Host evil.test; 2nd request carried Authorization (value not logged) | 0, PASS | FALSE PASS, credential sent to evil.test |
| 6 | `https://github.com@evil.test/…` | `https://evil.test/1h0lde4/ocbrain-v4.1` | no | Host evil.test | 1 | FAIL as expected |
| 7 | `https://evil.test/…` | `https://evil.test/…` | no | Host evil.test | 1 | FAIL as expected |

- **Case 2, request lines seen by the server:** `GET /?@github.com/1h0lde4/ocbrain-v4.1/info/refs&service=git-upload-pack` and `POST /?@github.com/1h0lde4/ocbrain-v4.1/git-upload-pack`. Client addresses were 127.0.0.1:33000 and :33016 (one of the 10 requests).
- **Case 2, stdout and stderr:** stdout was `follow-up: <c1> c1 follow-up`, then `PASS at 2026-11-24T01:53:51Z: remote tip 16dee1c4…; handoff commit 85de9df5… …`. stderr was empty.
- **Case 3:** the fragment is not sent, so the server only sees `GET /`. A PASS needs an attacker server that serves the git protocol at `/`. Case 3L did exactly that.
- **Cases 6 and 7:** the block prints FAIL but still runs fetch and ls-remote against evil.test, where the server logged 10 requests each. FAIL here is an output verdict, not a stop. Whether credentials would be sent in those two cases was not tested. The mechanism was shown only in 5A.

## 5. F15 case results
All tokens are the dummy `DUMMYTOKEN-xyz`. "Solo" is `git fetch` or `git ls-remote` run alone, 1 occurrence each.

| Case | Server | Block stdout / stderr count | Leaked text and path |
|---|---|---|---|
| a1: `https://TOKEN@github.com/…` | 401 Basic | 0 / 3 | `fatal: could not read Password for 'https://DUMMYTOKEN-xyz@github.com': terminal prompts disabled`. The block's own identity check PASSED here. |
| a2 | 200 | 0 / 0 | block PASS, no leak |
| a3 | challenge then 200 | 0 / 0 | block PASS, no leak |
| b1: `…ocbrain-v4.1?token=TOKEN` | 404 | 0 / 3 | `fatal: repository 'https://github.com/1h0lde4/ocbrain-v4.1?token=DUMMYTOKEN-xyz/' not found` |
| b2 | 200 | 0 / 0 | no leak; block FAIL (origin not canonical), and its text does not print the URL |
| c: `…#TOKEN` | strict, so 404 on `/` | 0 / 3 | `fatal: repository 'https://github.com/1h0lde4/ocbrain-v4.1#DUMMYTOKEN-xyz/' not found` |
| c-lenient | 200 | 0 / 0 | no leak |
| d: `https://user:TOKEN@github.com/…` | 401 | 0 / 0 | git printed `Authentication failed for 'https://github.com/…'` (anonymised) |

- **Source of the three stderr lines.** There are three occurrences per leaking case, and each of the three git network commands prints the leak once when run alone. The commands are `git fetch` (block line 17) and `git ls-remote` inside `live()` (line 10, called from lines 18 and 35). The attribution is DERIVED from the matching counts; the block's stderr lines are not tagged by command.
- **Block echo lines.** They never printed the token (stdout count 0 in every case).
- **No claim of prevention.** The password-bearing shape (d), the 200 cases and the lenient case showed no leak. These are only the shapes I tried.
- **Case c label.** The case id `F15-c-200` is a misnomer. That server returned 404; the 200 variant is `F15-c-lenient`.

## 6. Comparison with Addendum 6 (read only after the experiments)
- **Agree (F14).**
  - Line 15 cuts the authority only at `/`, so `?@` and `#@` forms parse as canonical.
  - Git connects to the other host in those forms.
  - Addendum 6 did not reproduce the printed `PASS`; I did, over real TLS and with git-http-backend.
- **Qualifier on `#` (my result).** Git requests only `/` from the other host, so the `#@` form gives a false PASS only against a hostile server that answers `/`. A strict repo server returned 404 and the block printed FAIL.
- **Additions on F14.**
  - A userinfo credential is sent to the other host after a 401 (5A).
  - The block still contacts non-canonical hosts after an identity FAIL (6, 7).
  - The IP-literal form (4) has no SNI.
- **Agree (F15).** The mechanism is real: the token appears as the user name or in the query string in git's own messages.
- **F15 gap now covered.** Addendum 6 listed `https://TOKEN@github.com/…` against a 401 as not reproduced. I reproduced it over TLS with the canonical host name, mapped to loopback. The block's identity check passed in that case, so the leak does not depend on a failed identity check.
- **Disagree or differ.** None on substance.
  - Addendum 6 quotes `unable to access '…?token=TOKEN/'` for dead ports. On a 404 I saw `repository '…' not found` instead, with the same leak.
  - Its sentence in section 4 that the block comment and prose hold only for the block's own lines is consistent with my data.
- **Not reproduced.** The reviewer's `\@` and `%2f@` forms, and the `/@` and `/x?@` rejection claims. I did not test them.

## 7. Findings register

**S3-F14 (false PASS)**
1. Id: S3-F14.
2. Source: `verify_block_rev3.sh` lines 14–16 (line 15 case statement, line 16 comparison). Lines 17–37 then run unconditionally.
3. Conditions: origin URL set to a crafted URL, netns loopback TLS server, git 2.43.0 and libcurl 8.5.0.
4. Commands and inputs: `run_all.sh`, cases F14-2 to F14-5A in `cases.tsv`.
5. Raw output: evidence/F14-2/block.stdout, evidence/F14-2/server.log and the equivalents for F14-3L, 4, 5 and 5A.
6. Expected: FAIL for any non-canonical host. Actual: PASS with rc 0 while Host was evil.test or 127.0.0.1.
7. Severity and impact: the false PASS is substantive under the brief. The attacker model is narrow, because someone must set origin. In 5A a credential in the URL reached the other host.
8. Classification: OBSERVED.
9. Limits: `github.com` is a loopback mapping of my own TLS server, and the hostile-server behaviour for `#` is my own server mode. The real GitHub was not contacted.
10. Substantive: yes.

**S3-F15 (credential output)**
1. Id: S3-F15.
2. Source: block line 17 (`git fetch`, stderr not captured), line 10 inside `live()` via lines 18 and 35, and line 15 (it does not touch the token that git later prints).
3. Conditions: token as the user name with a 401, or in the query string or fragment with a 404.
4. Commands and inputs: `run_all.sh`, cases F15-a1-401, F15-b1-404 and F15-c-200.
5. Raw output: evidence/F15-*/block.stderr plus solo_fetch.err and solo_lsremote.err.
6. Expected: no token in any output stream. Actual: 3 occurrences in stderr per leaking case, 0 in stdout.
7. Severity and impact: this is the revoked-token case; the output gets pasted into chats or issues. The block's comment and patch prose claim that credentials are never printed, and the claim is false for the whole run.
8. Classification: OBSERVED (path attribution DERIVED).
9. Limits: no real GitHub 401 behaviour; only the shapes in section 5.
10. Substantive: yes.

## 8. Unreviewed or unverified
- Real-GitHub behaviour (no public traffic allowed).
- The `\@`, `%2f@` and `/@` forms, ssh and scp forms, and non-443 ports.
- Case 5A shows an Authorization header sent to evil.test, but its value was deliberately not logged.
- Credential sending in cases 6 and 7 was not tested.
- Block lines 21–37 behaviour beyond what ran.
- My checks of git's stderr covered only git 2.43.0.

## 9. Environment
- git 2.43.0, bash 5.2.21, python 3.13.18, curl and libcurl 8.5.0 (OpenSSL 3.0.13), openssl 3.0.13, Linux 6.18.44, running as root inside `unshare -rn`.

## 10. Declaration
- I am a Claude model sub-agent (Sonnet 5.5) in an independent context. I am the same model family as the author. I am not a human.
- Tools: Bash and Read.
- Files read: COMMON_PREAMBLE.md; the package zip and the extracted block, the patch's `verify_block_rev3.sh` only; Addendum 6, only after the experiments.
- I did not open pkg/optional_item_I/ and no other stage directory.
- Date: 2026-11-24.

## 11. Reproducibility
- The paths below are all under /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a9/stage_S3/.
- `bash run_all.sh <stage dir>` runs everything. It calls `setup.sh` (certificate, synthetic T/H/c1 repository, block copy), then `inner.sh` (runs inside `unshare -rn`, uses `server.py` and `cases.tsv`), then `summarize.py`, which writes `SUMMARY.tsv`.
- Raw outputs and the index are in `evidence/` and `evidence/INDEX.txt`.
- REPORT_S3.md in that directory is a short stub (the full report is this message).

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
