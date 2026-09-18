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
