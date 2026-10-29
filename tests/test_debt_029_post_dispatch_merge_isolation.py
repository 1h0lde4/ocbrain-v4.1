"""DEBT-029 (class closure): nothing after the capability calls may turn completed work into a failure.

DEBT-029 is "a post-dispatch failure re-fires capability calls via node retry".  Its named instance
(Step 8 ``ContextMemory.save()``) is covered by ``test_debt_044_context_persistence.py`` (Test F).
These tests cover the one other post-dispatch step that is reachable in production: the three-or-more
module branch of ``merger.merge()``.  ``classifier_v3.classify()`` ignores ``top_k`` on its embedding
path, so ``PlannerWorker._run()`` can dispatch three or more modules, and ``merge()`` then calls
``_weave()`` -- whose provider resolution used to sit outside its ``try``.
"""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.merger as merger
from core.context import ContextMemory
from core.model_router import RouteResult
from core.runtime.execution_context import ExecutionContext
from core.workers.planner import PlannerWorker
from types import SimpleNamespace

CONFIG_FAILURE = "PROVIDER_RESOLUTION_FAILURE_SENTINEL"
# Mutually contradicting ("yes"/"no") so _answers_compatible() is False and merge() must reach _weave().
ANSWERS = ["yes alpha result", "no beta outcome", "gamma delta finding"]


def _results():
    return [RouteResult(answer=a, source=f"m{i}") for i, a in enumerate(ANSWERS)]


@pytest.mark.asyncio
async def test_merge_three_modules_survives_provider_resolution_failure(caplog):
    assert not merger._answers_compatible(ANSWERS)  # precondition: the _weave() branch is the one under test
    with patch.object(merger, "resolve_provider", side_effect=RuntimeError(CONFIG_FAILURE)):
        with caplog.at_level(logging.WARNING):
            out = await merger.merge(_results(), "q")
    for a in ANSWERS:
        assert a in out  # degraded to a plain join of the module answers, nothing lost
    assert CONFIG_FAILURE not in caplog.text  # exception text is not logged (DEBT-037 discipline)
    assert "RuntimeError" in caplog.text  # ...but the degradation is observable


@pytest.mark.asyncio
async def test_merge_three_modules_survives_generation_failure():
    with patch.object(merger, "generate_with_fallback", new=AsyncMock(side_effect=RuntimeError("all providers failed"))):
        out = await merger.merge(_results(), "q")
    for a in ANSWERS:
        assert a in out


@pytest.mark.asyncio
async def test_planner_three_module_merge_failure_does_not_fail_completed_work():
    """End to end through PlannerWorker._run() with the REAL merger: capability calls ran, merge degrades, save still runs."""
    ctx = MagicMock(spec=ContextMemory)
    answers = iter(ANSWERS)
    router = MagicMock()
    router.route = AsyncMock(side_effect=lambda *a, **k: RouteResult(answer=next(answers), source="test"))
    worker = PlannerWorker(modules={m: MagicMock() for m in ("coding", "knowledge", "web_search")},
                           context_memory=ctx, model_router=router)
    patches = (
        patch("core.parser.parse", return_value=SimpleNamespace(entities={"urls": [], "languages": [], "filenames": []})),
        patch("core.memory.assembly.context_assembler.assemble_context", new=AsyncMock(return_value="")),
        patch("core.classifier_v3.classify",
              return_value=[{"module": "coding"}, {"module": "knowledge"}, {"module": "web_search"}]),
        patch.object(merger, "resolve_provider", side_effect=RuntimeError(CONFIG_FAILURE)),
    )
    with patches[0], patches[1], patches[2], patches[3]:
        result = await worker._run(ExecutionContext(metadata={"query": "q"}))
    assert router.route.await_count == 3  # three real capability calls happened
    assert result.success, result.error  # ...and a post-dispatch merge degradation must not fail them
    ctx.save.assert_called_once()
