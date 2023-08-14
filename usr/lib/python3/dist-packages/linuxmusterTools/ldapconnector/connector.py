import logging

import ldap
from datetime import datetime
from dataclasses import fields, asdict

from .models import *
from ..lmnfile import LMNFile


class LdapConnector:

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
                        value = raw_data.get(field.name, None)
                        data[field.name] = self._filter_value(field, value)
                if dict:
                    model_dict = asdict(objectclass(**data))
                    if attributes:
                        return {k:v for k,v in model_dict.items() if k in attributes}
                    return model_dict
                return objectclass(**data)
        return {}

    def get_single(self, objectclass, ldap_filter, scope=ldap.SCOPE_SUBTREE, subdn='', **kwargs):
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

        results = self._get(ldap_filter, scope=scope, subdn=subdn)
        if len(results) > 1:
            # Only taking the first entry so warn the user
            logging.warning("Multiple entries found in LDAP, but only giving the first one as expected.")
        elif len(results) == 0:
            return {}
        else:
            return self._create_result_object(results[0], objectclass, **kwargs)

    def get_collection(self, objectclass, ldap_filter, scope=ldap.SCOPE_SUBTREE, subdn='', sortkey=None, **kwargs):
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

        results = self._get(ldap_filter, scope=scope, subdn=subdn)
        response = []
        for result in results:
            formatted_obj = self._create_result_object(result, objectclass, **kwargs)
            
            if formatted_obj:
                # Avoid empty dicts
                response.append(self._create_result_object(result, objectclass, **kwargs))
        if sortkey is not None:
            if dict:
                return sorted(response, key=lambda d: d.get(sortkey, None))
            else:
                return sorted(response, key=lambda d: getattr(d, sortkey))
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
            return value[0].decode() if value is not None else ''

        if field.type.__name__ == 'list':
            # Something like [b'a', b'c']
            if value is None:
                return []
            return [v.decode() for v in value] if value is not None else []

        if field.type.__name__ == 'bool':
            # Something like [b'FALSE']
            if value is None:
                return False
            return value[0].capitalize() == b'True'

        # if field.type.__name__ == 'datetime':
            # Something like [b'20210520111726.0Z']
            # return datetime.strptime(value[0].decode(), '%Y%m%d%H%M%S.%fZ')

        if field.type.__name__ == 'int':
            # Something like [b'20']
            if value is None:
                return 0
            return int(value[0].decode())

        if field.type.__name__ == 'List':
            if value is None:
                return []
            # Creepy test
            if 'LMNSession' in str(field.type.__args__[0]):
                result = []
                for v in value:
                    data = v.decode().split(';')
                    members = data[2].split(',') if data[2] else []
                    membersCount = len(members)
                    result.append(LMNSession(data[0], data[1], members, membersCount))
                return result

        if value is None:
            return None

    def _get(self, ldap_filter, scope=ldap.SCOPE_SUBTREE, subdn=''):
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

        l = ldap.initialize("ldap://localhost:389/")
        l.set_option(ldap.OPT_REFERRALS, 0)
        l.protocol_version = ldap.VERSION3

        with LMNFile('/etc/linuxmuster/webui/config.yml', 'r') as config:
            params = config.data['linuxmuster']['ldap']

        searchdn = f"{subdn}{params['searchdn']}"

        l.bind(params['binddn'], params['bindpw'])
        response = l.search_s(searchdn,scope, ldap_filter, attrlist=['*'])

        # Filter non-interesting values
        results = []
        for result in response:
            if result[0] is not None:
                results.append(result)
        
        l.unbind()

        # Removing sensitive data
        params = {}

        return results

