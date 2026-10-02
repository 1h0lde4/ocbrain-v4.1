# Runbook — live check of the draft-plan risk (ADR-KERNEL-07 §10.4)

**Purpose.** Establish whether the draft plan steps shown next to a content-anchor clarification
question add useful context or introduce speculation. **Status of that question today: UNKNOWN**
(ADR-KERNEL-07 §10.4) — it has never been run against a real model. This runbook produces the
evidence. It does **not** enable the feature, change code or config, or accept the ADR.

`scripts/live_check_draft_plan.py` is already on `main` (merged with PR #41). Open the Codespace on
`main`; this runbook can be read from this branch/PR.

## What the script does (and does not)
Runs the pipeline's **two real model calls** — `interpret_request()` (module `intent_interpreter`) and
the planner's decomposition (module `planner_decompose`) — on 11 requests that the content-anchor
detector would escalate (8 form-only, 3 long-form chosen to tempt multi-step plans). Per step it
reports the content words that appear in neither the request nor the interpretation, then labels the
plan `redundant` / `generic` / `speculative`. It does not use the capability registry and writes no events to the real
event log. It **does** use the local memory store: `interpret_request()` falls back to the global memory singleton, so a first run creates
*empty* databases `.data/memory/unified.db` and `archive.db` (git-ignored; verified 0 rows) and searches them. The prompt cache is
in-process only. **Label = word-level proxy; read the steps.**

## Prerequisites (verified from the repo)
| Need | Fact |
|---|---|
| Python | 3.12 (what CI uses): `pip install -r requirements.txt` |
| Provider | Both modules resolve to **Ollama at `http://localhost:11434`** (`[global] ollama_host`) using model **`llama3`** unless `bootstrap_model` is set for that module name in `config/models.toml` (neither module has an entry → default `llama3`) |
| Fallback provider | An OpenAI-compatible provider exists but has **no API-key support** and is fixed to `localhost:8080/v1` (the config key only gates it) → **hosted APIs will not work**; use Ollama |
| Which model | Use the model you actually deploy. The result characterizes **that model only**; record it (step 5) |
| Machine | Ollama on CPU is slow: 11 requests × 2 calls ≈ 22 generations. Prefer ≥ 4 cores / 16 GB RAM; expect roughly 10–30+ minutes for an 8B model. (Estimate, not measured) |

Ollama install/serve/pull commands below are the standard ones and were **not verifiable from the
authoring sandbox** (no access to ollama.com); adjust to your environment.

## Steps
```bash
# 0. Keep results out of git (live.json is NOT git-ignored)
printf 'live.json\nlive.meta.txt\nlive.out.txt\n' >> .git/info/exclude

# 1. Environment
pip install -r requirements.txt

# 2. Provider (standard Ollama commands; unverified from the authoring sandbox)
curl -fsSL https://ollama.com/install.sh | sh
(ollama serve > /tmp/ollama.log 2>&1 &) ; sleep 5
ollama pull llama3                       # or the model you deploy; see Prerequisites
curl -s localhost:11434/api/tags         # must list the model

# 3. Smoke test with ONE request: must exit 0 with an empty "degraded" list
printf 'write a story\n' > /tmp/one.txt
python scripts/live_check_draft_plan.py --prompts /tmp/one.txt ; echo "exit=$?"

# 4. The real run
python scripts/live_check_draft_plan.py --json live.json | tee live.out.txt

# 5. Record WHICH model/environment produced it (the JSON does not)
{ date -u; git rev-parse HEAD; python --version; ollama list; } > live.meta.txt 2>&1
```
Do **not** edit `config/*.toml`, commit anything, or enable `creative_content_anchor_enabled`.
The harness itself only creates the git-ignored `.data/` directory; `git status` should stay clean. If it shows changes under
`config/` or `data/`, they did not come from this check — discard them with `git checkout -- config data`.

## Is the run usable as evidence? (run this before sending anything back)
```python
python3 - <<'PYEOF'
import json, sys
d = json.load(open("live.json"))
esc = [r for r in d["rows"] if r["would_escalate"]]
degraded = [r["request"] for r in esc if r["degraded"]]
counts = [len(r["steps"]) for r in esc]
print(f"mode={d['mode']} not_evidence={d['not_evidence']} escalating={len(esc)}/{len(d['rows'])}")
print(f"rows with a degraded model call: {len(degraded)}")
print(f"steps per plan: {counts}")
ok = d["mode"] == "LIVE" and not d["not_evidence"] and bool(esc) and not degraded
print("USABLE AS EVIDENCE" if ok else "NOT USABLE -- see above")
sys.exit(0 if ok else 1)
PYEOF
```
**What makes a run usable:** live mode, and *no degraded model call* in any escalating row (the harness records a failed or empty
decomposition in `degraded`). **Note — `interpretation` equal to the request is NORMAL, not a warning sign:** the Goal's `description`
is the user's raw request by design (`structured_form["description"] = intent.raw_request`, `core/cognitive/intent.py:1090`). The
plan steps are generated from that text, so `interpret_request()`'s own success does not affect what this check measures. (An earlier
draft of this runbook treated "interpretation == request in every row" as a sign the intent step had fallen back; that was an
unverified assumption and would have rejected valid runs, including the first real one.)

## Send back
`live.json`, `live.out.txt`, `live.meta.txt`. They contain only the 11 prompts and the model's outputs; no secrets.

## Reading the result (the disposition is Moncif's, not the script's)
| Outcome across the 11 | What it suggests (ADR-KERNEL-07 §10.4) |
|---|---|
| mostly `redundant` | the plan just restates the interpretation line → option: omit a plan equal to the interpretation |
| `speculative` steps recur | steps invent premise content the user never gave → option: `plan_steps=[]` |
| mostly `generic` | harmless but possibly low value → keep, or drop for brevity |
Neither option is applied in the repo. Eleven requests and one model are a **small sample**; say so when recording the result.

## Afterwards (the agreed sequence)
Record the result as evidence in ADR-KERNEL-07 §10.4 (it does **not** turn the ADR into an acceptance), then reconcile
`CURRENT_STATE.md`, `KNOWN_ISSUES.md` and the roadmap from the verified state. Keep the failure accounting split: the 16
sandbox `FAILED` IDs are environment artifacts, the 8 collection errors remain uncharacterized.

## Troubleshooting
**Every call fails with `404 Not Found` for `http://localhost:11434/api/generate`** (seen in the first Codespace run, 2026-10-02).
A 404 arriving in ~2 ms means a server **is** answering and rejecting the request — not "connection refused". For Ollama that almost
always means the model is not installed under the name the code asks for (`llama3`). *(Inference from the error shape; the response
body was not captured.)* Confirm and fix:
```bash
curl -s localhost:11434/                  # expect: "Ollama is running"  (anything else = something else owns port 11434)
curl -s localhost:11434/api/tags          # lists installed models; is "llama3" there?
curl -s localhost:11434/api/generate -d '{"model":"llama3","prompt":"hi","stream":false}'   # the error body names the missing model
ollama pull llama3                        # fix A: install the model the code asks for
ollama cp <installed-model> llama3        # fix B: you already have another model — alias it; no config edit needed
```
Then repeat the **smoke test (step 3)** before the real run. (Fix C — setting `bootstrap_model` under `[intent_interpreter]` and
`[planner_decompose]` in `config/models.toml` — works but edits tracked config; prefer A or B.)

**The report is buried in `[ProviderMesh]` log lines.** The report starts at the line `MODE:`. View just it: `sed -n '/^MODE:/,$p' live.out.txt`.

**`L1 FTS5 search failed (non-blocking): fts5: syntax error near "."` appears once.** Expected and unrelated to this check: a request
containing a period (`'Write a 500 word story.'`) hits a pre-existing gap in `_fts_escape()` (documented for `?` in
`docs/reports/SESSION4B_REPORT.md`; the real scope is broader). It is not a sign the run failed.

## Limitations of the environment
A fresh Codespace has an **empty memory store**, so no promoted Intent Ontology categories are loaded (`known_categories`). The
interpretation step may therefore differ from a populated deployment. Record that when you report the result.
