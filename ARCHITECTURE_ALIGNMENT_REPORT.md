# Architecture Alignment Report

## Current State vs Target State (v4.9 target)

### 1. Memory Architecture Alignment
**Target:** Local-first, governed, event-sourced, 5-layer Unified Memory.
**Status:** **ALIGNED**
* `unified_memory.py` successfully assembles L0 (LRU), L1 (Episodic SQLite), L2 (Semantic InMemory), L3 (Graph SQLite - partial), and L4 (Archive).
* `knowledge_entry.py` provides the canonical truth model with `truth_status`, `supports`, and `contradicts` fields.
* The migration out of the monolithic structure has been successfully executed for memory.

### 2. Graph-Vector Mutual Indexing (v4.3.5.1 target)
**Target:** Multi-hop retrieval via mutual indexing.
**Status:** **PENDING**
* `graph_engine.py` exists, but the cross-indexing with L2 semantic memory is not fully implemented. `unified_memory.py` has basic hooks for adding nodes, but complex retrieval and sync drift mitigation are incomplete.

### 3. Active Memory Improvement (Memify) (v4.3.6 target)
**Target:** Memory actively improves itself; stale facts pruned, high-value strengthened.
**Status:** **PENDING RESTORATION**
* The `HookRegistry` exists in `unified_memory.py` to support this.
* However, the required `MemoryCuratorWorker` that utilizes these hooks is entirely missing from the codebase.

### 4. Observability & LLM Tracing (v4.4.5 target)
**Target:** Langfuse integration for prompt-level visibility.
**Status:** **NOT STARTED**
* Currently relies on internal logging and a basic `tracer.py`. No external LLM observability (Langfuse) is wired in.

### 5. Instinct → Skill Two-Stage Learning (v4.3.9 target)
**Target:** Robust skill learning via instinct clustering.
**Status:** **NOT STARTED**
* The `shadow/shadow_learner.py` exists but the clustering and automatic evolution pipeline (ECC-inspired) is not implemented.

### 6. Durable Workflow Execution (v4.4.8 target)
**Target:** Checkpoint/resume from EventStream.
**Status:** **BLOCKED (MISSING COMPONENTS)**
* Both `workflow_engine.py` and `event_stream.py` are completely absent from the codebase, making this architectural goal currently impossible.

## Immediate Action Items
To proceed on the critical path to v4.9, the following alignment steps are mandatory:
1. **Restore Core Missing Components:** `event_stream.py`, `governance_kernel.py`, `workflow_engine.py`, and the `core/workers/` framework.
2. **Implement MemoryCuratorWorker:** Required to unlock the Phase v4.3.6 Active Memify architecture.
3. **Upgrade L2 Persistence:** Migrate InMemoryVectorBackend to Chroma to satisfy Risk 1 (L2 Persistence Migration).
