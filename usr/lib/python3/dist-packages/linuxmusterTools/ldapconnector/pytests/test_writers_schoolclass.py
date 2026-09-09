import ldap
import pytest
from unittest.mock import MagicMock

from linuxmusterTools.ldapconnector.writers.schoolclass import LMNSchoolclass, LMNSchoolclassGroup
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


GROUP_DN = 'CN=7a,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
STUDENT_DN = 'CN=johndoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
TEACHER_DN = 'CN=teacher1,OU=Teachers,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'

SAMPLE_SCHOOLCLASS = {
    'cn': '7a', 'description': '', 'displayName': '7a',
    'distinguishedName': GROUP_DN,
    'mail': ['7a@school.lan'], 'member': [STUDENT_DN, TEACHER_DN], 'memberOf': [],
    'name': '7a', 'objectClass': [], 'proxyAddresses': [],
    'sAMAccountName': '7a', 'sAMAccountType': '',
    'sophomorixAdminClass': '', 'sophomorixAddMailQuota': '---',
    'sophomorixAddQuota': '---',
    'sophomorixCreationDate': '',
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
    'sophomorixMailQuota': '---:---:', 'sophomorixMembers': ['johndoe'],
    'sophomorixQuota': ['default-school:---:---:'],
    'sophomorixRole': '',
    'sophomorixSchoolname': 'default-school', 'sophomorixSchoolPrefix': '---',
    'sophomorixStatus': '', 'sophomorixType': 'adminclass',
    'dn': GROUP_DN, 'all_members': [], 'membersCount': -1,
}

SUBGROUP = dict(SAMPLE_SCHOOLCLASS, cn='7a-students', name='7a-students',
    distinguishedName=GROUP_DN.replace('CN=7a,', 'CN=7a-students,'),
    dn=GROUP_DN.replace('CN=7a,', 'CN=7a-students,'),
    member=[])


def make_schoolclass(monkeypatch, mock_connect):
    def mock_get(url, **kw):
        return dict(SAMPLE_SCHOOLCLASS)
    monkeypatch.setattr(router, 'get', mock_get)
    return LMNSchoolclass('7a'), mock_connect


class TestLMNSchoolclassInit:

    def test_init_loads_data(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        sc = LMNSchoolclass('7a')
        assert sc.data['cn'] == '7a'
        assert sc.cn == '7a'

    def test_init_raises_when_not_found(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {})
        with pytest.raises(Exception, match='was not found in ldap'):
            LMNSchoolclass('nonexistent')

    def test_init_creates_subgroups(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        sc = LMNSchoolclass('7a')
        assert hasattr(sc, 'students_group')
        assert hasattr(sc, 'teachers_group')
        assert hasattr(sc, 'parents_group')


class TestLMNSchoolclassGroupFillMembers:

    def _make_subgroup(self, suffix, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        sc = LMNSchoolclass('7a')
        if suffix == '-students':
            return sc.students_group
        elif suffix == '-teachers':
            return sc.teachers_group
        elif suffix == '-parents':
            return sc.parents_group

    def test_fill_students_filters_ou_students(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: None)
        sc = LMNSchoolclass('7a')

        sc.students_group.fill_members()
        assert mock_connect.modify_s.called
        call_args = mock_connect.modify_s.call_args
        # The member list in ldif should contain the student DN
        ldif = call_args[0][1]
        member_values = [v for op, attr, v in ldif if attr == 'member' and op != 1]
        flat_values = [v for vals in member_values for v in (vals if isinstance(vals, list) else [vals])]
        assert any(b'OU=Students' in v for v in flat_values)

    def test_fill_teachers_filters_ou_teachers(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        sc = LMNSchoolclass('7a')

        sc.teachers_group.fill_members()
        assert mock_connect.modify_s.called
        call_args = mock_connect.modify_s.call_args
        ldif = call_args[0][1]
        member_values = [v for op, attr, v in ldif if attr == 'member' and op != 1]
        flat_values = [v for vals in member_values for v in (vals if isinstance(vals, list) else [vals])]
        assert any(b'OU=Teachers' in v for v in flat_values)

    def test_fill_parents_queries_parents_units(self, monkeypatch, mock_connect):
        parent_dn = 'CN=parent1,OU=Parents,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: [parent_dn])

        sc = LMNSchoolclass('7a')
        sc.parents_group.fill_members()
        assert mock_connect.modify_s.called

    def test_fill_empty_members_deletes_attribute(self, monkeypatch, mock_connect):
        # No parents accounts is a valid state: the attribute must be cleared
        # through delattr(), setattr() would raise a ValueError.
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: None)

        sc = LMNSchoolclass('7a')
        mock_connect.modify_s.reset_mock()
        sc.parents_group.fill_members()

        assert mock_connect.modify_s.called
        ldif = mock_connect.modify_s.call_args[0][1]
        assert ldif == [(ldap.MOD_DELETE, 'member', None)]

    def test_fill_empty_members_without_attribute_does_nothing(self, monkeypatch, mock_connect):
        # Subgroup just auto created: no member attribute in ldap yet, so
        # there is nothing to delete either.
        def mock_get(url, **kw):
            if url.startswith('/units/7a-'):
                return dict(SUBGROUP, member=[])
            return dict(SAMPLE_SCHOOLCLASS)

        monkeypatch.setattr(router, 'get', mock_get)
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: None)

        sc = LMNSchoolclass('7a')
        mock_connect.modify_s.reset_mock()
        sc.parents_group.fill_members()

        assert not mock_connect.modify_s.called

    def test_fill_group_members_survives_empty_subgroup(self, monkeypatch, mock_connect):
        # fill_group_members() must not stop at the first empty subgroup:
        # the students and teachers groups have to be filled anyway.
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: None)

        sc = LMNSchoolclass('7a')
        mock_connect.modify_s.reset_mock()
        sc.fill_group_members()

        assert mock_connect.modify_s.call_count == 3


class TestLMNSchoolclassSubgroupAutoCreate:

    def test_subgroup_auto_created_when_missing(self, monkeypatch, mock_connect):
        call_count = {'add_s': 0}
        def mock_get(url, **kw):
            if '-students' in url or '-teachers' in url or '-parents' in url:
                return {}
            return dict(SAMPLE_SCHOOLCLASS)

        monkeypatch.setattr(router, 'get', mock_get)
        LMNSchoolclass('7a')
        assert mock_connect.add_s.called


class TestLMNSchoolclassAddMember:

    def test_add_member_triggers_fill_group_members(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw:
            'CN=janedoe,OU=7a,OU=Students,OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan'
        )
        sc = LMNSchoolclass('7a')
        initial_modify_calls = mock_connect.modify_s.call_count
        sc.add_member('janedoe')
        # add_member calls _setattr (for main group) + fill_group_members (3 subgroups)
        assert mock_connect.modify_s.call_count > initial_modify_calls

    def test_remove_member_triggers_fill_group_members(self, monkeypatch, mock_connect):
        monkeypatch.setattr(router, 'get', lambda url, **kw: dict(SAMPLE_SCHOOLCLASS))
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: STUDENT_DN)
        sc = LMNSchoolclass('7a')
        initial_modify_calls = mock_connect.modify_s.call_count
        sc.remove_member('johndoe')
        assert mock_connect.modify_s.call_count > initial_modify_calls
