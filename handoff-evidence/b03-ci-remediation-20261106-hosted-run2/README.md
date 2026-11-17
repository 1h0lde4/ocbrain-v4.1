# HOSTED evidence: GitHub Actions run 43644902316 (success), B03 CI remediation, PR #86

Governing document: `/handoff.md` (repository root), **section 0a**. Read it first.

This directory is separate from `../b03-ci-remediation-20261106/` on purpose. That directory is local-lab evidence plus the hosted *baseline*, and its `README.md` and `SHA256SUMS` were left byte-identical. This one is the first **hosted** evidence of the remediated workflow.

## What this is, exactly

- Run: `43644902316`, event `push`, branch `integration/b03-ci-remediation-20261106`, head `a1aaffc3088ab70dc69c1de1d3c4f0d59bc37c38` (tree `0209f75e702b183a61256e072c6deb027cef805a`), conclusion `success`, created 2026-11-14T21:50:14Z.
- Jobs: `tests` 132600378060, `typecheck-b03` 132600378311, `drift-and-ownership` 132600378424 (all success).
- The four artifacts of that run, supplied by the user on 2026-11-17 10:09 UTC as `PR86_run2_43644902316_artifacts_bundle.zip` (the session's proxy cannot download them: see the notes, section 4). The bundle was received as a file attachment; its outer SHA-256 is `ce6763ea0556b720beb73e51d33c742ba2d3e6b1beb270c2ffa1f61354404bda`.
- It is evidence about the **integration branch head `a1aaffc`**, NOT about PR #86's own head (`a887e148`), which has never run the remediated workflow (handoff F12/U9).
- It does not contain the original assignment text, and not the artifacts of the failed run 1 (`43643507359`).

## Layout

| Path | Content |
|---|---|
| `bundle/PR86_run2_43644902316_artifacts_bundle.zip` | The attachment exactly as received (the attachment's `707b3ab6-` filename prefix was dropped). |
| `artifacts/run-43644902316-*.zip` | The four GitHub artifact zips, extracted from the bundle, unchanged. `run-43644902316-MANIFEST.txt` is the bundle author's summary: **a claim, not proof** (every figure in it was re-derived, see below). |
| `unpacked/<artifact>/` | The files inside each zip, for reading: `docker-preflight/docker-preflight.json`, `pytest-output/pytest-output.txt` and `pytest-exit-code.txt`, `drift-report/drift-report.json`, `mypy-b03/mypy-b03.txt`. |
| `GITHUB_DIGESTS.sha256` | GitHub's own digests of the four zips (from the API's `digest` field), in `sha256sum -c` format. |
| `verification/` | `github_artifact_digests_api_response.txt` (artifact id, size, digest as the API returned them on 2026-11-17); `artifact_hash_check.txt` (the check below, with its output); `gate_rerun_on_hosted_output.txt` (the repo's `scripts/ci_test_gate.py` run on the hosted pytest output with the unchanged D10 list: exit 0); `skip_step_rerun_on_hosted_output.txt` (the `run:` block of the "Assert the Docker-backed tests ran" step, extracted from `ci.yml`, run on the hosted output: exit 0). |
| `review/` | `review_request_b0a1143_a1aaffc.md` (the brief for the independent review that could not run; reusable verbatim), `mutate_n1_n4.py.txt` (stored as `.py.txt` on purpose: the B03 inertness pin scans every `*.py`) and `n1_n4_mutation_output.txt` (7 of 7 mutants killed). |
| `second_session_notes_20261117.md` | Everything else the continuing session established, including what is NOT preserved here (section 5). |
| `SHA256SUMS` | SHA-256 of every other file in this directory. |

## How to re-verify (from the repository root)

```
cd handoff-evidence/b03-ci-remediation-20261106-hosted-run2
sha256sum -c SHA256SUMS            # this directory is intact
sha256sum -c GITHUB_DIGESTS.sha256 # the four zips equal GitHub's digests (the independent check)
```

To check GitHub's digests again, read them unauthenticated (public repo): `curl -sS https://api.github.com/repos/1h0lde4/ocbrain-v4.1/actions/runs/43644902316/artifacts` (artifacts expire 2027-02-12). Downloading the zips needs a network path to `productionresultssa8.blob.core.windows.net`, which the sandbox proxy blocked.

## What the artifacts show (re-derived from the bytes, not copied from the manifest)

| Artifact | Result |
|---|---|
| docker-preflight | `result: passed`, `failed_stage: null`; image `python:3.12-slim`, id and RepoDigest `sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`; 1 pull attempt; 19 required executables; `capability_probes: true`, `capabilities_rc`, `executables_rc`, `digest_run_rc`, `rc` all 0; Docker 29.4.2, linux/x86_64. |
| pytest-output | `2400 passed, 19 skipped, 9 xfailed, 2 warnings in 209.80s`; exit code file `0`; no FAILED/ERROR line; the 19 skips are 18 cgroup-v1 and 1 gcc-multilib; no Docker-prerequisite skip. |
| drift-report | `summary: total 15, pass 15, violation 0`. |
| mypy-b03 | mypy 2.4.0 and pytest 9.2.0 on Python 3.12.16; default and `--strict`: "Success: no issues found in 2 source files"; exit codes 0 and 0. |

Limits: these are logs of one run on one runner at one time. The image tag `python:3.12-slim` is floating (handoff N6: the digest above is what that tag resolved to on 2026-11-14, not a pin). The artifact zips cannot by themselves prove which run produced them; the match with the digests that the GitHub API lists for run 43644902316 is what ties them to it.
