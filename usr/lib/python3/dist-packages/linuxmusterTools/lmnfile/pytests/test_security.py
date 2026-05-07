"""
Tests for check_allowed_path: verify path whitelisting and traversal protection.
"""

import pytest
import linuxmusterTools.lmnfile.lmnfile as lmnfile_module
from linuxmusterTools.lmnfile import LMNFile


def test_allowed_path_does_not_raise(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')
    # Should not raise — tmp_path is in ALLOWED_PATHS (patched by conftest)
    lmn = LMNFile(str(f), 'r')
    assert lmn is not None


def test_disallowed_path_raises_ioerror(tmp_path, monkeypatch):
    monkeypatch.setattr(lmnfile_module, 'ALLOWED_PATHS', [])
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')
    with pytest.raises(IOError, match='Access refused'):
        LMNFile(str(f), 'r')


def test_path_outside_allowed_raises(tmp_path, monkeypatch, tmp_path_factory):
    other = tmp_path_factory.mktemp('other')
    # Allow only tmp_path, not other
    monkeypatch.setattr(lmnfile_module, 'ALLOWED_PATHS', [str(tmp_path)])
    f = other / 'config.yml'
    f.write_text('key: value\n')
    with pytest.raises(IOError, match='Access refused'):
        LMNFile(str(f), 'r')


def test_path_with_dotdot_raises(tmp_path):
    # Even if the base is allowed, a path containing .. must be blocked
    f = tmp_path / 'subdir' / '..' / 'config.yml'
    target = tmp_path / 'config.yml'
    target.write_text('key: value\n')
    with pytest.raises(IOError, match='Access refused'):
        LMNFile(str(f), 'r')
