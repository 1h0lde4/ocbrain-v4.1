import json
import logging
from core.observability.tracer import span, trace_function, get_trace_id, set_trace_id

def test_span_context_manager(caplog):
    caplog.set_level(logging.INFO, logger="ocbrain.tracer")
    
    with span("test_span", key="value"):
        pass

    assert len(caplog.records) == 1
    log_record = json.loads(caplog.records[0].message)
    
    assert log_record["span"] == "test_span"
    assert "trace_id" in log_record
    assert log_record["metadata"] == {"key": "value"}
    assert "duration_ms" in log_record
    assert log_record["duration_ms"] >= 0

def test_trace_function_decorator(caplog):
    caplog.set_level(logging.INFO, logger="ocbrain.tracer")
    
    @trace_function(name="decorated_span", extra="info")
    def my_func():
        return 42

    result = my_func()
    assert result == 42
    
    assert len(caplog.records) == 1
    log_record = json.loads(caplog.records[0].message)
    
    assert log_record["span"] == "decorated_span"
    assert log_record["metadata"] == {"extra": "info"}

def test_trace_id_propagation():
    set_trace_id("custom-trace-id")
    assert get_trace_id() == "custom-trace-id"
