# K4.2-H2 / D11 — Request Language Detection

**You are one of four Claude sessions implementing K4.2-H2 in parallel, with zero contact with the other three.** This brief is self-contained.

**Your branch:** `h2/d11-language-support`. Work only on this branch. Do not push to `main`.

**Ownership is mechanically enforced.** Before finishing, run:
```
python3 scripts/check_packet_ownership.py --packet D11
```
It must print `PASS`.

---

## Context you need

1. `CURRENT_STATE.md` / `IMPLEMENTATION_ROADMAP.md` — confirm H1 is FROZEN, H2 active. If not, stop and report the discrepancy.
2. `core/cognitive/intent.py` — read `RawRequest`'s definition and `normalize_request()` in full before changing either.
3. `docs/Bugs Hunt & fix reports/K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md`, section 11, for fuller background.

## Objective

Add best-effort request-language metadata without touching capability-matching semantics.

## The change, exactly (from the canonical spec)

- `RawRequest` gains `detected_language: Optional[str] = None`.
- `RawRequest` is `frozen=True` (H1's contract — confirmed by `scripts/check_drift.py`'s DRIFT-04/DRIFT-08 checks, which will flag a second construction site if you work around the freeze instead of respecting it). **Detection MUST happen before construction, not after.**
- Pattern: `language = _detect_language(text); return RawRequest(text=text, detected_language=language)`.
- Unknown/undetectable language: fall back to `None`. Never raise. This is an explicit H2 stop condition from the canonical spec, not a suggestion.

## Allowed files

- `core/cognitive/intent.py`
- `tests/core/cognitive/test_intent.py`
- `docs/architecture/h2_status/D11_STATUS.md`
- `docs/Bugs Hunt & fix reports/K4_2_H2_D11_COMPLETION_REPORT.md`
- `docs/architecture/decisions/ADR_K4_2_H_11_LANGUAGE_SUPPORT.md` (this slot reserved for H2)

Nothing else. **Specifically forbidden: `core/cognitive/planner.py`.** Do not wire `detected_language` into `discover_capabilities()` scoring, even if it seems like an obvious next step. Confirmed, as of the freeze review, that `discover_capabilities()` consumes `Goal`, not `RawRequest.detected_language` — that's deliberate, and changing it is a `CapabilityMatch` evidence-shape change requiring its own ADR and explicit approval, which is exactly the kind of decision a zero-contact parallel session shouldn't make unilaterally (a D3 session may be relying on today's scoring behavior at the same time). Also forbidden: `core/orchestrator.py`, `core/cognitive/compiler.py`, `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`/`KNOWN_ISSUES.md`/`docs/architecture/decisions/ADR_INDEX.md`/`PROJECT_INDEX.md`/`tests/conftest.py` (deferred to the sequential integration packet for all four parallel packets).

## Frozen contracts you must not change

`RawRequest.text` semantics. `RawRequest.frozen=True`. The single-construction-site invariant (DRIFT-04/08) — if your change results in `RawRequest(...)` being constructed anywhere other than `core/cognitive/intent.py`, that's a bug in your implementation, not an acceptable side effect.

## Tests

- `_detect_language()` unit tests: a clearly-identifiable-language input, an unknown/gibberish input, an empty string — confirm the fallback-to-`None` behavior specifically, don't just test the happy path.
- A construction test confirming `RawRequest.detected_language` is populated correctly and the frozen contract still holds (e.g. attempting to mutate it post-construction still raises).
- A **negative** test confirming `discover_capabilities()`'s behavior is unchanged by this field's mere presence — this mechanically guards the "don't wire it into scoring" rule above, not just documents it.

## Stop conditions

- The language-detection dependency (whatever library/approach you choose) being unavailable in this sandbox — fall back to `None`, don't block on it.
- Discovering `normalize_request()` has more than one call site — that's a separate, pre-existing question worth flagging in your status stub, not something to silently work around.

## How to report done

1. `python3 scripts/check_packet_ownership.py --packet D11` — must print `PASS`.
2. `python3 -m pytest tests/core/cognitive/test_intent.py -v` — all passing.
3. Full suite regression check (`python3 -m pytest tests/ -q --tb=no`) — compare against the known baseline; explain any new failure.
4. `python3 scripts/check_drift.py --quiet` — still 9/9 PASS.
5. Write `docs/architecture/h2_status/D11_STATUS.md`:

```markdown
# D11 Status

**State:** COMPLETE | BLOCKED | PARTIAL
**Branch:** h2/d11-language-support @ <commit sha>
**Ownership check:** PASS/FAIL
**Detection approach used:** <library/method, and why>
**Tests added:** N, all passing
**Regression check:** <passed>/<failed> vs baseline
**Drift check:** 9/9 PASS
**Confirmed:** discover_capabilities() behavior unaffected (negative test passing)
**ADR created:** ADR_K4_2_H_11_LANGUAGE_SUPPORT.md
```

6. Commit and push only this branch:
   `git push https://<token>@github.com/1h0lde4/ocbrain-v4.1.git HEAD:h2/d11-language-support`
