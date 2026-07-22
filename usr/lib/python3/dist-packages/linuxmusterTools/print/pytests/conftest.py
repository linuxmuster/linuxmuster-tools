import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from unittest.mock import MagicMock

import linuxmusterTools.print.render as render_module
import linuxmusterTools.print.templates as templates_module
import linuxmusterTools.print.schoolclasses as schoolclasses_module
import linuxmusterTools.print.passwords as passwords_module


# ---------------------------------------------------------------------------
# LDAP guard
#
# `lr` (LMNLdapReader) is a module-level singleton (see
# linuxmusterTools/ldapconnector/urls/ldaprouter.py: `router = LMNLdapRouter()`).
# templates.py imports it as `from ..ldapconnector import LMNLdapReader as lr`,
# and schoolclasses.py / passwords.py both re-import it via
# `from .templates import *`. Since it's the very same object everywhere,
# patching templates_module.lr's methods is enough to affect all three
# modules under test.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def guard_lr(monkeypatch):
    """
    Safety net: fail loudly if a test forgets to mock lr.getval/lr.get,
    instead of silently hitting a real LDAP connection.
    """

    def _boom_getval(url, attribute, **kwargs):
        raise AssertionError(f"lr.getval must be mocked in print tests (url={url!r})")

    def _boom_get(url, **kwargs):
        raise AssertionError(f"lr.get must be mocked in print tests (url={url!r})")

    monkeypatch.setattr(templates_module.lr, 'getval', _boom_getval)
    monkeypatch.setattr(templates_module.lr, 'get', _boom_get)


@pytest.fixture(autouse=True)
def guard_subprocess(monkeypatch):
    """
    Safety net: fail loudly if a test forgets to mock subprocess.Popen,
    instead of silently spawning a real /bin/pdflatex process.
    """

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess.Popen must be mocked in render tests")

    monkeypatch.setattr(render_module.subprocess, 'Popen', _boom)


@pytest.fixture
def mock_popen(monkeypatch):
    """
    Replace render_module.subprocess.Popen with a fake that behaves like a
    successful (returncode 0) pdflatex run. Tests can tweak `proc.returncode`
    and `proc.communicate.return_value` to exercise other cases.
    """
    proc = MagicMock()
    proc.communicate.return_value = (b"", b"")
    proc.returncode = 0

    popen_ctor = MagicMock(return_value=proc)
    monkeypatch.setattr(render_module.subprocess, 'Popen', popen_ctor)
    return popen_ctor, proc


@pytest.fixture
def render_dirs(tmp_path, monkeypatch):
    """
    Point render_module's OUTPUT_DIR/TEMPLATES_DIR to isolated tmp_path
    subdirectories.
    """
    templates_dir = tmp_path / "templates"
    output_dir = tmp_path / "output"
    templates_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(render_module, 'TEMPLATES_DIR', str(templates_dir))
    monkeypatch.setattr(render_module, 'OUTPUT_DIR', str(output_dir))

    return templates_dir, output_dir


@pytest.fixture
def templates_dirs(tmp_path, monkeypatch):
    """
    Point templates_module's three template-discovery directories to
    isolated tmp_path subdirectories.
    """
    lmntools_dir = tmp_path / "lmntools_templates"
    sophomorix_dir = tmp_path / "sophomorix_templates"
    config_dir = tmp_path / "sophomorix_config"
    lmntools_dir.mkdir()
    sophomorix_dir.mkdir()
    config_dir.mkdir()

    monkeypatch.setattr(templates_module, 'LMNTOOLS_TEMPLATES_DIR', str(lmntools_dir))
    monkeypatch.setattr(templates_module, 'SOPHOMORIX_TEMPLATES_DIR', str(sophomorix_dir))
    monkeypatch.setattr(templates_module, 'SOPHOMORIX_CONFIG_DIR', str(config_dir))

    return lmntools_dir, sophomorix_dir, config_dir
