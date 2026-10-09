"""FZ-02 / batch B2b -- stalled and hard-deadline outcomes are failures that
carry their partial text.

Decision D2=(i): a generation that stalls or hits its hard deadline did not
complete, so the adapter reports success=False with failure_type stalled /
hard_deadline, and the partial text is preserved (in metadata["partial_output"],
exactly as B2a does for provider failures -- never in `output`, so a failed
generation cannot be consumed as content).

Scope of B2b:
  * ModelRouterAdapter: STALLED and HARD_DEADLINE leave the pinned set;
  * nothing else changes. route()'s classification, its answer text, the
    EMPTY_RESPONSE / COMPLETED_WITH_PARTIAL_OUTPUT pins (see
    test_fz02_provider_failure.py), the FZ-01 result channel and other adapters
    are untouched.

Method follows B2a: the real ModelRouter and the real ModelRouterAdapter; only
the provider stream and the execution budget are replaced.
"""
import asyncio

import pytest

import core.model_router as mr
from core.capabilities.adapters.model_router_adapter import ModelRouterAdapter
from core.capabilities.capability import CapabilityRequest, CapabilityType
from core.model_router import ModelRouter, RouteResult
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_outcome import ExecutionOutcome, FailureType

# An explicit word count sends route() down the monitored-streaming branch.
LONG_FORM = "write a short story of 1000 words, fantasy type"
PARTIAL = "Beginning the tale"


class _FakeContext:
    def __init__(self):
        self.cancellation_token = CancellationToken()
        self.metadata = {}

    def format_for_prompt(self, n, scope=None):
        return ""


# --- provider streams -----------------------------------------------------

async def _hangs_after_one_token(module_name, subtask, context, scope=""):
    yield PARTIAL
    await asyncio.sleep(9999)
    yield "unreachable"  # pragma: no cover


async def _hangs_before_any_token(module_name, subtask, context, scope=""):
    await asyncio.sleep(9999)
    yield "unreachable"  # pragma: no cover


async def _steady_but_endless(module_name, subtask, context, scope=""):
    n = 0
    while True:
        n += 1
        await asyncio.sleep(0.02)
        yield f"tok{n} "


# --- budgets that make each outcome deterministic and fast -----------------

def _stall_budget():
    # Progress arrives, then stops; no extension is allowed: STALL.
    return ExecutionBudget(startup_deadline_s=0.5, progress_deadline_s=0.05,
                           hard_ceiling_s=5.0, absolute_ceiling_s=5.0, max_extension_s=0.0)


def _hard_ceiling_budget():
    # Progress never stops, but the hard ceiling is tiny: HARD_DEADLINE with output.
    return ExecutionBudget(startup_deadline_s=5.0, progress_deadline_s=5.0,
                           hard_ceiling_s=0.3, absolute_ceiling_s=0.3, max_extension_s=0.0)


def _startup_budget():
    # No first token inside the startup window: HARD_DEADLINE without output.
    return ExecutionBudget(startup_deadline_s=0.05, progress_deadline_s=0.05,
                           hard_ceiling_s=5.0, absolute_ceiling_s=5.0, max_extension_s=0.0)


@pytest.fixture
def router(monkeypatch):
    """A real ModelRouter in bootstrap stage with persistence side effects neutralised."""
    monkeypatch.setattr(
        mr.config, "get_module_state",
        lambda name: {"stage": "bootstrap", "bootstrap_model": "mistral"})
    r = ModelRouter()

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(r, "_record_training_pair", _noop)
    monkeypatch.setattr(r, "_increment_query_count", lambda module: 1)
    monkeypatch.setattr(r, "_maybe_promote", lambda *a, **k: None)
    return r


def _arrange(monkeypatch, router, stream, budget):
    monkeypatch.setattr(router, "_stream_external", stream)
    monkeypatch.setattr(mr.ExecutionPolicy, "for_generation",
                        classmethod(lambda cls, **kw: budget))


def _request(context):
    return CapabilityRequest(
        capability_type=CapabilityType.LLM_COMPLETION,
        payload={"module_name": "coding", "subtask": LONG_FORM,
                 "context": context, "scope": ""})


async def _execute(router):
    return await asyncio.wait_for(
        ModelRouterAdapter(router).execute(_request(_FakeContext()), resources=None),
        timeout=5.0)


class _StubRouter:
    def __init__(self, route_result):
        self._route_result = route_result

    async def route(self, module_name, subtask, context, scope=""):
        return self._route_result


# --------------------------------------------------------------------------
# Adapter level: every combination of {stalled, hard_deadline} x {partial, none}
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("failure_type", [FailureType.STALLED, FailureType.HARD_DEADLINE])
@pytest.mark.parametrize("partial", ["half a story", None])
async def test_stalled_and_deadline_outcomes_fail_and_keep_their_partial(failure_type, partial):
    outcome = ExecutionOutcome.failure(failure_type, partial_output=partial)
    rr = RouteResult(answer=partial or "", source="external", execution_detail=outcome)
    result = await ModelRouterAdapter(_StubRouter(rr)).execute(_request(None), resources=None)

    assert result.success is False
    assert result.output is None                         # never consumable as content
    assert result.metadata["failure_type"] == failure_type.value
    assert result.metadata["retryable"] == outcome.retryable
    if partial is None:
        assert "partial_output" not in result.metadata
    else:
        assert result.metadata["partial_output"] == partial
        assert partial not in result.error               # the error text stays fixed/opaque
    assert result.error


# --------------------------------------------------------------------------
# End to end through the real router (the shapes the watchdog really produces)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_stalled_stream_fails_with_its_partial_text(router, monkeypatch):
    _arrange(monkeypatch, router, _hangs_after_one_token, _stall_budget())
    result = await _execute(router)
    assert result.success is False
    assert result.output is None
    assert result.metadata["failure_type"] == "stalled"
    assert result.metadata["retryable"] is True
    assert result.metadata["partial_output"] == PARTIAL


@pytest.mark.asyncio
async def test_a_stream_that_hits_the_hard_ceiling_fails_with_its_partial_text(router, monkeypatch):
    _arrange(monkeypatch, router, _steady_but_endless, _hard_ceiling_budget())
    result = await _execute(router)
    assert result.success is False
    assert result.output is None
    assert result.metadata["failure_type"] == "hard_deadline"
    assert result.metadata["partial_output"].startswith("tok1 tok2 ")


@pytest.mark.asyncio
async def test_a_stream_with_no_first_token_fails_without_partial_text(router, monkeypatch):
    _arrange(monkeypatch, router, _hangs_before_any_token, _startup_budget())
    result = await _execute(router)
    assert result.success is False
    assert result.output is None
    assert result.metadata["failure_type"] == "hard_deadline"   # nothing to have stalled from
    assert "partial_output" not in result.metadata


@pytest.mark.asyncio
async def test_route_itself_is_unchanged_it_still_returns_the_partial_text(router, monkeypatch):
    """B2b changes the adapter's verdict only: route()'s classification and its
    answer text (what streaming consumers see) are exactly as before."""
    _arrange(monkeypatch, router, _hangs_after_one_token, _stall_budget())
    routed = await asyncio.wait_for(router.route("coding", LONG_FORM, _FakeContext()), timeout=5.0)
    assert routed.execution_detail.failure_type == FailureType.STALLED
    assert routed.answer == PARTIAL
    assert routed.execution_detail.partial_output == PARTIAL
