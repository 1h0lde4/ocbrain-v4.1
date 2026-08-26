import time

from core.runtime.progress_monitor import ProgressMonitor, ProgressState


def test_initial_state_is_pending():
    m = ProgressMonitor()
    assert m.state == ProgressState.PENDING
    assert not m.has_progressed()


def test_start_moves_to_active():
    m = ProgressMonitor()
    m.start()
    assert m.state == ProgressState.ACTIVE


def test_report_activity_does_not_count_as_progress():
    """A pathological provider sending meaningless keepalive traffic must
    not be able to postpone stall detection just by 'looking active.'"""
    m = ProgressMonitor()
    m.start()
    m.report_activity()
    m.report_activity()
    assert not m.has_progressed()
    assert m.snapshot().activity_count == 2
    assert m.snapshot().progress_count == 0


def test_report_progress_moves_to_progressing_and_records_timestamps():
    m = ProgressMonitor()
    m.start()
    m.report_progress(units=10)
    snap = m.snapshot()
    assert m.state == ProgressState.PROGRESSING
    assert m.has_progressed()
    assert snap.progress_count == 1
    assert snap.output_size == 10
    assert snap.first_progress_at is not None
    assert snap.last_progress_at is not None


def test_since_last_progress_s_resets_on_new_progress():
    m = ProgressMonitor()
    m.start()
    m.report_progress()
    time.sleep(0.05)
    first_gap = m.since_last_progress_s()
    m.report_progress()
    second_gap = m.since_last_progress_s()
    assert first_gap >= 0.05
    assert second_gap < first_gap


def test_since_last_progress_s_is_zero_before_any_progress():
    m = ProgressMonitor()
    m.start()
    assert m.since_last_progress_s() == 0.0


def test_negative_units_are_not_subtracted():
    m = ProgressMonitor()
    m.start()
    m.report_progress(units=-100)
    assert m.snapshot().output_size == 0


def test_throughput_none_until_two_progress_events_with_elapsed_time():
    m = ProgressMonitor()
    m.start()
    assert m.throughput_per_sec() is None
    m.report_progress(units=5)
    # first_progress_at == last_progress_at on the very first event -> elapsed 0
    assert m.throughput_per_sec() is None


def test_throughput_computed_after_multiple_events():
    m = ProgressMonitor()
    m.start()
    m.report_progress(units=5)
    time.sleep(0.05)
    m.report_progress(units=5)
    tps = m.throughput_per_sec()
    assert tps is not None
    assert tps > 0


def test_terminal_state_transitions():
    for method, expected in [
        ("complete", ProgressState.COMPLETED),
        ("fail", ProgressState.FAILED),
        ("cancel", ProgressState.CANCELLED),
    ]:
        m = ProgressMonitor()
        m.start()
        getattr(m, method)()
        assert m.state == expected


def test_mark_waiting_and_stalled_and_recovering():
    m = ProgressMonitor()
    m.start()
    m.mark_waiting()
    assert m.state == ProgressState.WAITING
    m.mark_stalled()
    assert m.state == ProgressState.STALLED
    m.mark_recovering()
    assert m.state == ProgressState.RECOVERING


def test_snapshot_is_a_stable_read_not_a_live_reference():
    m = ProgressMonitor()
    m.start()
    m.report_progress(units=1)
    snap1 = m.snapshot()
    m.report_progress(units=1)
    assert snap1.progress_count == 1  # unaffected by the later report_progress call
