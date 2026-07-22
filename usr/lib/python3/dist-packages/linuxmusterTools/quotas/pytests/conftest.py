import sys
import os
import types

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest

# ---------------------------------------------------------------------------
# check.py imports the external `smbclient` PyPI package and
# `smbprotocol.exceptions.SMBAuthenticationError`. Neither is installed in
# this test environment (and even when it is, we never want a real SMB
# connection during unit tests), so we install lightweight stand-in modules
# into sys.modules *before* linuxmusterTools.quotas.check is imported for the
# first time. Tests then monkeypatch the `scandir`/`stat` attributes of this
# fake module to simulate SMB directory trees.
# ---------------------------------------------------------------------------

if 'smbclient' not in sys.modules:
    fake_smbclient = types.ModuleType('smbclient')
    fake_smbclient.scandir = lambda path: iter([])
    fake_smbclient.stat = lambda path: None
    sys.modules['smbclient'] = fake_smbclient

if 'smbprotocol' not in sys.modules:
    fake_smbprotocol = types.ModuleType('smbprotocol')
    fake_smbprotocol_exceptions = types.ModuleType('smbprotocol.exceptions')

    class SMBAuthenticationError(Exception):
        pass

    fake_smbprotocol_exceptions.SMBAuthenticationError = SMBAuthenticationError
    fake_smbprotocol.exceptions = fake_smbprotocol_exceptions
    sys.modules['smbprotocol'] = fake_smbprotocol
    sys.modules['smbprotocol.exceptions'] = fake_smbprotocol_exceptions

import linuxmusterTools.quotas.check as check_module


@pytest.fixture
def check():
    """The module under test, imported once with fake smbclient/smbprotocol."""
    return check_module


@pytest.fixture(autouse=True)
def patch_samba_config(monkeypatch):
    """
    Replace the Samba constants imported into check.py's namespace
    (`from ..samba_util import ...`) with deterministic test values, instead
    of relying on whatever real /etc/samba/smb.conf happens to be on the
    machine running the tests.
    """
    monkeypatch.setattr(check_module, 'SAMBA_WORKGROUP', 'TESTDOM', raising=False)
    monkeypatch.setattr(check_module, 'SAMBA_DOMAIN', 'testdom.example.org', raising=False)
    monkeypatch.setattr(check_module, 'SAMBA_NETBIOS', 'testnb', raising=False)
    monkeypatch.setattr(check_module, 'DFS', {}, raising=False)
    monkeypatch.setattr(check_module, 'SHARES_LIST', ['default-school', 'linuxmuster-global'], raising=False)


# ---------------------------------------------------------------------------
# Fake SMB filesystem helpers
# ---------------------------------------------------------------------------

class FakeStat:
    def __init__(self, size=0, mtime=0):
        self.st_size = size
        self.st_mtime = mtime


class FakeDirEntry:
    def __init__(self, name, path, is_dir, stat):
        self.name = name
        self.path = path
        self._is_dir = is_dir
        self._stat = stat

    def is_file(self):
        return not self._is_dir

    def is_dir(self):
        return self._is_dir

    def stat(self):
        return self._stat


def build_fake_smb_tree(spec, base_path):
    """
    Build fake `smbclient.stat`/`smbclient.scandir` implementations from a
    plain nested-dict tree description, without touching any real SMB share.

    `spec` describes a directory: {'mtime': <int>, 'entries': {name: node}}.
    Each `node` is either another directory dict (has an 'entries' key) or a
    file dict: {'mtime': <int>, 'size': <int>}.

    Returns (fake_stat, fake_scandir, stat_map, scandir_map).
    """
    stat_map = {}
    scandir_map = {}

    def walk(path, node):
        if 'entries' in node:
            stat_map[path] = FakeStat(mtime=node.get('mtime', 0))
            entries = []
            for name, child in node['entries'].items():
                child_path = f"{path}/{name}"
                is_dir = 'entries' in child
                child_stat = FakeStat(size=child.get('size', 0), mtime=child.get('mtime', 0))
                entries.append(FakeDirEntry(name, child_path, is_dir, child_stat))
                walk(child_path, child)
            scandir_map[path] = entries
        else:
            stat_map[path] = FakeStat(size=node.get('size', 0), mtime=node.get('mtime', 0))

    walk(base_path, spec)

    def fake_stat(path):
        return stat_map[path]

    def fake_scandir(path):
        return iter(scandir_map[path])

    return fake_stat, fake_scandir, stat_map, scandir_map


@pytest.fixture
def fake_smb_tree():
    """Expose the tree-builder helper to test modules."""
    return build_fake_smb_tree
