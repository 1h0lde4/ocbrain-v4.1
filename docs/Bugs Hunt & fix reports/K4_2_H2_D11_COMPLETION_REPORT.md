# K4.2-H2-D11 Completion Report — Request Language Detection

**Repository:** `1h0lde4/ocbrain-v4.1`
**Branch:** `h2/d11-language-support`
**Implementation commit:** `f1866984d2c8e73300330ff7a173425d3bc7bcb0`
**Packet scope:** `docs/architecture/h2_packets/D11_LANGUAGE_SUPPORT.md`
**Final status:** **COMPLETE**

## What changed

`core/cognitive/intent.py`:
- `RawRequest` gains `detected_language: Optional[str] = None` — additive, `frozen=True` preserved.
- A new `_detect_language(text) -> Optional[str]` module-level helper, plus its Unicode script-range and Latin-stopword data tables, placed immediately before `normalize_request()`.
- `normalize_request()`'s sole return statement changed from `return RawRequest(text=text)` to `language = _detect_language(text); return RawRequest(text=text, detected_language=language)` — matching the brief's mandated pattern exactly; detection happens before construction, never as a post-hoc mutation.

`tests/core/cognitive/test_intent.py`: 18 new tests (81 → 99), detailed below.

`docs/architecture/decisions/ADR_K4_2_H_11_LANGUAGE_SUPPORT.md` (new) and `docs/architecture/h2_status/D11_STATUS.md` (overwritten from its `NOT STARTED` placeholder).

No other file touched. `core/cognitive/planner.py`, `core/orchestrator.py`, `core/cognitive/compiler.py`, `requirements.txt` — all untouched, all read-only where read at all.

## Detection approach, and why

No language-identification library (`langdetect`, `langid`, etc.) is installed in this environment, and `requirements.txt` is outside this packet's `allowed_files` — this packet could not authorize adding a new production dependency to itself. `_detect_language()` is therefore a small, dependency-free, entirely local heuristic:

- **8 non-Latin-script languages** (`ja`, `ko`, `zh`, `ru`, `ar`, `he`, `el`, `hi`) via direct Unicode code-point range membership. Checked in an order where Hiragana/Katakana precede the CJK Unified Ideographs range specifically so Japanese text (which mixes Kanji with Kana) isn't misclassified as Chinese (which never uses Kana).
- **6 Latin-script languages** (`en`, `es`, `fr`, `de`, `pt`, `it`) via common closed-class function-word overlap, requiring at least 3 alphabetic tokens and at least 2 distinct stopword hits from the winning language, with a genuine tie between two languages explicitly returning `None` rather than being resolved by incidental dict-iteration order.
- `None` — a legitimate, expected result — for empty/whitespace-only input, too-short input, and anything that doesn't clear the (deliberately conservative) confidence bar. Never raises.

Full reasoning, and the three alternatives considered and rejected (adding a new dependency; post-construction mutation; a richer confidence-score return type), are in `ADR_K4_2_H_11_LANGUAGE_SUPPORT.md`.

## Verification performed (not assumed)

- **Single construction site:** repo-wide `grep` for `RawRequest(` confirmed exactly one production call site (`core/cognitive/intent.py:341`, inside `normalize_request()`) both before and after this change — every other hit is in a test file. DRIFT-04/DRIFT-08 (which mechanically enforce exactly this) confirmed PASS both before and after.
- **Single call site for `normalize_request()`:** repo-wide `grep` confirmed exactly one production call site (`core/cognitive/intent.py`, inside `interpret_request()`). The brief's "more than one call site" stop condition did not trigger — nothing to flag.
- **`_detect_language()` correctness:** manually cross-checked against 6 hand-written sentences (one per Latin-script language, plus Japanese and Russian for the script-range path) before formalizing as parametrized tests — all matched expectations.
- **`_detect_language()` never raises:** tested directly against `"hi"`, `"12345 67890 !!!"`, control characters, a single character, and `None` itself — not merely inferred from the other passing cases.
- **Genuine tie handling:** the test's fixture computes both languages' stopword-hit counts inline and asserts they're equal *before* asserting the function's behavior — so the test would fail loudly (on its own precondition) if a future edit to either stopword list broke the intended tie, rather than silently testing something other than what it claims to.
- **`discover_capabilities()` unaffected — three-part mechanical guard, not just a docstring claim:**
  1. `CapabilityDiscoveryRequest`'s actual dataclass fields contain nothing named or resembling `detected_language`/`language`.
  2. The literal string `detected_language` does not appear anywhere in `core/cognitive/planner.py`'s source text.
  3. The real, unmocked `discover_capabilities()`, called with two `RawRequest`-derived descriptions identical in text and differing only in `detected_language`, returns byte-identical `CapabilityMatch` lists (both `relevance_score` and `capability_type` order compared).

## Tests

```
tests/core/cognitive/test_intent.py — 99 passed (81 pre-existing + 18 new)
```

New tests, by area:
- `TestNormalizeRequest` (+2): `detected_language` populated for a clear-language input; `None` for an unclassifiable one — integration-level, through the real `normalize_request()`.
- `TestDetectLanguage` (new class, 11 tests): 6 parametrized clearly-identifiable-language cases (en/es/fr/de/ja/ru); gibberish → `None`; empty string → `None`; whitespace-only → `None`; never-raises across arbitrary/symbolic/`None` input; genuine cross-language tie → `None`.
- `TestRawRequestFrozen` (+2): `detected_language` populated and still protected by the frozen contract specifically (mutating it raises, distinct from the pre-existing `.text`-mutation test); defaults to `None` on direct construction.
- `TestDetectedLanguageDoesNotAffectCapabilityDiscovery` (new class, 3 tests): the mechanical guard described above.

**Full suite:** `1192 passed, 34 failed` — matches `1174 + 18` exactly. The 34-item failing-test-ID list was diffed byte-for-byte against the same baseline already independently confirmed pre-existing on the D3 and D7 branches earlier this session (`git stash`-based both-ways comparison, not repeated here since it was already established) — identical, zero new failures, zero fixed-by-accident.

**Drift check:** `check_drift.py` → 9/9 PASS.

**Ownership check:** `check_packet_ownership.py --packet D11` → PASS.

## Contract impact

- `RawRequest`: one field added (`detected_language: Optional[str] = None`), additive, default-`None`. `.text`'s semantics, `frozen=True`, and the single-construction-site invariant are all unchanged.
- `normalize_request()`: same signature, same `NormalizationRejected` behavior, same single call site. Return value now carries one more (optional, defaulted) field.
- `discover_capabilities()` / `CapabilityDiscoveryRequest` / `CapabilityMatch`: untouched, mechanically confirmed unaffected (see above).
- No new events, no new diagnostics — none required by this packet.

## Parallel-session impact

D3, D7, D12's allowed files were not touched (`core/cognitive/planner.py` — explicitly forbidden to this packet and never opened for writing; `core/orchestrator.py`; D3/D7/D12's respective status stubs, ADRs, and completion reports). `requirements.txt`, `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md`, `ADR_INDEX.md`, `PROJECT_INDEX.md`, `tests/conftest.py` — all untouched, deferred to the integration packet as this packet's own brief specifies.

## Unresolved / deferred issues

1. `ADR_INDEX.md` needs a new row for ADR-K4.2-H-11 — outside this packet's `allowed_files`, deferred to integration.
2. Wiring `detected_language` into capability-discovery scoring is explicitly out of scope here (this packet's own forbidden-files note) and remains an open, separately-authorizable future decision, not a gap in this packet's own work.
3. The heuristic detector's accuracy is modest by design (see ADR §3) — a future packet may want to swap in a proper statistical model or library; `_detect_language()`'s `None`-on-uncertainty contract is written so that swap wouldn't require touching its call site in `normalize_request()`.
4. The same unrelated `config/*.toml` line-ending churn from running the full suite (seen and reverted on the D3 and D7 branches earlier this session) recurred here and was reverted before committing — not part of this packet's commits.

---

## Final Status

**COMPLETE**
