import json
import logging
import time
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Any, Optional, Iterator

# Setup a dedicated logger for traces
logger = logging.getLogger("ocbrain.tracer")
logger.setLevel(logging.INFO)
# Avoid double logging if handlers are already attached
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)

# ContextVar for async-safe request-level trace_id propagation
_current_trace_id: ContextVar[Optional[str]] = ContextVar("current_trace_id", default=None)

def set_trace_id(trace_id: Optional[str]) -> None:
    """Explicitly set a trace ID for the current context.
    Pass None to clear the current trace ID (a new one will be generated on next use).
    """
    _current_trace_id.set(trace_id)

def get_trace_id() -> str:
    """Get the current trace ID, or generate a new one if none exists."""
    trace_id = _current_trace_id.get()
    if not trace_id:
        trace_id = str(uuid.uuid4())
        _current_trace_id.set(trace_id)
    return trace_id

@contextmanager
def span(name: str, **metadata: Any) -> Iterator[None]:
    """
    Context manager to trace execution of a block of code.
    
    Example:
        with tracer.span("classifier", model="gpt-4", tokens=100):
            classify(query)
    """
    trace_id = get_trace_id()
    start_time = time.perf_counter()
    
    try:
        yield
    finally:
        end_time = time.perf_counter()
        duration_ms = int((end_time - start_time) * 1000)
        
        log_entry = {
            "trace_id": trace_id,
            "span": name,
            "duration_ms": duration_ms,
            "metadata": metadata
        }
        
        logger.info(json.dumps(log_entry))

def trace_function(name: Optional[str] = None, **metadata: Any):
    """
    Decorator to wrap functions with tracing.
    
    Example:
        @trace_function(name="classifier_exec")
        def classify(query):
            ...
    """
    def decorator(func):
        span_name = name or func.__name__
        def wrapper(*args, **kwargs):
            with span(span_name, **metadata):
                return func(*args, **kwargs)
        return wrapper
    return decorator

# Provide an async decorator as well if needed
def async_trace_function(name: Optional[str] = None, **metadata: Any):
    def decorator(func):
        span_name = name or func.__name__
        async def wrapper(*args, **kwargs):
            trace_id = get_trace_id()
            start_time = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                end_time = time.perf_counter()
                duration_ms = int((end_time - start_time) * 1000)
                log_entry = {
                    "trace_id": trace_id,
                    "span": span_name,
                    "duration_ms": duration_ms,
                    "metadata": metadata
                }
                logger.info(json.dumps(log_entry))
        return wrapper
    return decorator
