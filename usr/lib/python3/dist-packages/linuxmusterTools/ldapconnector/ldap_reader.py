import logging
import re
import ldap
from dataclasses import fields, asdict

from .connector import LdapConnector
from ..lmnconfig import CustomFieldsConfig


class LdapReader:

    def __init__(self):
        self.lc = LdapConnector()

    def _create_result_object(self, result, objectclass, dict=True, school='', attributes=[], dn_filter='', custom_config={}):
        """
        Formatting one ldap result object into a dict or a LMN model object.
        """

        if result[0] is not None:
            raw_data = result[1]
            data = {}
            school_node = ""

            # Filter per school in multischool environment, but not for
            # global-admins
            if school and school != 'global':
                school_node = f"OU={school},"

            dn = raw_data.get('distinguishedName', [b''])[0].decode()
            if school_node in dn and dn_filter in dn:
                for field in fields(objectclass):
                    if field.init:
                        value = raw_data.get(field.name, field.type())
                        data[field.name] = self._filter_value(field, value)
                if dict:
                    if objectclass.__name__ == 'LMNUser':
                        model_dict = asdict(objectclass(**data, custom_fields_config=custom_config))
                    else:
                        model_dict = asdict(objectclass(**data))

                    if attributes:
                        return {k:v for k,v in model_dict.items() if k in attributes}
                    return model_dict

                if objectclass.__name__ == 'LMNUser':
                        return objectclass(**data, custom_fields_config=custom_config)
                else:
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

        results = self.lc._get(ldap_filter, scope=scope, subdn=subdn)

        custom_fields_config = CustomFieldsConfig().config

        if len(results) == 0:
            return self._create_result_object([None], objectclass, attributes=attributes, custom_config= custom_fields_config, **kwargs)

        to_handle = results[0]

        if len(results) > 1:
            # Only taking the first entry so warn the user
            logging.warning("Multiple entries found in LDAP, but only giving the first one as expected.")

        return self._create_result_object(to_handle, objectclass, attributes=attributes, custom_config= custom_fields_config, **kwargs)

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

        results = self.lc._get(ldap_filter, scope=scope, subdn=subdn)
        response = []

        # TODO: ugly code, find a better way to handle specific parameters
        custom_fields_config = CustomFieldsConfig().config

        for result in results:
            formatted_obj = self._create_result_object(result, objectclass, attributes=attributes, custom_config= custom_fields_config, **kwargs)

            if formatted_obj:
                # Avoid empty dicts
                response.append(formatted_obj)
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

