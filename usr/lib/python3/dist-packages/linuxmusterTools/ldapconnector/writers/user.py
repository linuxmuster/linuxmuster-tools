import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from .object import LMNObjectWriter
from linuxmusterTools.common import lprint


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

    def move_parent_group(self, name, new_group, **kwargs):
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


        parents_dn = self.lr.getval(f'/search/{name}-parents', 'dn')

        if len(parents_dn) == 0:
            # Adding new parents group
            self.add_parent_group(name)
        elif len(parents_dn) == 1:
            actual_dn = parents_dn[0]
            actual_group = actual_dn.split(',')[1].split('=')[1]

            if f'OU={new_group}' in actual_dn:
                logging.info("Nothing to do, dn already exists")
                return
            else:
                newparentgroup_dn = actual_dn.replace(f"OU={actual_group}", f"OU={new_group}")
                newparentgroup_ou = ','.join(newparentgroup_dn.split(',')[1:])

                logging.info(f"Moving {actual_dn} to {newparentgroup_dn}")
                self.lw._move(actual_dn, newparentgroup_ou)
                logging.success(f"Group {newparentgroup_dn} moved successfully !")
                return
        else:
            # Too many parents groups for this user, this must be checked first
            print("TO CHECK")


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

    def del_parent_group(self, name, **kwargs):
        """
        Delete the parent group STUDENT-parent.

        :param dn: dn of the parent group
        :type dn: basestring
        """


        details = self.lr.get(f'/users/{name}')

        if details.get('sophomorixRole', None) != 'student':
            logging.info(f'{name} is not a student, no need to check the parent group.')
            return

        parentgroup_dn = details['dn'].replace(name, f"{name}-parents")
        if self.lr.get(f'/dn/{parentgroup_dn}'):
            self.lw._del(parentgroup_dn)
            logging.info(f"Group {parentgroup_dn} successfully deleted !")
            return

    def del_parent_group_per_dn(self, dn, **kwargs):
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


    def check_parents_groups(self):
        """
        Utility function for upgrade to LMN 7.3. This function creates for each
        student an associated parent CN and checks for orphan parents CN in order to
        delete it.
        """


        # First check: each student has a parent group
        students = self.lr.getval('/roles/student', 'cn')
        count = len(students)
        orphan_student_cn = []

        for idx, student in enumerate(students):
            parent_group = self.get_parent_group(student)
            if not parent_group:
                orphan_student_cn.append(student)
            print(f"First pass: checking parent group of existing student {idx+1:>4} of {count}", end="\r")

        print()

        # Create missing parents groups
        if orphan_student_cn:
            print("Creating missing parents group ...")
            for student in orphan_student_cn:
                self.add_parent_group(student)
                lprint.info(f"Missing parent group for {student} created!")
        else:
            lprint.success("Checks done, everything is alright!")

        orphan_parent_dn = []

        # Second check: each parent group is associated to a real student in the same OU
        parent_groups = self.lr.get('/search/-parents', attributes=['cn', 'dn'])
        count = len(parent_groups)

        for idx, group in enumerate(parent_groups):
            cn = group['cn']
            dn = group['dn']

            # Ignore global groups
            if cn in ['all-parents', 'global-parents']:
                continue

            parentgroup_schoolclass = dn.split(',')[1].split('=')[1]
            student = cn.split('-')[0]
            student_data = self.lr.get(f"/users/{student}")
            if not student_data or parentgroup_schoolclass != student_data['sophomorixAdminClass']:
                orphan_parent_dn.append(dn)
            print(f"Second pass: checking existing parent group {idx+1:>4} of {count}", end="\r")

        print()

        # Delete orphan parents groups
        if orphan_parent_dn:
            print("Deleting obsolete parents group ...")
            for parent in orphan_parent_dn:
                self.del_parent_group_per_dn(parent)
                lprint.info(f"Obsolete parent group {parent} deleted!")
        else:
            lprint.success("Checks done, everything is alright!")

