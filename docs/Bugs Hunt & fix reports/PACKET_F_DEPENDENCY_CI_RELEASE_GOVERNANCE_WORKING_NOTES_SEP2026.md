# Packet F — Dependency / CI / Release Governance: Working Notes

Findings recorded as produced. Taxonomy per the execution prompt.

---

## Finding F-1: CI's known-failures allowlist mislabels 5 of its 34 entries — chromadb fixture incompatibility filed under "Hugging Face Hub connectivity"

**Register checked first: no prior entry covers this file or this mechanism. Genuinely new.**

`.github/workflows/ci.yml`'s `tests` job does not gate on pytest's raw exit code. Instead: it runs the full suite (`pip install -r requirements.txt` — the *full* dependency set, unlike Packet E's minimal-dependency sandbox), extracts the list of `FAILED` node IDs, and fails the build only on any failure **not** already present in `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`. This is a deliberate, documented, reasonable pattern for handling a stable set of environment-only failures without permanently red-lighting CI.

**That file's own header attributes its entire 34-item list to one cause:** "Hugging Face Hub connectivity class... these tests need huggingface.co reachability that this sandboxed environment (and, presumably, a typical CI runner without a configured HF mirror) does not have." It also states the set was "independently, repeatedly reconfirmed byte-for-byte identical across five separate checks in one session (D3, D7, D11, the H2 integration, and this D10 packet itself)" — a different, earlier initiative (`K4.2-H2`) than this freeze audit's own C/D/E/F/G sequence.

**Five of the 34 listed node IDs are, by exact name, identical to Packet E's five chromadb-schema failures:**

```
tests/test_break_concurrency.py::test_cache_concurrency
tests/test_break_empty_db.py::test_empty_retrieve
tests/test_system_ctrl.py::test_empty_action_rejected
tests/test_system_ctrl.py::test_execute_write_file
tests/test_system_ctrl.py::test_unknown_action_rejected
```

Packet E traced these to the byte level: `KeyError: '_type'` raised entirely inside chromadb's own `_load_config_from_json_str_and_migrate`, reading a committed fixture (`modules/{mock,system_ctrl,empty_test}/knowledge.db/chroma.sqlite3`) whose `config_json_str` column is a literal `'{}'` — a newer-generation chromadb collection format that the pinned `0.6.3` can't migrate. Confirmed by successfully reading a copy of the same fixture under chromadb 1.5.9. **This failure involves zero network I/O and would occur identically with perfect internet access, a configured HF mirror, or any other network condition — it cannot be a Hugging Face Hub connectivity failure by mechanism.**

**Why the mislabeling is plausible and low-malice:** the D10 verification process confirmed the *set* is stable ("byte-for-byte identical" across five checks) — that's a real, valid verification of *stability*, not of *root-cause accuracy per entry*. In whatever environment the K4.2-H2 initiative ran (evidently a full-dependency one, given the file's own framing), both failure classes were almost certainly present simultaneously — genuine HF-unreachable failures alongside these 5 chromadb ones — and all 34 got attributed to the one diagnosed cause without each entry being individually root-caused. This is exactly the kind of thing this packet's job is to catch.

**Why it matters practically, not just as a correction:** if HF connectivity is ever fixed in CI (a configured mirror, as the file's own comment anticipates), whoever checks whether that resolved "the 34 known failures" will find 5 stubbornly remain, with the file's own documentation offering no explanation why — because the true cause (a stale dependency pin against committed fixtures) is a completely separate problem this file doesn't mention at all.

**Classification: DOCUMENT-ONLY, but the mechanism it labels is real and correctly gated (LIVE-ENFORCED).** The CI gate itself works exactly as designed — new failures fail the build, known ones don't — that enforcement is genuine. What's inaccurate is the causal label attached to a subset of the known list, not the gate's function.

**Disposition:** split the file's framing — either a second, explicitly separate section for the 5 chromadb-schema entries with the correct root cause noted (mirroring Packet E's classification), or at minimum a comment on those 5 lines correcting the attribution. Low-cost, high-value fix for whoever next relies on this file to reason about CI health. Not implemented here — characterization, consistent with how Packet E's own chromadb disposition was left to Moncif.

**Not yet checked:** whether the other 29 entries are genuinely HF-connectivity failures, as opposed to some other, third mislabeled cause. Given the exact match on all 5 chromadb-specific names and the mechanism-level certainty that they can't be HF-related, confidence in *this* finding doesn't depend on auditing the other 29 — and per Moncif's standing instruction, installing the heavy ML stack to verify the other 29 is not justified by any question currently open. Flagged as a bounded limit of this finding, not a gap papered over.

---

## Finding F-2: `release.yml` already pins the working chromadb version; `requirements.txt` was never tightened to match

**Checked first: no existing register entry tracks the core chromadb pin/fixture issue itself (Packet E characterized it in working notes; F-1 is about the CI allowlist's mislabeling, a distinct thing). This is the first dedicated entry for the core issue, now substantially sharpened.**

`.github/workflows/release.yml` — the workflow that actually builds every shipped artifact (Linux/Windows/macOS/Android) — does not rely on `requirements.txt`'s loose `chromadb>=0.4.0,<1.0` constraint alone. Before installing requirements, all three desktop build jobs run `pip install chromadb==0.5.3 numpy==1.26.4 scipy==1.13.1` — an **exact** pin, overriding whatever `requirements.txt` would otherwise resolve.

**Tested directly, on a throwaway copy, original never touched (same discipline as Packet E):** installed `chromadb==0.5.3` and pointed it at a copy of the same `system_ctrl` fixture that fails under `0.6.3`. **It read successfully.**

This closes the loop Packet E left open. The most likely explanation, consistent with all the evidence: whoever wrote `release.yml`'s exact pin did so because they'd already hit this exact incompatibility and pinned around it — but that knowledge was never propagated back into `requirements.txt`, which is what `ci.yml`'s test job, and any developer running a plain `pip install -r requirements.txt`, actually gets. The release pipeline has been silently correct; the test/dev pipeline has been silently wrong, and CI's own known-failures allowlist (`F-1`) has been quietly absorbing the resulting failures rather than surfacing the mismatch.

**This substantially sharpens Packet E's left-open disposition.** Of the three options Packet E named (regenerate fixtures / relax the pin / quarantine), there is now a fourth, better-evidenced option: **tighten `requirements.txt`'s chromadb constraint to match what `release.yml` already proves works** — `==0.5.3` or at least `<0.6.0`. This requires no fixture regeneration and no test quarantining; it makes the test/dev environment match the one that's already known-good.

**Classification: PARTIAL** — the release pipeline has live, correct dependency governance for this package; the test/CI/local-dev pipeline does not, and the two have silently diverged.

**Disposition, offered as a strong recommendation, not implemented here:** align `requirements.txt`'s chromadb constraint with `release.yml`'s proven `0.5.3` pin. This is the single highest-value, lowest-risk fix surfaced by either Packet E or Packet F — it's empirically verified, requires touching one line, and would make Packet E's 5 chromadb failures disappear from the *minimal-dependency sandbox* baseline entirely (F-1's mislabeling issue would also become moot for those 5, since they'd stop failing at all). Left for Moncif to decide and apply, consistent with "characterization, not remediation."

---

## Finding F-3: `main` has no branch protection — the explicit kernel/capability-boundary connection

**Register checked first: no prior entry covers repository-level branch protection. Genuinely new, and this is the finding that directly answers Moncif's framing for this packet — not CI-in-the-abstract, but whether a governance gap here has consequences for the kernel/capability boundary.**

Queried GitHub's branch-protection API directly for `main`: `"Branch not protected"`, a clean 404. Confirmed this isn't a permissions artifact — the credential used has `admin: True` on the repository, so an actual protection rule would have been visible. There are no required status checks, no required reviews, no restriction on direct pushes to `main`, and no protection against force-push or deletion.

**The direct connection to Packet C:** `C-2` established that `scripts/check_drift.py` contains a real, correctly-implemented static check (`DRIFT-05`) that fails if any worker calls `GovernanceKernel.evaluate_action()` directly instead of through the non-overridable base class — and that finding leaned on this check as evidence the base-class governance pattern is "structurally un-bypassable." That characterization needs one precise qualification, not a retraction: `check_drift.py` **runs** in CI (`.github/workflows/ci.yml`'s `drift-and-ownership` job, on every push and PR to `main`) — that part is accurate and unchanged. What Packet C didn't check, because it wasn't yet this packet's territory, is whether a failing result from that job can actually **stop** code from reaching `main`. It cannot. With no branch protection, a failing `drift-and-ownership` job is advisory — visible in the PR/push UI, but nothing prevents a merge or a direct push regardless of its result.

**Stated at the right scope, not overclaimed:** this does not reopen C-2 or C-7, and it is not evidence of an active bypass — every governance trace in Packet C was about the *running application's* execution path, which is unaffected by this finding (a merge doesn't change what's already deployed or running). What it does establish is a **second, independent trust assumption** underneath the first: Packet C's governance-boundary conclusions hold *for code that is actually running*, and depend on that code having been written correctly in the first place — a property that `check_drift.py` verifies but branch protection does not enforce. In a single-maintainer, local-first project this may be an entirely reasonable, deliberate trust model (the same shape as `DEBT-025`'s loopback-binding assumption) — but it is currently implicit, not stated anywhere, and it means a bad or malicious commit reaching `main` directly is limited only by who has push access, not by any automated gate.

**Classification: DOCUMENT-ONLY at the repository-governance level** (the check exists, runs, and is well-built; nothing requires it to pass) — **LIVE-ENFORCED at the application level**, exactly as Packet C found (the running code's own governance boundary is real and does not depend on this gap).

**Disposition:** enabling branch protection on `main` with `drift-and-ownership` and `tests` as required status checks would close this gap directly and cheaply — a repository setting, not a code change. Left as a recommendation, not applied here, consistent with "characterization, not remediation." Worth explicit note for the eventual freeze manifest: this is the one finding across Packets C through F that reaches outside the application/runtime boundary entirely and into repository governance itself.

---

## Finding F-4: A release can publish successfully with the Android artifact silently missing

**Register checked first: genuinely new, no prior entry covers release-artifact failure semantics.**

Traced the full chain end to end, each link verified rather than assumed:

1. `build-android`'s APK-building step ends `... --release || true`. `|| true` makes the step's exit code always `0`, regardless of whether `p4a` actually succeeded — confirmed by reading the line directly, with the job's own comment candidly stating the intent: "attempt a p4a run as well and ignore failures to ensure CI continuity."
2. Because the step "succeeds," the `build-android` **job** succeeds (nothing else in that job depends on the APK existing) — the Termux tarball is built separately, earlier, unaffected by whether `p4a` works.
3. `release:`'s `needs: [build-linux, build-windows, build-macos, build-android]` is satisfied by job success, not artifact existence — confirmed this is GitHub Actions' standard `needs:` semantics (gates on job outcome, not on what a job produced).
4. `actions/upload-artifact@v4`'s `path:` for the Android job includes `*.apk` with no `if-no-files-found` override — its default is `warn`, not `error`. Since the tarball still exists, this step "succeeds" regardless.
5. `softprops/action-gh-release@v2`'s own `files:` list includes `release-dist/*.apk`, and the workflow does not set `fail_on_unmatched_files: true`. **Verified externally, not just inferred from the workflow's own YAML:** that flag is opt-in and defaults to non-failing — `action-gh-release`'s own issue tracker documents exactly this failure mode (issue #383, "The action should fail with an error if the files: settings are not valid," closed by adding the *opt-in* flag this workflow doesn't set): a missing-file glob prints a notice and the release **publishes successfully anyway**.

**Direct answer to the question asked:** yes, a release can succeed with a broken/missing component, silently, with no failure signal anywhere in the pipeline — only a buried log notice a maintainer would have to go looking for.

**Classification: release-only, PARTIAL** (the release mechanism functions and produces artifacts for 3 of 4 platforms reliably; it just cannot detect or report the 4th failing) — not evidence of anything reaching the kernel/capability boundary; this is packaging/build integrity, scoped as such.

**Disposition:** two independent, low-cost fixes, either sufficient alone: remove `|| true` (or replace it with an explicit check that sets a job output/summary flag on failure without hard-failing CI, if silent tolerance is genuinely wanted for this one best-effort platform), and/or add `fail_on_unmatched_files: true` to the release step so a missing artifact for *any* platform is caught at the one point that currently has no visibility into the other four steps' outcomes. Not implemented here.

---

## Finding F-5: Dependency version divergence between release and test/CI is systemic, not chromadb-specific — confirmed with a second instance

**This directly bears on `DEBT-032`'s disposition, addressed in the synthesis section below rather than re-argued here.**

Checked whether `numpy`/`scipy` — the other two packages `release.yml` pins exactly alongside chromadb — also diverge from what `requirements.txt` resolves. `numpy` isn't even a direct dependency of this project at all — it appears in `requirements.txt` nowhere; it's pulled in transitively by chromadb with no ceiling. `scipy` is a direct dependency, but only as `>=1.11.0` — no ceiling. In this environment, that resolves to `1.17.1`; `release.yml` pins `numpy==1.26.4` (matches what's here) and **`scipy==1.13.1`** (does not — a second, independently confirmed divergence).

**Full inventory of `requirements.txt` (21 lines): zero exact pins anywhere.** 18 of 20 packages are floor-only (`>=X`, no ceiling at all); only `chromadb` and `sentence-transformers` carry any upper bound. **No lock file of any kind exists anywhere in the repository** — no `requirements-lock.txt`, `poetry.lock`, `Pipfile.lock`, or `constraints.txt`. No Dockerfile either, so there's no alternate, more-reproducible manifest to cross-check against — the entire dependency surface is governed by these 21 unbounded-or-loosely-bounded lines, with `release.yml`'s three inline exact pins as the *only* exact version constraints that exist anywhere in this project.

**Classification: PARTIAL, systemic.** The two confirmed divergent packages (chromadb, scipy) are not an isolated coincidence — they're the two places release.yml happened to need to pin something exactly, out of a dependency set where literally nothing else has a ceiling at all. Any of the other 18 unbounded packages could diverge the same way at any future point, silently, with nothing in CI positioned to notice until (as with chromadb) a fixture or behavior-dependent test starts failing for reasons that look, from the CI-log surface, indistinguishable from an unrelated environmental issue.

---

## Finding F-6: Supply-chain posture — no automated dependency monitoring, no vulnerability scanning, mutable Action pins, no environment or tag protection

Batched together as related, moderate findings rather than one row each, per the packet's own guidance not to over-fragment the register:

- **No Dependabot or Renovate configuration** anywhere in `.github/` — dependency updates and any associated security advisories are entirely manual.
- **No vulnerability scanning in CI** — no `pip-audit`, `safety`, OSV, or `bandit` step anywhere in either workflow.
- **Every third-party GitHub Action is pinned by mutable version tag** (`@v4`, `@v5`, `@v2`), not an immutable commit SHA — `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`, `softprops/action-gh-release@v2`. A compromised upstream action publishing malicious content under the same tag would be picked up automatically on the next run, with nothing in this repository's own configuration providing a check.
- **No GitHub Environments configured** (confirmed via API: `total_count: 0`) — `release.yml`'s `workflow_dispatch` has no manual-approval gate or deployment protection of any kind.
- **No tag protection rules** (confirmed via API: 404).
- **Workflow permissions, checked and found appropriately scoped, not a finding:** `ci.yml` declares `contents: read` at the workflow level, matching what its jobs actually do; `release.yml` declares `contents: write`, which is what creating a release and uploading assets genuinely requires. No excess permission found here — stated for completeness, not filed as a gap.

**Classification: repository/supply-chain-only, DOCUMENT-ONLY for the intended protections (none exist to be either enforced or bypassed).** None of this reaches the kernel/capability boundary — it's entirely about the integrity of the path code and dependencies take *into* the repository and *out* as shipped artifacts, upstream and downstream of the runtime boundary Packet C traced.

**Disposition:** standard, well-understood hardening steps, all independent and individually cheap: add Dependabot (or equivalent) for automated update PRs; add a `pip-audit` step to CI; pin Actions by SHA with the version as a trailing comment (the common convention); consider a required-approval Environment for the release workflow given it publishes public artifacts. Not implemented here.

---

## Kernel/capability-boundary cross-check (area 5)

| Finding | Classification | Why |
|---|---|---|
| F-1 (`DEBT-031`) — allowlist mislabeling | Repository-only | About the accuracy of CI documentation; no bearing on what code does at runtime. |
| F-2 (`DEBT-032`) — release/test dependency divergence | Release-only | About which dependency versions ship vs. get tested; the *code* being governed is identical either way — this is a supply-chain/reproducibility question, not a capability or governance-decision question. |
| F-3 (`DEBT-033`) — no branch protection | **Repository-only, but the one finding that is explicitly an assurance layer around the kernel boundary** | Direct connection to Packet C's `C-2`. Stated precisely to preserve the distinction from Packet C: branch protection is not part of `GovernanceKernel` and does not evaluate any `GovernanceAction` — it is a repository-level control over whether code reaches `main` at all. It sits *outside and upstream of* the runtime boundary Packet C traced, assuring that the boundary's own enforcement code (`check_drift.py`'s `DRIFT-05`) is actually checked before merge — it does not itself enforce anything the kernel enforces, and its absence does not change what the already-traced runtime governance boundary does for code that is running today. |
| F-4 (`DEBT-034`) — Android release failure semantics | Release-only | Packaging/build integrity; no interaction with capability admission, governance decisions, or any traced execution path. |
| F-5 (`DEBT-032` refinement) — systemic dependency divergence | Release-only | Same reasoning as F-2, generalized. |
| F-6 (`DEBT-035`) — supply-chain posture | Repository-only | Upstream of the runtime entirely — concerns the integrity of what enters the repository and how it's shipped, not what the running kernel does with it. |

**Net result: zero Packet F findings are kernel-boundary or capability-boundary relevant in the sense of changing what Packet C established about the running application.** `F-3` is the one genuine connection Moncif's framing was looking for, and it is deliberately classified as an assurance layer, not as part of the boundary itself — preserving exactly the distinction requested. This is itself a meaningful, positive result for the freeze manifest: the governance/capability boundary traced in Packet C does not depend on any of the repository, CI, or release-level gaps this packet found. Those gaps are real and worth fixing, but they are a different, upstream layer of assurance, not a hole in the kernel's own enforcement.
