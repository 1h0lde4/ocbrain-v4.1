"""
core/memory/retrieval/graphrag/intent.py — Session 5.5 GraphRAG Foundation.

IntentAnalyzer is the pipeline's first named stage (research guidance #1:
Query -> Intent Analysis -> Memory Retrieval -> Graph Expansion -> ...).

Session 5.5 deliberately does NOT implement query classification, rewriting,
or any "speculative AI heuristic" (explicit instruction in the session
brief). PassthroughIntentAnalyzer is a genuine no-op: it exists so the
STAGE is named, pluggable, and present in the pipeline from day one,
without inventing NLU work nobody asked for yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class QueryIntent:
    """Structured output of the intent-analysis stage.

    raw_query:    exactly what the caller passed in, untouched.
    search_query: what gets handed to the memory-retrieval stage. Equal to
                  raw_query for PassthroughIntentAnalyzer; a future
                  analyzer could rewrite/expand it (query expansion, HyDE
                  -- already a noted future direction in
                  OCBRAIN_FUTURE_ARCHITECTURE.md v4.3.8) without changing
                  this dataclass's shape or any downstream pipeline stage.
    metadata:     free-form extension point for a future analyzer's own
                  structured findings (detected entities, query type,
                  confidence). Unused today, deliberately.
    """
    raw_query: str
    search_query: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntentAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, query: str) -> QueryIntent: ...


class PassthroughIntentAnalyzer(IntentAnalyzer):
    """Default: search_query == raw_query, empty metadata.

    The pipeline STAGE exists; its logic doesn't, yet -- deliberately, per
    this session's explicit instruction not to implement speculative AI
    heuristics. Swap in a real analyzer later without touching
    GraphRAGPipeline itself.
    """

    async def analyze(self, query: str) -> QueryIntent:
        return QueryIntent(raw_query=query, search_query=query)
