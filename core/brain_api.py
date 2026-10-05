"""
core/brain_api.py — Versioned, documented Brain API contract.
This is the stable interface OpenClaw components use to talk to the brain.
Wraps the FastAPI app with a clear contract layer.

Versions:
  v1 — initial API (V1 of ocbrain)
  v2 — adds streaming, events, distillation, export/import (this file)
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import asyncio
import json
import logging
import uuid

log = logging.getLogger(__name__)

BRAIN_API_VERSION = "2.1.0"

router = APIRouter(prefix="/brain/v2", tags=["Brain API v2"])

# ── Request / Response models ─────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    module: Optional[str] = None
    stream: bool = False
    context_turns: int = 5

class QueryResponse(BaseModel):
    answer: str
    modules_used: list[str] = []
    latency_ms: int = 0
    brain_version: str = BRAIN_API_VERSION

class ModuleStatus(BaseModel):
    name: str
    stage: str
    maturity_score: float
    query_count: int
    kb_chunks: int
    db_ok: bool
    lora_version: int = 0

class BrainStatus(BaseModel):
    status: str
    brain_version: str
    app_version: str
    schema_version: int
    modules: dict[str, ModuleStatus]
    total_queries: int

class ExportRequest(BaseModel):
    module_name: str

class ImportRequest(BaseModel):
    bundle_path: str
    overwrite: bool = False

class DistillRequest(BaseModel):
    module_name: str
    topic: str
    num_pairs: int = 50
    teacher_model: Optional[str] = None

class EventSubscribeRequest(BaseModel):
    event: str
    webhook_url: str   # OpenClaw component registers a local webhook


# ── Route implementations (wired in interface/api.py) ─────────

def register(app, orchestrator_ref: dict):
    """Called from interface/api.py to mount all v2 brain routes."""

    @router.get("/status", response_model=BrainStatus)
    async def brain_status():
        from core.brain_version import brain_version_manager
        orch  = orchestrator_ref.get("orchestrator")
        state = brain_version_manager.get_state()
        mods  = {}
        if orch:
            for name, mod in orch.modules.items():
                h = mod.health()
                brain_mod = state.modules.get(name, {})
                mods[name] = ModuleStatus(
                    name=name,
                    stage=h.get("stage", "bootstrap"),
                    maturity_score=h.get("maturity_score", 0.0),
                    query_count=h.get("query_count", 0),
                    kb_chunks=h.get("kb_chunks", 0),
                    db_ok=h.get("db_ok", True),
                    lora_version=brain_mod.get("lora_version", 0),
                )
        return BrainStatus(
            status="ok",
            brain_version=state.brain_version,
            app_version=brain_version_manager.app_version,
            schema_version=state.schema_version,
            modules=mods,
            total_queries=state.total_queries_handled,
        )

    @router.post("/query")
    async def brain_query(req: QueryRequest):
        from core.brain_version import brain_version_manager
        import time
        orch = orchestrator_ref.get("orchestrator")
        if orch is None:
            return {"error": "Brain not ready"}

        if req.stream:
            return StreamingResponse(
                _stream_query(orch, req.query),
                media_type="text/event-stream",
            )

        t0     = time.monotonic()
        answer = await orch.handle(req.query)
        brain_version_manager.record_query()
        return QueryResponse(
            answer=answer,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    @router.post("/distill")
    async def distill(req: DistillRequest):
        # Same guard as interface/api.py's /distill; distill_topic and
        # _save_pairs also enforce it, this just turns it into a clean 400.
        if not req.module_name.isidentifier():
            raise HTTPException(
                400, "Invalid module_name: use only letters, digits, underscores."
            )
        from learning.distiller import distill_topic
        result = await distill_topic(
            req.module_name, req.topic,
            num_pairs=req.num_pairs,
            teacher_model=req.teacher_model,
        )
        return {"status": "done", "pairs_generated": result}

    @router.post("/export")
    async def export_module(req: ExportRequest):
        from core.brain_export import export_module
        path = export_module(req.module_name)
        return {"status": "exported", "path": str(path)}

    @router.post("/import")
    async def import_module(req: ImportRequest):
        from pathlib import Path
        from core.brain_export import BundlePathError, import_module
        try:
            name = import_module(Path(req.bundle_path), overwrite=req.overwrite)
        except BundlePathError:
            raise HTTPException(
                400, "bundle_path must be a file inside the configured import root."
            )
        return {"status": "imported", "module": name}

    @router.get("/version")
    async def version():
        from core.brain_version import brain_version_manager
        return {
            "brain_api_version": BRAIN_API_VERSION,
            "brain_version":     brain_version_manager.brain_version,
            "app_version":       brain_version_manager.app_version,
            "schema_version":    brain_version_manager.schema_version,
        }

    app.include_router(router)


async def _stream_query(orchestrator, query: str) -> AsyncGenerator[str, None]:
    """
    SSE streaming: yields tokens as they're generated.
    Currently yields the full answer as one event (token streaming
    requires Ollama streaming mode — wired in V2.1).
    """
    try:
        answer = await orchestrator.handle(query)
        if not answer:
            answer = ""
        # Yield in ~50-char chunks to simulate streaming
        chunk_size = 50
        for i in range(0, len(answer), chunk_size):
            chunk = answer[i:i + chunk_size]
            yield f"data: {json.dumps({'token': chunk})}\n\n"
            await asyncio.sleep(0.01)
        yield "data: [DONE]\n\n"
    except Exception as e:
        # SECURITY (CodeQL py/stack-trace-exposure, CWE-209/497): str(e)
        # can contain filesystem paths, internal component names, or other
        # implementation detail -- must not reach the SSE client. See
        # interface/api.py's _log_and_redact for the sibling fix; this file
        # doesn't import from interface/, so the same few lines are kept
        # local rather than introducing a cross-package dependency for one
        # helper.
        error_id = str(uuid.uuid4())
        log.error("Brain API streaming query failed; error_id=%s", error_id, exc_info=e)
        yield f"data: {json.dumps({'error': 'internal_error', 'error_id': error_id})}\n\n"
