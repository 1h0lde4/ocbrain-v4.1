"""
core/memory/graph/entity_extractor.py — Session 5.25 Graph Index Foundation.

EntityExtractor defines HOW entities/edges get derived from a KnowledgeEntry
for graph indexing. Session 5.25 scope: define the interface and ship a
swappable stub -- LLM-based extraction is explicitly out of scope here.

extract() is async even though today's implementations are pure CPU-bound
regex work. This is deliberate: a future LLM-backed extractor will need to
be async (it makes a model call), and changing a sync interface to async
later is a breaking change for every caller. Paying that cost now, while
there is exactly one caller (GraphIndexer), is free; paying it later is not.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from core.memory.knowledge_entry import KnowledgeEntry


@dataclass
class ExtractedEntity:
    """One entity (and the edge that should connect it to the source
    KnowledgeEntry's graph node) derived from a KnowledgeEntry.

    name:       display name / node identity source (GraphIndexer derives
                the actual node_id from this — see graph_indexer.py).
    entity_type: graph node "type" column (e.g. "concept", "person", "org").
    relation:   edge label from the memory node to this entity
                (e.g. "mentions"). Kept separate from entity_type so a
                single extractor can emit different relations for
                different entities in the same entry.
    confidence: 0.0-1.0, extractor's own confidence. Not currently
                consumed by GraphIndexer (no confidence-gated filtering
                in this session) — carried through for a future policy.
    properties: arbitrary extra node properties, merged into the graph
                node's properties dict.
    """
    name: str
    entity_type: str = "concept"
    relation: str = "mentions"
    confidence: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


class EntityExtractor(ABC):
    """Derives entities from a KnowledgeEntry for graph indexing.

    Implementations must be swappable (regex / spaCy / LLM / hybrid) behind
    this one interface — GraphIndexer never branches on extractor type.
    """

    @abstractmethod
    async def extract(self, entry: "KnowledgeEntry") -> List[ExtractedEntity]: ...


class NullEntityExtractor(EntityExtractor):
    """Default extractor: always returns no entities.

    This is a deliberate choice, not a placeholder-by-omission: populating a
    production graph with unsupervised entity guesses is a data-quality
    decision, not a wiring decision. Session 5.25 delivers the pipe; what
    flows through it (Null vs. Regex vs. a future LLM extractor) is a
    one-line constructor-kwarg choice at the call site (see
    UnifiedMemory.register_graph_backend()), left to whoever wires it.
    """

    async def extract(self, entry: "KnowledgeEntry") -> List[ExtractedEntity]:
        return []


class RegexEntityExtractor(EntityExtractor):
    """Naive baseline: extracts capitalized multi-word phrases (a crude
    proper-noun heuristic) from entry.content. NOT NLP-grade — no POS
    tagging, no disambiguation, no coreference. Exists to prove the
    EntityExtractor -> GraphIndexer -> GraphBackend pipeline end-to-end
    with a real (if unsophisticated) implementation, and as a documented
    upgrade path (regex -> spaCy -> LLM -> hybrid, per the Session 5.25
    brief) without changing the interface.

    max_entities caps pathological blowup on long content; dedup is
    case-insensitive so "OCBrain" and "Ocbrain" collapse to one entity.
    """

    _PATTERN = re.compile(r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,3})\b")
    _STOPWORDS = {"the", "a", "an", "this", "that", "these", "those"}

    def __init__(self, max_entities: int = 5) -> None:
        self.max_entities = max_entities

    async def extract(self, entry: "KnowledgeEntry") -> List[ExtractedEntity]:
        if not entry.content:
            return []
        seen: Dict[str, str] = {}   # lowercased -> first-seen original casing
        for match in self._PATTERN.finditer(entry.content):
            phrase = match.group(0).strip()
            key = phrase.lower()
            if key in self._STOPWORDS or len(phrase) < 3:
                continue
            if key not in seen:
                seen[key] = phrase
            if len(seen) >= self.max_entities:
                break
        return [
            ExtractedEntity(name=name, entity_type="concept", relation="mentions")
            for name in seen.values()
        ]
