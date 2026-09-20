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
