import ldap
import logging

from linuxmusterTools.ldapconnector.connector import LdapConnector
from .urls.ldaprouter import router as LMNLdapReader


logger = logging.getLogger(__name__)

OBJECT_MAPPING = {
    'user': {'url': '/users/'},
    'device': {'url': '/devices/'},
    'group': {'url': '/groups/'},
    'managementgroup': {'url': '/managementgroups/'},
    'schoolclass': {'url': '/schoolclasses/'},
    'project': {'url': '/projects/'},
    'printer': {'url': '/printers/'},
}

class LdapWriter:

    def __init__(self):
        self.lc = LdapConnector()
        self.lr = LMNLdapReader

    def _setattr(self, obj_details, data=None, add=False):
        """
        Set one or more attributes only for a ldap entry.

        :param obj_details: object to modify (project, ...)
        :type obj_details: dict
        :param data: Dict of attributes:values to write
        :type data: dict
        :type add: bool
        :param add: Define if the attribute should be added, even if the
        attribute is already present
        """


        if not data:
            logger.warning("No data provided, doing nothing.")
            return

        ldif = []
        for attr, new_val in data.items():
            if attr in obj_details:

                if isinstance(obj_details[attr], list):
                    # Multi-value
                    if not add and obj_details[attr]:
                        # Delete attribute first
                        ldif.append((ldap.MOD_DELETE, attr, None))

                    if isinstance(new_val, list):
                        for val in new_val:
                            ldif.append((ldap.MOD_ADD, attr, [f"{val}".encode()]))
                    else:
                        ldif.append((ldap.MOD_ADD, attr, [f"{new_val}".encode()]))

                else:
                    if attr == 'thumbnailPhoto' and not new_val:
                        # Special case for binary attribute
                        # Could be better handled
                        ldif.append((ldap.MOD_DELETE, attr, None))
                        continue

                    # Single-value
                    elif obj_details[attr]:
                        # Delete attribute first
                        ldif.append((ldap.MOD_DELETE, attr, None))

                    ldif.append((ldap.MOD_ADD, attr, [f"{new_val}".encode()]))

            elif attr == 'unicodePwd':
                ldif.append((ldap.MOD_REPLACE, attr, f'"{new_val}"'.encode('utf-16-le')))

            else:
                logger.warning(f"Attribute {attr} not found in {obj_details['distinguishedName']}.")

        if ldif:
            self.lc._set(obj_details['distinguishedName'], ldif)

    def _delattr(self, obj_details, data=None):
        """
        Delete one or more attributes only for a ldap entry.

        :param name: cn
        :type name: basestring
        :param objecttype: user, device, etc ... see OBJECT_MAPPING above
        :type objecttype: basestring
        :param data: Dict of attributes:values to delete.
        Value may be empty if the attribute is not ambiguous
        :type data: dict
        """

        if not data:
            logger.warning("No data provided, doing nothing.")
            return

        ldif = []
        for attr, val in data.items():
            if attr in obj_details:
                if not val:
                    # Delete the whole attribute
                    ldif.append((ldap.MOD_DELETE, attr, None))
                else:
                    if isinstance(val, str):
                        if val in obj_details[attr]:
                            ldif.append((ldap.MOD_DELETE, attr, val.encode()))
                        else:
                            logger.info(
                                f"Value {val} not found in attribute {attr} from {obj_details['distinguishedName']}.")
                    elif isinstance(val, list):
                        for v in val:
                            if v in obj_details[attr]:
                                ldif.append((ldap.MOD_DELETE, attr, v.encode()))
                            else:
                                logger.info(
                                    f"Value {v} not found in attribute {attr} from {obj_details['distinguishedName']}.")
            else:
                logger.warning(f"Attribute {attr} not found in {obj_details['distinguishedName']}.")

        if ldif:
            self.lc._set(obj_details['distinguishedName'], ldif)

    def _rename(self, old_dn, new_cn):
        """

        :param old_dn:
        :type old_dn:
        :param new_cn:
        :type new_cn:
        :return:
        :rtype:
        """

        self.lc._rename(old_dn, new_cn)

    def _move(self, old_dn, new_ou):
        """

        :param old_dn:
        :type old_dn:
        :param new_dn:
        :type new_dn:
        :return:
        :rtype:
        """

        self.lc._move(old_dn, new_ou)

    def _add_ou(self, dn):
        """
        Create an organisational unit with the given dn.

        :param dn: dn of the object to modify
        :type dn: basestring
        """


        self.lc._add_ou(dn)

    def _add_group(self, dn, ldif=[]):
        """
        Create a group with the given dn.

        :param dn: dn of the object to modify
        :type dn: basestring
        """

        self.lc._add_group(dn, ldif)

    def _del(self, dn):
        """
        Delete an Ldap object.

        :param dn: dn of the object to delete
        :type dn: basestring
        """


        self.lc._del(dn)


ldap_writer = LdapWriter()


