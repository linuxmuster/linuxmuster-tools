import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from .object import LMNObjectWriter


logger = logging.getLogger(__name__)

class LMNUserWriter:

    def __init__(self):
        self.lw = LdapWriter()
        self.lr = router
        self.ow = LMNObjectWriter()

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

    def add_parents(self, name, parents=[]):
        """

        :param name: cn of the student
        :type name: basestring
        :param parents: List of cn of the parents
        :type parents: list
        """

        # Check if the users exist
        student = self.lr.get(f'/users/{name}')

        if student.get('sophomorixRole', None) != 'student':
            logging.info(f'{name} is not a student, can not add parent.')
            return

        parents_dn = []
        for parent in parents:
            details = self.lr.get(f'/users/{parent}')
            # Allowing all roles but student
            if details.get('sophomorixRole', 'student') == 'student':
                logging.info(f'{parent} do not have a valid role to be parent.')
                return
            # At this point, we have a valid role for a parent
            parents_dn.append(details['dn'])

        parentgroup_dn = student['dn'].replace(name, f"{name}-parents")
        for dn in parents_dn:
            self.ow.add_member(parentgroup_dn, dn)



