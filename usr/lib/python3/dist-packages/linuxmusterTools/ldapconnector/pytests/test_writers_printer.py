import ldap
import pytest
from copy import deepcopy
from unittest.mock import MagicMock

import linuxmusterTools.ldapconnector.writers.device as device_module
from linuxmusterTools.ldapconnector.writers.device import LMNPrinter
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


PRINTER_DN = 'CN=printer1,OU=printer-groups,OU=Devices,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
USER_DN = 'CN=johndoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
JANE_DN = 'CN=janedoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
GROUP_DN = 'CN=7a-students,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

SAMPLE_PRINTER = {
    'cn': 'printer1', 'description': '', 'displayName': 'printer1',
    'distinguishedName': PRINTER_DN,
    'mail': [], 'member': [USER_DN], 'memberOf': [], 'name': 'printer1',
    'objectClass': [], 'proxyAddresses': [], 'sAMAccountName': 'printer1',
    'sAMAccountType': '', 'sophomorixAdminClass': '', 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [],
    'sophomorixCustomMulti3': [], 'sophomorixCustomMulti4': [],
    'sophomorixCustomMulti5': [],
    'sophomorixHidden': False, 'sophomorixJoinable': True,
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '',
    'sophomorixIntrinsic3': '', 'sophomorixIntrinsic4': '',
    'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [],
    'sophomorixIntrinsicMulti3': [], 'sophomorixIntrinsicMulti4': [],
    'sophomorixIntrinsicMulti5': [],
    'sophomorixMailAlias': False, 'sophomorixMailList': False,
    'sophomorixMembers': ['johndoe'], 'sophomorixRole': '',
    'sophomorixSchoolname': 'default-school', 'sophomorixSchoolPrefix': '---',
    'sophomorixStatus': '', 'sophomorixType': 'printer',
    'dn': PRINTER_DN, 'all_members': [], 'membersCount': -1,
}

USERS = {'johndoe': USER_DN, 'janedoe': JANE_DN}
UNITS = {'7a-students': GROUP_DN}


def _getval(url, attr, **kw):
    """
    Answer like the ldap router does: /users/ only knows users, /units/ only
    knows groups, and both answer None for anything else.
    """

    name = url.rsplit('/', 1)[-1]

    if url.startswith('/users/'):
        return USERS.get(name)

    if url.startswith('/units/'):
        return UNITS.get(name)

    return None


@pytest.fixture
def printer(monkeypatch, mock_connect):
    monkeypatch.setattr(router, 'get', lambda url, **kw: deepcopy(SAMPLE_PRINTER))
    monkeypatch.setattr(router, 'getval', _getval)
    monkeypatch.setattr(device_module, 'devices_list', MagicMock(**{'get_host.return_value': None}))
    return LMNPrinter('printer1'), mock_connect


def _ldif(mock_connect):
    """Return the ldif of the single modify which was applied."""

    assert mock_connect.modify_s.call_count == 1
    return mock_connect.modify_s.call_args[0][1]


class TestLMNPrinterAddMembers:

    def test_a_whole_batch_is_one_single_modify(self, printer):
        p, conn = printer
        assert p.add_members(['janedoe', '7a-students']) == []

        # One modify only: a member list rewritten once per entity is what
        # let two concurrent patches overwrite each other.
        ldif = _ldif(conn)
        assert [op for op, _, _ in ldif] == [ldap.MOD_ADD, ldap.MOD_ADD]
        assert [value for _, _, value in ldif] == [[JANE_DN.encode()], [GROUP_DN.encode()]]

    def test_the_existing_members_are_not_deleted_first(self, printer):
        p, conn = printer
        p.add_members(['janedoe'])

        # No MOD_DELETE: the directory applies the addition to whatever the
        # member list holds at that moment, so nothing concurrent is lost.
        assert ldap.MOD_DELETE not in [op for op, _, _ in _ldif(conn)]

    def test_a_member_already_in_the_list_is_skipped(self, printer):
        p, conn = printer
        assert p.add_members(['johndoe']) == []

        # A MOD_ADD on a value already present makes the whole modify fail.
        assert not conn.modify_s.called

    def test_a_member_given_twice_is_added_once(self, printer):
        p, conn = printer
        p.add_members(['janedoe', 'janedoe'])

        assert len(_ldif(conn)) == 1

    def test_an_unknown_name_is_reported_and_the_rest_applied(self, printer):
        p, conn = printer
        failures = p.add_members(['ghost', 'janedoe'])

        assert [name for name, _ in failures] == ['ghost']
        assert 'was not found in ldap' in failures[0][1]
        assert len(_ldif(conn)) == 1

    def test_a_failed_write_is_reported_for_every_member(self, printer):
        p, conn = printer
        conn.modify_s.side_effect = Exception('insufficient access')

        failures = p.add_members(['janedoe', '7a-students'])

        assert [name for name, _ in failures] == ['janedoe', '7a-students']
        assert all('insufficient access' in message for _, message in failures)


class TestLMNPrinterRemoveMembers:

    def test_removing_is_one_targeted_modify(self, printer):
        p, conn = printer
        assert p.remove_members(['johndoe']) == []

        ldif = _ldif(conn)
        assert [op for op, _, _ in ldif] == [ldap.MOD_DELETE]
        assert [value for _, _, value in ldif] == [USER_DN.encode()]

    def test_removing_the_last_member_does_not_rewrite_the_list(self, printer):
        p, conn = printer
        p.remove_members(['johndoe'])

        # setattr() refuses an empty value, which used to answer 500. Deleting
        # the last value leaves no attribute behind, nothing else to do.
        assert [op for op, _, _ in _ldif(conn)] == [ldap.MOD_DELETE]

    def test_a_member_not_in_the_list_is_skipped(self, printer):
        p, conn = printer
        assert p.remove_members(['janedoe']) == []
        assert not conn.modify_s.called

    def test_an_unknown_name_is_reported(self, printer):
        p, conn = printer
        failures = p.remove_members(['ghost', 'johndoe'])

        assert [name for name, _ in failures] == ['ghost']
        assert len(_ldif(conn)) == 1


class TestLMNPrinterSingleMember:

    def test_add_member_raises_when_the_user_is_unknown(self, printer):
        p, _ = printer
        with pytest.raises(Exception, match='was not found in ldap'):
            p.add_member('ghost')

    def test_remove_member_raises_when_the_user_is_unknown(self, printer):
        p, _ = printer
        with pytest.raises(Exception, match='was not found in ldap'):
            p.remove_member('ghost')

    def test_add_member_applies_one_modify(self, printer):
        p, conn = printer
        p.add_member('janedoe')

        assert [op for op, _, _ in _ldif(conn)] == [ldap.MOD_ADD]
