# Freeze Remediation — Batch 1A report (R-1 hardening) and reviewer package

**Status: IMPLEMENTED · verified locally and in ONE real CI run · NOT independently reviewed → overall `UNVERIFIED`.** Posture `NOT_FREEZE_READY`. Transfer record, not an authority. **Not merge approval.** The independent review of `667cb94` (**NOT APPROVED FOR MERGE**) is preserved and is not superseded by anything here.

## 1. Identity
| Item | Value |
|---|---|
| Base `origin/main` (unmoved during the work) | `2491ae469edd6ef1267a14604c4f8f40d698f7ea` |
| Original review target (UNCHANGED, own branch) | `667cb94dfc94a82d3218b596fd5aee4e4c73c317` on `fix/ci-gate-r1-structured-report-oct2026` |
| **Batch 1A final candidate (immutable review target)** | **`a0c12b58b7d2329fdec30580d11acb84ec5279f6`** on `fix/ci-gate-r1a-hardening-oct2026` |
| Commits on top of 667cb94 | `e1e6393` hardening · `321e56f` CI annotations (diagnostics) · `a0c12b5` test determinism fix |
| Draft PR | #107, **draft, open, not merged**; mergeable_state clean; body states the NOT APPROVED attestation |
| Review diff | `git diff 2491ae4..a0c12b5` — 8 files, +1368/−12 |
Not done (prohibited): no merge, no `main` change, no PR closed, no protection change, no tag.

## 2. Review findings → disposition (findings from the independent review of 667cb94)
| # | Finding | Fix | Evidence |
|---|---|---|---|
| 1 | Exception type collected but ignored; AssertionError mentioning the host excused | Matching requires an **exact fully-qualified type** + message tokens; a **deny list** vetoes by type (incl. base classes via `mro`) and HTTP status | reproduced on 667cb94 (gate exit 0 while pytest exit 1), then regression tests; mutants killed |
| 2 | PROPOSED policy operational | `status` ∈ PROPOSED/ACCEPTED/REVOKED; **only ACCEPTED (with `decision_ref`) can excuse**; invalid → gate error exit 2. Shipped policy is **PROPOSED** (diagnostic mode: listed failures stay red, chains printed + uploaded) | reproduced on 667cb94 (`_status` never read); lifecycle tests |
| 3 | Non-strict XPASS counted as an ordinary pass | categories `xpassed`/`xfailed`/`skipped` kept apart; ≥1 **ordinary** pass required | reproduced on 667cb94 (xpass-only suite → exit 0); tests |
| 4 | Report completeness weak | schema 2: collection inventory, per-test terminal outcome, outcome consistency, duplicate/unknown/uncollected records, `counts` re-derived and cross-checked, six outcome counts reconciled with pytest's summary | 18 tamper cases + mutants |
| 5 | Environment unrepresentative | see §5: lightweight env, pytest 8.0.0/8.4.2/9.2.0, and a real GitHub Actions run with declared dependencies — **kept as separate claims** | §5 |
| 6 | Docs, count discrepancy, artifact secrets | D10 header + `KNOWN_ISSUES.md` R-1 reconciled (**R-1 stays OPEN**); collected counts measured (below); credentials redacted before the report is written | tests; counts |
Collected counts (pytest `--collect-only`): **base 2185** (= 2184 passed + 1 xfailed), **candidate 2286** (= 2285 passed + 1 xfailed). Earlier "40/41 new tests" wording is superseded.

## 3. What the candidate does (summary)
`scripts/ci_gate_report.py` (plugin, schema 2) records: collection inventory; per-phase records with category `passed|failed|skipped|xfailed|xpassed|xpass_strict|error|phase_ok`; exception chain (≤8: type, mro, **redacted** message, errno, http_status); counts; completeness. `scripts/ci_test_gate.py::evaluate_report` is red on: exit ∉{0,1}; malformed/truncated allowlist entry; report missing/stale/incomplete/faulty/wrong schema; exitstatus mismatch; collection/setup/teardown errors; inconsistent records; uncollected/missing/duplicate tests; counts or text-summary disagreement; no ordinary pass; strict XPASS; and any listed failure unless policy is ACCEPTED **and** the failure is in `call` **and** its chain matches an approved class (exact type + tokens, no deny). In GitHub Actions a red verdict also prints ≤10 annotations (reasons first, then chains) so diagnostics are readable without log access.
**Unchanged, verified against `main`:** the 34 allowlist entries (content+order), `tests/core/cognitive/test_creative_content_anchor.py` (strict ADR-KERNEL-07 D-4 xfail), `scripts/check_drift.py`. `ci.yml` is identical to `667cb94` (differs from `main` only by that wiring). `tests/test_ci_test_gate.py`: 3 lines changed vs main (helper signature, fake-pytest shim, scratch-path relocation) + 1 test added; **no original assertion changed**. The legacy text path still contains R-1 and is unused by CI.

## 4. Mutation testing (each broken rule must turn a test red; sources restored byte-identical)
30 gate/plugin mutants (type ignored, tokens ignored, policy status unchecked ×2, deny ignored/base classes/http status, xpassed-as-pass, pass check removed, counts/text cross-check, terminal-outcome, uncollected, duplicate phase, category consistency, strict-xpass, decision_ref, status validation, allowlist validation, exitstatus, complete flag, phase restriction, setup/teardown errors, inventory; plugin: redaction, xpassed category, inventory, stale report, mro, http_status): **30/30 killed**. Two initially survived because the matcher's own status/phase checks were unexercised → unit tests added → killed. One mutant was "killed" only by a crash (my sloppy mutant) → redone faithfully. Annotation behaviour: 4 mutants; one was equivalent dead code (removed), replaced by a cap test that kills the cap mutant.

## 5. Verification evidence — three separate environments
**A. Lightweight local (Py 3.12.3, pytest 9.2.0, no torch)** — LOCAL, not CI: full CI simulation (`pytest tests/ -p scripts.ci_gate_report`, exit via `PIPESTATUS`, also with `CI=true GITHUB_ACTIONS=true`): **2285 passed, 1 xfailed, exit 0**; real gate on that report exit 0; `check_drift.py` exit 0. Gate test files: **168 passed** (with and without CI variables).
**B. pytest 8.x** — isolated venvs: **pytest 8.0.0: 168 passed; 8.4.2: 168 passed** (`--noconftest`, gate test files only).
**C. Real GitHub Actions, declared dependencies** (PR #107; the only real-CI evidence; ONE run per SHA):
| Run | SHA | Result | What it showed |
|---|---|---|---|
| 41355742895 | `e1e6393` | tests job **failed at the gate step** | cause **not visible** (log/artifact redirect to blob storage unreachable from the sandbox, network policy). Probably the same cause as the next row; **UNVERIFIED** |
| 41407716770 | `321e56f` | tests job **failed at the gate step** | annotations (the new diagnostics) show the only reason: **my own test** `test_very_long_node_id_signature_survives_terminal_width` failed because pytest's `running_on_ci()` disables terminal truncation when `CI` is set, so its precondition did not hold on Actions. **The gate was right; the test was non-deterministic across environments.** Reproduced locally with `CI=true`. |
| 41408979390 | `a0c12b5` | **success**: all steps, gate step success, 0 R-1 annotations; deps install ~1m14s, suite ~4m | the gate in report mode ran with the shipped **PROPOSED** policy and went green |
**Inference (from C, one run):** under a PROPOSED policy any failing allowlisted test would have turned the gate red; it did not ⇒ **none of the 34 listed tests failed in that CI run**; the allowlist appears dormant on CI. Consequence: **there are no real exception chains to calibrate the signature policy against**, so Q3 **cannot be decided from evidence**. Limits: a single run; I could not read the step log or artifact; versions of `sentence-transformers`/pytest installed on the runner are unknown to me.
**D. Local environment with declared heavy dependencies (torch/sentence-transformers):** attempted; the download stalled (sandbox paused; clock jump) and was abandoned → **UNVERIFIED locally**; environment C stands in for it.
**Correction of an earlier claim:** "long node IDs lose the message at 80 columns" holds **only outside CI** (pytest truncates unless `CI`/`BUILD_NUMBER` is set or `-vv`). The structured report remains the correct design; the claim is narrowed.
**Side effects (DEBT-012), reproducible:** `pytest --collect-only` alone dirties `data/context.sqlite`; a full run also dirties `config/models.toml`, `config/settings.toml`, `config/sources.toml`. All were clean before; restored with `git checkout --`; not part of this change; DEBT-012 and PR #91 remain **separately tracked and not reconciled here**.

## 6. Acceptance checklist (the Batch 1A criteria)
POLICY: PROPOSED cannot suppress ✔ · only owner-accepted can operate ✔ (mechanism; no owner verification beyond a reviewed file edit) · types + conditions matched ✔ · HTTP 401/403/404 and assertions denied ✔ (candidate lists only; unvalidated against real chains).
REPORT: schema/outcome validation ✔ · phase/collection completeness ✔ · all six outcome classes reconciled ✔ · xpass-only rejected ✔ · truncation/malformed ✔.
VERIFICATION: pytest 8.x + 9.x ✔ · legacy tests preserved ✔ · mutation ✔ · declared-dependency environment ✔ via CI run only · **real exception chains from Actions: none exist in the observed run** ✗ (nothing to obtain).
GOVERNANCE: 34 entries ✔ · D-4 xfail ✔ · `check_drift.py` ✔ · docs reconciled ✔ · DEBT-012/PR #91 tracked separately ✔ · **independent review of the final immutable commit: NOT DONE ✗**.

## 7. Reviewer package
Target: `git diff 2491ae4..a0c12b5` (or `667cb94..a0c12b5` for the 1A delta). Please check independently: (a) any path in `evaluate_report` returning ok with an unexplained failure; (b) exact-type matching limits (subclasses are not inferred; lists are candidates); (c) that PROPOSED can never excuse (also via direct `_matches_class`); (d) redaction coverage (`ci_gate_report.redact`); (e) the 3 changed helper lines in `tests/test_ci_test_gate.py`; (f) whether ≥1 more CI run is wanted to check determinism. **A reviewer must be a separate session; none has reviewed this.**

## 8. Risks / open items
1. Signature class: candidate lists are **unvalidated**; with no real failures observed, Q3 has no evidence. Owner options: keep PROPOSED (listed failures would stay red if they ever appear), or decide the policy by other authority.
2. `ACCEPTED` is activated by a file edit citing `decision_ref`; nothing verifies that the reference is a real owner decision.
3. One real CI run per SHA; I never saw the step log or the artifact (network policy; allowing `*.blob.core.windows.net` would let a session read them). Annotations are the only CI-side evidence.
4. pytest/dependency versions on the runner unknown; pytest ≥10 untested; `pytest-xdist` unsupported (fails closed).
5. Legacy text path retains R-1 (unused by CI) — recommend removal in a follow-up the owner approves.
6. PROPOSED + an allowlisted test failing in a future CI run ⇒ red build by design (diagnostic mode).
7. Out of scope/unchanged: stale-allowlist-entry detection, DEBT-012 fix, DEBT-031 misclassification, PR #91 reconciliation, Batch 2.

## 9. Recommendation
Independent review of `a0c12b5` (separate session). Owner decisions: Q3 (given no observed failures: keep PROPOSED?), whether to remove the dormant allowlist/legacy path later, and when to authorize Batch 2. **Do not merge PR #107 and do not start Batch 2 without explicit authorization.** Token rotation remains recommended.
