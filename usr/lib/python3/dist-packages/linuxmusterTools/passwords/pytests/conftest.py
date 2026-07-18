import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
import linuxmusterTools.lmnfile.lmnfile as lmnfile_module


@pytest.fixture(autouse=True)
def patch_allowed_paths(tmp_path, monkeypatch):
    """
    Replace ALLOWED_PATHS with the test's temporary directory so every test
    can read and write config files without needing real system paths.
    """
    monkeypatch.setattr(lmnfile_module, 'ALLOWED_PATHS', [str(tmp_path)])
