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
plan `redundant` / `generic` / `speculative`. It touches no capability registry, memory, or real event
log; the prompt cache is in-process only, so no state persists. **Label = word-level proxy; read the steps.**

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
(Running the app can rewrite `config/*.toml` and `data/*`; if `git status` shows changes there,
discard them with `git checkout -- config data` — they are not part of this check.)

## Is the run usable as evidence? (run this before sending anything back)
```python
python3 - <<'PYEOF'
import json, sys
d = json.load(open("live.json"))
esc = [r for r in d["rows"] if r["would_escalate"]]
norm = lambda s: " ".join(s.lower().rstrip(".").split())
degraded = [r["request"] for r in esc if r["degraded"]]
echoed = [r["request"] for r in esc if norm(r["interpretation"]) == norm(r["request"])]
print(f"mode={d['mode']} not_evidence={d['not_evidence']} escalating={len(esc)}/{len(d['rows'])}")
print(f"rows with a degraded model call: {len(degraded)}")
print(f"rows where interpretation == request verbatim: {len(echoed)}/{len(esc)}"
      "  (if ALL: the intent step probably fell back to its placeholder; do not trust)")
ok = d["mode"] == "LIVE" and not d["not_evidence"] and not degraded and len(echoed) < len(esc)
print("USABLE AS EVIDENCE" if ok else "NOT USABLE -- see above")
sys.exit(0 if ok else 1)
PYEOF
```
**Why the second check exists:** if every provider fails, the intent step does not raise — it returns a
placeholder hypothesis (`novel`, score 0.1). The harness cannot see that, so "interpretation equals the
request in every row" is the tell. The check is a heuristic.

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
