# D11 Status

**State:** COMPLETE
**Branch:** h2/d11-language-support @ (see `git log -1` on this branch for the exact final SHA -- this file's own commit necessarily follows the implementation commit f1866984d2c8e73300330ff7a173425d3bc7bcb0)
**Ownership check:** PASS
**Detection approach used:** dependency-free local heuristic (no external language-ID library installed in this environment, and `requirements.txt` sits outside this packet's `allowed_files`) -- Unicode script-range matching for 8 non-Latin-script languages (ja/ko/zh/ru/ar/he/el/hi), then common-function-word overlap for 6 Latin-script languages (en/es/fr/de/pt/it). Full rationale and alternatives considered in `ADR_K4_2_H_11_LANGUAGE_SUPPORT.md`.
**Tests added:** 18, all passing (81 -> 99 in `tests/core/cognitive/test_intent.py`)
**Regression check:** 1192 passed / 34 failed vs. documented baseline of 1174 passed / 34 failed (1174 + 18 new D11 tests). The 34-failure set is byte-for-byte identical (by test ID) to the same pre-existing baseline already confirmed on the D3 and D7 branches this session.
**Drift check:** 9/9 PASS
**Confirmed:** `discover_capabilities()` behavior unaffected -- `TestDetectedLanguageDoesNotAffectCapabilityDiscovery` (3 tests): `CapabilityDiscoveryRequest` has no language-shaped field at all; the literal string `detected_language` does not appear anywhere in `planner.py`'s source; and the real, unmocked `discover_capabilities()` produces byte-identical `CapabilityMatch` results for two `RawRequest`s differing only in `detected_language`.
**ADR created:** `ADR_K4_2_H_11_LANGUAGE_SUPPORT.md`
**Additional verification performed:**
- Repo-wide search confirmed `RawRequest(...)` still has exactly one production construction site (`core/cognitive/intent.py:341`, inside `normalize_request()`) both before and after this change -- DRIFT-04/08 unaffected.
- Repo-wide search confirmed `normalize_request(...)` still has exactly one production call site (`core/cognitive/intent.py`, inside `interpret_request()`) -- the brief's "more than one call site" stop condition did not trigger.
- `_detect_language()` never raises, verified directly (not only implied by other passing tests) against arbitrary short, symbolic, and `None` input.
- A genuine cross-language scoring tie (engineered fixture, verified equal by direct computation in the test itself) returns `None` rather than being resolved by incidental dict-iteration order.
**Deferred / out of scope:** wiring `detected_language` into capability-matching scoring -- explicitly forbidden by this packet's own brief; would require its own ADR and explicit approval per the brief's coordination note.
