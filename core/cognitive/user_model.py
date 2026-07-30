"""
core/cognitive/user_model.py — K4.2.7 User Cognitive Model.

Architecture:
    OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md §3 (User
    Cognitive Model), §11 (Event Integration), §15 (K4.2.7 roadmap entry).

Packet:
    Packet 05 — K4.2.7: User Cognitive Model.

Scope:
    K4.2 §3: a read-mostly projection over L1 raw preference/pattern
    signals and L3 promoted preference/pattern records, synthesizing
    stable traits (expertise, terminology preferences, preferred
    abstraction level, communication style, preferred output formats,
    recurring objectives, behavioral patterns) from what memory has
    accumulated -- not a new memory system, and not raw memory itself.
    K4.2 §3's privacy invariants: fully inspectable and deletable by the
    user at any time; governed by the same write-path as everything else
    (no separate, ungoverned "personalization" backdoor); excluded from
    any future cross-instance advisory mechanism.

Boundary (K4 §1, Evolution Directive):
    This module does NOT implement a write path of its own. K4.2 §3:
    "gated identically to Intent Ontology promotion" -- writes go
    through core.cognitive.learning.validation_gate() directly, exactly
    as Skill and Intent Ontology already do (Packet 04, K4.2.6), using
    ContentDomain.USER_MODEL, LearningTier.LEARNING/ADAPTATION/EVOLUTION,
    and (for Evolution-tier promotions) `is_new_entry` and
    `procedure_name` -- both added to validation_gate() by this packet
    (see core/cognitive/learning.py's docstring for the exact contract).
    This module provides no convenience wrapper around validation_gate()
    for writing: Packet 04 deliberately did not build per-domain wrapper
    functions for Skill or Intent Ontology either (see
    k4_2_6_completion_report.md), and adding one here -- rather than
    having callers use the shared gate directly -- would be exactly the
    kind of "another promotion gate" duplication both K4.2 §3 and this
    project's engineering standards reject. The only things this module
    owns are: (1) the read-mostly projection assembly, and (2) the two
    privacy-invariant operations (inspect, delete) that are genuinely
    specific to this content domain -- Skill/Intent Ontology have no
    analogous "privacy invariants" in their own scope.

    This module also does not wire the projection into Intent
    Interpretation or Goal Formation. K4.2 §3 describes that as the
    architecture's eventual intent ("Consulted read-only during Intent
    Interpretation and Goal Formation"), but that integration is not
    named in this packet's own scope, and `core.cognitive.planner`
    already carries a `HintSource.USER_MODEL` constant (pre-existing,
    from Packets 01-03, currently unused) anticipating exactly this
    future wiring -- this packet does not touch planner.py or intent.py
    at all. Whichever future packet performs that integration has a
    stable, tested projection function and a pre-existing hint-source
    constant to build on; it is not this packet's job to perform the
    wiring itself, mirroring how Packet 04 built the shared gate without
    itself wiring in a Skill Runtime or Intent Ontology storage system.

Namespace/procedure_name convention (K4.2 §3: "procedure_name scoped to
a user_model:* namespace" -- illustrative, concretized here since no
formal schema exists elsewhere):
    Each of the seven projection fields corresponds to exactly one
    procedure_name: "user_model:expertise", "user_model:
    terminology_preferences", "user_model:preferred_abstraction_level",
    "user_model:communication_style", "user_model:
    preferred_output_formats", "user_model:recurring_objectives",
    "user_model:behavioral_patterns". A caller writes to one of these via
    validation_gate(content_domain=ContentDomain.USER_MODEL,
    procedure_name=<one of the above>, ...). For the two per-key fields
    (expertise, terminology_preferences -- naturally keyed: expertise is
    per-domain, terminology_preferences is per-concept), the caller also
    supplies `metadata={"model_key": "<domain-or-concept-name>"}`; the
    entry's own `content` is the value (e.g. procedure_name=
    "user_model:expertise", metadata={"model_key": "python"}, content=
    "intermediate"). For the three list-shaped fields (preferred_
    output_formats, recurring_objectives, behavioral_patterns), each
    entry's `content` is one accumulated item. For the two scalar fields
    (preferred_abstraction_level, communication_style), the single most
    recently updated matching entry's `content` is the value.

Design decisions flagged as implementation judgment (K4.2 §3's fields are
illustrative, not a formal schema; the following concretize it):
    - Assembly precedence: L3 (promoted, cleared validation_gate()'s
      held-out-improvement + contradiction + governance checks) always
      takes precedence over L1 (raw, routine Learning-tier signals) for
      the same procedure_name/model_key -- confirmed truth beats an
      unvetted signal. Within a layer, the most recently updated
      (`updated_at`) matching entry wins for scalar fields; list fields
      accumulate and deduplicate by content across both layers.
    - Caching: K4.2 §3 says the projection may be "cached with a short
      TTL, purely as a performance measure" -- explicitly optional,
      naming no TTL value, cache size, or invalidation-on-write policy.
      This module deliberately does not build a cache: no TTL/eviction
      policy is specified anywhere, and inventing one would be exactly
      the kind of speculative, uncited implementation detail this
      project's standards reject. `assemble_user_cognitive_model` is a
      pure function of current memory state (no hidden state of its
      own), which is what makes it "cacheable" in the first place --
      any future caller that wants a TTL cache can wrap this function
      without needing to change it.
    - "Excluded from any future cross-instance advisory mechanism": no
      such mechanism exists anywhere in this codebase today (confirmed
      by repository-wide search), so this cannot be a runtime check
      against a real system. It is instead verified structurally: no
      code anywhere in core/ couples "user_model" data to anything
      "cross_instance"-named (see test_user_model.py's
      TestArchitectureCompliance). `cross_instance_excluded_metadata()`
      below returns `{"cross_instance_excluded": True}` for a caller to
      merge into validation_gate()'s `metadata` argument as a forward-
      looking marker for whenever such a mechanism is eventually built --
      this module does not call validation_gate() itself (see Boundary
      above), so it cannot force this tag onto a write; it is offered as
      a convention, not enforced.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.memory.knowledge_entry import KnowledgeEntry
from core.memory.unified_memory import UnifiedMemory, get_unified_memory

# ─────────────────────────────────────────────────────────────────────────
# Namespace convention -- K4.2 §3
# ─────────────────────────────────────────────────────────────────────────

NAMESPACE_PREFIX = "user_model:"

EXPERTISE = "expertise"
TERMINOLOGY_PREFERENCES = "terminology_preferences"
PREFERRED_ABSTRACTION_LEVEL = "preferred_abstraction_level"
COMMUNICATION_STYLE = "communication_style"
PREFERRED_OUTPUT_FORMATS = "preferred_output_formats"
RECURRING_OBJECTIVES = "recurring_objectives"
BEHAVIORAL_PATTERNS = "behavioral_patterns"

# Per-key fields: multi-valued, keyed by metadata["model_key"].
DICT_FIELDS = frozenset({EXPERTISE, TERMINOLOGY_PREFERENCES})
# Cumulative list fields: one entry's content = one accumulated item.
LIST_FIELDS = frozenset({PREFERRED_OUTPUT_FORMATS, RECURRING_OBJECTIVES, BEHAVIORAL_PATTERNS})
# Single-valued fields: most recently updated matching entry wins.
SCALAR_FIELDS = frozenset({PREFERRED_ABSTRACTION_LEVEL, COMMUNICATION_STYLE})

ALL_MODEL_FIELDS = DICT_FIELDS | LIST_FIELDS | SCALAR_FIELDS


def procedure_name_for(model_field: str) -> str:
    """The procedure_name a validation_gate() caller should use for a
    given projection field, e.g. procedure_name_for(EXPERTISE) ==
    "user_model:expertise". Raises ValueError for an unrecognized field
    name, so a typo is caught at the call site rather than silently
    producing an entry no projection assembly will ever find."""
    if model_field not in ALL_MODEL_FIELDS:
        raise ValueError(f"Unknown User Cognitive Model field: {model_field!r}")
    return f"{NAMESPACE_PREFIX}{model_field}"


def _model_field_from_procedure_name(procedure_name: Optional[str]) -> Optional[str]:
    """The reverse of procedure_name_for: extracts the field name from an
    entry's procedure_name, or None if it isn't a recognized User
    Cognitive Model procedure_name (including None itself, or a
    "user_model:*" value this module doesn't recognize -- e.g. a future
    field added by a later packet without updating ALL_MODEL_FIELDS)."""
    if not procedure_name or not procedure_name.startswith(NAMESPACE_PREFIX):
        return None
    candidate = procedure_name[len(NAMESPACE_PREFIX):]
    return candidate if candidate in ALL_MODEL_FIELDS else None


def cross_instance_excluded_metadata() -> Dict[str, bool]:
    """K4.2 §3: User Cognitive Model entries must be "excluded... from
    any future cross-instance advisory mechanism." No such mechanism
    exists yet (see module docstring), so there is nothing to enforce
    against today -- this returns the forward-looking marker a caller
    should merge into validation_gate()'s `metadata` argument, so that
    whenever such a mechanism is built, it has a correct, pre-existing
    signal to check rather than needing every prior User Cognitive Model
    entry retroactively re-tagged. Offered as a convention: this module
    does not call validation_gate() itself (see Boundary above), so it
    cannot apply this tag on a caller's behalf.
    """
    return {"cross_instance_excluded": True}


# ─────────────────────────────────────────────────────────────────────────
# Projection data contract — K4.2 §3 (illustrative fields, concretized)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class UserCognitiveModelProjection:
    """K4.2 §3's illustrative field list, concretized. Not raw memory --
    a synthesized view assembled fresh from whatever L1/L3 entries exist
    at call time (see assemble_user_cognitive_model)."""
    expertise: Dict[str, str] = field(default_factory=dict)
    terminology_preferences: Dict[str, str] = field(default_factory=dict)
    preferred_abstraction_level: Optional[str] = None
    communication_style: Optional[str] = None
    preferred_output_formats: List[str] = field(default_factory=list)
    recurring_objectives: List[str] = field(default_factory=list)
    behavioral_patterns: List[str] = field(default_factory=list)

    # Provenance (Law 2 / K4.2 §10): which entries backed this projection.
    source_entry_ids: List[str] = field(default_factory=list)
    # Aggregate of the backing entries' own KnowledgeEntry.confidence,
    # surfaced so a consumer can gauge how much to trust the projection
    # as a whole. None when no backing entries exist yet.
    average_confidence: Optional[float] = None
    assembled_at: float = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────────
# Read-mostly projection assembly — K4.2 §3: "Reads: ungated, ordinary
# memory search (same as any context assembly)."
# ─────────────────────────────────────────────────────────────────────────

async def assemble_user_cognitive_model(
    *,
    memory: Optional[UnifiedMemory] = None,
    limit_per_layer: int = 200,
) -> UserCognitiveModelProjection:
    """Assemble the current User Cognitive Model projection from L1 raw
    preference/pattern signals and L3 promoted preference/pattern
    records (K4.2 §3).

    Pure with respect to its inputs: given the same underlying memory
    state, this always returns the same projection. No caching, no
    hidden state (see module docstring's "Design decisions" for why no
    cache is built here).

    Precedence when the same field/model_key appears in both layers: L3
    (promoted -- already cleared validation_gate()'s checks) always wins
    over L1 (raw, unvetted). Within a layer, the most recently updated
    entry wins for scalar fields. List fields accumulate distinct content
    across both layers, L1 first then L3, deduplicated.

    Args:
        memory: injected UnifiedMemory for testing; defaults to the
            shared singleton.
        limit_per_layer: max entries fetched per layer before filtering
            to user_model:* procedure_names. K4.2 §3 does not specify a
            bound; 200 is a conservative default a caller can override.

    Returns:
        UserCognitiveModelProjection. All fields are empty/None (not an
        error) when no User Cognitive Model entries exist yet -- this is
        the ordinary state for a new install with no accumulated signal.
    """
    memory = memory or get_unified_memory()
    projection = UserCognitiveModelProjection()
    confidences: List[float] = []

    def _apply(entry: KnowledgeEntry) -> None:
        model_field = _model_field_from_procedure_name(entry.procedure_name)
        if model_field is None:
            return
        if entry.entry_id not in projection.source_entry_ids:
            projection.source_entry_ids.append(entry.entry_id)
            confidences.append(entry.confidence)

        if model_field in DICT_FIELDS:
            model_key = (entry.metadata or {}).get("model_key")
            if model_key:
                getattr(projection, model_field)[model_key] = entry.content
        elif model_field in LIST_FIELDS:
            target = getattr(projection, model_field)
            if entry.content not in target:
                target.append(entry.content)
        else:  # SCALAR_FIELDS
            setattr(projection, model_field, entry.content)

    # L1 (raw) first, sorted oldest-to-newest so "last write wins" within
    # the layer is genuinely "most recently updated wins", not an
    # accident of whatever order get_layer() returns. L3 (promoted)
    # second, same sort, so any L3 entry always overwrites an L1 entry
    # for the same field/model_key -- confirmed truth beats raw signal.
    for layer in ("l1", "l3"):
        entries = await memory.get_layer(layer, limit=limit_per_layer)
        for entry in sorted(entries, key=lambda e: e.updated_at):
            _apply(entry)

    if confidences:
        projection.average_confidence = sum(confidences) / len(confidences)
    return projection


# ─────────────────────────────────────────────────────────────────────────
# Privacy invariants — K4.2 §3: "fully inspectable and deletable by the
# user at any time." Deletion reuses UnifiedMemory's existing, already-
# governed delete() (action_type="memory_delete") -- not a new deletion
# mechanism, and not a bypass of whatever governance already applies to
# deletion generally.
# ─────────────────────────────────────────────────────────────────────────

async def list_user_model_entries(
    *, memory: Optional[UnifiedMemory] = None, limit_per_layer: int = 200,
) -> List[KnowledgeEntry]:
    """Every L1/L3 entry currently backing the User Cognitive Model, for
    user inspection (K4.2 §3's "fully inspectable... at any time").
    Returns raw KnowledgeEntry records, not the synthesized projection --
    inspection means seeing what's actually stored, not a derived view.
    """
    memory = memory or get_unified_memory()
    result: List[KnowledgeEntry] = []
    for layer in ("l1", "l3"):
        entries = await memory.get_layer(layer, limit=limit_per_layer)
        result.extend(
            e for e in entries
            if _model_field_from_procedure_name(e.procedure_name) is not None
        )
    return result


async def delete_user_model_entry(
    entry_id: str,
    *,
    memory: Optional[UnifiedMemory] = None,
    reason: str = "user-requested deletion",
) -> bool:
    """Delete a single User Cognitive Model entry (K4.2 §3's "...and
    deletable... at any time"). Thin wrapper over UnifiedMemory.delete()
    -- reuses its existing governance evaluation (action_type=
    "memory_delete") and archival behavior rather than building a
    separate deletion path for this content domain specifically.
    """
    memory = memory or get_unified_memory()
    return await memory.delete(entry_id, reason=reason, worker_id="UserCognitiveModel")
