"""
core/error_ref.py -- opaque references for failures whose text reaches a caller.

Anything that lands in an HTTP response, an SSE event or an answer string the
caller reads must not carry raw exception text: it can hold filesystem paths,
hosts and URLs, config values and other implementation detail (CWE-209/497).
log_and_ref() logs the real exception -- message and traceback -- server-side
under a fresh id and returns only that id, so the caller can quote it and an
operator can find the log line.

Callers decide what else, if anything, is safe to show. The convention so far
is the module or component name plus type(exc).__name__, e.g.
"[Error in web_search: ConnectError (ref <uuid>)]".

interface/api.py (_log_and_redact) and core/brain_api.py predate this helper
and keep their own equivalents; they are not changed here.
"""
import logging
import uuid


def log_and_ref(logger: logging.Logger, context: str, exc: BaseException) -> str:
    """Log exc with its traceback under a new id and return that id."""
    ref = str(uuid.uuid4())
    logger.error("%s failed; error_id=%s", context, ref, exc_info=exc)
    return ref
