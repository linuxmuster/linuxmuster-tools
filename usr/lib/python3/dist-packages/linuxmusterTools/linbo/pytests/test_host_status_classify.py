"""
Tests for the boot-state classification added to linuxmusterTools.linbo.host_status.
"""

from unittest.mock import patch

from linuxmusterTools.linbo import host_status
from linuxmusterTools.linbo.host_status import classify_os, classify_host


# ── classify_os (pure signature matching) ──────────────────────────────────


def test_classify_os_all_filtered_is_off():
    assert classify_os({2222: 'filtered', 22: 'filtered', 135: 'filtered'}) == 'Off'


def test_classify_os_only_2222_open_is_linbo():
    assert classify_os({2222: 'open', 22: 'closed', 135: 'closed'}) == 'Linbo'


def test_classify_os_22_open_is_linux():
    assert classify_os({2222: 'closed', 22: 'open', 135: 'closed'}) == 'OS Linux'


def test_classify_os_22_filtered_still_counts_as_linux():
    assert classify_os({2222: 'closed', 22: 'filtered', 135: 'closed'}) == 'OS Linux'


def test_classify_os_135_open_is_windows():
    assert classify_os({2222: 'closed', 22: 'closed', 135: 'open'}) == 'OS Windows'


def test_classify_os_both_22_and_135_open_is_unknown():
    assert classify_os({2222: 'closed', 22: 'open', 135: 'open'}) == 'OS Unknown'


def test_classify_os_2222_and_22_open_is_not_linbo():
    assert classify_os({2222: 'open', 22: 'open', 135: 'closed'}) == 'OS Linux'


# ── probe_port_state (plain blocking sockets, gevent-safe) ─────────────────


def test_probe_port_state_open(monkeypatch):
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(host_status.socket, 'create_connection', lambda addr, timeout: FakeSocket())

    assert host_status.probe_port_state('10.0.0.5', 2222) == 'open'


def test_probe_port_state_closed(monkeypatch):
    def fake_create_connection(addr, timeout):
        raise ConnectionRefusedError()

    monkeypatch.setattr(host_status.socket, 'create_connection', fake_create_connection)

    assert host_status.probe_port_state('10.0.0.5', 22) == 'closed'


def test_probe_port_state_filtered_on_timeout(monkeypatch):
    def fake_create_connection(addr, timeout):
        raise TimeoutError()

    monkeypatch.setattr(host_status.socket, 'create_connection', fake_create_connection)

    assert host_status.probe_port_state('10.0.0.5', 135, timeout=0.01) == 'filtered'


# ── classify_host ────────────────────────────────────────────────────────


def test_classify_host_combines_port_states():
    def fake_probe(ip, port, timeout):
        return {2222: 'open', 22: 'closed', 135: 'closed'}[port]

    with patch.object(host_status, 'probe_port_state', side_effect=fake_probe):
        result = classify_host('10.0.0.5')

    assert result == 'Linbo'
