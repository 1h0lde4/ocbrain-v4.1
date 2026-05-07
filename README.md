# OCBrain

<div align="center">

**The self-learning AI runtime for production systems**

[![Version](https://img.shields.io/badge/version-2.1.1-1d9e75?style=flat-square)](https://github.com/1h0lde4/OCBrain/releases)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)
[![API](https://img.shields.io/badge/API-v2-orange?style=flat-square)](#api-reference)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Quick Start](#quick-start)
7. [Usage](#usage)
8. [Configuration](#configuration)
9. [Project Structure](#project-structure)
10. [Module Maturity Model](#module-maturity-model)
11. [API Reference](#api-reference)
12. [Technical Stack](#technical-stack)
13. [Advanced Topics](#advanced-topics)
14. [Roadmap](#roadmap)
15. [Contributing](#contributing)

---

## Overview

OCBrain is a **local-first AI orchestration runtime** that manages expert LLM modules with automatic learning, adaptive routing, and production-grade resilience. It bridges the gap between libraries like LangChain (which help you *build* agents) and production requirements (which demand you *run and maintain* them reliably).

### Core Value Proposition

- **Local-first execution** — queries never leave your infrastructure
- **Self-improving modules** — each expert model learns from every interaction
- **Adaptive routing** — automatic failover, circuit breakers, and concurrency control
- **Zero external dependencies** — migrations from OpenAI to Ollama to local models in seconds
- **Built-in resilience** — backpressure guards, adaptive limits, streaming responses

### Who It's For

- **SaaS teams** building AI features who need cost control and latency optimization
- **Enterprise AI** in regulated industries (Finance, Healthcare, Legal) requiring data residency
- **DevOps/SRE** responsible for LLM uptime and monitoring
- **Researchers** experimenting with multi-model routing and automated knowledge distillation

---

## Key Features

### Orchestration & Routing

- **Smart module classification** — semantic intent detection routes queries to appropriate expert modules
- **Parallel execution** — multi-module queries execute concurrently with automatic merging
- **Task decomposition** — complex queries split into sequential or parallel subtasks
- **Fallback chains** — automatic provider failover if primary model unavailable

### Adaptive Learning

- **Module maturity tracking** — three-stage evolution (bootstrap → shadow → native)
  - **Bootstrap**: External LLM queries only, collecting training pairs
  - **Shadow**: Internal model runs in parallel, compared against external for convergence
  - **Native**: Local model takes over, external queries only for spot-checking
- **Automatic training** — LoRA fine-tuning on collected data scheduled hourly/daily
- **Knowledge distillation** — synthetic data generation via teacher models for weak areas
- **Gap detection** — identifies knowledge weaknesses and queues targeted learning

### Knowledge Management

- **Hybrid retrieval** — semantic search + keyword-based lookup for multi-source queries
- **Cognitive memory tiers** — L1 (short-term), L2 (session), L3 (long-term) consolidation
- **Web crawling** — hourly automatic data collection from configured sources
- **Deduplication** — MinHash-based chunk dedup to prevent knowledge bloat

### Production Resilience

- **Circuit breakers** — automatic dependency isolation when services degrade
- **Adaptive concurrency** — request limits scale with latency to prevent degradation
- **Backpressure guards** — system-level request throttling to prevent OOM
- **Iteration budgets** — prevent infinite loops in multi-step queries
- **Token streaming** — responses stream in real-time (~300ms to first token vs 3–8s before)

### Privacy & Control

- **Privacy guard** — enforces per-module opt-in for training, history save, crawling
- **Wipe operations** — single-module or full data deletion
- **No telemetry** — zero analytics or external calls by default
- **Local-only inference** — all inference runs via local Ollama instance

### Expert Modules (Built-in)

1. **coding** — code generation, debugging, system design (Python, JavaScript, SQL)
2. **web_search** — real-time information, news, trending topics
3. **knowledge** — general Q&A, definitions, explanations
4. **system_ctrl** — OS operations, file management, application launcher

---

## Architecture

```
OpenClaw (or caller)
      │
      │  HTTP/REST  (localhost:7437)
      ▼
┌─────────────────────────────────────────────────┐
│           OCBrain Orchestrator (V3)             │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  Intent  │→ │  Module  │→ │   Execute    │ │
│  │Classifier│  │ Router   │  │  (parallel)  │ │
│  └──────────┘  └──────────┘  └──────────────┘ │
│       ↓              ↓              ↓          │
│  ┌──────────────────────────────────────────┐ │
│  │        Expert Modules                    │ │
│  │  ┌────────┬─────────┬──────┬──────────┐ │ │
│  │  │ Coding │ Search  │ KnowL│ SysCtrl  │ │ │
│  │  └────────┴─────────┴──────┴──────────┘ │ │
│  └──────────────────────────────────────────┘ │
│       ↓              ↓              ↓          │
│  ┌──────────────────────────────────────────┐ │
│  │      Memory & Knowledge Management       │ │
│  │  ┌──────────┬──────────┬──────────────┐ │ │
│  │  │ Context  │  Hybrid  │   Cognitive  │ │ │
│  │  │  Memory  │ Retrieval│   Vault      │ │ │
│  │  └──────────┴──────────┴──────────────┘ │ │
│  └──────────────────────────────────────────┘ │
│       ↓              ↓              ↓          │
│  ┌──────────────────────────────────────────┐ │
│  │    Adaptive Control Plane                │ │
│  │  ┌──────────┬────────┬───────────────────┤ │
│  │  │ Circuit  │Adaptive│ Iteration Budget  │ │
│  │  │ Breaker  │Conc.   │ & Backpressure    │ │
│  │  └──────────┴────────┴───────────────────┘ │
│  └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
      ↓
  Local Ollama
  (or external provider)
```

### Data Flow

1. **Query Reception** → Context captured, privacy checks applied
2. **Intent Classification** → Semantic classifier routes to appropriate modules
3. **Context Assembly** → Cognitive memory pulls L1/L2/L3 context
4. **Module Dispatch** → Selected modules execute in parallel
5. **Result Merging** → Answers synthesized & confidence-scored
6. **Memory Consolidation** → Context saved, training pairs recorded
7. **Shadow Learning** → Background module promotion evaluation
8. **Response** → Full answer streamed back to caller

### Core Components

| Component | Purpose |
|-----------|---------|
| **Orchestrator** | Main query handler; coordinates parsing, classification, dispatch, merge |
| **Classifier** | Semantic intent detection (fast-path for >75% confidence queries) |
| **Decomposer** | Converts multi-module queries into task DAGs with dependencies |
| **Merger** | Synthesizes parallel module results into unified answers |
| **ModelRouter** | Manages module maturity stages and external/internal model switching |
| **MemoryVault** | Persistent knowledge store (ChromaDB) with LRU cache layer |
| **HybridRetriever** | Combined semantic + keyword-based search across knowledge |
| **CognitiveVault** | Multi-tier memory (L1/L2/L3) with consolidation scheduling |
| **ProviderMesh** | Provider selection & fallback logic (OpenAI, Anthropic, local Ollama) |
| **Trainer** | LoRA-based fine-tuning pipeline with automatic scheduling |

---

## Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **Python** | 3.11 | 3.12 |
| **RAM** | 8 GB | 16 GB |
| **VRAM** (training) | 6 GB | 12 GB |
| **Disk** | 10 GB | 50 GB |
| **Ollama** | Required | Latest |
| **OS** | Linux, macOS, Windows 10/11 | Linux |

### Installed Dependencies

- **Web Server & API**: FastAPI, Uvicorn, HTTPX
- **LLM Integration**: Ollama (external)
- **NLP & ML**: spaCy, sentence-transformers, torch, transformers, peft (for training)
- **Knowledge Store**: ChromaDB, SQLAlchemy
- **Data Processing**: BeautifulSoup4, trafilatura, feedparser, datasketch
- **Voice**: Whisper, pyttsx3, sounddevice (optional)
- **CLI & Web**: Click, Rich, Pydantic

---

## Installation

### Option 1: One-liner (Linux/macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/1h0lde4/OCBrain/main/install.sh | bash
```

### Option 2: pip from GitHub

```bash
pip install git+https://github.com/1h0lde4/OCBrain.git@main
```

Install optional extras:
```bash
pip install "ocbrain[training,voice]"
```

### Option 3: Clone and Setup (Development)

```bash
git clone https://github.com/1h0lde4/OCBrain.git
cd OCBrain
bash setup.sh                  # Interactive setup
# OR
TRAIN=y VOICE=n bash setup.sh  # Non-interactive
```

### Option 4: System Package Manager

**macOS (Homebrew):**
```bash
brew install 1h0lde4/ocbrain/ocbrain
```

**Linux (apt):**
```bash
echo "deb [trusted=yes] https://pages.github.com/1h0lde4/ocbrain/apt /" | sudo tee /etc/apt/sources.list.d/ocbrain.list
sudo apt update && sudo apt install ocbrain
```

**AUR (Arch Linux):**
```bash
yay -S ocbrain
```

### Verification

```bash
ocbrain --version       # Should print 2.1.1
which ocbrain           # Verify in PATH
pip show ocbrain        # Package details
```

---

## Quick Start

### Step 1: Ensure Ollama is Running

```bash
# Download and install: https://ollama.com
ollama serve                           # Start server (auto on port 11434)
# In another terminal:
ollama pull mistral                    # Download default model
ollama pull nomic-embed-text           # Download embeddings model
```

### Step 2: Start OCBrain

```bash
ocbrain-start          # Starts uvicorn on http://localhost:7437
# OR
python main.py         # From repo root
```

You should see Ollama model pre-warming:
```
Pre-warming 4 model(s): {'mistral', 'nomic-embed-text'}
  ✓ mistral warm
  ✓ nomic-embed-text warm
```

### Step 3: Test Your First Query

#### Via CLI

```bash
ocbrain "What's the latest news about AI?"
# Answers with web_search module, streams response
```

#### Via HTTP API

```bash
curl -X POST http://localhost:7437/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Write a Python function to reverse a string", "stream": false}'

# Response:
{
  "answer": "def reverse_string(s):\n    return s[::-1]\n\n# Usage:\nprint(reverse_string('hello'))  # Output: 'olleh'",
  "modules_used": ["coding"],
  "latency_ms": 1250,
  "brain_version": "2.1.1"
}
```

#### Via Web UI

Navigate to **http://localhost:7437** — interactive dashboard with module status, chat interface.

---

## Usage

### Command-Line Interface (CLI)

```bash
# Query
ocbrain "your question here"
ocbrain -m coding "help me debug this Python error"

# Pipe input
echo "What is machine learning?" | ocbrain

# Status
ocbrain --status
# Shows module maturity, KB size, training stats

# Module management
ocbrain --new-module                   # Interactive wizard
ocbrain --distill coding machine_learning --num-pairs 100
ocbrain --export coding > coding.ocbrain
ocbrain --import coding.ocbrain --overwrite

# Training & maintenance
ocbrain --train coding                 # Force training run
ocbrain --rollback coding              # Revert to previous weights
ocbrain --wipe-module coding           # Delete all data for coding
ocbrain --wipe-all                     # Nuclear option: delete everything

# System
ocbrain --update                       # Check for new version
ocbrain --help
```

### REST API

Base URL: `http://localhost:7437`

#### Query Endpoint

```bash
POST /query
```

Request:
```json
{
  "query": "string (required)",
  "module": "string (optional, force specific module)",
  "stream": "boolean (default: false)",
  "context_turns": "integer (default: 5)"
}
```

Response:
```json
{
  "success": true,
  "answer": "string",
  "modules_used": ["module1", "module2"],
  "latency_ms": 1250,
  "brain_version": "2.1.1"
}
```

#### Streaming Response

```bash
curl -X POST http://localhost:7437/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Write a haiku", "stream": true}'

# Streams tokens as newline-delimited JSON:
# {"token": "A "}
# {"token": "gentle "}
# {"token": "breeze "}
# ...
```

#### Brain Status

```bash
GET /brain/v2/status
```

Response:
```json
{
  "status": "ok",
  "brain_version": "2.1.1",
  "app_version": "2.1.1",
  "schema_version": 1,
  "total_queries": 4217,
  "modules": {
    "coding": {
      "name": "coding",
      "stage": "shadow",
      "maturity_score": 0.78,
      "query_count": 1249,
      "kb_chunks": 3450,
      "db_ok": true,
      "lora_version": 3
    },
    ...
  }
}
```

#### Knowledge Distillation

```bash
POST /distill

{
  "module_name": "coding",
  "topic": "async programming in Python",
  "num_pairs": 100,
  "teacher_model": "gpt-4"
}
```

Queues synthetic training data generation on a background scheduler.

#### Export/Import Modules

```bash
# Export one module
POST /export
{
  "module_name": "coding"
}
# Returns .ocbrain bundle (zip with model weights + KB)

# Import
POST /import
{
  "bundle_path": "/path/to/coding.ocbrain",
  "overwrite": false
}
```

#### Events (Server-Sent Events)

```bash
curl -N http://localhost:7437/events

# Streams events:
# data: {"_event": "module.promoted", "module": "coding", "new_stage": "native"}
# data: {"_event": "learning.train_done", "module": "web_search", "new_version": 5}
```

---

## Configuration

### Config Files Location

Config files are stored in `./config/` and hot-reload every 2 seconds:

| File | Purpose |
|------|---------|
| `settings.toml` | Global behavior (language, port, learning rates, privacy) |
| `models.toml` | Module maturity state, training history, weights versions |
| `sources.toml` | Per-module web crawl sources |
| `settings.yaml` | Alternative YAML format for settings |
| `user_prefs.yaml` | User-specific preferences |

### Global Settings (`settings.toml`)

```toml
[global]
language             = "auto"           # Language for responses
response_style       = "concise"        # or "detailed"
confidence_floor     = 0.6              # Min confidence to return answer
fanout_on_ambiguity  = true             # Multi-module on unclear queries
context_window       = 10               # Short-term memory turns
ollama_host          = "http://localhost:11434"
classifier_model     = "mistral"        # Model for intent classification
web_ui_port          = 7437             # API/UI port
voice_enabled        = false            # Enable voice input/output
log_level            = "INFO"           # Logging verbosity

[privacy]
save_history         = true             # Save chat history
save_training_pairs  = true             # Collect training data
telemetry            = false            # Send analytics
encrypt_context_db   = false            # Encrypt stored context

[learning]
crawl_interval_h     = 1                # How often to crawl sources
clean_interval_h     = 6                # How often to deduplicate
train_interval_h     = 24               # How often to run LoRA training
min_pairs_to_train   = 500              # Minimum pairs before training
replay_ratio         = 0.2              # % of past pairs to include
training_enabled     = true             # Master kill switch
```

### Module Configuration (`settings.toml`)

```toml
[modules.coding]
enabled              = true
keywords             = ["write", "code", "script", "function", ...]
staleness_decay      = true             # Older KB chunks score lower
max_kb_size_mb       = 500              # Max knowledge size
confidence_boost     = 0.1              # Classification confidence reward
pin_to_external      = false            # Force external provider
```

### Module State (`models.toml`)

Auto-managed, track maturity:
```toml
[coding]
stage                = "shadow"         # bootstrap | shadow | native
maturity_score       = 0.78             # 0.0–1.0
query_count          = 1249             # Total queries handled
bootstrap_model      = "mistral"        # External model name
base_model           = "mistral:7b"     # Base model for fine-tuning
active_weights       = "v3.safetensors" # Current LoRA weights file
last_trained         = "2025-05-07"     # Last training date
train_pairs          = 12450            # Total collected pairs
```

### Knowledge Sources (`sources.toml`)

```toml
[coding]
sources = [
  "https://docs.python.org/3/",
  "https://github.com/trending",
  "https://stackoverflow.com/questions?tab=votes",
]

[web_search]
sources = [
  "https://news.ycombinator.com/rss",
  "https://lobste.rs/rss",
]
```

These are crawled hourly to build KB.

---

## Project Structure

```
ocbrain/
├── config/                           # Configuration files (hot-reload)
│   ├── settings.toml               # Global settings
│   ├── settings.yaml               # Alternative YAML format
│   ├── user_prefs.yaml            # User preferences
│   ├── models.toml                # Module maturity state
│   └── sources.toml               # Web crawl sources per module
│
├── core/                            # Core orchestration engine
│   ├── orchestrator.py            # Main query handler (V3)
│   ├── brain_api.py               # Versioned API contract (v2)
│   ├── brain_version.py           # Version state management
│   ├── brain_export.py            # Module export/import
│   ├── parser.py                  # Query entity extraction
│   ├── classifier_v3.py           # Semantic intent detection
│   ├── classifier.py              # Legacy classifier
│   ├── decomposer.py              # Task DAG generation
│   ├── merger.py                  # Multi-module result synthesis
│   ├── dispatcher.py              # Module execution
│   ├── config.py                  # Config file loader + watcher
│   ├── context.py                 # Short-term context memory
│   ├── privacy.py                 # Privacy guard enforcement
│   ├── migrator.py                # DB schema migrations
│   ├── event_bus.py               # Pub/sub for brain events
│   ├── provider_mesh.py           # LLM provider selection & fallback
│   ├── model_router.py            # Module stage management & routing
│   ├── module_registry.py         # Module discovery
│   ├── module_factory.py          # Module creation wizard
│   │
│   ├── dashboard/                 # Status monitoring
│   │   └── state_dashboard.py    # Real-time brain state dashboard
│   │
│   ├── governance/                # Adaptive control plane
│   │   └── memory_governor.py    # Memory usage enforcement
│   │
│   ├── learning/                  # Knowledge management
│   │   ├── evaluator.py          # Training pair quality scoring
│   │   ├── gate.py               # Promotion/regression logic
│   │   ├── scorer.py             # Semantic similarity scoring
│   │   └── similarity.py         # Vector embedding utilities
│   │
│   ├── memory/                    # Knowledge management
│   │   ├── mem_vault.py          # Core memory store (ChromaDB)
│   │   ├── cognitive_vault.py    # Multi-tier memory (L1/L2/L3)
│   │   ├── hybrid_retrieval.py   # Semantic + keyword search
│   │   ├── assembly.py           # Context assembly from tiers
│   │   ├── dedup.py              # MinHash deduplication
│   │   ├── consolidation/        # Memory consolidation schedulers
│   │   ├── graph/                # Knowledge graph (phase 5)
│   │   └── retrieval/            # Retrieval augmentation
│   │
│   ├── meta/                      # Monitoring & observability
│   │   ├── health_monitor.py     # Module health tracking
│   │   └── observability/        # Metrics, tracing, logging
│   │
│   ├── observability/             # Tracing & metrics
│   │   ├── tracer.py             # Async span tracing
│   │   └── metrics.py            # Prometheus-style metrics
│   │
│   ├── prompt/                    # Prompt templates & generation
│   │
│   ├── runtime/                   # Execution control
│   │   ├── limits.py             # Iteration budgets, backpressure
│   │   ├── resilience.py         # Circuit breakers, adaptive concurrency
│   │   └── state.py              # Runtime state store
│   │
│   ├── shadow/                    # Shadow learning (phase 3)
│   │   └── shadow_learner.py    # Record & evaluate internal models
│   │
│   └── web/                       # Web components (tabled for now)
│
├── modules/                         # Expert module implementations
│   ├── base.py                   # Base module class w/ ChromaDB wrapper
│   ├── embedding_fn.py           # Embedding utilities
│   │
│   ├── coding/                   # Code generation & debugging
│   │   ├── module.py
│   │   ├── weights/
│   │   └── kb/
│   │
│   ├── web_search/               # Real-time information
│   │   ├── module.py
│   │   └── weights/
│   │
│   ├── knowledge/                # General Q&A & reasoning
│   │   ├── module.py
│   │   └── weights/
│   │
│   ├── system_ctrl/              # OS operations
│   │   ├── module.py
│   │   └── weights/
│   │
│   └── _template/                # Template for custom modules
│       ├── module.py
│       └── README.md
│
├── learning/                       # Training & knowledge management
│   ├── chunker.py                # Document chunking strategies
│   ├── cleaner.py                # Data cleaning pipeline
│   ├── crawler.py                # Web crawler (hourly scheduling)
│   ├── distiller.py              # Knowledge distillation (synthetic pairs)
│   ├── embedder.py               # Vector embeddings wrapper
│   ├── evaluator.py              # Training quality evaluation
│   ├── finetuner.py              # LoRA training orchestrator
│   ├── gap_detector.py           # Identify weak areas (6h loop)
│   ├── scheduler.py              # Crawl/train/distill scheduling
│   └── trainer.py                # Core LoRA trainer
│
├── interface/                       # User interfaces
│   ├── api.py                    # FastAPI app + v2 brain routes
│   ├── cli.py                    # Command-line interface
│   ├── tray.py                   # System tray icon (macOS/Windows)
│   ├── updater.py                # Auto-update checker
│   ├── voice.py                  # Voice I/O (Whisper + TTS)
│   │
│   └── web/                      # Web UI (React/Vue)
│       ├── index.html
│       ├── app.js
│       └── styles.css
│
├── install/                         # Installation & packaging
│   ├── build.py                  # Build script for installers
│   └── __init__.py
│
├── tests/                          # Comprehensive test suite
│   ├── test_*.py                # Unit tests by component
│   ├── test_phase*.py           # Integration tests (phase 1–4)
│   ├── break_*.py               # Chaos tests + edge cases
│   └── conftest.py              # pytest fixtures & config
│
├── data/                           # Runtime data
│   ├── context.sqlite            # Short-term memory DB
│   ├── evals/                    # Evaluation datasets
│   ├── raw/                      # Raw crawled documents
│   └── chunks/                   # Processed KB chunks
│
├── evals/                          # Evaluation harness
│   ├── dataset.json             # Test cases
│   └── run_eval.py              # Benchmark runner
│
├── examples/                        # Usage examples
│   └── demo_phase2.py           # End-to-end demo
│
├── main.py                         # Entry point + initialization
├── pyproject.toml                 # Package metadata & dependencies
├── requirements.txt               # pip dependencies
├── setup.sh                       # Setup automation
├── install.sh                     # One-liner installer
├── version.txt                    # Single source of version
│
├── CHANGELOG.md                   # Release history
├── PRODUCT.md                     # Product strategy document
├── LICENSE                        # MIT
└── README.md                      # This file
```

---

## Module Maturity Model

Modules evolve through three stages as they collect data:

### Stage 1: Bootstrap

- **Definition**: Learning phase, uses external provider (Ollama)
- **Behavior**: All queries routed to external model, training pairs collected
- **Training**: Passive observation mode
- **Duration**: ~500 queries
- **Next**: Auto-promote to Shadow when ready

```
Query → External Provider (Ollama) → Collect Pair
```

### Stage 2: Shadow

- **Definition**: Internal model runs in parallel with external
- **Behavior**: Both models queried, external answer used, similarity scored
- **Training**: Active fine-tuning on collected pairs
- **Metric**: Similarity score between internal & external (target > 0.85)
- **Duration**: Varies by convergence (100s–1000s of queries)
- **Next**: Auto-promote to Native when >0.85 similarity for 100+ consecutive queries

```
Query → [External Provider] + [Internal Model] → External used, Similarity scored
```

### Stage 3: Native

- **Definition**: Production mode, internal model used full-time
- **Behavior**: Internal model handles queries, external only for spot-checking
- **Training**: Continuous refinement on new data
- **Metric**: Regression detection (similarity < 0.70 triggers rollback)
- **Rollback**: Automatic if quality drops

```
Query → Internal Model → Spot-check with External (1 in 50)
```

### Monitoring Maturity

```bash
ocbrain --status

Module Status
═════════════════════════════════════════════════════════

coding
  Stage: shadow
  Maturity Score: 0.784
  Queries Handled: 1249
  Knowledge Chunks: 3450
  Training Pairs: 12450
  Last Trained: 2025-05-07 14:32
  LoRA Version: 3
  Recommendation: Monitor similarity; should promote in ~200 queries

web_search
  Stage: bootstrap
  Maturity Score: 0.0
  Queries Handled: 826
  Knowledge Chunks: 892
  Training Pairs: 826
  Last Trained: Never
  LoRA Version: 0
  Recommendation: Collecting pairs; train when >500 available
```

---

## API Reference

### Brain API v2 (Stable)

Base: `/brain/v2`

#### Query Endpoint

```
POST /brain/v2/query
Content-Type: application/json

{
  "query": "Write a Python decorator",
  "module": null,                  # null = auto-route
  "stream": false,
  "context_turns": 5
}

200 OK
{
  "answer": "...",
  "modules_used": ["coding"],
  "latency_ms": 1234,
  "brain_version": "2.1.1"
}
```

#### Status Endpoint

```
GET /brain/v2/status

200 OK
{
  "status": "ok",
  "brain_version": "2.1.1",
  "app_version": "2.1.1",
  "schema_version": 1,
  "total_queries": 4217,
  "modules": {
    "coding": { ... },
    "web_search": { ... },
    ...
  }
}
```

#### Distillation Endpoint

```
POST /brain/v2/distill

{
  "module_name": "coding",
  "topic": "async patterns",
  "num_pairs": 100,
  "teacher_model": "gpt-4"
}

202 Accepted
{
  "task_id": "distill_coding_async_12345",
  "status": "queued",
  "eta_seconds": 180
}
```

#### Module Export/Import

```
GET /brain/v2/export/coding
200 OK (binary zip)

POST /brain/v2/import
{
  "bundle_path": "/path/to/coding.ocbrain",
  "overwrite": false
}
202 Accepted
```

#### Events (Streaming)

```
GET /brain/v2/events

200 OK (text/event-stream)
data: {"_event": "module.promoted", "module": "coding", "new_stage": "native", "maturity_score": 0.89}
data: {"_event": "learning.train_done", "module": "web_search", "new_version": 5, "pairs_used": 1250}
...
```

---

## Technical Stack

### Core Framework

| Layer | Technology |
|-------|-----------|
| **Runtime** | Python 3.11+ |
| **Web Server** | FastAPI + Uvicorn |
| **HTTP Client** | httpx (async) |
| **Configuration** | TOML (tomli/tomli-w), YAML (PyYAML) |
| **CLI** | Click + Rich |

### AI & NLP

| Component | Library |
|-----------|---------|
| **LLM Inference** | Ollama (local) |
| **Intent Classification** | Sentence-transformers (semantic) |
| **Embeddings** | Sentence-transformers (nomic-embed-text) |
| **Entity Extraction** | spaCy (NER) |
| **Text Processing** | BeautifulSoup4, trafilatura |
| **Fine-tuning** | PyTorch, transformers, peft (LoRA), bitsandbytes, unsloth |

### Knowledge & Memory

| Component | Technology |
|-----------|-----------|
| **Vector DB** | ChromaDB (with LRU cache) |
| **Graph DB** | (Phase 5, not yet implemented) |
| **SQL DB** | SQLAlchemy + SQLite (WAL mode) |
| **Deduplication** | datasketch (MinHash) |
| **Caching** | In-memory LRU + TTL |

### Voice & I/O

| Input | Library |
|-------|---------|
| **STT** | OpenAI Whisper |
| **TTS** | pyttsx3 |
| **Audio** | sounddevice, soundfile |

### Testing & Quality

| Tool | Purpose |
|------|---------|
| **Unit Tests** | pytest + pytest-asyncio |
| **Mocking** | pytest-mock |
| **Chaos** | Custom break_*.py suites |
| **Packaging** | PyInstaller (binary builds), setuptools |

---

## Advanced Topics

### Creating Custom Modules

OCBrain uses an expert module architecture. Create your own:

```bash
ocbrain --new-module
# Interactive wizard:
# Name: my_expert
# Description: Custom domain expertise
# Base Model: mistral
# Keywords: keyword1, keyword2, ...
# Sources: https://docs.example.com, ...
```

This scaffolds `modules/my_expert/` with:
- `module.py` — (class inheriting from BaseModule)
- `weights/` — (training weights directory)
- `kb/` — (knowledge base)

Your module automatically:
- Appears in routing decision logic
- Collects training data from queries
- Participates in maturity progression
- Can be exported/imported

### Fine-tuning & Training

Training runs on schedule (hourly by default). Force manually:

```bash
ocbrain --train coding
# Logs:
# [trainer] Starting LoRA fine-tune for coding
# [trainer] Collected 5,234 training pairs
# [trainer] Using 4,687 for training, 547 for validation
# [trainer] epoch 1/3: loss=2.34, val_loss=2.41
# [trainer] epoch 2/3: loss=1.89, val_loss=1.95
# [trainer] epoch 3/3: loss=1.67, val_loss=1.76
# [trainer] Saved v4 weights → weights/active/coding_v4.safetensors
```

### Knowledge Distillation

Generate synthetic training data using a teacher model:

```bash
POST /brain/v2/distill
{
  "module_name": "coding",
  "topic": "error handling patterns",
  "num_pairs": 500,
  "teacher_model": "gpt-4"
}
```

Background job generates 500 (query, answer) pairs on the topic, adds to training pool.

### Gap Detection

Runs every 6 hours, identifies weak areas:

```
[gap_detector] Analyzing coding module responses...
[gap_detector] Low confidence on: ["async/await", "decorators", "context managers"]
[gap_detector] Queued distillation tasks:
  - coding: async patterns (500 pairs)
  - coding: python decorators (500 pairs)
  - coding: context managers (250 pairs)
```

### Privacy & Data Control

Enforce privacy with config:

```toml
[privacy]
save_history = false          # Don't persist chat
save_training_pairs = false   # Don't collect training data
telemetry = false             # No external analytics
```

Nuke data:

```bash
ocbrain --wipe-module coding       # Delete coding module data
ocbrain --wipe-all                 # Delete everything
```

### Monitoring & Observability

**Logs**: Configured in `settings.toml` with `log_level = "INFO"` (or DEBUG for trace logs)

**Metrics**: (Phase 5, not yet implemented)

**Events**: Subscribe to real-time brain state changes via SSE:

```bash
curl -N http://localhost:7437/events
# Streams: module promotions, training completions, health alerts
```

**Status Dashboard**: http://localhost:7437/dashboard

---

## Roadmap

### Near-term (Q2 2025)

- **Distributed mode** — Multi-node clustering with Redis backend
- **Metrics export** — Prometheus `/metrics` endpoint
- **Knowledge graph** — RDF-based reasoning across modules
- **Role-based access** — Fine-grained ACL for multi-user deployments

### Medium-term (Q3–Q4 2025)

- **Vision module** — Image understanding via local CLIP or LLaVA
- **Audio processing** — Auto-transcription + audio search
- **Real-time collaboration** — Shared context across team members
- **Audit logs** — Compliance-ready query auditing and retention policies

### Long-term (2026+)

- **Named entity linking** — Knowledge base graph construction
- **Multi-language support** — Automatic query translation + cross-lingual search
- **Optimized inference** — GPU quantization, dynamic batching
- **Federated learning** — Train modules across decentralized instances

---

## Contributing

OCBrain welcomes contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Areas of Interest

- **Module implementations** — New expert domains (image, audio, time-series)
- **Performance** — Latency optimizations, batching, caching strategies
- **Resilience** — Additional circuit breaker patterns, failure scenario testing
- **UX** — Web UI improvements, CLI enhancements
- **Documentation** — Examples, blog posts, tutorials

---

## License

OCBrain is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Support

- **Issues & Bugs**: [GitHub Issues](https://github.com/1h0lde4/OCBrain/issues)
- **Discussions**: [GitHub Discussions](https://github.com/1h0lde4/OCBrain/discussions)
- **Documentation**: Full docs at [https://ocbrain.io/docs](https://ocbrain.io/docs)

---

**Made with ❤ for production AI systems.**
