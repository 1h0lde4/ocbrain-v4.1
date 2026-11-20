import asyncio
from types import SimpleNamespace

import pytest

import interface.api as api


@pytest.mark.asyncio
async def test_single_module_streaming_does_not_retain_oversized_context_output(
    monkeypatch,
):
    monkeypatch.setattr(
        "core.runtime.execution_graph.execution_registry.get", lambda _id: None
    )
    monkeypatch.setattr("core.parser.parse", lambda query: query)

    async def labels(*args, **kwargs):
        return ["coding"]

    monkeypatch.setattr("core.classifier.label", labels)
    monkeypatch.setattr(
        "core.decomposer.build",
        lambda parsed, result: [
            SimpleNamespace(module="coding", subtask="respond")
        ],
    )
    monkeypatch.setattr("core.model_router.MAX_STREAM_BUFFER_CHARS", 4)

    route_calls = []

    class FakeRouter:
        async def stream_route(self, *args, **kwargs):
            route_calls.append(kwargs)
            yield "1234"
            yield "5678"

    saved = []

    async def save(*args, **kwargs):
        saved.append((args, kwargs))

    monkeypatch.setattr("core.model_router.model_router", FakeRouter())
    monkeypatch.setattr(api, "_save_context_background", save)

    chunks = [
        chunk async for chunk in api._stream_response(
            SimpleNamespace(context=SimpleNamespace()),
            "question",
            execution_id="exec-buffer-limit",
        )
    ]
    await asyncio.sleep(0)

    assert '"token": "1234"' in "".join(chunks)
    assert '"token": "5678"' in "".join(chunks)
    assert saved == []
    assert route_calls[0]["execution_id"] == "exec-buffer-limit"
