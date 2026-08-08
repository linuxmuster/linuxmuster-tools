import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from datetime import datetime

import pytest

from linuxmusterTools.devices.devices import Devices


# ---------------------------------------------------------------------------
# switch() / load()
# ---------------------------------------------------------------------------

def test_missing_devices_csv_results_in_empty_device_list(devices_path):
    # e.g. fresh install, school not provisioned yet: must not raise.
    assert not devices_path().exists()

    devicesmgr = Devices()

    assert devicesmgr.devices == []
    assert devicesmgr.groups == []
    assert devicesmgr.macs == []
    assert devicesmgr.ips == []
    assert devicesmgr.rooms == []


def test_default_school_loads_devices(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc01')])

    devicesmgr = Devices()

    assert devicesmgr.school == 'default-school'
    assert len(devicesmgr.devices) == 1
    assert devicesmgr.devices[0]['hostname'] == 'pc01'


def test_named_school_uses_prefixed_path(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='labpc')], school='school1')

    devicesmgr = Devices('school1')

    assert devicesmgr.school == 'school1'
    assert devicesmgr.prefix == 'school1.'
    assert len(devicesmgr.devices) == 1
    assert devicesmgr.devices[0]['hostname'] == 'labpc'
    assert devicesmgr.devices[0]['school'] == 'school1'


def test_switch_between_schools(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc-default')], school='default-school')
    write_devices_csv([make_device_row(hostname='pc-school1')], school='school1')

    devicesmgr = Devices()
    assert devicesmgr.devices[0]['hostname'] == 'pc-default'

    devicesmgr.switch('school1')
    assert devicesmgr.school == 'school1'
    assert devicesmgr.devices[0]['hostname'] == 'pc-school1'


def test_comment_lines_are_skipped(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(room='#disabled', hostname='ghost'),
        make_device_row(room='r101', hostname='pc01'),
    ])

    devicesmgr = Devices()

    hostnames = [d['hostname'] for d in devicesmgr.devices]
    assert hostnames == ['pc01']


def test_csv_mtime_is_set_after_load(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row()])

    devicesmgr = Devices()

    assert isinstance(devicesmgr.csv_mtime, datetime)


def test_derived_lists_are_populated(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', room='r101', group='g-pcs', mac='AA:BB:CC:DD:EE:01', ip='10.0.0.1'),
        make_device_row(hostname='pc02', room='r102', group='g-laptops', mac='AA:BB:CC:DD:EE:02', ip='10.0.0.2'),
    ])

    devicesmgr = Devices()

    assert set(devicesmgr.groups) == {'g-pcs', 'g-laptops'}
    assert set(devicesmgr.macs) == {'AA:BB:CC:DD:EE:01', 'AA:BB:CC:DD:EE:02'}
    assert set(devicesmgr.ips) == {'10.0.0.1', '10.0.0.2'}
    assert set(devicesmgr.rooms) == {'r101', 'r102'}


# ---------------------------------------------------------------------------
# mac normalization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('raw_mac, expected', [
    ('aa:bb:cc:dd:ee:01', 'AA:BB:CC:DD:EE:01'),
    ('aa-bb-cc-dd-ee-01', 'AA:BB:CC:DD:EE:01'),
    ('aabbccddee01', 'AA:BB:CC:DD:EE:01'),
])
def test_mac_is_normalized_to_colon_uppercase(make_device_row, write_devices_csv, raw_mac, expected):
    write_devices_csv([make_device_row(mac=raw_mac)])

    devicesmgr = Devices()

    assert devicesmgr.devices[0]['mac'] == expected


def test_invalid_mac_normalizes_to_none_and_is_excluded_from_macs(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(mac='not-a-mac')])

    devicesmgr = Devices()

    assert devicesmgr.devices[0]['mac'] is None
    assert devicesmgr.macs == []


# ---------------------------------------------------------------------------
# pxe flag
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('pxe_flag, group, expected', [
    ('1', 'g-pcs', True),
    ('9', 'g-pcs', True),
    ('0', 'g-pcs', False),
    ('', 'g-pcs', False),
    ('not-a-number', 'g-pcs', False),
    ('1', 'nopxe', False),
    ('1', 'NoPXE', False),
])
def test_pxe_enabled_flag(make_device_row, write_devices_csv, pxe_flag, group, expected):
    write_devices_csv([make_device_row(pxeFlag=pxe_flag, group=group)])

    devicesmgr = Devices()

    assert devicesmgr.devices[0]['pxeEnabled'] is expected


# ---------------------------------------------------------------------------
# filter()
# ---------------------------------------------------------------------------

def test_filter_no_args_returns_all(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01'),
        make_device_row(hostname='pc02'),
    ])

    devicesmgr = Devices()

    assert len(devicesmgr.filter()) == 2


def test_filter_by_roles(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='client1', sophomorixRole='classroom-studentcomputer'),
        make_device_row(hostname='server1', sophomorixRole='server'),
    ])

    devicesmgr = Devices()

    result = devicesmgr.filter(roles=['classroom-studentcomputer'])
    assert [d['hostname'] for d in result] == ['client1']


def test_filter_by_groups(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', group='g-a'),
        make_device_row(hostname='pc02', group='g-b'),
    ])

    devicesmgr = Devices()

    result = devicesmgr.filter(groups=['g-b'])
    assert [d['hostname'] for d in result] == ['pc02']


def test_filter_by_roles_and_groups_combined(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='match', sophomorixRole='classroom-studentcomputer', group='g-a'),
        make_device_row(hostname='wrong-role', sophomorixRole='server', group='g-a'),
        make_device_row(hostname='wrong-group', sophomorixRole='classroom-studentcomputer', group='g-b'),
    ])

    devicesmgr = Devices()

    result = devicesmgr.filter(roles=['classroom-studentcomputer'], groups=['g-a'])
    assert [d['hostname'] for d in result] == ['match']


def test_filter_by_macs_normalizes_input(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', mac='AA:BB:CC:DD:EE:02'),
    ])

    devicesmgr = Devices()

    result = devicesmgr.filter(macs=['aabbccddee01'])
    assert [d['hostname'] for d in result] == ['pc01']


# ---------------------------------------------------------------------------
# get_host / get_hosts_by_macs / get_client / get_clients
# ---------------------------------------------------------------------------

def test_get_host_found(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc01')])

    devicesmgr = Devices()

    assert devicesmgr.get_host('pc01')['hostname'] == 'pc01'


def test_get_host_not_found_returns_none(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc01')])

    devicesmgr = Devices()

    assert devicesmgr.get_host('does-not-exist') is None


def test_get_hosts_by_macs(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', mac='AA:BB:CC:DD:EE:02'),
    ])

    devicesmgr = Devices()

    result = devicesmgr.get_hosts_by_macs(macs=['AA:BB:CC:DD:EE:02'])
    assert [d['hostname'] for d in result] == ['pc02']


def test_get_client_found(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc01', sophomorixRole='classroom-studentcomputer')])

    devicesmgr = Devices()

    client = devicesmgr.get_client('pc01')
    assert client is not None
    assert client['hostname'] == 'pc01'


def test_get_client_wrong_role_returns_none(make_device_row, write_devices_csv):
    # 'server' is a valid computer role but not a client role, so it must
    # not be reachable through get_client().
    write_devices_csv([make_device_row(hostname='srv01', sophomorixRole='server')])

    devicesmgr = Devices()

    assert devicesmgr.get_client('srv01') is None


def test_get_client_not_found_returns_none(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc01')])

    devicesmgr = Devices()

    assert devicesmgr.get_client('does-not-exist') is None


def test_get_clients_filters_by_group(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', group='g-a', sophomorixRole='classroom-studentcomputer'),
        make_device_row(hostname='pc02', group='g-b', sophomorixRole='classroom-studentcomputer'),
        make_device_row(hostname='srv01', group='g-a', sophomorixRole='server'),
    ])

    devicesmgr = Devices()

    result = devicesmgr.get_clients(groups=['g-a'])
    assert [d['hostname'] for d in result] == ['pc01']


def test_get_clients_no_groups_returns_all_clients(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', sophomorixRole='classroom-studentcomputer'),
        make_device_row(hostname='srv01', sophomorixRole='server'),
    ])

    devicesmgr = Devices()

    result = devicesmgr.get_clients()
    assert [d['hostname'] for d in result] == ['pc01']


# ---------------------------------------------------------------------------
# check_conf()
# ---------------------------------------------------------------------------

def test_check_conf_valid_returns_false(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='10.0.0.2', mac='AA:BB:CC:DD:EE:02'),
    ])

    devicesmgr = Devices()

    assert devicesmgr.check_conf() is False


def test_check_conf_no_devices_returns_false(write_devices_csv):
    write_devices_csv([])

    devicesmgr = Devices()

    assert devicesmgr.devices == []
    assert devicesmgr.check_conf() is False


def test_check_conf_invalid_ip(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(ip='999.999.999.999')])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert report is not False
    assert any('is not a valid ip address' in line for line in report)


def test_check_conf_invalid_mac(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(mac='not-a-mac')])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('is not a valid mac address' in line for line in report)


def test_check_conf_invalid_group_name(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(group='Invalid Group!')])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('is not a valid Linbo group' in line for line in report)


def test_check_conf_invalid_room_name(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(room='room with spaces')])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('is not a valid room name' in line for line in report)


def test_check_conf_invalid_hostname(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='bad host name')])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('is not a valid hostname' in line for line in report)


def test_check_conf_invalid_pxe_flag(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(pxeFlag='42')])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('is not a valid pxe flag' in line for line in report)


def test_check_conf_invalid_role(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(sophomorixRole='not-a-real-role')])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('is not a valid computer role' in line for line in report)


def test_check_conf_duplicate_ip(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:02'),
    ])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('have the same ip 10.0.0.1' in line for line in report)


def test_check_conf_duplicate_mac(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='10.0.0.2', mac='AA:BB:CC:DD:EE:01'),
    ])

    devicesmgr = Devices()

    report = devicesmgr.check_conf()
    assert any('have the same mac AA:BB:CC:DD:EE:01' in line for line in report)
