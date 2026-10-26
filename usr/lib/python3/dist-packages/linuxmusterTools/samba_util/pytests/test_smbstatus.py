import json

import pytest

import linuxmusterTools.samba_util.smbstatus as smbstatus_module
from linuxmusterTools.samba_util.smbstatus import (
    SMBConnection,
    SMBConnections,
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
    # out to `smbstatus -b -j`; default to a harmless empty result so
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
        'username': 'DOMAIN\\jdoe', 'version': '-', 'rawline': '',
        'auth_time': '',
    }


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
        {'ip': '10.0.1.5', 'hostname': 'pc01', 'room': 'A1'},
    ]
    connections = SMBConnections()
    connections.switch('abc')
    assert connections.school == 'abc'
    # Like the computer account in AD
    assert connections.hostnames == {'10.0.1.5': {'hostname': 'abc-pc01', 'room': 'A1'}}


# --- SMBConnections.get_users / get_machines -------------------------------

def _connections_with_hostnames(hostnames_by_key):
    FakeDevicesCSV.rows_by_path['/etc/linuxmuster/sophomorix/default-school/devices.csv'] = []
    connections = SMBConnections()
    connections.hostnames = hostnames_by_key
    return connections


def _session(pid, username, ip, auth_time, group='users', port=50000, family='ipv4'):
    """
    One session as listed by `smbstatus -b -j`.
    """

    return {
        'session_id': f'{pid}{port}',
        'server_id': {'pid': str(pid), 'task_id': '0', 'vnn': '4294967295', 'unique_id': '0'},
        'uid': 3000000, 'gid': 100,
        'username': username,
        'groupname': group,
        'creation_time': auth_time,
        'expiration_time': auth_time,
        'auth_time': auth_time,
        'remote_machine': ip,
        'hostname': f'{family}:{ip}:{port}',
        'session_dialect': 'SMB3_11',
        'client_guid': '00000000-0000-0000-0000-000000000000',
        'encryption': {'cipher': '-', 'degree': 'none'},
        'signing': {'cipher': 'AES-128-GMAC', 'degree': 'full'},
        'channels': {},
    }


def _smbstatus_output(*sessions):
    return json.dumps({
        'timestamp': '2026-10-26T19:30:00.000000+01:00',
        'version': '4.x',
        'smb_conf': '/etc/samba/smb.conf',
        'sessions': {s['session_id']: s for s in sessions},
    })


def _patch_smbstatus(monkeypatch, *sessions):
    output = _smbstatus_output(*sessions)
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: output)


T1 = '2026-10-26T19:02:43.717022+01:00'
T2 = '2026-10-26T19:27:40.514768+01:00'
T3 = '2026-10-26T19:27:41.000000+01:00'


def test_get_users_parses_and_resolves_hostname(monkeypatch):
    connections = _connections_with_hostnames({'10.0.0.5': {'hostname': 'pc01', 'room': 'B101'}})
    _patch_smbstatus(monkeypatch, _session(1234, 'DOMAIN\\jdoe', '10.0.0.5', T1, port=445))

    connections.get_users()

    assert list(connections.users.keys()) == ['jdoe']
    conn = connections.users['jdoe']
    assert conn.hostname == 'pc01'
    assert conn.room == 'B101'
    assert conn.group == 'users'
    assert conn.machine == '10.0.0.5'
    assert conn.ip4 == '10.0.0.5:445'
    assert conn.ip is None
    assert conn.pid == '1234'
    assert conn.protocol == 'SMB3_11'
    assert conn.signing == 'AES-128-GMAC'
    assert conn.encryption == '-'
    assert conn.auth_time == T1


def test_get_users_defaults_when_machine_unknown(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(monkeypatch, _session(1234, 'DOMAIN\\jdoe', '10.0.0.9', T1))

    connections.get_users()

    conn = connections.users['jdoe']
    assert conn.hostname == 'No hostname found'
    assert conn.room == 'No room found'


def test_get_users_does_not_depend_on_primary_group(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(monkeypatch, _session(1234, 'DOMAIN\\jdoe', '10.0.0.9', T1, group='DOMAIN\\teachers'))

    connections.get_users()

    assert connections.users['jdoe'].group == 'DOMAIN\\teachers'


def test_get_users_excludes_machine_and_anonymous_sessions(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(
        monkeypatch,
        _session(77, 'DOMAIN\\pc04$', '10.0.0.7', T1, group='DOMAIN\\domain computers'),
        _session(78, 'nobody', '10.0.0.7', T1, group='nogroup'),
    )

    connections.get_users()

    assert connections.users == {}
    assert connections.connections == {}


def test_get_users_excludes_server_own_machine(monkeypatch):
    # SERVER_IP is patched to '10.0.0.1' by the autouse fixture
    connections = _connections_with_hostnames({})
    _patch_smbstatus(monkeypatch, _session(1234, 'DOMAIN\\srv', '10.0.0.1', T1))

    connections.get_users()

    assert connections.users == {}


def test_get_users_excludes_connection_from_server_ip4(monkeypatch):
    # Machine name differs from SERVER_IP, but the ip4 field starts with it
    connections = _connections_with_hostnames({})
    session = _session(1234, 'DOMAIN\\srv', 'SOMEHOST', T1)
    session['hostname'] = 'ipv4:10.0.0.1:39999'
    _patch_smbstatus(monkeypatch, session)

    connections.get_users()

    assert connections.users == {}


def test_get_users_keeps_client_whose_ip_contains_server_ip(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(monkeypatch, _session(1234, 'DOMAIN\\jdoe', '110.0.0.1', T1))

    connections.get_users()

    assert list(connections.users.keys()) == ['jdoe']


def test_get_users_invalid_output(monkeypatch):
    # e.g. smbstatus not run as root
    connections = _connections_with_hostnames({})
    monkeypatch.setattr(smbstatus_module.subprocess, 'getoutput', lambda cmd: 'garbage, not json')

    connections.get_users()

    assert connections.users == {}
    assert connections.connections == {}


def test_get_users_accepts_ipv6_connection(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(monkeypatch, _session(1234, 'DOMAIN\\jdoe', 'fd00::5', T1, family='ipv6'))

    connections.get_users()

    conn = connections.users['jdoe']
    assert conn.ip6 == 'fd00::5:50000'
    assert conn.ip4 is None


def test_get_users_one_connection_per_ip(monkeypatch):
    # A client opens several sessions for the same user
    connections = _connections_with_hostnames({})
    _patch_smbstatus(
        monkeypatch,
        _session(10, 'DOMAIN\\jdoe', '10.0.0.100', T2, port=1),
        _session(11, 'DOMAIN\\jdoe', '10.0.0.100', T3, port=2),
        _session(12, 'DOMAIN\\jdoe', '10.0.0.100', T1, port=3),
    )

    connections.get_users()

    assert len(connections.connections['jdoe']) == 1
    assert connections.connections['jdoe'][0].pid == '11'
    assert connections.users['jdoe'].pid == '11'


def test_get_users_keeps_most_recent_connection_whatever_the_order(monkeypatch):
    # A session closed on the client can stay open on the server: the most
    # recent login is used, not the last line of smbstatus
    connections = _connections_with_hostnames({})
    _patch_smbstatus(
        monkeypatch,
        _session(10, 'DOMAIN\\jdoe', '10.0.0.100', T2),
        _session(20, 'DOMAIN\\jdoe', '10.0.0.102', T1),
    )

    connections.get_users()

    assert sorted(c.machine for c in connections.connections['jdoe']) == ['10.0.0.100', '10.0.0.102']
    assert connections.users['jdoe'].machine == '10.0.0.100'


def test_get_users_compares_auth_time_across_utc_offsets(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(
        monkeypatch,
        # 18:30 UTC
        _session(10, 'DOMAIN\\jdoe', '10.0.0.100', '2026-10-26T19:30:00.000000+01:00'),
        # 18:00 UTC
        _session(20, 'DOMAIN\\jdoe', '10.0.0.102', '2026-10-26T20:00:00.000000+02:00'),
    )

    connections.get_users()

    assert connections.users['jdoe'].machine == '10.0.0.100'


def test_get_machines_parses_and_resolves_hostname(monkeypatch):
    # get_machines() looks up hostnames by the computer account name, which
    # keeps the trailing '$' (e.g. 'pc04$').
    connections = _connections_with_hostnames({'pc04$': {'hostname': 'pc04.lan', 'room': 'C1'}})
    _patch_smbstatus(
        monkeypatch,
        _session(77, 'DOMAIN\\pc04$', '10.0.0.7', T1, group='DOMAIN\\domain computers', port=445),
        _session(78, 'DOMAIN\\jdoe', '10.0.0.7', T1),
    )

    connections.get_machines()

    assert list(connections.machines.keys()) == ['pc04$']
    machine = connections.machines['pc04$']
    assert machine.hostname == 'pc04.lan'
    assert machine.room == 'C1'
    assert machine.group == 'DOMAIN\\domain computers'
    assert machine.ip4 == '10.0.0.7:445'


def test_get_machines_defaults_when_unknown(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(monkeypatch, _session(77, 'DOMAIN\\pc05$', '10.0.0.8', T1, group='DOMAIN\\domain computers'))

    connections.get_machines()

    machine = connections.machines['pc05$']
    assert machine.hostname == 'No hostname found'
    assert machine.room == 'No room found'


def test_get_machines_keeps_most_recent_connection(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(
        monkeypatch,
        _session(77, 'DOMAIN\\pc05$', '10.0.0.8', T2, group='DOMAIN\\domain computers'),
        _session(78, 'DOMAIN\\pc05$', '10.0.0.8', T1, group='DOMAIN\\domain computers'),
    )

    connections.get_machines()

    assert connections.machines['pc05$'].pid == '77'


# --- SMBConnections.get_room_users -----------------------------------------

# A teacher is logged on pc01, and the Ajenti worker of the teacher's Webui
# session keeps its own connection from the server. This second connection
# was taken as the room of the teacher (#11518).
ROOM_SESSIONS = [
    _session(264465, 'DOMAIN\\teacher', '10.0.0.102', T1, port=50682),
    _session(264466, 'DOMAIN\\pc01$', '10.0.0.102', T1, group='DOMAIN\\domain computers', port=50691),
    _session(264470, 'DOMAIN\\s1', '10.0.0.103', T1, port=50710),
    _session(264480, 'DOMAIN\\s2', '10.0.0.120', T1, port=50720),
    _session(268253, 'DOMAIN\\teacher', '10.0.0.1', T2, port=51538),
]

ROOM_HOSTNAMES = {
    '10.0.0.1': {'hostname': 'server', 'room': 'server'},
    '10.0.0.102': {'hostname': 'pc01', 'room': 'r101'},
    '10.0.0.103': {'hostname': 'pc02', 'room': 'r101'},
    '10.0.0.120': {'hostname': 'r201-pc01', 'room': 'r201'},
    '10.0.0.121': {'hostname': 'r201-pc02', 'room': 'r201'},
}


def test_get_room_users_ignores_the_server_connection(monkeypatch):
    connections = _connections_with_hostnames(ROOM_HOSTNAMES)
    _patch_smbstatus(monkeypatch, *ROOM_SESSIONS)
    connections.get_users()

    room, users = connections.get_room_users('teacher')

    assert room == 'r101'
    assert list(users.keys()) == ['s1']
    assert users['s1'].hostname == 'pc02'


def test_get_room_users_uses_most_recent_login(monkeypatch):
    # The teacher moved from r101 to r201, the old session is still open
    connections = _connections_with_hostnames(ROOM_HOSTNAMES)
    _patch_smbstatus(
        monkeypatch,
        *ROOM_SESSIONS,
        _session(270000, 'DOMAIN\\teacher', '10.0.0.121', T3),
    )
    connections.get_users()

    room, users = connections.get_room_users('teacher')

    assert room == 'r201'
    assert list(users.keys()) == ['s2']


def test_get_room_users_only_server_connection(monkeypatch):
    connections = _connections_with_hostnames(ROOM_HOSTNAMES)
    _patch_smbstatus(monkeypatch, ROOM_SESSIONS[-1])
    connections.get_users()

    assert connections.get_room_users('teacher') == ('', {})


def test_get_room_users_unknown_client(monkeypatch):
    connections = _connections_with_hostnames({})
    _patch_smbstatus(monkeypatch, *ROOM_SESSIONS)
    connections.get_users()

    assert connections.get_room_users('teacher') == ('', {})


def test_get_room_users_not_connected(monkeypatch):
    connections = _connections_with_hostnames(ROOM_HOSTNAMES)
    _patch_smbstatus(monkeypatch, *ROOM_SESSIONS)
    connections.get_users()

    assert connections.get_room_users('nobody') == ('', {})
