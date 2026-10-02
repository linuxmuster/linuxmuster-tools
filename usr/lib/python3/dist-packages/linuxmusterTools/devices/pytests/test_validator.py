import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest

import linuxmusterTools.devices.validator as validator_module
from linuxmusterTools.lmnconfig import ComputerRoles
from linuxmusterTools.devices.validator import (
    ERROR,
    prefixed_hostname,
    validate_device,
    validate_group,
    validate_hostname,
    validate_ip,
    validate_mac,
    validate_pxe_flag,
    validate_role,
    validate_room,
)


ROLES = ComputerRoles(
    accounts=('classroom-studentcomputer', 'staffcomputer', 'printer'),
    dns_only=('thinclient',),
    default='classroom-studentcomputer',
)


@pytest.fixture(autouse=True)
def fixed_sophomorix_ini(monkeypatch):
    """
    Pin what the rules read from sophomorix.ini, so the expectations below
    describe the rules and not the file installed on the machine running
    the tests.
    """

    class FixedSophomorixIni:
        computer_roles = ROLES

    monkeypatch.setattr(validator_module, 'SophomorixIni', FixedSophomorixIni)


def codes(findings):
    return [finding.code for finding in findings]


# ---------------------------------------------------------------------------
# hostname
# ---------------------------------------------------------------------------

def test_a_plain_hostname_is_valid():
    assert validate_hostname('pc01', role='staffcomputer') == []


def test_an_upper_case_hostname_is_accepted_as_is():
    # Nothing is rewritten in devices.csv: sophomorix lower cases the dns
    # node and upper cases the machine account out of the same field.
    assert validate_hostname('PC01', role='staffcomputer') == []


@pytest.mark.parametrize('hostname', ['pc 01', 'pc_01', 'pc.01', 'pc/01', ''])
def test_a_hostname_with_invalid_characters_is_refused(hostname):
    assert codes(validate_hostname(hostname)) == ['hostname.invalid']


def test_an_all_digits_hostname_is_refused():
    # AD naming rules: a name may not consist only of digits.
    assert codes(validate_hostname('12345')) == ['hostname.all_digits']


def test_a_hostname_starting_with_a_hyphen_is_refused():
    assert codes(validate_hostname('-pc01')) == ['hostname.leading_character']


def test_a_hostname_ending_with_a_hyphen_is_refused():
    assert codes(validate_hostname('pc01-')) == ['hostname.trailing_hyphen']


def test_a_hostname_of_fifteen_characters_is_valid():
    assert validate_hostname('abcdefghijklmno', role='staffcomputer') == []


def test_a_longer_hostname_is_refused_for_a_role_with_a_machine_account():
    findings = validate_hostname('abcdefghijklmnop', role='staffcomputer')

    assert codes(findings) == ['hostname.too_long']
    assert findings[0].severity == ERROR


def test_the_length_limit_does_not_apply_without_a_machine_account():
    # The limit comes from the sAMAccountName: a role that only gets a dns
    # node is not concerned.
    assert validate_hostname('abcdefghijklmnop', role='thinclient') == []


def test_the_length_limit_applies_to_the_prefixed_name():
    # school2-pc0123456789 is what lands in the AD.
    assert codes(validate_hostname('pc0123456789', role='staffcomputer', school='school2')) \
        == ['hostname.too_long']
    assert validate_hostname('pc0123456789', role='staffcomputer') == []


def test_an_empty_role_falls_back_to_the_default_role():
    # sophomorix substitutes COMPUTERROLE_DEFAULT, which has an account.
    assert codes(validate_hostname('abcdefghijklmnop', role='')) == ['hostname.too_long']


def test_an_unknown_role_is_treated_as_having_no_account():
    # The unknown role itself is what validate_role() reports.
    assert validate_hostname('abcdefghijklmnop', role='not-a-real-role') == []


def test_every_hostname_problem_is_reported_at_once():
    assert sorted(codes(validate_hostname('-pc01-', role='staffcomputer'))) == [
        'hostname.leading_character', 'hostname.trailing_hyphen',
    ]


# ---------------------------------------------------------------------------
# room, group, mac, ip, pxe, role
# ---------------------------------------------------------------------------

def test_a_valid_room_name():
    assert validate_room('R101') == []


def test_a_room_name_with_spaces_is_refused():
    assert codes(validate_room('room 101')) == ['room.invalid']


def test_a_room_name_is_not_limited_in_length():
    # A room is an ou, not a machine account.
    assert validate_room('a' * 40) == []


@pytest.mark.parametrize('group', ['win11', 'Win11_UEFI-2', 'g-pcs', 'g_pcs', '101'])
def test_a_valid_linbo_group(group):
    assert validate_group(group) == []


@pytest.mark.parametrize('group', ['bad group', 'group!', '', 'win11.2', 'room+1'])
def test_an_invalid_linbo_group(group):
    assert codes(validate_group(group)) == ['group.invalid']


@pytest.mark.parametrize('mac', [
    'AA:BB:CC:DD:EE:FF', 'aa:bb:cc:dd:ee:ff', 'AA-BB-CC-DD-EE-FF', 'AABBCCDDEEFF',
])
def test_the_three_accepted_mac_forms(mac):
    assert validate_mac(mac) == []


@pytest.mark.parametrize('mac', ['not-a-mac', 'AA:BB:CC:DD:EE', '', None])
def test_an_invalid_mac(mac):
    assert codes(validate_mac(mac)) == ['mac.invalid']


def test_a_valid_ip():
    assert validate_ip('10.16.1.10') == []


def test_dhcp_is_a_legal_ip_value():
    assert validate_ip('DHCP') == []


@pytest.mark.parametrize('ip', ['999.999.999.999', '10.16.1', 'dhcp', ''])
def test_an_invalid_ip(ip):
    assert codes(validate_ip(ip)) == ['ip.invalid']


@pytest.mark.parametrize('pxe_flag', ['0', '1', '9', '', '  ', 'ml'])
def test_a_valid_pxe_flag(pxe_flag):
    assert validate_pxe_flag(pxe_flag) == []


@pytest.mark.parametrize('pxe_flag', ['42', 'yes', '-1'])
def test_an_invalid_pxe_flag(pxe_flag):
    assert codes(validate_pxe_flag(pxe_flag)) == ['pxe.invalid']


def test_a_known_role():
    assert validate_role('printer') == []


def test_an_empty_role_is_the_default_one():
    assert validate_role('') == []


def test_an_unknown_role():
    assert codes(validate_role('not-a-real-role')) == ['role.unknown']


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def test_prefixed_hostname_leaves_default_school_alone():
    assert prefixed_hostname('pc01', 'default-school') == 'pc01'
    assert prefixed_hostname('pc01', 'school2') == 'school2-pc01'


# ---------------------------------------------------------------------------
# validate_device()
# ---------------------------------------------------------------------------

def test_validate_device_locates_its_findings():
    device = {
        'room': 'R101', 'hostname': 'pc01', 'group': 'g-pcs',
        'macRaw': 'nope', 'ip': '10.0.0.1', 'pxeFlag': '1',
        'sophomorixRole': 'staffcomputer', 'csvLine': 7,
    }

    findings = validate_device(device, school='school2', file='/tmp/school2.devices.csv')

    assert codes(findings) == ['mac.invalid']
    assert findings[0].school == 'school2'
    assert findings[0].file == '/tmp/school2.devices.csv'
    assert findings[0].line == 7
    assert findings[0].subject == 'pc01'


def test_validate_device_falls_back_to_the_normalized_mac():
    # A caller building a device by hand may only have 'mac'.
    device = {'hostname': 'pc01', 'room': 'R101', 'group': 'g-pcs',
              'mac': 'AA:BB:CC:DD:EE:01', 'ip': '10.0.0.1',
              'pxeFlag': '0', 'sophomorixRole': 'staffcomputer'}

    assert validate_device(device) == []


def test_a_finding_serializes_to_the_documented_keys():
    finding = validate_ip('999.999.999.999')[0]

    assert set(finding.as_dict()) == {
        'severity', 'code', 'message', 'field', 'value',
        'school', 'file', 'line', 'subject', 'related',
    }
