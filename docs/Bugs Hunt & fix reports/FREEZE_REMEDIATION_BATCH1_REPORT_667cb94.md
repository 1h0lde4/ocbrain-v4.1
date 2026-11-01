# Freeze Remediation — Batch 1 report (R-1, GATE-CI-ALLOWLIST) and reviewer package

**Status: IMPLEMENTED · locally verified · NOT independently reviewed · NOT run in CI → overall `UNVERIFIED`.** Posture remains `NOT_FREEZE_READY`. This document is a transfer/review record, not an authority.

## 1. Identity
| Item | Value |
|---|---|
| Base (`origin/main`, unmoved during the work) | `2491ae469edd6ef1267a14604c4f8f40d698f7ea` |
| **Immutable result SHA** | **`667cb94dfc94a82d3218b596fd5aee4e4c73c317`** |
| Branch (remote, new, non-forced) | `fix/ci-gate-r1-structured-report-oct2026` |
| Gate blob on base (unchanged since `f13bfde`) | `934251744567965d5b4c7919d39bf8554fddaee5` |
| Not done (prohibited) | no merge, no `main` change, no PR closed, no protection change, no tag. No PR opened (owner call). |

## 2. R-1 state and mapping (FACT, executed)
Base gate truncates `FAILED` ids at the first ` - ` and matches by id only. Re-measured on `2491ae4` (harness: `evidence/harness.py` (next to this report); gate blob asserted; pytest exit codes asserted ∈{0,1}; real exit codes 1,1,1):
S1 red (a legitimately listed ` - ` id can never be tolerated) · **S2 green — false** (hand-truncated entry excuses a genuine `AssertionError`) · S3 red (count cross-check catches collisions) · **S4 green — false** (id-only match excuses any failure of a listed test).
**Long-id inference confirmed:** at `COLUMNS=80` pytest drops the `- message` part of a long `FAILED` line, so the exception type is unavailable from text — text parsing cannot meet the signature requirement.
Register mapping: `KNOWN_ISSUES.md` R-1 (parser residual). Kept **distinct** from historical OCT01-FZ-07 (no crosswalk equivalence claimed). Binding disposition applied per the prompt's GATE-CI-ALLOWLIST (R-1 = freeze blocker).

## 3. What changed (6 files, +771/−6)
| File | Change |
|---|---|
| `scripts/ci_gate_report.py` (new) | stdlib pytest plugin → atomic JSON report: nodeid, phase, outcome, strict-xpass, exception chain (≤8, via `__cause__/__context__`), `schema`, `complete`, `exitstatus`, `plugin_fault`. Deletes stale report at start; writes only at `sessionfinish`. |
| `scripts/ci_test_gate.py` | `evaluate_report`, `load_policy`, `validate_allowlist_entries`; CLI `--report` + `--signature-policy` (must be given together). **Legacy `evaluate()`/text path unchanged.** Docstring clause updated. |
| `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURE_SIGNATURE.json` (new) | class `hf_hub_unreachable` (phase `call`; an exception in the chain mentions `huggingface.co`). **PROPOSED.** |
| `.github/workflows/ci.yml` | pytest loads the plugin (`PYTHONPATH` = workspace); gate step uses `--report`/`--signature-policy`; text `--output` kept as cross-check; report uploaded as artifact. |
| `tests/test_ci_gate_report.py` (new) | 41 tests, real pytest → real plugin → real gate CLI. |
| `tests/test_ci_test_gate.py` | **Only the fake-`pytest` shim changed** (it now writes the structured report the real plugin would, via `_synth_report`). **No assertion changed**; 65 of its 67 cases pass untouched, the other 2 needed the shim change (see §7 risk 4). |
**Byte-identical to `main` (verified `git diff --quiet`):** `D10_KNOWN_ENVIRONMENTAL_FAILURES.txt` (34 entries), `tests/core/cognitive/test_creative_content_anchor.py` (strict ADR-KERNEL-07 D-4 xfail), `scripts/check_drift.py`.

## 4. Rules enforced by `evaluate_report` (fail closed)
Tolerated **only if** exact id ∈ allowlist **and** phase=`call` **and** not strict XPASS **and** exception chain matches an approved class. Also red on: exit ∉{0,1}; any malformed/truncated allowlist entry (balanced brackets, `path.py::…`, no stray whitespace/CR); report missing/unparsable/`schema≠1`/not `complete`/`plugin_fault`; `report.exitstatus≠exit code`; collection errors; setup/teardown failures (never excused); exit 0 with failures / exit 1 without; no passed test; text-summary cross-check disagreement or absent summary. Parameter ids containing ` - ` are compared whole.

## 5. Verification evidence (all LOCAL — no CI)
Env: Python 3.12.3, pytest 9.2.0, pytest-asyncio 1.4.1, chromadb 0.5.3, no torch, Linux. Every run bracketed by `git status`.
| Command | Result |
|---|---|
| baseline `pytest -q` on `2491ae4` | **2184 passed, 1 xfailed**, exit 0 (66.49 s) |
| `pytest tests/test_ci_gate_report.py` | 40 passed (+1 wiring test added after = 41) |
| `pytest tests/test_ci_test_gate.py tests/test_ci_gate_report.py` | 107 passed |
| **CI simulation** (`bash`, `PYTHONPATH=$PWD pytest tests/ -q --tb=short -p scripts.ci_gate_report --ci-gate-report=… \| tee`; exit via `PIPESTATUS`) | **2225 passed, 1 xfailed**, pytest exit **0**; report `complete=True`, `exitstatus=0`, 6678 records, no fault |
| real gate on that report (`--report --signature-policy`) | **exit 0** |
| `scripts/check_drift.py` | **exit 0**, DRIFT-14/15 PASS |
**Mutation checks (rule broken → intended test goes red; gate restored byte-identical):** signature-always-matches → S1b + S4 red · allowlist validation off → S2 red · strict-XPASS excused → xpass test red (reason text) · setup/teardown errors ignored → both error tests red · exitstatus cross-check off → tamper test red · `complete` ignored → tamper test red.
**Pre/post for S1–S4 through the real path** (new tests): S1 listed ` - ` ids + matching signature → **tolerated** · S1b listed ` - ` id, different failure → **red** · S2 truncated entry → **red** · S3 colliding prefixes → **red** · S4 listed id, genuine `AssertionError` → **red**. Long node id at `COLUMNS=80` with matching signature → tolerated (the report carries what text lost).
**Side effect (DEBT-012), VERIFIED reproducible:** every full run dirtied `config/models.toml`, `config/settings.toml`, `config/sources.toml`, `data/context.sqlite` (tree was clean before). Diff saved in `evidence/debt012_*`. Restored with `git checkout --` (nothing pre-existing was lost); **not part of this change**.
**Local vs CI:** no workflow run exists for `667cb94` (`actions/runs?head_sha=` → `total_count 0`). CI triggers only on push to `main`/`h2/**`/`integration/**` and PRs to `main`, so the `fix/…` branch cannot trigger it; a PR to `main` would. **Real CI: NOT RUN → UNVERIFIED.**

## 6. Reviewer package
Review target: **`git diff 2491ae4..667cb94`** (6 files). Governing contract: prompt §3 `GATE-CI-ALLOWLIST` (acceptance text in Batch 0 report §9). Pre-fix behaviour: §2 above + `evidence/harness.py` (next to this report). Please independently: (a) read `evaluate_report` for any path that returns `ok` while a failure is unexplained; (b) check the plugin under the CI pytest (unpinned `>=8.0.0`; only 9.2.0 tested); (c) decide the signature class (open owner question); (d) run the real workflow via a PR to `main`; (e) confirm the 2 wiring-test shim edits don't weaken them. **A reviewer must be a separate session — none has reviewed this.**

## 7. Risks / open items
1. **Signature class is PROPOSED and unvalidated.** Real failure signatures of the 34 listed tests are unknown (they need torch/sentence-transformers with huggingface.co blocked; this sandbox lacks torch and the tests *pass* here). If real failures don't mention `huggingface.co`, **CI goes red** — the change is *stricter for the existing 34 entries*, by design. If those tests pass in CI (likely), the list is dormant and CI is unaffected. Cannot be confirmed without CI logs.
2. pytest version: tested only 9.2.0; CI installs `>=8.0.0` (latest). The plugin uses documented hooks (`pytest_runtest_makereport` hookwrapper, `logreport`, `collectreport`, `sessionfinish`); not run on 8.x.
3. `pytest-xdist` unsupported: chains would be lost → fail closed (not used today).
4. Wiring tests: the 2 cases that expect a green job needed the fake `pytest` to emit a report — a necessary consequence of moving CI to report mode, visible in the diff.
5. The legacy text path still contains R-1 (kept so existing tests pinning it stay valid); it is no longer used by CI → recommend removal in a follow-up the owner approves.
6. Defence in depth: a strict XPASS has an empty chain so it could never match a signature anyway; the explicit rule is redundant by design.
7. Out of scope, unchanged: stale-allowlist-entry detection (OCT01-FZ-07 residual / D6), DEBT-012 fix, DEBT-031 misclassification.

## 8. Owner questions (still open)
Q3 approved failure class for the 34 entries (and whether the proposed one is acceptable) · open a PR to `main` to obtain real CI? · authorize a separate reviewer session · authorize Batch 2 (scheduler isolation).

## 9. Recommendation
Hold at this checkpoint. Next: independent review of `667cb94` + a PR-triggered CI run; ratify or replace the signature class. **Do not start Batch 2 until authorized.**
