# Live check of the draft-plan risk — first valid result (llama3, n = 11)

**Status:** evidence record for ADR-KERNEL-07 §10.4. It does **not** accept the ADR, and it applies no
containment; the disposition is Moncif's. Method: `OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RUNBOOK_OCT2026.md`.

> **Read first — limits.** 11 prompts, **one** model, **one** run. These are *observations*, not evidence of
> general behavior across models, runs, or a populated memory store. The model identity was recovered only after the
> fact and sampling was uncontrolled, so a re-run is expected to differ (see Provenance). Nothing here proves that any particular response to it (options A–D) is correct.

## Provenance
- **Run 1:** every call failed with `404 Not Found` at `/api/generate` (1–3 ms). `mistral` was installed, `llama3`
  was not — confirming the diagnosis in the runbook (a server answering, model not installed under that name).
- **Run 2 (this record):** `mistral` removed, `llama3` installed. Console output supplied by Moncif in chat.
- **Model identity: RECOVERED AFTER THE FACT.** Moncif supplied the complete output of `ollama show llama3` and
  `ollama list`, run *after* the experiment:
  - **`llama3:latest`, ID `365c0bd3c000`, 4.7 GB**; architecture `llama`; **8.0B parameters**; context length 8192;
    embedding length 4096; **quantization Q4_0**; capability `completion`; the Llama 3 chat-template parameters
    (`num_keep 24`, stop tokens `<|start_header_id|>`, `<|end_header_id|>`, `<|eot_id|>`); license
    `META LLAMA 3 COMMUNITY LICENSE AGREEMENT`, `Meta Llama 3 Version Release Date: April 18, 2024` (the original
    Llama 3 release).
  - **It applies to the run only if the installed model is unchanged since.** `ollama list` showed `MODIFIED 37 hours
    ago` (relative to the listing). The model was installed before the experiment, and a re-pull afterwards would have
    reset that time, so the listing is consistent with this being the model that ran — but it is **not proof**,
    because the experiment's own timestamp was not captured. (Optional: compare `ls -l --time-style=full-iso
    live.json` with the date implied by "37 hours ago".)
  - **Sampling was uncontrolled.** The code sends only `{"model", "prompt", "stream": false}` to `/api/generate`
    (`core/provider_mesh.py:90`); no temperature, seed, top_p or token cap is set anywhere on the two call paths, and
    the model's own parameters set only `num_keep` and the stop tokens. Ollama's runtime defaults therefore applied
    (sampling is stochastic; Ollama's documented default temperature is 0.8 — from its docs, not verified here). A
    re-run is **expected to differ in wording**; whether the structural findings (multi-step generic workflow) are
    stable across runs is unknown.
  - **Still not captured:** repo commit, Python version, run date/time (`live.meta.txt`), and `live.json`.

## Is it valid evidence? (checked against the code, not assumed)
| Check | Result |
|---|---|
| Mode / harness verdict | `LIVE`; no "NOT EVIDENCE" banner; **no `degraded:` line in any of the 11 rows** |
| Plans model-generated? | yes — every plan is multi-step; the decomposition fallback is a *single* step equal to the request |
| Model calls | **22 attempts: 21 successful, 1 timeout** (= exactly 2 attempts per request; the attempts are not all completed calls). The 21 successes took 12.4–38.5 s each; the 1 failure was a `TimeoutError` at 60,138 ms. Calls run in order (interpret, then decompose, per request), and the FTS5 warning appears after 12 completed calls, i.e. at the start of request 7 — the only request containing a period — which corroborates that ordering. So the timed-out call was **request 1's interpretation call** (cold-start suspected, **unverified**). It cannot affect the steps (see next row), and request 1's 7-step plan shows its decomposition call succeeded |
| Does the intent step matter here? | **No.** `structured_form["description"] = intent.raw_request` (`core/cognitive/intent.py:1090`): the plan steps are generated from the raw request, so `interpret_request()`'s own success does not affect what is measured. `interpretation == request` in every row is therefore **normal**, not a failure sign |
| `FTS5 syntax error near "."` (once) | expected, unrelated: the only request with a period ("Write a 500 word story.") hit the pre-existing `_fts_escape()` gap |

## What was observed
| # | Request | Steps | Shown to the user (cap 5) |
|---|---|---|---|
| 1 | write a 1000 words story | 7 | 5 (+2 more) |
| 2 | write a story | 6 | 5 (+1) |
| 3 | write a poem | 7 | 5 (+2) |
| 4 | write me an essay | 7 | 5 (+2) |
| 5 | tell me a joke | 5 | 5 |
| 6 | write a long story please | 11 | 5 (+6) |
| 7 | Write a 500 word story. | 5 | 5 |
| 8 | compose a song | 7 | 5 (+2) |
| 9 | write a novel | 9 | 5 (+4) |
| 10 | write a 5000 word story | 7 | 5 (+2) |
| 11 | write a 10000 word essay | 12 | 5 (+7) |

**83 steps in total; median 7 per plan; 0 of 11 single-step; 9 of 11 plans exceed the display cap.**

**The harness label is saturated.** It labeled 11 of 11 plans `speculative` (80 of 83 steps flagged), because generic
planning vocabulary — *develop, including, clear, key, main, overall, ensure* — counts as "content". The label
carries no information here; **read the steps, not the label.**

## Reading of the steps (one reader — the author; verify it)
1. **No step names a concrete subject, genre, character, setting or premise** (0 of 83). The strict form of the
   reviewer's worry — the model inventing "a detective story" — was **not observed**.
2. **Most steps are generic authoring workflow**: brainstorm / outline / draft / revise / edit / proofread /
   finalize. Any writing request would produce them.
3. **A minority presuppose form or process the user never chose**: character profiles, backstories and arcs
   (story plans); plot twists; a thesis statement plus "credible sources, data, and statistics" (essays); chord
   progressions and "record a demo" (song); "establish a writing routine", "get feedback from beta readers"
   (novel); "select a joke from a database or generate a new one using a joke generation algorithm" (joke).
   Several of these are advice to a human author, not tasks for an executing model.
4. **The strongest argument for keeping the plan:** several steps tell the user what happens to the missing
   content — "Generate a theme or topic for the poem", "Develop a tone or mood", "Develop a concept and plot".
   That makes explicit that *unspecified dimensions get decided by the system*. But the question already says
   so ("or say 'surprise me' and I'll choose"), so the plan adds little beyond it.
5. **The first five steps are the ones shown**, and in story plans they are exactly the content-presupposing ones
   (concept → outline with character arcs → character profiles); the generic edit/proofread steps are cut.

## Two separate conclusions (do not merge them)
**1. The hypothesis test — REFUTED.** I expected a single-step, "redundant" plan that merely restates the request.
This run did not produce one: 0 of 11 plans were single-step (median 7 steps). That is all this experiment tests.

**2. What the system actually does — observed, not judged.** With a request the detector flags as lacking content,
the model still produces a multi-step generic workflow; it invents no concrete premise, but it fills the missing
task structure with workflow and form assumptions (characters and backstories, a thesis with researched sources,
chord progressions, "beta readers", a joke "database"). The steps add almost nothing toward *what should it be
about?* — the question the response asks.

**Not established: that this behavior is undesirable, or that any specific response to it is correct.** Whether a
user is better served by seeing the plan, a shorter plan, or none is a product/architecture judgment. This run
informs that judgment; it does not make it.

## What the user would actually see (shipped Option C response, fed with this run's real steps)
```
USER: 'write a 1000 words story'
Here's how I read your request: write a 1000 words story

My draft plan: 1. Develop a concept and plot for the story.; 2. Create a detailed outline of the story's structure,
including character arcs and key events.; 3. Develop character profiles, including backstories, motivations, and
personalities.; 4. Write a first draft of the story, following the outline and staying within the 1000-word limit.;
5. Revise the first draft, refining the writing, character development, and plot execution. (+2 more)

Before I write this story, what should it be about? A subject, genre, or tone is enough (for example: a noir
mystery, a cozy fantasy, a funny office comedy) — or say "surprise me" and I'll choose. Please send your request
again with those details.
```
(The "joke" request renders the same question, including "a noir mystery, a cozy fantasy…".) Defects visible only
with real output, none caught by the synthetic tests:
- **"Here's how I read your request: …" is an echo.** `description` is the raw request; the only real interpretation
  the Intent stage produces is the hypothesis category label. ADR §2 item 4 / §9 had called it "the interpreted intent".
- **Formatting:** steps ending in a period are joined with semicolons ("story.; 2.").
- **The example text is story-specific for every artifact** (joke, essay, song, poem).

## What this does and does not establish
Establishes: for **llama3 via Ollama**, on these **11** requests, in **one** run, the decomposition is a multi-step
generic workflow, not a restatement and not an invented premise. Does **not** establish: behavior of other models
(e.g. `mistral`), of a populated memory store (a fresh Codespace has none, so no promoted ontology categories),
variance across runs, or any effect on user outcomes. My earlier expectation — a single-step "redundant" plan — was
**wrong** for this model, and my claim that the plan input is "the interpretation, not the raw request" was also wrong.

## Disposition options (none applied — Moncif's decision)
| Option | Change | Notes |
|---|---|---|
| A | pass `plan_steps=[]` | one line in `core/orchestrator.py`; keeps the echoed interpretation line |
| B | A **and** drop the echoed interpretation → **question only** | removes two lines of noise; the author's reading of this evidence favors it |
| C | cap at 3 steps and fix the `; ` joining | keeps a (shorter) plan; the first three steps are the most content-presupposing |
| D | keep as is | the plan does signal that missing content is self-generated, but the question already says so |
The experiment **supports changing** the behavior but does not by itself prove that any one option is the only
correct implementation — choosing among A–D is a product/architecture decision. D-5 as decided says an ESCALATE
*may* surface a question paired with the plan/intent, so A and B stay inside it.
Any of A–C also needs `tests/core/cognitive/test_creative_content_anchor.py` (`TestClarificationResponse`, the
orchestrator "question and plan" test) updated. Independently of A–D, the question's example text should adapt to the
artifact (separate, small change). Re-running the harness on a second model, or twice on this one, would address
the main limits; it is optional.
