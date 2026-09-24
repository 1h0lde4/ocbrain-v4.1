"""
core/workers/capability_steps.py — step workers for the foundation capabilities.

A compiled WorkflowNode has ``worker_type == capability_type`` (compile() passes
the capability type straight through, Packet 06), and WorkerRegistry resolves a
node by that string. CapabilityExecutorWorker answers only for "llm_completion";
its own docstring says a second capability needs "one worker per capability_type
... future work". These are those workers -- one small explicit class per
capability, no dispatch table, no magic (LAW 4).

What a step worker does, and nothing else: build a CapabilityRequest from
  * the node's *trusted plan-level config* (description -> instruction;
    operation / selection / focus / constraints ... if present),
  * the results of the node's direct predecessors (the runtime hands these over
    in context.metadata["upstream_results"]; ADR-CAP-02), and
  * for FILE_READING only, the caller-authorized ``input_artifacts`` of the run,
invoke AdapterRuntime, and translate the CapabilityResult into a WorkerResult.

Boundaries kept here:
  * Governance is not bypassed: these are AbstractCognitiveWorker subclasses;
    execute() runs evaluate_action() before _run() exists as a code path.
  * Document content is never an instruction: upstream material only ever goes
    into the *data* payload keys (sources / source / context); the instruction
    is always the node's own description from the plan.
  * Least privilege: raw artifact bytes (``input_artifacts``) are read by the
    FILE_READING worker only; reasoning and generation workers never see them.
  * Nothing here plans, selects a capability, or judges the result.

WorkerResult convention: ``output`` is a human-readable string (the generated
text, or a one-line summary) so a plan that ends in any of these still yields a
string final answer; the typed hand-off lives in ``artifacts["structured"]``,
with ``status`` and ``provenance`` beside it. Partial and degraded results map
to COMPLETED_WITH_PARTIAL_OUTPUT (is_success but not is_fully_satisfied,
DEBT-020) -- they are not laundered into a clean success.
"""
from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from core.capabilities.adapter_runtime import AdapterRuntime
from core.capabilities.capability import (
    CapabilityRequest, CapabilityResult, CapabilityType,
)
from core.capabilities.descriptors import CapabilityStatus as S
from core.runtime.execution_context import ExecutionContext
from core.runtime.execution_outcome import ExecutionOutcome, FailureType
from core.workers.base import AbstractCognitiveWorker, WorkerResult

INPUT_ARTIFACTS_KEY = "input_artifacts"  # run-level metadata key, FILE_READING only


def _failure_type(result: CapabilityResult) -> FailureType:
    status, error = result.status, result.error or ""
    if status in (S.INVALID_REQUEST, S.UNSUPPORTED, S.MALFORMED,
                  S.UNREADABLE, S.LIMIT_EXCEEDED):
        return FailureType.VALIDATION_ERROR
    if status == S.TIMEOUT:
        return FailureType.HARD_DEADLINE
    if status == S.CANCELLED:
        return FailureType.CANCELLED
    if status in (S.DEPENDENCY_UNAVAILABLE, S.UNAVAILABLE):
        return FailureType.OTHER_FAILURE
    if error.startswith("empty model response"):
        return FailureType.EMPTY_RESPONSE
    if error.startswith("model error"):
        return FailureType.PROVIDER_FAILURE
    return FailureType.OTHER_FAILURE


class CapabilityStepWorker(AbstractCognitiveWorker):
    """Common bridge. Subclasses set ``capability_type`` (== worker_type) and
    implement ``build_payload`` and ``summarize``."""

    capability_type: ClassVar[str] = ""

    def __init__(self, *, adapter_runtime: AdapterRuntime, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._adapter_runtime = adapter_runtime

    # -- subclass hooks ------------------------------------------------------
    def build_payload(self, *, instruction: str, operation: str,
                      upstream: List[Any], node_config: Dict[str, Any],
                      context: ExecutionContext) -> Dict[str, Any]:
        raise NotImplementedError

    def summarize(self, result: CapabilityResult) -> str:
        raise NotImplementedError

    # -- template ------------------------------------------------------------
    async def _run(self, context: ExecutionContext) -> WorkerResult:
        node_config: Dict[str, Any] = context.metadata.get("node_config", {}) or {}
        instruction = str(node_config.get("description", context.query) or "")
        operation = str(node_config.get("operation", "") or "")
        upstream = self._upstream_sources(context)
        payload = self.build_payload(
            instruction=instruction, operation=operation, upstream=upstream,
            node_config=node_config, context=context)
        request = CapabilityRequest(
            capability_type=self.capability_type,
            payload={k: v for k, v in payload.items() if v is not None},
            operation=operation,
            metadata={"node_id": context.metadata.get("node_id", "")})
        result = await self._adapter_runtime.invoke(
            self.capability_type, request=request)
        return self._to_worker_result(result)

    @staticmethod
    def _upstream_sources(context: ExecutionContext) -> List[Any]:
        """Data handed over by direct predecessors, in predecessor order.
        Typed hand-off when the predecessor produced one; otherwise its text
        output (e.g. a legacy llm_completion node) -- as *data*, like anything
        else that arrives from upstream."""
        out: List[Any] = []
        upstream = context.metadata.get("upstream_results") or {}
        for wr in upstream.values():
            structured = (getattr(wr, "artifacts", None) or {}).get("structured")
            if isinstance(structured, dict):
                out.append(structured)
            elif isinstance(getattr(wr, "output", None), str) and wr.output.strip():
                out.append(wr.output)
        return out

    def _to_worker_result(self, result: CapabilityResult) -> WorkerResult:
        detail = {"capability_status": result.status,
                  "capability_type": self.capability_type,
                  "operation": result.provenance.get("operation", "")}
        structured = result.output if isinstance(result.output, dict) else None
        artifacts = {"adapter_used": result.adapter_used,
                     "capability_type": self.capability_type,
                     "operation": result.provenance.get("operation", ""),
                     "status": result.status,
                     "provenance": result.provenance,
                     "structured": structured}
        if not result.success:
            return WorkerResult(
                success=False,
                error=result.error or f"{self.capability_type} failed ({result.status})",
                artifacts=artifacts,
                execution_detail=ExecutionOutcome.failure(
                    _failure_type(result),
                    retryable=bool(result.metadata.get("retryable")) or None,
                    detail=detail))
        text = self.summarize(result)
        if result.status in (S.PARTIAL, S.DEGRADED):
            outcome = ExecutionOutcome(
                failure_type=FailureType.COMPLETED_WITH_PARTIAL_OUTPUT,
                partial_output=text, detail=detail)
        else:
            outcome = ExecutionOutcome.success(detail=detail)
        return WorkerResult(success=True, output=text, artifacts=artifacts,
                            execution_detail=outcome)


def _reason(structured: Optional[Dict[str, Any]]) -> str:
    notes = (structured or {}).get("notes") or []
    return notes[0] if notes else ""


class FileReadingStepWorker(CapabilityStepWorker):
    worker_type = CapabilityType.FILE_READING
    capability_type = CapabilityType.FILE_READING

    def build_payload(self, *, instruction, operation, upstream, node_config, context):
        return {"artifacts": context.metadata.get(INPUT_ARTIFACTS_KEY),
                "selection": node_config.get("selection"),
                "limits": node_config.get("limits")}

    def summarize(self, result: CapabilityResult) -> str:
        docs = (result.output or {}).get("documents") or []
        parts = []
        for d in docs:
            doc = d.get("document") or {}
            stats = doc.get("stats") or {}
            parts.append(f"{d['artifact']['artifact_id']}: {d['status']}"
                         + (f" ({stats.get('blocks', 0)} blocks, "
                            f"{stats.get('tables', 0)} tables)" if doc else ""))
        return f"Read {len(docs)} artifact(s) [{result.status}] " + "; ".join(parts)


class StructuredReasoningStepWorker(CapabilityStepWorker):
    worker_type = CapabilityType.STRUCTURED_REASONING
    capability_type = CapabilityType.STRUCTURED_REASONING

    def build_payload(self, *, instruction, operation, upstream, node_config, context):
        return {"task": instruction, "sources": upstream or None,
                "focus": node_config.get("focus"),
                "subjects": node_config.get("subjects")}

    def summarize(self, result: CapabilityResult) -> str:
        out = result.output or {}
        if result.status == S.EMPTY:
            return f"No analysis: {_reason(out) or 'no findings'}"
        concl = out.get("conclusions") or []
        head = f"Analysis [{result.status}]: {len(out.get('findings', []))} finding(s), " \
               f"{len(out.get('contradictions', []))} contradiction(s)"
        return head + ("; " + " ".join(concl[:3]) if concl else "")


class TextGenerationStepWorker(CapabilityStepWorker):
    worker_type = CapabilityType.TEXT_GENERATION
    capability_type = CapabilityType.TEXT_GENERATION

    def build_payload(self, *, instruction, operation, upstream, node_config, context):
        payload: Dict[str, Any] = {"instruction": instruction,
                                   "constraints": node_config.get("constraints"),
                                   "target_format": node_config.get("target_format")}
        key = "source" if operation in ("rewrite", "summarize", "transform") else "context"
        payload[key] = upstream or None
        return payload

    def summarize(self, result: CapabilityResult) -> str:
        out = result.output or {}
        if result.status == S.EMPTY:
            return f"No output: {_reason(out) or 'no content'}"
        return out.get("text", "")


FOUNDATION_STEP_WORKERS = (FileReadingStepWorker, StructuredReasoningStepWorker,
                           TextGenerationStepWorker)
