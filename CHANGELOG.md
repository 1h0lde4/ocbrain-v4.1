# Changelog

## [2.1.0] — 2025

### Performance — response speed

- **Ollama token streaming** — all model calls now stream tokens via `stream=true`.
  Users see the first token in ~300ms instead of waiting 3–8s for the full response.
  Single-module queries stream directly from Ollama → SSE → client with zero buffering.
- **Classifier fast-path** — keyword confidence ≥ 0.75 skips the LLM classifier entirely.
  ~80% of queries never touch Ollama for routing. Saves 1–3s on obvious queries.
- **Smart merger** — 1-module queries pass through instantly. 2-module queries use
  a template join (~0ms). LLM weave only fires for 3+ conflicting module responses.
  Eliminates an entire Ollama round-trip for the majority of multi-module queries.
- **KB retrieval LRU cache** — `retrieve()` caches last 128 results (5 min TTL).
  Repeat/near-identical queries in the same session skip ChromaDB entirely (~180ms saved).
- **Web search parallel fetch** — URLs fetched with `asyncio.gather()` instead of
  sequentially. 3 URLs in parallel cuts web_search module latency ~60% (~1–2s saved).
- **SQLite WAL mode** — `PRAGMA journal_mode=WAL` on context DB. 3–5× faster reads.
  Prompt cache: `format_for_prompt()` returns a cached string until next turn is saved.
- **Async file I/O** — `aiofiles` replaces synchronous `read_text()` in `api.py`.
  Static file serving no longer blocks the event loop.
- **Ollama model pre-warm** — at startup, all module models receive a silent 1-token
  prompt in parallel. First real query is instant — no cold-load penalty (1–3s saved).

### Summary
| Scenario | Before V2.1 | After V2.1 |
|---|---|---|
| First perceived token | 3–8s | ~300ms |
| Simple query, cached | ~4s | ~500ms |
| Simple query, cold | ~4s | ~1.5s |
| Multi-module (2) | ~8–14s | ~2.5s |
| Web search | ~12–18s | ~3.5s |

## [2.0.0] — 2025

### New features
- **Brain API v2** (`/brain/v2/*`) — versioned, stable API contract with OpenAPI docs
- **Event bus** (`core/event_bus.py`) — pub/sub system for real-time brain events
- **Streaming responses** (`/query` with `stream: true`, `/events` SSE)
- **Knowledge distillation** (`learning/distiller.py`) — use teacher LLMs to generate synthetic training data on specific topics
- **Gap detection** (`learning/gap_detector.py`) — automatically detects knowledge weaknesses and queues targeted distillation
- **Brain versioning** (`core/brain_version.py`) — separate version tracking for brain state vs app code
- **Schema migrations** (`core/migrator.py`) — safe, automatic schema upgrades on every startup
- **Brain export/import** (`core/brain_export.py`) — portable `.ocbrain` bundles for sharing trained modules
- **Distillation + gap detection scheduler loops** — runs every 12h and 6h respectively
- **pip installable from GitHub** — `pip install git+https://github.com/1h0lde4/OCBrain.git`
- **apt repo on GitHub Pages** — `sudo apt install ocbrain` after adding repo
- **winget + brew + AUR** — native package manager support on all platforms

### Improvements
- `main.py` — migration check runs before anything else starts
- `scheduler.py` — adds distillation and gap detection loops
- `interface/api.py` — adds Brain API v2 router, SSE event stream, distill/export/import endpoints
- `install.sh` — unified installer with graceful pip fallback on all platforms
- `pyproject.toml` — GitHub URLs, dynamic version from version.txt, all extras defined
- `README.md` — full installation docs, API reference, module maturity model

### Bug fixes (from V1 review)
- `evaluator.py` — was calling `asyncio.run()` inside an async context (deadlock risk)
- `model_router.py` — privacy guard was imported inside method on every call
- `finetuner.py` — `__import__("datetime")` hack replaced with proper import
- `context.py` — dataclass with mutable defaults replaced with plain class

## [1.0.0] — initial release
- Core orchestrator (parser, classifier, decomposer, dispatcher, merger)
- 4 expert modules (coding, web_search, knowledge, system_ctrl)
- Custom module system with factory + registry
- LoRA fine-tuning pipeline (Unsloth/QLoRA)
- Web crawler + ChromaDB knowledge store
- Cross-platform packaging (deb, rpm, arch, exe, pkg)
- System tray, voice input, CLI
