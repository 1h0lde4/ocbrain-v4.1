import time

import pytest

from core.events.event_stream import SQLiteEventStore, StreamEvent


@pytest.mark.asyncio
async def test_sqlite_event_store_prunes_all_event_classes_past_retention(
    tmp_path,
):
    store = SQLiteEventStore(
        str(tmp_path / "events.db"), retention_seconds=10,
    )
    old_event = StreamEvent(
        event_type="workflow.checkpoint",
        checkpoint="workflow-1",
        timestamp=time.time() - 20,
        payload={"workflow_id": "workflow-1"},
    )
    recent_event = StreamEvent(
        event_type="execution.completed",
        timestamp=time.time(),
        payload={"execution_id": "exec-recent"},
    )

    old_sequence = await store.append(old_event)
    recent_sequence = await store.append(recent_event)
    assert await store.prune_expired() == 1
    assert await store.count() == 1

    replayed = [event async for event in store.replay()]
    assert [event.event_type for event in replayed] == ["execution.completed"]
    assert replayed[0].sequence == recent_sequence
    assert recent_sequence > old_sequence

    next_sequence = await store.append(StreamEvent(
        event_type="execution.failed",
        timestamp=time.time(),
        payload={"execution_id": "exec-next"},
    ))
    assert next_sequence > recent_sequence


@pytest.mark.asyncio
async def test_sqlite_event_store_runs_retention_sweep_during_append(tmp_path):
    store = SQLiteEventStore(
        str(tmp_path / "scheduled-events.db"), retention_seconds=10,
    )
    await store.append(StreamEvent(
        event_type="worker.progress",
        timestamp=time.time() - 20,
    ))
    store._last_retention_check -= store.RETENTION_CHECK_INTERVAL_SECONDS + 1

    await store.append(StreamEvent(
        event_type="worker.completed",
        timestamp=time.time(),
    ))

    assert await store.count() == 1
    replayed = [event async for event in store.replay()]
    assert [event.event_type for event in replayed] == ["worker.completed"]
