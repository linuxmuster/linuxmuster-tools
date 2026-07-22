import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
import linuxmusterTools.smbclient.smbclient as smbclient_module


@pytest.fixture(autouse=True)
def patch_schools(monkeypatch):
    """
    Replace LMNLdapReader.getval (imported into the smbclient module as `lr`)
    with a stub returning a controlled list of school names, so
    LMNSMBClient.__init__()/switch() never hit a real LDAP connection.
    """
    monkeypatch.setattr(
        smbclient_module.lr,
        'getval',
        lambda url, attribute, **kwargs: ['default-school', 'school2'],
    )


@pytest.fixture(autouse=True)
def guard_subprocess(monkeypatch):
    """
    Safety net: fail loudly if a test forgets to mock subprocess.Popen,
    instead of silently spawning a real /bin/smbclient process.
    Tests that need to exercise _execute() override this with their own
    fake Popen via monkeypatch.
    """
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess.Popen must be mocked in smbclient tests")

    monkeypatch.setattr(smbclient_module.subprocess, 'Popen', _boom)
