import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router


logger = logging.getLogger(__name__)

class LMNUserWriter:

    def __init__(self):
        self.lw = LdapWriter()
        self.lr = router

    def setattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/users/{name}')

        if not details:
            logger.info(f"The user {name} was not found in ldap.")
            raise Exception(f"The user {name} was not found in ldap.")

        self.lw._setattr(details, **kwargs)

    def delattr(self, name, **kwargs):
        """
        Middleware to check if the object exists.

        :param name: cn of the object
        :type name: basestring
        """

        details = self.lr.get(f'/users/{name}')

        if not details:
            logger.info(f"The user {name} was not found in ldap.")
            raise Exception(f"The user {name} was not found in ldap.")

        self.lw._delattr(details, **kwargs)

    def add_parent_group(self, name, **kwargs):
        """
        Each student should have an associated parent group, like STUDENT-parent
        in which the parents are members.

        :param name: cn of the student
        :type name: basestring
        """


        details = self.lr.get(f'/users/{name}')

        if details.get('sophomorixRole', None) != 'student':
            logging.info(f'{name} is not a student, no need to check the parent group.')
            return

        parentgroup_dn = details['dn'].replace(name, f"{name}-parents")
        if not self.lr.get(f'/dn/{parentgroup_dn}'):
            self.lw._add_group(parentgroup_dn)
            logging.info(f"Group {parentgroup_dn} added successfully !")
            return

        logging.info(f"Group {parentgroup_dn} already exists !")


