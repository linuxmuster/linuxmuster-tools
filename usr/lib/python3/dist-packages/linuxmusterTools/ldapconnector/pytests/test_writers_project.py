import pytest

from linuxmusterTools.ldapconnector.writers.project import LMNProject
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


PROJECT_DN = 'CN=p_robotics,OU=Projects,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

SAMPLE_PROJECT = {
    'cn': 'robotics', 'description': 'robotics', 'displayName': 'robotics',
    'distinguishedName': PROJECT_DN, 'mail': [], 'member': [], 'name': 'robotics',
    'objectClass': [], 'proxyAddresses': [], 'sAMAccountName': 'robotics',
    'sAMAccountType': '', 'sophomorixAddMailQuota': [], 'sophomorixAddQuota': [],
    'sophomorixAdminGroups': [], 'sophomorixAdmins': [], 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [],
    'sophomorixCustomMulti3': [], 'sophomorixCustomMulti4': [],
    'sophomorixCustomMulti5': [],
    'sophomorixHidden': False,
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '',
    'sophomorixIntrinsic3': '', 'sophomorixIntrinsic4': '',
    'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [],
    'sophomorixIntrinsicMulti3': [], 'sophomorixIntrinsicMulti4': [],
    'sophomorixIntrinsicMulti5': [],
    'sophomorixJoinable': False, 'sophomorixMailAlias': False,
    'sophomorixMailList': False, 'sophomorixMailQuota': [],
    'sophomorixMaxMembers': 0, 'sophomorixMemberGroups': [],
    'sophomorixMembers': ['johndoe'], 'sophomorixQuota': [],
    'sophomorixSchoolname': 'default-school', 'sophomorixStatus': '',
    'sophomorixType': 'project',
    'dn': PROJECT_DN, 'all_members': [], 'all_admins': [],
    'membersCount': -1, 'adminsCount': -1,
}


class TestLMNProjectInit:

    def test_existing_project_new_is_false(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_PROJECT))
        p = LMNProject('robotics')
        assert p.new is False
        assert p.data['cn'] == 'robotics'

    def test_missing_project_new_is_true(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        p = LMNProject('newproject')
        assert p.new is True

    def test_missing_project_data_has_expected_dn(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        p = LMNProject('newproject')
        assert 'newproject' in p.data['distinguishedName']
        assert 'OU=Projects' in p.data['distinguishedName']

    def test_non_default_school_uses_school_prefix_in_dn(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        p = LMNProject('newproject', school='secondary')
        assert 'p_secondary-newproject' in p.data['distinguishedName']


class TestLMNProjectCreate:

    def test_create_calls_add_group_when_new(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        p = LMNProject('newproject')
        p.create()
        assert mock_connect.add_s.called
        assert p.new is False

    def test_create_prints_warning_when_already_exists(self, monkeypatch, mock_connect, capsys):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_PROJECT))
        p = LMNProject('robotics')
        p.create()
        output = capsys.readouterr().out
        assert 'already exists' in output
        assert not mock_connect.add_s.called


class TestLMNProjectAddRemoveMember:

    def test_add_member_calls_ldap_modify(self, monkeypatch, mock_connect):
        new_user_dn = 'CN=janedoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_PROJECT))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: new_user_dn)
        p = LMNProject('robotics')
        p.add_member('janedoe')
        assert mock_connect.modify_s.called

    def test_remove_member_calls_ldap_modify(self, monkeypatch, mock_connect):
        user_dn = 'CN=johndoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
        data = dict(SAMPLE_PROJECT)
        data['member'] = [user_dn]
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: user_dn)
        p = LMNProject('robotics')
        p.remove_member('johndoe')
        assert mock_connect.modify_s.called
