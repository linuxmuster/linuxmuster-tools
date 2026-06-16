import pytest

from linuxmusterTools.ldapconnector.writers.user import (
    LMNUser, LMNStudent, LMNTeacher, LMNStaff, LMNSchoolAdmin, LMNGlobalAdmin,
)
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


USER_DN = 'CN=johndoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

SAMPLE_USER = {
    'cn': 'johndoe', 'displayName': 'John Doe', 'distinguishedName': USER_DN,
    'givenName': 'John', 'homeDirectory': '\\\\lmn\\students\\7a\\johndoe',
    'homeDrive': 'H:', 'mail': [], 'memberOf': [], 'name': 'johndoe',
    'objectClass': ['top', 'person', 'user'], 'preferredLanguage': '',
    'proxyAddresses': [], 'sAMAccountName': 'johndoe', 'sAMAccountType': '',
    'sn': 'Doe', 'sophomorixAdminClass': '7a', 'sophomorixAdminFile': 'students.csv',
    'sophomorixBirthdate': '', 'sophomorixCloudQuotaCalculated': [],
    'sophomorixComment': '', 'sophomorixCreationDate': '',
    'sophomorixCustom1': '', 'sophomorixCustom2': '', 'sophomorixCustom3': '',
    'sophomorixCustom4': '', 'sophomorixCustom5': '',
    'sophomorixCustomMulti1': [], 'sophomorixCustomMulti2': [],
    'sophomorixCustomMulti3': [], 'sophomorixCustomMulti4': [],
    'sophomorixCustomMulti5': [],
    'sophomorixDeactivationDate': '', 'sophomorixExamMode': [],
    'sophomorixExitAdminClass': '', 'sophomorixFirstnameASCII': 'John',
    'sophomorixFirstnameInitial': 'J', 'sophomorixFirstPassword': '',
    'sophomorixIntrinsic1': '', 'sophomorixIntrinsic2': '',
    'sophomorixIntrinsic3': '', 'sophomorixIntrinsic4': '',
    'sophomorixIntrinsic5': '',
    'sophomorixIntrinsicMulti1': [], 'sophomorixIntrinsicMulti2': [],
    'sophomorixIntrinsicMulti3': [], 'sophomorixIntrinsicMulti4': [],
    'sophomorixIntrinsicMulti5': [],
    'sophomorixMailQuotaCalculated': [], 'sophomorixMailQuota': [],
    'sophomorixQuota': [], 'sophomorixRole': 'student',
    'sophomorixSchoolname': 'default-school', 'sophomorixSchoolPrefix': '---',
    'sophomorixSessions': [], 'sophomorixStatus': 'U',
    'sophomorixSurnameASCII': 'Doe', 'sophomorixSurnameInitial': 'D',
    'sophomorixTolerationDate': '', 'sophomorixUnid': '',
    'sophomorixUserToken': '', 'sophomorixWebuiDashboard': [],
    'sophomorixWebuiPermissionsCalculated': [], 'thumbnailPhoto': '',
    'unixHomeDirectory': '/home/default-school/students/7a/johndoe',
    'userAccountControl': 66048, 'whenChanged': '',
    'dn': USER_DN, 'children': [], 'customFields': {}, 'examMode': False,
    'examTeacher': '', 'examBaseCn': '', 'internet': False, 'intranet': False,
    'isAdmin': False, 'lmnsessions': [], 'parents': [], 'permissions': {},
    'printers': [], 'printing': False, 'projects': [], 'schoolclasses': ['7a'],
    'school': 'default-school', 'webfilter': False, 'wifi': False,
}


class TestLMNUserInit:

    def test_existing_user_loads_data(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        assert u.data['cn'] == 'johndoe'
        assert u.new is False

    def test_missing_user_sets_new_true(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        u = LMNUser('newuser')
        assert u.new is True
        assert u.data['cn'] == 'newuser'

    def test_invalid_cn_raises(self, monkeypatch, mock_connect):
        with pytest.raises(Exception):
            LMNUser('invalid cn with spaces')

    def test_getattr_returns_value(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        assert u.getattr('sophomorixRole') == 'student'

    def test_getattr_unknown_key_returns_none(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        assert u.getattr('notAField') is None


class TestLMNUserSetattr:

    def test_setattr_calls_ldap_modify_for_existing_user(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        u.setattr(data={'sophomorixStatus': 'A'})
        assert mock_connect.modify_s.called

    def test_setattr_blocked_when_user_is_new(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        u = LMNUser('newuser')
        u.setattr(data={'sophomorixStatus': 'A'})
        assert not mock_connect.modify_s.called


class TestLMNUserDelattr:

    def test_delattr_calls_ldap_modify_for_existing_user(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        u.delattr(data={'sophomorixComment': ''})
        assert mock_connect.modify_s.called

    def test_delattr_blocked_when_user_is_new(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        u = LMNUser('newuser')
        u.delattr(data={'sophomorixComment': ''})
        assert not mock_connect.modify_s.called


class TestLMNUserRename:

    def test_rename_calls_ldap_rename(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        u.rename('johndoe2')
        assert mock_connect.rename_s.called

    def test_rename_blocked_when_user_is_new(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        u = LMNUser('newuser')
        u.rename('newuser2')
        assert not mock_connect.rename_s.called

    def test_rename_skipped_for_invalid_cn(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        u.rename('invalid name with spaces')
        assert not mock_connect.rename_s.called


class TestLMNUserDelete:

    def test_delete_calls_ldap_delete(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        u.delete()
        assert mock_connect.delete_s.called

    def test_delete_blocked_when_user_is_new(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        u = LMNUser('newuser')
        u.delete()
        assert not mock_connect.delete_s.called


class TestRoleChecks:

    def test_student_wrong_role_raises(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_USER, sophomorixRole='teacher')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        with pytest.raises(Exception, match='is not a student'):
            LMNStudent('johndoe')

    def test_teacher_wrong_role_raises(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_USER, sophomorixRole='student')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        with pytest.raises(Exception, match='is not a teacher'):
            LMNTeacher('johndoe')

    def test_staff_wrong_role_raises(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_USER, sophomorixRole='student')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        with pytest.raises(Exception, match='is not a staff member'):
            LMNStaff('johndoe')

    def test_schooladmin_wrong_role_raises(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_USER, sophomorixRole='student')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        with pytest.raises(Exception, match='is not a schooladministrator'):
            LMNSchoolAdmin('johndoe')

    def test_globaladmin_wrong_role_raises(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_USER, sophomorixRole='student')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        with pytest.raises(Exception, match='is not a globaladministrator'):
            LMNGlobalAdmin('johndoe')
