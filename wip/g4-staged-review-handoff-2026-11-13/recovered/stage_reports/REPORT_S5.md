STAGE S5: COMPLETE (criterion E, credential confidentiality, non-TLS only)

SUBSTANTIVE FINDINGS: yes (reproduced output of dummy credentials by git, in the block's whole run, and prose contradicted)

Working directory: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S5/
Report file: none written (the harness refuses report files from subagents). An earlier running REPORT_S5.md was deleted. This message is the full report.
Evidence: .../stage_S5/evidence/ (INDEX.txt = one line per file, 695 files, classified BLOCK-OUTPUT or HARNESS/other, with dummy-token occurrence counts; ROWS_TABLE.txt; rows/<ID>/{stdout.txt, stderr.txt, combined.txt, exit_code*.txt, block.sh, HARNESS_META.txt}; servers/ logs). evidence/INDEX_rows.txt is a raw append log that contains superseded lines from reruns; INDEX.txt is the authoritative index.

## 1. Package integrity
- Full SHA-256 of my copy of the zip: 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286. It equals the authoritative value, compared in full. The original zip was copied, never modified.
- `sha256sum -c SHA256SUMS.txt` inside the package: all 7 listed files OK.
- Extracted into stage_S5/pkg/review_package/ with `python3 -I`. Nothing from the package was executed in place. The block was copied per row; only the CANON=, T= and H= lines were substituted. The diff of the substituted copy against the original is recorded in each row's changed_lines_count.txt (3, or 2 for rows where CANON stayed canonical).
- I read the brief's item E, the block (38 lines) and the patch. I did not read item I, any other stage directory, /home/claude, or any author report.

## 2. Criteria table (scope: brief item E, exactly as written)
| Criterion | Status | Evidence and reasoning |
|---|---|---|
| E. Credential confidentiality: no remote URL, embedded credential or token may appear in any PASS/FAIL or diagnostic output of the whole run, including messages printed by git itself | **FAIL** | A dummy credential appeared in captured output in 27 of 68 rows. In every case git printed it on stderr, not the block's own echo lines. Token as the URL user name (R01, R01n, R01p, R11) and token in a query string (R20, R21, R13q and others) are the strongest cases. Token in a path appeared in the PASS-run row S13. Details are in F1 to F4. |

TLS-only gap (stated as required): reproductions that need a real TLS git server were NOT RUN.
- Not run: an https canonical host answering 401 with a token as user name. The credential-prompt code path is the same git code I observed over plain http (R01), so a leak there is DERIVED, not observed.
- Not run: a successful https fetch against a TLS server. Git's "From <url>" line is scheme-independent, and I observed it over http and for local paths (S12, S13).
- Run only as "https origin against a plain-http server": R4Gs, R4Ns, R4Es, R4Xs. The TLS handshake failed locally; no token appeared.

I never observed a false PASS caused by credentials. All origins carrying a userinfo or query token that I tested produced exit 1 and the TRANSFER INCOMPLETE line, apart from rows where my own CANON substitution made the identity check pass. A false PASS is outside my scope in any case.

## 3. Findings register (substantive)

### F-S5-1: token as URL user name is printed by git (SECRET OUTPUT)
1. Id: F-S5-1.
2. Source: block line 17 (`git fetch origin ...`, stderr not suppressed) and line 10 inside `live()` (called at lines 18 and 35). `git ls-remote` is inside `$(...)`, so only its stdout is captured and its stderr passes through. Line 15 strips only the https userinfo from the compared copy, not from the URL that git uses.
3. Conditions: origin URL `http://TOKEN@127.0.0.1:18101/origin.git` (no password). The server answers 401. git 2.43.0.
4. Commands: `bash scripts/start_servers.sh; NOTE=... scripts/run_row.sh R01 'http://@TOK@@127.0.0.1:18101/origin.git' 'http://127.0.0.1:18101/origin'` (scripts/matrix1.sh). Variants: R01n (GIT_TERMINAL_PROMPT unset, no tty, no askpass), R01d (GIT_ASKPASS logging double), R01p (pty via script(1)), R11 (token@ only, server wants a password).
5. Raw output, R01 stderr (3 times): `fatal: could not read Password for 'http://DUMMYTOKEN-S5-R01-zq9x@127.0.0.1:18101': terminal prompts disabled`.
   - R01n stderr: same text, ending `: No such device or address`.
   - R01p (terminal): `Password for 'http://DUMMYTOKEN-S5-R01p-zq9x@127.0.0.1:18101': `.
   - R01d: git itself printed only `Authentication failed for 'http://127.0.0.1:18101/origin.git/'`, but the askpass program received the token-bearing prompt (rows/R01d/doubles/askpass.log). That is a harness log, not block output.
   - The block's own stdout never contained the token in these rows.
6. Expected versus actual: the patch says credentials in the URL are "ignored and never printed". Actual: the token printed in full, three times per run, on stderr.
7. Severity and impact: High. A token used as a user name (`https://TOKEN@github.com/...`) is a common form. The block's identity check accepts it for the canonical https host (line 15 drops userinfo), so the block proceeds to fetch and would pass this to git. If the server returns 401, the token is printed into whatever log or terminal captures the run.
8. Classification: OBSERVED over plain http. For https the leak is DERIVED (not run, TLS).
9. Limitations: tested over plain http against my 401 server only, so the https/real-GitHub behaviour was not reproduced. Whether real GitHub answers 401 to a token-only user name was not tested. My own identity-gate CANON for http rows is not the canonical check.
10. Substantive: yes (reproduced output of a credential).

### F-S5-2: token in query string, fragment or path suffix is printed by git (SECRET OUTPUT)
1. Id: F-S5-2.
2. Source: lines 10 and 17 (same invocations). Line 15 neither strips nor rejects query strings, fragments or path tokens. The identity check fails (line 16, whose message prints only the constant CANON), but git is still run afterwards.
3. Conditions: origin URL with `?token=T`, `?x=1&token=T`, `#T`, or a token in the path.
4. Commands: `run_row.sh R20 'http://127.0.0.1:1/origin.git?token=@TOK@' 'http://127.0.0.1:1/origin'`; also R21 (https, dead port), R24, R25, R26, R33, R34, R35f, R35p (canonical host, no network via `unshare -rn`), R13q, R4Gq, R4Nq, R4Eq, R4Xq (local server answering 200 garbage, 404, 500 and connection reset), R61q (insteadOf that rewrites to a query-token URL), R72 (path).
5. Raw output, R20 stderr (3 times): `fatal: unable to access 'http://127.0.0.1:1/origin.git?token=DUMMYTOKEN-S5-R20-zq9x/': Failed to connect to 127.0.0.1 port 1 after 0 ms: Couldn't connect to server`.
   - R33 (canonical host, no network): `fatal: unable to access 'https://github.com/1h0lde4/ocbrain-v4.1?token=DUMMYTOKEN-S5-R33-zq9x/': Could not resolve host: github.com`.
   - R13q (ok server): `fatal: repository 'http://127.0.0.1:18103/origin.git?token=...-R13q-.../' not found`.
   - Same pattern for the fragment, path-suffix and 404/500/garbage/reset variants.
6. Expected versus actual: the block states it does not print the URL "because it may carry credentials", and the patch says credentials are "never printed". Actual: git echoed the full URL including the query token.
7. Severity and impact: High. A token passed in a query string reaches stderr and any log.
8. Classification: OBSERVED.
9. Limitations: git 2.43.0 only; other versions may format messages differently. For the 401 server rows R05 to R08, git's prompt text omits query and path, so there was no leak (see the table).
10. Substantive: yes.

### F-S5-3: git prints the remote URL on every successful fetch, including a PASS run (SECRET OUTPUT under the strict reading of E)
1. Id: F-S5-3.
2. Source: line 17, `git fetch origin ...`. When the remote-tracking ref is created or moved, git writes `From <url>` to stderr.
3. Conditions: a fetch that actually updates the tracking ref (rows use STALE=1, which deletes the tracking ref before the run).
4. Commands: S12, S13, S70, S71, S10, S14 (scripts/matrix3.sh and matrix4.sh).
5. Raw output: S12 (no credentials) stderr `From http://127.0.0.1:18103/origin`. S13, which ends in a **PASS line, exit 0**, has stderr `From http://127.0.0.1:18103/DUMMYTOKEN-S5-S13-zq9x` (path token). S70 (local path): `From <path>/tokdir-DUMMYTOKEN-S5-S70-zq9x`. S71 (file://): `From file://...tokdir-DUMMYTOKEN-S5-S71-zq9x`.
   - Counter-observation: git strips user info in this line. S10 (`http://user:TOKEN@...`, successful authenticated fetch) and S14 (`http://TOKEN@...`) printed `From http://127.0.0.1:18108/origin` and `From http://127.0.0.1:18103/origin`, with no token.
6. Expected versus actual: brief E says no remote URL (not only no credential) may appear in any output, including messages printed by git. The URL appears even with no credentials (S12). For the real canonical clone, `From https://github.com/1h0lde4/ocbrain-v4.1` would appear on the first fetch (DERIVED).
7. Severity and impact: Medium for URLs without credentials, High where the credential is in the path or query (S13).
8. Classification: OBSERVED for http and local paths; the https form is DERIVED.
9. Limitations: only appears when the fetch updates a ref. A clone whose tracking ref is already current prints nothing there (R12, R13 are quiet PASS runs). Whether F-S5-3 counts as a violation depends on reading "no remote URL" literally; token-in-path in S13 is a credential-bearing case regardless.
10. Substantive: yes on the strict wording of E; S13 is a credential case in a PASS run.

### F-S5-4: credential claims in the block and patch are contradicted (PROSE INACCURACY)
1. Id: F-S5-4.
2. Source: block line 15 (comment: "credentials in the host part are dropped, so they are neither compared nor printed"), block line 16 (message: "the configured URL is not printed because it may carry credentials"), patch line 30 (new step 2 prose: "credentials in the URL are ignored and never printed").
3. Conditions: any of the rows in F-S5-1 to F-S5-3.
4. Commands: see those findings; claim-by-claim comparison in section 5.
5. Raw output: see F-S5-1 and F-S5-2. The block's own FAIL lines never contain the origin credential; git's lines do.
6. Expected versus actual: the patch's step 2 claim is absolute and is made about the whole procedure. Observed: it holds for userinfo-with-password forms (R02, R03, R10, R22, R23, R32, S10, S14) and for ssh forms with my double (R50 to R56), and fails for a token as user name and for query, fragment and path tokens.
7. Severity: Medium to High (an overstated security guarantee in a handoff document).
8. Classification: OBSERVED contradiction, from the rows above.
9. Limitations: the line 15 and line 16 statements are literally about the block's own `echo` lines and about the identity comparison; they hold for those. The overstatement is in how they read at run level and in the patch prose.
10. Substantive: yes (a claim in the patch prose that the block does not satisfy).

## 4. Table of all rows tested
All rows are OBSERVED. Every row ran twice: once with stdout and stderr captured separately, once combined with the exit code (I report the exit code of the separate run; the combined run matched in all rows except R01p). Every row used `env -i` with a clean PATH, GIT_CONFIG_GLOBAL and GIT_CONFIG_SYSTEM set to /dev/null, GIT_TERMINAL_PROMPT=0 unless "TPunset" is noted, and proxy variables unset with NO_PROXY=127.0.0.1. "netns" means `unshare -rn` (no network at all). "Block" is what the block itself printed: nxFAIL is the number of FAIL lines, plus the TRANSFER INCOMPLETE line unless PASS. "Git" is git's own first relevant stderr line, with the dummy token written as TOK. Tokens are different per row (DUMMYTOKEN-S5-<row>-zq9x). Ports: 18101 = 401 always, 18102/18108/18109 = 401 unless the right password, 18103 = ok, 18104 = 200 garbage, 18105 = 404, 18106 = 500, 18107 = reset, 1 = dead.

| Row | Origin form | Flags | Block | Git printed | Token in output | Exit |
|---|---|---|---|---|---|---|
| R01 | http://TOK@127.0.0.1:18101 (token as user name, 401) | | 6xFAIL | could not read Password for 'http://TOK@127.0.0.1:18101': terminal prompts disabled | YES | 1 |
| R01n | same | TPunset, no tty | 6xFAIL | same, ending "No such device or address" | YES | 1 |
| R01d | same | TPunset, askpass double | 6xFAIL | Authentication failed for 'http://127.0.0.1:18101/origin.git/' (token only in askpass.log) | no (in askpass prompt log) | 1 |
| R01p | same | pty via script(1) | 1xFAIL then hang | terminal prompt "Password for 'http://TOK@127.0.0.1:18101':" | YES | 124 (my timeout) |
| R02 | http://user:TOK@ (token as password, 401) | | 6xFAIL | Authentication failed for 'http://127.0.0.1:18101/origin.git/' | no | 1 |
| R03 | http://TOK:x@ (401) | | 6xFAIL | same as R02 | no | 1 |
| R04 | no credentials (401, control) | | 5xFAIL | could not read Username for 'http://127.0.0.1:18101' | no | 1 |
| R05 | ?token=TOK (401) | | 6xFAIL | could not read Username for 'http://127.0.0.1:18101' | no | 1 |
| R06 | ?x=1&token=TOK (401) | | 6xFAIL | same | no | 1 |
| R07 | #TOK (401) | | 6xFAIL | same | no | 1 |
| R08 | path /TOK/origin.git (401) | | 6xFAIL | same | no | 1 |
| R10 | http://user:TOK@ correct password, 18102 | | 1xFAIL (identity, my CANON is http) | none (fetch succeeded, up to date) | no | 1 |
| R11 | http://TOK@ 18102 (server wants a password) | | 6xFAIL | could not read Password for 'http://TOK@127.0.0.1:18102' | YES | 1 |
| R12 | no credentials, 18103 (control) | | PASS | none | no | 0 |
| R13 | token in path, 18103 | | PASS | none | no | 0 |
| R13q | ?token=TOK, 18103 | | 6xFAIL | repository 'http://127.0.0.1:18103/origin.git?token=TOK/' not found | YES | 1 |
| R14 | token in path, trailing slash | | 1xFAIL | none | YES (harness CANON echo, see minor M1) | 1 |
| R14u | http://TOK@ 18103 | | 1xFAIL | none | no | 1 |
| R20 | http dead port 1, ?token=TOK | | 6xFAIL | unable to access 'http://127.0.0.1:1/origin.git?token=TOK/': Failed to connect | YES | 1 |
| R21 | https dead port 1, ?token=TOK | | 6xFAIL | unable to access 'https://127.0.0.1:1/origin.git?token=TOK/': Failed to connect | YES | 1 |
| R22 | https://user:TOK@127.0.0.1:1 | | 5xFAIL | unable to access 'https://127.0.0.1:1/origin.git/' | no | 1 |
| R23 | https://TOK@127.0.0.1:1 | | 5xFAIL | same | no | 1 |
| R24 | https dead port, ?x=1&token=TOK | | 6xFAIL | unable to access '...?x=1&token=TOK/' | YES | 1 |
| R25 | https dead port, #TOK | | 6xFAIL | unable to access '...#TOK/' | YES | 1 |
| R26 | https dead port, token in path (CANON also carries it, harness) | | 5xFAIL | unable to access '.../TOK/origin.git/' | YES | 1 |
| R27 | http://TOK@127.0.0.1:1 | | 6xFAIL | unable to access 'http://127.0.0.1:1/origin.git/' | no | 1 |
| R30 | https://TOK@github.com/1h0lde4/ocbrain-v4.1.git (canonical host) | netns | 5xFAIL | unable to access 'https://github.com/1h0lde4/ocbrain-v4.1.git/': Could not resolve host | no | 1 |
| R31 | https://TOK@gitlab.example.invalid/x/y.git (non-canonical) | netns | 6xFAIL | unable to access 'https://gitlab.example.invalid/x/y.git/' | no | 1 |
| R32 | https://user:TOK@github.com/... | netns | 5xFAIL | unable to access 'https://github.com/1h0lde4/ocbrain-v4.1.git/' | no | 1 |
| R33 | https://github.com/1h0lde4/ocbrain-v4.1?token=TOK | netns | 6xFAIL | unable to access '...?token=TOK/' | YES | 1 |
| R34 | .../ocbrain-v4.1.git?x=1&token=TOK | netns | 6xFAIL | unable to access '...?x=1&token=TOK/' | YES | 1 |
| R35 | https://TOK@github.com/... | netns, TPunset | 5xFAIL | unable to access (DNS fails before auth) | no | 1 |
| R35f | canonical host, #TOK | netns | 6xFAIL | unable to access '...#TOK/' | YES | 1 |
| R35p | canonical host, .git/TOK | netns | 6xFAIL | unable to access '.../.git/TOK/' | YES | 1 |
| R36 | https://github.com@gitlab.example.invalid/... | netns | 6xFAIL | unable to access 'https://gitlab.example.invalid/...' | no | 1 |
| R37 | https://user:TOK@gitlab.example.invalid/x/y.git | netns | 6xFAIL | unable to access (userinfo stripped) | no | 1 |
| R4Gh / R4Nh / R4Eh / R4Xh | http://TOK@ vs 200-garbage / 404 / 500 / reset server | | 6xFAIL each | not valid: is this a git repository? / repository not found / error: 500 / Recv failure (all with userinfo stripped) | no | 1 |
| R4Gs / R4Ns / R4Es / R4Xs | https://TOK@ vs the same plain-http servers (identity passes) | | 5xFAIL each | gnutls_handshake() failed (userinfo stripped) | no | 1 |
| R4Gq / R4Nq / R4Eq / R4Xq | http ?token=TOK vs the same four servers | | 6xFAIL each | URL with ?token=TOK echoed in each message | YES | 1 |
| R50 | ssh://user:TOK@github.com/... | netns, ssh double | 6xFAIL | "ssh double: connection refused (simulated)", then fatal: Could not read from remote repository | no (token in double's argv log only) | 1 |
| R51 | git:TOK@github.com:path (scp form) | netns, ssh double | 6xFAIL | same | no | 1 |
| R52 | TOK@github.com:path | netns, ssh double | 6xFAIL | same | no | 1 |
| R53 | git@github.com:1h0lde4/ocbrain-v4.1.git (accepted form) | netns, ssh double | 5xFAIL | same | no | 1 |
| R54 | ssh://git@github.com/... (accepted form) | netns, ssh double | 5xFAIL | same | no | 1 |
| R55 | ssh://git:TOK@github.com/... | netns, ssh double | 6xFAIL | same | no | 1 |
| R56 | ssh://TOK@127.0.0.1:2222/o/r.git | netns, ssh double | 6xFAIL | same | no | 1 |
| R60 | token only on remote `upstream` and on `remote.origin.pushurl`; origin = clean local path | | PASS | none | no | 0 |
| R61 | insteadOf rewriting https://github.com/ to https://TOK@github.com/ | netns | 5xFAIL | unable to access 'https://github.com/...' | no | 1 |
| R61b | insteadOf to https://user:TOK@127.0.0.1:1/ | | 5xFAIL | unable to access 'https://127.0.0.1:1/origin.git/' | no | 1 |
| R61q | insteadOf to https://127.0.0.1:1/x?token=TOK&y= | | 6xFAIL | unable to access '.../x?token=TOK&y=origin.git/' | YES | 1 |
| R72 | nonexistent local path containing TOK | | 6xFAIL | '$S/work/nodir-TOK/o.git' does not appear to be a git repository | YES | 1 |
| R80 | NOTE ONLY: GIT_TRACE=1 GIT_CURL_VERBOSE=1, user:TOK@ | | 1xFAIL | trace and curl lines, 12 contain TOK | YES (not part of the contract) | 1 |
| R81 | http.proxy with user:TOK in config; origin via localhost | | 5xFAIL | Failed to connect to 127.0.0.1 port 1 (proxy credential not shown) | no | 1 |
| S12 | no credentials, fresh fetch (STALE) | | PASS | `From http://127.0.0.1:18103/origin` | no (URL printed) | 0 |
| S10 | user:TOK@, correct password, fresh fetch | | 1xFAIL | `From http://127.0.0.1:18108/origin` | no | 1 |
| S14 | TOK@ only, 18103, fresh fetch | | 1xFAIL | `From http://127.0.0.1:18103/origin` | no | 1 |
| S13 | token in path, fresh fetch | | PASS | `From http://127.0.0.1:18103/TOK` | YES (in a PASS run) | 0 |
| S70 | local path with TOK in directory name, fresh fetch | | PASS | `From <path>/tokdir-TOK` | YES | 0 |
| S71 | file:// URL with TOK in directory name | | 1xFAIL (identity) | `From file://...tokdir-TOK` | YES (also harness CANON echo in the block line) | 1 |

Rows tested: 68 distinct row ids, including reruns. Rows R61, R60, R81, R56, S10 to S14, S70, S71 and R80 were first run before my servers or substitutions were correct (servers had stopped after a sandbox restart; the CFG field did not substitute the token). They were rerun and I report only the reruns. The superseded first runs are still in evidence/INDEX_rows.txt but not in the table.

## 5. Claim-by-claim table of credential statements
I searched the block and the patch for the words credential, printed, ignored, token, secret, password. Four statements exist; there are no other credential or URL-printing claims.

| # | Statement (location) | Test and observation | Verdict |
|---|---|---|---|
| 1 | "credentials in the host part are dropped, so they are neither compared nor printed" (block line 15 comment) | Dropped from the comparison for https:// authority forms: R22, R23, R32, R61, R61b pass the identity step without a FAIL line. Not printed by the block's own echo lines in any of 68 rows. Not applied to http://, ssh:// with a password, or scp forms; those forms fall through the case and fail identity (R27, R50 to R56). Git itself prints a user-name-only token (R01, R11) and git's own URL echoes happen after the strip. | Holds for the block's own echo lines and the compared copy; does not describe what the run prints (see F-S5-1) |
| 2 | "the configured URL is not printed because it may carry credentials" (block line 16, runs only on identity failure) | The FAIL line prints only the constant CANON (R20, R14). In the same run git prints the configured URL in three or more places (R20 stderr three times; S12 `From ...`). | True for that line, misleading at run level (F-S5-4) |
| 3 | "credentials in the URL are ignored and never printed" (patch line 30, step 2 prose) | Held for user:password forms in every row. Contradicted by R01/R01n/R01p/R11 (user-name token), R20 to R26 and R33, R34, R35f, R35p (query, fragment, path suffix), R13q, R4Gq, R4Nq, R4Eq, R4Xq, R61q, S13 (path token in a PASS run), R72. | FALSE as stated (F-S5-1, F-S5-2, F-S5-3, F-S5-4) |
| 4 | "(the SSH forms and a trailing `.git` are accepted ...; a fork, mirror or proxy URL fails the identity check by design ...)" (patch line 30) | Not a credential claim but touches the URL forms: git@github.com:path (R53) and ssh://git@github.com/path (R54) pass the identity step; fork-like hosts fail (R31, R36, R37). | Consistent with the rows tested |

Block `echo` lines that could carry a URL: line 8 (all `bad` messages), lines 20, 29 and 36 (hashes and commit ids), line 31 (commit hash and subject of follow-up commits), line 37 (PASS). None prints the origin URL. The git invocations whose stderr is not suppressed are lines 10 (inside `live()`, called at 18 and 35), 17, 19, 21 to 26, 28, 29, 30, 31, 37. Only 10 and 17 touch the remote URL.

## 6. Minor findings
- M1: R14 and S71 contain the token in a FAIL line because my harness put the token into the CANON substitution (a token directory name). That is a harness echo; the real CANON is fixed and carries no credential. The row table marks it.
- M2: Verbose git environment variables are not in the contract; the block does not enable them. Noted only: R80 (GIT_TRACE=1 GIT_CURL_VERBOSE=1 inherited from the environment) printed the token-bearing URL in 12 stderr lines.
- M3: Line 31 prints commit subjects from the remote branch. These are remote-controlled strings, but not a credential of the origin URL.
- M4: For ssh forms (R50 to R56) the token reached my ssh double's argv (`user:TOKEN@github.com`, `git:TOKEN@github.com`, `TOKEN@github.com`) but nothing was printed. Real OpenSSH is not installed in the sandbox, so what a real ssh client prints for such a host argument was not tested.
- M5: R56 initially failed with git's `ssh variant 'simple' does not support setting port`; the rerun used GIT_SSH_VARIANT=ssh. No leak either way.

## 7. Unreviewed or unverified
- Any real TLS test (see TLS-only gap above): https 401 prompt, https successful fetch "From https://...", certificate errors, redirects between hosts.
- Real OpenSSH client output (not installed), and `core.sshCommand`.
- Credential helpers (store, cache, libsecret), `credential.*` config, `url.<base>.pushInsteadOf`.
- HTTP redirects (3xx), `http.followRedirects`, git versions other than 2.43.0.
- Multiple `remote.origin.url` values.
- The question of whether the whole-run output in an interactive terminal differs from my non-interactive captures beyond R01p.
- I did not test items A to D, F to I (other stages).

## 8. Environment and tool versions
git 2.43.0 (libcurl 8.5.0; handshake errors show GnuTLS); GNU bash 5.2.21; Python 3.13.16 (all harness Python run with `-I`); curl 8.5.0; Linux 6.18.44 and later 6.18.x kernel (sandbox restarted once mid-run, which stopped my servers; I restarted them); `unshare -rn` available; real ssh not installed; script(1) available. Servers: my own scripts/srv.py (plain-http, 127.0.0.1 only, git http-backend for the ok and authenticated modes). All runs under `env -i`, no network traffic left the machine; no host other than 127.0.0.1 and netns-isolated DNS failures was contacted. The real environment contained credentials (GH_TOKEN etc.); `env -i` ensured none reached any run, and none is in any evidence file.

## 9. Declaration
I am a Claude model sub-agent (Sonnet 5.5, claude-sonnet-5-5), not a human, in an independent context, of the same model family as the author. Tools: bash, file read/edit/write, python3 -I, git. I had no contact with the author's results: I read only the package, the common preamble and my prompts. A coordinator message mid-task told me to resume after a usage-limit cut-off and to return the report as a message; it contained no results. Date: 2026-11-11 (UTC).

## 10. Reproducibility
All under /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S5/scripts/ (run in this order; they use absolute paths):
1. `setup_repo.sh` builds the synthetic bare origin (work/origin.git), the pristine clone (work/pristine), and work/ids.env (T and H).
2. `start_servers.sh` starts srv.py servers on 127.0.0.1:18101 to 18109 (and creates the path-token symlinks under work/srvroot).
3. `matrix1.sh` (R01, R20, R21, R30, R31, R01n; R01p is the pty command described in its last comment), `matrix2.sh` (local-server rows), `matrix3.sh` (canonical host, ssh double, insteadOf, non-origin remote, path rows), `matrix4.sh` (reruns).
4. `run_row.sh ROW ORIGIN_TEMPLATE CANON_TEMPLATE` is the per-row runner; knobs NETNS, TP, ASKPASS, SSHD, STALE, CFG, EXTRA_ENV, NOTE.
5. `scan.py` regenerates evidence/INDEX.txt and evidence/ROWS_TABLE.txt and scans every artifact for every dummy token (cross-row token hits: 0). Token appearance in artifacts: BLOCK-OUTPUT files (stdout, stderr, combined) hold tokens in the rows marked YES above; harness artifacts holding tokens: HARNESS_META.txt in every row, block.sh in R13, R14, R26, S13, S70, S71 (CANON line), ssh_double.log (R50 to R52, R55, R56), askpass.log (R01d), servers/srv_*.log. Those harness echoes are not block output.
6. Stop the servers with the pids in evidence/servers/pids.txt (already stopped).

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
