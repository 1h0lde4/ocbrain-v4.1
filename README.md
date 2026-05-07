<div align="center">

# ⚙ OCBrain

**The self-learning AI brain for OpenClaw.**  
Modular expert models that start on Ollama and progressively train their own weights — until they run fully independently, with no external dependencies.

[![Version](https://img.shields.io/badge/version-2.1.0-1d9e75?style=flat-square)](https://github.com/1h0lde4/OCBrain/releases)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/1h0lde4/OCBrain/ci.yml?style=flat-square&label=CI)](https://github.com/1h0lde4/OCBrain/actions)

</div>

---

## Table of contents

1. [What is OCBrain?](#1-what-is-ocbrain)
2. [Requirements](#2-requirements)
3. [Installation](#3-installation)
4. [First-time setup](#4-first-time-setup)
5. [Starting the brain](#5-starting-the-brain)
6. [Connecting OpenClaw to the brain](#6-connecting-openclaw-to-the-brain)
7. [Verifying the connection](#7-verifying-the-connection)
8. [Brain API reference](#8-brain-api-reference)
9. [Module maturity model](#9-module-maturity-model)
10. [Adding custom modules](#10-adding-custom-modules)
11. [Knowledge distillation](#11-knowledge-distillation)
12. [Updating](#12-updating)
13. [Project structure](#13-project-structure)
14. [Contributing](#14-contributing)

---

## 1. What is OCBrain?

OCBrain is the intelligence layer for the OpenClaw system. It runs locally on your machine and exposes a REST API that OpenClaw connects to for all reasoning, decision-making, and learning tasks.

It is made up of **expert modules** — each one a small LLM specialised for a domain (coding, web search, general knowledge, OS control). Each module starts by routing queries through an external Ollama model, collects training data automatically from every interaction and from the web, and gradually trains its own weights until it operates with no external dependency at all.

```
OpenClaw hardware/OS layer
         │
         │  HTTP  (localhost:7437)
         ▼
  OCBrain  ◄──── Web crawler (hourly)
  ┌─────────────┐ ◄──── LoRA fine-tuning (daily)
  │ Orchestrator│
  │ ┌─────────┐ │
  │ │ coding  │ │
  │ │ search  │ │
  │ │ knowledge│ │
  │ │ sys_ctrl│ │
  │ └─────────┘ │
  └─────────────┘
```

---

## 2. Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| RAM | 8 GB | 16 GB |
| VRAM (training) | 6 GB | 12 GB |
| Disk | 10 GB | 50 GB |
| [Ollama](https://ollama.ai) | required (bootstrap stage) | — |
| OS | Linux, macOS, Windows 10/11 | Linux |

---

## 3. Installation

Pick one method:

**One-liner — Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/1h0lde4/OCBrain/main/install.sh | bash
```

**pip from GitHub (any OS):**
```bash
pip install git+https://github.com/1h0lde4/OCBrain.git
```

**pip — specific release:**
```bash
pip install https://github.com/1h0lde4/OCBrain/archive/refs/tags/v2.1.0.tar.gz
```

**Clone and run (recommended for development):**
```bash
git clone https://github.com/1h0lde4/OCBrain.git
cd OCBrain
bash setup.sh
```

**Windows:**
```powershell
winget install OCBrain.OCBrain
```

---

## 4. First-time setup

Run `setup.sh` once after cloning. It handles everything:

```bash
bash setup.sh
```

What it does, step by step:

```
1. Checks Python 3.11+
2. Creates .venv virtual environment
3. Installs all core dependencies (requirements.txt)
4. Installs the package in editable mode (pip install -e .)
5. Downloads the spaCy language model
6. Prompts: install training deps? (PyTorch + LoRA, ~3 GB)
7. Prompts: install voice deps? (Whisper, optional)
8. Checks Ollama — pulls mistral if no model found
9. Creates all data directories
```

> **Non-interactive / CI mode:**
> ```bash
> TRAIN=y VOICE=n bash setup.sh
> ```

After setup, install at least two Ollama models — one for general modules, one for coding:

```bash
ollama pull mistral       # used by knowledge, web_search, system_ctrl
ollama pull codestral     # used by coding module
```

---

## 5. Starting the brain

```bash
# Activate your virtual environment first
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows

# Start the brain
python main.py
```

On startup you will see:

```
==================================================
  OCBrain  v2.1.0
==================================================
[INFO] Running schema migrations...   ← safe, never destructive
[INFO] Ollama OK
[INFO] Loaded 4 module(s): ['coding', 'web_search', 'knowledge', 'system_ctrl']
[INFO] Pre-warming Ollama models...   ← loads models into VRAM
[INFO]   ✓ mistral warm
[INFO]   ✓ codestral warm
[INFO] Orchestrator ready
[INFO] Web UI  → http://localhost:7437
[INFO] API     → http://localhost:7437/docs
[INFO] Stream  → POST http://localhost:7437/query  {stream: true}
[INFO] Events  → GET  http://localhost:7437/events
[INFO] OCBrain v2.1 is ready.
```

The brain is now listening. Leave this terminal open — the brain must be running for OpenClaw to work.

**Run as a background service (Linux):**
```bash
# Enable autostart via systemd user service
systemctl --user enable ocbrain
systemctl --user start ocbrain

# View logs
journalctl --user -u ocbrain -f
```

**macOS autostart:**
```bash
launchctl load ~/Library/LaunchAgents/io.ocbrain.plist
```

---

## 6. Connecting OpenClaw to the brain

OpenClaw communicates with the brain over HTTP on `localhost:7437`. This section covers every integration point.

### 6.1 Point OpenClaw at the brain

In your OpenClaw configuration file, set the brain URL:

```yaml
# openclaw_config.yaml (or equivalent in your OpenClaw setup)
brain:
  url: "http://localhost:7437"
  timeout_seconds: 30
  stream: true          # enable token streaming for live output
```

If OpenClaw and the brain run on **different machines** on the same network, replace `localhost` with the brain machine's IP:

```yaml
brain:
  url: "http://192.168.1.42:7437"
```

> To expose the brain on your local network, edit `main.py` and change the uvicorn host from `127.0.0.1` to `0.0.0.0`. Do not expose it to the internet without adding authentication.

---

### 6.2 Sending queries to the brain

**Standard query (full response):**
```http
POST http://localhost:7437/query
Content-Type: application/json

{
  "query": "write a Python function to sort a list"
}
```

Response:
```json
{
  "answer": "def sort_list(lst):\n    return sorted(lst)",
  "modules_used": ["coding"]
}
```

**Streaming query (tokens as they generate):**
```http
POST http://localhost:7437/query
Content-Type: application/json

{
  "query": "explain how neural networks work",
  "stream": true
}
```

Response: `text/event-stream` — each event is:
```
data: {"token": "Neural"}
data: {"token": " networks"}
data: {"token": " are"}
...
data: [DONE]
```

**Force a specific module:**
```json
{
  "query": "open spotify",
  "module": "system_ctrl"
}
```

---

### 6.3 Subscribing to brain events

OpenClaw can subscribe to the brain's event stream to react to state changes without polling:

```http
GET http://localhost:7437/events
Accept: text/event-stream
```

Events emitted:

| Event | When it fires | Payload |
|---|---|---|
| `brain.ready` | Brain fully started | `{modules, version}` |
| `module.promoted` | Module reached next stage | `{module, stage}` |
| `module.weights_updated` | New LoRA weights hot-swapped | `{module}` |
| `module.weights_failed` | Training failed eval | `{module}` |
| `module.created` | New custom module added | `{module}` |
| `learning.crawl_done` | Crawler finished a run | `{modules}` |
| `learning.train_started` | Fine-tuning run began | `{module}` |
| `learning.train_done` | Fine-tuning run completed | `{module, passed}` |
| `learning.distill_done` | Distillation batch done | `{module, topic, pairs}` |
| `learning.gap_detected` | Knowledge gaps found | `{module, gaps}` |
| `kb.ingested` | New chunks written to KB | `{module}` |
| `query.received` | Query arrived | `{query}` |
| `query.answered` | Answer returned | `{latency_ms}` |

**Example — Python client:**
```python
import httpx

with httpx.stream("GET", "http://localhost:7437/events") as r:
    for line in r.iter_lines():
        if line.startswith("data:"):
            print(line[5:])   # handle event JSON
```

---

### 6.4 Checking brain and module health

```http
GET http://localhost:7437/status
```

Response:
```json
{
  "status": "ok",
  "brain_version": "2.1.0",
  "app_version": "2.1.0",
  "modules": {
    "coding": {
      "stage": "shadow",
      "maturity_score": 0.71,
      "query_count": 1842,
      "kb_chunks": 4200,
      "db_ok": true
    },
    "knowledge": { "stage": "bootstrap", ... },
    "web_search": { "stage": "bootstrap", ... },
    "system_ctrl": { "stage": "bootstrap", ... }
  }
}
```

Use this endpoint as a health check. OpenClaw should wait for `status: "ok"` before sending queries.

---

### 6.5 Brain API v2 (versioned endpoints)

All v2 endpoints are prefixed `/brain/v2/` and are stable across minor versions:

```http
GET  /brain/v2/status        # full status + per-module brain state
POST /brain/v2/query         # query with optional stream:true
GET  /brain/v2/version       # brain version, app version, schema version
```

---

### 6.6 Full connection example (Python)

```python
import httpx
import json

BRAIN = "http://localhost:7437"

class OCBrainClient:
    def __init__(self, url: str = BRAIN):
        self.url = url

    def is_ready(self) -> bool:
        try:
            r = httpx.get(f"{self.url}/status", timeout=5)
            return r.json().get("status") == "ok"
        except Exception:
            return False

    def query(self, text: str, module: str = None) -> str:
        payload = {"query": text}
        if module:
            payload["module"] = module
        r = httpx.post(f"{self.url}/query", json=payload, timeout=30)
        return r.json()["answer"]

    def stream(self, text: str):
        """Yields tokens as they arrive from the brain."""
        with httpx.stream(
            "POST", f"{self.url}/query",
            json={"query": text, "stream": True},
            timeout=60,
        ) as r:
            for line in r.iter_lines():
                if line.startswith("data:") and "[DONE]" not in line:
                    data = json.loads(line[5:])
                    yield data.get("token", "")

    def status(self) -> dict:
        return httpx.get(f"{self.url}/status").json()


# Usage
brain = OCBrainClient()

if not brain.is_ready():
    raise RuntimeError("Brain not running. Start it with: python main.py")

# Standard query
answer = brain.query("write a function to reverse a string")

# Streaming query
for token in brain.stream("explain diffusion models"):
    print(token, end="", flush=True)

# Force a module
result = brain.query("open spotify", module="system_ctrl")
```

---

## 7. Verifying the connection

Once the brain is running and OpenClaw is configured, verify everything works:

```bash
# 1. Check brain is alive
curl http://localhost:7437/status

# 2. Send a test query
curl -X POST http://localhost:7437/query \
  -H "Content-Type: application/json" \
  -d '{"query": "hello, are you online?"}'

# 3. Check all modules loaded
curl http://localhost:7437/modules

# 4. Check brain version
curl http://localhost:7437/brain/v2/version

# 5. Open Web UI to see module maturity
open http://localhost:7437
```

Expected output for step 2:
```json
{"answer": "Yes, I'm online. How can I help you?", "modules_used": ["knowledge"]}
```

---

## 8. Brain API reference

Full auto-generated docs are available at `http://localhost:7437/docs` when the brain is running.

| Endpoint | Method | Description |
|---|---|---|
| `/query` | POST | Send a query. Add `"stream": true` for SSE token streaming. |
| `/status` | GET | Brain + module health check. |
| `/modules` | GET | List all loaded modules and their status. |
| `/modules/new` | POST | Create a new custom expert module. |
| `/train/{name}` | POST | Manually trigger a training run for a module. |
| `/distill` | POST | Generate synthetic training data via knowledge distillation. |
| `/export` | POST | Export a module as a portable `.ocbrain` bundle. |
| `/import` | POST | Import a `.ocbrain` bundle. |
| `/events` | GET | SSE stream of all brain events. |
| `/config` | GET/PUT | Read or update brain configuration. |
| `/updates` | GET | Check for available app updates. |
| `/brain/v2/status` | GET | Versioned status endpoint. |
| `/brain/v2/query` | POST | Versioned query endpoint. |
| `/brain/v2/version` | GET | Brain version info. |
| `/docs` | GET | Auto-generated OpenAPI documentation. |

---

## 9. Module maturity model

Each module evolves through three stages automatically, based on usage:

```
Bootstrap ──(1,000 queries)──► Shadow ──(score ≥ 0.85, 500q)──► Native
    │                              │                                │
    │  Ollama answers all          │  Both models run in           │  Own model only
    │  queries. Brain saves        │  parallel. Own model          │  Ollama not
    │  every pair for training.    │  scored against Ollama.       │  involved.
    └──────────────────────────────┴───────────────────────────────┘
         Collecting training data       Evaluating own model         Fully autonomous
```

You can check every module's current stage:
```bash
curl http://localhost:7437/modules
# or
ocbrain status
```

To manually force a training run for a module:
```bash
curl -X POST http://localhost:7437/train/coding
# or
ocbrain train coding
```

---

## 10. Adding custom modules

### Via Web UI
Open `http://localhost:7437` → **Modules** → **+ Add custom module**. Fill in name, description, bootstrap model, trigger keywords, and source URLs.

### Via CLI
```bash
ocbrain new-module
```

### Via API
```bash
curl -X POST http://localhost:7437/modules/new \
  -H "Content-Type: application/json" \
  -d '{
    "name": "finance",
    "desc": "Financial analysis and market knowledge",
    "model": "mistral",
    "keywords": ["stock", "market", "invest", "portfolio", "price"],
    "sources": ["https://finance.yahoo.com", "https://arxiv.org/rss/q-fin"]
  }'
```

Custom modules follow the same bootstrap → shadow → native maturity path as built-in modules.

**Export and share a trained module:**
```bash
curl -X POST http://localhost:7437/export \
  -H "Content-Type: application/json" \
  -d '{"module_name": "finance"}'
# Returns path to .ocbrain bundle
```

**Import on another machine:**
```bash
curl -X POST http://localhost:7437/import \
  -H "Content-Type: application/json" \
  -d '{"bundle_path": "/path/to/finance_20250610.ocbrain"}'
```

---

## 11. Knowledge distillation

Instead of waiting for organic query pairs to accumulate, you can seed a module with synthetic training data immediately:

```bash
curl -X POST http://localhost:7437/distill \
  -H "Content-Type: application/json" \
  -d '{
    "module_name": "knowledge",
    "topic": "transformer architecture and attention mechanisms",
    "num_pairs": 100
  }'
```

The brain uses the bootstrap model as a teacher, generates high-quality Q&A pairs on that topic, scores them, saves them to the training queue, and the next scheduled training run picks them up.

Use this to rapidly bootstrap a new module on a specific domain before it has seen any real user queries.

---

## 12. Updating

```bash
# Check for updates
ocbrain update

# Via package manager
sudo apt upgrade ocbrain        # Debian / Ubuntu
sudo dnf upgrade ocbrain        # Fedora
yay -Syu ocbrain                # Arch Linux
brew upgrade --cask ocbrain     # macOS
winget upgrade OCBrain.OCBrain # Windows

# Roll back to previous version if needed
ocbrain rollback
```

Updates only touch the application code. Your trained module weights, knowledge base, conversation history, and configuration are never modified during an update.

---

## 13. Project structure

```
OCBrain/
├── core/           Orchestrator, classifier, router, brain API, migrator
├── modules/        Expert modules: coding, web_search, knowledge, system_ctrl
│   └── _template/  Template for new custom modules
├── learning/       Crawler, cleaner, trainer, finetuner, distiller, gap detector
├── interface/      FastAPI server, Web UI, CLI, system tray, voice, updater
├── config/         settings.toml, sources.toml, models.toml, settings.yaml
├── data/           Context DB, raw training pairs, KB chunks, evals, exports
├── tests/          Full test suite
├── install/        Cross-platform build scripts (deb, rpm, exe, pkg)
├── .github/        CI and release workflows
├── main.py         Entry point
├── setup.sh        First-time setup script
└── install.sh      One-liner remote installer
```

---

## 14. Contributing

```bash
git clone https://github.com/1h0lde4/OCBrain.git
cd OCBrain
pip install -e ".[dev]"
pytest tests/
```

---

## License

MIT — see [LICENSE](LICENSE)
