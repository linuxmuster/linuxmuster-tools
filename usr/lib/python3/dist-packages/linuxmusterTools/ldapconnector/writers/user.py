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

    def get_parent_group(self, name, **kwargs):
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
        return self.lr.get(f'/dn/{parentgroup_dn}')

    def move_parent_group(self, name, old_group, new_group, **kwargs):
        """
        Move the parent group STUDENT-parent to a new group (like from schoolclass 5a
        to schoolclass 6a).

        :param name: cn of the student
        :type name: basestring
        :param old_group: old schoolclass of the student
        :type old_group: basestring
        :param new_group: new schoolclass of the student
        :type new_group: basestring
        """


        details = self.lr.get(f'/users/{name}')

        if details.get('sophomorixRole', None) != 'student':
            logging.info(f'{name} is not a student, no need to check the parent group.')
            return

        parentgroup_dn = details['dn'].replace(name, f"{name}-parents")
        newparentgroup_dn = parentgroup_dn.replace(f"OU={old_group}", f"OU={new_group}")
        newparentgroup_ou = ','.join(newparentgroup_dn.split(',')[1:])
        if not self.lr.get(f'/dn/{parentgroup_dn}'):
            self.lw._add_group(newparentgroup_dn)
            logging.info(f"Group {newparentgroup_dn} added successfully !")
            return
        else:
            self.lw._move(parentgroup_dn, newparentgroup_ou)
            logging.info(f"Group {newparentgroup_dn} added successfully !")
            return

    def rename_parent_group(self, old_name, new_name, **kwargs):
        """
        Move the parent group OLDNAME-parent to a NEWNAME-parents in case of
        change of the student sAMAccountName. Wenn this method is called, I assume
        that the current sAMAccountName is already new_name.

        :param old_name: old cn of the student
        :type old_name: basestring
        :param new_name: new cn of the student
        :type new_name: basestring
        """


        details = self.lr.get(f'/users/{new_name}')

        if details.get('sophomorixRole', None) != 'student':
            logging.info(f'{new_name} is not a student, no need to check the parent group.')
            return

        oldparentgroup_dn = details['dn'].replace(new_name, f"{old_name}-parents")
        newparentgroup_dn = details['dn'].replace(new_name, f"{new_name}-parents")

        if not self.lr.get(f'/dn/{oldparentgroup_dn}'):

            self.lw._add_group(newparentgroup_dn)

            logging.info(f"Group {newparentgroup_dn} added successfully !")
            return
        else:
            self.lw._rename(oldparentgroup_dn,f"{new_name}-parents" )
            logging.info(f"Group {newparentgroup_dn} added successfully !")
            return

    def del_parent_group(self, dn, **kwargs):
        """
        Delete the parent group STUDENT-parent.

        :param dn: dn of the parent group
        :type dn: basestring
        """


        cn = dn.split(',')[0]

        if not cn.endswith('-parents'):
            logging.info(f'{cn} is not a parent group, nothing to do here.')
            return

        student_dn = dn.replace("-parents", "")
        if self.lr.getval(f'/dn/{student_dn}', 'cn'):
            logging.warning(f"This function will delete a parent group associated with the student {cn}, please check if it's the correct behaviour.")

        if self.lr.get(f'/dn/{dn}'):
            self.lw._del(dn)
            logging.info(f"Group {dn} successfully deleted !")
            return

    def get_parents(self, name):
        """
        Get parents member of the group STUDENT-parents

        :param name: cn of the student
        :type name: basestring
        """

        # Check if the users exist
        student = self.lr.get(f'/users/{name}')

        if student.get('sophomorixRole', None) != 'student':
            logging.info(f'{name} is not a student, can not add parent.')
            return

        parentgroup_dn = student['dn'].replace(name, f"{name}-parents")
        return self.lr.getval(f'/dn/{parentgroup_dn}', 'member')

    def add_parents(self, name, parents=[]):
        """
        Add parents to the group STUDENT-parents

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

    def remove_parents(self, name, parents=[]):
        """
        Remove parents from the group STUDENT-parents

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
            self.ow.remove_member(parentgroup_dn, dn)



