"""
Tests for linuxmusterTools.lmnconfig.samba.parse_log_level().

Note: everything else in samba.py (SAMBA_DOMAIN, SAMBA_REALM,
SAMBA_WORKGROUP, SAMBA_NETBIOS, SAMBA_TLD, LDAP_CONTEXT, DFS,
SHARES_LIST, LOG_LEVEL) is computed as a *module-level* side effect at
import time (reading /etc/samba/smb.conf and running
`/usr/bin/net conf list`). Since the module is only imported once per
test process and depends on this machine's real Samba configuration,
that computation itself is not re-testable/mockable per test case, so
it is intentionally left untested here. parse_log_level() is pure and
independent of any of that, so it is fully covered below.
"""

import importlib
from subprocess import CalledProcessError

import linuxmusterTools.lmnconfig.samba as samba_module
from linuxmusterTools.lmnconfig.samba import parse_log_level


def test_empty_string_gives_default_general_level():
    assert parse_log_level('') == {'general': 1}


def test_single_int_sets_general_level():
    assert parse_log_level('3') == {'general': 3}


def test_single_key_value_pair():
    assert parse_log_level('auth_audit:2') == {'general': 1, 'auth_audit': 2}


def test_mixed_general_and_key_value_pairs():
    result = parse_log_level('1 auth_audit:3 winbind:5')
    assert result == {'general': 1, 'auth_audit': 3, 'winbind': 5}


def test_multiple_key_value_pairs_without_general_override():
    result = parse_log_level('auth_audit:2 winbind:4')
    assert result == {'general': 1, 'auth_audit': 2, 'winbind': 4}


def test_last_bare_int_wins_for_general():
    # Nothing in the code de-duplicates repeated bare ints; the last one read wins.
    result = parse_log_level('1 2')
    assert result == {'general': 2}


def test_extra_whitespace_is_ignored():
    result = parse_log_level('   1   auth_audit:2   ')
    assert result == {'general': 1, 'auth_audit': 2}


# ---------------------------------------------------------------------------
# Import without a Samba installation
# ---------------------------------------------------------------------------

def _reload_samba_with_check_output(monkeypatch, raising):
    """Re-execute samba.py with a check_output that fails the given way."""
    import subprocess

    monkeypatch.setattr(subprocess, 'check_output', raising)
    return importlib.reload(samba_module)


def test_import_survives_missing_net_binary(monkeypatch):
    def _no_binary(*args, **kwargs):
        raise FileNotFoundError(2, 'No such file or directory', '/usr/bin/net')

    reloaded = _reload_samba_with_check_output(monkeypatch, _no_binary)

    assert reloaded.SHARES_LIST == []
    assert reloaded.DFS == {}


def test_import_survives_failing_net_call(monkeypatch):
    def _fails(*args, **kwargs):
        raise CalledProcessError(1, ['/usr/bin/net', 'conf', 'list'])

    reloaded = _reload_samba_with_check_output(monkeypatch, _fails)

    assert reloaded.SHARES_LIST == []
    assert reloaded.DFS == {}
