# OCBrain Reality Audit

## Executive Summary
This document provides a reality matrix comparing the physical state of the repository against the architectural requirements laid out in `OCBRAIN_FUTURE_ARCHITECTURE.md` and `Update Unified Memory Migration Design.md`. The audit reveals significant discrepancies: while the `core/memory` system has seen substantial implementation progress (specifically L0-L4 layered memory), the surrounding orchestration, governance, and worker frameworks are either completely missing or present as empty stubs.

## Reality Matrix

### 1. Existing (Fully or Substantially Implemented)
These components exist and align closely with the target architecture:
* **Knowledge Model (`core/memory/knowledge_entry.py`)**: Implements the canonical `KnowledgeEntry` object with truth status, provenance, and contradiction relations.
* **Unified Memory (`core/memory/unified_memory.py`)**: Central memory hub implementing the `LayerRouter` and assembling L0-L4 memory backends. Features the `HookRegistry` for the Memory Curator.
* **Hybrid Retrieval (`core/memory/hybrid_retrieval.py`)**: Implements BM25 + semantic + RRF fusion as required.
* **SQLite & InMemory Backends (`core/memory/backends/`)**: Storage, Vector, and Archive backends are present.
* **Core Base (`core/config.py`, `core/context.py`, `core/model_router.py`)**: Basic routing and config structures exist.

### 2. Partial (Implemented but Incomplete or Misaligned)
These components exist but require alignment, refactoring, or completion:
* **Memory Curator (`core/memory/unified_memory.py`)**: The `HookRegistry` exists, but the actual `MemoryCuratorWorker` that registers and implements these hooks is missing.
* **Governance (`core/governance/`)**: The directory exists, and `memory_governor.py` is present, but it lacks the canonical 5 governors (specifically missing `GovernanceKernel` and `OrchestrationGovernor`).
* **Observability (`core/observability/`)**: Contains a `tracer.py`, but lacks the comprehensive `observability_framework.py` mentioned in the design.
* **Graph Memory (`core/memory/graph/`)**: `graph_engine.py` exists but is not yet fully wired for multi-hop retrieval or mutual indexing with L2 (scheduled for v4.3.5.1).

### 3. Missing (Required but Absent)
These components are explicitly required by the architecture or listed as existing in `STATUS.md` but are physically missing (directories contain only `__init__.py`):
* **Events Framework (`core/events/`)**: Completely missing. No `event_stream.py` (Immutable WAL + pub/sub + replay).
* **Workflow Engine (`core/workflow/`)**: Completely missing. No `workflow_engine.py` (DAG + partial exec).
* **Pipeline Middleware (`core/pipeline/`)**: Completely missing. No `pipeline_middleware.py`.
* **Worker Framework (`core/workers/`)**: Completely missing. No canonical worker types implemented (missing `cognitive_worker.py`, `specialist_workers.py`, `system_prompt_registry.py`). Missing `MemoryCuratorWorker`, `PlannerWorker`, `ReActWorker`, etc.
* **Governance Kernel (`core/governance/`)**: Missing `governance_kernel.py` which enforces hard limits.
* **Skill Registry (`core/skills/`)**: Missing `skill_registry.py` (only `skill_interface.py` exists).

## Conclusion
The `STATUS.md` file incorrectly states that events, workflow, pipeline, and worker modules are implemented. They must be restored or implemented to align with the Phase 4+ target architecture.
