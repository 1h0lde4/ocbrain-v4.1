STAGE S2: COMPLETE

Note on files: the Write tool refused to create REPORT_S2.md ("Subagents should return findings as text, not write report files"), twice, and I did not work around that with a shell redirect. The old REPORT_S2.md was renamed to REPORT_S2_prior_2.md before that refusal, so no REPORT_S2.md exists on disk. This message is the complete report. Base directory D = /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S2. Paths below are relative to D unless absolute.

# Stage S2: criterion B, Repository identity and URL parsing (finishing pass 2)

## 1. Package integrity
- I re-ran `sha256sum` in this run on the original zip /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/deliver_a5/final7/g4_rev3_independent_review_package.zip. The result is 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286. The authoritative value is the same, and all 64 hex digits were compared.
- The copy D/finishing_pass/pkg_fresh.zip has the same hash.
- `sha256sum -c SHA256SUMS.txt` in D/finishing_pass/pkg/review_package/ gave 7/7 OK (re-run in this run).
- D/finishing_pass/pkg/review_package/rev3/verify_block_rev3.sh is byte-identical to the member in pkg_fresh.zip (`cmp`).

## 2. Criteria table
| Criterion | Status | Evidence and reasoning |
|---|---|---|
| B. Repository identity and URL parsing | **FAIL** | A false PASS was reproduced. In the real-TLS run, the unmodified block (only T=/H= substituted) printed a `PASS` line and exited 0 for five origin strings whose host git actually contacted was not github.com. Those strings were `https://evil.test?@github.com/1h0lde4/ocbrain-v4.1`, `https://evil.test#@github.com/…`, `https://127.0.0.1:18443?@github.com/…`, `https://user:DUMMYTOKEN-xyz@127.0.0.1:18443?@github.com/…` and `https://2130706433?@github.com/…`. The server saw `Host: evil.test` (Q01, Q03), `Host: 127.0.0.1:18443` (Q05, Q07) and `Host: 127.0.0.1` (Q08). Cause: block line 15 takes the text before the first `/` as the authority and keeps what follows the last `@`, but libcurl ends the authority at `?` or `#`. This breaks the cardinal invariant that PASS must never print when the actual git destination is not the intended canonical repository. |

## 3. What I verified in this run (small checks, no new infrastructure, no network, TLS pass not re-run)
- **(a) Line 15 on origin strings.** I copied line 15 verbatim to D/fp2/line15.txt. I applied it, followed by the line 16 comparison `${URL%.git}` = CANON, to 17 strings with D/fp2/check_line15.sh and D/fp2/forms.txt. The output is D/fp2/line15_recheck_output.txt.
  - ACCEPT (normalised to the canonical URL): the canonical URL with and without `.git`, `https://DUMMYTOKEN-xyz@github.com/…`, `https://user:DUMMYTOKEN-xyz@github.com/…git`, `https://evil.test?@github.com/…`, `https://evil.test#@github.com/…`, `https://127.0.0.1:18443?@github.com/…`, `https://evil.test\@github.com/…`, `https://evil.test%2f@github.com/…` and `https://2130706433?@github.com/…`.
  - REJECT: `https://github.com@evil.test/…`, `https://evil.test/@github.com/…`, `https://evil.test/?@github.com/…`, `https://github.com/@evil.test/…`, `https://github.com/1h0lde4/ocbrain-v4.1?@evil.test`, `https://github.com:443/…` and `https://GITHUB.COM/…`.
  - This matches the earlier 93-row table for these 17 rows. It is a string-level decision only.
- **(b) Full stdout, stderr and server request files in D/finishing_pass/handcheck/out_tls/.** I read the complete `*.stdout`, `*.stderr`, `*.server_requests`, `server.log`, `table.txt`, `netns_proof.txt` and `block_diff.txt`.
  - Each of the 5 false-PASS runs prints `PASS at <UTC>: remote tip a7c7df97…; handoff commit a7c7df97…; 0 follow-up(s)…` as the only stdout line, with exit=0 recorded in table.txt. The control runs with the canonical URL and with the canonical URL plus a dummy credential also print PASS, with `Host: github.com`.
  - Each run made 6 requests (3 GET and 3 POST). The Host headers seen are in the table in section 4.
  - The two negative controls (`NEG_U01` for `https://github.com@evil.test/…`, `NEG_D02` for `https://127.0.0.1:18443/…`) print the identity FAIL line and `TRANSFER INCOMPLETE …`. The server saw `Host: evil.test` and `Host: 127.0.0.1:18443`, so the block fails closed there.
  - table.txt truncates the PASS line, but the full stdout files confirm it.
- **(c) Block-copy diffs.** I diffed every block copy used in the tests against the original block. The real-CANON copies (run/work, finishing_pass/rerun/work, handcheck/w, handcheck/w_tls) differ only in the `T=` and `H=` lines. The synthetic-CANON copies (block_synth_canon.sh, used only for the fork/mirror cases M01–M11) also differ in `CANON=`. No other line differs. The TLS-run diff is out_tls/block_diff.txt (lines 6–7 only). The real CANON line `https://github.com/1h0lde4/ocbrain-v4.1` was kept for every false-PASS evidence run.
- **(d) DUMMYTOKEN scan of the TLS pass.** The scan that run_tls_pass.sh prints at its end was not saved to any file, so no earlier scan result exists on disk. I re-scanned the saved files in this run. The result is D/fp2/dummytoken_scan_out_tls.txt.
  - There are 0 occurrences of `DUMMYTOKEN-xyz` in all out_tls `*.stdout`, `*.stderr`, `server.log` and `*.server_requests`, and none in handcheck/out block stdout and stderr.
  - The token appears only in out_tls/table.txt, where the harness echoes the origin string it was given (harness output, not block output).
  - The earlier compare_runs_output.txt reports "token leak: []" for the 93-row harness.
- Not re-run: the TLS pass (not needed). The earlier full re-run of the 93-row harness in finishing_pass/rerun matched the original with 0 row differences (finishing_pass/compare_runs_output.txt).

## 4. Findings register
Reading the severity labels: this is a verification block whose cardinal invariant is "never print PASS when the contract is not met". "High" means that invariant is violated.

### S2-01: false PASS for "?@" origins (SUBSTANTIVE, FALSE PASS)
1. **Id:** S2-01.
2. **Location:** /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S2/finishing_pass/pkg/review_package/rev3/verify_block_rev3.sh, line 15 (authority extraction `auth=${rest%%/*}; URL=https://${auth##*@}…`). Line 16 compares the result with `$CANON` (line 4). The same line is embedded in rev3/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch (patch line 47), and the patch prose at patch line 30 says "credentials in the URL are ignored … a fork, mirror or proxy URL fails the identity check by design".
3. **Conditions:** git 2.43.0 with libcurl-gnutls 8.5.0. The clone's `origin` URL is `https://<host>[:port]?@github.com/1h0lde4/ocbrain-v4.1[.git]`, and the server at that host serves a repository containing T and H on the branch. The run happened inside a loopback-only network namespace (`unshare -rn`), with name mapping via `http.curloptResolve`, `GIT_SSL_CAINFO` trusting a self-signed loopback cert, and a purpose-built TLS smart-HTTP server that maps `/?@github.com/<repo>/…` back to its repository (an attacker-style server).
4. **Commands:** `cd D/finishing_pass/handcheck && bash run_tls_pass.sh`. It re-executes itself under `env -i … unshare -rn`. It builds a synthetic repository, copies the block with only T=/H= substituted, and runs the block in clones whose origin is each tested string.
5. **Raw output (stdout of Q01, the same shape for Q05, Q07 and Q08):** `PASS at 2026-11-09T22:22:51Z: remote tip a7c7df9745ae0f17e4f46ed0669e625cd3d4b34c; handoff commit a7c7df9745ae0f17e4f46ed0669e625cd3d4b34c on docs/g4-fts-errata-handoff-oct2026; 0 follow-up(s), each a single-parent child changing handoff.md alone`. The server request lines are `port=443 GET /?@github.com/1h0lde4/ocbrain-v4.1/info/refs&service=git-upload-pack | Host: evil.test …`. Evidence files, all under /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S2/finishing_pass/handcheck/out_tls/: Q01_evil_test_qmark_at.{stdout,stderr,server_requests}, Q05_ip_literal_qmark_at.*, Q07_dummy_credential_before_qmark.*, Q08_decimal_ipv4_qmark_at.*, table.txt, server.log, block_diff.txt, netns_proof.txt.
6. **Expected vs actual:** expected the `FAIL: origin is not the canonical repository …` line and exit 1 (as for NEG_U01). Actual: PASS and exit 0 while all 6 requests went to evil.test, or to 127.0.0.1 (Q05, Q07 on :18443; Q08 on the default port).
7. **Severity and impact:** High. A fork or impersonating server with identical history, plus follow-ups that change handoff.md only, would be reported as "remote checkpoint verified", which brief item B requires to fail. It needs control of the clone's origin URL and a serving host. The `\@`, `%2f@` and `/@` forms do not reproduce it (see S2-02 and section 5).
8. **Classification:** OBSERVED, executed in the earlier run of this stage (finishing_pass/handcheck, 2026-11-09 22:22 UTC). In this run I re-read the raw files and re-checked line 15, but did not re-execute the TLS pass.
9. **Limitations:** loopback emulation of the attacker host. DNS is replaced by curloptResolve and the self-signed cert is trusted via an environment variable. Only 4 of the "?@" forms were run with real TLS. The others have the destination observed but not a printed PASS from a real server (see table tags).
10. **Substantive?** Yes. It is a reproduced false PASS of the REV3 block.

### S2-02: false PASS for "#@" origins (SUBSTANTIVE, FALSE PASS)
1. **Id:** S2-02.
2. **Location:** same as S2-01 (line 15, then line 16).
3. **Conditions:** as S2-01, origin `https://evil.test#@github.com/1h0lde4/ocbrain-v4.1`. libcurl drops the fragment, so the repository path is never sent. The attacker server answers `GET /` and `POST /`.
4. **Commands:** same run_tls_pass.sh, row Q03.
5. **Raw output:** /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S2/finishing_pass/handcheck/out_tls/Q03_evil_test_hash_at.stdout holds the same PASS line as S2-01. The server_requests file shows `port=443 GET / | Host: evil.test`, `POST /`, repeated 3 times. stderr holds `warning: redirecting to https://evil.test/#@github.com/1h0lde4/ocbrain-v4.1/` (3 times).
6. **Expected vs actual:** the same as S2-01.
7. **Severity and impact:** High, the same impact as S2-01.
8. **Classification:** OBSERVED (earlier run, raw files re-read now).
9. **Limitations:** as S2-01. Q06 (`https://127.0.0.1:18443#@…`) and Q09 (`https://0x7f000001#@…`) have an observed destination of 127.0.0.1 only; their printed PASS comes from the simulated-transport run.
10. **Substantive?** Yes.

### S2-03: the same defect for other "host?@" and "host#@" variants (SUBSTANTIVE, same root cause as S2-01 and S2-02)
- **Forms:** Q02 (`https://evil.test:8443?@…git`), Q04 (`https://evil.test?x=1#@…`), Q06, Q09 (`0x7f000001#@`), Q10 (`127.1?@`), Q12 (`https://evil.test:?@…`) and Q11 (`https://[::1]:18443?@…`).
- **Evidence:** the line 15/16 decision is ACCEPT for all of them (OBSERVED in the harness and re-checked by me for the representative strings). The libcurl destination (OBSERVED, `GIT_CURL_VERBOSE` "Connected to …") is evil.test:8443, evil.test:443, 127.0.0.1:18443 (Q06), 127.0.0.1:443 (Q09, Q10) and evil.test:443 (Q12), as in /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S2/run/evidence/results.md (section 1 table). A printed PASS for the whole block was observed only with simulated transport (wrapper_pass section 3 of results.md, `wp_Q01`…`wp_Q12`, rc=0).
- **Q11:** libcurl tried `::1 port 18443` and failed (finishing_pass/handcheck/out/F6.lsr.stderr), because this sandbox has no IPv6 loopback (`listener bind failed ::1 18443 [Errno 97]`). The row in results.md says "none (no connection attempt visible)"; the handcheck output supersedes that. A printed PASS is not reproduced for Q11.
- **Classification:** OBSERVED for the identity decision, destination and simulated-transport PASS; the real-TLS printed PASS for these forms was not run (DERIVED from the same code path as S2-01).
- **Substantive?** Yes. It is the same reproduced defect family.

### S2-04: URLs printed by git itself in the PASS and FAIL runs (informational; flagged against the literal contract wording)
- **Location:** the block's `git fetch` and `git ls-remote` calls (lines 17, 18, 35). It is git's own stderr, not a block `echo`.
- **Observed:**
  - In the false-PASS runs, git prints `warning: redirecting to https://evil.test/?@github.com/1h0lde4/ocbrain-v4.1/` (3 times) to stderr (out_tls/Q01…Q08 `.stderr`). The URL has no userinfo, so the dummy token is not printed, and the scan found 0 occurrences.
  - In the non-TLS handcheck runs, git printed `fatal: unable to access 'https://github.com/1h0lde4/ocbrain-v4.1/': gnutls_handshake() failed …` while libcurl had connected to evil.test (handcheck/out/F1.lsr.stderr, F1.block.stderr). The URL shown in that diagnostic has the same host misparse as line 15.
- **Classification:** OBSERVED (output). The explanation that this comes from git's URL anonymisation is DERIVED, because I did not read git's source.
- **Severity:** Low. The brief's definition of "substantive" includes "any reproduced output of a credential or URL". Whether URLs without credentials printed by git count is an owner decision. No credential output was reproduced for criterion B.

### Minor findings (false FAIL only, not substantive)
- **Rows:** E05 `github%2ecom`, E06 `%67ithub.com`, E08 `/%31h0lde4/`, N01 `GITHUB.COM`, N03 trailing `/`, N04 `.git/`, N05 `:443`, N07 `github.com:`, N11 different case in the path, N13 `github.com.`, N15 `/./`, N16 `/x/../`, S05 `ssh://git@github.com:22/…`, S07 ssh with a password, S11 `GitHub.com`, S13 ssh with a trailing `/`.
- **Observation:** these are rejected although git contacts github.com. Rejecting them fails closed.
- **Fork and alias cases with a synthetic CANON:** M03 `file://` URL, M04 symlink path, M05 relative path and M06 trailing slash are rejected. This is a string comparison, so the block cannot recognise the same repository under another spelling.
- **Classification:** OBSERVED (run/evidence/results.md, sections 1 and 4).

## 5. All URL forms tested (93 string-level rows, `https` only unless stated)
The identity decision is block lines 4, 8, 15 and 16 applied to the value `git remote get-url origin` returns. The "host git contacts" column is OBSERVED: libcurl's `Connected to host (ip) port N` under `GIT_CURL_VERBOSE` in a loopback-only namespace with github.com and evil.test mapped to 127.0.0.1, or the arguments passed to a logging ssh double. "none" means git refused the URL or showed no connection attempt. Source for every row: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S2/run/evidence/results.md (section 1), reproduced identically by finishing_pass/rerun (0 row differences).

Legend:
- CA = accepted and git contacts github.com (consistent).
- CR = rejected, fail closed.
- FI = FALSE IDENTITY: accepted, git contacts another host.
- NC = accepted, but git makes no connection.
- fF = minor false FAIL.
- [T] = full block printed PASS (exit 0) in the real-TLS run.
- [W] = full block printed PASS only in the simulated-transport run (git wrapper redirecting to a synthetic origin).

| id | origin string (`github.com/…` stands for `github.com/1h0lde4/ocbrain-v4.1`) | line-15 decision | host git contacts | class |
|---|---|---|---|---|
| B01 | https://github.com/… | ACCEPT | github.com:443 | CA (TLS control: PASS, Host github.com) |
| B02 | https://github.com/….git | ACCEPT | github.com:443 | CA |
| B03 | https://DUMMYTOKEN-xyz@github.com/… | ACCEPT | github.com:443 | CA |
| B04 | https://user:DUMMYTOKEN-xyz@github.com/….git | ACCEPT | github.com:443 | CA (TLS control: PASS, Host github.com) |
| B05 | https://@github.com/… | ACCEPT | github.com:443 | CA |
| U01 | https://github.com@evil.test/… | REJECT | evil.test:443 | CR (TLS NEG: FAIL, Host evil.test) |
| U02 | https://github.com:DUMMYTOKEN-xyz@evil.test/… | REJECT | evil.test:443 | CR |
| U03 | https://evil.test@github.com@github.com/… | ACCEPT | none | NC |
| U04 | https://github.com@github.com@evil.test/… | REJECT | none | CR |
| U05 | https://evil.test:1@github.com/… | ACCEPT | github.com:443 | CA |
| U06 | https://user:a%2Fb@github.com/… | ACCEPT | github.com:443 | CA |
| P01 | https://evil.test/@github.com/… | REJECT | evil.test:443 | CR |
| P02 | https://evil.test/x@github.com/… | REJECT | evil.test:443 | CR |
| P03 | https://github.com/@evil.test/… | REJECT | github.com:443 | CR |
| P04 | https://evil.test/?@github.com/… | REJECT | evil.test:443 | CR |
| P05 | https://evil.test/#@github.com/… | REJECT | evil.test:443 | CR |
| P06 | https://github.com/…?@evil.test | REJECT | github.com:443 | CR |
| P07 | https://github.com/…#@evil.test | REJECT | github.com:443 | CR |
| Q01 | https://evil.test?@github.com/… | ACCEPT | evil.test:443 | FI [T][W] |
| Q02 | https://evil.test:8443?@github.com/….git | ACCEPT | evil.test:8443 | FI [W] |
| Q03 | https://evil.test#@github.com/… | ACCEPT | evil.test:443 | FI [T][W] |
| Q04 | https://evil.test?x=1#@github.com/… | ACCEPT | evil.test:443 | FI [W] |
| Q05 | https://127.0.0.1:18443?@github.com/… | ACCEPT | 127.0.0.1:18443 | FI [T][W] |
| Q06 | https://127.0.0.1:18443#@github.com/… | ACCEPT | 127.0.0.1:18443 | FI [W] |
| Q07 | https://user:DUMMYTOKEN-xyz@127.0.0.1:18443?@github.com/… | ACCEPT | 127.0.0.1:18443 | FI [T][W] |
| Q08 | https://2130706433?@github.com/… | ACCEPT | 127.0.0.1:443 | FI [T][W] |
| Q09 | https://0x7f000001#@github.com/… | ACCEPT | 127.0.0.1:443 | FI [W] |
| Q10 | https://127.1?@github.com/… | ACCEPT | 127.0.0.1:443 | FI [W] |
| Q11 | https://[::1]:18443?@github.com/… | ACCEPT | ::1:18443 attempt, failed (handcheck F6; no IPv6 loopback in sandbox) | FI by destination; PASS not reproduced |
| Q12 | https://evil.test:?@github.com/… | ACCEPT | evil.test:443 | FI [W] |
| K01 | https://evil.test\@github.com/… | ACCEPT | github.com:443 | CA |
| K02 | https://127.0.0.1:18443\@github.com/… | ACCEPT | github.com:443 | CA |
| K03 | https://github.com\@evil.test/… | REJECT | evil.test:443 | CR |
| K04 | https://github.com\1h0lde4\ocbrain-v4.1 | REJECT | none | CR |
| K05 | https:\\github.com\1h0lde4\ocbrain-v4.1 | REJECT | ssh host "https":22 | CR |
| K06 | https://evil.test\github.com@github.com/… | ACCEPT | github.com:443 | CA |
| E01 | https://evil.test%2f@github.com/… | ACCEPT | github.com:443 | CA |
| E02 | https://127.0.0.1:18443%3f@github.com/… | ACCEPT | github.com:443 | CA |
| E03 | https://evil.test%23@github.com/… | ACCEPT | github.com:443 | CA |
| E04 | https://evil.test%5c@github.com/… | ACCEPT | github.com:443 | CA |
| E05 | https://github%2ecom/… | REJECT | github.com:443 | fF |
| E06 | https://%67ithub.com/… | REJECT | github.com:443 | fF |
| E07 | https://github.com%2f@evil.test/… | REJECT | evil.test:443 | CR |
| E08 | https://github.com/%31h0lde4/ocbrain-v4.1 | REJECT | github.com:443 | fF |
| E09 | https://github.com/1h0lde4%2focbrain-v4.1 | REJECT | github.com:443 | CR |
| N01 | https://GITHUB.COM/… | REJECT | GITHUB.COM:443 | fF |
| N02 | HTTPS://github.com/… | REJECT | none | CR |
| N03 | https://github.com/…/ | REJECT | github.com:443 | fF |
| N04 | https://github.com/….git/ | REJECT | github.com:443 | fF |
| N05 | https://github.com:443/… | REJECT | github.com:443 | fF |
| N06 | https://github.com:8443/… | REJECT | github.com:8443 | CR |
| N07 | https://github.com:/… | REJECT | github.com:443 | fF |
| N08 | http://github.com/… | REJECT | github.com:80 | CR |
| N09 | https://github.com/…?x=1 | REJECT | github.com:443 | CR |
| N10 | https://github.com/…#frag | REJECT | github.com:443 | CR |
| N11 | https://github.com/1H0LDE4/OCBrain-v4.1 | REJECT | github.com:443 | fF |
| N12 | https://github.com/….git.git | REJECT | github.com:443 | CR |
| N13 | https://github.com./… | REJECT | github.com.:443 | fF |
| N14 | https://github.com//1h0lde4/ocbrain-v4.1 | REJECT | github.com:443 | CR |
| N15 | https://github.com/./1h0lde4/ocbrain-v4.1 | REJECT | github.com:443 | fF |
| N16 | https://github.com/x/../1h0lde4/ocbrain-v4.1 | REJECT | github.com:443 | fF |
| D01 | https://140.82.112.3/… | REJECT | 140.82.112.3:443 (attempt, unreachable in netns) | CR |
| D02 | https://127.0.0.1:18443/… | REJECT | 127.0.0.1:18443 | CR (TLS NEG: FAIL, Host 127.0.0.1:18443) |
| D03 | https://github.com.evil.test/… | REJECT | resolve github.com.evil.test | CR |
| D04 | https://evilgithub.com/… | REJECT | resolve evilgithub.com | CR |
| I01 | https://github。com/… | REJECT | github。com:443 | CR |
| I02 | https://ｇithub.com/… | REJECT | ｇithub.com:443 | CR |
| W01 | leading space + canonical | REJECT | none | CR |
| W02 | canonical + trailing space | REJECT | none | CR |
| W03 | canonical + trailing tab | REJECT | none | CR |
| W04 | https://evil.test @github.com/… (space) | ACCEPT | none (URL refused) | NC |
| W05 | https://evil.test\t@github.com/… | ACCEPT | none (URL refused) | NC |
| W06 | https://evil.test\n@github.com/… | ACCEPT | none | NC |
| W07 | https://evil.test\r@github.com/… | ACCEPT | none (URL refused) | NC |
| W08 | canonical + `\n` | ACCEPT | none visible | NC (command substitution strips the trailing newline) |
| W09 | canonical + `\n\n` | ACCEPT | none visible | NC |
| T01 | git://github.com/… | REJECT | none | CR |
| S01 | git@github.com:1h0lde4/ocbrain-v4.1 | ACCEPT | ssh github.com:22 | CA |
| S02 | git@github.com:1h0lde4/ocbrain-v4.1.git | ACCEPT | ssh github.com:22 | CA |
| S03 | ssh://git@github.com/… | ACCEPT | ssh github.com:22 | CA |
| S04 | ssh://git@github.com/….git | ACCEPT | ssh github.com:22 | CA |
| S05 | ssh://git@github.com:22/… | REJECT | ssh github.com:22 | fF |
| S06 | ssh://git@github.com:2222/… | REJECT | ssh github.com:2222 | CR |
| S07 | ssh://git:DUMMYTOKEN-xyz@github.com/… | REJECT | ssh github.com:22 | fF |
| S08 | git:DUMMYTOKEN-xyz@github.com:1h0lde4/ocbrain-v4.1 | REJECT | ssh host "git":22 | CR |
| S09 | ssh://github.com/… | REJECT | ssh github.com:22 | CR |
| S10 | github.com:1h0lde4/ocbrain-v4.1 | REJECT | ssh github.com:22 | CR |
| S11 | ssh://git@GitHub.com/… | REJECT | ssh GitHub.com:22 | fF |
| S12 | git@github.com:/1h0lde4/ocbrain-v4.1 | REJECT | ssh github.com:22 | CR |
| S13 | ssh://git@github.com/…/ | REJECT | ssh github.com:22 | fF |
| S14 | ssh://git@evil.test/… | REJECT | ssh evil.test:22 | CR |
| S15 | ssh://git@github.com@evil.test/… | REJECT | ssh evil.test:22 | CR |
| S16 | ssh://git@github.com:evil.test/… | REJECT | ssh "github.com:evil.test":22 | CR |

Corroboration with plain `http` (transport only; the block rejects scheme http) from results.md section 2: libcurl connected to, and the listener saw, these hosts.
- H01 `127.0.0.1:18080?@github.com/…` and H02 `…#@…`: 127.0.0.1:18080, Host 127.0.0.1:18080 (H02 request `GET /`).
- H03 `127.0.0.1:18080\@github.com/…`: github.com:80, Host github.com.
- H04 `127.0.0.1:18080/@github.com/…`: 127.0.0.1:18080.
- H05 `github.com@127.0.0.1:18080/…`: 127.0.0.1:18080.
- H06 `127.0.0.1:18080%2f@github.com/…`: github.com:80.
- H07 `evil.test:18080?@…`: evil.test:18080.
- H08 with a dummy credential: 127.0.0.1:18080.

The answer to "do `\@` and `%2f@` contact the other host?" is NO, in this environment. OBSERVED: K01, K02, E01–E04, F4s and H03/H06 all contact github.com, so the block's ACCEPT is consistent there. This holds only for git 2.43.0 / libcurl 8.5.0.

Other adjacent cases, run with a synthetic CANON (results.md sections 4–5):
- M02 (fork with identical history) rejects.
- M09 (two URLs, canonical first) passes and uses the first URL.
- M10 (fork first) rejects.
- M07 and M08 (`url.<x>.insteadOf` rewriting) reject, and git uses the rewritten fork.
- X01 and X02 (proxy via environment or config) fail closed only because the loopback proxy refused CONNECT.
- M11 (`remote.origin.vcs` helper) accepts the identity, git runs the helper, the helper exits 1, and the block prints FAIL. A cooperating helper was not run (see section 7).

## 6. How the printed-PASS evidence differs from the string-level evidence
1. **String-level evidence** (line 15 and 16 on the `get-url` value; 93 rows in the table above; re-checked by me on 17 strings). It shows only the identity decision. It says nothing about what git contacts.
2. **Whole-block runs with real git but no real git server** (run/evidence/forms, handcheck/out, table_handcheck.txt). The identity decision matches the string-level one in every row ("e2e agrees: yes"). The block never prints PASS because the listener is not a git server (TLS handshake fails or the connection is refused). The "block printed PASS=no" column for ACCEPT rows there is therefore not evidence of safety. Those runs are destination evidence: they show which host libcurl contacts and which SNI the listener sees, for example F1 contacts evil.test:443.
3. **Whole-block runs with simulated transport** (run/evidence/wrapper_pass, `wp_*`). A `git` wrapper first in PATH redirects `fetch` and `ls-remote` to a synthetic origin whatever the URL. It printed PASS (rc=0) for the 11 accepted look-alikes Q01–Q10 and Q12, and for the control B01. It printed FAIL for the controls U01 and D02. This shows that nothing after line 16 checks the destination. The destination itself is simulated.
4. **Whole-block runs against a real TLS smart-HTTP git server in a loopback namespace** (finishing_pass/handcheck/out_tls). This is the decisive evidence: real git, real libcurl and TLS, real `Host` headers. It printed PASS and exit 0 for Q01, Q03, Q05, Q07 and Q08, and FAIL for U01 and D02.

Caveats on item 4: name mapping by `http.curloptResolve`, trust of the self-signed cert by `GIT_SSL_CAINFO`, and a server written to answer the odd request paths (`/?@github.com/…`, `/`).

## 7. Unreviewed, not reproduced, or inconclusive
- A real-TLS printed PASS was not run for Q02, Q04, Q06, Q09, Q10, Q12 or Q11. The first six have an observed destination and a simulated-transport PASS only. Q11 failed to connect because the sandbox has no IPv6 loopback. Q02 needs port 8443, which the TLS server did not listen on.
- The `\@` and `%2f@` forms contacted github.com here. Other libcurl or git versions, and URL parsers that treat `\` like `/`, were not tested, so whether they would contact the other host is unknown.
- Only git 2.43.0 with libcurl-gnutls 8.5.0 was exercised. Other versions can parse `?`, `#`, `\` and numeric hosts differently.
- ssh was tested only with a logging ssh double (no real sshd). I did not test `?@` or `#@` forms with `ssh://`; they do not match the `ssh://git@github.com/*` pattern on line 15.
- Whether git forwards credentials to the wrong host (Q07 with its dummy userinfo) was not examined in the full-block runs. The server log does not record Authorization headers. In the plain-http adjacent cases C02 and C03 (results.md section 6), git's credential helper was asked for the host it actually contacts (127.0.0.1:18080), not for github.com.
- A cooperating `remote.origin.vcs` helper (DERIVED false PASS), and a transparent proxy or MITM, were not run. Both need control of git configuration or the network path.
- The brief's criterion E wording ("including messages printed by git itself") is left to its own stage; see S2-04.
- Real GitHub was never contacted, by design.
- The scan output printed by run_tls_pass.sh was never saved; I re-scanned the saved files (section 3d).
- The package's optional item I and the other brief items A and C–H were out of scope.

## 8. Environment and tool versions
- OS: Linux 6.18.44-fc-v338 x86_64.
- git 2.43.0; its `git-remote-https` links libcurl-gnutls 8.5.0-2ubuntu10.15 with GnuTLS 3.8.3.
- bash 5.2.21.
- Python 3.13.16.
- curl 8.5.0 / libcurl 8.5.0 with OpenSSL 3.0.13 (the curl CLI; git does not use it).
- util-linux unshare 2.39.3.
- Tests ran in a user and network namespace (`unshare -rn`) with only the loopback interface (`netns_proof.txt` shows `1.1.1.1:443 -> Errno 101 Network is unreachable`), with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null`, `GIT_TERMINAL_PROMPT=0` and fixed author and committer variables. Dummy credentials only.

## 9. Declaration
I am a Claude model sub-agent (Sonnet 5.5, model ID claude-sonnet-5-5) running in an independent context for this resumed pass. I am the same model family as the author of the package, not a human.
- **Tools used:** a read and file-inspection tool, bash, grep and file-edit tools. No network access beyond the machine. All network-stack tests ran in the earlier runs of this stage, in loopback-only namespaces.
- **This pass:** it only read the earlier evidence files, ran a local string check (no network) and wrote small helper files under D/fp2.
- **Contact with author results:** the only author-provided inputs were the common preamble, the package brief and the prompts. I read my own earlier outputs in this stage directory, as the prompt allowed. I did not read other stage directories, /home/claude, any repository or any author report.
- **Date:** 2026-11-10 UTC. The earlier runs were on 2026-11-08 and 2026-11-09.

## 10. Reproducibility
All scripts and outputs are under D.
- Package integrity: `sha256sum <package zip>` (full value in section 1); `cd D/finishing_pass/pkg/review_package && sha256sum -c SHA256SUMS.txt`.
- String-level re-check (no network): `bash D/fp2/check_line15.sh`, using D/fp2/line15.txt, D/fp2/forms.txt and D/fp2/block_copy.sh. Output: D/fp2/line15_recheck_output.txt.
- Block-copy diffs: `diff D/finishing_pass/pkg/review_package/rev3/verify_block_rev3.sh <copy>`, for the copies listed in section 3(c).
- DUMMYTOKEN re-scan: output in D/fp2/dummytoken_scan_out_tls.txt, from `grep -c DUMMYTOKEN-xyz D/finishing_pass/handcheck/out_tls/*.stdout *.stderr server.log *.server_requests`.
- Real-TLS false-PASS pass (loopback only; self-executes under `env -i … unshare -rn`): `cd D/finishing_pass/handcheck && bash run_tls_pass.sh`. It uses tls_git_server.py, cert.pem and key.pem. Output goes to out_tls/. Not re-run in this pass.
- Destination pass without a git server: `bash D/finishing_pass/handcheck/run_handcheck.sh`, using listener.py. Output goes to handcheck/out/.
- Full 93-form harness (self-executes under `unshare -rn`): `python3 -I D/run/s2_harness.py`. Output goes to run/evidence/ (results.md, results.json, phase2.json, forms/, adjacent/, wrapper_pass/).
- 93-row re-run comparison: D/finishing_pass/rerun/s2_harness.py, then `python3 -I D/finishing_pass/compare_runs.py D/run/evidence/results.json D/finishing_pass/rerun/evidence/results.json` (output: D/finishing_pass/compare_runs_output.txt).
- Earlier reports: D/REPORT_S2_prior_1.md and D/REPORT_S2_prior_2.md (renamed, not overwritten).

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
