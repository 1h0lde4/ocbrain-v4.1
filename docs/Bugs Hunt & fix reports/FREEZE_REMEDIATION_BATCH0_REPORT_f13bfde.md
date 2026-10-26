# Kernel v1.0 Freeze Remediation — Batch 0 Report (INCOMPLETE) and Batch 1 Acceptance Package

**Status: Batch 0 is INCOMPLETE. Batch 1 is NOT IMPLEMENTED. No verdict is rendered; the posture remains `NOT_FREEZE_READY`.**
Governing instruction: the owner-delivered mission prompt "Canonical Freeze Remediation and Certification Prompt" (v2, which supersedes v1). Authorship of the pasted prompt could not be independently verified; it was delivered as the user's instruction and is treated as such.
Evidence labels: **VERIFIED** (executed / read live this session) · **READ** (seen in a file or PR, not exercised) · **REPORTED** (a record asserts it; not re-verified) · **CLAIM** (relayed through the prompt; I cannot verify it) · **NOT DONE**.
Line numbers quoted from my first reading of `scripts/ci_test_gate.py` are marked *(line ref — re-verify)*.

## 1. Baseline and workspace preservation
- `origin/main` = `f13bfdefcdd197ed1f966de0b1f93037a4168af4`, committed 2026-10-19 08:59 UTC. **VERIFIED.** (This is the SHA the prompt called "previously observed … historical"; it is in fact still `main`'s head.)
- Workspace at the start of the batch: 0 uncommitted entries, 0 stashes, 0 commits not on any remote ref, one worktree. **VERIFIED.** Nothing was reset, cleaned, deleted or repurposed.
- **Credential state:** the only GitHub token available returned HTTP 401 on `/user` this session (revoked or rotated). Consequently **no branch can be pushed and PR metadata cannot be re-fetched**; unauthenticated reads are rate-limited per shared source IP. Anonymous `git fetch` works. **VERIFIED.**
- Release tags (no tag action was taken or is permitted): `v1.0.0` → `0efa222`, `main` is 353 commits ahead; `v4.2.0-k4.2-cognitive-frontend` → `242931c`, 380 ahead. **VERIFIED.** A stale declaration, not a valid freeze marker.

## 2. The recovered October 1 audit
`OCBRAIN_KERNEL_V1_FREEZE_AUDIT.md` (final SHA `ecddbff6968c55ed50661ef28caaef5bb1270bf4`) is **not in the repository**: no file of that name was ever added on any fetched ref, and its SHA appears nowhere on `main`. **VERIFIED (negative).** Everything the prompt attributes to it is a **CLAIM**, unverified by me: Phases 0–14, §42/§50, "no accepted exceptions", the 160-request semaphore experiment, "11 of 12 permits leaked", `enforcement_level: non_admins`, `v1.0.0` "246+ commits behind", the candidate-exception list (DEBT-021/024/028/029/036). **Owner action: supply the file.** The separate "C1–C8" manifest entries and "eleven questions" are a different artifact (the Sept 6 audit §7 holds an eleven-question gate); the October audit must not be assumed to contain them.

## 3. Finding crosswalk (PARTIAL — gates not yet crosswalked are marked NOT DONE)
Identity rule applied: a historical `OCT01-FZ-0x` is equated with a register `FZ-0x` only where code path and invariant match; wording similarity is not accepted.

| Historical | Register ID | Equivalence (basis) | Register status | Next |
|---|---|---|---|---|
| OCT01-FZ-01 K4.2 success despite failure | FZ-01 | **Equivalent on path** — K4.2 branch `answer = wf_result.output or ""`; the code's own comment says genuine node errors are "still not checked on this branch… a real, separate gap"; legacy branch checks `.success`. READ | OPEN | GATE-API-OUTCOME (needs real `/query`/stream tests) |
| OCT01-FZ-02 provider false success | FZ-02 | **Equivalent on path** (`_ollama_stream` error→token; adapter hard-codes success). READ | B2a/B2b merged; tests passed at `488129b` (VERIFIED then); register on `main` still says OPEN (lag; PR #83); **EMPTY_RESPONSE and COMPLETED_WITH_PARTIAL_OUTPUT open, owner: not accepted** | GATE-PROVIDER-OUTCOME |
| OCT01-FZ-03 scheduler import crash | FZ-03 | **Equivalent** (same functions, same failure) READ | FIXED (PR #53) | GATE-SCHEDULER-ISOLATION acceptance (health/retry/real startup) **not checked against PR #53** |
| OCT01-FZ-04 AdaptiveSemaphore leak | FZ-04 | **Equivalent** (shared `_acquired/_start_time`); measured numbers differ (register 1 of 10; prompt "11 of 12") READ | FIXED (PR #51) | repeat the 160-request experiment — NOT DONE |
| OCT01-FZ-05 registry + EventStream | FZ-05a / FZ-05b | **Equivalent, two halves.** 5a re-measured by me at `488129b`: every unknown ID → 200 and state in `_graphs` *and* `_queues`; linear to 5,000, no cap observed (VERIFIED then). 5b not measured | OPEN; FZ-D3 open | GATE-REGISTRY / GATE-EVENT-RETENTION |
| OCT01-FZ-06 event identity islands | FZ-06 and **DEBT-030** | FZ-06 ≈ OCT01-FZ-06 (15 of 16 `_emit_event` sites carry only `interaction_id`; four namespaces). **FZ-06 vs DEBT-030: OVERLAPPING, equivalence NOT demonstrated** (DEBT-030 = `CapabilityRequest.trace_id` fresh random UUID at 3 sites). Keep separate until every emission/construction path is covered | OPEN | GATE-EVENT-LINEAGE |
| OCT01-FZ-07 broad CI allowlist | FZ-07 + residual **R-1** | **NOT equivalent.** Register FZ-07 = "`tests` job discarded pytest's exit code" (fixed, PR #55). OCT01-FZ-07 = "34 accepted failures / cannot detect stale or overbroad exceptions". Partial overlap at most. R-1 is a distinct residual | FZ-07 fixed; **R-1 OPEN** | **Batch 1 = R-1 only** |
| DEBT-023 / CVE-2026-31431 | (register sync + `CURRENT_STATE.md`) | docs say the AF_ALG/AF_VSOCK mitigation is done; `main`'s `_seccomp.py` names neither family and `_net_proxy.py` does not exist on `main`. **VERIFIED** (docs ahead of code) | docs: resolved | GATE-DEBT023 |
| REM-004; CTX-EXPORT-001; DEBT-025; DEBT-028/029/036/015; DEBT-012; DEBT-031/032; platform scope | — | **NOT DONE** beyond the facts in §5/§7 | — | later batches |

## 4. Corrections to my own earlier statements (must propagate)
- I previously asserted **FZ-06 and DEBT-030 are "one defect"** (PR #87's text; the manifest draft §3 F4/§4). Under this prompt's standard that is **an inference, not a demonstrated equivalence.** PR #87 (open, unmerged) and the manifest draft should say "overlapping; equivalence unproven."
- I previously treated the register's `FZ-07` as the October audit's finding. It is **not** the same (§3).

## 5. Decision and conflict register
| # | Item | State |
|---|---|---|
| C1 | OCT01-FZ-07 vs register FZ-07/R-1 | different invariants; both histories preserved; Batch 1 applies the owner-directed R-1 disposition only |
| C2 | **R-1 scope**: the register's R-1 is the ` - ` truncation (candidate fix "split at first ` - ` outside `[...]`"); the prompt's `GATE-CI-ALLOWLIST` also requires an **approved failure signature** so an ID alone cannot excuse a different failure. The live gate matches **ID-only**. | **Owner decision needed:** confirm the broader scope and define the signature for the 34 entries |
| C3 | ADR-KERNEL-06 (accepted, on `main`) vs CTX-AUTH-002 / ADR-KERNEL-08: **no mention of either on `main`**; the competing design exists only on branches (`fix/ctx-auth-001b-rem004-authority-boundary-sep2026`, `fix/ctx-auth-002-reject-content-corroboration-authority-sep2026`, `preserve/ctx-auth-002-verified-99875d0-oct2026`, possibly more) | unresolved; preserve both |
| C4 | **DEBT-042 ID collision:** `main` already has `DEBT-042` (`SqliteStorage._fts_escape`) and `DEBT-043` (content-anchor defects); my PR #79 adds a *different* `DEBT-042` (privacy deletion sink) | PR #79 row must be renumbered; #79 is also 8 commits behind and `dirty` |
| C5 | Branch protection: live `enforce_admins: true`; owner chose "exempt admins" on Sept 19; the Oct audit CLAIMS `non_admins`. Who changed it, and whether deliberate, is **unrecorded** | register row corrected in PR #87 (open) |
| C6 | Register ↔ code gaps: FZ-02 status lags merged B2a/B2b (PR #83, dirty); CodeQL fixed-count docs 34 vs API 33 (earlier read; unresolved) | open |
| C7 | PR #25 (stale FREEZE_READY claim) was closed by another session *before* this prompt's no-close rule | informational |
| C8 | PR #88 records an owner-directed disposition on the creative-content-anchor response path (DEBT-042/043 stay open); **not FZ-01** | READ |
| C9 | Merge authority: `premerge_guard.py` pins merges to explicit owner authorization at a head SHA (per PR #88's text) | READ |

## 6. PR / branch report (heads via `refs/pull/*`; mergeability and checks are REPORTED from an earlier authenticated read, not re-fetched)
| PR | state | head | vs `main` | notes |
|---|---|---|---|---|
| #23 | merged | `30e8834` | — | CTX-AUTH-001b / ADR-KERNEL-06 implementation |
| #25 | closed | `57f053f` | — | stale; not merged |
| #41, #42 | merged | `7acbf3c`, `57dde35` | — | |
| #79 | open | `bcbe574` | 4 ahead / 8 behind, 3 files | privacy sink; `dirty`; **DEBT-042 collision** |
| #81 | open | `647b63e` | 13 ahead / 0 behind, 4 files | DEBT-028 (serialize same-`instance_id`) — **stacked: 13 commits** |
| #83 | open | `dda84f2` | 2 ahead / 8 behind, 1 file | register decisions; `dirty` |
| #86 | open | `6643309` | **62 ahead / 50 behind**, 24 files | sandbox B03 primitives |
| #87 | open | `917bb37` | 1 ahead / 0 behind, 1 file | DEBT-033/030 register rows (see §4) |
| #88 | open | `e634c41` | 1 ahead / 0 behind, 4 files | owner-directed disposition (C8) |
| #89 | open | `676f97a` | **48 ahead** / 0 behind, 7 files | DEBT-029 — **stacked: 48 commits**; scope must be isolated before review |
| #39, #40 | **not re-fetched** (API access lost) | | | |
All named PRs showed zero reviews and green checks at the last authenticated read; none is part of any candidate until selected, reviewed and integrated.

## 7. Supported-environment statement (READ; re-verify)
`pyproject.toml`: `requires-python >=3.11`, `chromadb==0.5.3`. CI (`ci.yml`): **Ubuntu, Python 3.12 only.** `release.yml` builds on Linux, Windows and macOS, but **tests run only on Linux/3.12** — Windows/macOS test coverage is **UNVERIFIED**; embedding-model paths are not exercised in the sandbox (no `torch`). No cross-platform claim is supported.

## 8. Required-gate matrix (status = current evidence only)
GATE-API-OUTCOME NOT STARTED · GATE-PROVIDER-OUTCOME partly implemented, open policy cases · GATE-SCHEDULER-ISOLATION UNVERIFIED vs gate · GATE-ADAPTIVE-SEMAPHORE UNVERIFIED vs gate · GATE-REGISTRY OPEN (measured) · GATE-EVENT-RETENTION BLOCKED (decision) · GATE-EVENT-LINEAGE OPEN · **GATE-CI-ALLOWLIST: Batch 1** · GATE-DEBT023 docs≠code · GATE-REM004 BLOCKED (ADR conflict) · GATE-CTX-EXPORT / GATE-DEBT025 owner decision · GATE-CROSS-DEBTS NOT DONE · GATE-RELEASE-INTEGRITY NOT DONE · GATE-TEST-HYGIENE NOT DONE (DEBT-012 suspected; see §9 note) · GATE-REVIEW / MANIFEST / ADMISSION / FINAL-VERDICT NOT STARTED.

## 9. Batch 1 acceptance package — R-1
**State: OPEN.** Register (`KNOWN_ISSUES.md` line 131 at `f13bfde`): `FAILED` IDs containing ` - ` are cut at the first ` - ` before allowlist matching; real pytest probing showed a real listed ID leaves the gate red (fail-closed), colliding truncated IDs trip the count cross-check, and **a hand-truncated entry can still tolerate a single failing ` - ` id** (false green). 0 of the 34 current entries contain ` - `. READ of `scripts/ci_test_gate.py` (244 lines): `parse_allowlist` takes non-comment lines verbatim *(line ref ~96–102)*; `parse_failed_ids` does `ln[len("FAILED "):].split(" - ", 1)[0]` *(~110)*; matching is `failed_ids & allowlist` / `failed_ids − allowlist` **by ID only** *(~178–181)*.
**Not yet demonstrated by execution** — the probe below was attempted and lost to a container reset.

**Defects to address (READ):** D1 ` - ` truncation; D2 ID-only matching (no failure signature/phase); D3 no validation of malformed/truncated allowlist entries; D4 an allowlisted ID can excuse a strict-XPASS failure (reported as `FAILED … [XPASS(strict)]`); D5 text-parsed IDs rather than a structured report; D6 (outside R-1, record only) no stale-entry detection — the script's docstring declares it a non-goal.

**Acceptance (from GATE-CI-ALLOWLIST, R-1 parser defect):** exact node IDs **and** a narrowly defined approved failure classification/signature must both match; an ID alone cannot suppress a different assertion failure; malformed/truncated entries cannot broaden exclusions; missing/incomplete report, collection/setup/internal errors, interruption, empty required runs, inconsistent exit status, unexpected xpass, unexpected failure phase and unclassified outcomes fail closed; parameter IDs containing ` - ` are not truncated; **existing allowlist entries stay unchanged unless individually justified** (preservation must not preserve overbroad matching); test the real gate and the drift check; **do not touch the strict ADR-KERNEL-07 D-4 xfail** (`tests/core/cognitive/test_creative_content_anchor.py`); record whether real CI ran or only local tests.

**Pre-fix probe (run in a fresh session; read-only):** write `/tmp/probe/test_probe.py` with `@pytest.mark.parametrize("v", ["a - b","a - c","plain"], ids=["a - b","a - c","plain"]) def test_p(v): assert v=="plain"`; `def test_env(): raise AssertionError("expected 3 got 4")`; `def test_ok(): pass`. Capture real pytest output and exit code for (i) `-k "(test_p and a - b) or test_ok"`, (ii) `-k "test_env or test_ok"`, (iii) all. Load the gate from `git show origin/main:scripts/ci_test_gate.py`, call `evaluate(output, exit_code, allowlist)` and print `dataclasses.asdict(verdict)`. Scenarios: S1 allowlist = the real ID `test_probe.py::test_p[a - b]`; S2 = hand-truncated `test_probe.py::test_p[a`; S3 = truncated prefix + `test_env` on the all-failures run; S4 = only `test_env` listed while it fails with a genuine AssertionError. **Guard against the trap:** print the gate file's blob hash and assert the module exposes `evaluate`; an empty result is meaningless until the probe is shown capable of producing output.

**Direction (not a decision):** prefer structured pytest reporting (a small plugin writing JSON: node ID, phase, outcome, exception type, plus a completeness marker) over parsing terminal text; keep the allowlist file byte-identical and carry the signature policy separately. **Prerequisite research:** the real failure signatures of the 34 listed tests under blocked connectivity — in GitHub CI they likely pass, so the list may be dormant; reproducing them locally needs `torch`/`sentence-transformers` and a network-blocked run. Cite pytest's documented exit codes and hook behaviour (`pytest_runtest_logreport`, `pytest_collectreport`, `pytest_sessionfinish`) when designing; this session did not consult them.

**Isolation and review target:** `git worktree add <path> -b fix/ci-gate-r1-parser-hardening-oct2026 origin/main` (re-pin first); one commit-set, frozen at an immutable SHA; review by a **separate** session/reviewer — absent that, status is `UNVERIFIED`. Bracket every test run with `git status` to detect and attribute test-generated changes (DEBT-012) instead of silently reverting them.

## 10. Batch 0 — still NOT DONE
Crosswalk rows for REM-004, CTX-EXPORT-001, DEBT-025, DEBT-028/029/036/015, DEBT-012, DEBT-031/032; re-fetch of PR checks/reviews/mergeability and of #39/#40 (needs a credential); a full read of `scripts/ci_test_gate.py`, `tests/test_ci_test_gate.py` (18 test functions, 67 cases per the register) and the allowlist's header semantics; the machine-checkable manifest; DEBT-023's exposure history (unknown — no logs).
