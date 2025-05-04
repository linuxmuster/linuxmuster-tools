import logging
from dataclasses import fields

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from .object import LMNObject
from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNUserModel


logger = logging.getLogger(__name__)
name_checker = NameChecker()

## TODO:
# - load data ✅
# - setattr, delattr, getattr ✅
# - rename entry (change cn) ✅
# - delete entry ✅
# - move (to another OU) ✅
# - create (self.new == False, needs OU, create new CN with ldif in it) ✅
# - check ?
# - Student, Teacher, Staff, Parent, Admins classes


class LMNUser:

    def __init__(self, cn):

        if not name_checker.check_login_name(cn):
            raise Exception(f"{cn} is not a valid CN")

        self.cn = cn
        self.lw = LdapWriter()
        self.lr = router
        self.ow = LMNObject()
        self.model = LMNUser
        self.data = {}
        self.new = False
        self.load_data()

    def load_data(self):
        self.data = self.lr.get(f'/users/{self.cn}')

        if not self.data:
            logger.info(f"The user {self.cn} was not found in ldap.")
            self.new = True
            self.data =  {field.name:field.type() for field in fields(self.model) if field.init}
            self.data['cn'] = self.cn

    def setattr(self, **kwargs):
        """
        Set some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """

        if not self.new:
            self.lw._setattr(self, **kwargs)
            self.load_data()
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')

    def delattr(self, **kwargs):
        """
        Delete some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """

        if not self.new:
            self.lw._delattr(self, **kwargs)
            self.load_data()
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')

    def getattr(self, attr):
        """
        Get a specific attribute of the object.
        """


        return self.data.get(attr, None)

    def rename(self, new_cn):
        """
        Update the cn of an user.
        """


        if not self.new:
            if not name_checker.check_login_name(new_cn):
                logging.warning(f"{new_cn} contains not allowed characters, please check it again.")
            else:
                self.lw._rename(self.data['distinguishedName'], new_cn)
                self.cn = new_cn
                self.load_data()
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')

    def delete(self):
        """
        Delete the user's entry.
        """

        if not self.new:
            self.lw._del(self.data['distinguishedName'])
            self.load_data() # Will load an empty User
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')

    def _move(self, dst_ou):
        """
        Move the user to a new Organisational Unit.
        """

        # Maybe it is better and safer to implement this method only per role
        # and avoid movement accross roles.

        if not self.new:
            # Check OU ?
            try:
                self.lw._move(self.data['distinguishedName'], dst_ou)
                self.load_data()
            except Exception as e:
                logging.error(str(e))
        else:
            logging.warning('This object does not exist in Ldap, please create it first using the method .create()')

    def _create(self, dst_ou):
        """
        For an user marked as new, create an entry in the specified OU.
        """


        if self.new:
            if not self.cn:
                raise Exception("Can not create an entry without a valid CN.")

            if not dst_ou:
                raise Exception("Can not create an entry without a valid OU.")

            if not name_checker.check_login_name(self.cn):
                logging.warning(f"{self.cn} contains not allowed characters, please check it again.")
            else:
                # Check OU ?
                try:
                    self.data['objectClass'] = ['top', 'user', 'person', 'organizationalPerson']
                    self.data['distinguishedName'] = f"CN={self.cn},{dst_ou}"
                    self.data['sAMAccountName'] = self.cn

                    # userAccountControl:
                    # DONT_EXPIRE_PASSWORD (65536) + NORMAL_ACCOUNT (512)
                    # see https://learn.microsoft.com/fr-fr/troubleshoot/windows-server/active-directory/useraccountcontrol-manipulate-account-properties
                    self.data['userAccountControl'] = 66048

                    self.lw._add(self, data=self.data)

                    self.new = False
                    self.load_data()
                except Exception as e:
                    logging.warning(str(e))
        else:
            logging.warning(f"This object already exists in Ldap, it's not possible to create it!")

    def check(self):
        """
        Check the LDAP consistence of the user's entry.
        """

        pass

class LMNStudent(LMNUser):

    def __init__(self, cn):
        super().__init__(cn)
        if self.data.get('sophomorixRole', None) != 'student':
            raise Exception(f"{cn} is not a student!")




    #### ALL the next methods should be moved to student class, parent class or students-parents join

    # def add_parent_group(self, name, **kwargs):
    #     """
    #     Each student should have an associated parent group, like STUDENT-parent
    #     in which the parents are members.
    #
    #     :param name: cn of the student
    #     :type name: basestring
    #     """
    #
    #
    #     details = self.lr.get(f'/users/{name}')
    #
    #     if details.get('sophomorixRole', None) != 'student':
    #         logging.info(f'{name} is not a student, no need to check the parent group.')
    #         return
    #
    #     parentgroup_dn = details['dn'].replace(name, f"{name}-parents")
    #     if not self.lr.get(f'/dn/{parentgroup_dn}'):
    #         self.lw._add_group(parentgroup_dn)
    #         logging.info(f"Group {parentgroup_dn} added successfully !")
    #         return
    #
    #     logging.info(f"Group {parentgroup_dn} already exists !")
    #
    # def get_parent_group(self, name, **kwargs):
    #     """
    #     Each student should have an associated parent group, like STUDENT-parent
    #     in which the parents are members.
    #
    #     :param name: cn of the student
    #     :type name: basestring
    #     """
    #
    #
    #     details = self.lr.get(f'/users/{name}')
    #
    #     if details.get('sophomorixRole', None) != 'student':
    #         logging.info(f'{name} is not a student, no need to check the parent group.')
    #         return
    #
    #     parentgroup_dn = details['dn'].replace(name, f"{name}-parents")
    #     return self.lr.get(f'/dn/{parentgroup_dn}')
    #
    # def move_parent_group(self, name, new_group, **kwargs):
    #     """
    #     Move the parent group STUDENT-parent to a new group (like from schoolclass 5a
    #     to schoolclass 6a).
    #
    #     :param name: cn of the student
    #     :type name: basestring
    #     :param old_group: old schoolclass of the student
    #     :type old_group: basestring
    #     :param new_group: new schoolclass of the student
    #     :type new_group: basestring
    #     """
    #
    #
    #     parents_dn = self.lr.getval(f'/search/{name}-parents', 'dn')
    #
    #     if len(parents_dn) == 0:
    #         # Adding new parents group
    #         self.add_parent_group(name)
    #     elif len(parents_dn) == 1:
    #         actual_dn = parents_dn[0]
    #         actual_group = actual_dn.split(',')[1].split('=')[1]
    #
    #         if f'OU={new_group}' in actual_dn:
    #             logging.info("Nothing to do, dn already exists")
    #             return
    #         else:
    #             newparentgroup_dn = actual_dn.replace(f"OU={actual_group}", f"OU={new_group}")
    #             newparentgroup_ou = ','.join(newparentgroup_dn.split(',')[1:])
    #
    #             logging.info(f"Moving {actual_dn} to {newparentgroup_dn}")
    #             self.lw._move(actual_dn, newparentgroup_ou)
    #             logging.info(f"Group {newparentgroup_dn} moved successfully !")
    #             return
    #     else:
    #         # Too many parents groups for this user, this must be checked first
    #         print("TO CHECK")
    #
    #
    # def del_parent_group(self, name, **kwargs):
    #     """
    #     Delete the parent group STUDENT-parent.
    #
    #     :param dn: dn of the parent group
    #     :type dn: basestring
    #     """
    #
    #
    #     details = self.lr.get(f'/users/{name}')
    #
    #     if details.get('sophomorixRole', None) != 'student':
    #         logging.info(f'{name} is not a student, no need to check the parent group.')
    #         return
    #
    #     parentgroup_dn = details['dn'].replace(name, f"{name}-parents")
    #     if self.lr.get(f'/dn/{parentgroup_dn}'):
    #         self.lw._del(parentgroup_dn)
    #         logging.info(f"Group {parentgroup_dn} successfully deleted !")
    #         return
    #
    # def del_parent_group_per_dn(self, dn, **kwargs):
    #     """
    #     Delete the parent group STUDENT-parent.
    #
    #     :param dn: dn of the parent group
    #     :type dn: basestring
    #     """
    #
    #
    #     cn = dn.split(',')[0]
    #
    #     if not cn.endswith('-parents'):
    #         logging.info(f'{cn} is not a parent group, nothing to do here.')
    #         return
    #
    #     student_dn = dn.replace("-parents", "")
    #     if self.lr.getval(f'/dn/{student_dn}', 'cn'):
    #         logging.warning(f"This function will delete a parent group associated with the student {cn}, please check if it's the correct behaviour.")
    #
    #     if self.lr.get(f'/dn/{dn}'):
    #         self.lw._del(dn)
    #         logging.info(f"Group {dn} successfully deleted !")
    #         return
    #
    # def get_parents(self, name):
    #     """
    #     Get parents member of the group STUDENT-parents
    #
    #     :param name: cn of the student
    #     :type name: basestring
    #     """
    #
    #     # Check if the users exist
    #     student = self.lr.get(f'/users/{name}')
    #
    #     if student.get('sophomorixRole', None) != 'student':
    #         logging.info(f'{name} is not a student, can not add parent.')
    #         return
    #
    #     parentgroup_dn = student['dn'].replace(name, f"{name}-parents")
    #     return self.lr.getval(f'/dn/{parentgroup_dn}', 'member')
    #
    # def add_parents(self, name, parents=[]):
    #     """
    #     Add parents to the group STUDENT-parents
    #
    #     :param name: cn of the student
    #     :type name: basestring
    #     :param parents: List of cn of the parents
    #     :type parents: list
    #     """
    #
    #     # Check if the users exist
    #     student = self.lr.get(f'/users/{name}')
    #
    #     if student.get('sophomorixRole', None) != 'student':
    #         logging.info(f'{name} is not a student, can not add parent.')
    #         return
    #
    #     parents_dn = []
    #     for parent in parents:
    #         details = self.lr.get(f'/users/{parent}')
    #         # Allowing all roles but student
    #         if details.get('sophomorixRole', 'student') == 'student':
    #             logging.info(f'{parent} do not have a valid role to be parent.')
    #             return
    #         # At this point, we have a valid role for a parent
    #         parents_dn.append(details['dn'])
    #
    #     parentgroup_dn = student['dn'].replace(name, f"{name}-parents")
    #     for dn in parents_dn:
    #         self.ow.add_member(parentgroup_dn, dn)
    #
    # def remove_parents(self, name, parents=[]):
    #     """
    #     Remove parents from the group STUDENT-parents
    #
    #     :param name: cn of the student
    #     :type name: basestring
    #     :param parents: List of cn of the parents
    #     :type parents: list
    #     """
    #
    #     # Check if the users exist
    #     student = self.lr.get(f'/users/{name}')
    #
    #     if student.get('sophomorixRole', None) != 'student':
    #         logging.info(f'{name} is not a student, can not add parent.')
    #         return
    #
    #     parents_dn = []
    #     for parent in parents:
    #         details = self.lr.get(f'/users/{parent}')
    #         # Allowing all roles but student
    #         if details.get('sophomorixRole', 'student') == 'student':
    #             logging.info(f'{parent} do not have a valid role to be parent.')
    #             return
    #         # At this point, we have a valid role for a parent
    #         parents_dn.append(details['dn'])
    #
    #     parentgroup_dn = student['dn'].replace(name, f"{name}-parents")
    #     for dn in parents_dn:
    #         self.ow.remove_member(parentgroup_dn, dn)
    #
    #
    # def check_parents_groups(self):
    #     """
    #     Utility function for upgrade to LMN 7.3. This function creates for each
    #     student an associated parent CN and checks for orphan parents CN in order to
    #     delete it.
    #     """
    #
    #
    #     # First check: each student has a parent group
    #     students = self.lr.getval('/roles/student', 'cn')
    #     count = len(students)
    #     orphan_student_cn = []
    #     report = {
    #         'add': [],
    #         'move': {},
    #         'delete': [],
    #     }
    #
    #     with spinner:
    #         for idx, student in enumerate(students):
    #             parent_group = self.get_parent_group(student)
    #             if not parent_group:
    #                 orphan_student_cn.append(student)
    #             spinner.print(f"First pass: checking parent group of existing student {idx+1:>4} of {count}")
    #
    #     print()
    #
    #     # Create missing parents groups
    #     if orphan_student_cn:
    #         print("Creating missing parents group ...")
    #         for student in orphan_student_cn:
    #             parents_dn = self.lr.getval(f'/search/{student}-parents', 'dn')
    #             if len(parents_dn) == 0:
    #                 # self.add_parent_group(student)
    #                 report['add'].append(student)
    #                 # lprint.info(f"Missing parent group for {student} created!")
    #             elif len(parents_dn) == 1:
    #                 # lprint.info(f"Maybe should {parents_dn[0]} be renamed for student {student}")
    #                 report['move'][student] = parents_dn
    #             else:
    #                 report['move'][student] = parents_dn
    #                 # lprint.info(f"Too many parents groups for {student}: ")
    #                 # for dn in parents_dn:
    #                 #     lprint.info(f"\t{dn}")
    #     # else:
    #     #     lprint.success("Checks done, everything is alright!")
    #
    #     orphan_parent_dn = []
    #
    #     # Second check: each parent group is associated to a real student in the same OU
    #     parent_groups = self.lr.get('/search/-parents', attributes=['cn', 'dn'])
    #     count = len(parent_groups)
    #
    #     with spinner:
    #         for idx, group in enumerate(parent_groups):
    #             cn = group['cn']
    #             dn = group['dn']
    #
    #             # Ignore global groups
    #             if cn in ['all-parents', 'global-parents']:
    #                 continue
    #
    #             parentgroup_schoolclass = dn.split(',')[1].split('=')[1]
    #             student = cn.split('-')[0]
    #             student_data = self.lr.get(f"/users/{student}")
    #             if not student_data or parentgroup_schoolclass != student_data['sophomorixAdminClass']:
    #                 orphan_parent_dn.append(dn)
    #             spinner.print(f"Second pass: checking existing parent group {idx+1:>4} of {count}")
    #
    #     print()
    #
    #     # Delete orphan parents groups
    #     if orphan_parent_dn:
    #         # print("Deleting obsolete parents group ...")
    #         for parent in orphan_parent_dn:
    #             # self.del_parent_group_per_dn(parent)
    #             report['delete'].append(parent)
    #             # lprint.info(f"Obsolete parent group {parent} can be deleted!")
    #     # else:
    #     #     lprint.success("Checks done, everything is alright!")
    #
    #     return report
