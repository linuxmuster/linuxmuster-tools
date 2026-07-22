import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

import pytest

import linuxmusterTools.common.parsers.sophomorix_log as sophomorix_log


@pytest.fixture(autouse=True)
def log_paths(tmp_path, monkeypatch):
    """
    Redirect the hardcoded sophomorix log paths to files inside the test's
    temporary directory, so tests can write arbitrary log content without
    touching the real system logs. The monkeypatch fixture automatically
    restores the original values after each test.
    """
    paths = {
        "kill": tmp_path / "user-kill.log",
        "add": tmp_path / "user-add.log",
        "update": tmp_path / "user-update.log",
    }
    monkeypatch.setattr(sophomorix_log, "KILL_LOG_PATH", str(paths["kill"]))
    monkeypatch.setattr(sophomorix_log, "ADD_LOG_PATH", str(paths["add"]))
    monkeypatch.setattr(sophomorix_log, "UPDATE_LOG_PATH", str(paths["update"]))
    return paths
