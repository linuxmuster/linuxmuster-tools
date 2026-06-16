import pytest
from unittest.mock import MagicMock

from linuxmusterTools.ldapconnector.writers.group import LMNGroupCommon, LMNGroup
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


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
