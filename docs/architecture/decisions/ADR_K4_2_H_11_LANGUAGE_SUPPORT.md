# ADR-K4.2-H-11: Request Language Detection

**Status:** ACCEPTED
**Date:** August 20, 2026
**Author:** K4.2-H2-D11 packet (Request Language Detection)
**Scope:** `core/cognitive/intent.py` (`RawRequest`, `normalize_request()`) only.

---

## 1. Context

The canonical spec (K4.2 §12, via `IMPLEMENTATION_ROADMAP.md`/the H2 readiness plan §11) calls for `RawRequest` to gain a `detected_language: Optional[str] = None` field, populated by a `_detect_language()` call made *before* construction — respecting `RawRequest.frozen=True` (H1 D1, ADR-K4.2-H-01) rather than working around it with a post-hoc mutation or `dataclasses.replace()`. Acceptance criterion H2-G4: "`detected_language` field present; frozen construction pattern works; no silent output language change."

This packet's `allowed_files` (`docs/architecture/h2_packet_ownership.json`) covers `core/cognitive/intent.py` and its test file, but not `requirements.txt`. No language-identification library (`langdetect`, `langid`, or similar) is installed in this environment. Adding one would have meant declaring a new production dependency in a file this packet has no authorization to touch — not a technical blocker so much as a scope one: a new third-party dependency is exactly the kind of decision `docs/architecture/h2_packets/README.md`'s zero-contact-parallel-session model reserves for something other than an unreviewed addition inside an unrelated packet's diff.

## 2. Decision

`_detect_language()` is a small, dependency-free, entirely local heuristic, implemented directly in `core/cognitive/intent.py`:

- **Non-Latin script (8 languages):** direct Unicode code-point range membership — Hiragana/Katakana → `ja`, Hangul → `ko`, CJK Unified Ideographs → `zh` (checked *after* the Kana ranges, since Japanese text mixes Kanji with Kana and Chinese text never contains Kana — checking Kana first is what keeps mixed Japanese text from being misread as Chinese), Cyrillic → `ru`, Arabic → `ar`, Hebrew → `he`, Greek → `el`, Devanagari → `hi`. A single matching character is enough to decide these — script membership is a near-zero-false-positive signal on its own.
- **Latin-script (6 languages):** common closed-class function-word overlap (`the`/`and`/`is` for `en`; `el`/`la`/`de`/`que` for `es`; and so on for `fr`/`de`/`pt`/`it`) — script alone can't distinguish these from each other. Requires at least 3 alphabetic tokens in the input and at least 2 distinct stopword hits from the winning language before returning anything; a genuine tie between two languages' hit counts returns `None` rather than being broken by whichever language happens to iterate first in the scoring dict.
- Returns `None` — a legitimate, expected result, not an error — for empty/whitespace-only input, too-short input, unrecognized/gibberish input, and ties. Never raises, verified directly (not just implied) by a test that feeds it arbitrary short, symbolic, and `None` input.
- Zero network I/O, zero new third-party dependencies, zero changes outside `core/cognitive/intent.py`.

`RawRequest` gains the field as `detected_language: Optional[str] = None`, additive, default `None`. `normalize_request()`'s sole return statement becomes `language = _detect_language(text); return RawRequest(text=text, detected_language=language)` — detection happens on the already-normalized `text` local variable, immediately before the one, unchanged construction call.

## 3. Consequences

- **Accuracy is intentionally modest.** This is closer to "confidently recognizes a clearly-written sentence in one of 14 common languages, declines everything else" than a production-grade language identifier. That is the deliberate trade this ADR makes for zero new dependencies and zero scope beyond this packet's `allowed_files` — consistent with `normalize_request()`'s own pre-existing philosophy (documented in its own docstring) of staying "lightweight" rather than building a general-purpose classifier ahead of a concrete need for one.
- **Existing consumers are unaffected.** `detected_language` is read nowhere else in the codebase as of this packet. `interpret_request()` (the only caller of `normalize_request()`) only ever read `.text`; that continues to be all it reads. `discover_capabilities()` consumes `CapabilityDiscoveryRequest` (a `core/cognitive/planner.py` type with no language-shaped field at all), never `RawRequest` directly — mechanically confirmed by `TestDetectedLanguageDoesNotAffectCapabilityDiscovery` in the test file, which checks `CapabilityDiscoveryRequest`'s actual field set, greps `planner.py`'s literal source for the string `detected_language` (absent), and runs the real, unmocked `discover_capabilities()` against two otherwise-identical requests differing only in `detected_language`, confirming byte-identical results.
- **DRIFT-04/08 unaffected.** The single-construction-site invariant (`RawRequest(...)` constructed only in `core/cognitive/intent.py`) was re-verified by repository-wide search before this change and holds after it — this change adds a field to the one existing call, not a second call site.
- **A future packet that wants real statistical language identification** (a proper n-gram-frequency model, or a library dependency) is a separate, explicitly-scoped change — this ADR's heuristic is deliberately easy to swap out later (`_detect_language()`'s signature and `None`-on-uncertainty contract would not need to change for a higher-accuracy implementation to drop in behind it).
- **Wiring `detected_language` into capability-matching is explicitly out of scope here** and remains so — per this packet's own forbidden-files note, that would be a `CapabilityMatch` evidence-shape change requiring its own ADR and explicit approval, precisely because a zero-contact parallel session (this one) has no visibility into whether a concurrently-running D3-style session is relying on today's scoring behavior.

## 4. Alternatives considered

- **Add `langdetect` or `langid` as a new dependency:** rejected for this packet specifically — not because either is a bad choice in the abstract (both are legitimate, offline-capable, pure/mostly-Python libraries consistent with this project's local-first principle), but because `requirements.txt` is outside `allowed_files` for D11, and introducing a new production dependency is exactly the kind of unilateral, cross-cutting decision the zero-contact parallel-packet model is designed to prevent any one packet from making alone. Worth revisiting as an explicit, separately-authorized follow-up if the heuristic's accuracy proves insufficient in practice.
- **Post-construction mutation (detect after building `RawRequest`, then set the field):** rejected outright — `RawRequest.frozen=True` is an H1-frozen contract; this is exactly the "or a post-hoc mutation" pattern the brief explicitly names as unacceptable, and DRIFT-04/08 would not even catch it if it somehow avoided a second construction site while still violating frozen semantics via some other means, so this had to be avoided by design, not caught by a check.
- **A single "confidence score" instead of a plain `Optional[str]`:** rejected — the canonical spec and this packet's brief both specify `Optional[str]`, not a scored/structured result; introducing a richer return shape than what was asked for would be exactly the kind of speculative field-adding `RawRequest`'s own docstring already argues against ("kept to the one field every description... supports, rather than speculating further ones").
