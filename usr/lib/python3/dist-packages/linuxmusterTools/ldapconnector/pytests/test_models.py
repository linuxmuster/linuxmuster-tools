import pytest
from unittest.mock import MagicMock

from linuxmusterTools.ldapconnector.models.common import LMNModel
from linuxmusterTools.ldapconnector.models.lmnusermixin import LMNUserMixin
from linuxmusterTools.ldapconnector.models.lmngroup import LMNGroupModel
from linuxmusterTools.ldapconnector.models.lmnproject import LMNProjectModel
from linuxmusterTools.ldapconnector.urls.ldaprouter import router

DN = 'CN=johndoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

# Minimal concrete class to test LMNModel methods
class _Concrete(LMNModel):
    pass


class _FakeUser(LMNUserMixin):
    """Minimal user object to test mixin methods directly."""

    def split_dn(self, dn):
        return [node.split('=') for node in dn.split(',')]

    def common_name(self, dn):
        try:
            return self.split_dn(dn)[0][1]
        except (IndexError, KeyError):
            return ''


class TestLMNModel:

    def test_split_dn_produces_pairs(self):
        pairs = LMNModel.split_dn(DN)
        assert pairs[0] == ['CN', 'johndoe']
        assert pairs[1] == ['OU', '7a']

    def test_split_dn_on_simple_dn(self):
        pairs = LMNModel.split_dn('CN=test,DC=example,DC=com')
        assert len(pairs) == 3
        assert pairs[2] == ['DC', 'com']

    def test_common_name_extracts_first_value(self):
        obj = _Concrete()
        assert obj.common_name(DN) == 'johndoe'

    def test_common_name_on_ou_dn(self):
        obj = _Concrete()
        assert obj.common_name('OU=Students,DC=test,DC=lan') == 'Students'


class TestCheckSchoolclassNumber:

    def test_numeric_prefix_returns_int(self):
        assert LMNUserMixin._check_schoolclass_number('7a') == 7

    def test_numeric_only_returns_int(self):
        assert LMNUserMixin._check_schoolclass_number('10') == 10

    def test_no_digit_returns_large_number(self):
        assert LMNUserMixin._check_schoolclass_number('attic') == 10000000

    def test_no_digit_at_all_returns_large_number(self):
        assert LMNUserMixin._check_schoolclass_number('abc') == 10000000


class TestExtractSchoolclasses:

    def setup_method(self):
        self.user = _FakeUser()

    def test_extracts_schoolclass_from_students_ou(self):
        membership = [
            f'CN=7a,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_schoolclasses(membership)
        assert '7a' in result

    def test_excludes_teachers_subgroup(self):
        membership = [
            'CN=7a-teachers,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_schoolclasses(membership)
        assert result == []

    def test_excludes_parents_subgroup(self):
        membership = [
            'CN=7a-parents,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_schoolclasses(membership)
        assert result == []

    def test_excludes_students_subgroup(self):
        membership = [
            'CN=7a-students,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_schoolclasses(membership)
        assert result == []

    def test_ignores_non_students_ou(self):
        membership = [
            'CN=p_test,OU=Projects,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_schoolclasses(membership)
        assert result == []

    def test_sorts_numerically(self):
        membership = [
            'CN=10a,OU=10a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
            'CN=7b,OU=7b,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
            'CN=7a,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_schoolclasses(membership)
        assert result.index('7a') < result.index('7b')
        assert result.index('7b') < result.index('10a')


class TestExtractProjects:

    def setup_method(self):
        self.user = _FakeUser()

    def test_extracts_from_projects_ou(self):
        membership = [
            'CN=p_robotics,OU=Projects,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_projects(membership)
        assert 'p_robotics' in result

    def test_ignores_students_ou(self):
        membership = [
            'CN=7a,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_projects(membership)
        assert result == []


class TestExtractPrinters:

    def setup_method(self):
        self.user = _FakeUser()

    def test_extracts_from_printer_groups_ou(self):
        membership = [
            'CN=printerA,OU=printer-groups,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_printers(membership)
        assert 'printerA' in result

    def test_ignores_other_ous(self):
        membership = [
            'CN=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ]
        result = self.user.extract_printers(membership)
        assert result == []


class TestExtractManagement:

    def _make_user(self, school, groups):
        user = _FakeUser()
        user.sophomorixSchoolname = school
        user.memberOf = groups
        return user

    def test_internet_group_detected(self):
        user = self._make_user('default-school', [
            'CN=internet,OU=Management,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ])
        user.extract_management()
        assert user.internet is True
        assert user.intranet is False

    def test_wifi_group_detected(self):
        user = self._make_user('default-school', [
            'CN=wifi,OU=Management,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ])
        user.extract_management()
        assert user.wifi is True

    def test_non_default_school_uses_prefix(self):
        user = self._make_user('secondary', [
            'CN=secondary-internet,OU=Management,OU=secondary,OU=SCHOOLS,DC=test,DC=lan',
        ])
        user.extract_management()
        assert user.internet is True

    def test_wrong_school_prefix_not_matched(self):
        user = self._make_user('secondary', [
            'CN=internet,OU=Management,OU=default-school,OU=SCHOOLS,DC=test,DC=lan',
        ])
        user.extract_management()
        assert user.internet is False

    def test_no_groups_all_false(self):
        user = self._make_user('default-school', [])
        user.extract_management()
        assert user.internet is False
        assert user.wifi is False
        assert user.printing is False


class TestParseSessions:

    def test_parses_session_string(self):
        user = _FakeUser()
        user.sophomorixSessions = ['sess1;sessionname;user1,user2']
        user.parse_sessions()
        assert len(user.lmnsessions) == 1
        session = user.lmnsessions[0]
        assert session.sid == 'sess1'
        assert session.name == 'sessionname'
        assert session.members == ['user1', 'user2']
        assert session.membersCount == 2

    def test_empty_sessions_list(self):
        user = _FakeUser()
        user.sophomorixSessions = []
        user.parse_sessions()
        assert user.lmnsessions == []

    def test_session_with_no_members(self):
        user = _FakeUser()
        user.sophomorixSessions = ['sess1;paused;']
        user.parse_sessions()
        assert user.lmnsessions[0].membersCount == 0


class TestParseExam:

    def test_empty_exam_mode_sets_false(self):
        user = _FakeUser()
        user.sophomorixExamMode = []
        user.cn = 'johndoe'
        user.parse_exam()
        assert user.examMode is False
        assert user.examTeacher == ''
        assert user.examBaseCn == ''

    def test_exam_mode_with_dashes_sets_false(self):
        user = _FakeUser()
        user.sophomorixExamMode = ['---']
        user.cn = 'johndoe'
        user.parse_exam()
        assert user.examMode is False

    def test_active_exam_mode_sets_teacher_and_base(self):
        user = _FakeUser()
        user.sophomorixExamMode = ['teacher1']
        user.cn = 'johndoe-exam'
        user.parse_exam()
        assert user.examMode is True
        assert user.examTeacher == 'teacher1'
        assert user.examBaseCn == 'johndoe'


class TestGroupModelGetAllMembers:

    def _make_group(self, member_dns):
        g = LMNGroupModel(
            cn='7a', description='', displayName='7a',
            distinguishedName='CN=7a,OU=SCHOOLS,DC=test,DC=lan',
            mail=[], member=member_dns, memberOf=[], name='7a', objectClass=[],
            proxyAddresses=[], sAMAccountName='7a', sAMAccountType='',
            sophomorixAdminClass='', sophomorixCreationDate='',
            sophomorixCustom1='', sophomorixCustom2='', sophomorixCustom3='',
            sophomorixCustom4='', sophomorixCustom5='',
            sophomorixCustomMulti1=[], sophomorixCustomMulti2=[],
            sophomorixCustomMulti3=[], sophomorixCustomMulti4=[],
            sophomorixCustomMulti5=[],
            sophomorixHidden=False, sophomorixJoinable=False,
            sophomorixIntrinsic1='', sophomorixIntrinsic2='',
            sophomorixIntrinsic3='', sophomorixIntrinsic4='',
            sophomorixIntrinsic5='',
            sophomorixIntrinsicMulti1=[], sophomorixIntrinsicMulti2=[],
            sophomorixIntrinsicMulti3=[], sophomorixIntrinsicMulti4=[],
            sophomorixIntrinsicMulti5=[],
            sophomorixMailAlias=False, sophomorixMailList=False,
            sophomorixMembers=[], sophomorixRole='',
            sophomorixSchoolname='default-school', sophomorixSchoolPrefix='---',
            sophomorixStatus='', sophomorixType='adminclass',
        )
        return g

    def test_direct_person_members_are_collected(self, monkeypatch):
        user_dn = 'CN=johndoe,OU=7a,OU=Students,DC=test,DC=lan'
        group = self._make_group([user_dn])

        monkeypatch.setattr(router, 'get', lambda url, **kw: {
            'cn': 'johndoe',
            'objectClass': ['top', 'person', 'user'],
        })

        group.get_all_members()
        assert 'johndoe' in group.all_members
        assert group.membersCount == 1

    def test_empty_member_list_gives_zero_count(self, monkeypatch):
        group = self._make_group([])
        group.get_all_members()
        assert group.membersCount == 0
        assert group.all_members == []
