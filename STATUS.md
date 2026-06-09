# OCBrain v4.3.4 — Project Status

## Tests
**114 passing · 0 failing · 0 skipped**

```
pytest tests/ -q -p no:warnings
114 passed in 14.78s
```

## Graphify Analysis
- **1,543 nodes** · **2,755 edges** · **43.1× token reduction per query**
- Code graph: `graphify-out/graph.json` + `graphify-out/graph.html`

## Bug Fixes Applied
| Bug | File | Status |
|-----|------|--------|
| AdaptiveSemaphore release-before-acquire | core/runtime/resilience.py | ✅ Fixed |
| bm25_search_placeholder (fake BM25) | core/memory/mem_vault.py | ✅ Fixed |
| set_long_term_memories defined twice | core/context.py (ZIP) | ✅ Already fixed in GitHub |

See `BUG_FIXES.md` for detailed descriptions.

## Architecture
```
core/
  config.py              Config with TOML/YAML hot-reload + dot-path access
  context.py             ContextMemory — SQLite WAL session + entity tracking
  event_bus.py           Internal pub/sub EventBus
  orchestrator.py        Central request orchestrator (classify→route→memory→respond)
  model_router.py        MaturityRouter: bootstrap→shadow→native stages
  provider_mesh.py       OllamaProvider + OpenAI-compatible + fallback
  classifier_v3.py       Semantic intent classifier (sentence-transformers + keyword fallback)
  brain_version.py       Version management
  brain_api.py           FastAPI Brain API v2
  brain_export.py        .ocbrain bundle import/export
  migrator.py            SQLite schema migrations
  privacy.py             PrivacyGuard — consent + GDPR wipe
  
  events/event_stream.py       Immutable WAL + pub/sub + replay (v4.1.3)
  governance/
    governance_kernel.py       Hard limits: recursion, steps, tokens, HITL (v4.1.4)
    memory_governor.py         Memory quality/size enforcement
  workflow/workflow_engine.py  DAG + partial exec + retry + HITL (v4.1.5)
  pipeline/pipeline_middleware.py  PII + safety + memory inject (v4.1.6)
  observability/
    observability_framework.py Counters + spans + health checks (v4.1.7)
    tracer.py                  ContextVar span tracing
  skills/
    skill_interface.py         BaseSkill + validation + cache (v4.1.1)
    skill_registry.py          SemVer + MCP auto-expose (v4.1.2)
  workers/
    cognitive_worker.py        ToolLoopAgent + stopWhen (v4.2.1)
    specialist_workers.py      ReAct + Planner + Reflection (v4.2.2)
    system_prompt_registry.py  7-system validated prompt registry (v4.2.6)
  memory/
    mem_vault.py               MemoryVault with real BM25 (BUG FIXED)
    hybrid_retrieval.py        BM25 + semantic + RRF fusion (v4.3.2)
    cognitive_vault.py         High-level CognitiveVault interface
    assembly.py                ContextAssemblyEngine
    memory_system.py           L0-L4 UnifiedMemory (v4.3.1-4)
    consolidation/             Background consolidation loop
    retrieval/fusion.py        TEMPR-inspired fusion engine
    graph/graph_engine.py      SQLite knowledge graph
    dedup.py                   Content deduplication
  runtime/
    resilience.py              CircuitBreaker + AdaptiveSemaphore (BUG FIXED)
    limits.py                  safe_llm_call + BackpressureGuard
    state.py                   StateStore SQLite WAL async queue
    network.py                 httpx AsyncClient pool
    efficiency.py              PromptCache + ModelTier
  web/                         fetch + parse + clean + search
  web_learning/                WebLearningPipeline: crawl→trust→quarantine→memory
  meta/                        health_monitor + planner + self_model + introspection
  shadow/                      ShadowLearner + ShadowCollector (RLHF dataset)
  context_loader.py            OCBRAIN.md cascading loader (v4.1.8)

interface/
  cli.py                       argparse CLI
  api.py                       FastAPI REST server

modules/
  base.py                      BaseModule with memory + LLM access
  coding/                      CodingModule

main.py                        Entry point (REPL + API server modes)
```

## Quick Start
```bash
cd ocbrain
pip install pytest pytest-asyncio --break-system-packages
python -m pytest tests/ -q
python main.py                  # REPL mode
python main.py --serve          # API server mode (requires fastapi uvicorn)
python main.py --cli ask "hello" # CLI mode
```
