import ldap
import logging

from linuxmusterTools.ldapconnector.connector import LdapConnector
from .urls.ldaprouter import router as LMNLdapReader


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
            logging.warning("No data provided, doing nothing.")
            return

        ldif = []
        for attr, new_val in data.items():
            if attr in obj_details:

                if isinstance(obj_details[attr], list):
                    # Multi-value
                    if not add:
                        # Delete attribute first
                        ldif.append((ldap.MOD_DELETE, attr, None))

                    if isinstance(new_val, list):
                        for val in new_val:
                            ldif.append((ldap.MOD_ADD, attr, [f"{val}".encode()]))
                    else:
                        ldif.append((ldap.MOD_ADD, attr, [f"{new_val}".encode()]))

                else:
                    # Single-value
                    if obj_details[attr] not in [None, ""]:
                        # Delete attribute first
                        ldif.append((ldap.MOD_DELETE, attr, None))

                    ldif.append((ldap.MOD_ADD, attr, [f"{new_val}".encode()]))

            elif attr == 'unicodePwd':
                ldif.append((ldap.MOD_REPLACE, attr, f'"{new_val}"'.encode('utf-16-le')))

            else:
                logging.warning(f"Attribute {attr} not found in {obj_details}'s values.")

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
            logging.warning("No data provided, doing nothing.")
            return

        ldif = []
        for attr, val in data.items():
            if attr in obj_details:
                ldif.append((ldap.MOD_DELETE, attr, None))
            else:
                logging.warning(f"Attribute {attr} not found in {obj_details}'s values.")
        self.lc._set(obj_details['distinguishedName'], ldif)

    def setattr_user(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/users/{name}')

        if not details:
            logging.info(f"The user {name} was not found in ldap.")
            raise Exception(f"The user {name} was not found in ldap.")

        self._setattr(details, **kwargs)

    def setattr_device(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/devices/{name}')

        if not details:
            logging.info(f"The device {name} was not found in ldap.")
            raise Exception(f"The device {name} was not found in ldap.")

        self._setattr(details, **kwargs)

    def setattr_group(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/groups/{name}')

        if not details:
            logging.info(f"The group {name} was not found in ldap.")
            raise Exception(f"The group {name} was not found in ldap.")

        self._setattr(details, **kwargs)

    def setattr_managementgroup(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/managementgroups/{name}')

        if not details:
            logging.info(f"The managementgroup {name} was not found in ldap.")
            raise Exception(f"The managementgroup {name} was not found in ldap.")

        self._setattr(details, **kwargs)

    def setattr_schoolclass(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/schoolclasses/{name}')

        if not details:
            logging.info(f"The schoolclass {name} was not found in ldap.")
            raise Exception(f"The schoolclass {name} was not found in ldap.")

        self._setattr(details, **kwargs)

    def setattr_printer(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/printers/{name}')

        if not details:
            logging.info(f"The printer {name} was not found in ldap.")
            raise Exception(f"The printer {name} was not found in ldap.")

        self._setattr(details, **kwargs)

    def setattr_project(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/projects/{name}')

        if not details:
            logging.info(f"The project {name} was not found in ldap.")
            raise Exception(f"The project {name} was not found in ldap.")

        self._setattr(details, **kwargs)

    def delattr_user(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/users/{name}')

        if not details:
            logging.info(f"The user {name} was not found in ldap.")
            raise Exception(f"The user {name} was not found in ldap.")

        self._delattr(details, **kwargs)

    def delattr_device(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/devices/{name}')

        if not details:
            logging.info(f"The device {name} was not found in ldap.")
            raise Exception(f"The device {name} was not found in ldap.")

        self._delattr(details, **kwargs)

    def delattr_group(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/groups/{name}')

        if not details:
            logging.info(f"The group {name} was not found in ldap.")
            raise Exception(f"The group {name} was not found in ldap.")

        self._delattr(details, **kwargs)

    def delattr_managementgroup(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/managementgroups/{name}')

        if not details:
            logging.info(f"The managementgroup {name} was not found in ldap.")
            raise Exception(f"The managementgroup {name} was not found in ldap.")

        self._delattr(details, **kwargs)

    def delattr_schoolclass(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/schoolclasses/{name}')

        if not details:
            logging.info(f"The schoolclass {name} was not found in ldap.")
            raise Exception(f"The schoolclass {name} was not found in ldap.")

        self._delattr(details, **kwargs)

    def delattr_printer(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/printers/{name}')

        if not details:
            logging.info(f"The printer {name} was not found in ldap.")
            raise Exception(f"The printer {name} was not found in ldap.")

        self._delattr(details, **kwargs)

    def delattr_project(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/projects/{name}')

        if not details:
            logging.info(f"The project {name} was not found in ldap.")
            raise Exception(f"The project {name} was not found in ldap.")

        self._delattr(details, **kwargs)


ldap_writer = LdapWriter()


