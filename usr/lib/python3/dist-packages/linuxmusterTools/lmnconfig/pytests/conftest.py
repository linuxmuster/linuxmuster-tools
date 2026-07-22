import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest


class FakeLMNFile:
    """
    Stand-in for linuxmusterTools.lmnfile.LMNFile used to test the config
    classes in lmnconfig/ without ever touching the real filesystem.

    Real LMNFile instances (in particular YAMLLoader) create the target file
    on disk if it does not already exist when opened for reading, which is
    exactly what we must NOT do when the hardcoded production paths
    (/etc/linuxmuster/..., /var/lib/linuxmuster/...) don't exist in the test
    environment. So instead of letting os.path.isfile lie about a production
    path and then really instantiating LMNFile, we replace LMNFile itself
    with this fake for the duration of the "file found" tests.
    """

    def __init__(self, data):
        self._data = data
        self.data = data

    def __call__(self, path, mode, *args, **kwargs):
        self.path = path
        self.mode = mode
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def read(self):
        return self._data


@pytest.fixture
def fake_lmnfile():
    """
    Factory fixture: call with the canned data the fake file should
    "contain" and get back a callable that behaves like the LMNFile
    constructor (usable directly with monkeypatch.setattr(module, 'LMNFile', ...)).
    """
    def _make(data):
        return FakeLMNFile(data)
    return _make


def isfile_only_for(expected_path):
    """
    Build a fake os.path.isfile that returns True only for the exact
    expected_path, and delegates to the real os.path.isfile for anything
    else, so we never accidentally lie about unrelated paths the test
    process might check.
    """
    real_isfile = os.path.isfile

    def _fake(path):
        if path == expected_path:
            return True
        return real_isfile(path)
    return _fake
