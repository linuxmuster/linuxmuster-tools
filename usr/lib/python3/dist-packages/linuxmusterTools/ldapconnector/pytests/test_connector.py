import pytest
import ldap
from unittest.mock import MagicMock

from linuxmusterTools.ldapconnector.connector import LdapConnector
import linuxmusterTools.ldapconnector.connector as conn_module

SEARCHDN = 'DC=linuxmuster,DC=lan'
USER_DN = 'CN=johndoe,OU=7a,OU=default-school,DC=linuxmuster,DC=lan'


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    conn.search_s.return_value = []
    return conn


@pytest.fixture
def lc(mock_conn, monkeypatch):
    monkeypatch.setattr(LdapConnector, '_connect', lambda self: (mock_conn, SEARCHDN))
    return LdapConnector(), mock_conn


def make_alternating_connect(conn_a, conn_b):
    calls = [0]
    def connect(self):
        c = conn_a if calls[0] == 0 else conn_b
        calls[0] += 1
        return c, SEARCHDN
    return connect


class TestPool:

    def test_get_conn_creates_connection_on_first_call(self, lc):
        connector, mock_conn = lc
        conn, searchdn = connector._get_conn()
        assert conn is mock_conn
        assert searchdn == SEARCHDN

    def test_get_conn_reuses_connection_on_subsequent_calls(self, lc):
        connector, mock_conn = lc
        conn1, _ = connector._get_conn()
        conn2, _ = connector._get_conn()
        assert conn1 is conn2

    def test_get_conn_calls_connect_only_once(self, mock_conn, monkeypatch):
        call_count = [0]
        def counting_connect(self):
            call_count[0] += 1
            return mock_conn, SEARCHDN
        monkeypatch.setattr(LdapConnector, '_connect', counting_connect)
        connector = LdapConnector()
        for _ in range(3):
            connector._get_conn()
        assert call_count[0] == 1

    def test_reconnect_clears_and_creates_new_connection(self, mock_conn, monkeypatch):
        new_conn = MagicMock()
        monkeypatch.setattr(LdapConnector, '_connect', make_alternating_connect(mock_conn, new_conn))
        connector = LdapConnector()
        conn1, _ = connector._get_conn()
        conn2, _ = connector._reconnect()
        assert conn1 is mock_conn
        assert conn2 is new_conn

    def test_reconnect_clears_cached_conn(self, lc):
        connector, mock_conn = lc
        connector._get_conn()
        assert conn_module.local_thread.conn is mock_conn
        connector._reconnect()
        # After reconnect, a new call to _connect happened
        assert conn_module.local_thread.conn is mock_conn  # same mock returned again


class TestGet:

    def test_get_returns_non_none_results(self, lc):
        connector, mock_conn = lc
        mock_conn.search_s.return_value = [
            (USER_DN, {'cn': [b'johndoe']}),
            (None, {}),
        ]
        results = connector._get('(cn=johndoe)')
        assert len(results) == 1
        assert results[0][0] == USER_DN

    def test_get_returns_empty_list_on_no_such_object(self, lc):
        connector, mock_conn = lc
        mock_conn.search_s.side_effect = ldap.NO_SUCH_OBJECT
        assert connector._get('(cn=x)') == []

    def test_get_reconnects_and_retries_on_ldap_error(self, mock_conn, monkeypatch):
        new_conn = MagicMock()
        new_conn.search_s.return_value = [(USER_DN, {'cn': [b'johndoe']})]
        monkeypatch.setattr(LdapConnector, '_connect', make_alternating_connect(mock_conn, new_conn))
        mock_conn.search_s.side_effect = ldap.LDAPError

        connector = LdapConnector()
        results = connector._get('(cn=johndoe)')
        assert len(results) == 1
        assert new_conn.search_s.called

    def test_get_uses_subdn(self, lc):
        connector, mock_conn = lc
        connector._get('(cn=x)', subdn='OU=Students,')
        call_args = mock_conn.search_s.call_args[0]
        assert call_args[0].startswith('OU=Students,')

    def test_get_passes_scope(self, lc):
        connector, mock_conn = lc
        connector._get('(cn=x)', scope=ldap.SCOPE_ONELEVEL)
        assert mock_conn.search_s.call_args[0][1] == ldap.SCOPE_ONELEVEL


class TestWriteOperations:

    def test_set_calls_modify_s(self, lc):
        connector, mock_conn = lc
        ldif = [(ldap.MOD_REPLACE, 'mail', [b'john@example.com'])]
        connector._set(USER_DN, ldif)
        mock_conn.modify_s.assert_called_once_with(USER_DN, ldif)

    def test_set_reconnects_on_server_down(self, mock_conn, monkeypatch):
        new_conn = MagicMock()
        monkeypatch.setattr(LdapConnector, '_connect', make_alternating_connect(mock_conn, new_conn))
        mock_conn.modify_s.side_effect = ldap.SERVER_DOWN

        connector = LdapConnector()
        connector._set(USER_DN, [])
        assert new_conn.modify_s.called

    def test_add_calls_add_s(self, lc):
        connector, mock_conn = lc
        ldif = [('cn', [b'johndoe'])]
        connector._add(USER_DN, ldif)
        mock_conn.add_s.assert_called_once_with(USER_DN, ldif)

    def test_add_reconnects_on_server_down(self, mock_conn, monkeypatch):
        new_conn = MagicMock()
        monkeypatch.setattr(LdapConnector, '_connect', make_alternating_connect(mock_conn, new_conn))
        mock_conn.add_s.side_effect = ldap.SERVER_DOWN

        connector = LdapConnector()
        connector._add(USER_DN, [])
        assert new_conn.add_s.called

    def test_del_calls_delete_s(self, lc):
        connector, mock_conn = lc
        connector._del(USER_DN)
        mock_conn.delete_s.assert_called_once_with(USER_DN)

    def test_del_reconnects_on_server_down(self, mock_conn, monkeypatch):
        new_conn = MagicMock()
        monkeypatch.setattr(LdapConnector, '_connect', make_alternating_connect(mock_conn, new_conn))
        mock_conn.delete_s.side_effect = ldap.SERVER_DOWN

        connector = LdapConnector()
        connector._del(USER_DN)
        assert new_conn.delete_s.called

    def test_rename_calls_rename_s_with_cn(self, lc):
        connector, mock_conn = lc
        connector._rename(USER_DN, 'newname')
        mock_conn.rename_s.assert_called_once_with(USER_DN, 'CN=newname')

    def test_rename_reconnects_on_server_down(self, mock_conn, monkeypatch):
        new_conn = MagicMock()
        monkeypatch.setattr(LdapConnector, '_connect', make_alternating_connect(mock_conn, new_conn))
        mock_conn.rename_s.side_effect = ldap.SERVER_DOWN

        connector = LdapConnector()
        connector._rename(USER_DN, 'newname')
        assert new_conn.rename_s.called

    def test_move_calls_rename_s_with_new_ou(self, lc):
        connector, mock_conn = lc
        connector._move('CN=johndoe,OU=7a,DC=test', 'OU=8b,DC=test')
        mock_conn.rename_s.assert_called_once_with('CN=johndoe,OU=7a,DC=test', 'CN=johndoe', 'OU=8b,DC=test')

    def test_add_ou_includes_correct_objectclass(self, lc):
        connector, mock_conn = lc
        connector._add_ou('OU=test,DC=test')
        ldif = mock_conn.add_s.call_args[0][1]
        assert ('objectclass', [b'top', b'OrganizationalUnit']) in ldif

    def test_add_group_includes_group_objectclass(self, lc):
        connector, mock_conn = lc
        connector._add_group('CN=test,DC=test', [])
        ldif = mock_conn.add_s.call_args[0][1]
        assert ('objectclass', [b'top', b'group']) in ldif

    def test_add_group_does_not_duplicate_objectclass(self, lc):
        connector, mock_conn = lc
        existing_ldif = [('objectclass', [b'top', b'group'])]
        connector._add_group('CN=test,DC=test', existing_ldif)
        ldif = mock_conn.add_s.call_args[0][1]
        assert ldif.count(('objectclass', [b'top', b'group'])) == 1
