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
   A one-request **preflight** aborts the batch (exit 2) if the provider is not answering cleanly.
3. `python scripts/live_check_repeat.py compare live_runs/<batch_id>` → `report.md` and `compare.json`.
4. Send back the whole `live_runs/<batch_id>/` directory (prompts and model outputs only; no secrets).

**Captured automatically** (so it cannot be forgotten, unlike last time): repo commit, branch and dirty state; Python and
platform; SHA-256 of the tool and of the harness; `ollama list` and `ollama show <model>` **before and after** the batch and
whether the model ID changed in between; each run's UTC start and end; each run's full JSON.

## A run is valid iff
mode `LIVE`, not flagged `not_evidence`, at least one escalating request, and **no degraded model call in any escalating
row**. Invalid and synthetic runs are excluded and listed. **Fewer than 2 valid runs ⇒ INSUFFICIENT**; no criterion is evaluated.

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

## Changing this protocol
Any threshold or lexicon change made **after** seeing repeated-run data must be reported as post-hoc, together with the
original criteria and their verdicts.
