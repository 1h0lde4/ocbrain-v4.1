"""
interface/api.py — V2.1: true token streaming via SSE + async file I/O.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, AsyncGenerator, Any

import aiofiles
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import config
from core.event_bus import bus
from core.orchestrator import Orchestrator
from core.module_factory import create as factory_create

log = logging.getLogger(__name__)

app = FastAPI(
    title="OCBrain",
    version="2.1.0",
    description="OCBrain API — local self-learning AI assistant",
)

_orchestrator: Optional[Orchestrator] = None
_scheduler    = None
_orchestrator_ref: dict = {}

WEB_DIR = Path(__file__).parent / "web"


def setup(orchestrator: Orchestrator, scheduler):
    global _orchestrator, _scheduler
    _orchestrator = orchestrator
    _scheduler    = scheduler
    _orchestrator_ref["orchestrator"] = orchestrator

    from core.brain_api import register as register_brain_api
    register_brain_api(app, _orchestrator_ref)

    bus.on("module.promoted",      _log_evt)
    bus.on("learning.train_done",  _log_evt)
    bus.on("learning.distill_done",_log_evt)


def _log_evt(p): log.info(f"[event] {p.get('_event')}: {p}")


# ── Models ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    module: Optional[str] = None
    stream: bool = False

class QueryResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    answer: str
    error: Optional[str] = None
    meta: dict = {}

class NewModuleRequest(BaseModel):
    name: str; desc: str; model: str
    keywords: list[str]; sources: list[str]

class DistillRequest(BaseModel):
    module_name: str; topic: str; num_pairs: int = 50

class ExportRequest(BaseModel):
    module_name: str

class ImportRequest(BaseModel):
    bundle_path: str; overwrite: bool = False


# ── Routes ─────────────────────────────────────────────────────

@app.post("/query")
async def query(req: QueryRequest):
    if _orchestrator is None:
        return QueryResponse(
            success=False,
            answer="OCBrain is still starting up. Please wait a moment and try again.",
            error="Orchestrator not initialized"
        )

    try:
        if req.stream:
            return StreamingResponse(
                _stream_response(_orchestrator, req.query),
                media_type="text/event-stream",
                headers={
                    "Cache-Control":     "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        answer = await _orchestrator.handle(req.query)
        
        # Standardized Response Contract
        return QueryResponse(
            success=True,
            answer=answer,
            data={"query": req.query},
            meta={
                "version": "3.01",
                "orchestrator": "v3",
                "phase": 4
            }
        )

    except Exception as e:
        import logging, traceback
        err_msg = f"{type(e).__name__}: {e}"
        logging.getLogger("ocbrain").error(
            f"POST /query failed: {err_msg}\n{traceback.format_exc()}"
        )
        return QueryResponse(
            success=False,
            answer="I encountered an internal error. Check logs for details.",
            error=err_msg,
            meta={"traceback": traceback.format_exc() if config.get("global.debug") else None}
        )

@app.get("/health")
async def get_health():
    from core.meta.self_model import SELF_MODEL
    return QueryResponse(
        success=True,
        answer="System health check complete.",
        data=SELF_MODEL["health"]
    )

@app.get("/introspection")
async def get_introspection():
    from core.meta.introspection import summarize_system_state, explain_capabilities, explain_limitations
    return QueryResponse(
        success=True,
        answer=summarize_system_state(),
        data={
            "capabilities": explain_capabilities(),
            "limitations": explain_limitations()
        }
    )

@app.get("/dashboard")
async def get_dashboard_data():
    from core.meta.self_model import SELF_MODEL
    return QueryResponse(
        success=True,
        answer="Returning real-time dashboard state.",
        data=SELF_MODEL
    )

@app.post("/evolve/plan")
async def generate_evolution_plan():
    from core.meta.planner import upgrade_planner
    proposals = upgrade_planner.propose_upgrades()
    prioritized = upgrade_planner.prioritize_upgrades(proposals)
    return QueryResponse(
        success=True,
        answer=f"Generated {len(prioritized)} evolution proposals.",
        data=prioritized
    )


async def _stream_response(
    orchestrator: Orchestrator, query: str
) -> AsyncGenerator[str, None]:
    """
    True token streaming: feeds Ollama stream tokens directly to the SSE client.
    The orchestrator handle() still collects the full answer for context saving,
    but the client sees tokens as they arrive from the model.
    """
    from core.model_router import model_router
    from core import classifier, decomposer, parser

    # Parse + classify (fast — typically < 10ms)
    parsed = parser.parse(query)
    labels = await classifier.label(parsed, orchestrator.context)
    tasks  = decomposer.build(parsed, labels)

    # For single-module queries: stream tokens directly
    if len(tasks) == 1:
        task        = tasks[0]
        module_name = task.module
        collected   = []

        async for token in model_router.stream_route(
            module_name, task.subtask, orchestrator.context
        ):
            collected.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"

        yield "data: [DONE]\n\n"

        # Save full collected answer to context (non-blocking)
        asyncio.create_task(
            _save_context_background(orchestrator, query, [module_name], "".join(collected))
        )

    else:
        # Multi-module: collect all, then stream the merged result in chunks
        answer = await orchestrator.handle(query)
        chunk_size = 40
        for i in range(0, len(answer), chunk_size):
            yield f"data: {json.dumps({'token': answer[i:i+chunk_size]})}\n\n"
            await asyncio.sleep(0.008)
        yield "data: [DONE]\n\n"


async def _save_context_background(
    orchestrator: Orchestrator, query: str, modules: list[str], answer: str
):
    """Fire-and-forget context save after streaming completes."""
    try:
        orchestrator.context.save(query, modules, answer)
    except Exception:
        pass


@app.get("/status")
async def status():
    if _orchestrator is None:
        return {"status": "starting"}
    from core.brain_version import brain_version_manager
    return {
        "status":        "ok",
        "modules":       _orchestrator.status(),
        "brain_version": brain_version_manager.brain_version,
        "app_version":   brain_version_manager.app_version,
    }


@app.get("/modules")
async def list_modules():
    if _orchestrator is None:
        raise HTTPException(503, "Not ready")
    return {name: mod.health() for name, mod in _orchestrator.modules.items()}


@app.post("/modules/new")
async def new_module(req: NewModuleRequest):
    try:
        path = factory_create(req.name, req.desc, req.model, req.keywords, req.sources)
        from core.module_registry import reload_module
        reload_module(req.name, _orchestrator.modules)
        await bus.emit("module.created", {"module": req.name})
        return {"status": "created", "path": str(path)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/train/{module_name}")
async def train_module(module_name: str):
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not running")
    if module_name not in _orchestrator.modules:
        raise HTTPException(404, f"Module '{module_name}' not found")
    result = await _scheduler.trigger_module(module_name)
    return {"result": result}


@app.post("/distill")
async def distill(req: DistillRequest):
    from learning.distiller import distill_topic
    n = await distill_topic(req.module_name, req.topic, req.num_pairs)
    return {"status": "done", "pairs_generated": n}


@app.post("/export")
async def export_module(req: ExportRequest):
    from core.brain_export import export_module
    path = export_module(req.module_name)
    return {"status": "exported", "path": str(path)}


@app.post("/import")
async def import_module(req: ImportRequest):
    from core.brain_export import import_module
    name = import_module(Path(req.bundle_path), overwrite=req.overwrite)
    return {"status": "imported", "module": name}


@app.get("/debug")
async def debug():
    """
    Returns a full diagnostic snapshot — call this when something is broken.
    Visit http://localhost:7437/debug in your browser.
    """
    import httpx, traceback
    report = {}

    # Orchestrator
    report["orchestrator"] = "ready" if _orchestrator else "NOT INITIALISED"

    # Module health
    if _orchestrator:
        report["modules"] = {}
        for name, mod in _orchestrator.modules.items():
            try:
                report["modules"][name] = mod.health()
            except Exception as e:
                report["modules"][name] = {"error": str(e)}

    # Ollama connectivity
    host = config.get("global.ollama_host") or "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{host}/api/tags")
            data = r.json()
            models = [m.get("name") for m in data.get("models", [])]
            report["ollama"] = {
                "status": "reachable",
                "host": host,
                "models_available": models,
            }
    except Exception as e:
        report["ollama"] = {
            "status": "UNREACHABLE",
            "host": host,
            "error": str(e),
            "fix": "Make sure Ollama is running: ollama serve",
        }

    # Check configured models vs available models
    if _orchestrator and "models_available" in report.get("ollama", {}):
        available = report["ollama"]["models_available"]
        for name, mod_info in report.get("modules", {}).items():
            bm = mod_info.get("model", "?")
            # Ollama uses "mistral:latest" for "mistral" etc.
            found = any(bm in m or m.startswith(bm) for m in available)
            mod_info["model_available_in_ollama"] = found
            if not found:
                mod_info["model_warning"] = (
                    f"'{bm}' not found in Ollama. "
                    f"Run: ollama pull {bm}"
                )

    # Config summary
    report["config"] = {
        "ollama_host": config.get("global.ollama_host"),
        "web_ui_port": config.get("global.web_ui_port"),
    }

    return report


@app.get("/config")
async def get_config():
    return config._settings


@app.put("/config")
async def set_config(updates: dict):
    for k, v in updates.items():
        config.set(k, v)
    return {"status": "updated"}


@app.get("/updates")
async def check_updates():
    from interface.updater import check
    result = check()
    return {
        "available":    result.available,
        "version":      result.version,
        "current":      result.current,
        "changelog":    result.changelog,
        "download_url": result.download_url,
        "check_failed": result.check_failed,
        "check_error":  result.check_error,
    }


@app.post("/update/install")
async def install_update():
    from interface.updater import check, install_async
    info = check()
    if info.check_failed:
        return {"status": "check_failed", "error": info.check_error}
    if not info.available:
        return {"status": "already_up_to_date", "version": info.current}
    # Run non-blocking — git pull can take 30-60s
    asyncio.create_task(_do_install_async(info.version))
    return {
        "status":  "installing",
        "version": info.version,
        "message": "Update started in background. Restart OCBrain when complete.",
    }


async def _do_install_async(version: str):
    from interface.updater import install_async
    import logging
    result = await install_async(version)
    logging.getLogger("ocbrain").info(
        f"[updater] {'OK' if result.success else 'FAILED'}: {result.message}"
    )


@app.post("/update/restart")
async def restart_server():
    """Restart OCBrain process to apply a completed update."""
    from interface.updater import restart
    asyncio.get_event_loop().call_later(1.0, restart)
    return {"status": "restarting", "message": "OCBrain will restart in 1 second."}


@app.post("/rollback")
async def rollback():
    from interface.updater import rollback as do_rollback
    result = do_rollback()
    return {
        "status":           "ok" if result.success else "failed",
        "message":          result.message,
        "restart_required": result.restart_required,
    }


@app.get("/brain/version")
async def brain_version():
    from core.brain_version import brain_version_manager
    return brain_version_manager.to_dict()


@app.get("/events")
async def event_stream():
    """SSE stream of all brain events."""
    async def _gen():
        queue: asyncio.Queue = asyncio.Queue()

        async def enqueue(payload):
            await queue.put(payload)

        from core.event_bus import EVENTS
        for evt in EVENTS:
            bus.on(evt, enqueue)
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            for evt in EVENTS:
                bus.off(evt, enqueue)

    return StreamingResponse(_gen(), media_type="text/event-stream")


# V2.1 FIX: async file I/O for static files
@app.get("/", response_class=HTMLResponse)
async def root():
    index = WEB_DIR / "index.html"
    if index.exists():
        async with aiofiles.open(index, "r", encoding="utf-8") as f:
            content = await f.read()
        return HTMLResponse(content)
    return HTMLResponse(
        "<h2>OCBrain v2.1 is running.</h2>"
        "<p>API docs: <a href='/docs'>/docs</a></p>"
    )


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
