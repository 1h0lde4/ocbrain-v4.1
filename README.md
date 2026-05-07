# OCBrain V3.01

OCBrain is a local-first, self-governing cognitive memory runtime and AI orchestrator designed to transform standard LLM interactions into a coherent, long-term learning experience. It moves beyond stateless RAG architectures by implementing a multi-layer cognitive substrate that manages episodic, semantic, and procedural knowledge with integrated governance and health monitoring.

## Overview

OCBrain solves the "context amnesia" problem in local AI systems. While traditional assistants lose state between sessions, OCBrain continuously learns from interactions, extracting facts into a semantic graph and recording successful workflows into procedural memory. 

The system is built on a "Resilience-First" architecture, ensuring stability through adaptive concurrency control and a multi-provider mesh that gracefully handles local model failures.

### Key Value Proposition
- **Long-Term Coherence**: Maintains memory across sessions via a multi-tier cognitive vault.
- **Relational Intelligence**: Connects events, entities, and code modules using a SQLite-based Knowledge Graph.
- **Production-Grade Reliability**: Enforces circuit breakers, backpressure guards, and health-based provider fallback.
- **Self-Governing Evolution**: Automatically monitors its own health and proposes architectural upgrades.

## Features

- **Multi-Layer Cognitive Memory**: Specialized tiers for Episodic (events), Semantic (facts), Procedural (workflows), and Archive (provenance) data.
- **TEMPR Retrieval Fusion**: Advanced multi-channel retrieval combining Semantic (Vector), Keyword (FTS5), Graph (Relational), and Temporal context via Reciprocal Rank Fusion (RRF).
- **Relational Graph Engine**: SQLite-backed graph tracking of Entity-Relationship-Event (ERE) triplets for causal reasoning.
- **Adaptive Forgetting**: Importance-based memory decay that prunes "semantic silt" while reinforcing high-value knowledge.
- **Resilient Provider Mesh**: Unified interface for Ollama and OpenAI-compatible backends with exponential cooldowns and health scoring.
- **Meta-Cognitive Introspection**: A self-modeling system that can factually report its own capabilities, limitations, and stability metrics.
- **Goal-Aware Context Assembly**: Dynamically constructs the LLM context by prioritizing relevant memory tiers based on query intent.
- **Shadow Learning**: Background recording and distillation of high-confidence interactions for continuous refinement.

## Architecture

OCBrain follows a modular, layered architecture designed for local execution and high observability.

### Key Modules
- **Orchestrator (`core/orchestrator.py`)**: Coordinates the parallel execution flow from classification to memory assembly and final merging.
- **Cognitive Vault (`core/memory/cognitive_vault.py`)**: Manages the multi-tier storage substrate and provenance tracking.
- **Graph Engine (`core/memory/graph/`)**: Handles relational indexing and graph-walk retrieval.
- **Health Monitor (`core/meta/health_monitor.py`)**: Continuously audits system metrics (stability, retrieval precision, provider uptime).
- **Provider Mesh (`core/provider_mesh.py`)**: Manages the lifecycle and failover logic for LLM backends.
- **Memory Governor (`core/governance/`)**: Enforces quality floors, growth limits, and consistency checks on the memory system.

### Execution Flow
1. **API/CLI**: Receives user query.
2. **Parser**: Extracts entities and intent.
3. **Context Assembly**: Triggers TEMPR fusion to pull relevant Episodic, Semantic, and Procedural memories.
4. **Classifier**: Semantically routes the query to specialized expert modules (Coding, Knowledge, System Ctrl).
5. **Provider Mesh**: Executes generation across available local models with fallback logic.
6. **Merger**: Synthesizes multi-module results into a single coherent response.
7. **Shadow Learner**: Records the interaction for long-term memory consolidation.

## Installation

### Dependencies
- **Python**: 3.11 or higher.
- **Ollama**: Required for local LLM execution.
- **System Libraries**: `sqlite3`, `scipy`, `sentence-transformers`.

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/1h0lde4/OCBrain.git
   cd OCBrain
   ```
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   ```
   *For full feature support (voice, training):*
   ```bash
   pip install -e ".[all]"
   ```

## Usage

### Running the API
Start the OCBrain server (FastAPI):
```bash
python main.py
```
By default, the API runs on `http://localhost:8000`.

### Command Line Interface
Interact with OCBrain via the CLI:
```bash
ocbrain "Explain how the memory graph works"
```

### Key Endpoints
- `POST /query`: Main entry point for user interaction (supports streaming).
- `GET /health`: Returns real-time health and stability metrics.
- `GET /introspection`: Provides a factual report on active capabilities and limitations.
- `GET /dashboard`: Exports the full state of the meta-cognitive self-model.
- `POST /evolve/plan`: Generates prioritized system upgrade proposals.

## Configuration

OCBrain uses a central configuration system managed in `core/config.py`.

### Environment Variables
- `OLLAMA_HOST`: URL of the Ollama server (default: `http://localhost:11434`).
- `OCBRAIN_DEBUG`: Set to `true` for verbose logging and tracebacks.

### Configuration Files
- `pyproject.toml`: Manages dependencies and project metadata.
- `.data/`: All persistent state (Memory Vault, Knowledge Graph, Context History) is stored here.

## Project Structure

```text
├── core/                # System Core
│   ├── memory/          # Cognitive Memory (Vaults, Graph, Fusion)
│   ├── meta/            # Meta-Cognition (Self-Model, Health, Planner)
│   ├── governance/      # Safety and Evolution Guards
│   ├── runtime/         # Resilience and Concurrency Limits
│   └── shadow/          # Shadow Learning and Interaction Recording
├── modules/             # Expert Modules (Coding, Knowledge, Web Search)
├── interface/           # Entry points (API, CLI, Voice, Web UI)
├── learning/            # Distillation, Embedding, and Training pipelines
├── tests/               # Multi-tier test suite (Unit, Phase, Stress, Chaos)
└── data/                # Local data storage (SQLite, JSONL)
```

## Technical Details

- **Framework**: FastAPI (API), Pydantic (Models), SQLAlchemy/SQLite (Storage).
- **NLP/Embeddings**: Sentence-Transformers (Local), SciPy (Cosine Similarity).
- **Concurrency**: Asyncio-native with `AdaptiveSemaphore` for latency-based load management.
- **Design Patterns**: Provider Abstraction, Event-Bus architecture, Parallel Orchestration, Circuit Breaker.

## Roadmap

Derived from current TODOs and evolutionary goals:
- **Autonomous Evolution (Phase 5)**: Automated application of upgrade proposals via sandboxed patching.
- **Graph-Walk Reasoning**: Deep causal retrieval for complex multi-step reasoning.
- **Semantic Silt Management**: Automated dataset distillation from high-value episodic traces.
- **Cross-Verification**: Multi-model consensus for validating quarantined web knowledge.

## License

MIT License. See [LICENSE](LICENSE) for details.
