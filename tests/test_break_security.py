import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from modules.system_ctrl.module import _safe_path, SAFE_ROOT

def test_sandbox_neighbor_escape():
    # Setup: Create a "neighbor" directory that starts with the same prefix as SAFE_ROOT
    parent = SAFE_ROOT.parent
    neighbor_name = SAFE_ROOT.name + "_secret"
    neighbor_dir = parent / neighbor_name
    neighbor_dir.mkdir(exist_ok=True)
    
    secret_file = neighbor_dir / "passwords.txt"
    secret_file.write_text("my_secret_password")
    
    try:
        # This SHOULD fail, but if we use simple string prefix matching, it might pass
        # because neighbor_dir starts with SAFE_ROOT's string representation.
        escaped_path = _safe_path(str(neighbor_dir / "passwords.txt"))
        print(f"\nVULNERABILITY CONFIRMED: Accessed {escaped_path}")
        assert False, f"Sandbox escaped! Accessed neighbor directory: {neighbor_dir}"
    except PermissionError:
        print("\nSandbox held: Access denied to neighbor directory.")
        assert True
    finally:
        # Cleanup
        if secret_file.exists(): secret_file.unlink()
        if neighbor_dir.exists(): neighbor_dir.rmdir()

if __name__ == "__main__":
    try:
        test_sandbox_neighbor_escape()
    except AssertionError as e:
        print(e)
    except Exception as e:
        print(f"Test failed with error: {e}")
