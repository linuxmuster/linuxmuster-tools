import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import xml.etree.ElementTree as ElementTree

import pytest

import linuxmusterTools.devices.ping as ping_module
from linuxmusterTools.devices.ping import UPChecker


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeDevices:
    """
    Stand-in for linuxmusterTools.devices.devices.Devices so UPChecker()
    never touches the filesystem. Only the surface UPChecker actually uses
    is implemented (clients / get_client / get_clients).
    """

    def __init__(self, clients=None):
        self.clients = clients or []

    def get_client(self, hostname, groups=None):
        for device in self.clients:
            if device['hostname'] != hostname:
                continue
            if groups and device.get('group') not in groups:
                continue
            return device
        return None

    def get_clients(self, groups=None):
        if groups:
            return [d for d in self.clients if d.get('group') in groups]
        return self.clients


class FakeStdout:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


class FakePopen:
    def __init__(self, data):
        self.stdout = FakeStdout(data)


def make_popen_by_ip(responses_by_ip):
    """
    Build a drop-in replacement for subprocess.Popen: looks at the target ip
    (4th element of the nmap command list) and returns the canned xml bytes
    registered for it. Pure dict lookup, no shared mutable state, so it's
    safe to call concurrently from a ThreadPoolExecutor.
    """

    def _popen(command, stdout=None, stderr=None, shell=False):
        ip = command[3]
        return FakePopen(responses_by_ip[ip])

    return _popen


def nmap_xml(up=True, ports=None):
    """
    Build canned nmap -oX xml output.

    :param up: whether the host answered at all (runstats hosts up=1/0)
    :param ports: dict of portid -> state ("open"/"closed"/"filtered")
    """
    if not up:
        return (
            b'<?xml version="1.0"?><nmaprun>'
            b'<runstats><hosts up="0" down="1" total="1"/></runstats>'
            b'</nmaprun>'
        )

    ports = ports or {}
    ports_xml = ''.join(
        f'<port protocol="tcp" portid="{portid}"><state state="{state}"/></port>'
        for portid, state in ports.items()
    )
    return (
        '<?xml version="1.0"?><nmaprun>'
        f'<host><ports>{ports_xml}</ports></host>'
        '<runstats><hosts up="1" down="0" total="1"/></runstats>'
        '</nmaprun>'
    ).encode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def stub_devices(monkeypatch):
    """
    Replace Devices as referenced from the ping module with a no-op fake so
    constructing UPChecker() never reads devices.csv from disk. Individual
    tests still override checker.devicesmgr when they need specific data.
    """
    monkeypatch.setattr(ping_module, 'Devices', lambda school='default-school': FakeDevices())


@pytest.fixture
def checker():
    return UPChecker()


def device(hostname='pc01', ip='10.0.0.1', group='g-a'):
    return {'hostname': hostname, 'ip': ip, 'group': group}


# ---------------------------------------------------------------------------
# test_online()
# ---------------------------------------------------------------------------

def test_online_host_off(checker, monkeypatch):
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': nmap_xml(up=False)})
    )

    result = checker.test_online(device(ip='10.0.0.1'))

    assert result == {'10.0.0.1': 'Off'}


def test_online_host_no_response(checker, monkeypatch):
    ports = {'2222': 'filtered', '22': 'filtered', '135': 'filtered'}
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': nmap_xml(ports=ports)})
    )

    result = checker.test_online(device(ip='10.0.0.1'))

    assert result == {'10.0.0.1': 'No response'}


def test_online_host_linbo(checker, monkeypatch):
    ports = {'2222': 'open', '22': 'closed', '135': 'closed'}
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': nmap_xml(ports=ports)})
    )

    result = checker.test_online(device(ip='10.0.0.1'))

    assert result == {'10.0.0.1': 'Linbo'}


def test_online_host_linux(checker, monkeypatch):
    ports = {'2222': 'closed', '22': 'open', '135': 'closed'}
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': nmap_xml(ports=ports)})
    )

    result = checker.test_online(device(ip='10.0.0.1'))

    assert result == {'10.0.0.1': 'OS Linux'}


def test_online_host_windows(checker, monkeypatch):
    ports = {'2222': 'closed', '22': 'closed', '135': 'open'}
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': nmap_xml(ports=ports)})
    )

    result = checker.test_online(device(ip='10.0.0.1'))

    assert result == {'10.0.0.1': 'OS Windows'}


def test_online_host_unknown(checker, monkeypatch):
    ports = {'2222': 'filtered', '22': 'closed', '135': 'closed'}
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': nmap_xml(ports=ports)})
    )

    result = checker.test_online(device(ip='10.0.0.1'))

    assert result == {'10.0.0.1': 'OS Unknown'}


def test_online_malformed_xml_raises_parse_error(checker, monkeypatch):
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': b''})
    )

    with pytest.raises(ElementTree.ParseError):
        checker.test_online(device(ip='10.0.0.1'))


def test_online_xml_missing_runstats_raises_attribute_error(checker, monkeypatch):
    # Well-formed xml, but missing the <runstats> element test_online relies on.
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': b'<nmaprun></nmaprun>'})
    )

    with pytest.raises(AttributeError):
        checker.test_online(device(ip='10.0.0.1'))


# ---------------------------------------------------------------------------
# checkhost()
# ---------------------------------------------------------------------------

def test_checkhost_known_host(checker, monkeypatch):
    checker.devicesmgr = FakeDevices(clients=[device(hostname='pc01', ip='10.0.0.1')])
    ports = {'2222': 'open', '22': 'closed', '135': 'closed'}
    monkeypatch.setattr(
        ping_module.subprocess, 'Popen',
        make_popen_by_ip({'10.0.0.1': nmap_xml(ports=ports)})
    )

    result = checker.checkhost('pc01')

    assert result == {'10.0.0.1': 'Linbo'}


def test_checkhost_unknown_host_returns_empty_dict(checker):
    checker.devicesmgr = FakeDevices(clients=[device(hostname='pc01', ip='10.0.0.1')])

    result = checker.checkhost('does-not-exist')

    assert result == {}


# ---------------------------------------------------------------------------
# check()
# ---------------------------------------------------------------------------

def test_check_aggregates_multiple_devices(checker, monkeypatch):
    devices = [
        device(hostname='pc01', ip='10.0.0.1', group='g-a'),
        device(hostname='pc02', ip='10.0.0.2', group='g-a'),
        device(hostname='pc03', ip='10.0.0.3', group='g-a'),
    ]
    checker.devicesmgr = FakeDevices(clients=devices)

    responses = {
        '10.0.0.1': nmap_xml(ports={'2222': 'open', '22': 'closed', '135': 'closed'}),
        '10.0.0.2': nmap_xml(ports={'2222': 'closed', '22': 'open', '135': 'closed'}),
        '10.0.0.3': nmap_xml(up=False),
    }
    monkeypatch.setattr(ping_module.subprocess, 'Popen', make_popen_by_ip(responses))

    result = checker.check()

    assert result == {
        '10.0.0.1': 'Linbo',
        '10.0.0.2': 'OS Linux',
        '10.0.0.3': 'Off',
    }


def test_check_filters_by_groups(checker, monkeypatch):
    devices = [
        device(hostname='pc01', ip='10.0.0.1', group='g-a'),
        device(hostname='pc02', ip='10.0.0.2', group='g-b'),
    ]
    checker.devicesmgr = FakeDevices(clients=devices)

    responses = {
        '10.0.0.1': nmap_xml(ports={'2222': 'open', '22': 'closed', '135': 'closed'}),
    }
    monkeypatch.setattr(ping_module.subprocess, 'Popen', make_popen_by_ip(responses))

    result = checker.check(groups=['g-a'])

    assert result == {'10.0.0.1': 'Linbo'}


def test_check_no_devices_returns_empty_dict(checker):
    checker.devicesmgr = FakeDevices(clients=[])

    result = checker.check()

    assert result == {}


# ---------------------------------------------------------------------------
# get_os_from_ports() / port signature helpers (pure unit tests)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('ports, expected', [
    ({'2222': 'open'}, True),
    ({'2222': 'open', '22': 'open'}, False),
    ({'2222': 'closed'}, False),
    ({}, False),
])
def test_is_port_signature_linbo(ports, expected):
    assert UPChecker.is_port_signature_linbo(ports) is expected


@pytest.mark.parametrize('ports, expected', [
    ({'22': 'open'}, True),
    ({'22': 'filtered'}, True),
    ({'22': 'open', '135': 'open'}, False),
    ({'135': 'open'}, False),
    ({'22': 'closed'}, False),
])
def test_is_port_signature_linux(ports, expected):
    assert UPChecker.is_port_signature_linux(ports) is expected


@pytest.mark.parametrize('ports, expected', [
    ({'135': 'open'}, True),
    ({'135': 'filtered'}, True),
    ({'135': 'open', '22': 'open'}, False),
    ({'22': 'open'}, False),
    ({'135': 'closed'}, False),
])
def test_is_port_signature_windows(ports, expected):
    assert UPChecker.is_port_signature_windows(ports) is expected


def test_get_os_from_ports_prefers_linbo_over_linux_signature(checker):
    # A port set that could arguably match either linbo or linux criteria
    # should resolve to the first check in the method: linbo.
    result = checker.get_os_from_ports({'2222': 'open'})
    assert result == 'Linbo'
