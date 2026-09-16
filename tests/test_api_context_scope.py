"""
tests/test_api_context_scope.py — CTX-SCOPE-001 caller wiring, interface/api.py

interface/api.py had no dedicated test file before this fix. Rather than
build full FastAPI TestClient/ASGI scaffolding (a larger, separate lift,
out of scope for a minimal caller-wiring fix), this tests
_save_context_background directly -- it's a standalone async function,
not a route handler itself, so it doesn't need one.

Covers site #5 from docs/Bugs Hunt & fix reports/CONTEXT_ISOLATION_CALLER_AUDIT_SEP2026.md
(interface/api.py's streaming SSE fire-and-forget context save).

The other site touched in interface/api.py by this same fix -- the direct
model_router.stream_route(..., scope=execution_id) call inside
_stream_response's single-module fast path -- is a one-line addition of an
already-in-scope variable, verified by direct code reading rather than a
dedicated test here; tests/test_model_router.py::test_stream_route_forwards_scope_to_build_prompt
covers the receiving end of that same call.
"""
from unittest.mock import MagicMock

import pytest

from interface.api import _save_context_background


@pytest.mark.asyncio
async def test_save_context_background_passes_execution_id_as_scope():
    mock_orchestrator = MagicMock()

    await _save_context_background(
        mock_orchestrator, "what's the weather", ["knowledge"], "sunny",
        "exec-background-save-123",
    )

    mock_orchestrator.context.save.assert_called_once_with(
        "what's the weather", ["knowledge"], "sunny", scope="exec-background-save-123")


@pytest.mark.asyncio
async def test_save_context_background_defaults_to_unscoped():
    """No execution_id supplied (e.g. an old caller that never adopted
    it) must preserve the exact pre-fix call shape -- not scope=None,
    not a crash."""
    mock_orchestrator = MagicMock()

    await _save_context_background(
        mock_orchestrator, "q", ["mod"], "a")

    mock_orchestrator.context.save.assert_called_once_with("q", ["mod"], "a", scope="")


@pytest.mark.asyncio
async def test_save_context_background_still_swallows_exceptions():
    """Regression guard: this function's fire-and-forget contract (a
    context-save failure must never surface to the streaming client)
    predates this fix and must not have been disturbed by adding the
    scope parameter."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.context.save.side_effect = RuntimeError("disk full")

    await _save_context_background(mock_orchestrator, "q", ["mod"], "a", "exec-1")
    # No exception propagated -- that's the whole assertion.
