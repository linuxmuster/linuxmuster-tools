import logging
import ldap
import re
import os
from datetime import datetime
from dataclasses import fields, asdict

from ..lmnfile import LMNFile

try:
    from aj.plugins.lmn_common.api import ldap_config as params
    webui_import = True
except ImportError as e:
    webui_import = False

class LdapConnector:

    def __init__(self):
        if webui_import:
            self.params = params
        else:
            self.params = {}

    def _create_result_object(self, result, objectclass, dict=True, school='', attributes=[]):
        """
        Formatting one ldap result object into a dict or a LMN model object.
        """

        if result[0] is not None:
            raw_data = result[1]
            data = {}
            school_node = ""
            if school:
                school_node = f"OU={school},"

            dn = raw_data.get('distinguishedName', [b''])[0].decode()
            if school_node in dn:
                for field in fields(objectclass):
                    if field.init:
                        value = raw_data.get(field.name, field.type())
                        data[field.name] = self._filter_value(field, value)
                if dict:
                    model_dict = asdict(objectclass(**data))
                    if attributes:
                        return {k:v for k,v in model_dict.items() if k in attributes}
                    return model_dict
                return objectclass(**data)

        if dict:
            return {}

        # Creating empty object with default values
        data = {field.name:field.type() for field in fields(objectclass) if field.init }
        return objectclass(**data)

    def get_single(self, objectclass, ldap_filter, scope=ldap.SCOPE_SUBTREE, subdn='', attributes=[], **kwargs):
        """
        Handle a single result from a ldap request (with required ldap filter)
        and convert it in the given object class.

        :param objectclass: dataclass like LMNUser
        :type objectclass:
        :param ldap_filter: A valid ldap filter
        :type ldap_filter: basestring
        :param dict: if True, returns a dict, else an object
        :type dict: bool
        :param school: school to search
        :typee school: str
        :param attributes: list of attributes to return
        :typee attributes: list
        """

        results = self._get(ldap_filter, scope=scope, subdn=subdn, attributes=attributes)

        if len(results) == 0:
            return self._create_result_object([None], objectclass, attributes=attributes, **kwargs)

        to_handle = results[0]

        if len(results) > 1:
            # Only taking the first entry so warn the user
            logging.warning("Multiple entries found in LDAP, but only giving the first one as expected.")

        return self._create_result_object(to_handle, objectclass, attributes=attributes, **kwargs)

    def get_collection(self, objectclass, ldap_filter, scope=ldap.SCOPE_SUBTREE, subdn='', sortkey=None, attributes=[], **kwargs):
        """
        Handle multiples results from a ldap request (with required ldap filter)
        and convert it in a list of given object class.

        :param objectclass: dataclass like LMNUser
        :type objectclass:
        :param ldap_filter: A valid ldap filter
        :type ldap_filter: basestring
        :param dict: if True, returns a list of dict, else a list of objects
        :type dict: bool
        :param sortkey: if given, sorts the list with the given attribute
        :type sortkey: basestring
        :param school: school to search
        :typee school: str
        :param attributes: list of attributes to return
        :typee attributes: list
        """

        def _check_schoolclass_number(s):
            if not isinstance(s, str):
                return s

            n = re.findall(r'\d+', s)
            if n:
                return int(n[0])
            else:
                return 10000000  # just a big number to come after all schoolclasses

        results = self._get(ldap_filter, scope=scope, subdn=subdn, attributes=attributes)
        response = []
        for result in results:
            formatted_obj = self._create_result_object(result, objectclass, attributes=attributes, **kwargs)
            
            if formatted_obj:
                # Avoid empty dicts
                response.append(self._create_result_object(result, objectclass, attributes=attributes, **kwargs))
        if sortkey is not None:
            if dict:
                return sorted(response, key=lambda d: _check_schoolclass_number(d.get(sortkey, None)))
            else:
                return sorted(response, key=lambda d: _check_schoolclass_number(getattr(d, sortkey)))
        return response

    @staticmethod
    def _filter_value(field, value):
        """
        Middleware to decode values and convert it in an usable format (mostly
        compatible with json). Parameter field is given in order to find out the
        type of object.
        """

        # TODO : more exception catch on values
        if field.type.__name__ == 'str':
            # Something like [b'']
            if value is None:
                return ''
            return value[0].decode() if value else ''

        if field.type.__name__ == 'list':
            # Something like [b'a', b'c']
            if value is None:
                return []
            return [v.decode() for v in value] if value else []

        if field.type.__name__ == 'bool':
            # Something like [b'FALSE']
            if value is None or value == False:
                return False
            return value[0].capitalize() == b'True'

        # if field.type.__name__ == 'datetime':
            # Something like [b'20210520111726.0Z']
            # return datetime.strptime(value[0].decode(), '%Y%m%d%H%M%S.%fZ')

        if field.type.__name__ == 'int':
            # Something like [b'20']
            if value is None or value == 0:
                return 0
            return int(value[0].decode())

        if value is None:
            return None

    def _get(self, ldap_filter, scope=ldap.SCOPE_SUBTREE, subdn='', attributes=['*']):
        """
        Connect to ldap and perform the request.

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
                    self.params = config.data['linuxmuster']['ldap']
                with open('/etc/linuxmuster/.secret/administrator', 'r') as admpwd:
                    bindpwd = admpwd.read().strip()
                binddn = f"CN=Administrator,CN=Users,{self.params['searchdn']}"
            else:
                # Importing lmntools from the Webui will resulting into using the same binddn as the one configured
                # in the config.yml from the Webui
                binddn = self.params['binddn']
                bindpwd = self.params['bindpw']

            l.bind_s(binddn, bindpwd)

        attrlist = attributes[:]
        # Not a proper way to add DN
        if attributes != ['*']:
            attrlist.append('distinguishedName')

        if not attributes:
            attrlist = ['*']

        searchdn = f"{subdn}{self.params['searchdn']}"
        response = l.search_s(searchdn,scope, ldap_filter, attrlist=attrlist)

        # Filter non-interesting values
        results = []
        for result in response:
            if result[0] is not None:
                results.append(result)
        
        l.unbind()

        # Removing sensitive data
        if not webui_import:
            self.params = {}
            binddn, bindpwd = '', ''

        return results

    def _set(self, dn, ldif):
        # Only allow to modify on the server
        l = ldap.initialize("ldap://localhost:389/")
        # l.set_option(ldap.OPT_REFERRALS, 0)
        # l.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
        # l.protocol_version = ldap.VERSION3
        if not webui_import:
            with LMNFile('/etc/linuxmuster/webui/config.yml','r') as config:
                self.params = config.data['linuxmuster']['ldap']
            with open('/etc/linuxmuster/.secret/administrator', 'r') as admpwd:
                passwd = admpwd.read().strip()
        l.simple_bind_s(f"CN=Administrator,CN=Users,{self.params['searchdn']}", passwd)

        l.modify_s(dn, ldif)
        l.unbind_s()



