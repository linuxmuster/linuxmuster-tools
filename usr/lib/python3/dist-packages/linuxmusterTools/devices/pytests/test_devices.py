import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from datetime import datetime

import pytest

from linuxmusterTools.devices.devices import Devices, check_all_schools, list_schools


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


def test_hostnames_are_collected(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01'),
        make_device_row(hostname='pc02'),
    ])

    devicesmgr = Devices()

    assert sorted(devicesmgr.hostnames) == ['pc01', 'pc02']


def test_default_school_hostnames_carry_no_prefix(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc01')])

    devicesmgr = Devices()

    assert devicesmgr.hostname_prefix == ''
    assert devicesmgr.prefixed_hostnames == {'pc01'}


def test_named_school_hostnames_are_prefixed_with_a_hyphen(make_device_row, write_devices_csv):
    """
    The inventory file is school1.devices.csv, but the host is school1-labpc:
    the two prefixes are not the same and must not be confused.
    """

    write_devices_csv([make_device_row(hostname='labpc')], school='school1')

    devicesmgr = Devices('school1')

    assert devicesmgr.prefix == 'school1.'
    assert devicesmgr.hostname_prefix == 'school1-'
    assert devicesmgr.hostnames == ['labpc']
    assert devicesmgr.prefixed_hostnames == {'school1-labpc'}


def test_prefixed_hostnames_follow_a_switch(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='pc01')])
    write_devices_csv([make_device_row(hostname='labpc')], school='school1')

    devicesmgr = Devices()
    assert devicesmgr.prefixed_hostnames == {'pc01'}

    devicesmgr.switch('school1')

    assert devicesmgr.prefixed_hostnames == {'school1-labpc'}


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

def test_check_conf_valid_inventory(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='10.0.0.2', mac='AA:BB:CC:DD:EE:02'),
    ])

    result = Devices().check_conf()

    assert result['valid'] is True
    assert result['findings'] == []
    assert result['report'] == []
    assert result['counts'] == {
        'schools': 1, 'devices': 2, 'errors': 0, 'warnings': 0,
    }


def test_check_conf_no_devices_is_valid(write_devices_csv):
    write_devices_csv([])

    result = Devices().check_conf()

    assert result['valid'] is True
    assert result['counts']['devices'] == 0


def test_check_conf_invalid_ip(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(ip='999.999.999.999')])

    result = Devices().check_conf()

    assert result['valid'] is False
    assert [f['code'] for f in result['findings']] == ['ip.invalid']
    assert any('is not a valid ip address' in line for line in result['report'])


def test_check_conf_invalid_mac_names_the_raw_address(make_device_row, write_devices_csv):
    # The normalized mac is None here, so only macRaw can name the problem.
    write_devices_csv([make_device_row(mac='not-a-mac')])

    result = Devices().check_conf()

    finding = result['findings'][0]
    assert finding['code'] == 'mac.invalid'
    assert finding['value'] == 'not-a-mac'
    assert 'not-a-mac is not a valid mac address' in finding['message']


def test_check_conf_invalid_group_name(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(group='Invalid Group!')])

    result = Devices().check_conf()

    assert [f['code'] for f in result['findings']] == ['group.invalid']


def test_check_conf_accepts_an_upper_case_linbo_group(make_device_row, write_devices_csv):
    # check_linbo_conf_name(), not check_group_name(): a LINBO group may
    # carry upper case.
    write_devices_csv([make_device_row(group='Win11_UEFI-2')])

    assert Devices().check_conf()['valid'] is True


def test_check_conf_invalid_room_name(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(room='room with spaces')])

    result = Devices().check_conf()

    assert [f['code'] for f in result['findings']] == ['room.invalid']


def test_check_conf_invalid_hostname(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(hostname='bad host name')])

    result = Devices().check_conf()

    assert [f['code'] for f in result['findings']] == ['hostname.invalid']


def test_check_conf_invalid_pxe_flag(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(pxeFlag='42')])

    result = Devices().check_conf()

    assert [f['code'] for f in result['findings']] == ['pxe.invalid']


def test_check_conf_accepts_an_empty_pxe_flag(make_device_row, write_devices_csv):
    # Devices._check_pxe_flag() already reads an empty field as no pxe.
    write_devices_csv([make_device_row(pxeFlag='')])

    assert Devices().check_conf()['valid'] is True


def test_check_conf_invalid_role(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(sophomorixRole='not-a-real-role')])

    result = Devices().check_conf()

    assert [f['code'] for f in result['findings']] == ['role.unknown']


def test_check_conf_accepts_dhcp_as_an_ip(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='DHCP', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='DHCP', mac='AA:BB:CC:DD:EE:02'),
    ])

    # DHCP is a legal value and two devices may both carry it.
    assert Devices().check_conf()['valid'] is True


def test_check_conf_reports_everything_at_once(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='999.999.999.999', mac='nope', group='bad group'),
    ])

    result = Devices().check_conf()

    assert sorted(f['code'] for f in result['findings']) == [
        'group.invalid', 'ip.invalid', 'mac.invalid',
    ]


def test_check_conf_duplicate_ip(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:02'),
    ])

    result = Devices().check_conf()

    finding = result['findings'][0]
    assert finding['code'] == 'ip.duplicate'
    assert finding['subject'] == 'pc01'
    assert [o['subject'] for o in finding['related']] == ['pc02']
    assert any('have the same ip 10.0.0.1' in line for line in result['report'])


def test_check_conf_duplicate_mac(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='10.0.0.2', mac='aa:bb:cc:dd:ee:01'),
    ])

    result = Devices().check_conf()

    assert [f['code'] for f in result['findings']] == ['mac.duplicate']
    assert any('have the same mac AA:BB:CC:DD:EE:01' in line for line in result['report'])


def test_check_conf_duplicate_hostname_ignores_case(make_device_row, write_devices_csv):
    # sophomorix lower cases the dns node and upper cases the machine
    # account out of the same field, so these are the same host.
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='PC01', ip='10.0.0.2', mac='AA:BB:CC:DD:EE:02'),
    ])

    result = Devices().check_conf()

    assert [f['code'] for f in result['findings']] == ['hostname.duplicate']


def test_check_conf_reports_the_line_to_fix(make_device_row, write_devices_csv):
    write_devices_csv([
        ['# a comment line'],
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc02', ip='999.999.999.999', mac='AA:BB:CC:DD:EE:02'),
    ])

    result = Devices().check_conf()

    finding = result['findings'][0]
    assert finding['line'] == 3
    assert finding['subject'] == 'pc02'
    assert finding['file'].endswith('default-school/devices.csv')
    assert result['report'][0] == (
        f"ERROR: pc02: 999.999.999.999 is not a valid ip address ({finding['file']}, line 3)"
    )


def test_check_conf_report_names_a_duplicate_once_with_every_line(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
        make_device_row(hostname='pc01', ip='10.0.0.2', mac='AA:BB:CC:DD:EE:02'),
    ])

    result = Devices().check_conf()

    finding = result['findings'][0]
    assert finding['message'] == 'pc01 is used 2 times'
    assert result['report'][0] == f"ERROR: pc01 is used 2 times ({finding['file']}, lines 1, 2)"


# ---------------------------------------------------------------------------
# list_schools() / check_all_schools()
# ---------------------------------------------------------------------------

def test_list_schools_finds_the_schools_holding_an_inventory(tmp_path):
    root = tmp_path / 'sophomorix'
    (root / 'default-school').mkdir(parents=True)
    (root / 'default-school' / 'devices.csv').write_text('')
    (root / 'school2').mkdir()
    (root / 'school2' / 'school2.devices.csv').write_text('')
    # A school directory without an inventory, and a stray file
    (root / 'school3').mkdir()
    (root / 'sophomorix.conf').write_text('')

    assert list_schools(root) == ['default-school', 'school2']


def test_list_schools_on_a_missing_directory_returns_nothing(tmp_path):
    assert list_schools(tmp_path / 'nowhere') == []


def test_check_all_schools_sees_a_mac_used_in_two_schools(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
    ])
    write_devices_csv([
        make_device_row(hostname='pc02', ip='10.0.0.2', mac='AA:BB:CC:DD:EE:01'),
    ], school='school2')

    result = check_all_schools(['default-school', 'school2'])

    assert result['counts'] == {
        'schools': 2, 'devices': 2, 'errors': 1, 'warnings': 0,
    }
    finding = result['findings'][0]
    assert finding['code'] == 'mac.duplicate'
    assert finding['school'] == 'default-school'
    assert finding['related'][0]['school'] == 'school2'


def test_check_all_schools_warns_on_an_ip_shared_between_schools(make_device_row, write_devices_csv):
    # A fileserver legitimately carries the same address in every school.
    write_devices_csv([
        make_device_row(hostname='nas', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
    ])
    write_devices_csv([
        make_device_row(hostname='nas', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:02'),
    ], school='school2')

    result = check_all_schools(['default-school', 'school2'])

    assert result['valid'] is True
    assert [f['code'] for f in result['findings']] == ['ip.duplicate_across_schools']


def test_check_all_schools_keeps_the_same_hostname_in_two_schools(make_device_row, write_devices_csv):
    # pc01 of school2 is school2-pc01 in the AD: not the same name.
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.1', mac='AA:BB:CC:DD:EE:01'),
    ])
    write_devices_csv([
        make_device_row(hostname='pc01', ip='10.0.0.2', mac='AA:BB:CC:DD:EE:02'),
    ], school='school2')

    assert check_all_schools(['default-school', 'school2'])['valid'] is True


# ---------------------------------------------------------------------------
# macRaw and csvLine, added by load() for the callers that report errors
# ---------------------------------------------------------------------------

def test_load_keeps_the_raw_mac_beside_the_normalized_one(make_device_row, write_devices_csv):
    write_devices_csv([make_device_row(mac='aa-bb-cc-dd-ee-01')])

    device = Devices().devices[0]

    assert device['mac'] == 'AA:BB:CC:DD:EE:01'
    assert device['macRaw'] == 'aa-bb-cc-dd-ee-01'


def test_load_keeps_the_raw_mac_when_it_is_invalid(make_device_row, write_devices_csv):
    # normalize_mac() gives None, which names nothing in a report
    write_devices_csv([make_device_row(mac='not-a-mac')])

    device = Devices().devices[0]

    assert device['mac'] is None
    assert device['macRaw'] == 'not-a-mac'


def test_load_numbers_the_lines(make_device_row, write_devices_csv):
    write_devices_csv([
        make_device_row(hostname='pc01'),
        make_device_row(hostname='pc02', mac='AA:BB:CC:DD:EE:02', ip='10.16.1.11'),
    ])

    devices = Devices().devices

    assert [d['csvLine'] for d in devices] == [1, 2]


def test_load_line_numbers_account_for_comments(make_device_row, write_devices_csv, devices_path):
    path = devices_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = ';'.join(make_device_row(hostname='pc01'))
    path.write_text(f"# a comment\n{row}\n", encoding='utf-8')

    devices = Devices().devices

    # The comment is dropped from the list but still counts as a line
    assert len(devices) == 1
    assert devices[0]['csvLine'] == 2
