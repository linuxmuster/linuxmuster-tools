import logging
import ldap
import os

from ..lmnfile import LMNFile

try:
    from aj.plugins.lmn_common.api import ldap_config as params
    webui_import = True
except ImportError as e:
    webui_import = False


class LdapConnector:

    def _connect(self, webui=False):
        """
        Choose the right credentials, depending if the this module is imported in linuxmuster-webui7 or used directly on
        the server, and the perform a connection to the ldap server.

        :param webui: True only if using the _get method from the webui (no changes possible from the webui)
        :type webui: bool
        :return: LDAP object with connection data
        :rtype: LDAPObject
        """


        ## AUTH via GSSAPI for linuxmuster-client7, actually not used
        # if not os.path.isfile('/etc/linuxmuster/webui/config.yml'):
        #     # Using it from linuxclient
        #     # Trying to auth via GSSAPI
        #     try:
        #         from linuxmusterLinuxclient7 import config
        #     except ModuleNotFoundError:
        #         raise Exception('Ldap config missing, could not connect to LDAP server.')
        #
        #     rc, networkConfig = config.network()
        #
        #     if not rc:
        #         return []
        #
        #     serverHostname = networkConfig["serverHostname"]
        #     l = ldap.initialize(f"ldap://{serverHostname}:389/")
        #     l.set_option(ldap.OPT_REFERRALS, 0)
        #     l.protocol_version = ldap.VERSION3
        #     sasl_auth = ldap.sasl.sasl({} ,'GSSAPI')
        #     l.sasl_interactive_bind_s("", sasl_auth)

        # On the server, accessing directly to bind user credentials
        conn = ldap.initialize("ldap://localhost:389/")
        conn.set_option(ldap.OPT_REFERRALS, 0)
        conn.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
        conn.protocol_version = ldap.VERSION3

        if not webui_import:
            # Using Administrator password to be able to write data in LDAP
            with LMNFile('/etc/linuxmuster/webui/config.yml', 'r') as config:
                ldap_params = config.data['linuxmuster']['ldap']
            with open('/etc/linuxmuster/.secret/administrator', 'r') as admpwd:
                bindpwd = admpwd.read().strip()

            binddn = f"CN=Administrator,CN=Users,{ldap_params['searchdn']}"
            searchdn = ldap_params['searchdn']

        elif webui:
            # Importing lmntools from the Webui will resulting into using the same binddn as the one configured
            # in the config.yml from the Webui
            try:
                binddn = params['binddn']
                bindpwd = params['bindpw']
                searchdn = params['searchdn']
            except KeyError:
                logging.error('LDAP credentials not found, is linuxmuster installed and configured ?')
                raise Exception('LDAP credentials not found, is linuxmuster installed and configured ?')

        try:
            conn.bind_s(binddn, bindpwd)

            # Removing sensitive data
            binddn, bindpwd = '', ''
        except ldap.INVALID_CREDENTIALS as e:
            logging.error(str(e))
            raise Exception(f'Invalid credentials: {str(e)}')
        except ldap.SERVER_DOWN as e:
            logging.error(str(e))
            raise Exception(f'Ldap server down: {str(e)}')
        except ldap.LDAPError as e:
            logging.error(e['desc'])
            raise Exception(f"Other ldap error: {e['desc']}")

        return conn, searchdn

    def _get(self, ldap_filter, scope=ldap.SCOPE_SUBTREE, subdn=''):
        """
        Connect to ldap and perform a search.

        :param ldap_filter: Valid ldap filter
        :type ldap_filter: basestring
        :param scope: subtree search or one level
        :type scope: str
        :param searchdn: special searchdn
        :type searchdn: str
        :return: Raw result of the request
        :rtype: dict
        """

        conn, _searchdn = self._connect(webui=True)

        searchdn = f"{subdn}{_searchdn}"

        try:
            response = conn.search_s(searchdn, scope, ldap_filter)
        except ldap.NO_SUCH_OBJECT:
            # Searchdn is maybe wrong, returning empty response
            logging.warning(f"Searchdn {searchdn} is maybe wrong")
            return []

        # Filter non-interesting values
        results = []
        for result in response:
            if result[0] is not None:
                results.append(result)
        
        conn.unbind()

        return results

    def _set(self, dn, ldif):
        """
        Connect to ldap and apply a ldif on the given dn.

        :param dn: dn of the object to modify
        :type dn: basestring
        :param ldif: Valid ldif (list of tuples, one tuple per operation)
        :type ldif: list
        """


        conn, _ = self._connect()
        conn.modify_s(dn, ldif)
        conn.unbind_s()

    def _add(self, dn, ldif):
        """
        Connect to ldap and insert an object with the given dn and ldif attributes.

        :param dn: dn of the object to modify
        :type dn: basestring
        :param ldif: Valid ldif (list of tuples, one tuple per operation)
        :type ldif: list
        """


        conn, _ = self._connect()
        conn.add_s(dn, ldif)
        conn.unbind_s()

    def _add_ou(self, dn):
        """
        Connect to ldap and insert an organisational unit with the given dn.

        :param dn: dn of the object to modify
        :type dn: basestring
        """


        self._add(dn, [('objectclass', [b'top', b'OrganizationalUnit'])])

    def _del(self, dn):
        """
        Connect to ldap and delete the object with the given dn.

        :param dn: dn of the object to modify
        :type dn: basestring
        """


        conn, _ = self._connect()
        conn.delete_s(dn)
        conn.unbind_s()