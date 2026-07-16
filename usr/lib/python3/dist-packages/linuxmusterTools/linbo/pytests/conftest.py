import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
import linuxmusterTools.lmnfile.lmnfile as lmnfile_module
import linuxmusterTools.linbo.config as config_module


@pytest.fixture(autouse=True)
def patch_linbo_paths(tmp_path, monkeypatch):
    """
    Point LINBO_PATH/GRUB_DIR_DEFAULT to the test's temporary directory, and
    relax LMNFile's allowed-paths check accordingly, so tests never touch
    real system paths (e.g. /srv/linbo).
    """
    grub_dir = tmp_path / 'boot' / 'grub'
    grub_dir.mkdir(parents=True)

    monkeypatch.setattr(config_module, 'LINBO_PATH', str(tmp_path))
    monkeypatch.setattr(config_module, 'GRUB_DIR_DEFAULT', str(grub_dir))
    monkeypatch.setattr(lmnfile_module, 'ALLOWED_PATHS', [str(tmp_path)])
