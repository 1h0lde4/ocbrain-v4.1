OCBRAIN FUTURE ARCHITECTURE
Comprehensive Research & Upgrade Plan
Date: June 15, 2026
Status: Research Only — NO implementation
Scope: 200+ repositories studied | Architecture analysis | Roadmap reconciliation
Output: Architectural recommendations for OCBrain v4.x → v5.0


CRITICAL RULE COMPLIANCE
This document contains zero code, zero patches, zero modifications.
Every recommendation follows the evaluation framework:
Why → Problem solved → Affected component → Tradeoffs → Complexity → Worth it when?


SECTION 1 — CURRENT STATE ASSESSMENT
1.1 Memory System
Current architecture: 5-layer unified memory (L0 LRU → L1 SQLite+FTS5 → L2 BM25+embeddings → L3 procedural → L4 archive) with a SQLite knowledge graph.
Strengths:

Zero-dependency baseline (works without sentence-transformers)
WAL mode + atomic writes after audit fixes
Provenance via L4 archive
GraphEngine with contradiction detection

Weaknesses:

L2 semantic memory is in-memory only — lost on restart
No graph-vector fusion (graph and L2 operate independently)
BM25 index rebuilt from scratch on each restart (no persistence)
No multi-hop reasoning across graph edges
Entity extraction is regex-based, not LLM-assisted
No memory versioning or temporal queries ("what did I know before X?")
Consolidator promotes to L2 but L2 doesn't persist — creates illusion of upgrade

Bottlenecks:

L2 semantic search: no true ANN (approximate nearest neighbor) — O(n) cosine scan
Graph engine: per-call SQLite connections (high overhead for dense traversals)
No streaming from memory layers to workers

Technical debt:

MemoryConsolidator promotes L1→L2 but L2 evaporates on restart
CognitiveVault wraps UnifiedMemory with only basic store/recall — misses graph queries, temporal filtering, provenance lookup
MemoryCuratorWorker class entirely absent (§7.1 canonical worker types)

Architectural risks:

L2 data loss on restart will cause subtle degradation (system appears healthy, memory silently shrinks)
BM25 index cold-start adds 100-500ms latency spike at startup for large corpora
Graph and vector layers not fused — parallel queries with separate scoring miss cross-layer signals


1.2 Orchestration
Current architecture: OCBrainOrchestrator → classify intent → route to worker → pipeline → memory → response.
Strengths:

GovernanceKernel enforces hard limits at every step
EventStream provides full audit trail
Worker pool with pluggable types

Weaknesses:

No durable execution — if worker crashes mid-task, state is lost
No saga/compensation pattern for multi-step workflows
Orchestrator blocks on single worker; no true parallel fan-out
No long-horizon task capability (tasks bounded by request lifetime)
No human-in-the-loop at workflow DAG level (only at governance level)


1.3 Learning Pipeline
Current architecture: crawl → clean → distil → train (LoRA) with SQLite state tracking.
Strengths:

Shadow dataset with poison filter (post-audit)
Cross-platform file moves
Safe interval parsing

Weaknesses:

No evaluation framework (are fine-tuned models actually better?)
No A/B evaluation of model generations
Training pipeline entirely offline — no online RL signal
SFTTrainer uses full instruction/input/output (post-fix) but no DPO, PPO, or GRPO
No curriculum learning — pairs not ordered by difficulty
Replay buffer exists but DATA_CHUNKS → replay path not validated end-to-end


1.4 Retrieval
Current architecture: BM25+cosine+RRF for L2; FTS5 for L1; in-memory BM25Index.
Strengths:

Hybrid retrieval validated by HandsOnLLM Ch8
RRF fusion with configurable k

Weaknesses:

No knowledge graph retrieval integration (graph and vector are disjoint)
No multi-hop retrieval (can only answer single-hop "what is X?")
No reranking step (cross-encoder reranking improves precision significantly)
No query expansion or HyDE (Hypothetical Document Embeddings)
Embeddings are optional — when unavailable, falls back to BM25-only


1.5 State Management
Current architecture: StateStore (SQLite WAL, Persistence Actor post-audit), ContextMemory (SQLite WAL), EventStream (WAL log).
Strengths:

Persistence Actor pattern isolates DB from event loop (post-audit)
WAL mode for concurrent reads
Full queue drain on shutdown (post-audit)

Weaknesses:

Three separate SQLite files with no unified query capability
No distributed state (single-node only)
No state schema versioning beyond basic migrations
EventStream WAL is append-only but not replicated


1.6 Workflow Handling
Current architecture: WorkflowEngine with DAG JSON, partial execution, node caching, retry, HITL nodes.
Strengths:

DAG-based (no unbounded loops)
Partial re-execution skips unchanged nodes
Node output caching

Weaknesses:

No durable execution (workflow dies with process)
No cross-process workflow continuation
No workflow versioning (deploying new version breaks in-flight workflows)
No saga/compensation for multi-service transactions
No workflow marketplace or template registry


1.7 Scalability Limitations

Single process: all components share one Python asyncio event loop
Memory: L2 in-memory caps practical corpus at ~GB scale
Graph: SQLite caps at ~10M edges before degrading
Inference: single Ollama instance (no exo cluster yet)
Concurrency: AdaptiveSemaphore is in-process, not distributed
Storage: no columnar storage for analytics, no time-series for metrics


SECTION 2 — REPOSITORY ANALYSIS
The 200+ repositories studied are grouped into 15 architectural domains. Each analysis answers: purpose, key concepts, valuable ideas, irrelevant ideas, OCBrain application, priority (0-10).

DOMAIN A: Agent Harness Operating Systems
ECC (affaan-m/ECC) — ★215k · Priority: 10/10
Purpose: Agent harness performance optimization system for Claude Code, Codex, Cursor, OpenCode, Zed, and GitHub Copilot. 261 skills, 64 agents, 84 legacy command shims.
Architecture:

Plugin system with agent-harness-specific adapters (.claude/, .cursor/, .codex/, etc.)
Instinct-based continuous learning v2: session patterns → instincts (confidence-scored) → skills (clustered)
SQLite state store for cross-session memory and skill tracking
Hook system: PreToolUse, PostToolUse, SessionStart, SessionEnd, Stop
AgentShield: security auditor with 102 static analysis rules, red-team/blue-team/auditor pipeline
Rust control-plane prototype (ecc2/) with daemon, sessions, status commands
Manifest-driven selective install with state tracking

Key concepts:

Instinct ≠ Skill: instincts are session-extracted raw patterns (low confidence); skills are evolved clusters (high confidence). This two-stage learning is more robust than direct session→skill.
Cross-harness isolation: ECC_AGENT_DATA_HOME scopes memory per harness to prevent cross-contamination
Hook profiles: ECC_HOOK_PROFILE=minimal|standard|strict — severity-tiered governance
Observer loop prevention: 5-layer re-entrancy guard prevents recursive hook chains
Session state as operator handoff: ecc status --markdown --write status.md exports readiness for async team workflows

Valuable for OCBrain:

Instinct→Skill two-stage learning: OCBrain's SkillCreator should learn instincts first, cluster to skills later (not direct)
Hook architecture for lifecycle events (pre/post tool, session start/end)
Cross-harness session isolation pattern
AgentShield security model for provider validation
Rust control-plane direction validates v5.0 Rust Cognitive Kernel
ecc status operator handoff = OCBrain CURRENT_STATE.md automated generation

Irrelevant: Language-specific rules (TypeScript, PHP, etc.), marketplace billing, Tkinter dashboard
Recommended action: Heavy Inspiration. Adopt instinct→skill two-stage learning pattern. Do not adopt the cross-harness adapter approach (OCBrain is a platform, not a harness plugin).

AutoGPT (Significant-Gravitas/AutoGPT) — ★184k · Priority: 6/10
Purpose: Autonomous AI agent with Block platform, Agent Protocol, Langfuse integration.
Key concepts: Agent Protocol standardization, Block-based workflow composition, forked execution graph.
Valuable for OCBrain: Agent Protocol endpoints already adopted. Block platform concept = OCBrain's WorkflowNode but with visual composition. Forked execution for parallel task branches.
Irrelevant: Frontend heavy (React), cloud-first.
Recommended action: Adopt Concepts Only. Agent Protocol already integrated.

MetaGPT (FoundationAgents/MetaGPT) — ★50k · Priority: 8/10
Purpose: Multi-agent framework with role-based team simulation, SOP-driven workflows.
Architecture:

Roles: Product Manager, Architect, Engineer, QA Engineer each have defined tools, responsibilities
Memory: shared message pool + role-specific scratchpad
Structured output: each role emits typed artifacts (PRD, Design, Code, Tests)
SOP (Standard Operating Procedure): explicit inter-role communication protocols

Key concepts:

Role specialization over generalist agents: specialized roles with fixed tool access outperform generalist agents on complex tasks
Typed artifact flow: each agent produces a typed artifact that becomes the next agent's input (no unstructured text passing)
Shared environment: all roles read from a shared message environment rather than private communication channels

Valuable for OCBrain:

OCBrain worker types (§7.1) map well to roles: PlannerWorker → Product Manager, CoderWorker → Engineer, EvaluatorWorker → QA
Typed artifact pattern: workers should produce typed outputs (not raw strings) passed to next worker
Shared message environment = OCBrain's EventStream extended with typed artifacts

Recommended action: Heavy Inspiration. Formalize worker output types. Add artifact-passing between workers.

BabyAGI (yoheinakajima/babyagi) — ★20k · Priority: 3/10
Purpose: Task-driven autonomous agent loop: create task → prioritize → execute → repeat.
Key concepts: Simple task queue with priority ordering. The task-creation loop without bounds.
Valuable for OCBrain: Historical reference only. OCBrain's stopWhen(N) + GovernanceKernel already addresses BabyAGI's unbounded loop failure mode.
Recommended action: Not Recommended. OCBrain already exceeds this architecture.

CrewAI (crewAIInc/crewAI) — ★30k · Priority: 7/10
Purpose: Role-based multi-agent collaboration with crew coordination, task delegation.
Key concepts: Crew = group of agents with roles, tools, and delegation rules. Sequential and hierarchical processes. Inter-agent memory sharing.
Valuable for OCBrain: Hierarchical process pattern (SupervisorWorker orchestrates sub-workers). Delegation with fallback. Role-specific memory scoping.
Recommended action: Adopt Concepts Only. Delegation pattern and role-scoped memory.

Agno (agno-agi/agno) — ★8k · Priority: 7/10
Purpose: Lightweight, production-grade agent framework. Multi-modal, multi-agent, structured outputs.
Key concepts: Agent teams with shared memory. Session storage. Reasoning steps exposed. Streaming built-in.
Valuable for OCBrain: Agent team composition pattern where multiple specialist workers collaborate on one task with shared context.
Recommended action: Adopt Concepts Only.

Mastra (mastra-ai/mastra) — ★12k · Priority: 7/10
Purpose: TypeScript-native agent framework with durable workflows, built-in evaluation, tracing.
Key concepts: Workflows as durable TypeScript functions. Built-in eval framework. OpenTelemetry native. Tool calling with structured results.
Valuable for OCBrain: Durable workflow pattern. Built-in eval framework design. TypeScript type safety for tool schemas (applicable to Python via dataclasses).
Recommended action: Adopt Concepts Only. Durable execution pattern.

DOMAIN B: Durable Workflow Execution
Temporal (temporalio/temporal) — ★24k · $5B valuation · Priority: 10/10
Purpose: Durable execution platform. Workflows survive process crashes via event sourcing and replay.
Architecture:

Event-sourced workflow history (append-only)
Worker polls task queues, executes workflow code, emits commands
Deterministic replay: same event history → same execution path
Activity = individual operation (retryable, isolated)
Signal = external event injection into running workflow
Timer = wait for duration (days/weeks, survives restarts)
Workflow versioning: multiple versions can coexist

Key insight for OCBrain: OCBrain's EventStream is already event-sourced, but workflows don't survive process restarts. Temporal's "durable execution" is the missing piece between OCBrain's current WorkflowEngine and truly autonomous long-running agents.
Why OCBrain needs this pattern:

Current OCBrain workflows die when the server restarts
Long-horizon tasks (train a model, crawl a knowledge base for days) require durable execution
HITL approval can block for hours/days — workflow must survive the wait
Retry with backoff across restarts is impossible without durability

What problem it solves: Makes OCBrain workflows fault-oblivious. "Run until done, regardless of server restarts."
Tradeoffs:

Temporal server is a significant infrastructure dependency (Go + Cassandra/PostgreSQL)
Deterministic code constraints (no random, no time.time() in workflow code)
Cold start latency for workflow replay
Complexity: workflows + activities + workers + task queues

Complexity introduced: HIGH (requires Temporal server, workflow SDK integration)
Worth it: Later (v4.8+). OCBrain needs durable execution for Phase 7 autonomous learning but this is premature before v4.5.
Recommended action: Adopt Concepts Only now. Direct Integration for v4.8 Durable Workflow Runtime. Model OCBrain's WorkflowEngine on Temporal patterns (durable state in EventStream WAL, checkpoint/resume API).

Kestra (kestra-io/kestra) — ★15k · Priority: 7/10
Purpose: Declarative workflow orchestration with YAML-based workflow definitions, 400+ plugins.
Key concepts: Namespace-scoped workflows. Trigger system (schedule, webhook, API). Flow namespace inheritance. Real-time execution topology.
Valuable for OCBrain: YAML workflow definitions = portable, version-controllable workflow templates. Namespace pattern = skill registry namespacing. Trigger system = OCBrain's EventStream subscriber pattern.
Recommended action: Adopt Concepts Only. YAML workflow format for human-authored workflows.

Prefect (PrefectHQ/prefect) — ★16k · Priority: 6/10
Purpose: Python-native workflow orchestration with deployments, flow versioning, infrastructure.
Key concepts: @flow and @task decorators. Deployments = scheduled flow runs. Artifacts = flow outputs. Infrastructure pools.
Valuable for OCBrain: Decorator-based workflow definition is simpler than DAG JSON for Python users. Deployment concept = skill versioning + scheduling.
Recommended action: Adopt Concepts Only. Decorator pattern for workflow authoring UX.

Dagster (dagster-io/dagster) — ★12k · Priority: 7/10
Purpose: Data orchestration platform with asset-based paradigm, lineage, and observability.
Key concepts: Software-defined assets. Asset materialization lineage. Sensors and schedules. Built-in UI with asset graph visualization.
Valuable for OCBrain: Asset paradigm = every memory write is an asset with provenance. Materialization lineage = OCBrain's L4 archive but queryable. Asset graph = OCBrain's knowledge graph but for data flow.
Recommended action: Heavy Inspiration. Asset-based paradigm for knowledge provenance in Phase 4.

Apache Airflow (apache/airflow) — ★39k · Priority: 4/10
Purpose: Platform to programmatically author, schedule and monitor workflows as DAGs.
Key concepts: DAG + tasks + sensors + operators. Mature scheduler with backfill. Python-native DAG definition.
Relevant for OCBrain: OCBrain's WorkflowEngine already uses DAG paradigm. Airflow's mature scheduling pattern relevant for knowledge acquisition scheduling.
Recommended action: Adopt Concepts Only. Scheduler design for knowledge acquisition cron-like tasks.

PowerJob/xxl-job — Priority: 2/10
Purpose: Java-based distributed job schedulers.
Valuable for OCBrain: Near-zero. Python-native schedulers already covered by Prefect/Dagster.
Recommended action: Not Recommended.

DOMAIN C: Knowledge Graphs & GraphRAG
topoteretes/cognee — ★5k · Priority: 10/10
Purpose: Open-source AI memory platform. Graph + vector hybrid for agent persistent memory.
Architecture:

cognify pipeline: classify docs → check permissions → extract chunks → LLM entity/relationship extraction → generate summaries → embed to vector + commit to graph
memify pipeline: post-processing that prunes stale nodes, strengthens frequent connections, adds derived facts
search: 14 retrieval modes from classic RAG to chain-of-thought graph traversal
30+ data source connectors
Supports NetworkX, FalkorDB, Neo4j as graph backends
Incremental learning: only processes new/updated files on re-runs

Key insight: Cognee's memify pipeline is what OCBrain's MemoryConsolidator SHOULD be doing — not just promoting entries between layers, but actively improving the quality of existing memory through pruning, strengthening, and deriving new facts.
Why OCBrain needs this:

Current consolidation is passive (evict old, promote high-importance)
Cognee's active memory improvement derives new knowledge from existing knowledge
The graph-vector mutual indexing gives context that pure vector search misses
The "Optimizing the Interface Between Knowledge Graphs and LLMs" paper validates the approach scientifically

Tradeoffs:

LLM calls required for entity extraction (cost per document)
Graph and vector must be kept in sync (consistency challenge)
Complex pipeline vs OCBrain's current simple write-and-search pattern

Recommended action: Heavy Inspiration. Adopt cognify/memify pipeline pattern for OCBrain's knowledge acquisition and memory curation. Do not directly integrate cognee (OCBrain has its own memory architecture) — instead, borrow the pipeline design.

OpenSPG/KAG — Priority: 9/10
Purpose: Knowledge Augmented Generation. Outperforms RAG by 19.6% on HotpotQA, 33.5% on 2wiki multi-hop QA.
Architecture:

Five enhancements over RAG: (1) LLM-friendly KG representation, (2) mutual-indexing between KG and text chunks, (3) logical-form-guided hybrid reasoning, (4) knowledge alignment with semantic reasoning, (5) model capability enhancement
OpenSPG engine for KG construction
Knowledge and chunk mutual indexing: same entity has both a graph node AND a text chunk reference
Logical form guided retrieval: converts NL query to logical form before graph traversal
Lightweight build mode: 89% token cost reduction for KG construction

Key insight for OCBrain: KAG's "mutual-indexing" — every knowledge graph node also has a pointer to the original text chunk it was extracted from — is what OCBrain's graph and L2 semantic memory should share. Currently they're disjoint.
Why OCBrain needs this: Multi-hop questions (e.g., "What did we decide about the deployment strategy based on the infrastructure constraints we learned last week?") currently fail because OCBrain's retrieval is single-hop. KAG's logical-form-guided traversal enables this.
Recommended action: Heavy Inspiration. Adopt mutual-indexing between graph nodes and L2 chunks. Add logical-form query path for complex queries (Phase 4.3.8 Cognitive Retrieval Engine).

FalkorDB/FalkorDB — Priority: 7/10
Purpose: In-memory graph database with Redis-style API. Handles graphs 6x faster than Neo4j for certain workloads.
Architecture: Redis module. GraphBLAS linear algebra library for graph operations. Cypher query language.
Valuable for OCBrain: FalkorDB is the fastest open-source graph DB option. At scale (10M+ edges), SQLite graph engine will become a bottleneck. FalkorDB is the upgrade path.
When OCBrain needs it: When graph exceeds ~500K edges (Phase 5-6).
Recommended action: Future Integration Candidate (Phase 5). Keep SQLite graph for now, plan FalkorDB migration path.

neo4j/neo4j-graphrag-python — Priority: 8/10
Purpose: GraphRAG Python library for Neo4j. LLM-powered KG construction + hybrid retrieval.
Architecture: Entity extraction → KG construction → vector+graph hybrid search → LLM synthesis.
Valuable for OCBrain: Production-proven GraphRAG patterns. The entity extraction + community detection + global/local summarization pattern from Microsoft's original GraphRAG paper.
Recommended action: Adopt Concepts Only. GraphRAG retrieval patterns for Phase 4.3.8.

DB-GPT (eosphoros-ai/DB-GPT) — Priority: 7/10
Purpose: LLM + database native AI. Natural language to SQL, database agent, knowledge management.
Architecture: Agentic data interaction, AWEL workflow, model serving, knowledge base management.
Valuable for OCBrain: Database-native AI patterns. OCBrain's knowledge warehouse (v4.6.7) will need NL→SQL capability. AWEL (Agentic Workflow Expression Language) as a DSL for agent workflows.
Recommended action: Adopt Concepts Only. NL→SQL pattern for knowledge warehouse queries.

DOMAIN D: Memory for AI Agents
mem0ai/mem0 — ★40k · Priority: 9/10
Purpose: AI memory management. User-level, session-level, agent-level memory with automatic extraction.
Architecture:

Memory extraction: LLM extracts facts from conversations automatically
Three memory types: user-level (permanent preferences), session-level (temporary context), agent-level (agent-specific knowledge)
Semantic deduplication: before storing, checks if similar memory already exists
Memory graph: recent addition, stores entities and relationships
Auto-update: if new info contradicts existing memory, updates rather than duplicates

Key insight for OCBrain: Mem0's automatic extraction — the LLM reads conversations and extracts {fact, category, user_id, agent_id} tuples without human annotation — is what OCBrain should do at session end. Current OCBrain requires explicit remember() calls.
Why OCBrain needs this:

Users shouldn't need to explicitly call remember() — the system should extract facts automatically
Semantic deduplication prevents memory bloat (OCBrain has no semantic dedup in write path)
Auto-update on contradiction is more sophisticated than current dedup

Recommended action: Heavy Inspiration. Add automatic fact extraction at session end. Add semantic deduplication in write path. These are Phase 3 completion items.

chatgpt-retrieval-plugin (openai) — Priority: 5/10
Purpose: OpenAI's reference implementation for semantic document retrieval via ChatGPT plugins.
Key concepts: Upsert/query/delete API pattern. Metadata filtering. Chunk-level embedding storage.
Valuable for OCBrain: Standard retrieval API shape. Metadata filtering patterns.
Recommended action: Adopt Concepts Only. API shape already adopted.

GPTCache (zilliztech) — Priority: 6/10
Purpose: Semantic caching for LLM queries. If similar query asked before, return cached response.
Architecture: Encoder (embedding) → similarity search → cache store. Cache invalidation by TTL or exact match.
Valuable for OCBrain: OCBrain's PromptCache is hash-based (exact match only). Semantic caching would catch paraphrased queries. Significant cost saving for repeated similar queries.
Recommended action: Adopt Concepts Only. Replace hash-based cache with semantic similarity cache in core/runtime/efficiency.py.

DOMAIN E: Vector Databases
qdrant/qdrant — ★22k · Priority: 9/10
Purpose: Vector database with payload filtering, quantization, sparse-dense hybrid search.
Architecture:

Collections with typed payload
Sparse + dense vector hybrid (SPLADE + embeddings)
Quantization: scalar, product, binary — 4x-64x compression
Filtering at HNSW index level (not post-retrieval)
Raft consensus for distributed deployments
Disk-based segments (not fully in-memory requirement)

Key insight for OCBrain: Qdrant's sparse+dense hybrid directly replaces OCBrain's BM25+cosine approach. Sparse vectors (SPLADE) outperform BM25 for out-of-vocabulary terms. Payload filtering at index level is 10-100x faster than post-retrieval filtering.
Why OCBrain needs this:

Current L2 semantic memory is fully in-memory (lost on restart, O(n) scan)
Qdrant persists to disk + provides ANN (O(log n) search)
Sparse+dense eliminates the two-pass BM25+embedding approach

When OCBrain needs it: When L2 corpus exceeds ~100K entries (Phase 5).
Recommended action: Direct Integration Candidate (Phase 5.1+). Replace in-memory L2 with Qdrant for persistent, scalable semantic search.

chroma-core/chroma — ★18k · Priority: 7/10
Purpose: Embedded vector database. Zero infrastructure, runs in-process.
Architecture: SQLite + HNSW. Persistent by default. Python-first API.
Valuable for OCBrain: Chroma is already in requirements.txt. Zero-setup upgrade from in-memory L2 to persistent. Migration path is simpler than Qdrant.
Recommended action: Partial Adoption. Use Chroma as intermediate L2 upgrade before Qdrant at scale. Simpler migration path.

milvus-io/milvus — ★33k · Priority: 7/10
Purpose: Cloud-native vector database. Billions of vectors, cloud-first.
Valuable for OCBrain: Relevant only at OCBrain scale >10M entries (Phase 7+).
Recommended action: Long-term consideration. Not needed until Phase 7.

facebookresearch/faiss — ★34k · Priority: 8/10
Purpose: Library for efficient similarity search. Production-grade ANN with GPU support.
Valuable for OCBrain: FAISS's IVF+PQ index provides the best compression+speed tradeoff at medium scale. Can be used locally without infrastructure.
Recommended action: Partial Adoption (Phase 5). Use FAISS as self-contained ANN for L2 when Qdrant is too heavy.

pgvector/pgvector — Priority: 6/10
Purpose: Vector extension for PostgreSQL. Combines relational and vector queries.
Valuable for OCBrain: If OCBrain migrates to PostgreSQL (Phase 7 data platform), pgvector unifies SQL + vector in one database.
Recommended action: Future Integration Candidate (Phase 7).

neuml/txtai — Priority: 6/10
Purpose: All-in-one embeddings database. Text, image, audio semantic search.
Valuable for OCBrain: txtai's pipelines (workflow-based embedding processing) are an interesting alternative to the chunk-embed-store pattern.
Recommended action: Adopt Concepts Only.

Weaviate, HNSWLIB, Annoy, Vearch — Priority: 4/10 each
All are production-ready but covered by Qdrant/FAISS. Weaviate has GraphQL API which adds overhead. HNSWLIB and Annoy are embedding-only libraries without payloads.
Recommended action: Not Recommended. Qdrant and FAISS cover the use cases.

DOMAIN F: Observability & Evaluation
langfuse/langfuse — ★12k · Priority: 9/10
Purpose: LLM observability: traces, spans, scores, datasets, evaluations.
Architecture:

Traces → Spans → Observations hierarchy
Prompts: versioned, tested, deployed
Datasets: input/output/expected for evals
Scores: human feedback, model-based eval, rule-based
Self-hosted or cloud

Key insight for OCBrain: OCBrain's ObservabilityFramework tracks spans but doesn't capture LLM call details (prompt, response, tokens, cost). Langfuse fills this gap specifically for LLM tracing.
Why OCBrain needs this: Without LLM-level tracing, you can't know:

Which prompts cause failures
Which model versions regress quality
Where token budget is spent
How to improve the system prompt

Recommended action: Direct Integration Candidate. Add Langfuse SDK calls in core/provider_mesh.py around each LLM call. hooks exist in core/observability/ already.

confident-ai/deepeval — ★8k · Priority: 8/10
Purpose: LLM evaluation framework. Metrics: correctness, faithfulness, relevance, toxicity.
Architecture:

Test cases with input, actual output, expected output, context
G-Eval: GPT-4 based criteria evaluation
RAG metrics: faithfulness, contextual precision/recall
Regression testing for prompt/model changes

Key insight for OCBrain: OCBrain's EvaluatorWorker does pointwise (1-5) scoring but no automated regression testing. DeepEval's approach of testing every prompt change against a dataset is how OCBrain should validate SkillCreator-generated skills.
Recommended action: Heavy Inspiration. Add automated evaluation suite for skills using DeepEval metrics pattern.

wandb/wandb + SwanHubX/SwanLab — Priority: 6/10
Purpose: ML experiment tracking, visualization, collaboration.
Valuable for OCBrain: Training run tracking for Phase 7 fine-tuning pipeline. SwanLab is the open-source self-hostable alternative.
Recommended action: Partial Adoption. SwanLab for self-hosted ML experiment tracking (Phase 7).

DOMAIN G: Structured Data & Analytics
duckdb/duckdb — ★28k · Priority: 9/10
Purpose: In-process analytical SQL database. Reads Parquet, CSV, JSON natively. Vectorized execution.
Architecture:

Columnar storage, vectorized execution engine
No separate server process — runs embedded like SQLite
Direct Parquet/CSV/JSON read without import
Excellent compression ratios

Key insight for OCBrain: DuckDB is the ideal analytics layer for OCBrain's memory and event data. Currently all analytics (memory stats, learning pipeline metrics, event analysis) require custom Python. DuckDB enables:

SELECT count(*) FROM read_json('.data/archive.jsonl') WHERE importance > 0.7
Analysis of EventStream WAL without loading into memory
Knowledge corpus statistics without iterating Python lists

Why OCBrain needs this: As the memory corpus grows, Python-level statistics become too slow. DuckDB adds zero infrastructure and can query existing JSONL/SQLite files directly.
Recommended action: Partial Adoption. Add DuckDB as an analytics layer in Phase 4.4.3 Cognitive Analytics Platform. Zero infrastructure cost.

ClickHouse/ClickHouse — ★41k · Priority: 7/10
Purpose: High-performance columnar OLAP database. 100x faster than row-oriented DBs for analytics.
Architecture:

MergeTree table engine family
Real-time inserts with deferred background merges
Materialized views for precomputed aggregations
Vector similarity search (experimental)

Key insight for OCBrain: ClickHouse is the right backend for OCBrain's event telemetry at scale (Phase 4.4.5 Cognitive Observability Layer). EventStream WAL → ClickHouse enables real-time query: "How many tool calls in the last hour? What are the top failure reasons this week?"
When OCBrain needs it: Phase 4.4+ when event volume exceeds SQLite analytical capability.
Recommended action: Future Integration Candidate (Phase 4.5+). Self-hosted ClickHouse for event analytics.

postgres/postgres — Priority: 6/10
Purpose: The production relational database standard.
Key insight for OCBrain: When OCBrain moves to distributed state (Phase 7), PostgreSQL + pgvector is the natural upgrade from SQLite. All current SQLite tables have equivalent PostgreSQL schemas.
Recommended action: Future Integration Candidate (Phase 7). Migration path from SQLite → PostgreSQL for production deployment.

risingwavelabs/risingwave — Priority: 7/10
Purpose: Streaming SQL database. Write SQL, get materialized views that update in real-time.
Key insight for OCBrain: RisingWave could power OCBrain's "live memory views" — materialized aggregations that update as new memories are written. "Show me the top 10 topics OCBrain learned about this week" would be a standing SQL query, not a batch job.
Recommended action: Adopt Concepts Only (Phase 6+). Streaming SQL pattern for live analytics.

apache/kafka + redpanda-data/redpanda + apache/pulsar + AutoMQ/automq — Priority: 5/10 each
Purpose: Distributed event streaming.
Key insight for OCBrain: OCBrain's current EventStream is single-process WAL. For multi-agent deployments (Phase 5+), a distributed event bus becomes necessary. Redpanda is Kafka-compatible with zero ZooKeeper and lower latency.
Recommended action: Future Integration Candidate (Phase 5). Replace EventStream WAL with Redpanda for distributed deployments. Adopt Concepts Only now.

apache/flink + apache/spark + apache/beam — Priority: 4/10 each
Purpose: Distributed stream/batch processing.
Key insight for OCBrain: Too heavyweight for current OCBrain scale. Relevant for Phase 7.5 Data Platform Evolution.
Recommended action: Not Recommended until Phase 7.5.

DOMAIN H: LLM Serving & Inference
vllm-project/vllm — ★50k · Priority: 9/10
Purpose: Fast LLM inference. PagedAttention for 24x more efficient KV cache utilization.
Architecture:

PagedAttention: KV cache stored in non-contiguous pages (like OS virtual memory)
Continuous batching: new requests inserted mid-inference
Tensor parallelism across GPUs
OpenAI-compatible API

Key insight for OCBrain: vLLM is the production inference upgrade from Ollama when OCBrain deploys to GPU servers. PagedAttention enables 4-24x higher throughput for the same GPU memory.
Recommended action: Direct Integration Candidate (Phase 5). Add vLLM as a provider option in config/providers.json. Zero code change needed — it's OpenAI-compatible.

sgl-project/sglang — ★12k · Priority: 8/10
Purpose: Structured generation language for LLMs. 5x faster than vLLM for constrained decoding.
Architecture:

RadixAttention: KV cache sharing across requests with common prefixes
Constraint-guided generation: grammar-constrained, JSON-constrained output
Frontend language (SGLang) for complex prompting patterns

Key insight for OCBrain: When OCBrain generates structured outputs (skill specs, workflow DAG JSON), sglang's constraint-guided generation guarantees valid JSON without post-processing/retry loops. RadixAttention's prefix sharing is ideal for OCBrain's system prompt (same prefix for all workers).
Recommended action: Direct Integration Candidate (Phase 5.5). Replace JSON output retry loops with sglang constraint-guided generation.

ollama/ollama — ★110k · Priority: 10/10 (already integrated)
Purpose: Local LLM serving. Already OCBrain's primary inference backend.
Key insight: The providers.json integration completed in the audit lets users switch between Ollama models without code changes. Continue using Ollama as the primary local provider.
Recommended action: Keep. Already integrated. Add model auto-download when recommended hardware profile selects a model not yet pulled.

mudler/LocalAI — Priority: 8/10 (already in study)
Purpose: Local inference with 36+ backends, gRPC, MCP server.
Recommended action: Keep as secondary provider. Already in provider_mesh.

ggml-org/llama.cpp — Priority: 7/10
Purpose: LLM inference in pure C++. Runs on CPU without GPU.
Valuable for OCBrain: CPU-only fallback for users without GPU. Already used by Ollama and LocalAI internally.
Recommended action: Indirect Integration (via Ollama/LocalAI).

DOMAIN I: AI Coding Assistants
affaan-m/ECC — Already covered in Domain A (Priority 10/10)
cline/cline — ★40k · Priority: 8/10
Purpose: Claude Code-native autonomous coding agent. File editing, terminal, browser control.
Key concepts:

SYSTEM_PROMPT hierarchical: project → user → defaults
Tool use: read/write file, bash, browser, MCP
Plan/Act mode: plan first (user approves), then execute
Checkpoint before each action

Valuable for OCBrain: Plan/Act mode = OCBrain's PlannerWorker + ReActWorker sequence with explicit human checkpoint. Cline's checkpoint-per-action is more granular than OCBrain's per-workflow HITL.
Recommended action: Adopt Concepts Only. Per-action checkpoint pattern.

Aider-AI/aider — ★30k · Priority: 7/10
Purpose: AI pair programmer for existing codebases. Git-native (commits changes automatically).
Key concepts: Repo map (tree-sitter based code graph for context). Architect+Editor mode (two-model: cheap model edits, expensive model architects). Edit formats (SEARCH/REPLACE blocks).
Valuable for OCBrain: Repo map concept = OCBrain's CoderWorker needs a code graph for context (validated by graphify in our build). Architect+Editor two-model pattern = OCBrain's PlannerWorker → CoderWorker handoff.
Recommended action: Adopt Concepts Only. Repo map for CoderWorker context (repomix integration already planned).

continuedev/continue — ★25k · Priority: 7/10
Purpose: Open-source GitHub Copilot alternative. IDE plugin with custom context and actions.
Key concepts: Context providers (file, web, codebase, issue, docs). Actions = slash commands in IDE. Indexing via Chroma.
Valuable for OCBrain: Context provider pattern = OCBrain's PipelineMiddleware context injection but for IDE context. Standardized context API that any provider can implement.
Recommended action: Adopt Concepts Only. Context provider abstraction.

google-gemini/gemini-cli — ★70k · Priority: 8/10
Purpose: Gemini AI terminal interface. GEMINI.md context file, file I/O, tool use.
Already studied: GEMINI.md → OCBRAIN.md pattern already adopted in Phase 1.
Recommended action: Keep. Already integrated pattern.

TabbyML/tabby — ★24k · Priority: 6/10
Purpose: Self-hosted AI coding assistant server. Code completion + chat.
Key concepts: Repository context indexing. Self-hosted, no cloud required.
Valuable for OCBrain: Code completion API pattern for CoderWorker. Self-hosted approach validates local-first strategy.
Recommended action: Partial Adoption. Code completion endpoint for CoderWorker.

DOMAIN J: Data Lineage & Metadata
MarquezProject/marquez — Priority: 7/10
Purpose: Open-source data lineage metadata service. OpenLineage standard.
Architecture: Dataset + Job + Run DAG. OpenLineage events for lineage tracking.
Key insight for OCBrain: Every OCBrain memory write is like a dataset with lineage — it came from a source, was processed by workers, and produced outputs. Marquez's lineage model maps perfectly to OCBrain's L4 archive + EventStream provenance.
Recommended action: Adopt Concepts Only. OpenLineage event model for memory provenance.

open-metadata/OpenMetadata — Priority: 7/10
Purpose: Unified metadata platform. Data catalog, lineage, data quality, governance.
Key insight for OCBrain: OpenMetadata's data catalog concept = OCBrain's SkillRegistry but for knowledge assets. Every document, skill, and workflow should be discoverable in a catalog.
Recommended action: Heavy Inspiration. Knowledge catalog pattern for Phase 4.6.5 Knowledge Exploration Workspace.

datahub-project/datahub — Priority: 6/10
Purpose: LinkedIn's open-source data catalog. Entity-relationship metadata model.
Key insight: DataHub's entity model (Dataset, DataFlow, DataJob) maps to OCBrain (MemoryEntry, Workflow, WorkflowNode).
Recommended action: Adopt Concepts Only. Entity metadata model.

amundsen-io/amundsen — Priority: 5/10
Recommended action: Not Recommended. Superseded by OpenMetadata and DataHub.

DOMAIN K: Logging & Structured Logging
uber-go/zap, rs/zerolog, phuslu/log, natefinch/lumberjack — Priority: 3/10 for OCBrain
Purpose: High-performance structured loggers for Go.
Key insight for OCBrain: OCBrain is Python-based. These are Go loggers. However, their design principles apply:

Structured logging (JSON fields, not string formatting): OCBrain already uses structlog/logging, add explicit fields
Log levels per component: different verbosity per module
Zero-allocation logging: premature optimization for OCBrain's scale

OCBrain application: Add structured logging with fields to core/observability/tracer.py. Each log line should include {trace_id, worker_type, worker_id, skill_name, duration_ms}.
Recommended action: Adopt Concepts Only. Structured logging fields pattern.

DOMAIN L: MCP Ecosystem
modelcontextprotocol/servers — ★30k · Priority: 10/10
Purpose: Reference MCP server implementations. Filesystem, GitHub, databases, web search.
Key insight for OCBrain: OCBrain's SkillRegistry already auto-exposes skills as MCP servers. The reference implementations define the canonical patterns for tool definitions, error handling, and resource management.
Recommended action: Adopt Concepts Only. Already integrated. Use as reference for MCP server quality.

upstash/context7 — Priority: 8/10
Purpose: MCP server that provides up-to-date library docs to LLMs. use context7 in any prompt.
Key insight for OCBrain: Context7's "library documentation as MCP resource" pattern is how OCBrain's knowledge base should be exposed. "What does OCBrain's GovernanceKernel do?" should resolve via MCP.
Recommended action: Adopt Concepts Only. Knowledge base as MCP resource pattern.

microsoft/playwright-mcp — Priority: 7/10
Purpose: Browser automation as MCP tools.
Key insight for OCBrain: BrowserWorker (Phase 4.4.1) should be exposed as an MCP server with tools: browser_navigate, browser_click, browser_extract_text, browser_screenshot.
Recommended action: Direct Integration Candidate (Phase 4.4.1). BrowserWorker = Playwright MCP server.

github/github-mcp-server — Priority: 7/10
Purpose: GitHub as MCP tools. Issues, PRs, code, repos, actions.
Valuable for OCBrain: CoderWorker needs GitHub access for PR review, issue analysis, code browsing.
Recommended action: Direct Integration Candidate. Add GitHub MCP as default capability for CoderWorker.

DOMAIN M: Infrastructure & IaC
hashicorp/terraform + opentofu/opentofu — Priority: 5/10
Purpose: Infrastructure as code. Declarative resource management.
Key insight for OCBrain: OCBrain's deployment (Phase 7.7) needs IaC. OpenTofu (OSS fork) is preferred over Terraform (BSL license change).
Recommended action: Future Integration Candidate (Phase 7.7). OpenTofu for OCBrain deployment automation.

pulumi/pulumi — Priority: 6/10
Purpose: IaC in Python/TypeScript/Go/C#. OCBrain's infrastructure defined in Python.
Recommended action: Future Integration Candidate (Phase 7.7). Pulumi preferred over Terraform for OCBrain (Python-native).

ansible/ansible — Priority: 5/10
Purpose: Agentless configuration management.
Valuable for OCBrain: Configuration management for multi-node OCBrain deployments.
Recommended action: Adopt Concepts Only. Deployment automation.

prometheus/prometheus + grafana/grafana — Priority: 8/10
Purpose: Metrics collection + visualization. Industry standard.
Key insight for OCBrain: OCBrain's ObservabilityFramework should export Prometheus metrics. Grafana provides dashboards for memory utilization, inference latency, skill success rates.
Recommended action: Direct Integration Candidate (Phase 4.4.5). Add Prometheus exporter to ObservabilityFramework.

VictoriaMetrics/VictoriaMetrics — Priority: 7/10
Purpose: Prometheus-compatible time-series DB. Better compression, lower resource usage.
Recommended action: Partial Adoption. VictoriaMetrics as self-hosted metrics backend alternative to Prometheus.

netdata/netdata — Priority: 5/10
Purpose: Real-time performance monitoring.
Recommended action: Adopt Concepts Only. System-level metrics alongside OCBrain metrics.

DOMAIN N: Security Testing (Largely Irrelevant)
wfuzz, commix, ffuf, w3af, zaproxy, nikto, feroxbuster, dirsearch, gobuster, wpscan, sqlmap, nuclei, hetty
Purpose: Web application security testing tools.
Key insight for OCBrain: These are offensive security tools. OCBrain should not include offensive security capabilities in its core. However, AgentShield (from ECC) is the correct model for OCBrain's security analysis — it audits agent configurations, not web applications.
What IS relevant:

Security testing patterns for OCBrain's own API endpoints
Input sanitization validation (fuzzing concept)
nuclei's template-driven scanning pattern = OCBrain skill quality validation templates

Recommended action: Not Recommended (tools). Adopt Concepts Only (security testing patterns for OCBrain's own surfaces).

DOMAIN O: Data Quality & ETL
great-expectations/great_expectations — Priority: 7/10
Purpose: Data quality validation. Expectations (assertions) on datasets.
Key insight for OCBrain: Every memory write should have expectations: "content length > 50", "importance in [0,1]", "source is not empty". This is the MemoryGovernor concept but with declarative expectations rather than hardcoded checks.
Recommended action: Adopt Concepts Only. Declarative expectations pattern for memory quality validation.

dbt-labs/dbt-core — Priority: 6/10
Purpose: SQL-based data transformation with tests, documentation, lineage.
Key insight for OCBrain: dbt's model-as-transformation concept (each SQL file is a named, versioned, tested transformation) maps to OCBrain's skill concept. Skills = transformations on inputs → outputs, with tests and versioning.
Recommended action: Adopt Concepts Only. Model-as-transformation pattern.

airbytehq/airbyte — Priority: 7/10
Purpose: Open-source ETL. 300+ connectors for data ingestion.
Key insight for OCBrain: OCBrain's knowledge acquisition pipeline (Phase 4.4.2) needs connectors for: GitHub repos, Notion docs, Confluence, Slack, email, PDFs, YouTube transcripts. Airbyte's connector model (each connector is a Docker image with a standardized catalog/sync interface) is the right pattern.
Recommended action: Adopt Concepts Only. Connector abstraction for knowledge sources.

dlt-hub/dlt — Priority: 7/10
Purpose: Lightweight Python ETL library. Zero-infrastructure data loading.
Key insight for OCBrain: dlt is "airbyte in Python, without Docker". OCBrain's knowledge acquisition can use dlt's source → destination pipeline without running Airbyte infrastructure. Zero external dependency.
Recommended action: Partial Adoption (Phase 4.4.2). dlt for knowledge source connectors.

DOMAIN P: Agent Evaluation & RAG
deepset-ai/haystack — Priority: 7/10
Purpose: Production RAG + agent framework. Pipelines, evaluation, tracing.
Key concepts: Pipeline DAG for document processing. Evaluation harness with component-level metrics.
Valuable for OCBrain: Component-level evaluation (not just end-to-end): how well does each pipeline stage perform? Isolating failures to specific pipeline components.
Recommended action: Adopt Concepts Only. Component-level pipeline evaluation pattern.

infiniflow/ragflow — Priority: 7/10
Purpose: RAG engine with deep document understanding. Layout-aware chunking.
Key insight: Layout-aware chunking (recognizes tables, figures, headers) produces better chunks than naive text splitting. OCBrain's WebCleaner and knowledge acquisition chunking would benefit.
Recommended action: Adopt Concepts Only. Layout-aware chunking for Phase 4.4.2.

Mintplex-Labs/anything-llm — Priority: 6/10
Purpose: All-in-one LLM app. Document RAG, agent mode, multi-user, self-hosted.
Valuable for OCBrain: Multi-user workspace isolation pattern. Each user's knowledge is scoped to their workspace.
Recommended action: Adopt Concepts Only. Multi-tenant workspace isolation for Phase 6.

DOMAIN Q: ML Training Frameworks
hpcaitech/ColossalAI — Priority: 7/10
Purpose: Distributed deep learning with tensor/pipeline/data parallelism.
Valuable for OCBrain: Phase 7 fine-tuning at scale (>7B models) requires ColossalAI-style parallelism.
Recommended action: Future Integration Candidate (Phase 7.2).

karpathy/nanoGPT + karpathy/minGPT — Priority: 5/10
Purpose: Minimal GPT implementations for education.
Valuable for OCBrain: Understanding transformer internals for custom model development in Phase 7.
Recommended action: Adopt Concepts Only. Educational reference.

tatsu-lab/stanford_alpaca — Priority: 5/10
Purpose: Instruction fine-tuning of LLaMA. Self-instruct data generation.
Key insight: Self-instruct (using GPT-4 to generate training data) is exactly what OCBrain's distiller.py should do — use a capable model to generate instruction→response pairs from raw knowledge.
Recommended action: Adopt Concepts Only. Self-instruct data generation for Phase 7.

DOMAIN R: Chat UIs & Wrappers (Mostly Irrelevant)
chatbox, chatgpt-web, NextChat, chatbot-ui, chatgpt-web-share, etc.
Purpose: Chat interface wrappers around OpenAI/Claude APIs.
Key insight for OCBrain: These have no architectural value for OCBrain. They're thin UI wrappers. OCBrain's interface/web/ already has a more sophisticated design.
Recommended action: Not Recommended.

DOMAIN S: Workflow Automation
activepieces/activepieces — Priority: 6/10 (already in study)
Purpose: Open-source workflow automation. 280+ pieces-as-MCP.
Already validated: Skills-as-MCP pattern. Continue applying this.

PipedreamHQ/pipedream — Priority: 5/10
Purpose: Cloud workflow automation with 1000+ integrations.
Key insight for OCBrain: Event-trigger → workflow pattern. Every external event (email received, GitHub PR opened, Slack message) can trigger an OCBrain workflow.
Recommended action: Adopt Concepts Only. Event-trigger workflow pattern.

DOMAIN T: Optimization (Numerical)
google/or-tools, ERGO-Code/HiGHS, osqp/osqp, embotech/ecos
Purpose: Mathematical optimization solvers.
Key insight for OCBrain: The future "Executive Cortex" (v4.4) needs multi-objective optimization for resource allocation, task scheduling, and model selection. or-tools provides constraint satisfaction and scheduling.
Recommended action: Future Integration Candidate (Phase 4.4). or-tools for cognitive resource optimization in Executive Cortex.

DOMAIN U: Other Relevant Repositories
toeverything/AFFiNE — Priority: 6/10
Purpose: Open-source Notion alternative. Docs + whiteboard + database.
Key insight for OCBrain: AFFiNE's block-based document model is how OCBrain's knowledge exploration workspace (v4.6.5) should represent knowledge — blocks with type-safe properties, not raw Markdown.
Recommended action: Adopt Concepts Only. Block-based knowledge representation.

juputer/notebook — Priority: 4/10
Purpose: Interactive computing. Already widely known.
Key insight for OCBrain: Jupyter-style notebooks for OCBrain's knowledge exploration workspace — run queries, visualize memory graphs, explore learning pipeline outputs.
Recommended action: Adopt Concepts Only. Notebook interface for knowledge exploration.

mastra-ai/mastra (already covered), ag2ai/ag2 (AutoGen successor) — Priority: 7/10
ag2 (AutoGen v2): Multi-agent framework with code execution, tool use, human-in-the-loop. Two-agent conversation pattern (user proxy + assistant). Group chat for multi-agent coordination.
Key insight for OCBrain: Two-agent conversation (critic-generator) is exactly OCBrain's ReflectionWorker. Group chat = ParallelOrchestrator with multiple workers all seeing the same conversation.
Recommended action: Adopt Concepts Only. Group chat multi-agent pattern.

SECTION 3 — CROSS-REPOSITORY PATTERN EXTRACTION
Pattern 1: Graph-Vector Hybrid Memory (★ 9/10 prevalence)
Evidence: cognee, neo4j-graphrag, FalkorDB, OpenSPG/KAG, DB-GPT, mem0, AutoFlow
Why it keeps appearing: Pure vector search (cosine similarity) fails at:

Multi-hop reasoning ("who built the system that Alice designed based on Bob's research?")
Structural queries ("list all entities of type 'database' connected to 'OCBrain'")
Contradiction detection ("system was designed in 2024 AND 2025 — which is correct?")

Graph adds structure; vector adds semantic fuzzy matching. Neither alone is sufficient.
Maturity: High. KAG's mutual-indexing is peer-reviewed (ACM WWW 2025). Cognee has 1M+ users.
OCBrain implication: The current graph and L2 semantic layers must be fused. Every L2 entry needs a graph node; every graph node needs an L2 entry. Queries should traverse both simultaneously.

Pattern 2: Durable Execution with Event Sourcing (★ 10/10 prevalence)
Evidence: Temporal, Prefect, Dagster, Kestra, AutoGPT, OpenHands (already in OCBrain)
Why it keeps appearing: Agent workflows break at the worst times. Distributed systems fail. Processes crash. Stateless retry loses context.
Maturity: Extremely high. Temporal is $5B. Apache Airflow is 10+ years old.
OCBrain implication: OCBrain's EventStream (already event-sourced) needs to become the basis for durable workflow execution, not just observability. Workflows should be resumable from last EventStream checkpoint after a crash.

Pattern 3: Instinct/Skill Two-Stage Learning (★ 7/10 prevalence)
Evidence: ECC (instinct→skill), MetaGPT (SOP evolution), hermes-agent (trajectory→skill), mem0 (extraction→memory)
Why it keeps appearing: Raw observations → generalizations requires aggregation. Direct extraction of generalizations is noisy. Two stages (accumulate instincts → cluster to skills) produces more robust patterns.
Maturity: Moderate. ECC's implementation is production-proven (215k stars). Academic validation sparse but intuitive.
OCBrain implication: SkillCreator should produce instincts (raw session patterns) → then cluster into skills via Evolve command (like ECC). Currently SkillCreator goes directly to skill files.

Pattern 4: Active Memory Improvement (★ 8/10 prevalence)
Evidence: cognee memify, mem0 auto-update on contradiction, OpenSPG entity alignment, ECC continuous-learning-v2
Why it keeps appearing: Static memory degrades over time (stale facts, contradictions accumulate, infrequently accessed nodes clog retrieval). Active maintenance produces self-improving memory.
Maturity: High in cognee (production). Theoretical in many others.
OCBrain implication: MemoryConsolidator should not just evict+promote but actively: prune stale nodes, strengthen high-access connections, derive new facts from existing facts, detect and resolve contradictions.

Pattern 5: Semantic Caching (★ 7/10 prevalence)
Evidence: GPTCache, semantic retrieval plugins, Qdrant's payload caching, Temporal memoization
Why it keeps appearing: LLM calls are expensive. Similar queries should reuse cached results.
OCBrain implication: Replace PromptCache (hash-based) with semantic similarity cache. "What is OCBrain?" and "Explain OCBrain to me" should hit the same cache entry.

Pattern 6: Capability-Based Model Routing (★ 8/10 prevalence)
Evidence: ECC (/model-route), MetaGPT (role → model assignment), mastra (task-aware routing), sglang (structured output routing)
Why it keeps appearing: Different tasks need different models. Planning needs reasoning models; coding needs code models; summarization needs context-window models.
OCBrain implication: ModelRouter should route by capability ("coding", "reasoning", "summarization") not just by maturity stage. Configuration: {"coding": "deepseek-coder", "reasoning": "o1", "general": "mistral"}.

Pattern 7: Knowledge Provenance as First-Class Citizen (★ 9/10 prevalence)
Evidence: Marquez (OpenLineage), DataHub, OpenMetadata, dagster (asset lineage), Temporal (event history), dbt (model lineage)
Why it keeps appearing: In a system that learns continuously, knowing WHERE knowledge came from is critical for:

Auditing incorrect answers
Removing knowledge from tainted sources
Trust scoring queries

OCBrain implication: Every memory entry needs traceable provenance: source_url, extraction_method, trust_score, worker_id, workflow_id, timestamp. L4 archive is write-once provenance but not queryable. Need a queryable provenance index.

Pattern 8: Declarative Skill/Tool Definitions (★ 10/10 prevalence)
Evidence: ECC (SKILL.md), Activepieces (pieces-as-MCP), n8n (node manifests), Temporal (workflow definitions), Kestra (YAML workflows)
Why it keeps appearing: Code-only skill definitions are hard to discover, compose, and share. Declarative definitions enable tooling.
OCBrain implication: Already implemented (.skill.md files). Extend with: JSON Schema for input validation, example pairs for auto-testing, performance benchmarks, and cost estimates.

Pattern 9: Evaluation as Infrastructure (★ 9/10 prevalence)
Evidence: DeepEval, wandb, langfuse, agbenchmark, ECC (997 internal tests), keploy
Why it keeps appearing: LLM systems degrade silently. Without evaluation infrastructure, improvements are guesses and regressions go undetected.
OCBrain implication: Every skill should have a test dataset (input → expected output). Every new version should run against this dataset before promotion to L3 procedural memory.

Pattern 10: MCP as Universal Integration Layer (★ 9/10 prevalence)
Evidence: ECC, Activepieces, n8n, Langflow, Dify, context7, playwright-mcp, github-mcp-server
Why it keeps appearing: MCP provides a standardized way for any AI system to access any tool. The ecosystem is consolidating around it.
OCBrain implication: Every OCBrain capability should eventually be MCP-exposed. Already started with SkillRegistry. Extend to: MemoryVault, GraphEngine, WorkflowEngine, EventStream query, ObservabilityFramework.

Pattern 11: Multi-Agent Role Specialization (★ 9/10 prevalence)
Evidence: MetaGPT (PM/Architect/Engineer/QA), CrewAI, ag2, ECC (64 specialized agents), mastra
Why it keeps appearing: Generalist agents underperform specialists on complex tasks. Role constraints improve output quality by narrowing the solution space.
OCBrain implication: Worker types (ReAct, Planner, Coder, Evaluator) are correct. Add role-specific system prompts with explicit capability constraints. ECC's approach of 64 domain-specialized agents (go-reviewer, python-reviewer, mle-reviewer, etc.) is the right direction for OCBrain's SkillRegistry.

Pattern 12: Rust as the Performance Kernel (★ 7/10 prevalence)
Evidence: ECC (ecc2/ Rust prototype), LaurentMazare/tch-rs, tracel-ai/burn, ggml-org/llama.cpp, candle (HuggingFace), rustformers/llm
Why it keeps appearing: Python event loops and GIL are fundamental scalability constraints. Rust enables zero-cost abstractions, memory safety, and true parallelism.
OCBrain implication: v5.0 Rust Cognitive Kernel is validated by the ecosystem. Specifically: the EventStream WAL, StateStore persistence actor, and BM25 index are strong Rust candidates. ECC's ecc2/ shows this path is feasible with a Python→Rust gradual migration.

Pattern 13: Self-Improving Memory via Feedback Loops (★ 8/10 prevalence)
Evidence: cognee memify, mem0 contradiction resolution, ECC instinct evolution, hermes-agent Atropos RL
Why it keeps appearing: Static databases don't improve. Cognitive systems must improve their own knowledge.
OCBrain implication: Every successful task should update memory quality scores. Every unsuccessful task should flag involved memories for review. OCBrain's EvolutionGovernor should govern this feedback loop.

SECTION 4 — REVISED OCBRAIN TARGET ARCHITECTURE
4.1 Layer Architecture (Target: v4.9)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OCBrain v4.9 Cognitive Operating System                  │
│         Local-First · Governed · Event-Sourced · Self-Improving             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 0: GOVERNANCE & SECURITY                                             │
│  ├─ GovernanceKernel (recursion, steps, tokens, workers)                   │
│  ├─ HumanApprovalNode (HITL at workflow DAG nodes)                         │
│  ├─ GuardrailsNode (PII, content safety, prompt injection)                 │
│  ├─ AgentShield-style validation (provider configs, MCP tools)             │
│  └─ EvolutionGovernor (self-modification requires approval)                │
│                               ↓                                             │
│  LAYER 1: EVENT BACKBONE                                                    │
│  ├─ EventStream (immutable WAL, pub/sub, replay, checkpoints)              │
│  ├─ Durable Execution (workflow state survives restarts)                    │
│  ├─ Kafka/Redpanda integration point (Phase 5, distributed)                │
│  └─ ClickHouse export (event analytics, Phase 4.5)                         │
│                               ↓                                             │
│  LAYER 2: COGNITIVE ORCHESTRATION                                           │
│  ├─ OCBrainOrchestrator (classify → route → worker → memory → response)    │
│  ├─ WorkflowEngine (DAG, durable execution, partial re-run, HITL nodes)    │
│  ├─ ParallelOrchestrator (fan-out, fan-in, typed artifact flow)            │
│  └─ Executive Cortex (multi-objective optimization, resource allocation)   │
│                               ↓                                             │
│  LAYER 3: AGENT RUNTIME                                                     │
│  ├─ ReActWorker (tool loop, stopWhen, Agent Protocol)                      │
│  ├─ PlannerWorker (decompose, schedule, validate dependencies)             │
│  ├─ ReflectionWorker (generate, critique, refine)                          │
│  ├─ CoderWorker (sandbox, repomix, git-native, Playwright MCP)             │
│  ├─ EvaluatorWorker (pointwise, pairwise, DeepEval-inspired metrics)      │
│  ├─ BrowserWorker (Playwright MCP, Firecrawl, trust pipeline)             │
│  ├─ MemoryCuratorWorker (active memory improvement, memify-style)         │
│  └─ [Role-specialized workers added per Phase 4+ skills]                  │
│                               ↓                                             │
│  LAYER 4: KNOWLEDGE & MEMORY                                                │
│  ├─ L0 Working Memory (LRU, in-process, <1ms)                             │
│  ├─ L1 Episodic Memory (SQLite+FTS5, recency×importance×relevance)        │
│  ├─ L2 Semantic Memory (Qdrant/Chroma, sparse+dense, persistent)          │
│  ├─ L3 Procedural Memory (skills, workflows, instincts→skills)            │
│  ├─ L4 Immutable Archive (JSONL, write-once provenance)                   │
│  ├─ Graph Layer (FalkorDB at scale, mutual-indexed with L2)               │
│  └─ Memory Curator (memify-style: prune, strengthen, derive, align)       │
│                               ↓                                             │
│  LAYER 5: RETRIEVAL ENGINE                                                  │
│  ├─ Hybrid Retrieval (BM25+sparse+dense, RRF fusion)                      │
│  ├─ Graph Traversal (multi-hop, logical-form-guided, KAG-inspired)        │
│  ├─ Reranker (cross-encoder, improves precision after ANN recall)          │
│  ├─ Semantic Cache (GPTCache-inspired, similarity-based)                   │
│  └─ Query Expansion (HyDE, query reformulation)                            │
│                               ↓                                             │
│  LAYER 6: KNOWLEDGE ACQUISITION                                             │
│  ├─ Knowledge Pipeline (URL→fetch→parse→trust→chunk→embed→graph→memory)   │
│  ├─ Connector Library (dlt-inspired, Airbyte-compatible adapters)         │
│  ├─ Trust Manager (domain reputation, content quality, dedup)              │
│  ├─ Quarantine (low-trust holding, human review, promote/reject)          │
│  ├─ Entity Extractor (LLM-assisted, not just regex)                        │
│  └─ Knowledge Quality Validation (great-expectations inspired)             │
│                               ↓                                             │
│  LAYER 7: LEARNING PIPELINE                                                 │
│  ├─ Session Extractor (auto-extract facts at session end, mem0-inspired)   │
│  ├─ Instinct Collector (raw patterns from successful task trajectories)    │
│  ├─ Skill Evolver (cluster instincts → skills, ECC evolve-inspired)       │
│  ├─ Evaluation Harness (DeepEval-inspired per-skill test dataset)          │
│  ├─ Fine-tuning Pipeline (LoRA, DPO, GRPO, curriculum learning)           │
│  └─ RL Signal (online feedback from task outcomes)                         │
│                               ↓                                             │
│  LAYER 8: INFERENCE FABRIC                                                  │
│  ├─ Provider Mesh (providers.json, 11 providers + custom)                  │
│  ├─ Capability Router (task-type → model routing, not just maturity)      │
│  ├─ Semantic Cache (cached responses by query similarity)                  │
│  ├─ Ollama (local, primary, mistral/llama3/deepseek)                      │
│  ├─ vLLM (GPU server, PagedAttention, Phase 5)                             │
│  ├─ sglang (structured output generation, Phase 5.5)                       │
│  └─ Cloud providers (OpenAI, Anthropic, Gemini, Groq, Mistral, etc.)     │
│                               ↓                                             │
│  LAYER 9: OBSERVABILITY & TELEMETRY                                         │
│  ├─ Langfuse integration (LLM tracing: prompt, response, tokens, cost)     │
│  ├─ Prometheus metrics (exported from ObservabilityFramework)              │
│  ├─ Grafana dashboards (memory utilization, inference latency, skill ROI)  │
│  ├─ DuckDB analytics (inline query on JSONL/SQLite without infrastructure) │
│  └─ ClickHouse (event analytics at scale, Phase 4.5)                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
4.2 Key Architectural Changes from Current State
AreaCurrentTargetPriorityL2 persistenceIn-memory, lost on restartChroma → Qdrant, persistentHIGHGraph-vector fusionSeparate layersMutual-indexed, co-queriedHIGHMemory curationPassive evictionActive memify (prune/strengthen/derive)HIGHMulti-hop retrievalSingle-hop onlyLogical-form-guided graph traversalHIGHInstinct→SkillDirect to skillTwo-stage (instinct accumulate → evolve)MEDIUMDurable executionDies with processCheckpoint-resume from EventStreamHIGHLLM observabilitySpan-level onlyLangfuse prompt-level tracingHIGHModel routingMaturity-basedCapability-based (task → model)MEDIUMSemantic cacheHash-onlySimilarity-based (GPTCache-inspired)MEDIUMProvenanceL4 write-onlyQueryable provenance indexMEDIUM

SECTION 5 — ROADMAP REVISION
5.1 Source A: Original Implementation Plan (from PROJECT_INSTRUCTIONS.md and early sessions)
Phase 1: v4.1.x — Cognitive Foundation (COMPLETE)
Phase 2: v4.2.x — Worker Runtime (COMPLETE)
Phase 3: v4.3.x — Memory System (COMPLETE through v4.3.4; v4.3.5-v4.3.7 partially complete)
Phase 4: v4.4.x — Knowledge Acquisition + Execution Sandbox
Phase 5: v4.5.x — Distributed Compute
Phase 6: v4.6.x — Multimodal + Collaboration
Phase 7: v4.7.x — Controlled Evolution
5.2 Source B: Current Revised Roadmap (from session architecture research prompt)
v4.3.4    L4 Archive
v4.3.4.5  Memory Metadata & Provenance
v4.3.4.6  Knowledge Event Model
v4.3.5    Graph Memory Foundation
v4.3.5.1  GraphRAG Layer
v4.3.5.5  Event Backbone
v4.3.6    Memory Curator
v4.3.6.2  Knowledge Acquisition Layer
v4.3.6.3  Knowledge Quality & Validation Layer
v4.3.6.5  Knowledge Governance Layer
v4.3.7    Testing & Integration
v4.3.7.1  Documentation Infrastructure
v4.3.8    Cognitive Retrieval Engine
v4.4      Executive Cortex
v4.4.3    Cognitive Analytics Platform
v4.4.4    Agent Evaluation Framework
v4.4.5    Cognitive Observability Layer
v4.4.7    Workflow Engine
v4.4.8    Durable Workflow Runtime
v4.4.9    Event Intelligence Layer
v4.5      Agent Operating System
v4.5.5    Workflow Marketplace
v4.6      Autonomous Development Platform
v4.6.5    Knowledge Exploration Workspace
v4.6.7    Knowledge Warehouse
v4.7      MCP Native Ecosystem
v4.7.5    Data Platform Evolution
v4.8      Autonomous Learning Platform
v4.8.5    Infrastructure Automation Engine
v4.9      Cognitive Operating System
v5.0      Rust Cognitive Kernel
5.3 Source C: Newly Proposed Roadmap (from repository research)
From the research, the following additions/modifications are warranted:
Missing in A and B:

Instinct→Skill two-stage learning (ECC pattern)
Mutual indexing of graph nodes and L2 chunks (KAG pattern)
Semantic cache upgrade (GPTCache pattern)
Langfuse LLM tracing integration
Capability-based model routing
Active memory curation (memify pattern)
Per-skill evaluation datasets (DeepEval pattern)
Prometheus/Grafana observability
dlt knowledge connectors
Playwright MCP BrowserWorker
vLLM inference server

Premature in B:

v4.4 Executive Cortex (before basic knowledge acquisition works)
v4.4.7 Workflow Engine (already in Phase 1)
v4.6 Autonomous Development Platform (before learning pipeline matures)
v4.7 MCP Native Ecosystem (MCP already integrated; this step is vague)
v5.0 Rust Cognitive Kernel (valid but 3+ years out; plan but don't schedule yet)


5.4 Roadmap Difference Analysis
ComponentSource ASource BSource CFinal DecisionRationaleL4 Archive✅ Completev4.3.4Already doneKeepCompletedMemory ProvenanceNot specifiedv4.3.4.5NeededMerge into v4.3.5Part of graph foundationKnowledge Event ModelNot specifiedv4.3.4.6NeededMerge into event backboneNot standaloneGraph Memory FoundationPhase 3v4.3.5CriticalKeep — v4.3.5Core architectureGraphRAG LayerNot specifiedv4.3.5.1CriticalRename → Mutual IndexingMore precise scopeEvent BackboneNot specifiedv4.3.5.5ImportantRename → Durable ExecutionBetter captures valueMemory Curator WorkerPhase 3 §7.1v4.3.6CriticalKeep — v4.3.6Missing canonical workerActive MemifyNot specifiedImplicitCriticalAdd to v4.3.6Core improvement patternKnowledge AcquisitionPhase 4v4.3.6.2CriticalMove to v4.3.6.2Source B sequence correctKnowledge QualityNot specifiedv4.3.6.3CriticalKeepgreat_expectations patternKnowledge GovernanceNot specifiedv4.3.6.5ImportantKeepEvolutionGovernor extensionTesting & IntegrationPhase 3 v4.3.7v4.3.7CriticalKeepQuality gateDocumentation InfraNot specifiedv4.3.7.1CompleteMark CompleteDone this sessionCognitive Retrieval EngineNot specifiedv4.3.8CriticalKeep — add KAG patternsMulti-hop retrievalSemantic CacheNot specifiedNot in BNeededAdd v4.3.8.1GPTCache patternInstinct→Skill LearningNot specifiedNot in BCriticalAdd v4.3.9ECC pattern, foundationalPer-Skill Eval DatasetsNot specifiedNot in BNeededAdd v4.3.9.1DeepEval patternLLM ObservabilityNot specifiedNot in BCriticalAdd v4.3.9.2Langfuse integrationCapability Model RoutingNot in ANot in BNeededAdd v4.3.9.3ECC model-route patternExecutive CortexNot in Av4.4ValidMove to v4.5Too early before learning worksCognitive AnalyticsNot in Av4.4.3ValidKeep v4.4.3DuckDB pattern, early valueAgent Evaluation FrameworkNot in Av4.4.4CriticalKeep v4.4.4Before autonomous learningCognitive ObservabilityPhase 1 partialv4.4.5CriticalKeep v4.4.5Prometheus/Grafana/LangfuseWorkflow EnginePhase 1 donev4.4.7DuplicateRemoveAlready completeDurable Workflow RuntimeNot in Av4.4.8CriticalKeep v4.4.8Temporal patternEvent IntelligenceNot in Av4.4.9ValidKeep v4.4.9ClickHouse + streaming SQLBrowserWorkerPhase 4.4.1Not in BCriticalAdd v4.4.1Playwright MCPConnectors LibraryNot in A or BSource CNeededAdd v4.4.2.1dlt/Airbyte patternvLLM IntegrationPhase 5Not in BImportantAdd v4.5.1PagedAttention upgradesglang Structured OutputNot in A or BNot in BNeededAdd v4.5.2Constraint-guided generationAgent Operating SystemPhase 5 conceptv4.5ValidRename → Distributed Agent RuntimeMore preciseWorkflow MarketplaceNot in Av4.5.5ValidKeepSkill/workflow sharingAutonomous Dev PlatformPhase 6 conceptv4.6ValidKeep v4.6Post-learning maturityKnowledge WorkspaceNot in Av4.6.5ValidKeepDuckDB/AFFiNE-inspiredKnowledge WarehouseNot in Av4.6.7ValidKeepClickHouse/DB-GPT patternMCP Native EcosystemNot in Av4.7VagueSplit into v4.7 skillsEach MCP integration is specificData Platform EvolutionNot in Av4.7.5ValidKeepPostgreSQL + pgvector migrationAutonomous LearningPhase 7 conceptv4.8CriticalKeep v4.8RL + DPO + GRPOSelf-Instruct Data GenNot in A or BSource CNeededAdd v4.8.1Stanford Alpaca patternInfrastructure AutomationNot in Av4.8.5ValidKeepPulumi/OpenTofuCognitive Operating Systemv4.9v4.9Goal stateKeepTarget architectureRust Cognitive Kernelv5.0v5.0ValidKeep v5.0ECC ecc2/ validates

5.5 Final Unified Roadmap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT PHASE: v4.3.5 — Complete Memory Foundation
(paused pending this architecture study)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 3 COMPLETION (v4.3.x) — Memory System
────────────────────────────────────────────────────────────────────────────
v4.3.5   Graph Memory Foundation
         - GraphEngine: WAL, find_contradictions, stats, lazy singleton ✅
         - Mutual indexing: every L2 entry → graph node pointer (NEW)
         - Entity extraction: upgrade from regex to LLM-assisted
         - Memory provenance: source_url, worker_id, workflow_id on every entry

v4.3.5.1 GraphRAG Layer (Mutual Indexing)
         - Every graph node stores L2 entry_id reference
         - Every L2 entry stores graph node_id reference
         - Unified query: graph traversal enriched by vector context
         - KAG-inspired logical-form query path for multi-hop questions

v4.3.6   Memory Curator Worker (§7.1 canonical worker)
         - MemoryCuratorWorker as CognitiveWorker subclass (currently MISSING)
         - Wraps MemoryConsolidator with Agent Protocol interface
         - Active memify pipeline: prune stale, strengthen high-access, derive facts
         - Contradiction resolution: when graph finds contradictions, curator resolves

v4.3.6.2 Knowledge Acquisition Layer
         - Full pipeline: URL→trust→chunk→embed→graph→memory
         - dlt-inspired connector abstraction for multiple source types
         - Layout-aware chunking (ragflow-inspired, handles tables/figures)
         - Quarantine: low-trust → review queue → promote/reject

v4.3.6.3 Knowledge Quality & Validation Layer
         - Declarative expectations on memory entries (great_expectations-inspired)
         - Quality scoring per memory entry (not just trust for web content)
         - Deduplication: semantic dedup on write path (mem0-inspired)
         - Contradiction detection integrated into write path

v4.3.6.5 Knowledge Governance Layer
         - Source allowlist/blocklist management
         - Acquisition rate limits per domain
         - Knowledge expiry: TTL-based invalidation for time-sensitive facts
         - EvolutionGovernor integration: knowledge changes require approval above threshold

v4.3.7   Testing & Integration (in progress)
         - GraphEngine functional tests ✅ (complete this session)
         - MemoryCuratorWorker tests (pending)
         - Knowledge acquisition integration tests
         - Contradiction detection tests
         - Mutual indexing round-trip tests

v4.3.7.1 Documentation Infrastructure ✅ COMPLETE (this session)

v4.3.8   Cognitive Retrieval Engine
         - Multi-hop retrieval: logical-form-guided graph traversal (KAG-inspired)
         - Reranker: cross-encoder step after ANN recall (improves precision)
         - HyDE: generate hypothetical document, embed it, use for retrieval
         - Semantic cache: similarity-based (replace hash-only cache)
         - Unified query API: one call, all layers, fused ranking

v4.3.9   Instinct → Skill Two-Stage Learning (ECC-inspired)
         - Session end: auto-extract facts and patterns (mem0-inspired)
         - Instinct storage: low-confidence patterns accumulate in L3
         - Evolve command: cluster instincts into validated skills
         - Per-skill evaluation dataset: input/output pairs for regression testing
         - LLM tracing: Langfuse integration for prompt-level observability
         - Capability routing: task-type → model mapping (not just maturity)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 (v4.4.x) — Knowledge Infrastructure & Tooling
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v4.4.1   BrowserWorker (Playwright MCP)
         - playwright-mcp as BrowserWorker backend
         - Trust pipeline for browser-extracted content
         - Sandboxed execution with governance limits
         - Screenshot → LLM-described for non-text pages

v4.4.1.1 Execution Sandbox (Task Runner)
         - Isolated subprocess for code execution (n8n Task Runner pattern)
         - Security: import whitelist, network restriction, memory limits
         - CoderWorker sandbox integration

v4.4.2   Knowledge Acquisition Pipeline v2
         - Connector library (dlt): GitHub, Notion, Confluence, Slack, YouTube, PDF, RSS
         - Scheduled acquisition (Prefect-inspired DAG scheduling)
         - Incremental sync: only process new/changed content (cognee-inspired)
         - Source tracking: each connector reports what was acquired when

v4.4.2.1 SkillCreator (hermes-agent pattern)
         - Autonomous .skill.md authoring from successful sessions
         - Uses instinct system (v4.3.9) as foundation
         - Requires EvaluatorWorker approval before L3 write

v4.4.3   Cognitive Analytics Platform
         - DuckDB embedded analytics (zero infrastructure)
         - Queryable memory corpus: `SELECT * FROM memories WHERE importance > 0.8`
         - EventStream analytics: failure rates, latency distributions, skill ROI
         - Knowledge corpus statistics: topic distribution, freshness, coverage

v4.4.4   Agent Evaluation Framework
         - Per-skill test datasets (input → expected output)
         - DeepEval-inspired metrics: correctness, faithfulness, relevance
         - Automated regression testing on skill promotion
         - A/B evaluation: compare skill versions before promotion

v4.4.5   Cognitive Observability Layer
         - Langfuse integration: prompt-level LLM tracing
         - Prometheus metrics export from ObservabilityFramework
         - Grafana dashboards: memory health, inference latency, skill success
         - Alert rules: memory utilization >80%, inference error rate >5%

v4.4.8   Durable Workflow Runtime
         - Checkpoint/resume from EventStream WAL on process restart
         - Long-horizon tasks: workflows can wait days for HITL approval
         - Workflow versioning: in-flight workflows not broken by deployment
         - Saga/compensation: undo steps on workflow failure (Temporal-inspired)

v4.4.9   Event Intelligence Layer
         - ClickHouse export for high-volume event analytics
         - Streaming SQL patterns (RisingWave-inspired) for live aggregations
         - Event replay for debugging and simulation
         - Pattern detection: recurring failure modes identified automatically

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 (v4.5.x) — Distributed Agent Runtime
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v4.5.1   vLLM Inference Integration
         - Add vLLM as high-performance GPU inference provider
         - PagedAttention enables 4-24x higher throughput vs Ollama at scale
         - Zero code change: vLLM is OpenAI-compatible

v4.5.2   SGLang Structured Output
         - Constraint-guided generation for skill JSON outputs
         - Eliminate JSON parse+retry loops
         - RadixAttention for system prompt prefix sharing

v4.5.3   Persistent L2 Semantic Memory
         - Replace in-memory L2SemanticMemory with Chroma (step 1)
         - Migration path to Qdrant for scale (step 2)
         - BM25+sparse+dense (SPLADE) hybrid replacing current BM25+cosine

v4.5.4   exo P2P Cluster
         - Ring topology for distributed inference across OCBrain nodes
         - Auto-discovery: no manual config
         - DeepSeek-V3.1 across cluster: 37B active/671B total

v4.5.5   Distributed EventStream
         - Redpanda as distributed event backbone (Kafka-compatible, no ZooKeeper)
         - Multi-node OCBrain instances share event bus
         - Event sourcing for distributed workflow coordination

v4.5.6   Workflow Marketplace
         - Published workflow templates (DAG JSON)
         - Skill bundles: domain-specific skill packages
         - Community contributions via GitHub

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 6 (v4.6.x) — Autonomous Development Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v4.6.1   Voice Interface (LocalAI realtime)
v4.6.2   Multimodal Workers (image, audio, document understanding)
v4.6.3   Executive Cortex
         - Multi-objective optimization for resource allocation
         - or-tools for constraint satisfaction
         - Autonomous task scheduling and prioritization
v4.6.5   Knowledge Exploration Workspace
         - Jupyter-style interactive queries on memory corpus
         - DuckDB-powered analytics UI
         - Graph visualization for knowledge graph exploration
         - AFFiNE-inspired block-based knowledge representation
v4.6.7   Knowledge Warehouse
         - PostgreSQL + pgvector migration path
         - NL→SQL for knowledge queries (DB-GPT-inspired)
         - Data lineage: full provenance for every knowledge item

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 7 (v4.7.x) — MCP Ecosystem + Data Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v4.7.1   GitHub MCP Integration (CoderWorker PR/issue access)
v4.7.2   Context7-style Knowledge MCP (OCBrain docs as MCP resource)
v4.7.3   Memory MCP (expose all memory layers via MCP tools)
v4.7.4   Workflow MCP (trigger workflows from any MCP client)
v4.7.5   Data Platform Evolution
         - PostgreSQL + pgvector for production deployment
         - VictoriaMetrics or ClickHouse for metrics
         - OpenTofu/Pulumi for infrastructure automation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 8 (v4.8.x) — Autonomous Learning Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v4.8.1   Self-Instruct Data Generation
         - Use capable model to generate instruction→response pairs from knowledge
         - Stanford Alpaca / self-instruct pattern
v4.8.2   Trajectory Dataset Builder
         - All successful sessions → training data (existing, complete v4.8 goal)
v4.8.3   LoRA Fine-tuning Pipeline
         - Curriculum learning (order pairs by difficulty)
         - DPO/GRPO alongside SFT
         - ColossalAI for multi-GPU (>7B models)
v4.8.4   Online RL Signal
         - Task outcomes → immediate memory quality updates
         - Failed tasks → flag involved memories for review
v4.8.5   Safe Self-Improvement
         - sim → validate → human-approve → deploy
         - Rollback-safe: checkpoint before every evolution
v4.8.6   Infrastructure Automation (Pulumi/OpenTofu)
v4.8.7   Benchmark Suite
         - agbenchmark + DeepEval metrics + task-specific evals

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v4.9 — COGNITIVE OPERATING SYSTEM (Target State)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All layers complete. OCBrain is:
- Self-learning (automatic fact extraction, instinct→skill evolution)
- Self-improving (RL feedback, LoRA fine-tuning, active memory curation)
- Self-evolving (autonomous skill creation, validated by evaluation harness)
- Local-first (Ollama/vLLM/exo, zero mandatory cloud)
- Provider-independent (11 providers, capability routing)
- Scalable (Qdrant, Redpanda, ClickHouse, PostgreSQL)
- Observable (Langfuse, Prometheus, Grafana, DuckDB)
- Governed (GovernanceKernel, AgentShield, EvolutionGovernor)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v5.0 — RUST COGNITIVE KERNEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- EventStream WAL in Rust (zero-copy, no GIL)
- BM25 index and HNSW search in Rust
- StateStore persistence actor in Rust
- Python wrapper layer for user-facing APIs
- HuggingFace Candle or Burn for local model inference
- Validated by: ECC ecc2/ prototype, candle, burn, tract

5.6 Dependency Validation
PhasePrerequisitesSystems that depend on itIf delayedIf too earlyv4.3.5 GraphRAGL4 Archive (done), GraphEngine (done)v4.3.8 retrieval, v4.3.6 curatorMulti-hop retrieval failsNo riskv4.3.6 Curatorv4.3.5 mutual indexingKnowledge quality, v4.3.8Memory degrades silentlyCan't curate without graphv4.3.6.2 Knowledge AcquisitionTrust pipeline (exists), chunker (exists)v4.4.1 BrowserWorkerNo external knowledge—v4.3.8 Retrieval Enginev4.3.5 mutual index, v4.3.6 curatorPhase 4 workers, v4.8 learningPoor retrieval qualityRetrieval without memory is uselessv4.3.9 Instinct→Skillv4.3.8 retrieval, EvaluatorWorkerPhase 7 fine-tuningNo self-learningSkills before learning pipeline = manual onlyv4.4.4 Eval FrameworkSkills exist (v4.3.9)v4.8 autonomous learningRegressions undetected—v4.4.8 Durable ExecutionWorkflowEngine (done), EventStream (done)v4.8 autonomous learningLong tasks dieAdded complexity before neededv4.5.3 Persistent L2L2 architecture (done)v4.5.5 distributedMemory lost on restartEarlier is finev5.0 Rust KernelAll Python components stableFuture performancePython bottlenecksPremature rewrite

SECTION 6 — PRIORITY MATRIX
Immediate (Complete before Phase 4)
CapabilitySource PatternEffortImpactMemoryCuratorWorker class§7.1 canonicalLowHIGH — required by specGraphEngine testsv4.3.7LowHIGH — quality gateL2 persistence (Chroma)Chroma, QdrantMediumCRITICAL — data lost on restartMutual graph-L2 indexingKAG, cogneeMediumHIGH — unlocks multi-hopActive memify pipelinecognee memifyMediumHIGH — self-improving memoryLangfuse LLM tracingLangfuseLowHIGH — invisible without it
Short-Term (Phase 4)
CapabilitySource PatternEffortImpactInstinct→Skill two-stageECC, cogneeMediumCRITICAL — foundational for learningBrowserWorker (Playwright MCP)playwright-mcpMediumHIGHPer-skill eval datasetsDeepEvalMediumHIGH — prevents regressionsDuckDB analyticsDuckDBLowMEDIUM — immediate query valuePrometheus metrics exportPrometheusLowMEDIUMCapability model routingECC, MetaGPTLowHIGHSemantic cacheGPTCacheLowMEDIUMKAG-style multi-hop retrievalKAG, OpenSPGHighHIGH
Mid-Term (Phase 5)
CapabilitySource PatternEffortImpactChroma → Qdrant (persistent L2)QdrantMediumHIGHvLLM inference providervLLMLowHIGH for GPU deploymentssglang structured outputsglangMediumMEDIUMRedpanda distributed eventsRedpandaHighHIGH for multi-nodeexo P2P clusterexoMediumHIGH for distributed inferencedlt connector librarydltMediumHIGH
Long-Term (Phase 6-7)
CapabilitySource PatternEffortImpactFalkorDB graph upgradeFalkorDBHighHIGH at scaleClickHouse event analyticsClickHouseHighHIGH at scalePostgreSQL + pgvector migrationpostgres, pgvectorHighHIGH for productionKnowledge Exploration WorkspaceDuckDB, AFFiNEHighMEDIUMExecutive Cortexor-tools, DagsterVery HighHIGH for autonomous opsVictoriaMetrics metrics backendVictoriaMetricsMediumMEDIUM
Experimental (Phase 8-9)
CapabilitySource PatternEffortImpactOnline RL signalhermes/AtroposVery HighCRITICAL for autonomySelf-instruct data generationStanford AlpacaHighHIGHDPO/GRPO trainingrasbt, NeMoVery HighHIGHTemporal durable workflow serverTemporalVery HighHIGH for v4.9ColossalAI multi-GPU trainingColossalAIVery HighHIGH for >7BRisingWave streaming SQLRisingWaveHighMEDIUMRust EventStream kernelECC ecc2/, candleExtremeCRITICAL for v5.0

SECTION 7 — ADOPTION RECOMMENDATIONS
Direct Integration Candidates
RepoIntegration PointWhylangfuse/langfusecore/provider_mesh.pyLLM tracing is missing; existing hooks make it low-effortplaywright-mcpBrowserWorker (Phase 4.4.1)Ready-made Playwright-as-MCP; zero reimplementationdlt-hub/dltKnowledge acquisition connectorsLightweight, Python-native, 300+ sources, zero infravllm-project/vllmproviders.json + provider_mesh.pyOpenAI-compatible, zero code change neededchroma-core/chromaL2SemanticMemory backendAlready in requirements.txt, minimal migration
Heavy Inspiration (implement patterns, not code)
RepoOCBrain ApplicationKey Patterntopoteretes/cogneeMemoryCuratorWorker active memifyPrune/strengthen/derive/alignaffaan-m/ECCSkillCreator, instinct systemTwo-stage instinct→skill learningOpenSPG/KAGCognitive Retrieval EngineMutual indexing, logical-form queriestemporalio/temporalWorkflowEngine durable executionCheckpoint/resume from EventStreamconfident-ai/deepevalEvaluation frameworkPer-skill test datasets, metric librarymem0ai/mem0Session end auto-extractionAutomatic fact extraction, semantic dedupOpenMetadataKnowledge catalogDiscoverable knowledge assetsgreat-expectationsMemory quality validationDeclarative expectations
Adopt Concepts Only
RepoConceptMetaGPTRole specialization, typed artifact flowCrewAIHierarchical delegation patterndagsterAsset materialization lineageduckdb/duckdbEmbedded analytics (adopt directly, but lightweight)ClickHouseTime-series event storage (adopt when volume warrants)kestraYAML workflow definitionsprefectDecorator-based workflow authoringgorillaTool documentation quality standardsMarquezOpenLineage event modelGPTCacheSemantic similarity cachingragflowLayout-aware chunkingneo4j-graphragGraphRAG retrieval patternsairflowScheduler design for knowledge acquisitionag2Two-agent critic-generator pattern
Partial Adoption
RepoWhat to Adoptfacebookresearch/faissANN index as L2 alternative to in-memory scanchroma-core/chromaAs intermediate L2 backend before QdrantSwanHubX/SwanLabSelf-hosted ML experiment trackingVictoriaMetricsMetrics backend alternativeairbytehq/airbyteConnector model design (not the Docker-heavy runtime)
Not Recommended
RepoReasonSecurity tools (wfuzz, ffuf, nikto, zaproxy, sqlmap, etc.)Different domain; OCBrain is cognitive OS, not security scannerSimple chat UIs (chatgpt-web, chatbox, NextChat, etc.)Thin wrappers, zero architectural valuebabayagiSuperseded; OCBrain already exceeds this architectureLAION/Open-AssistantTraining data source, not architectural modellivewire/phoenix_live_viewPHP/Elixir specific; not applicablebootstrap-table, react-spectrum, mantineFrontend component libraries; OCBrain UI uses vanilla HTMLChanzhaoyu/chatgpt-web, ChatGPTNextWeb/NextChat, chatpireThin wrapperskeployAPI testing tool; not cognitive system relevantCLIUtils/CLI11C++ CLI library; OCBrain is Pythongoss-org/gossGo system testing; not applicablewordpress/wpscanWordPress scanner; not applicable

SECTION 8 — RISK ANALYSIS
Risk 1: L2 Persistence Migration (Chroma)
Benefits: Memory survives restarts; semantic search persists; 10x faster than cold-rebuild BM25 index
Complexity: Medium — Chroma API differs from current in-memory L2SemanticMemory
Migration cost: Medium — need to migrate existing L2 data on first startup
Maintenance burden: Low — Chroma is stable and well-maintained
Performance impact: +50ms for Chroma vs in-memory, but eliminates cold-start rebuild
Failure modes: Chroma file corruption (mitigate: backups); API breaking changes (pin version)
Verdict: Low risk, high reward. Do immediately.

Risk 2: Graph-Vector Mutual Indexing
Benefits: Multi-hop retrieval; richer context; contradiction-aware queries
Complexity: High — requires schema changes to both GraphEngine and L2SemanticMemory
Migration cost: High — existing entries need back-fill
Maintenance burden: Medium — keeping two indexes in sync requires careful write ordering
Performance impact: +5-15ms per write (dual index); improved retrieval precision
Failure modes: Sync drift (mitigate: atomic write with rollback); node_id not found in L2 (mitigate: graceful fallback)
Verdict: Medium risk, critical reward. Phase v4.3.5.1.

Risk 3: Langfuse Integration
Benefits: Prompt-level visibility, cost tracking, regression detection
Complexity: Low — Python SDK, minimal code changes
Migration cost: None — additive
Maintenance burden: Low — external service or self-hosted
Performance impact: +5-10ms per LLM call (HTTP to Langfuse server)
Failure modes: Langfuse server down (mitigate: failsafe wrapper that catches errors)
Verdict: Very low risk, high reward. Do immediately.

Risk 4: Instinct→Skill Two-Stage Learning
Benefits: More robust skill learning; filters noise; enables confidence-based promotion
Complexity: Medium — adds instinct storage layer, cluster algorithm, evolve command
Migration cost: Low — existing skills not affected
Maintenance burden: Medium — cluster quality depends on embedding quality
Performance impact: None to production path; slight latency added to session-end hook
Failure modes: Poor clustering (mitigate: human review before evolve); instinct bloat (mitigate: TTL + prune command like ECC)
Verdict: Medium risk, critical reward. Phase v4.3.9.

Risk 5: Durable Workflow Execution (Temporal patterns)
Benefits: Long-horizon tasks; workflows survive restarts; HITL can block for days
Complexity: High — deterministic code constraints, new programming model
Migration cost: High — existing workflows need rewriting to be deterministic
Maintenance burden: High — Temporal server (if full integration) is significant infra
Performance impact: Higher per-workflow overhead; better for long-running, worse for fast batch
Failure modes: Non-deterministic workflow code causes replay failures (mitigate: code review, strict conventions)
Mitigation strategy: Implement checkpoint/resume on top of existing EventStream WAL first (simpler, 80% of value). Full Temporal integration only at Phase 4.8+.
Verdict: High risk if done wrong; implement EventStream-based checkpoint first (v4.4.8), defer Temporal server to v4.8+.

Risk 6: FalkorDB at Scale
Benefits: 6x faster graph operations than current SQLite at large scale
Complexity: High — requires Redis-compatible server, new client library
Migration cost: Very High — full graph migration from SQLite to FalkorDB
Maintenance burden: High — Redis + FalkorDB module running alongside OCBrain
Performance impact: Dramatically better at 500K+ edges; marginal below
Failure modes: FalkorDB server crash (mitigate: Redis persistence modes); query compatibility
Verdict: Only needed at Phase 5-6 when graph exceeds ~500K edges. Low priority now.

Risk 7: Active Memify (Memory Improvement)
Benefits: Self-improving memory; stale facts pruned; high-value connections strengthened
Complexity: Medium — adds LLM calls to consolidation process
Migration cost: None — additive
Maintenance burden: Medium — derived facts may be incorrect; pruning may delete valid entries
Performance impact: MemoryConsolidator runs slower (LLM calls); memory quality improves
Failure modes: Incorrect fact derivation (mitigate: low confidence score + review); over-pruning (mitigate: importance threshold before delete, log pruned entries to L4)
Verdict: Medium risk. Add confidence thresholds and log all deletions to L4 (immutable record). Phase v4.3.6.

SECTION 9 — FINAL EXECUTIVE RECOMMENDATION
9.1 Optimal Path from v4.3.5 to v5.0
The critical insight from 200+ repositories: OCBrain's architecture is fundamentally sound. The 5-layer memory, event sourcing, governance-first pattern are validated by the best production systems. The gaps are specific and addressable:

Memory persistence — L2 lost on restart is the highest-impact bug. Fix immediately with Chroma.
Graph-vector fusion — Graph and vector are disjoint. Mutual indexing is the unlock for multi-hop reasoning.
Active memory improvement — Passive consolidation is insufficient. Adopt cognee's memify pattern.
LLM observability — Currently blind to what the LLM is doing. Langfuse fills this with one integration.
Instinct→Skill — ECC's two-stage learning is more robust than direct skill creation. Add immediately.

The optimal path is not about adding features but about making the existing layers genuinely work together:

Graph speaks to L2 (mutual indexing)
L2 persists across restarts (Chroma)
Memory actively improves itself (memify)
Skills are learned, not just written (instinct evolution)
System knows what LLMs are doing (Langfuse)

Only once these foundations work should Phase 4 knowledge acquisition, Phase 5 distributed infrastructure, and Phase 7 autonomous learning be attempted. Building on a shaky foundation compounds technical debt.

9.2 Final Target Architecture
The target architecture for v4.9 is:
A local-first, governed, event-sourced cognitive operating system with:

Graph-vector fused memory (mutual-indexed, multi-hop retrieval, actively curated)
Durable workflow execution (checkpoint/resume, saga compensation)
Two-stage instinct→skill learning pipeline (ECC-inspired, automatically improving)
Capability-based model routing (task-type → optimal model)
Full-spectrum observability (Langfuse + Prometheus + Grafana + DuckDB)
MCP-native exposure of all capabilities
Provider independence (11+ providers, graceful fallback, semantic cache)

At v5.0: A Rust cognitive kernel wrapping a stable Python API layer, enabling true parallelism without GIL constraints, at significantly lower latency.

9.3 Highest Architectural Value Repositories
Ranked by concrete OCBrain applicability:

ECC (affaan-m/ECC) — Instinct→Skill two-stage learning, cross-harness isolation, AgentShield security model, Rust control-plane validation. Most directly applicable.
topoteretes/cognee — Active memory improvement (memify), graph-vector fusion, incremental learning. Most aligned with OCBrain's memory vision.
temporalio/temporal — Durable execution pattern. Critical for Phase 4.4.8+.
OpenSPG/KAG — Multi-hop retrieval via mutual indexing, 40% better than RAG. Critical for v4.3.8 retrieval engine.
mem0ai/mem0 — Automatic fact extraction at session end, semantic dedup. Fills the "remember automatically" gap.
confident-ai/deepeval — Per-skill evaluation datasets. Critical for Phase 4.4.4 eval framework.
langfuse/langfuse — LLM-level observability. The lowest-effort, highest-impact immediate integration.
qdrant/qdrant — Production-grade persistent vector search. The endgame for L2 persistence.
vllm-project/vllm — 24x throughput improvement for GPU inference. Phase 5.1, zero code change.
dlt-hub/dlt — Lightweight Python connectors for knowledge acquisition. Phase 4.4.2.


9.4 Repositories to Ignore Despite Popularity
RepoStarsWhy IgnoreSecurity testing tools (ffuf, nikto, sqlmap, etc.)10k-30k eachDifferent domain entirelybabyagi20kOCBrain already exceeds this architecturechatgpt-web, NextChat, chatbox30-50k eachThin UI wrappers, zero architectural valueLAION/Open-Assistant37kTraining data source, not architecture modellivewire, phoenix_live_view20-30k eachPHP/Elixir specificwxt-dev/wxt14kBrowser extension framework, not applicablestanford_alpaca (as architecture)30kData generation only; superseded by better methodsapache/spark, flink, beam35k+ eachToo heavyweight for OCBrain's data scale

9.5 Critical Path to Final Architecture
v4.3.5 ──▶ v4.3.5.1 ──▶ v4.3.6 ──▶ v4.3.6.2 ──▶ v4.3.6.3 ──▶ v4.3.7 ──▶ v4.3.8
(Graph)    (Mutual     (Curator)   (Acquisition) (Quality)    (Tests)   (Retrieval)
            Index)
                                                                               │
                                                                               ▼
v4.3.9 ─────────────────────────────────────────────────────────────────────────
(Instinct→Skill + Langfuse + Semantic Cache + Capability Routing + Eval Datasets)
│
▼
v4.4.x ──── v4.4.1 (BrowserWorker) ──── v4.4.3 (Analytics) ──── v4.4.4 (Eval)
              │                                                        │
              ▼                                                        ▼
           v4.4.5 (Observability) ──── v4.4.8 (Durable Execution) ── v4.4.9
│
▼
v4.5.x ──── v4.5.1 (vLLM) ──── v4.5.3 (Persistent L2) ──── v4.5.5 (Distributed)
│
▼
v4.6.x ──── Knowledge Warehouse ──── Executive Cortex ──── Multimodal
│
▼
v4.7.x ──── MCP Ecosystem ──── Data Platform (PostgreSQL/pgvector)
│
▼
v4.8.x ──── Autonomous Learning (LoRA + DPO + RL) ──── Benchmark Suite
│
▼
v4.9 ───── Cognitive Operating System (All layers stable, self-improving)
│
▼
v5.0 ───── Rust Cognitive Kernel (EventStream + StateStore + BM25 in Rust)
The critical path bottleneck: Everything in Phase 4+ depends on v4.3.5.1 (mutual indexing) and v4.3.9 (instinct→skill). If these are not done well, the rest of the roadmap builds on sand. Invest in getting these right before accelerating to Phase 4.

Research Complete — No code generated, no modifications made.
Ready for implementation plan revision and approval before resuming at v4.3.5.
