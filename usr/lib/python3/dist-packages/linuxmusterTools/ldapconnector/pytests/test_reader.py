import pytest
from types import SimpleNamespace
from dataclasses import dataclass, asdict
from unittest.mock import MagicMock

from linuxmusterTools.ldapconnector.ldap_reader import LdapReader


def make_field(type_):
    return SimpleNamespace(type=type_)


@dataclass
class _SimpleModel:
    cn: str
    distinguishedName: str
    name: str


SIMPLE_DN = 'CN=test,OU=default-school,DC=test,DC=lan'


def _raw(cn='test', dn=SIMPLE_DN, name='test'):
    return (dn, {
        'cn': [cn.encode()],
        'distinguishedName': [dn.encode()],
        'name': [name.encode()],
    })


class TestFilterValue:

    def test_str_decodes_bytes(self):
        assert LdapReader._filter_value(make_field(str), [b'hello']) == 'hello'

    def test_str_empty_list_returns_empty_string(self):
        assert LdapReader._filter_value(make_field(str), []) == ''

    def test_str_none_returns_empty_string(self):
        assert LdapReader._filter_value(make_field(str), None) == ''

    def test_list_decodes_all_elements(self):
        assert LdapReader._filter_value(make_field(list), [b'a', b'b']) == ['a', 'b']

    def test_list_empty_returns_empty(self):
        assert LdapReader._filter_value(make_field(list), []) == []

    def test_list_none_returns_empty(self):
        assert LdapReader._filter_value(make_field(list), None) == []

    def test_bool_true_bytes(self):
        assert LdapReader._filter_value(make_field(bool), [b'TRUE']) is True

    def test_bool_false_bytes(self):
        assert LdapReader._filter_value(make_field(bool), [b'FALSE']) is False

    def test_bool_none_returns_false(self):
        assert LdapReader._filter_value(make_field(bool), None) is False

    def test_bool_python_false_returns_false(self):
        assert LdapReader._filter_value(make_field(bool), False) is False

    def test_int_decodes_value(self):
        assert LdapReader._filter_value(make_field(int), [b'42']) == 42

    def test_int_none_returns_zero(self):
        assert LdapReader._filter_value(make_field(int), None) == 0

    def test_int_zero_returns_zero(self):
        assert LdapReader._filter_value(make_field(int), 0) == 0


class TestCreateResultObject:

    def setup_method(self):
        self.reader = LdapReader.__new__(LdapReader)

    def test_returns_dict_by_default(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel)
        assert isinstance(result, dict)
        assert result['cn'] == 'test'

    def test_returns_dataclass_when_as_dict_false(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, as_dict=False)
        assert isinstance(result, _SimpleModel)
        assert result.cn == 'test'

    def test_no_school_filter_accepts_any_dn(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, school='')
        assert result['cn'] == 'test'

    def test_school_filter_matches_dn(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, school='default-school')
        assert result['cn'] == 'test'

    def test_school_filter_rejects_other_school(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, school='other-school')
        assert result == {}

    def test_school_global_bypasses_filter(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, school='global')
        assert result['cn'] == 'test'

    def test_dn_filter_matching_substring(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, dn_filter='default-school')
        assert result['cn'] == 'test'

    def test_dn_filter_non_matching_returns_empty(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, dn_filter='missing')
        assert result == {}

    def test_attributes_filter_restricts_keys(self):
        result = self.reader._create_result_object(_raw(), _SimpleModel, attributes=['cn'])
        assert list(result.keys()) == ['cn']

    def test_none_dn_in_result_returns_empty_dict(self):
        result = self.reader._create_result_object((None, {}), _SimpleModel, as_dict=True)
        assert result == {}

    def test_none_dn_with_as_dict_false_returns_default_object(self):
        result = self.reader._create_result_object((None, {}), _SimpleModel, as_dict=False)
        assert isinstance(result, _SimpleModel)
        assert result.cn == ''
