import pytest
import asyncio
import os
import sys

# Ensure the root directory is in the python path for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def temp_data_dir(tmp_path):
    """
    Provides a temporary directory for tests that need to write to disk.
    """
    return str(tmp_path)
