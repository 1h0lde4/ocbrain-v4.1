"""DEBT-025: durable authentication audit records (the owner's EventStream decision).

Rules under test:
* every opt-out transition (disable AND re-enable) is persisted;
* denials are persisted as bounded AGGREGATES (window, total, per-reason breakdown), never per request,
  and the existing log/event flood protection is unchanged;
* no credential is ever persisted;
* an audit-storage failure never makes authentication fail open: a pending ``api.auth_disabled`` record
  keeps the effective mode at "required", so the opt-out cannot silently succeed while its record is lost.

Nothing here is Windows or browser evidence; the sink is an in-memory recorder except in TestRealStore,
which uses the real SQLite-backed EventStream.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from pathlib import Path

import pytest

from interface import auth, auth_audit
from interface.api import app
from tests.test_api_auth_boundary import TOKEN, WRONG, bearer, call

DENIED = auth.EVENT_DENIED


class RecordingSink:
    """An in-memory audit sink with switchable failure modes."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []
        self.fail = False
        self.hang = False
        self.calls = 0

    async def append(self, event_type, payload):
        self.calls += 1
        if self.hang:
            await asyncio.sleep(3600)
        if self.fail:
            raise OSError("disk full")
        self.records.append((event_type, json.loads(json.dumps(dict(payload)))))  # must be JSON-serialisable


@pytest.fixture
def sink():
    s = RecordingSink()
    auth_audit.set_sink(s)       # conftest's autouse fixture restores the default afterwards
    return s


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth, "_clock", lambda: now[0])
    monkeypatch.setattr(auth, "_WINDOW_TIMER", False)    # the timer is tested separately, with a real loop
    return now


@pytest.fixture
def required(monkeypatch, tmp_path):
    monkeypatch.delenv(auth.ENV_MODE, raising=False)
    monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
    monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "api_token"))
    auth.reset_cache_for_tests()
    return TOKEN


@pytest.fixture
def opted_out(required, monkeypatch):
    """Configured as disabled (a token still exists, so the required settings can be built)."""
    monkeypatch.setenv(auth.ENV_MODE, "disabled")
    auth.reset_cache_for_tests()


def flush() -> bool:
    return asyncio.run(auth.flush_audit())


def aggregates(sink: RecordingSink) -> list[dict]:
    return [p for t, p in sink.records if t == DENIED]


class TestTransitionsArePersisted:
    def test_disable_enable_disable_each_leave_a_record_in_order(self, sink, required, monkeypatch):
        auth.get_settings(None)                                            # required at start: nothing to record
        for value in ("disabled", "required", "disabled"):
            monkeypatch.setenv(auth.ENV_MODE, value)
            auth.get_settings(None)
            assert flush() is True
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED, auth.EVENT_ENABLED, auth.EVENT_DISABLED]
        assert [(p["mode"], p["previous"]) for _, p in sink.records] == [
            ("disabled", "required"), ("required", "disabled"), ("disabled", "required")]
        for _, p in sink.records:
            assert p["schema"] == auth_audit.SCHEMA_VERSION and p["source"] == "env"
            assert isinstance(p["pid"], int) and p["at"].endswith("+00:00")
        assert len({p["transition_id"] for _, p in sink.records}) == 3

    def test_the_source_is_config_when_no_environment_override_is_set(self, sink, required, monkeypatch):
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        auth.get_settings("disabled")
        flush()
        assert sink.records[0][1]["source"] == "config"

    def test_a_started_disabled_server_records_its_start_state(self, sink, opted_out):
        auth.get_settings(None)
        assert flush() is True
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED]
        assert sink.records[0][1]["previous"] is None

    def test_no_credential_is_ever_persisted(self, sink, required, monkeypatch):
        auth.get_settings(None)
        monkeypatch.setenv(auth.ENV_MODE, "disabled"); auth.get_settings(None); flush()
        monkeypatch.setenv(auth.ENV_MODE, "required"); auth.get_settings(None); flush()
        blob = json.dumps(sink.records)
        assert TOKEN not in blob and "authorization" not in blob.lower() and "bearer" not in blob.lower()


class TestTheOptOutWaitsForItsRecord:
    """Disabling authentication must not silently succeed while its audit record is lost."""

    def test_a_failing_store_keeps_authentication_required(self, sink, opted_out, clock):
        sink.fail = True
        assert call(app, "GET", "/config")[0] == 401                       # configured disabled, still enforced
        assert call(app, "GET", "/config", bearer(TOKEN))[0] == 200
        assert sink.records == [] and auth.has_pending_audit()
        sink.fail = False
        clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
        assert call(app, "GET", "/config")[0] == 200                       # now the opt-out is in effect
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED]
        assert not auth.has_pending_audit()

    def test_a_hanging_store_cannot_hang_requests(self, sink, opted_out, monkeypatch):
        sink.hang = True
        monkeypatch.setattr(auth_audit, "AUDIT_TIMEOUT_S", 0.2)
        t0 = time.time()
        status = call(app, "GET", "/config")[0]
        assert status == 401 and time.time() - t0 < 2.0

    def test_a_dead_store_is_not_retried_on_every_request(self, sink, opted_out, clock):
        sink.fail = True
        for _ in range(5):
            assert call(app, "GET", "/config")[0] == 401
        assert sink.calls == 1                                              # backed off
        clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
        call(app, "GET", "/config")
        assert sink.calls == 2

    def test_the_failure_is_logged_loudly_and_without_secrets(self, sink, opted_out, clock, caplog):
        sink.fail = True
        with caplog.at_level(logging.ERROR):
            call(app, "GET", "/config")
        assert "STAYS REQUIRED" in caplog.text and "OSError" in caplog.text
        assert TOKEN not in caplog.text

    def test_a_failing_store_never_weakens_a_re_enable(self, sink, required, monkeypatch, clock):
        auth.get_settings(None)
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        assert call(app, "GET", "/config")[0] == 200                       # stored: the opt-out took effect
        sink.fail = True
        monkeypatch.setenv(auth.ENV_MODE, "required")
        assert call(app, "GET", "/config")[0] == 401                       # required at once, record or not
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED]
        sink.fail = False
        clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
        assert flush() is True
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED, auth.EVENT_ENABLED]

    def test_disable_then_enable_before_the_record_is_stored(self, sink, required, monkeypatch, clock):
        auth.get_settings(None)
        sink.fail = True
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        assert auth.get_settings(None).mode == auth.MODE_REQUIRED          # effective mode stays required
        monkeypatch.setenv(auth.ENV_MODE, "required")
        assert auth.get_settings(None).mode == auth.MODE_REQUIRED
        sink.fail = False
        clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
        assert flush() is True
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED, auth.EVENT_ENABLED]   # in order

    def test_the_enabled_mode_never_waits_for_anything(self, sink, required):
        sink.fail = True
        assert call(app, "GET", "/config")[0] == 401
        assert call(app, "GET", "/config", bearer(TOKEN))[0] == 200


class TestDenialAggregates:
    def _flood(self, mix):
        statuses = []
        for reason, n in mix.items():
            for _ in range(n):
                if reason == "missing":
                    statuses.append(call(app, "GET", "/config")[0])
                elif reason == "invalid":
                    statuses.append(call(app, "GET", "/config", bearer(WRONG))[0])
                else:
                    statuses.append(call(app, "GET", "/config", host="evil.example")[0])
        return statuses

    def test_one_aggregate_per_window_with_a_reason_breakdown(self, sink, required, clock):
        statuses = self._flood({"missing": 60, "invalid": 30, "host": 10})
        assert statuses.count(401) == 90 and statuses.count(400) == 10      # every request was still rejected
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        call(app, "GET", "/config")                                          # first denial of the next window closes this one
        assert flush() is True
        aggs = aggregates(sink)
        assert len(aggs) == 1
        a = aggs[0]
        assert a["kind"] == "aggregate" and a["total"] == 100
        assert a["by_reason"] == {"host": 10, "invalid": 30, "missing": 60}
        assert a["logged"] == auth.THROTTLE_BURST and a["suppressed"] == 100 - auth.THROTTLE_BURST
        assert a["window_seconds"] == auth.THROTTLE_WINDOW_S and a["schema"] == auth_audit.SCHEMA_VERSION

    def test_nothing_is_written_per_denial(self, sink, required, clock):
        for _ in range(300):
            call(app, "GET", "/config")
        assert sink.records == [] and sink.calls == 0
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        call(app, "GET", "/config")
        flush()
        assert len(aggregates(sink)) == 1 and aggregates(sink)[0]["total"] == 300

    def test_flood_protection_for_logs_is_unchanged(self, sink, required, clock, caplog):
        with caplog.at_level(logging.WARNING):
            for _ in range(100):
                call(app, "GET", "/config")
        assert sum(1 for r in caplog.records if r.getMessage().startswith("api.auth_denied reason=")) == auth.THROTTLE_BURST

    def test_a_quiet_final_window_is_flushed_by_the_timer(self, sink, required, monkeypatch):
        monkeypatch.setattr(auth, "THROTTLE_WINDOW_S", 0.2)
        auth.reset_cache_for_tests()

        async def main():
            async def downstream(scope, receive, send):
                raise AssertionError("every request here is denied")
            mw = auth.ApiAuthMiddleware(downstream)
            for _ in range(5):
                await _acall(mw)
            assert sink.records == []                                        # nothing yet: the window is open
            await asyncio.sleep(0.7)                                         # no further traffic at all

        asyncio.run(main())
        aggs = aggregates(sink)
        assert len(aggs) == 1 and aggs[0]["total"] == 5 and aggs[0]["by_reason"] == {"missing": 5}

    def test_aggregates_flush_in_the_background_never_in_the_request_path(self, sink, required, clock):
        for _ in range(3):
            call(app, "GET", "/config")
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        call(app, "GET", "/config")                                          # closes the first window: an aggregate is pending
        assert auth.has_pending_audit()
        sink.hang = True
        t0 = time.time()
        assert call(app, "GET", "/config", bearer(TOKEN))[0] == 200          # not blocked by the hanging store
        assert time.time() - t0 < 1.0

    def test_a_dead_store_changes_no_decision_and_its_losses_are_counted(self, sink, required, clock, monkeypatch):
        monkeypatch.setattr(auth_audit, "MAX_PENDING_AGGREGATES", 3)
        sink.fail = True
        for _ in range(6):                                                   # six windows, one denial each
            assert call(app, "GET", "/config")[0] == 401
            clock[0] += auth.THROTTLE_WINDOW_S + 1
        pending = [r for r in auth._pending if r["kind"] == "aggregate"]
        assert len(pending) <= 3                                             # bounded
        assert auth._audit_state["dropped_aggregates"] > 0                   # and the loss is visible, not silent
        sink.fail = False
        clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
        assert call(app, "GET", "/config")[0] == 401
        assert flush() is True
        assert any(a["dropped_aggregates"] > 0 for a in aggregates(sink))    # reported in a later record

    def test_aggregates_hold_only_counts(self, sink, required, clock):
        for hdr in ("SECRET-ATTEMPT-1", "SECRET-ATTEMPT-2"):
            call(app, "GET", "/x?token=" + hdr, bearer(hdr))
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        call(app, "GET", "/config")
        flush()
        blob = json.dumps(sink.records)
        assert "SECRET-ATTEMPT" not in blob and "/x" not in blob and "127.0.0.1" not in blob
        # aggregate_id (PR #112 review) is a random hex id so a duplicate after a timed-out append can be recognised;
        # it carries no information about any request.
        assert set(aggregates(sink)[0]) <= {"schema", "kind", "aggregate_id", "window_start", "window_end", "window_seconds",
                                            "total", "by_reason", "logged", "suppressed", "pid", "dropped_aggregates",
                                            "dropped_denials"}


async def _acall(mw, headers=(), host="localhost:7437"):
    from tests.test_api_auth_boundary import _scope
    sent = []
    done = asyncio.Event()
    delivered = []

    async def receive():
        if not delivered:
            delivered.append(1)
            return {"type": "http.request", "body": b"", "more_body": False}
        await done.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body"):
            done.set()

    await mw(_scope("GET", "/config", headers, host=host), receive, send)
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


class TestRealStore:
    """The real SQLite-backed EventStream, reopened from disk."""

    def test_records_survive_a_reopen_with_sequence_and_source(self, tmp_path, required, clock, monkeypatch):
        from core.events.event_stream import EventStream, SQLiteEventStore
        db = str(tmp_path / "stream.db")
        stream = EventStream(store=SQLiteEventStore(db))

        class StreamSink:
            async def append(self, event_type, payload):
                await stream.append(event_type, source=auth_audit.SOURCE, payload=dict(payload))

        auth_audit.set_sink(StreamSink())
        auth.get_settings(None)
        monkeypatch.setenv(auth.ENV_MODE, "disabled"); auth.get_settings(None); assert flush() is True
        monkeypatch.setenv(auth.ENV_MODE, "required"); auth.get_settings(None); assert flush() is True
        for _ in range(7):
            call(app, "GET", "/config")
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        call(app, "GET", "/config")
        assert flush() is True

        async def read_back():
            reopened = EventStream(store=SQLiteEventStore(db))
            return [e async for e in reopened.replay()]

        events = asyncio.run(read_back())
        assert [e.event_type for e in events] == [auth.EVENT_DISABLED, auth.EVENT_ENABLED, DENIED]
        assert {e.source for e in events} == {"ApiAuth"}
        assert [e.sequence for e in events] == sorted(e.sequence for e in events) and len({e.sequence for e in events}) == 3
        assert events[2].payload["total"] == 7 and events[2].payload["by_reason"] == {"missing": 7}
        assert TOKEN not in json.dumps([e.payload for e in events])

    def test_the_default_sink_writes_through_the_projects_event_stream(self, monkeypatch):
        import core.events.event_stream as es
        seen = []

        class Fake:
            async def append(self, event_type, *, source, payload):
                seen.append((event_type, source, dict(payload)))

        monkeypatch.setattr(es, "get_event_stream", lambda: Fake())
        asyncio.run(auth_audit.EventStreamSink().append("api.auth_disabled", {"mode": "disabled"}))
        assert seen == [("api.auth_disabled", "ApiAuth", {"mode": "disabled"})]

    def test_a_store_error_propagates_from_the_default_sink(self, monkeypatch):
        import core.events.event_stream as es

        class Broken:
            async def append(self, event_type, *, source, payload):
                raise OSError("database is locked")

        monkeypatch.setattr(es, "get_event_stream", lambda: Broken())
        with pytest.raises(OSError):
            asyncio.run(auth_audit.EventStreamSink().append("api.auth_disabled", {}))


class TestPlumbing:
    def test_schedule_flush_without_a_loop_is_a_noop(self, sink, required, monkeypatch):
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        auth.get_settings(None)
        auth.schedule_flush()                       # no running loop: must not raise or start anything
        assert sink.records == [] and auth.has_pending_audit()

    def test_schedule_flush_persists_on_a_running_loop(self, sink, required, monkeypatch):
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        auth.get_settings(None)

        async def main():
            auth.schedule_flush()
            await asyncio.sleep(0.1)

        asyncio.run(main())
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED]

    def test_setup_persists_a_disabled_start_state_without_a_request(self, sink, opted_out):
        import interface.api as api

        async def main():
            api.setup(object(), object())
            await asyncio.sleep(0.1)

        asyncio.run(main())
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED]


class TestDeliveryGuarantees:
    """Three guarantees the mutation review (Nov 2026) found unasserted in the first version of this file."""

    def test_traffic_alone_persists_a_re_enable_record(self, sink, required, monkeypatch):
        """No manual flush and no setup(): the request path itself schedules the background flush."""
        async def main():
            async def downstream(scope, receive, send):
                raise AssertionError("every request here is denied")
            mw = auth.ApiAuthMiddleware(downstream)
            monkeypatch.setenv(auth.ENV_MODE, "disabled")
            auth.get_settings(None)
            assert await auth.flush_audit() is True                      # the disable record is stored
            monkeypatch.setenv(auth.ENV_MODE, "required")
            assert await _acall(mw) == 401                               # this request notices the re-enable
            await asyncio.sleep(0.1)                                     # let the background flush run

        asyncio.run(main())
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED, auth.EVENT_ENABLED]

    def test_concurrent_flushes_append_each_record_exactly_once(self, required, monkeypatch):
        monkeypatch.setenv(auth.ENV_MODE, "disabled")

        async def main():
            gate = asyncio.Event()

            class Gated(RecordingSink):
                async def append(self, event_type, payload):
                    self.calls += 1
                    await gate.wait()
                    self.records.append((event_type, json.loads(json.dumps(dict(payload)))))

            gated = Gated()
            auth_audit.set_sink(gated)
            auth.get_settings(None)                                      # queues the disable record
            first = asyncio.ensure_future(auth.flush_audit())
            await asyncio.sleep(0.05)                                    # `first` is now inside append()
            second = await asyncio.wait_for(auth.flush_audit(), timeout=1.0)   # single-flight: returns at once
            assert second is False and gated.calls == 1
            gate.set()
            assert await first is True
            return gated

        gated = asyncio.run(main())
        assert [t for t, _ in gated.records] == [auth.EVENT_DISABLED] and gated.calls == 1

    def test_every_overflow_loss_is_reported_exactly_once(self, sink, required, clock, monkeypatch):
        monkeypatch.setattr(auth_audit, "MAX_PENDING_AGGREGATES", 3)
        sink.fail = True
        for _ in range(6):                                               # six windows, one denial each
            assert call(app, "GET", "/config")[0] == 401
            clock[0] += auth.THROTTLE_WINDOW_S + 1
        sink.fail = False
        clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
        assert call(app, "GET", "/config")[0] == 401                     # closes the sixth window: six aggregates in all
        assert flush() is True
        lost = 6 - 3                                                     # six aggregates were created, three fit
        got = aggregates(sink)
        assert sum(a["dropped_aggregates"] for a in got) + auth._audit_state["dropped_aggregates"] == lost
        assert sum(a["dropped_denials"] for a in got) + auth._audit_state["dropped_denials"] == lost


def drain(**kw) -> bool:
    return asyncio.run(auth.drain_audit(**kw))


class TestShutdownDrainAndIds:
    """PR #112 review: pending records must get one last bounded attempt at shutdown, duplicates must be
    identifiable, and the per-process limit of transition tracking is a documented, pinned fact."""

    def test_drain_turns_the_open_window_into_an_aggregate_and_stores_it(self, sink, required, clock):
        for _ in range(2):
            assert call(app, "GET", "/config")[0] == 401
        assert aggregates(sink) == []                                    # the window is still open: nothing stored yet
        assert drain() is True
        got = aggregates(sink)
        assert len(got) == 1 and got[0]["total"] == 2

    def test_drain_ignores_the_retry_backoff_for_one_last_attempt(self, sink, opted_out, clock):
        sink.fail = True
        auth.get_settings(None)                                          # queues the disable record
        assert flush() is False                                          # fails and sets the backoff
        sink.fail = False
        assert flush() is False and sink.records == []                   # still inside the backoff
        assert drain() is True
        assert [t for t, _ in sink.records] == [auth.EVENT_DISABLED]

    def test_drain_is_bounded_and_never_raises_when_the_store_hangs(self, sink, opted_out, clock, monkeypatch, caplog):
        monkeypatch.setattr(auth_audit, "AUDIT_TIMEOUT_S", 5.0)          # one append would outlast the drain
        monkeypatch.setattr(auth_audit, "AUDIT_DRAIN_TIMEOUT_S", 0.2)
        sink.hang = True
        auth.get_settings(None)
        t0 = time.monotonic()
        with caplog.at_level(logging.ERROR):
            assert drain() is False
        assert time.monotonic() - t0 < 2.0
        assert auth.has_pending_audit()                                  # nothing is dropped silently ...
        assert "could not be persisted at shutdown" in caplog.text       # ... and the loss is logged

    def test_drain_gives_up_at_the_first_failure_instead_of_spinning(self, sink, opted_out, clock):
        sink.fail = True
        auth.get_settings(None)
        t0 = time.monotonic()
        assert drain() is False
        assert time.monotonic() - t0 < 1.0 and sink.calls == 1           # one attempt, not a loop to the deadline

    def test_drain_waits_for_an_append_already_in_flight(self, required, monkeypatch):
        monkeypatch.setenv(auth.ENV_MODE, "disabled")

        async def main():
            gate = asyncio.Event()

            class Gated(RecordingSink):
                async def append(self, event_type, payload):
                    self.calls += 1
                    await gate.wait()
                    self.records.append((event_type, json.loads(json.dumps(dict(payload)))))

            gated = Gated()
            auth_audit.set_sink(gated)
            auth.get_settings(None)
            first = asyncio.ensure_future(auth.flush_audit())
            await asyncio.sleep(0.05)                                    # `first` is inside append()
            d = asyncio.ensure_future(auth.drain_audit())
            await asyncio.sleep(0.05)
            assert not d.done()                                          # waiting for it, not giving up
            gate.set()
            assert await d is True and await first is True
            return gated

        gated = asyncio.run(main())
        assert [t for t, _ in gated.records] == [auth.EVENT_DISABLED] and gated.calls == 1

    def test_aggregate_ids_identify_a_duplicate_after_a_timed_out_append(self, required, clock):
        class LandsThenFails(RecordingSink):
            first = True

            async def append(self, event_type, payload):
                await super().append(event_type, payload)                # the write lands ...
                if self.first and event_type == DENIED:
                    self.first = False
                    raise TimeoutError("the caller gave up")             # ... but the caller sees a timeout

        s = LandsThenFails()
        auth_audit.set_sink(s)
        assert call(app, "GET", "/config")[0] == 401
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        assert call(app, "GET", "/config")[0] == 401                     # closes window 1: aggregate A1
        assert flush() is False                                          # A1 landed, then the call "timed out"
        clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
        assert flush() is True                                           # A1 is retried: a duplicate in the store
        dup = aggregates(s)
        assert len(dup) == 2 and dup[0]["aggregate_id"] == dup[1]["aggregate_id"]
        assert re.fullmatch(r"[0-9a-f]{32}", dup[0]["aggregate_id"])
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        assert call(app, "GET", "/config")[0] == 401                     # closes window 2: aggregate A2
        assert flush() is True
        assert len({a["aggregate_id"] for a in aggregates(s)}) == 2      # another window, another id

    def test_main_drains_the_audit_queue_before_it_closes_the_orchestrator(self):
        src = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        assert src.count("await _api_auth.drain_audit()") == 1
        at = src.index("await _api_auth.drain_audit()")
        assert at < src.index("await orchestrator.close()")
        assert src.rindex("finally:", 0, at) > src.index("asyncio.gather(server.serve()")   # inside the exit path

    def test_a_restart_into_required_mode_writes_no_record_documented_limit(self, sink, required):
        """Report section 6 item 16: transitions are tracked per process. A process that starts in 'required' mode
        cannot know the previous one was disabled, so a disabled period that ends across a restart has no
        api.auth_enabled. If a startup record or a restored previous mode is ever added, change this on purpose."""
        auth.get_settings(None)
        assert flush() is True and sink.records == []


class TestSuppressionSummaryAndFinalLoss:
    """Second review (Nov 25): 112-R1 the flood-protection summary must survive the window timer;
    112-R2 the last overflow loss must reach a durable record at shutdown, not stay in memory."""

    def test_the_suppression_summary_is_emitted_when_a_later_denial_closes_the_window(self, sink, required, clock, monkeypatch, caplog):
        seen = []
        monkeypatch.setattr(auth, "_emit", lambda event, payload: seen.append((event, dict(payload))))
        for _ in range(auth.THROTTLE_BURST + 5):
            assert call(app, "GET", "/config")[0] == 401
        clock[0] += auth.THROTTLE_WINDOW_S + 1
        with caplog.at_level(logging.WARNING):
            call(app, "GET", "/config")                                  # this denial closes the window
        summaries = [p for e, p in seen if e == auth.EVENT_DENIED and p.get("reason") == auth.REASON_THROTTLED]
        assert summaries == [{"reason": auth.REASON_THROTTLED, "count": 5}]
        assert "5 further denials were suppressed" in caplog.text
        flush()
        assert aggregates(sink)[0]["suppressed"] == 5

    def test_the_suppression_summary_survives_the_window_timer(self, sink, required, monkeypatch, caplog):
        """The timer closes a quiet window; it must emit the same summary, exactly once, not just persist a count."""
        monkeypatch.setattr(auth, "THROTTLE_WINDOW_S", 0.2)
        auth.reset_cache_for_tests()
        seen = []
        monkeypatch.setattr(auth, "_emit", lambda event, payload: seen.append((event, dict(payload))))

        async def main():
            async def downstream(scope, receive, send):
                raise AssertionError("every request here is denied")
            mw = auth.ApiAuthMiddleware(downstream)
            for _ in range(auth.THROTTLE_BURST + 5):
                await _acall(mw)
            await asyncio.sleep(0.7)                                     # no traffic: the timer closes the window
            await _acall(mw)                                             # a later denial must not repeat the summary

        with caplog.at_level(logging.WARNING):
            asyncio.run(main())
        summaries = [p for e, p in seen if e == auth.EVENT_DENIED and p.get("reason") == auth.REASON_THROTTLED]
        assert summaries == [{"reason": auth.REASON_THROTTLED, "count": 5}]
        assert caplog.text.count("further denials were suppressed") == 1
        assert aggregates(sink)[0]["suppressed"] == 5

    def test_the_last_overflow_loss_is_persisted_at_shutdown(self, sink, required, clock, monkeypatch):
        monkeypatch.setattr(auth_audit, "MAX_PENDING_AGGREGATES", 3)
        sink.fail = True
        for _ in range(6):                                               # six windows, one denial each
            assert call(app, "GET", "/config")[0] == 401
            clock[0] += auth.THROTTLE_WINDOW_S + 1
        sink.fail = False
        assert drain() is True                                           # closes window six; no further traffic follows
        got = aggregates(sink)
        lost = 6 - 3                                                     # six aggregates were created, three fit
        assert sum(a["dropped_aggregates"] for a in got) == lost         # durably reported ...
        assert sum(a["dropped_denials"] for a in got) == lost
        assert auth._audit_state["dropped_aggregates"] == 0 and auth._audit_state["dropped_denials"] == 0   # ... none left in memory

    def test_overflow_losses_are_reported_even_when_no_aggregate_is_pending(self, sink, required, clock):
        auth._audit_state["dropped_aggregates"], auth._audit_state["dropped_denials"] = 2, 7   # losses nobody has reported yet
        assert drain() is True
        got = aggregates(sink)
        assert len(got) == 1 and got[0]["total"] == 0
        assert (got[0]["dropped_aggregates"], got[0]["dropped_denials"]) == (2, 7)
        assert auth._audit_state["dropped_aggregates"] == 0


class TestEventSemanticsAndTimedOutAppends:
    """Third review (Nov 25): what a notification means, and what a timed-out append really does."""

    def test_the_bus_announcement_of_an_opt_out_says_what_is_actually_enforced(self, sink, required, monkeypatch):
        seen = []
        monkeypatch.setattr(auth, "_emit", lambda event, payload: seen.append((event, dict(payload))))
        sink.fail = True
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        assert auth.get_settings(None).mode == auth.MODE_REQUIRED
        monkeypatch.setenv(auth.ENV_MODE, "required")
        auth.get_settings(None)
        disabled = next(p for e, p in seen if e == auth.EVENT_DISABLED)
        enabled = next(p for e, p in seen if e == auth.EVENT_ENABLED)
        assert disabled["mode"] == auth.MODE_DISABLED and disabled["effective"] == auth.MODE_REQUIRED   # requested, not enforced
        assert enabled["mode"] == auth.MODE_REQUIRED and enabled["effective"] == auth.MODE_REQUIRED

    def test_a_timed_out_append_that_keeps_running_in_its_thread_is_retried_without_loss(self, required, clock, monkeypatch):
        """The EventStream appends in an executor thread; cancelling the asyncio waiter does not stop that thread, so the
        first write can still land.  Delivery is at-least-once: the record is retried, never lost, and a duplicate
        carries the same transition_id."""
        monkeypatch.setattr(auth_audit, "AUDIT_TIMEOUT_S", 0.05)
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        threaded = ThreadedSink(slow_first=0.3)
        auth_audit.set_sink(threaded)
        auth.get_settings(None)                                           # queues the disable record

        async def main():
            assert await auth.flush_audit() is False                      # the waiter gave up after 0.05 s ...
            assert auth.has_pending_audit()                               # ... so the record is still pending
            await asyncio.sleep(0.5)                                      # the first thread finishes and commits anyway
            assert len(threaded.records) == 1
            clock[0] += auth_audit.AUDIT_RETRY_BACKOFF_S + 1
            assert await auth.flush_audit() is True

        asyncio.run(main())
        assert [t for t, _ in threaded.records] == [auth.EVENT_DISABLED, auth.EVENT_DISABLED]      # a duplicate, never a loss
        assert threaded.records[0][1]["transition_id"] == threaded.records[1][1]["transition_id"]  # and it is recognisable
        assert not auth.has_pending_audit()

    def test_single_flight_is_per_coroutine_not_per_storage_operation_documented_limit(self, required, monkeypatch):
        """Report section 6 item 12: a retry can start while the timed-out first write is still running in its thread, so
        two storage operations overlap.  Pinned so that a change here is deliberate."""
        monkeypatch.setattr(auth_audit, "AUDIT_TIMEOUT_S", 0.05)
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        threaded = ThreadedSink(slow_first=0.3)
        auth_audit.set_sink(threaded)
        auth.get_settings(None)

        async def main():
            assert await auth.flush_audit() is False
            assert await auth.flush_audit(force=True) is True             # starts while the first thread still runs
            await asyncio.sleep(0.5)

        asyncio.run(main())
        assert threaded.peak == 2, "the two writes overlapped"
        assert len(threaded.records) == 2


class ThreadedSink:
    """A sink whose append runs its blocking write in an executor thread, as the real EventStream does."""

    def __init__(self, slow_first: float = 0.0) -> None:
        self.records, self.calls, self.in_flight, self.peak = [], 0, 0, 0
        self.slow_first, self._lock = slow_first, threading.Lock()

    async def append(self, event_type, payload):
        self.calls += 1
        delay = self.slow_first if self.calls == 1 else 0.0
        await asyncio.get_running_loop().run_in_executor(None, self._write, event_type, dict(payload), delay)

    def _write(self, event_type, payload, delay):
        with self._lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
        time.sleep(delay)
        with self._lock:
            self.records.append((event_type, json.loads(json.dumps(payload))))
            self.in_flight -= 1
