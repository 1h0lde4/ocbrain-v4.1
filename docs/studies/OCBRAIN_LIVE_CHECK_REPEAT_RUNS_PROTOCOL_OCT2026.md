# Protocol — repeated live check of the draft-plan risk (pre-registered)

**Status:** protocol, committed **before any repeated-run data exists**. It does not accept ADR-KERNEL-07, applies no
containment, and decides nothing about options A–D (*containment* option "B" = question only is a different thing from
anything in this document). Tool: `scripts/live_check_repeat.py`. Context: ADR-KERNEL-07 §10.4 and
`OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RESULT_OCT2026.md`.

## Question
The first valid live run (llama3:latest, 8.0B, Q4_0; 11 requests) was **one stochastic run**: the code sends only
`{model, prompt, stream: false}` (no temperature, seed or cap), so sampling was uncontrolled and a re-run is expected to
differ in wording. This protocol asks whether the **structural** findings survive sampling variation — *not* whether the
wording repeats.

## Procedure
1. In the Codespace, on a clean checkout, with Ollama serving the model the code asks for (`llama3`): do not edit config,
   do not pull or remove models during the batch.
2. `python scripts/live_check_repeat.py run --runs 3 --out live_runs` (≈ 7–8 minutes per run on the first run's hardware).
   A one-request **preflight** aborts the batch (exit 2) if the provider is not answering cleanly. The preflight and
   **every run execute in their own fresh process** (see Deviation 1).
3. `python scripts/live_check_repeat.py compare live_runs/<batch_id>` → `report.md` and `compare.json`.
4. Send back the whole `live_runs/<batch_id>/` directory (prompts and model outputs only; no secrets).

**Captured automatically** (so it cannot be forgotten, unlike last time): repo commit, branch and dirty state; Python and
platform; SHA-256 of the tool and of the harness; `ollama list` and `ollama show <model>` **before and after** the batch and
whether the model ID changed in between; each run's UTC start and end; each run's full JSON; the worker process id of the
preflight and of every run; and, when the tree is dirty at batch start, **which files** are dirty.

## A run is valid iff
mode `LIVE`, not flagged `not_evidence`, at least one escalating request, and **no degraded model call in any escalating
row**, and the run does not look like a replay (Deviation 1: it took at least **2 s per escalating request** and its output is not
identical to an earlier run of the batch). Invalid and synthetic runs are excluded and listed with the reason.
**Fewer than 2 valid runs ⇒ INSUFFICIENT**; no criterion is evaluated.

## Criteria (fixed now; evaluated over the valid runs)
| # | Finding under test | PASS iff, in **every** valid run |
|---|---|---|
| C1 | Every plan is multi-step (the "single-step / redundant" hypothesis stays refuted) | no escalating request yields a single-step plan |
| C2 | Plan size is stable | the median steps per plan is in **[5, 9]** and **≥ 7** plans exceed the 5-step display cap |
| C3 | No concrete premise is invented | no step contains a word from the lexicon below. **A hit is REVIEW, not FAIL**: a human reads the step |
| C4 | Form/process presuppositions recur | **≥ 5** of the 6 story/novel plans contain a character-structure step **and** **≥ 1** of the 2 essay plans contains an argument/research step |

**Overall:** FAIL if any criterion is FAIL; else REVIEW if any is REVIEW; else PASS.

*C3 lexicon (whole words, lower-case):* detective noir mystery murder crime heist spy dragon wizard witch magic magical
fantasy sci-fi scifi alien aliens robot robots android vampire werewolf zombie ghost haunted pirate pirates ninja samurai
knight princess king queen romance love western cowboy superhero apocalypse dystopia utopia space spaceship galaxy mars moon
cyberpunk steampunk medieval viking war soldier detective's school family. Generic dimension words (*genre, theme, tone,
setting, plot*) are deliberately excluded.

*C4 words:* character-structure = character(s), backstory/backstories, protagonist(s), personality/personalities,
motivation(s), arc(s); argument/research = thesis, research, sources, statistics, evidence, citation(s).

*Descriptive only (no criterion):* plot devices, worldbuilding, human-workflow ("beta readers", "demo", "routine"), tooling
("database", "algorithm") category counts per run.

## What each verdict means
- **PASS** — no contradiction found in these runs. **Not** proof, and not a statement about any other model, populated memory,
  or desirability.
- **FAIL** — that finding does **not** survive sampling variation; the evidence record and ADR §10.4 must say so.
- **REVIEW** — read the printed steps; the lexicon is a proxy and can hit harmlessly or miss.
- **INSUFFICIENT** — not enough valid runs; rerun.

## Not concluded, whatever the verdict
That the observed behavior is desirable or undesirable; that any of options A–D is correct; anything about ADR-KERNEL-07's
status (still PROPOSED); behavior with a different model or hardware.

## Known weaknesses (stated now, not discovered later)
- **The thresholds are partly calibrated on run 0** (median 7; 9 of 11 over the cap; story plans all had character steps).
  C1/C2/C4 therefore test *stability around run 0* more than an independent hypothesis. C1 is the exception: it was an
  independent hypothesis (single-step plans) that run 0 refuted.
- Run 0's step texts are not available to the mechanical screens; it is shown for step counts only.
- The keyword screens are proxies; the harness's earlier word-novelty label was saturated and is **not** used here.
- Only 3 runs by default; llama3:latest only; default sampling; one machine.
- Latency and timeouts vary; a run that times out is invalid, not a counterexample.

## Deviation 1 — execution method and replay guard (added after the first batch; post-hoc, criteria untouched)
**What happened.** The first repeated-run batch (2026-10-09, `llama3:latest` id `365c0bd3c000`, tool at `258a58a`, 3 runs) ran the
preflight and all runs inside **one Python process**. `core/provider_mesh.py` sends every model call through a module-level
prompt cache (`core/prompt/cache.py`: keyed by the full prompt, 1 h TTL, never cleared) and a shared network client. Run 1 was a
genuine sample (≈ 6.3 min). Runs 2 and 3 finished in 0 s and 15 s with nearly every model call at 0 ms, and every per-request step
count, total and category count was identical to run 1: they were **replays of run 1 served from the cache**, so the tool's own
"Overall: PASS" over 3 "valid" runs carried **no information about stability**. (The first call of each later run also failed
with `Event loop is closed`: a shared client bound to the previous run's event loop.) That batch is kept as a **diagnostic
record** and does **not** count toward C1–C4. The earlier single-invocation run 0 is unaffected (11 different prompts, one pass,
every call took ≥ 12 s).

**What changed (execution method only).**
1. The preflight and **each run execute in their own fresh process** (`live_check_repeat.py _worker`): empty prompt cache, fresh
   provider and network singletons, its own event loop. The parent process never makes a model call.
2. A **replay guard** excludes a run from the valid set (it is listed as NOT EVIDENCE with the reason) when either (a) it finished in
   less than **2 s per escalating request** (a coarse floor, far below the ≥ ~25 s per request seen in real runs and above the
   observed 0 s and ~1.4 s per request of the replays), or (b) its output (request, interpretation and steps of every escalating
   request) is byte-identical to an earlier run of the same batch — such a run cannot be told apart from a replay, so it is not an
   independent sample. The earliest of a group of identical runs stays. A backend that is genuinely deterministic would therefore
   yield INSUFFICIENT, which is the honest result for a repeat that repeats nothing.
3. `compare` prints which files were dirty at batch start and whether every run really ran in a fresh process; a batch made before
   this fix is labelled **isolation NOT GUARANTEED**.

**What did not change.** C1–C4, every threshold, the lexicon, the 2-valid-run minimum, and the question. The guard thresholds are
not criteria; they are validity checks and, being introduced after seeing data, are **post-hoc** (the first batch's own verdicts:
runs 1–3 "valid", Overall PASS — **withdrawn**, see above; re-evaluated with the guard: run 1 valid, runs 2–3 excluded ⇒ INSUFFICIENT).

## Changing this protocol
Any threshold or lexicon change made **after** seeing repeated-run data must be reported as post-hoc, together with the
original criteria and their verdicts.
