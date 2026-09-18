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
