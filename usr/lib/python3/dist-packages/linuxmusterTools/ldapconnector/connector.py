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

        if not os.path.isfile('/etc/linuxmuster/webui/config.yml'):
            # Using it from linuxclient
            # Trying to auth via GSSAPI
            try:
                from linuxmusterLinuxclient7 import config
            except ModuleNotFoundError:
                raise Exception('Ldap config missing, could not connect to LDAP server.')

            rc, networkConfig = config.network()

            if not rc:
                return []

            serverHostname = networkConfig["serverHostname"]
            l = ldap.initialize(f"ldap://{serverHostname}:389/")
            l.set_option(ldap.OPT_REFERRALS, 0)
            l.protocol_version = ldap.VERSION3
            sasl_auth = ldap.sasl.sasl({} ,'GSSAPI')
            l.sasl_interactive_bind_s("", sasl_auth)
        else:
            # On the server, accessing directly to bind user credentials
            l = ldap.initialize("ldap://localhost:389/")
            l.set_option(ldap.OPT_REFERRALS, 0)
            l.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
            l.protocol_version = ldap.VERSION3
            if not webui_import:
                # Using Administrator password to be able to write data in LDAP
                with LMNFile('/etc/linuxmuster/webui/config.yml','r') as config:
                    ldap_params = config.data['linuxmuster']['ldap']
                with open('/etc/linuxmuster/.secret/administrator', 'r') as admpwd:
                    bindpwd = admpwd.read().strip()

                binddn = f"CN=Administrator,CN=Users,{ldap_params['searchdn']}"
                searchdn = f"{subdn}{ldap_params['searchdn']}"
            else:
                # Importing lmntools from the Webui will resulting into using the same binddn as the one configured
                # in the config.yml from the Webui
                try:
                    binddn = params['binddn']
                    bindpwd = params['bindpw']
                    searchdn = f"{subdn}{params['searchdn']}"
                except KeyError:
                    logging.warning(f'LDAP credentials not found, is linuxmuster installed and configured ?')
                    return []

            try:
                l.bind_s(binddn, bindpwd)
            except ldap.SERVER_DOWN as e:
                logging.error(str(e))
                return []

        try:
            response = l.search_s(searchdn, scope, ldap_filter)
        except ldap.NO_SUCH_OBJECT:
            # Searchdn is maybe wrong, returning empty response
            logging.warning(f"Searchdn {searchdn} is maybe wrong")
            return []

        # Filter non-interesting values
        results = []
        for result in response:
            if result[0] is not None:
                results.append(result)
        
        l.unbind()

        # Removing sensitive data
        binddn, bindpwd, searchdn = '', '', ''

        return results

    def _set(self, dn, ldif):
        """
        Connect to ldap and apply a ldif on the given dn.

        :param dn: dn of the object to modify
        :type dn: basestring
        :param ldif: Valid ldif (list of tuples, one tuple per operation)
        :type ldif: list
        """


        # Only allow to modify on the server
        l = ldap.initialize("ldap://localhost:389/")
        l.set_option(ldap.OPT_REFERRALS, 0)
        l.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
        l.protocol_version = ldap.VERSION3
        if not webui_import:
            with LMNFile('/etc/linuxmuster/webui/config.yml','r') as config:
                params = config.data['linuxmuster']['ldap']
            with open('/etc/linuxmuster/.secret/administrator', 'r') as admpwd:
                passwd = admpwd.read().strip()

        l.simple_bind_s(f"CN=Administrator,CN=Users,{params['searchdn']}", passwd)

        l.modify_s(dn, ldif)
        l.unbind_s()

        # Removing sensitive data
        params = {}
        passwd = ''

    def _add_ou(self, dn):


        # Only allow to modify on the server
        l = ldap.initialize("ldap://localhost:389/")
        l.set_option(ldap.OPT_REFERRALS, 0)
        l.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
        l.protocol_version = ldap.VERSION3
        if not webui_import:
            with LMNFile('/etc/linuxmuster/webui/config.yml','r') as config:
                params = config.data['linuxmuster']['ldap']
            with open('/etc/linuxmuster/.secret/administrator', 'r') as admpwd:
                passwd = admpwd.read().strip()

        l.simple_bind_s(f"CN=Administrator,CN=Users,{params['searchdn']}", passwd)

        l.add_s(dn, [('objectclass', [b'top', b'OrganizationalUnit'])])
        l.unbind_s()

        # Removing sensitive data
        params = {}
        passwd = ''
