import pytest
import os
import sys

# Ensure the root directory is in the python path for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True)
def _api_auth_opt_out(monkeypatch):
    """DEBT-025: the HTTP API is authenticated by default (interface/auth.py).

    The route-behaviour tests exercise handlers, not the boundary, so they opt out
    explicitly here.  tests/test_api_auth_boundary.py removes this override and
    tests the boundary itself.
    """
    from interface import auth, auth_audit

    class _NullAuditSink:
        """The opt-out waits for its audit record (interface/auth.py): give these tests a sink that
        stores nothing and always succeeds, so they see the opt-out take effect immediately.
        tests/test_api_auth_audit.py tests the real behaviour."""

        async def append(self, event_type, payload):
            return None

    auth_audit.set_sink(_NullAuditSink())
    monkeypatch.setenv(auth.ENV_MODE, auth.MODE_DISABLED)
    auth.reset_cache_for_tests()
    yield
    auth.reset_cache_for_tests()
    auth_audit.set_sink(None)


@pytest.fixture
def temp_data_dir(tmp_path):
    """
    Provides a temporary directory for tests that need to write to disk.
    """
    return str(tmp_path)
