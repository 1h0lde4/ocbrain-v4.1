"""
core/capabilities/foundation/contracts.py — the semantic contracts.

These are the *definitions* of the three capabilities: identity, operations,
structured input/output, side-effect classification, contract version. They say
nothing about how any operation is implemented (no adapter, no model, no
provider, no parser) -- that is the point: an implementation can be replaced,
and a model or provider changed, without touching anything in this file.

Descriptions are deliberately plain and honest. The K4.2 discovery matcher
still scores them lexically (ADR-K4.2-H-04, unchanged); they are NOT written to
win that score (ADR-K4.2-H-13 rejected "gaming the scorer"), and none is
marked is_general_purpose: none of them is a fallback -- LLM_COMPLETION
remains the one general-purpose fallback (ADR-CAP-01 §LLM_COMPLETION).
"""
from __future__ import annotations

from typing import List

from core.capabilities.capability import CapabilityContract, CapabilityType
from core.capabilities.descriptors import (
    OperationSpec, Repeatability, SemanticType, SideEffect, TypeSpec,
)
from core.capabilities.foundation.readers.base import SUPPORTED_MEDIA_TYPES
from core.capabilities.foundation.schemas import (
    SCHEMA_ANALYSIS, SCHEMA_ARTIFACT_INPUT, SCHEMA_DOCUMENT_SET, SCHEMA_TEXT,
)

CONTRACT_VERSION = "1.0.0"

_TEXT_OUT = TypeSpec(SemanticType.TEXT, ("text/plain", "text/markdown"), SCHEMA_TEXT)
_ANALYSIS = TypeSpec(SemanticType.ANALYSIS, ("application/json",), SCHEMA_ANALYSIS)
_DOCUMENTS = TypeSpec(SemanticType.DOCUMENT, ("application/json",), SCHEMA_DOCUMENT_SET)
_PLAIN_TEXT = TypeSpec(SemanticType.TEXT, ("text/plain", "text/markdown"))
_ARTIFACTS = TypeSpec(SemanticType.ARTIFACTS, SUPPORTED_MEDIA_TYPES, SCHEMA_ARTIFACT_INPUT)

# What may be supplied as *source material* to text and reasoning operations.
_SOURCE_TYPES = (_PLAIN_TEXT, _DOCUMENTS, _ANALYSIS)


def text_generation_contract() -> CapabilityContract:
    common = dict(inputs=_SOURCE_TYPES, outputs=(_TEXT_OUT,),
                  produces=("schema", "status", "text"),
                  repeatability=Repeatability.MODEL_VARIABLE)
    return CapabilityContract(
        capability_type=CapabilityType.TEXT_GENERATION,
        description=("Write, compose, draft, rewrite, summarize or transform "
                     "text: generate prose from an instruction, condense or "
                     "restyle supplied material, or convert it to another "
                     "format."),
        version=CONTRACT_VERSION,
        side_effects=SideEffect.NONE,
        default_operation="generate",
        operations=(
            OperationSpec("generate",
                          "Produce text from an instruction, optionally "
                          "grounded in supplied context.",
                          requires=("instruction",), **common),
            OperationSpec("rewrite",
                          "Rewrite supplied text under an instruction "
                          "(tone, register, clarity) preserving its meaning.",
                          requires=("source",), **common),
            OperationSpec("summarize",
                          "Condense supplied material to its essentials.",
                          requires=("source",), **common),
            OperationSpec("transform",
                          "Convert supplied material into a target format "
                          "(bullets, table, outline ...).",
                          requires=("source", "target_format"), **common),
        ),
    )


def structured_reasoning_contract() -> CapabilityContract:
    common = dict(inputs=_SOURCE_TYPES, outputs=(_ANALYSIS,),
                  produces=("schema", "status", "findings", "contradictions",
                            "uncertainties", "conclusions"),
                  repeatability=Repeatability.MODEL_VARIABLE)
    return CapabilityContract(
        capability_type=CapabilityType.STRUCTURED_REASONING,
        description=("Analyze, compare, diagnose and evaluate alternatives "
                     "across supplied material; identify contradictions and "
                     "draw structured conclusions with cited sources and "
                     "stated uncertainty."),
        version=CONTRACT_VERSION,
        side_effects=SideEffect.NONE,
        default_operation="analyze",
        operations=(
            OperationSpec("analyze",
                          "Structured analysis of supplied material for a "
                          "task (diagnosis, contradictions, alternatives and "
                          "relationships are focuses of this operation).",
                          requires=("task", "sources"), **common),
            OperationSpec("compare",
                          "Compare two or more named subjects across "
                          "supplied material.",
                          requires=("task", "sources", "subjects"), **common),
        ),
    )


def file_reading_contract() -> CapabilityContract:
    common = dict(inputs=(_ARTIFACTS,), outputs=(_DOCUMENTS,),
                  requires=("artifacts",),
                  produces=("schema", "status", "documents", "trust"),
                  repeatability=Repeatability.REPEATABLE)
    return CapabilityContract(
        capability_type=CapabilityType.FILE_READING,
        description=("Read, inspect and extract content from supplied "
                     "documents and files (PDF, DOCX, spreadsheets, CSV, "
                     "Markdown, text): structured sections, tables and "
                     "page-referenced text."),
        version=CONTRACT_VERSION,
        side_effects=SideEffect.READ_ONLY,
        default_operation="read_document",
        operations=(
            OperationSpec("read_document",
                          "Read artifact(s) into a structured document set, "
                          "optionally restricted by a selection (pages, "
                          "sections, tables, lines, sheets).", **common),
            OperationSpec("extract_structure",
                          "Outline only: sections and table shapes without "
                          "bodies, for progressive reading.", **common),
        ),
    )


def foundation_contracts() -> List[CapabilityContract]:
    return [file_reading_contract(), structured_reasoning_contract(),
            text_generation_contract()]
