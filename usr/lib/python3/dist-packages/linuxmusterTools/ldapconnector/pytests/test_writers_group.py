import pytest
from unittest.mock import MagicMock

from linuxmusterTools.ldapconnector.writers.group import LMNGroupCommon, LMNGroup, find_legacy_groups
from linuxmusterTools.ldapconnector.urls.ldaprouter import router
from linuxmusterTools.lmnconfig import LDAP_CONTEXT
from linuxmusterTools.common import SchoolError


GROUP_DN = 'CN=7a,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
USER_DN = 'CN=johndoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

SAMPLE_GROUP = {
    'cn': '7a', 'description': '', 'displayName': '7a',
    'distinguishedName': GROUP_DN,
    'mail': [], 'member': [USER_DN], 'memberOf': [], 'name': '7a',
    'objectClass': [], 'proxyAddresses': [], 'sAMAccountName': '7a',
    'sAMAccountType': '', 'sophomorixAdminClass': '', 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [],
    'sophomorixCustomMulti3': [], 'sophomorixCustomMulti4': [],
    'sophomorixCustomMulti5': [],
    'sophomorixHidden': False, 'sophomorixJoinable': False,
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '',
    'sophomorixIntrinsic3': '', 'sophomorixIntrinsic4': '',
    'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [],
    'sophomorixIntrinsicMulti3': [], 'sophomorixIntrinsicMulti4': [],
    'sophomorixIntrinsicMulti5': [],
    'sophomorixMailAlias': False, 'sophomorixMailList': False,
    'sophomorixMembers': ['johndoe'], 'sophomorixRole': '',
    'sophomorixSchoolname': 'default-school', 'sophomorixSchoolPrefix': '---',
    'sophomorixStatus': '', 'sophomorixType': 'adminclass',
    'dn': GROUP_DN, 'all_members': [], 'membersCount': -1,
}


@pytest.fixture
def group(monkeypatch, mock_connect):
    monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
    return LMNGroupCommon('7a'), mock_connect


class TestLMNGroupCommonInit:

    def test_init_loads_data(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        g = LMNGroupCommon('7a')
        assert g.data['cn'] == '7a'
        assert g.cn == '7a'

    def test_init_raises_when_group_not_found(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        with pytest.raises(Exception, match='was not found in ldap'):
            LMNGroupCommon('nonexistent')

    def test_getattr_returns_field_value(self, group):
        g, _ = group
        assert g.getattr('cn') == '7a'

    def test_getattr_unknown_key_returns_none(self, group):
        g, _ = group
        assert g.getattr('nonExistentAttr') is None


class TestLMNGroupCommonAddMember:

    def test_add_member_calls_ldap_modify(self, monkeypatch, mock_connect):
        new_user_dn = 'CN=janedoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: new_user_dn)

        g = LMNGroupCommon('7a')
        g.add_member('janedoe')
        assert mock_connect.modify_s.called

    def test_add_member_raises_when_user_not_found(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: None)

        g = LMNGroupCommon('7a')
        with pytest.raises(Exception, match='was not found in ldap'):
            g.add_member('nonexistent')


class TestLMNGroupCommonAddMembers:

    def test_valid_members_are_added_despite_invalid_ones_in_the_batch(self, monkeypatch, mock_connect):
        dns = {
            'janedoe': 'CN=janedoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan',
            'bobdoe': 'CN=bobdoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan',
        }
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: dns.get(url.rsplit('/', 1)[-1]))

        g = LMNGroupCommon('7a')
        failures = g.add_members(['ghost1', 'janedoe', 'ghost2', 'bobdoe'])

        assert [f[0] for f in failures] == ['ghost1', 'ghost2']
        assert all('was not found in ldap' in message for _, message in failures)
        # janedoe and bobdoe were both still applied despite the invalid entries.
        assert mock_connect.modify_s.call_count == 2

    def test_all_valid_members_returns_no_failures(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: USER_DN)

        g = LMNGroupCommon('7a')
        failures = g.add_members(['janedoe', 'bobdoe'])

        assert failures == []


class TestLMNGroupCommonRemoveMember:

    def test_remove_member_calls_ldap_modify(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: USER_DN)

        g = LMNGroupCommon('7a')
        g.remove_member('johndoe')
        assert mock_connect.modify_s.called

    def test_remove_member_no_op_when_not_in_group(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_GROUP)
        data['member'] = []
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: USER_DN)

        g = LMNGroupCommon('7a')
        mock_connect.modify_s.reset_mock()
        g.remove_member('johndoe')
        assert not mock_connect.modify_s.called

    def test_remove_member_raises_when_user_not_found(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: None)

        g = LMNGroupCommon('7a')
        with pytest.raises(Exception, match='was not found in ldap'):
            g.remove_member('ghost')


class TestLMNGroupCommonRemoveMembers:

    def test_valid_members_are_removed_despite_invalid_ones_in_the_batch(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: USER_DN if url.endswith('/johndoe') else None)

        g = LMNGroupCommon('7a')
        failures = g.remove_members(['ghost', 'johndoe'])

        assert failures == [('ghost', 'The object ghost was not found in ldap.')]
        assert mock_connect.modify_s.called

    def test_all_valid_members_returns_no_failures(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: USER_DN)

        g = LMNGroupCommon('7a')
        failures = g.remove_members(['johndoe'])

        assert failures == []


class TestLMNGroupCommonRemoveAllMembers:

    def test_remove_all_members_calls_ldap_modify(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))

        g = LMNGroupCommon('7a')
        g.remove_all_members()
        assert mock_connect.modify_s.called


class TestLMNGroupCommonSetDelattr:

    def test_setattr_calls_ldap_modify(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        g = LMNGroupCommon('7a')
        g.setattr(data={'sophomorixStatus': 'U'})
        assert mock_connect.modify_s.called

    def test_delattr_calls_ldap_modify(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        g = LMNGroupCommon('7a')
        g.delattr(data={'sophomorixStatus': ''})
        assert mock_connect.modify_s.called


class TestLMNGroupCommonDelete:

    def test_delete_calls_ldap_delete(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_GROUP))
        g = LMNGroupCommon('7a')
        g.delete()
        assert mock_connect.delete_s.called
        assert mock_connect.delete_s.call_args[0][0] == GROUP_DN


SOPHOMORIX_GROUP_DN = 'CN=robotics,OU=Groups,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

SAMPLE_SOPHOMORIX_GROUP = {
    'cn': 'robotics', 'description': 'robotics', 'displayName': 'robotics',
    'distinguishedName': SOPHOMORIX_GROUP_DN,
    'mail': [], 'member': [], 'memberOf': [], 'name': 'robotics',
    'objectClass': [], 'proxyAddresses': [], 'sAMAccountName': 'robotics',
    'sAMAccountType': '', 'sophomorixAddMailQuota': [], 'sophomorixAddQuota': [],
    'sophomorixAdminClass': '', 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [],
    'sophomorixCustomMulti3': [], 'sophomorixCustomMulti4': [],
    'sophomorixCustomMulti5': [],
    'sophomorixHidden': False, 'sophomorixJoinable': False,
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '',
    'sophomorixIntrinsic3': '', 'sophomorixIntrinsic4': '',
    'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [],
    'sophomorixIntrinsicMulti3': [], 'sophomorixIntrinsicMulti4': [],
    'sophomorixIntrinsicMulti5': [],
    'sophomorixMailAlias': False, 'sophomorixMailList': False,
    'sophomorixMailQuota': [], 'sophomorixMembers': [], 'sophomorixQuota': [],
    'sophomorixRole': '',
    'sophomorixSchoolname': 'default-school', 'sophomorixSchoolPrefix': '---',
    'sophomorixStatus': '', 'sophomorixType': 'sophomorix-group',
    'dn': SOPHOMORIX_GROUP_DN, 'all_members': [], 'membersCount': -1,
}


class TestLMNGroupInit:

    def test_existing_group_new_is_false(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SOPHOMORIX_GROUP))
        g = LMNGroup('robotics')
        assert g.new is False
        assert g.data['cn'] == 'robotics'

    def test_missing_group_new_is_true(self, monkeypatch, mock_connect):
        fake_get = lambda url, **kw: [] if url.startswith('/ou') else ({} if url.startswith('/groups/') else {'cn': 'default-school'})
        monkeypatch.setattr(router, 'get', fake_get)
        g = LMNGroup('newgroup')
        assert g.new is True

    def test_missing_group_data_has_expected_dn(self, monkeypatch, mock_connect):
        fake_get = lambda url, **kw: [] if url.startswith('/ou') else ({} if url.startswith('/groups/') else {'cn': 'default-school'})
        monkeypatch.setattr(router, 'get', fake_get)
        g = LMNGroup('newgroup')
        assert 'CN=newgroup' in g.data['distinguishedName']
        assert 'OU=LMNGroups' in g.data['distinguishedName']


class TestLMNGroupGlobalSchoolGuard:

    def test_raises_before_any_ldap_call(self, monkeypatch, mock_connect):
        def fake_get(url, **kw):
            raise AssertionError('LMNGroup must not touch ldap when school is "global"')

        monkeypatch.setattr(router, 'get', fake_get)
        with pytest.raises(SchoolError, match="school='global'"):
            LMNGroup('robotics', school='global')


class TestLMNGroupCreate:

    def test_create_calls_add_group_and_reloads(self, monkeypatch, mock_connect):
        calls = {'n': 0}

        def fake_get(url, **kw):
            calls['n'] += 1
            # Not found on init, found once created (reload after create()).
            return {} if calls['n'] == 1 else dict(SAMPLE_SOPHOMORIX_GROUP)

        monkeypatch.setattr(router, 'get', fake_get)
        g = LMNGroup('robotics')
        g.create()
        assert mock_connect.add_s.called
        assert g.new is False
        assert g.data['cn'] == 'robotics'

    def test_create_prints_warning_when_already_exists(self, monkeypatch, mock_connect, capsys):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SOPHOMORIX_GROUP))
        g = LMNGroup('robotics')
        mock_connect.add_s.reset_mock()
        g.create()
        output = capsys.readouterr().out
        assert 'already exists' in output
        assert not mock_connect.add_s.called


class TestLMNGroupDelete:

    def test_delete_calls_ldap_delete(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SOPHOMORIX_GROUP))
        g = LMNGroup('robotics')
        g.delete()
        assert mock_connect.delete_s.called
        assert mock_connect.delete_s.call_args[0][0] == SOPHOMORIX_GROUP_DN


class TestLMNGroupMigrate:

    def test_migrate_moves_and_relabels_sophomorix_group(self, monkeypatch, mock_connect):
        legacy_group = dict(SAMPLE_SOPHOMORIX_GROUP, member=[USER_DN])
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(legacy_group))
        g = LMNGroup('robotics')
        g.migrate()

        assert mock_connect.rename_s.called
        old_dn, new_rdn, new_ou = mock_connect.rename_s.call_args[0]
        assert old_dn == SOPHOMORIX_GROUP_DN
        assert new_rdn == 'CN=robotics'
        assert new_ou == f"OU=LMNGroups,OU=default-school,{LDAP_CONTEXT}"
        assert mock_connect.modify_s.called

    def test_migrate_relabels_the_post_move_dn_not_the_stale_one(self, monkeypatch, mock_connect):
        # Simulates the dn actually changing once the group has been moved:
        # the sophomorixType relabel must target the NEW dn, not the one
        # captured in self.data before _move() ran (which no longer exists
        # once the rename has gone through).
        old_data = dict(SAMPLE_SOPHOMORIX_GROUP, member=[USER_DN])
        new_dn = f"CN=robotics,OU=LMNGroups,OU=default-school,{LDAP_CONTEXT}"
        new_data = dict(old_data, distinguishedName=new_dn, sophomorixType='lmngroup')

        calls = {'n': 0}
        def fake_get(url, **kw):
            calls['n'] += 1
            return dict(old_data) if calls['n'] == 1 else dict(new_data)

        monkeypatch.setattr(router, 'get', fake_get)
        g = LMNGroup('robotics')
        g.migrate()

        modify_dn = mock_connect.modify_s.call_args[0][0]
        assert modify_dn == new_dn

    def test_migrate_is_no_op_for_already_migrated_group(self, monkeypatch, mock_connect, capsys):
        lmngroup_data = dict(SAMPLE_SOPHOMORIX_GROUP, sophomorixType='lmngroup')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(lmngroup_data))
        g = LMNGroup('robotics')
        g.migrate()

        output = capsys.readouterr().out
        assert 'already a lmngroup' in output
        assert not mock_connect.rename_s.called


class TestFindLegacyGroups:

    def test_find_legacy_groups_filters_sophomorix_type(self, monkeypatch, mock_connect):
        groups = [
            dict(SAMPLE_SOPHOMORIX_GROUP),
            dict(SAMPLE_SOPHOMORIX_GROUP, cn='alreadymigrated', sophomorixType='lmngroup'),
        ]
        monkeypatch.setattr(router, 'get', lambda url, **kw: list(groups))

        legacy = find_legacy_groups()
        assert [g['cn'] for g in legacy] == ['robotics']
