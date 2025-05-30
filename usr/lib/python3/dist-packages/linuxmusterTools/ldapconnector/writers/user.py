import logging
from dataclasses import fields

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from .schoolclass import LMNSchoolclass
from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNUserModel
from .group import LMNGroupCommon

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

    def __init__(self, cn, school='default-school'):

        if not name_checker.check_login_name(cn):
            raise Exception(f"{cn} is not a valid CN")

        self.cn = cn
        self.lw = LdapWriter()
        self.lr = router
        self.model = LMNUserModel
        self.data = {}
        self.new = False
        self.school = school
        self.load_data()

    def load_data(self):
        self.data = self.lr.get(f'/users/{self.cn}', school=self.school)

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
        Move the user to a new Organisational Unit.This method just move an
        existing ldap account to a new OU but do not handle the filesystem
        to move the user's files: it's necessary to use separately
        Samba/smbclient for this. Use this method very carefully!
        """


        # Maybe it is better and safer to implement this method only per role
        # and avoid movement across roles.

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
        This method just create an account ldap but do not handle the filesystem
        to create the appropriate directory tree for the user: it's necessary to
        use separately Samba/smbclient for this. Use this method very carefully!
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

    def create(self):
        raise NotImplementedError

    def move(self):
        raise NotImplementedError

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

        self.load_parents()

    def load_parents(self):

        self.parents_group = LMNParentsGroup(self.cn)
        self.parents = self.parents_group.parents
        self.parents_cn = self.parents_group.parents_cn

    def add_parent(self, parent_cn):

        self.parents_group.add_parent(parent_cn)
        self.load_parents()

    def remove_parent(self, parent_cn):

        self.parents_group.remove_parent(parent_cn)
        self.load_parents()

    def move(self, new_schoolclass):

        valid_schoolclasses = self.lr.getval('/schoolclasses', 'cn')

        if new_schoolclass not in valid_schoolclasses:
            raise Exception(f'{new_schoolclass} is not even a valid schoolclass!')

        old_schoolclass = self.data['sophomorixAdminClass']

        if old_schoolclass == new_schoolclass:
            return

        dst_ou = self.data['distinguishedName'].replace(f'OU={old_schoolclass}', f'OU={new_schoolclass}')
        dst_ou = dst_ou.replace(f'CN={self.cn},', '')

        self._move(dst_ou)

        # Only modify the attributes, does not actually move the user's files.

        old_schoolclass_group = LMNSchoolclass(old_schoolclass)
        old_schoolclass_group.remove_member(self.cn)

        new_schoolclass_group = LMNSchoolclass(new_schoolclass)
        new_schoolclass_group.add_member(self.cn)

        self.setattr(data={
            'sophomorixAdminClass': new_schoolclass,
            'homeDirectory': self.data['homeDirectory'].replace(old_schoolclass, new_schoolclass),
            'unixHomeDirectory': self.data['unixHomeDirectory'].replace(old_schoolclass, new_schoolclass),
            'sophomorixIntrinsic2': self.data['sophomorixIntrinsic2'].replace(old_schoolclass, new_schoolclass)
        })

    def create(self, school, new_schoolclass):
        # Will come later, just need to provide specific data to students
        self.data['sophomorixRole'] = 'student'
        # dst_ou = BASE_OU + school + schoolclass
        # self._create(dst_ou)
        raise NotImplementedError


class LMNTeacher(LMNUser):

    def __init__(self, cn):
        super().__init__(cn)
        if self.data.get('sophomorixRole', None) != 'teacher':
            raise Exception(f"{cn} is not a teacher!")

    def move(self):
        # The only moves for a teacher should be in attic or back in teacher
        # role
        raise NotImplementedError

    def create(self):
        # Will come later, just need to provide specific data to teachers
        self.data['sophomorixRole'] = 'teacher'
        # dst_ou = BASE_OU + school + teachers
        # self._create(dst_ou)
        raise NotImplementedError

class LMNParent(LMNUser):

    def __init__(self, cn):
        super().__init__(cn)
        if self.data.get('sophomorixRole', None) != 'parent':
            raise Exception(f"{cn} is not a parent!")

    def move(self):
        # The only moves for a parent should be in attic or back in parent
        # role
        raise NotImplementedError

    def create(self):
        # Will come later, just need to provide specific data to parents
        self.data['sophomorixRole'] = 'parent'
        # dst_ou = BASE_OU + school + parents
        # self._create(dst_ou)
        raise NotImplementedError

class LMNStaff(LMNUser):

    def __init__(self, cn):
        super().__init__(cn)
        if self.data.get('sophomorixRole', None) != 'staff':
            raise Exception(f"{cn} is not a staff member!")

    def move(self):
        # The only moves for a staff member should be in attic or back in staff
        # role
        raise NotImplementedError

    def create(self):
        # Will come later, just need to provide specific data to staff
        self.data['sophomorixRole'] = 'staff'
        # dst_ou = BASE_OU + school + staff
        # self._create(dst_ou)
        raise NotImplementedError

class LMNSchoolAdmin(LMNUser):

    def __init__(self, cn):
        super().__init__(cn)
        if self.data.get('sophomorixRole', None) != 'schooladministrator':
            raise Exception(f"{cn} is not a schooladministrator!")

class LMNGlobalAdmin(LMNUser):

    def __init__(self, cn):
        super().__init__(cn)
        if self.data.get('sophomorixRole', None) != 'globaladministrator':
            raise Exception(f"{cn} is not a globaladministrator!")



class LMNParentsGroup(LMNGroupCommon):

    def __init__(self, student_cn, school='default-school'):
        """
        cn represents the cn of the students. For example, if cn is frayka, this
         class will handle the group
         CN=frayka-parents,OU=Student-Parents,OU=Parents,OU=default-school,OU=SCHOOLS...
        """


        self.cn = f"{student_cn}-parents"
        self.student_cn = student_cn
        super().__init__(self.cn, school=school)

    def load_data(self):
        # Check if the given cn is from a student
        student = self.lr.get(f'/users/{self.student_cn}')
        if student['sophomorixRole'] != 'student':
            raise Exception(f"The student {self.student_cn} was not found in ldap.")

        # Check if the Student-Parents group exists
        if not 'Student-Parents' in self.lr.getval('/ou/parents', 'ou', school=self.school):
            domain = ','.join(student['dn'].split(',')[3:])
            new_ou = f"OU=Student-Parents,OU=Parents,{domain}"
            self.lw._add_ou(new_ou)

        self.data = self.lr.get(f'/units/{self.cn}', school=self.school)

        if not self.data:
            # This kind of group must always be provided in Ldap, so if it's not
            # existing, it must be automatically created.
            logging.info(f"The group {self.cn}-parents was not found in ldap, creating it!")

            # TODO: Check the following attributes:
            domain = ','.join(student['dn'].split(',')[3:])
            new_dn = f"CN={self.cn},OU=Student-Parents,OU=Parents,{domain}"

            self.data = {
                'description': self.cn,
                'displayName': self.cn,
                'distinguishedName': new_dn,
                'mail': [],
                'name': self.cn,
                'sAMAccountName': self.cn,
                'sophomorixAddMailQuota': '---',
                'sophomorixAddQuota': '---',
                'sophomorixCreationDate': '',
                'sophomorixHidden': True,
                'sophomorixJoinable': False,
                'sophomorixMailAlias': False,
                'sophomorixMailList': False,
                'sophomorixMailQuota': '---:---:',
                'sophomorixQuota': [f'{self.school}:---:---:', 'linuxmuster-global:---:---:'],
                'sophomorixSchoolname': self.school,
                'sophomorixStatus': '',
                'sophomorixType': f"adminparents",
            }

            self.lw._add_group(self, data=self.data)

        self.get_parents()

    def get_parents(self):

        self.parents_cn = [dn.split(',')[0].split('=')[1]
            for dn in self.data.get('member', [])
        ]
        self.parents = [self.lr.get(f'/users/{cn}') for cn in self.parents_cn]

    def add_parent(self, parent_cn):

        # TODO: this allow all roles to be a parent, should this be restrited to
        # users in parents OU ?

        self.add_member(parent_cn)
        self.get_parents()

    def remove_parent(self, parent_cn):

        self.remove_member(parent_cn)
        self.get_parents()
