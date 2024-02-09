import ldap
import logging

from linuxmusterTools.ldapconnector.connector import LdapConnector
from .urls.ldaprouter import router as LMNLdapReader

OBJECT_MAPPING = {
    'user': {'url': '/users/'},
    'device': {'url': '/devices/'},
    'group': {'url': '/groups/'},
    'schoolclass': {'url': '/schoolclasses/'},
    'project': {'url': '/projects/'},
}

class LdapWriter():
    def __init__(self):
        self.lc = LdapConnector()
        self.lr = LMNLdapReader

    def _is_valid_object(self, name, objecttype):
        """
        Check if the object exists in ldap and return his values.

        :param name: cn of the object
        :type name: basestring
        :param objecttype: user, device, etc ... see OBJECT_MAPPING above
        :type objecttype: basestring
        :return: details
        :rtype: dict
        """

        details = self.lr.get(f'{OBJECT_MAPPING[objecttype]["url"]}{name}')

        if not details:
            logging.info(f"The {objecttype} {name} not found in ldap.")
            raise Exception(f"The {objecttype} {name} not found in ldap.")

        return details

    def set(self, name, objecttype, data):
        """
        Set one or more attributes only for a ldap entry.

        :param name: cn
        :type name: basestring
        :param objecttype: user, device, etc ... see OBJECT_MAPPING above
        :type objecttype: basestring
        :param data: Dict of attributes:values to write
        :type data: dict
        """

        details = self._is_valid_object(name, objecttype)

        ldif = []
        for attr, new_val in data.items():
            if attr in details:
                if details[attr]:
                    # Delete attribute first
                    ldif.append((ldap.MOD_DELETE, attr, None))
                ldif.append((ldap.MOD_ADD, attr, [new_val.encode()]))
            elif attr == 'unicodePwd':
                ldif.append((ldap.MOD_REPLACE, attr, f'"{new_val}"'.encode('utf-16-le')))
            else:
                logging.warning(f"Attribute {attr} not found in {details}'s values.")

        self.lc._set(details['dn'], ldif)

ldap_writer = LdapWriter()


