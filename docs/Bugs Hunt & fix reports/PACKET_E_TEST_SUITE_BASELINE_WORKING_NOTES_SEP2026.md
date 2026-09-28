# Packet E — Full Test-Suite Baseline: Working Notes (Characterization Phase)

Per Moncif's explicit framing: this phase is environment characterization, not remediation. No fixtures modified, no heavy ML stack installed, no code changes.

---

## Environment fingerprint

| | |
|---|---|
| Commit | `b8fa4f9b645f86e98653ee601037f2cdf22da83b` (`audit/tracking-integration`) |
| OS | Ubuntu 24.04.4 LTS, kernel 6.18.44 |
| Python | 3.12.3 |
| chromadb | 0.6.3 (matches `requirements.txt`'s `>=0.4.0,<1.0` pin) |
| fastapi | 0.141.1 (matches `>=0.111.0`) |
| huggingface_hub | 0.36.2 (present — transitive dep of chromadb's tokenizer needs) |
| tokenizers | 0.22.2 (present, same reason) |
| torch / transformers / sentence-transformers / trafilatura | Not installed |
| Disk | 2.8 GB free / 252 GB |

**Collection: 1,507 / 1,507 clean, zero errors. Full execution: 1,501 passed, 6 failed, 0 skipped, 33.04s.**

---

## Step 1: The five Chroma failures — classified

**Isolated re-run:** all five fail identically alone as in the full run — not an interaction artifact.

**Root cause, traced to the exact byte:** `modules/{mock,system_ctrl,empty_test}/knowledge.db/chroma.sqlite3` are **tracked, committed fixtures** (`git ls-files` confirms), uploaded **2026-06-22** (`bff10ab`, "Add files via upload"). Inspected the raw SQLite content directly: the `collections` table's `config_json_str` column is a literal `'{}'` — empty, no `_type` key — while `schema_str` holds a full, rich JSON structure (HNSW params, `"embedding_function":{"type":"legacy"}`, etc.). chromadb 0.6.3's `_load_config_from_json_str_and_migrate` → `CollectionConfigurationInternal.from_json` unconditionally does `json_map['_type']`, which raises on this input.

**Tested directly, on a throwaway copy, original never touched:** installed chromadb 1.5.9 (cheap — confirmed earlier, ~0.1GB), pointed it at a copy of the `system_ctrl` fixture. **It read the collection successfully.** The fixture is valid data — just written by a newer chromadb generation (schema-based config as primary, `config_json_str` left as an empty legacy placeholder) that `0.6.3`'s migration path doesn't know how to handle.

**Independently corroborated, not a new discovery:** `git log --grep` surfaced a July 4, 2026 commit ("Architecture Hardening Complete — Session 4D") whose own message states: *"Regression: 407 passed, same 5 pre-existing chromadb-schema failures, same 1 pre-existing collection error — identical before and after every change in this session."* This exact 5-failure count has been stable and already-labeled "pre-existing" since at least July 4 — eleven weeks before this run, across an enormous amount of intervening work and a 3.7x growth in test count (407 → 1,501 passing).

**Classification: broken migration compatibility in the pinned chromadb version reading a newer-generation collection format.** Not a stale/corrupted fixture (it's valid, just from a later chromadb generation) and not a genuine OCBrain defect (the failure occurs entirely inside chromadb's own library code, before any OCBrain assertion). There is a secondary, softer "incorrect pin" dimension worth naming: the pin has apparently been `<1.0` for as long as these fixtures have existed stale against it, meaning either the fixtures were generated once, outside the pin's discipline, and never regenerated, or the pin was always intentionally conservative relative to whatever created them. Disposition (regenerate fixtures vs. relax the pin vs. quarantine) is explicitly left to Moncif, per the "characterization not remediation" framing — not decided here.

## Step 2: The disappearance of the historical `huggingface.co` failures — explained, not just observed

Searched every production file referencing `sentence_transformers`/`transformers`/`torch`: `core/learning/similarity.py`, `core/memory/backends/memory_vector.py`, `modules/embedding_fn.py` (plus `tests/phase2_verification.py`, which is not pytest-collected — doesn't match `test_*.py`, confirmed absent from the run log, and its own docstring states "no external dependencies").

All three real production files wrap their `sentence_transformers` usage in `try/except ImportError` (or `(ImportError, ValueError)`), falling back to a safe default (`0.0` similarity, or a `HashEmbeddingFunction`) rather than raising or reaching the network. Checked whether this is a recent fix: `git log --follow` on `similarity.py` traces back to `165d02c`, "first commit," May 7, 2026 — **this guard has been present since the repository's beginning.** Ruled out "the system got healthier" for this path specifically.

**The real answer: this is a documented, precedented pattern, not a mystery.** `CURRENT_STATE.md` records a Sept 12, 2026 session running in an explicitly-named "minimal-dependency sandbox" that got **1,427 passed / 7 failed / 4 errors**, with its own text attributing *"the 4 errors and 6 of the 7 failures"* directly to *"chromadb unavailable in that sandbox"* — and **no huggingface-class failures at all** in that run either. The historical ~34-failure baseline is specific to environments where the *full* `requirements.txt`, including `torch`/`sentence-transformers`, is installed — enough for the code to actually attempt a live model resolution and hit a real, attributable `huggingface.co` connection failure. In a minimal-dependency sandbox, that code path is never reached — the `ImportError` guard trips first, safely, before any network attempt. This run is a second, independent instance of that same already-documented sandbox category, not a new phenomenon.

**Direct answer to the framed question:** the failures didn't disappear because the environment is healthier or because tests stopped exercising the path — they don't appear in this *class* of environment because the guarded fallback activates before network code is ever reached, and this exact environment class has produced this exact pattern before.

## Step 3: ML runtime dependency matrix

| Component | Needed for collection | Needed for core kernel tests | Needed for specific runtime tests | Currently installed |
|---|---:|---:|---:|---:|
| torch | No | No | No (zero direct references anywhere in `core/`/`interface/`/`modules/`/`tests/`; pure transitive dep of sentence-transformers) | No |
| transformers | No | No | No (same — zero direct references, transitive only) | No |
| sentence-transformers | No | No | Guarded fallback only — 3 production files (`similarity.py`, `memory_vector.py`, `embedding_fn.py`), all with `try/except ImportError`, all exercised by currently-passing tests via their fallback path | No |
| trafilatura | No | No | **Unguarded** — `modules/web_search/module.py:10` is a bare top-level `import trafilatura` with no try/except, would fail to import if reached. Currently reached by zero collected tests (`test_context_scope_security.py`'s "web_search" hit is a docstring mention, not an import — checked directly) | No |

The one asymmetry worth flagging: `trafilatura`'s import is not guarded like the other three. It causes zero problems today only because nothing currently collected imports that module — a different, more fragile risk profile than the other three, worth knowing before anything changes what exercises `web_search/module.py`.

**Given this matrix, installing the heavy ML stack now would not answer any open question** — nothing in the currently-collected suite needs it, and the two remaining open items (chromadb fixture disposition, `trafilatura`'s unguarded import) are both independent of it.

## Current baseline, stated precisely

- Collection: 1,507 / 1,507 clean.
- Execution: 1,501 passed / 6 failed / 0 skipped, 33.04s.
- 1 known: `TestCtxAuth001ParserAcceptance`, the intentional CTX-AUTH-001b tripwire (ADR-KERNEL-05).
- 5 characterized: chromadb migration-compatibility failures on newer-generation committed fixtures, precedented since July 4, 2026 — disposition not yet decided.
- Not comparable, and not claimed to be better than, the historical ~34-failure full-dependency baseline — this is a different, already-precedented environment class (minimal-dependency sandbox), established via direct evidence rather than assumed.
