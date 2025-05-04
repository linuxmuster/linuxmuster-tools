import ldap
import logging
from dataclasses import fields

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

    def _addLDIF(self, lmnobject, data={}):
        if not data:
            logger.warning("No data provided, doing nothing.")
            return

        ldif = []
        valid_fields = {field.name:field.type() for field in fields(lmnobject.model) if field.init}

        for attr, new_val in data.items():
            if not new_val:
                continue

            if attr in valid_fields:
                if isinstance(valid_fields[attr], list):
                    if isinstance(new_val, list):
                        for val in new_val:
                            if val:
                                ldif.append((attr, [f"{val}".encode()]))
                    else:
                        ldif.append((attr, [f"{new_val}".encode()]))

                else:
                    # Single-value
                    ldif.append((attr, [f"{new_val}".encode()]))

            elif attr == 'unicodePwd':
                ldif.append(('unicodePwd', f'"{new_val}"'.encode('utf-16-le')))

            else:
                logger.warning(f"Attribute {attr} not found in {lmnobject.data['distinguishedName']}.")

        return ldif

    def _setattr(self, lmnobject, data=None, add=False):
        """
        Set one or more attributes only for a ldap entry.
        data is a dict of attributes/values to set.
        If some attributes are lists, the boolean add permit to decide if the
        new values must be added to the existing value list (add=True) or
        if the list must be completely replaced (add=False, default behaviour).

        :param lmnobject: object to modify (project, student ...)
        :type lmnobject: something like User, Project, etc
        :param data: Dict of attributes:values to write
        :type data: dict
        :param add: Replace a list values with the new values or add the
        new values to the existing ones.
        :type add: bool
        """


        if not data:
            logger.warning("No data provided, doing nothing.")
            return

        ldif = []
        valid_fields = {field.name:field.type() for field in fields(lmnobject.model) if field.init}

        for attr, new_val in data.items():
            if attr in valid_fields:

                if isinstance(valid_fields[attr], list):
                    # Multi-value
                    if not add and lmnobject.data[attr]:
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
                    elif lmnobject.data[attr]:
                        # Delete attribute first
                        ldif.append((ldap.MOD_DELETE, attr, None))

                    ldif.append((ldap.MOD_ADD, attr, [f"{new_val}".encode()]))

            elif attr == 'unicodePwd':
                ldif.append((ldap.MOD_REPLACE, attr, f'"{new_val}"'.encode('utf-16-le')))

            else:
                logger.warning(f"Attribute {attr} not found in {lmnobject.data['distinguishedName']}.")

        if ldif:
            self.lc._set(lmnobject.data['distinguishedName'], ldif)

    def _delattr(self, lmnobject, data=None):
        """
        Delete one or more attributes only for a ldap entry.

        :param lmnobject: object to modify (project, student ...)
        :type lmnobject: something like User, Project, etc
        :param data: Dict of attributes:values to delete.
        Value may be empty if the attribute is not ambiguous
        :type data: dict
        """

        if not data:
            logger.warning("No data provided, doing nothing.")
            return

        ldif = []
        valid_fields = {field.name:field.type() for field in fields(lmnobject.model) if field.init}

        for attr, val in data.items():
            if attr in valid_fields:
                if not val:
                    # Delete the whole attribute
                    ldif.append((ldap.MOD_DELETE, attr, None))
                else:
                    if isinstance(val, str):
                        if val in lmnobject.data[attr]:
                            ldif.append((ldap.MOD_DELETE, attr, val.encode()))
                        else:
                            logger.info(
                                f"Value {val} not found in attribute {attr} from {lmnobject.data['distinguishedName']}.")
                    elif isinstance(val, list):
                        for v in val:
                            if v in lmnobject.data[attr]:
                                ldif.append((ldap.MOD_DELETE, attr, v.encode()))
                            else:
                                logger.info(
                                    f"Value {v} not found in attribute {attr} from {lmnobject.data['distinguishedName']}.")
            else:
                logger.warning(f"Attribute {attr} not found in {lmnobject.data['distinguishedName']}.")

        if ldif:
            self.lc._set(lmnobject.data['distinguishedName'], ldif)

    def _rename(self, old_dn, new_cn):
        """
        Update the CN of an entry, given by its dn.
        """


        self.lc._rename(old_dn, new_cn)

    def _move(self, old_dn, new_ou):
        """
        Move an entry, given by its dn, to a new OU.
        """


        self.lc._move(old_dn, new_ou)

    def _add(self, lmnobject, data={}):
        """
        Create an entry with the given dn.
        Should be mostly used for users or computers.

        :param dn: dn of the object to add
        :type dn: basestring
        """


        ldif = []
        if data:
            ldif = self._addLDIF(lmnobject, data)
        self.lc._add(lmnobject.data['distinguishedName'], ldif)

    def _add_ou(self, dn):
        """
        Create an organisational unit with the given dn.

        :param dn: dn of the object to add
        :type dn: basestring
        """


        # TODO: still necessary ? ldif ?
        self.lc._add_ou(dn)

    def _add_group(self, dn, ldif=[]):
        """
        Create a group with the given dn.

        :param dn: dn of the object to add
        :type dn: basestring
        """


        # TODO: still necessary ? ldif with createLDIF ?
        self.lc._add_group(dn, ldif)

    def _del(self, dn):
        """
        Delete an Ldap object.

        :param dn: dn of the object to delete
        :type dn: basestring
        """


        self.lc._del(dn)


ldap_writer = LdapWriter()


