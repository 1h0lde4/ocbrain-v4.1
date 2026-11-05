import pytest
import os
import sys

# Ensure the root directory is in the python path for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Rev 3 (G4-FTS remediation) — Amendment 1 §E: the SQLite WAL runtime gate
# defaults to "enforce", which refuses memory-backend construction on an
# affected runtime (the one bundled with this interpreter is affected — see
# docs/reports/G4_FTS_REV3_REMEDIATION_REPORT.md). The whole test suite must
# still run: it acknowledges the runtime EXPLICITLY. Under "acknowledge" the
# gate never lies: every readiness report stays
# `ready_degraded_runtime_not_supported` with memory_ready=False, and the
# dedicated runtime-gate tests below remove the variable to prove the
# refusal itself.
#
# THIS IS A TEST-ENV-ONLY setting. It is NOT a production recommendation:
# production must either upgrade the runtime, install a documented backport,
# or register verified vendor-build provenance (Amendment 1 §D / report §R1).
os.environ.setdefault("OCBRAIN_MEMORY_RUNTIME_ACK", "acknowledge")


@pytest.fixture
def temp_data_dir(tmp_path):
    """
    Provides a temporary directory for tests that need to write to disk.
    """
    return str(tmp_path)


@pytest.fixture
def enforce_runtime_gate(monkeypatch):
    """
    Remove the suite-wide acknowledgement so a test can observe the default
    fail-closed behavior (constructor raises
    MemoryRuntimeCompatibilityError on an affected runtime).
    """
    monkeypatch.delenv("OCBRAIN_MEMORY_RUNTIME_ACK", raising=False)
    return monkeypatch
