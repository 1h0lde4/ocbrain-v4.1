# Live check of the draft-plan risk — first valid result (llama3, n = 11)

**Status:** evidence record for ADR-KERNEL-07 §10.4. It does **not** accept the ADR, and it applies no
containment; the disposition is Moncif's. Method: `OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RUNBOOK_OCT2026.md`.

> **Update (2026-10-12).** A pre-registered repeated-run batch (3 runs, same model) is recorded in
> "Repeated-run evidence" below: **Overall FAIL (C1)** — a rare single-step plan. Its limits replace "one run" for
> questions of stability; everything else in this record still describes run 0.

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
**1. The hypothesis test — REFUTED (for run 0 only).** I expected a single-step, "redundant" plan that merely
restates the request. This run did not produce one: 0 of 11 plans were single-step (median 7 steps). That is all this
experiment tests. *Qualified 2026-10-12:* in the repeated batch 1 of 33 plans was single-step (`tell me a joke`), so
single-step plans do occur — rarely, and so far only for that request. My expectation was too strong, and the later
universal claim "every plan is multi-step" (C1) was too strong in the other direction; see "Repeated-run evidence".

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
variance across runs *(partly addressed since: see "Repeated-run evidence")*, or any effect on user outcomes. My earlier expectation — a single-step "redundant" plan — was
**wrong** for this model, and my claim that the plan input is "the interpretation, not the raw request" was also wrong.

## Repeated-run evidence (2026-10-12) — batch `20261012T121543Z`
**Status:** evidence only. Overall verdict **FAIL (C1)**, exactly as computed under the pre-registered criteria. This
section does not accept ADR-KERNEL-07, applies no containment, and does not choose among options A–D.

> **Limits.** One model, three runs, 11 prompts, sampling uncontrolled, a fresh and empty memory store. "PASS" here
> means *no contradiction found in these runs*, not proof. The C3 human review covered the flagged steps and the joke plans, not all 252 steps (see below). Nothing in
> this section is a robust model-wide result.

### Method and history (so the numbers are not over-read)
- **Protocol:** `docs/studies/OCBRAIN_LIVE_CHECK_REPEAT_RUNS_PROTOCOL_OCT2026.md`, criteria C1–C4 and thresholds
  pre-registered before any data; **not changed after seeing data**. That file and the tool are on `main` since PR #61
  was merged on 2026-10-14 (merge commit `4b90ed94d038a5d2e765ca517e94608b78f556a6`). `e305f20` — the commit that produced
  this batch — is an **ancestor of `main` (verified)**, as are `851d4ee` and `7044fdb`. Two amendments were made **after** this
  batch ran and before the merge: `851d4ee` rewords the replay guard as a suspicion screen, not a proof of replay (Deviation 1
  text), and `7044fdb` adds the model-identity validity rule (Deviation 2, found by review, not by data). Criteria and
  thresholds are unchanged; recomputed with the final tool, this batch's `report.md` is byte-identical to the supplied one.
- **First batch (2026-10-09, tool at `258a58a`): INVALID.** Runs 2 and 3 were indistinguishable from replays of run 1
  (byte-identical output, nearly every call at 0 ms), which the in-process prompt cache explains, so its "Overall: PASS" is **withdrawn**; kept only as a diagnostic
  record. The fix (one fresh process per preflight and run) and a replay guard are protocol **Deviation 1**, commit
  `e305f20`.
- **Two interrupted batches** (2026-10-09 23:59 UTC and 2026-10-10 00:40 UTC; one completed isolated run each, then the
  process stopped for a reason not established — host disk exhaustion is Moncif's unverified hypothesis): supplementary
  only, **not counted** toward C1–C4.
- **This batch is the first complete, valid one.**

### Provenance (captured automatically by the tool unless marked)
| Item | Value |
|---|---|
| Batch / window (UTC) | `20261012T121543Z`, 2026-10-12T12:15:43Z → 12:39:40Z |
| Tested commit | `e305f2091802a02b01d607b9baf05fa08fdc6535` (PR #61's branch `tools/live-check-repeat-runs`; merged into `main` on 2026-10-14, so now an ancestor of `main`). Tree "dirty" **only** by three untracked files — `.ocbrain_install_state`, `.python-version`, `.python_selected` (referenced only by `setup.sh`; no tracked file modified, none read by `core/`, `scripts/`, `config/`) |
| Tool / harness SHA-256 | `463d6b934f8a694bf13188fa6243ef617d9fb03f12d8fef8a4589577d64724f4` / `70b3ed9d3bd4ade6958f39f7aedc652773087d1d159b844a56a0b153b16ddc64` — both **verified equal** to the files at `e305f20` |
| Model | `llama3:latest`, ID `365c0bd3c000`, 4.7 GB; `ollama show`: architecture `llama`, 8.0B, context 8192, embedding 4096, Q4_0; Meta Llama 3 license (Apr 18, 2024). `ollama list` MODIFIED "2 days ago" before and after; **ID unchanged before/after** (tool check true) |
| Environment | `Linux-6.8.0-1064-azure-x86_64-with-glibc2.39`, Python 3.11.9 — an Azure-hosted Linux VM, consistent with a Codespace (not independently confirmed; not a local machine) |
| Isolation | preflight pid 6906; runs pid 7728, 12096, 16424 — each in its own fresh process |
| Sampling | uncontrolled, as in run 0 (the code sends only `model`, `prompt`, `stream: false`) |

| Run | Start → end (UTC) | Duration | Worker pid |
|---|---|---|---|
| 1 | 12:17:09 → 12:24:24 | 7.2 min | 7728 |
| 2 | 12:24:24 → 12:31:51 | 7.5 min | 12096 |
| 3 | 12:31:51 → 12:39:40 | 7.8 min | 16424 |

### Validity checks (done, not assumed)
| Check | Result |
|---|---|
| Valid runs | **3 of 3** (LIVE; no degraded row in any run; no replay flag) |
| Independent samples | three **distinct** output fingerprints; wall-clock 7.2–7.8 min per run (the suspected replays took 0–15 s) |
| Recomputation | `compare` re-run on the supplied archive. With the tool at `e305f20`, `report.md` and `compare.json` are **byte-identical** to the supplied ones. With the final tool (`7044fdb`, identical to `main`), `report.md` is **byte-identical**, and `compare.json` differs only by one added field, `evaluation.model_identity` (the Deviation 2 record in the next row: `established: true`, `365c0bd3c000` before and after); the verdict (FAIL on C1) and every other field are unchanged |
| Model identity (Deviation 2) | **established**: the `ollama list` ID was `365c0bd3c000` before and after the batch. The rule was added after the batch ran; the final tool gives the same verdicts for it |
| Harness label | `speculative` on 11 of 11 plans in every run — saturated, **carries no information** (as in run 0) |

### Verdicts, exactly as computed
| Criterion | Verdict |
|---|---|
| C1 every plan multi-step (no single-step plan in any run) | **FAIL** |
| C2 per-run median steps in [5,9] and ≥ 7 plans over the 5-step cap | PASS |
| C3 no concrete-premise word in any step (lexicon screen; human read still required) | PASS (automated) · human review of the flagged steps and the joke plans: **PASS, qualified on run 2** (see below) |
| C4 form/process presupposition recurs (≥ 5 story plans with a character step and ≥ 1 essay plan with an argument/research step, every run) | PASS |
| **Overall** | **FAIL** |

| Run | median | total steps | single-step | over cap | premise-word hits | story→character | essay→argument |
|---|---|---|---|---|---|---|---|
| 0 (supplied, earlier) | 7 | 83 | 0 | 9 | n/a | n/a | n/a |
| 1 | 8 | 87 | 0 | 9 | 0 | 6/6 | 2/2 |
| 2 | 7 | 79 | 0 | 10 | 0 | 6/6 | 2/2 |
| 3 | 8 | 86 | 1 | 10 | 0 | 6/6 | 2/2 |

Steps per plan:
| request | run 0 | run 1 | run 2 | run 3 |
|---|---|---|---|---|
| write a 1000 words story | 7 | 7 | 7 | 9 |
| write a story | 6 | 9 | 8 | 7 |
| write a poem | 7 | 8 | 8 | 6 |
| write me an essay | 7 | 13 | 7 | 12 |
| tell me a joke | 5 | 4 | 4 | 1 |
| write a long story please | 11 | 8 | 8 | 9 |
| Write a 500 word story. | 5 | 8 | 8 | 8 |
| compose a song | 7 | 5 | 7 | 8 |
| write a novel | 9 | 8 | 7 | 9 |
| write a 5000 word story | 7 | 10 | 7 | 7 |
| write a 10000 word essay | 12 | 7 | 8 | 10 |

### C1: a counterexample, not a defect finding
In run 3, `tell me a joke` produced **one** step: *"Conjure a memorable punchline from the vast repository of known humor."* The same request produced four steps in run 1 and
four in run 2 (run 1: Think of a joke that is likely to be understood and appreciated by the target audience.; Come up with a clear and concise setup for the joke.; Create a punchline that is surprising yet makes sense in hindsight.; Put the setup and punchline together to form the joke.; run 2: Choose a joke topic or theme; Select a punchline; Create a setup or premise for the joke; Combine the setup and punchline to form the joke).
- This is a **counterexample to the universal claim "every plan is multi-step"** for this model at default sampling.
- It is **not** evidence that single-step plans are defective, that one step is wrong for a joke, or how often the
  case occurs beyond this sample: **1 of 33** plans in this batch; **2 of 77** across all independent samples seen
  (run 0, the invalid batch's run 1, the two interrupted batches' run 1, and this batch — supplementary, mixed
  environments, not pre-registered), both for `tell me a joke` (step counts for that request across those samples:
  5, 5, 3, 1, 4, 4, 1).
- It qualifies the earlier "hypothesis test — REFUTED" below: that conclusion holds for run 0 only.
- **Validity of the counterexample run:** run 3 is part of a valid batch (3 of 3) — LIVE, no degraded row, its own fresh
  process (pid 16424), 7.8 min, output fingerprint distinct from runs 1–2, no replay flag. The **C1 verdict FAIL is
  preserved**: the criterion was not changed, and the C3 review below neither offsets nor modifies it.

### C3: review status
- **Automated:** PASS — the 55-word lexicon found no hit in 252 steps.
- **Read review by Claude (an AI reader), 2026-10-12:** read **all 252 steps** of the three run files, plus a broader
  screen (extra genre/topic words, mid-sentence capitals) that flagged 3 steps, all for the generic word
  "historical" in research/setting steps ("Research and fact-check any historical, scientific, or cultural details…",
  "Conduct research on the story's setting, including historical events…", "…any relevant historical or scientific
  context"). **No step names a concrete subject, genre, character, setting or premise.** Generic mentions only: "decide
  the tone and genre" (asks to choose one; names none).
- **Observed process/form presuppositions (descriptive):** character profiles and backstories (all story plans, every
  run); outlines and drafts for a one-line request; "beta readers" and "publish in print and digital formats" (novel
  plans); "record a rough demo" (song plans); "query letter, synopsis, and other marketing materials" (run 1 novel
  plan); advice that reads as addressed to a human author.
- **Human review (Moncif), 2026-10-13 — scope: the three flagged steps and the three joke plans, not all 252 steps.
  C3: PASS for the three "historical" examples, with a scope qualification on run 2.**
  - Run 1, "write a novel": acceptable; research and fact-checking are limited to historical, scientific or cultural
    details integral to the plot or setting.
  - Run 2, "write a long story please": the instruction to research historical events, cultural context and
    geographical details is overly broad for an unspecified story; it should ideally be conditional on the setting
    and story requirements. A **plan-quality concern, not evidence that a concrete premise has been invented**.
  - Run 3, "write a long story please": acceptable; it refers to *relevant* historical or scientific context, which
    does not require those elements in every story.
  - The word "historical" alone does not establish that the plan invented a concrete premise; the three examples do
    not justify a C3 failure.
- **Joke plans — structural assessment (Moncif; plan quality, separate from C3 and from C1):** runs 1 and 2 are
  coherent four-step plans (choosing a punchline before constructing the setup is a legitimate approach); run 3 is
  **unsatisfactory as a complete plan** for "tell me a joke": a punchline-generation step only, no setup, and the
  "vast repository of known humor" wording — which does not establish copying but is a less appropriate formulation
  than explicitly constructing a joke.
- **C3 status:** automated PASS; AI read of all 252 steps; human review of the flagged steps and the joke plans: PASS
  (qualified). **Not done:** a human read of all 252 steps. The human C3 disposition is recorded separately from the C1
  result, which stays **FAIL**.

### What the repeated runs show — and do not show
- **Held in all three runs:** C2–C4 features — median 7–8, 9–10 of 11 plans over the display cap, a character step
  in every story plan, an argument/research step in both essay plans, no concrete-premise word.
- **Varied between runs:** wording (distinct fingerprints) and step counts per request (essay 7–13, joke 1–4, 5000-word
  story 7–10, 10000-word essay 7–10); category counts differ (e.g. plot-device plans 1 / 2 / 5).
- **Not shown:** behavior of other models or of a populated memory store; any effect on user outcomes; that the
  multi-step generic workflow is desirable or undesirable; which of A–D is correct. "Held in all three runs" is not
  "robust": three runs, one model, uncontrolled sampling.

### Artifacts and where they live
- **In the repository:** `docs/studies/evidence/live-check-draft-plan-batch-20261012T121543Z.zip` — the archive exactly
  as supplied by Moncif (supplied name `archive.zip`; **only the file name differs, the bytes are unchanged**), added
  by commit `ad3a7e79f7d30c66ed3535dc4a4715198e2e507b` on this branch (PR #45). **21,632 bytes**; SHA-256
  `b6d51a901d89ca3e8f19a7add0c1b11dc6aba8b7936b8db1ada309552bff2f0f`. **Independently verified 2026-10-13:** the hash of the supplied file, of the blob in
  that commit, and of a copy downloaded back from the remote after the push are identical, and `unzip -t` reports no
  errors. The contents were scanned beforehand: no tokens, emails, home paths or IP addresses. The repository is public.
- **Second copy in an access-controlled store:** to be retained (decision of 2026-10-13). **Not yet recorded as
  placed:** its location will be recorded here once the copy has actually been placed there; nothing is claimed about
  it now.
- **Members (SHA-256):**
  `meta.json` `09305493b490621d41e64d8ac85968df91c1dae98a87e1661bce1cd5d032928e` ·
  `run1.json` `802c99df5f28b44c9a11cffa6a7f768c4084a39fecc1ebfdadd730eff2730ae2` ·
  `run2.json` `a5cee0a386de8103281eb48a49779f816e4feaed347c414ab2c304f8c364ed24` ·
  `run3.json` `49a4fe343a91e0f68b04991298342448fb75c827aacab635164f2de6390dfcb7` ·
  `compare.json` `561eac17c3d79817698cffad51a0b49c55227e3e9c847634c29e6885ddbbd483` ·
  `report.md` `7b5786d025e83d5618c31fdda8c67d596efddd8154e94d3a9435c9e19651105f`.
- The batch cannot be regenerated identically (sampling is stochastic). The batch's own `live_runs/` directory stays
  out of git by design; the committed archive is the evidence copy.

### Applicability to current `main`
Static comparison only; the harness was **not** re-run on current `main`. Between the tested commit `e305f20` (product
code identical to `main` @ `80a1bb8`) and `main` @ `1d813bd` (the commit immediately before PR #61 merged; that merge adds only the repeat-run tool, its protocol and
its tests): `core/cognitive/content_anchor.py`,
`core/cognitive/compiler.py` and `core/governance/orchestration_governor.py` are **identical**; `core/orchestrator.py`
differs only in the workflow-failure answer, `core/model_router.py` changed (FZ-02; not referenced from the harness or
cognitive path by a static search), `config/settings.toml` differs by a comment. A change on those paths would
require re-qualifying these findings.

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
the main limits; it is optional. *(Done once on this model: the 3-run batch above; a second model remains unrun.)*

The repeated-run evidence does not select among A–D and applies none: choosing is Moncif's explicit decision, to be
implemented, if any change is chosen, in a separate PR from `main`.
