import pytest

import linuxmusterTools.samba_util.smbstatus as smbstatus_module
from linuxmusterTools.samba_util.smbstatus import (
    SMBConnection,
    SMBConnections,
    users_regex,
    machine_regex,
)


class FakeDevicesCSV:
    """
    Stand-in for the LMNFile CSV loader used by load_hostnames(): supports
    the same 'with LMNFile(...) as f: f.read()' usage without touching a
    real file on disk.
    """

    rows_by_path = {}

    def __init__(self, path, mode):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def read(self):
        return list(FakeDevicesCSV.rows_by_path.get(self.path, []))


@pytest.fixture(autouse=True)
def patch_lmnfile(monkeypatch):
    FakeDevicesCSV.rows_by_path = {}
    monkeypatch.setattr(smbstatus_module, 'LMNFile', FakeDevicesCSV)
    monkeypatch.setattr(smbstatus_module, 'SERVER_IP', '10.0.0.1')
    # SMBConnections.__init__ unconditionally calls get_users(), which shells
    # out to `smbstatus -b`; default to a harmless empty result so
    # instantiating the class never spawns a real subprocess. Tests that
    # care about get_users()/get_machines() output override this themselves.
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: '')


# --- SMBConnection dataclass ---------------------------------------------

def test_smb_connection_as_dict():
    conn = SMBConnection(
        encryption='-', ip=None, ip4='10.0.0.5:445', ip6=None, group='users',
        hostname='pc01', machine='PC01', pid='123', protocol='SMB3_11',
        room='B101', signing='AES-128-CMAC', username='DOMAIN\\jdoe',
        version='-',
    )
    assert conn.as_dict() == {
        'encryption': '-', 'ip': None, 'ip4': '10.0.0.5:445', 'ip6': None,
        'group': 'users', 'hostname': 'pc01', 'machine': 'PC01', 'pid': '123',
        'protocol': 'SMB3_11', 'room': 'B101', 'signing': 'AES-128-CMAC',
        'username': 'DOMAIN\\jdoe', 'version': '-',
    }


# --- regex parsing ---------------------------------------------------------

def test_users_regex_matches_ipv4_line():
    line = "1234    DOMAIN\\jdoe   users    PC01    (ipv4:10.0.0.5:445)    SMB3_11    -    AES-128-CMAC    AES-128-CMAC"
    match = users_regex.match(line)
    assert match is not None
    data = match.groupdict()
    assert data['pid'] == '1234'
    assert data['username'] == 'DOMAIN\\jdoe'
    assert data['machine'] == 'PC01'
    assert data['ip4'] == '10.0.0.5:445'
    assert data['ip'] is None
    assert data['ip6'] is None
    assert data['protocol'] == 'SMB3_11'
    # `version` is captured with a greedy `.*`, so it retains any trailing
    # whitespace the regex didn't need to backtrack over to still match the
    # remaining fields.
    assert data['version'].strip() == '-'
    assert data['encryption'] == 'AES-128-CMAC'
    assert data['signing'] == 'AES-128-CMAC'


def test_users_regex_matches_bare_ip_without_prefix():
    line = "42    DOMAIN\\jdoe   users    PC02    (10.0.0.6)    SMB3_11    -    -    -"
    match = users_regex.match(line)
    assert match is not None
    data = match.groupdict()
    assert data['ip'] == '10.0.0.6'
    assert data['ip4'] is None
    assert data['ip6'] is None


def test_users_regex_matches_ipv6_line():
    line = "42    DOMAIN\\jdoe   users    PC03    (ipv6:fe80::1)    SMB3_11    -    -    -"
    match = users_regex.match(line)
    assert match is not None
    data = match.groupdict()
    assert data['ip6'] == 'fe80::1'
    assert data['ip'] is None
    assert data['ip4'] is None


def test_users_regex_rejects_header_or_separator_lines():
    assert users_regex.match("PID     Username     Group        Machine") is None
    assert users_regex.match("-" * 40) is None
    assert users_regex.match("") is None


def test_machine_regex_requires_domain_computers_group():
    line = "77    DOMAIN\\pc04$   corp.example\\domain computers    PC04    (ipv4:10.0.0.7:445)    SMB3_11    -    -    -"
    match = machine_regex.match(line)
    assert match is not None
    data = match.groupdict()
    assert data['group'] == 'corp.example\\domain computers'
    assert data['machine'] == 'PC04'


def test_machine_regex_does_not_match_users_group():
    line = "77    DOMAIN\\jdoe   users    PC01    (ipv4:10.0.0.5:445)    SMB3_11    -    -    -"
    assert machine_regex.match(line) is None


# --- SMBConnections.load_hostnames -----------------------------------------

def test_load_hostnames_default_school_uses_unprefixed_path():
    FakeDevicesCSV.rows_by_path['/etc/linuxmuster/sophomorix/default-school/devices.csv'] = [
        {'ip': '10.0.0.5', 'hostname': 'pc01', 'room': 'B101'},
    ]
    connections = SMBConnections()
    assert connections.hostnames == {'10.0.0.5': {'hostname': 'pc01', 'room': 'B101'}}


def test_switch_reloads_hostnames_with_school_prefix():
    FakeDevicesCSV.rows_by_path['/etc/linuxmuster/sophomorix/default-school/devices.csv'] = []
    FakeDevicesCSV.rows_by_path['/etc/linuxmuster/sophomorix/abc/abc.devices.csv'] = [
        {'ip': '10.0.1.5', 'hostname': 'abc-pc01', 'room': 'A1'},
    ]
    connections = SMBConnections()
    connections.switch('abc')
    assert connections.school == 'abc'
    assert connections.hostnames == {'10.0.1.5': {'hostname': 'abc-pc01', 'room': 'A1'}}


# --- SMBConnections.get_users / get_machines -------------------------------

def _connections_with_hostnames(hostnames_by_key):
    FakeDevicesCSV.rows_by_path['/etc/linuxmuster/sophomorix/default-school/devices.csv'] = []
    connections = SMBConnections()
    connections.hostnames = hostnames_by_key
    return connections


def test_get_users_parses_and_resolves_hostname(monkeypatch):
    connections = _connections_with_hostnames({'PC01': {'hostname': 'pc01.lan', 'room': 'B101'}})
    output = (
        "Samba version 4.x\n"
        "PID     Username     Group        Machine\n"
        "----------------------------------------\n"
        "1234    DOMAIN\\jdoe   users    PC01    (ipv4:10.0.0.5:445)    SMB3_11    -    AES-128-CMAC    AES-128-CMAC\n"
    )
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)

    connections.get_users()

    assert list(connections.users.keys()) == ['jdoe']
    conn = connections.users['jdoe']
    assert conn.hostname == 'pc01.lan'
    assert conn.room == 'B101'
    assert conn.group == 'users'
    assert conn.machine == 'PC01'
    assert conn.ip4 == '10.0.0.5:445'


def test_get_users_defaults_when_machine_unknown(monkeypatch):
    connections = _connections_with_hostnames({})
    output = "1234    DOMAIN\\jdoe   users    UNKNOWNPC    (ipv4:10.0.0.9:445)    SMB3_11    -    -    -\n"
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)

    connections.get_users()

    conn = connections.users['jdoe']
    assert conn.hostname == 'No hostname found'
    assert conn.room == 'No room found'


def test_get_users_excludes_server_own_machine(monkeypatch):
    # SERVER_IP is patched to '10.0.0.1' by the autouse fixture
    connections = _connections_with_hostnames({})
    output = "1234    DOMAIN\\srv   users    10.0.0.1    (ipv4:10.0.0.1:445)    SMB3_11    -    -    -\n"
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)

    connections.get_users()

    assert connections.users == {}


def test_get_users_excludes_connection_from_server_ip4(monkeypatch):
    # Machine name differs from SERVER_IP, but the ip4 field starts with it
    connections = _connections_with_hostnames({})
    output = "1234    DOMAIN\\srv   users    SOMEHOST    (ipv4:10.0.0.1:39999)    SMB3_11    -    -    -\n"
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)

    connections.get_users()

    assert connections.users == {}


def test_get_users_ignores_non_matching_lines(monkeypatch):
    connections = _connections_with_hostnames({})
    output = "garbage line that does not match anything\n\n"
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)

    connections.get_users()

    assert connections.users == {}


def test_get_machines_parses_and_resolves_hostname(monkeypatch):
    # get_machines() looks up hostnames by `data['username'].split('\\')[1]`,
    # which keeps the trailing '$' of a machine account name (e.g. 'pc04$').
    connections = _connections_with_hostnames({'pc04$': {'hostname': 'pc04.lan', 'room': 'C1'}})
    output = (
        "77    DOMAIN\\pc04$   corp.example\\domain computers    PC04    "
        "(ipv4:10.0.0.7:445)    SMB3_11    -    -    -\n"
    )
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)

    connections.get_machines()

    assert list(connections.machines.keys()) == ['pc04$']
    machine = connections.machines['pc04$']
    assert machine.hostname == 'pc04.lan'
    assert machine.room == 'C1'
    assert machine.group == 'corp.example\\domain computers'


def test_get_machines_defaults_when_unknown(monkeypatch):
    connections = _connections_with_hostnames({})
    output = (
        "77    DOMAIN\\pc05$   corp.example\\domain computers    PC05    "
        "(ipv4:10.0.0.8:445)    SMB3_11    -    -    -\n"
    )
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)

    connections.get_machines()

    machine = connections.machines['pc05$']
    assert machine.hostname == 'No hostname found'
    assert machine.room == 'No room found'
