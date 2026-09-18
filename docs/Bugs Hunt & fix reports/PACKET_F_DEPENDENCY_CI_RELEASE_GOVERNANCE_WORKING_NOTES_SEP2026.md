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
