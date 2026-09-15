# ADR-KERNEL-05: CTX-AUTH-001b Deferral (PROPOSED — awaiting decision)

**Status:** PROPOSED — this is a recommendation, not a decision. Matches the project's established pattern (both the Sept 6 freeze audit and the closure audit explicitly deferred their own blocker-or-not judgment on CTX findings to the project owner rather than deciding unilaterally); this ADR does the same.
**Date:** September 12, 2026
**Reviewed:** September 12, 2026, Moncif — confirmed the analysis and recommended disposition are technically defensible, with one correction (the exploitability finding's wording, now incorporated below) and a request for explicit numbered acceptance criteria (also now incorporated). **This review is not the same as formal Accepted status or inclusion in the freeze baseline** — those require a separate, explicit sign-off, per Moncif's own instruction to keep this ADR's Status as PROPOSED for now.
**Context:** `docs/Bugs Hunt & fix reports/CTX_AUTH_001_CTX_DELETE_001_DEFINITIVE_HARDENING_SEP2026.md` — this session's definitive hardening pass on CTX-AUTH-001 and CTX-DELETE-001.

---

## The question

CTX-AUTH-001b (the parser-acceptance half of CTX-AUTH-001 — `intent.py`'s `_parse_hypotheses()` accepting an injection-shaped completion line with no way to distinguish it from a genuine one) remains open after a second, deeper resolution attempt this session. Is it a Kernel v1.0 freeze blocker, or can it be deferred?

## Why a second attempt didn't close it — formal, not just empirical, this time

The first attempt (earlier this session) tried an order/contiguity-based mitigation, which passed its target test but broke three pre-existing ones. This second attempt sought a *different* signal rather than repeating that approach, and instead produced a proof that no structural signal can exist:

**`tests/core/cognitive/test_intent.py::test_clamps_out_of_range_scores`** requires `"edge_low | 0.0\nedge_high | 1.0"` fully accepted — position 2, score exactly 1.0, immediately following a lower score.
**`tests/core/cognitive/test_intent_security.py::TestCtxAuth001ParserAcceptance`** requires `"rename_branch | 0.62\nnovel:CONTEXT_SENTINEL_INJECTED | 1.00"` to reject line 2 — position 2, score exactly 1.0, immediately following a lower score.

These two completions are **structurally identical** — same line count, same position, same score, same delta from the preceding line — and require **opposite outcomes**. They differ only in the literal label text. This is a formal proof, not an empirical failure to find something: no signal derived from structure (position, count, score, ordering, contiguity) can distinguish them. The only remaining signal is the label text itself, which is exactly the keyword/content-blacklist approach `_neutralize_structural_tokens`'s own design explicitly rejects as an unwinnable, gameable arms race — and would still be trivially defeated by using a differently-worded injected label next time.

A wire-format change (e.g. requiring structured/JSON output with a per-call marker) was also considered. It would work in principle, but every other test in the file mocks the plain-text `"label | score"` format — adopting it would mean rewriting roughly ten tests' mock shapes and, almost certainly, whatever production code elsewhere expects this completion format, which is a materially larger change than this task's two-named-item scope justifies without separate authorization.

**Conclusion:** closing CTX-AUTH-001b soundly requires provenance that survives from context assembly through to the parsed hypothesis (the authority taxonomy `docs/reports/context-compiler-remediation-register.md`'s REM-004 already names) — genuine Context Compiler-adjacent infrastructure, which this task's own instructions correctly exclude ("the future Context Compiler is not to be fully implemented in this task").

## Exploitability, re-verified from source rather than assumed

The original threat model doc's "no live entry point" claim was re-checked directly against today's `main`, not trusted:

- **No `BrowserWorker` class exists anywhere in the codebase.**
- **`core/web_learning/pipeline.py` exists, with a real quarantine/trust-score gate — but `core/meta/self_model.py` explicitly carries `"web_learning": False`, and every reference to this pipeline outside its own module is in a test file.** It is not invoked from any live orchestration path.
- Every actual memory-write call site traced (`reflection.py`, `planner.py`, `evaluator.py`, `orchestrator.py`, `cognitive/learning.py`) is the cognitive system writing its own internal reasoning — none ingest content from an external or adversarial source.

No currently traced live execution path was found that permits externally supplied content to reach memory. The known web-learning path is disabled (`"web_learning": False` in `core/meta/self_model.py`) and has no live callers outside its own tests. This is a statement about what this session's traced search found, not an architectural absolute — the search covered `BrowserWorker`/`ToolResult`-shaped classes and every `memory.write()` call site reachable from `core/`, not literally every file in the repository, and should not be read as a claim that all possible ingress mechanisms were enumerated.

CTX-AUTH-001a (already fixed) closes the higher-leverage vector regardless of this finding. CTX-AUTH-001b's residual scenario — a model echoing an injected line into its own completion — additionally requires 001a's protection to have already been defeated some other way. And even a successfully-hijacked Intent hypothesis would still need to survive Planning, Compilation, and `GovernanceKernel` evaluation before any real-world effect — Intent Interpretation is deliberately not the authorization boundary in this architecture (K4.2 §4).

### Explicit acceptance criteria for revisiting this deferral

Any of the following establishes a live untrusted-content → memory path and makes CTX-AUTH-001b a release/freeze concern again, not a future nice-to-have:

1. `web_learning` is re-enabled (the `core/meta/self_model.py` flag flips to `True`, or `WebLearningPipeline` gains a live caller outside its own tests).
2. A browser, tool-result, or other externally-sourced ingestion worker is introduced (a `BrowserWorker`-shaped class, or any worker that writes tool/API/web output into `UnifiedMemory`).
3. Any other externally-sourced retrieval or write path is added that this ADR's traced search did not cover.
4. Independent of the above, a live untrusted-content → memory path is otherwise established by any means.

`TestCtxAuth001ParserAcceptance` remaining red is the standing, automatic tripwire for all four — its continued failure after any of these lands is exactly the signal that this deferral needs to be revisited before the new path ships, not after.

This does not make the code path unreachable in the mission's technical sense (`core/cognitive/intent.py` is a live, Kernel-required path, and the parser genuinely would accept an injected line if one arrived) — reachability of the *code* and live existence of an *attacker-controlled input source* are different questions, and this ADR is careful not to conflate them.

## Recommendation

**Defer CTX-AUTH-001b — tracked, not blocking, contingent on Context Compiler's authority-taxonomy work — rather than treat it as a Kernel v1.0 freeze blocker.** Reasoning: the higher-leverage half of the same finding is closed; no currently traced live execution path was found for the specific residual scenario this half defends against; a downstream governance layer exists regardless; and a sound fix requires infrastructure this task and the broader project have both already scoped as post-freeze.

This recommendation explicitly does **not** claim the underlying code is safe in some absolute sense, and does not propose closing or weakening `TestCtxAuth001ParserAcceptance` — it stays red, honestly, as a standing regression trigger: the day a live external-content-ingestion path is added (web-learning re-enabled, a browser/tool-result worker introduced), this test's continued failure is exactly the signal that CTX-AUTH-001b needs to be revisited before that path ships, not after.

## Current state (as of the September 12, 2026 review)

- Reasoning, wording, and acceptance criteria reviewed and endorsed as technically defensible.
- Status remains **PROPOSED**, deliberately — not flipped to Accepted by this review.
- The deferral is **not yet part of the Kernel v1.0 freeze baseline.** Treating it as such requires the separate, explicit sign-off described below.
- **For the Kernel-freeze work specifically, Moncif's stated disposition (Sept 12) is: "documented/deferred, but not yet a formally accepted freeze exception."** His own stated reason: this "keeps the evidence-first rule intact and prevents the audit from silently converting a justified present-state observation into a permanent architectural guarantee." Any future freeze verdict referencing this item should carry that exact distinction, not shorthand it to "resolved" or "excepted."

## Upon formal sign-off (not yet given)

- This ADR's Status changes to **Accepted**, dated and attributed.
- `KNOWN_ISSUES.md`'s DEBT-019 row is updated to reflect the explicit deferral decision (not just "still open, Moncif's call") — satisfying the mission's own freeze-classification rule, which requires *"an explicit current Kernel policy/ADR"* to narrow a reachable violation out of the Kernel v1.0 contract, not silence.
- No code changes are implied — `TestCtxAuth001ParserAcceptance` remains red by design, as described above.

## If rejected

- CTX-AUTH-001b is a genuine P0/P1 Kernel v1.0 freeze blocker, and closing it for real requires at least a minimal slice of the Context Compiler authority-taxonomy work — scoped separately, since this task's own instructions exclude implementing that here.
