# OCBrain — Update Unified Memory Migration Design

Review the current **Memory Migration Design (v4.3.4.91 + v4.3.4.9)** and apply the following architectural modifications before implementation begins.

These changes are **design-level updates**, not implementation work.

The objective is to ensure the Unified Memory architecture can support:

* Graph Memory
* Contradiction Detection
* Governance
* Memory Curator
* GraphRAG
* Provenance Tracking
* Self-Learning Validation
* Future Distributed Memory Systems

without requiring another major memory refactor later.

---

## 1. Introduce v4.3.4.92 — Knowledge Model Foundation

Insert a new roadmap phase:

```text
v4.3.4.91 Memory Abstraction Layer

v4.3.4.92 Knowledge Model Foundation

v4.3.4.9 Unified Memory Consolidation

v4.3.4.95 Memory Benchmarking

v4.3.5 Graph Memory
v4.3.6 Memory Curator
v4.3.7 Testing + Integration
```

This phase must be completed before Unified Memory migration begins.

---

## 2. Separate KnowledgeEntry From KnowledgeEvent

The current design treats memory as events.

Replace this with a dual-object model.

### KnowledgeEntry

Represents the canonical memory object.

Example fields:

```python
KnowledgeEntry:
    entry_id
    content
    summary
    layer
    importance
    confidence
    truth_status
    provenance
    graph_refs
    tags
    metadata
    created_at
    updated_at
```

### KnowledgeEvent

Represents lifecycle changes affecting a KnowledgeEntry.

Examples:

```python
created
updated
accessed
promoted
archived
contradicted
merged
deprecated
deleted
```

KnowledgeEntry becomes the primary memory unit.

KnowledgeEvent becomes the audit/history layer.

Do not use KnowledgeEvent as the sole memory representation.

---

## 3. Add Truth & Contradiction Framework

Extend the canonical memory schema with:

```python
truth_status
```

Allowed values:

```text
unknown
candidate
verified
conflicted
deprecated
```

Add relationship fields:

```python
supports[]
contradicts[]
supersedes[]
```

These fields must be available before Graph Memory begins.

Future phases will use them for:

* contradiction detection
* governance
* memory curation
* self-learning validation
* graph reasoning

No implementation required now.

Only update the architecture and schema.

---

## 4. Add L0 Working Memory

Current architecture effectively begins at L1.

Update target architecture to:

```text
L0 Working Memory
L1 Episodic Memory
L2 Semantic Memory
L3 Graph Memory
L4 Archive Memory
```

L0 may initially be a lightweight in-memory cache.

Purpose:

* active context
* reasoning workspace
* retrieval acceleration

Ensure UnifiedMemory can expose L0 even if implementation is minimal initially.

---

## 5. Add Memory Curator Lifecycle Hooks

Add extension points to UnifiedMemory.

Examples:

```python
before_write()
after_write()

before_promote()
after_promote()

before_archive()
after_archive()

before_delete()
after_delete()
```

These are placeholders for v4.3.6.

No implementation required now.

Only define extension points and integration strategy.

---

## 6. Re-evaluate Archive Strategy

Current design uses:

```text
JSONLArchiveBackend
```

Reassess whether archive storage should instead be:

```text
SQLiteArchiveBackend
```

Compare:

* provenance queries
* contradiction tracing
* audit history
* event replay
* retrieval performance
* long-term scalability

Produce a recommendation and justification.

If JSONL remains preferred, explain why.

If SQLite is superior, update the design accordingly.

---

## 7. Update Migration Design

Review all migration phases and update them to reflect:

* KnowledgeEntry + KnowledgeEvent split
* Truth model
* L0 memory layer
* Curator hooks
* Archive decision

Ensure:

```text
Single authoritative memory source
```

remains a hard requirement.

Avoid:

* split-brain memory systems
* parallel write paths
* duplicate ownership of memory data

---

## 8. Deliverables

Produce updated versions of:

* Dependency Graph
* Target Architecture
* Knowledge Schema
* Backend Architecture
* Migration Phases
* Benchmark Plan
* Rollback Plan
* Updated Roadmap

Do not begin implementation.

Only update the design documents and migration plan.

The goal is to ensure UnifiedMemory becomes the permanent foundation for all future OCBrain cognitive systems.
