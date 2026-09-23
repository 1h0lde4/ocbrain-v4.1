# Packet G — Implementation/Readiness: Working Notes

---

## Track 1: Dependency reproducibility (`DEBT-032`) — implemented and verified

**Change:** `requirements.txt`'s chromadb line changed from `chromadb>=0.4.0,<1.0` to `chromadb==0.5.3` — the exact version tested and confirmed against the fixture during Packet F's `F-2`, matching what `release.yml` already pins. Chose the exact version actually tested, not a broader range (`<0.6.0`) that would have asserted untested territory — only `0.5.3` itself and `0.6.3` were ever directly verified.

**A real before/after, not an assumption:** re-ran the identical full-suite command from Packet E's baseline (`pytest -q --tb=no`), in the identical minimal-dependency sandbox. One accidental deviation caught and corrected mid-process: a plain `pip install -r requirements.txt` pulls every dependency, not just the changed line — this briefly installed the full ML stack (torch, transformers, sentence-transformers, trafilatura, ~2MB→554MB+ of new packages), which would have confounded the comparison by changing the environment class, not just the one variable under test. Caught via a disk-space check, reverted (uninstalled the unrelated additions, reinstalled just `chromadb==0.5.3` and `fastapi`), confirmed disk back to the exact prior level before re-running.

**Result:**

| | Before (Packet E, `chromadb==0.6.3`) | After (`chromadb==0.5.3`) |
|---|---|---|
| Collected | 1,507 | 1,507 |
| Passed | 1,501 | **1,506** |
| Failed | 6 | **1** |
| The 5 chromadb-schema failures | Present | **Gone** |
| `TestCtxAuth001ParserAcceptance` | Failed (expected) | Failed (expected, unchanged) |

All five chromadb-schema failures (`test_cache_concurrency`, `test_empty_retrieve`, `test_empty_action_rejected`, `test_execute_write_file`, `test_unknown_action_rejected`) now pass. The one remaining failure is exactly and only the known CTX-AUTH-001b tripwire — untouched, as it should be; this change has nothing to do with that finding.

**Disposition:** `DEBT-032` moves from "characterized, remediation recommended" to "implemented and empirically verified" — not merely argued from the release.yml evidence, but directly confirmed by re-running the exact baseline. The broader architectural point F-5 raised — CI still doesn't structurally test against the exact set `release.yml` ships (`numpy`, and the 18 other unbounded packages, remain unaligned) — is not resolved by this one-line fix and is not claimed to be; this closes the demonstrated instance, not the underlying pattern. That broader convergence (`release.yml` installing from `requirements.txt`, or CI additionally testing against `release.yml`'s exact pins) remains open, tracked in `DEBT-032`'s own reframed text.

---

## Track 2: Required CI/branch enforcement (`DEBT-033`) — implemented and verified

**Decision point surfaced to Moncif explicitly before applying anything**, since it materially changes repository behavior: GitHub branch protection's `enforce_admins` setting determines whether admin accounts (including the repository owner's own) are bound by required status checks, or can bypass them the way direct pushes have worked throughout this project's history. Moncif chose **exempt admins** — his own direct-push workflow continues unchanged; the protection binds non-admin contribution paths.

**Applied via the branch-protection API** (`PUT /repos/1h0lde4/ocbrain-v4.1/branches/main/protection`): required status checks `tests` and `drift-and-ownership` (the exact job IDs from `.github/workflows/ci.yml`, confirmed directly from the workflow file rather than assumed — neither job has an explicit `name:`, so GitHub uses the job ID as the check name), `strict: true` (a PR branch must be up to date with `main` before its checks count), `enforce_admins: false` per the decision above, no required review count (would deadlock any non-admin contribution with no second reviewer available), no additional push restrictions.

**Verified independently, not by trusting the `PUT` response**: a separate `GET` request confirms `required_status_checks.contexts = ['tests', 'drift-and-ownership']`, `strict = true`, `enforce_admins = false`, `allow_force_pushes = false`, `allow_deletions = false`.

**Named consequence, stated plainly:** this closes `DEBT-033`'s specific gap for non-admin contribution paths (a PR without passing CI can no longer merge). It does **not** close the gap for admin-authored direct pushes to `main` — including, notably, other concurrent Claude sessions operating with admin-level credentials, which this engagement has observed pushing directly to `main` more than once. That residual is the direct, known consequence of the exemption Moncif chose, not an oversight — recorded here so it's explicit rather than assumed away.

**Disposition:** `DEBT-033` moves from "characterized, recommendation offered" to "implemented and verified, with a stated, deliberate scope limit." Not classified as fully closed — the admin-bypass path remains open by design, and should be revisited if the direct-push-by-multiple-credentialed-sessions pattern continues to be a live concern.

---

## Track 3: Release artifact integrity (`DEBT-034`) — implemented, verification bounded as stated

**Deliberately minimal, surgical change, not a rearchitecture.** Considered and rejected removing the Android job's `|| true`: its own comment states the intent plainly ("ignore failures to ensure CI continuity"), and nothing in this packet's mandate is to second-guess that design choice — best-effort platform support that doesn't block the other three is a reasonable position on its own. The actual gap `F-4` found is narrower: that failure was not just tolerated, it was *invisible* all the way through to a published release. Fixed at the one point that already aggregates every platform's output: `.github/workflows/release.yml`'s `Create Release and Upload Assets` step now sets `fail_on_unmatched_files: true`. If the APK (or any other listed file) is missing when this step runs, the release action now fails loudly and the release does not publish — regardless of why the file is missing, not only the Android case specifically.

**Verification, bounded honestly as stated in the execution prompt:** this environment cannot trigger an actual Actions run. Verified instead: the YAML parses correctly (`yaml.safe_load`, full file, not just the changed fragment) and the field lands in the intended step under `with:`. `fail_on_unmatched_files` is confirmed as a real, documented, opt-in input of `softprops/action-gh-release` — established externally during `F-4`'s own investigation (that action's issue #383), not assumed.

**Disposition:** `DEBT-034` moves from "characterized, two options offered" to "implemented (the `fail_on_unmatched_files` option), verification bounded to syntactic/logical correctness." The `|| true` tolerance itself is left as-is, by deliberate choice stated above, not overlooked.

---

## Track 4: Supply-chain controls (`DEBT-035`) — implemented, verification bounded as stated

**Action SHA-pinning.** Looked up the exact current commit SHA behind each mutable version tag via the GitHub API (`git/refs/tags/{tag}`) rather than guessing or using a plausible-looking placeholder — all five resolved directly to commit objects, no extra dereference needed for an annotated tag. Replaced all 23 occurrences across both workflow files (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`, `softprops/action-gh-release@v2`) with `@<40-char-SHA> # v<N>` — the standard convention: the SHA is what's actually trusted, the comment keeps the human-readable version visible. Verified the occurrence count before and after matched exactly (23 → 23) before treating the change as complete, and that both workflow files still parse as valid YAML afterward.

**Dependabot.** Added `.github/dependabot.yml` with two ecosystems: `pip` (for `requirements.txt`) and `github-actions`. The second is not incidental — pinning by SHA closes the "a compromised tag silently updates" risk, but a SHA pin also doesn't self-update the way a mutable tag implicitly did; Dependabot's `github-actions` ecosystem is the mechanism that now proposes a reviewable PR bumping the pin when a new release exists, so the SHA-pinning fix and the Dependabot addition are a matched pair, not two independent items.

**Verification, bounded as stated in the execution prompt:** no way to trigger Dependabot itself or an actual Actions run from this environment. Confirmed instead: exact SHA lookups against the real GitHub API (not fabricated), occurrence-count integrity before/after the bulk replacement, and full-file YAML validity for all three touched/added files.

**Disposition:** `DEBT-035` moves from "characterized, four independent recommendations" to "two of four implemented (Action SHA-pinning, Dependabot), verification bounded as described." `pip-audit` in CI and a required-approval Environment for the release workflow remain open — not attempted this pass; recorded as still-open rather than silently dropped.

---

## Post-reconciliation verification finding: `tests` required check would have blocked every future merge — found and fixed

**Not a new track — a necessary follow-through surfaced by actually verifying Track 2, not just implementing it.** Ran `drift-and-ownership`'s two checks locally on the reconciled branch: `scripts/check_drift.py` reports all 15 checks passing, zero violations (confirms C-2's finding still holds after the CTX-AUTH-001b work merged in); the packet-ownership check correctly skips cleanly on this branch (not one of `h2_packet_ownership.json`'s declared branches).

Checking the `tests` check the same way surfaced something real: `TestCtxAuth001ParserAcceptance::test_injection_shaped_completion_line_is_not_accepted_as_a_hypothesis` — the intentional CTX-AUTH-001b tripwire, permanently red by design until ADR-KERNEL-06's provenance mechanism is implemented — is **not** present in `D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`, and `ci.yml`'s gating script has no exception for intentional failures, only environmental ones. Confirmed by reading the gate script directly: any `FAILED` node ID not in that file causes `exit 1`, unconditionally. This predates Track 2 — CI would already have been failing on this basis. What Track 2 changed is that this failure became **consequential**: with `tests` now required, no PR could merge, including this one.

**Resolved exactly as directed, not by any of the three options this finding was originally flagged with.** Checked the test's actual structure before touching anything: `TestCtxAuth001ParserAcceptance` is a single-method class, that method contains exactly one assertion, and the test's own inline comment already read "DESIRED FUTURE INVARIANT (CTX-AUTH-001) -- currently expected to fail" — nothing to isolate from; the whole test already was the one specific check. Added `@pytest.mark.xfail(strict=True, reason="CTX-AUTH-001b provenance acceptance pending ADR-KERNEL-06 implementation")` directly to that method.

**Verified, not assumed:** full suite re-run: `1514 passed, 1 xfailed, ... exit code 0`. Separately verified `strict=True`'s actual behavior — not just cited from memory — with a throwaway sandbox test outside the repo: a deliberately-passing `xfail(strict=True)` test reports `XPASS(strict)` as `FAILED`, exit code 1. Confirms the tripwire genuinely works: if CTX-AUTH-001b's provenance mechanism is ever implemented (or the test starts passing for any other reason), CI will fail until the marker is deliberately removed, not silently absorb the change.

**Freeze status unaffected, exactly as instructed:** this is CI bookkeeping, not an architectural resolution. CTX-AUTH-001b/REM-004 remains exactly as open as before; ADR-KERNEL-06 remains accepted-not-implemented. CI now correctly distinguishes "environmental failure" from "intentional architectural tripwire" instead of conflating the second into the first's mechanism -- it does not resolve what the tripwire is tracking.
