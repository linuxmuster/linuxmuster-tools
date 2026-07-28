import ldb
import pytest

import linuxmusterTools.passwords as passwords_module
import linuxmusterTools.samba_util.samba_tool as samba_tool_module
from linuxmusterTools.passwords import MinLengthRule
from linuxmusterTools.ldapconnector.writers import user as user_module
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


class TestLMNUserTestFirstPassword:

    def test_returns_check_password_result(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_USER, sophomorixFirstPassword='Muster!1')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        calls = {}

        def fake_check_password(dn, password):
            calls['dn'] = dn
            calls['password'] = password
            return True

        monkeypatch.setattr(user_module, 'check_password', fake_check_password)
        u = LMNUser('johndoe')
        assert u.test_first_password() is True
        assert calls == {'dn': USER_DN, 'password': 'Muster!1'}

    def test_returns_false_on_invalid_credentials(self, monkeypatch, mock_connect):
        data = dict(SAMPLE_USER, sophomorixFirstPassword='wrong')
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(data))
        monkeypatch.setattr(user_module, 'check_password', lambda dn, password: False)
        u = LMNUser('johndoe')
        assert u.test_first_password() is False

    def test_propagates_check_password_exception(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))

        def raising_check_password(dn, password):
            raise RuntimeError('ldap unreachable')

        monkeypatch.setattr(user_module, 'check_password', raising_check_password)
        u = LMNUser('johndoe')
        with pytest.raises(RuntimeError, match='ldap unreachable'):
            u.test_first_password()


class TestLMNUserSetActualPassword:

    def test_calls_samdb_setpassword(self, monkeypatch, mock_connect, tmp_path):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        samdb_path = tmp_path / 'sam.ldb'
        samdb_path.write_text('not a real db')
        calls = []
        fake_samdb = type('FakeSamDB', (), {
            'setpassword': lambda self, dn, password: calls.append((dn, password)),
        })()
        monkeypatch.setattr(samba_tool_module, 'load_samba_bindings', lambda: None)
        monkeypatch.setattr(samba_tool_module, 'SAMDB_PATH', str(samdb_path))
        monkeypatch.setattr(samba_tool_module, 'SamDB', lambda **kw: fake_samdb)
        monkeypatch.setattr(samba_tool_module, 'system_session', lambda: None)
        monkeypatch.setattr(samba_tool_module, 'creds', None)
        monkeypatch.setattr(samba_tool_module, 'lp', None)

        u = LMNUser('johndoe')
        u.set_actual_password('N3wP@ss!')

        assert calls == [('samaccountname=johndoe', 'N3wP@ss!')]

    def test_raises_when_samdb_path_missing(self, monkeypatch, mock_connect, tmp_path):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        monkeypatch.setattr(samba_tool_module, 'load_samba_bindings', lambda: None)
        monkeypatch.setattr(samba_tool_module, 'SAMDB_PATH', str(tmp_path / 'missing.ldb'))

        u = LMNUser('johndoe')
        with pytest.raises(RuntimeError, match='could not be opened'):
            u.set_actual_password('N3wP@ss!')

    def test_wraps_ldb_error(self, monkeypatch, mock_connect, tmp_path):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        samdb_path = tmp_path / 'sam.ldb'
        samdb_path.write_text('not a real db')

        def raise_ldb_error(self, dn, password):
            raise ldb.LdbError(1, 'Password does not meet complexity requirements')

        fake_samdb = type('FakeSamDB', (), {'setpassword': raise_ldb_error})()
        monkeypatch.setattr(samba_tool_module, 'load_samba_bindings', lambda: None)
        monkeypatch.setattr(samba_tool_module, 'SAMDB_PATH', str(samdb_path))
        monkeypatch.setattr(samba_tool_module, 'SamDB', lambda **kw: fake_samdb)
        monkeypatch.setattr(samba_tool_module, 'system_session', lambda: None)
        monkeypatch.setattr(samba_tool_module, 'creds', None)
        monkeypatch.setattr(samba_tool_module, 'lp', None)
        monkeypatch.setattr(samba_tool_module, 'LdbError', ldb.LdbError)

        u = LMNUser('johndoe')
        with pytest.raises(Exception, match='complexity requirements'):
            u.set_actual_password('weak')


class TestLMNUserSetFirstPassword:

    def test_writes_first_password_attribute_and_current_password(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        calls = []
        monkeypatch.setattr(u, 'set_actual_password', lambda password: calls.append(password))

        u.set_first_password('N3wFirstP@ss!')

        assert mock_connect.modify_s.called
        assert calls == ['N3wFirstP@ss!']


class TestLMNUserSetRandomFirstPassword:

    def test_generates_password_at_policy_minimum_length_and_applies_it(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        set_first_calls = []
        monkeypatch.setattr(u, 'set_first_password', lambda password: set_first_calls.append(password))

        fake_policy = type('FakePolicy', (), {
            'rules': (MinLengthRule(length=8),),
            'validate': lambda self, password, username=None: type('Result', (), {'ok': True})(),
        })()
        fake_provider = type('FakeProvider', (), {
            'get_policy': lambda self, role, school='default-school': fake_policy,
        })()
        monkeypatch.setattr(passwords_module, 'PasswordPolicyProvider', lambda: fake_provider)

        generated = u.set_random_first_password()

        assert len(generated) == 8
        assert set_first_calls == [generated]

    def test_falls_back_to_default_length_when_policy_has_no_min_length_rule(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')
        monkeypatch.setattr(u, 'set_first_password', lambda password: None)

        fake_policy = type('FakePolicy', (), {
            'rules': (),
            'validate': lambda self, password, username=None: type('Result', (), {'ok': True})(),
        })()
        fake_provider = type('FakeProvider', (), {
            'get_policy': lambda self, role, school='default-school': fake_policy,
        })()
        monkeypatch.setattr(passwords_module, 'PasswordPolicyProvider', lambda: fake_provider)

        generated = u.set_random_first_password()

        assert len(generated) == 8

    def test_raises_when_no_candidate_satisfies_policy(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_USER))
        u = LMNUser('johndoe')

        fake_policy = type('FakePolicy', (), {
            'rules': (),
            'validate': lambda self, password, username=None: type('Result', (), {'ok': False})(),
        })()
        fake_provider = type('FakeProvider', (), {
            'get_policy': lambda self, role, school='default-school': fake_policy,
        })()
        monkeypatch.setattr(passwords_module, 'PasswordPolicyProvider', lambda: fake_provider)

        with pytest.raises(RuntimeError, match='100 attempts'):
            u.set_random_first_password()


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
