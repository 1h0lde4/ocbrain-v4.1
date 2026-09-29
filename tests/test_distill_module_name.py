"""
tests/test_distill_module_name.py -- POST /distill path traversal.

module_name came straight from the request body (DistillRequest) into
learning/distiller.py, where _save_pairs did
`(DATA_RAW / module_name).mkdir(parents=True)` and wrote distil_*.json
files there. Nothing validated it, so a name like "../../x" created a
directory (and, when the model returned parseable pairs, JSON files)
outside data/raw. Found by asking CodeQL where its remaining
py/path-injection flows *start*: they start at HTTP handler parameters
(interface/api.py), not at internal registry values. /train/{module_name}
is guarded by an `in _orchestrator.modules` allowlist and /modules/new by
factory_create's .isidentifier() check; /distill had neither.

Reproduced first against the unfixed code (directory created outside
data/raw with Ollama unreachable and zero pairs generated), then fixed
with the same .isidentifier() convention used elsewhere.
"""
import asyncio  # noqa: F401  (pytest-asyncio auto mode)

import pytest
from fastapi import HTTPException

import interface.api as api_module
import learning.distiller as distiller

TRAVERSAL = "../../escaped_by_request"


def _outside(tmp_path, raw):
    return sorted(
        str(p.relative_to(tmp_path))
        for p in tmp_path.rglob("*")
        if raw not in p.parents and p not in (raw, raw.parent)
    )


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    monkeypatch.setattr(distiller, "DATA_RAW", raw)
    return raw


def test_save_pairs_rejects_traversal_and_creates_nothing(tmp_path, raw_dir):
    with pytest.raises(ValueError, match="Invalid module_name"):
        distiller._save_pairs(TRAVERSAL, "topic", [{"query": "q", "answer": "a"}])
    assert _outside(tmp_path, raw_dir) == []


def test_save_pairs_still_saves_for_a_legitimate_name(tmp_path, raw_dir):
    n = distiller._save_pairs(
        "finance_helper", "topic", [{"query": "q", "answer": "a"}]
    )
    assert n == 1
    assert len(list((raw_dir / "finance_helper").glob("distil_*.json"))) == 1
    assert _outside(tmp_path, raw_dir) == []


@pytest.mark.asyncio
async def test_distill_topic_rejects_before_any_model_call(monkeypatch, raw_dir):
    def _no_network(*a, **kw):
        raise AssertionError("distill_topic contacted the model before validating")

    monkeypatch.setattr(distiller.httpx, "AsyncClient", _no_network)
    with pytest.raises(ValueError, match="Invalid module_name"):
        await distiller.distill_topic(TRAVERSAL, "topic", num_pairs=1)


@pytest.mark.asyncio
async def test_distill_endpoint_returns_400_and_creates_nothing(tmp_path, raw_dir):
    req = api_module.DistillRequest(module_name=TRAVERSAL, topic="x", num_pairs=1)
    with pytest.raises(HTTPException) as exc:
        await api_module.distill(req)
    assert exc.value.status_code == 400
    assert TRAVERSAL not in exc.value.detail  # fixed message, no echo of input
    assert _outside(tmp_path, raw_dir) == []


# ── Second surface: POST /brain/v2/distill (core/brain_api.py) ──────────
#
# core/brain_api.py exposes its own /distill under the /brain/v2 prefix,
# with the same request shape, calling the same distill_topic(). Found
# because an outside review said it existed (its cited source was an
# unrelated repository, so it was verified in the code, not on that
# citation). Reproduced against unfixed source: HTTP 200 and a directory
# created outside data/raw. Guarding the sink already blocked it; this
# route additionally returns a clean 400 instead of an unhandled 500.

def _v2_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core.brain_api import register

    app = FastAPI()
    register(app, {})
    return TestClient(app, raise_server_exceptions=False)


def test_brain_v2_distill_returns_400_and_creates_nothing(tmp_path, raw_dir):
    r = _v2_client().post(
        "/brain/v2/distill",
        json={"module_name": TRAVERSAL, "topic": "x", "num_pairs": 1},
    )
    assert r.status_code == 400, r.text
    assert TRAVERSAL not in r.text  # fixed message, no echo of the input
    assert _outside(tmp_path, raw_dir) == []
