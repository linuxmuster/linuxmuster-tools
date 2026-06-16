import pytest
import ldap
from types import SimpleNamespace
from unittest.mock import MagicMock, call

from linuxmusterTools.ldapconnector.ldap_writer import LdapWriter
from linuxmusterTools.ldapconnector.models import LMNGroupModel


DN = 'CN=7a,OU=SCHOOLS,DC=test,DC=lan'


def make_writer():
    lw = LdapWriter.__new__(LdapWriter)
    lw.lc = MagicMock()
    lw.lr = MagicMock()
    return lw


def make_obj(extra_data=None):
    obj = SimpleNamespace()
    obj.model = LMNGroupModel
    obj.data = {
        'distinguishedName': DN,
        'cn': '',
        'description': '',
        'sophomorixRole': 'student',
        'sophomorixHidden': False,
        'member': ['existing_dn'],
        'memberOf': ['dn_a', 'dn_b'],
        'sophomorixStatus': '',
    }
    if extra_data:
        obj.data.update(extra_data)
    return obj


class TestSetattr:

    def test_replaces_existing_str_attribute(self):
        lw = make_writer()
        obj = make_obj({'sophomorixRole': 'student'})
        lw._setattr(obj, data={'sophomorixRole': 'teacher'})
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_DELETE, 'sophomorixRole', None) in ldif
        assert (ldap.MOD_ADD, 'sophomorixRole', [b'teacher']) in ldif

    def test_adds_str_attribute_when_empty(self):
        lw = make_writer()
        obj = make_obj({'sophomorixRole': ''})
        lw._setattr(obj, data={'sophomorixRole': 'teacher'})
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_DELETE, 'sophomorixRole', None) not in ldif
        assert (ldap.MOD_ADD, 'sophomorixRole', [b'teacher']) in ldif

    def test_replaces_list_when_add_false(self):
        lw = make_writer()
        obj = make_obj({'member': ['existing_dn']})
        lw._setattr(obj, data={'member': ['new_dn']}, add=False)
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_DELETE, 'member', None) in ldif
        assert (ldap.MOD_ADD, 'member', [b'new_dn']) in ldif

    def test_adds_to_list_when_add_true(self):
        lw = make_writer()
        obj = make_obj({'member': ['existing_dn']})
        lw._setattr(obj, data={'member': ['new_dn']}, add=True)
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_DELETE, 'member', None) not in ldif
        assert (ldap.MOD_ADD, 'member', [b'new_dn']) in ldif

    def test_bool_true_encodes_as_uppercase(self):
        lw = make_writer()
        obj = make_obj({'sophomorixHidden': False})
        lw._setattr(obj, data={'sophomorixHidden': True})
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_ADD, 'sophomorixHidden', [b'TRUE']) in ldif

    def test_bool_false_encodes_as_uppercase(self):
        lw = make_writer()
        obj = make_obj({'sophomorixHidden': True})
        lw._setattr(obj, data={'sophomorixHidden': False})
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_ADD, 'sophomorixHidden', [b'FALSE']) in ldif

    def test_unicodepwd_uses_replace_and_utf16(self):
        lw = make_writer()
        obj = make_obj()
        lw._setattr(obj, data={'unicodePwd': 'secret'})
        _, ldif = lw.lc._set.call_args[0]
        assert ldif[0][0] == ldap.MOD_REPLACE
        assert ldif[0][1] == 'unicodePwd'
        assert isinstance(ldif[0][2], bytes)
        assert ldif[0][2] == '"secret"'.encode('utf-16-le')

    def test_unknown_attribute_skipped_and_no_ldap_call(self):
        lw = make_writer()
        obj = make_obj()
        lw._setattr(obj, data={'nonExistentAttr': 'value'})
        lw.lc._set.assert_not_called()

    def test_empty_data_does_not_call_set(self):
        lw = make_writer()
        obj = make_obj()
        lw._setattr(obj, data={})
        lw.lc._set.assert_not_called()

    def test_none_data_does_not_call_set(self):
        lw = make_writer()
        obj = make_obj()
        lw._setattr(obj, data=None)
        lw.lc._set.assert_not_called()


class TestDelattr:

    def test_deletes_whole_attribute_when_value_empty(self):
        lw = make_writer()
        obj = make_obj()
        lw._delattr(obj, data={'sophomorixRole': ''})
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_DELETE, 'sophomorixRole', None) in ldif

    def test_deletes_specific_str_value(self):
        lw = make_writer()
        obj = make_obj({'memberOf': ['dn_a', 'dn_b']})
        lw._delattr(obj, data={'memberOf': 'dn_a'})
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_DELETE, 'memberOf', b'dn_a') in ldif

    def test_skips_str_value_not_in_attribute(self):
        lw = make_writer()
        obj = make_obj({'memberOf': ['dn_a']})
        lw._delattr(obj, data={'memberOf': 'dn_missing'})
        lw.lc._set.assert_not_called()

    def test_deletes_each_value_from_list(self):
        lw = make_writer()
        obj = make_obj({'memberOf': ['dn_a', 'dn_b', 'dn_c']})
        lw._delattr(obj, data={'memberOf': ['dn_a', 'dn_b']})
        _, ldif = lw.lc._set.call_args[0]
        assert (ldap.MOD_DELETE, 'memberOf', b'dn_a') in ldif
        assert (ldap.MOD_DELETE, 'memberOf', b'dn_b') in ldif

    def test_skips_list_values_not_in_attribute(self):
        lw = make_writer()
        obj = make_obj({'memberOf': ['dn_a']})
        lw._delattr(obj, data={'memberOf': ['dn_missing']})
        lw.lc._set.assert_not_called()

    def test_empty_data_does_not_call_set(self):
        lw = make_writer()
        obj = make_obj()
        lw._delattr(obj, data={})
        lw.lc._set.assert_not_called()

    def test_unknown_attribute_does_not_call_set(self):
        lw = make_writer()
        obj = make_obj()
        lw._delattr(obj, data={'nonExistent': ''})
        lw.lc._set.assert_not_called()


class TestAddLDIF:

    def test_str_field_encodes_value(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'sophomorixRole': 'teacher'})
        assert ('sophomorixRole', [b'teacher']) in ldif

    def test_list_field_encodes_each_item(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'member': ['dn1', 'dn2']})
        assert ('member', [b'dn1']) in ldif
        assert ('member', [b'dn2']) in ldif

    def test_bool_true_encodes_as_true(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'sophomorixHidden': True})
        assert ('sophomorixHidden', [b'TRUE']) in ldif

    def test_bool_false_encodes_as_false(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'sophomorixHidden': False})
        assert ('sophomorixHidden', [b'FALSE']) in ldif

    def test_unicodepwd_uses_utf16le(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'unicodePwd': 'secret'})
        assert any(item[0] == 'unicodePwd' for item in ldif)
        pwd_entry = next(item for item in ldif if item[0] == 'unicodePwd')
        assert pwd_entry[1] == '"secret"'.encode('utf-16-le')

    def test_empty_value_is_skipped(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'sophomorixRole': ''})
        assert all(item[0] != 'sophomorixRole' for item in ldif)

    def test_none_value_is_skipped(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'sophomorixRole': None})
        assert all(item[0] != 'sophomorixRole' for item in ldif)

    def test_empty_data_returns_none(self):
        lw = make_writer()
        obj = make_obj()
        result = lw._addLDIF(obj, data={})
        assert result is None

    def test_unknown_attr_is_skipped(self):
        lw = make_writer()
        obj = make_obj()
        ldif = lw._addLDIF(obj, data={'nonExistent': 'value'})
        assert all(item[0] != 'nonExistent' for item in ldif)
