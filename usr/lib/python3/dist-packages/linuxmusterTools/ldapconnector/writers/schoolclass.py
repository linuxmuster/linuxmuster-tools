import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNSchoolClassModel
from .group import LMNGroupCommon
from ..urls.ldaprouter import router


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNSchoolclassGroup(LMNGroupCommon):
    """
    Class to handle subgroups of a schoolclass, like e.g. 7a-students, 7a-teachers
    and 7a-parents for the schoolclass 7a.
    """


    def __init__(self, cn, suffix='', schoolclass_data={}):
        # Doing nothing without associated schoolclass
        if not schoolclass_data:
            return

        self.schoolclass_data = schoolclass_data
        self.suffix = suffix

        self.type = None
        if suffix in ['-parents', '-students', '-teachers']:
            self.type = suffix[1:]

        self.school = self.schoolclass_data.get('sophomorixSchoolname', 'default-school')
        super().__init__(f"{cn}{suffix}", school=self.school)

    def load_data(self):
        self.model = LMNSchoolClassModel
        self.data = self.lr.get(f'/units/{self.cn}', school=self.school)

        if not self.data:
            # This kind of group must always be provided in Ldap, so if it's not
            # existing, it must be automatically created.
            logger.info(f"The group {self.cn} was not found in ldap, creating it!")

            # TODO: Check the following attributes:
            dn = self.schoolclass_data['dn'].replace(
                        f"CN={self.schoolclass_data['cn']}",
                        f"CN={self.cn}"
            )

            mail = self.schoolclass_data['mail'][0].replace(
                        self.schoolclass_data['cn'],
                        self.cn
            )

            self.data = {
                'description': self.cn,
                'displayName': self.cn,
                'distinguishedName': dn,
                'mail': [mail],
                'member': [],
                'name': self.cn,
                'sAMAccountName': self.cn,
                'sophomorixAddMailQuota': '---',
                'sophomorixAddQuota': '---',
                'sophomorixCreationDate': '',
                'sophomorixHidden': False,
                'sophomorixJoinable': False,
                'sophomorixMailAlias': False,
                'sophomorixMailList': False,
                'sophomorixMailQuota': '---:---:',
                'sophomorixQuota': [f'{self.school}:---:---:', 'linuxmuster-global:---:---:'],
                'sophomorixSchoolname': self.school,
                'sophomorixStatus': '',
                'sophomorixType': f"adminclass{self.suffix}",
            }

            self.lw._add_group(self, data=self.data)

    def delete(self):

        self.lw._del(self.data['distinguishedName'])

    def fill_members(self):
        """
        This method is only intended for subgroups like 7a-teachers, 7a-parents
        and 7a-students, and will fill the membership through the memberships
        stored in CN=7a,OU=7a or OU=Student-Parents,OU=Parents.
        """


        members = []

        if self.type == 'students':
            for member_dn in self.schoolclass_data['member']:
                if 'OU=Students' in member_dn:
                    members.append(member_dn)

        elif self.type == 'parents':
            for student in self.schoolclass_data['sophomorixMembers']:
                parents_dn = self.lr.getval(f'/units/{student}-parents', 'member')
                if parents_dn is not None:
                    for dn in parents_dn:
                        members.append(dn)


        elif self.type == 'teachers':
            for member_dn in self.schoolclass_data['member']:
                if 'OU=Teachers' in member_dn and 'OU=attic' not in member_dn:
                    members.append(member_dn)
        else:
            return

        self.setattr(data={'member': list(set(members))})


class LMNSchoolclass(LMNGroupCommon):

    def __init__(self, cn, school='default-school'):
        super().__init__(cn, school=school)
        self.model = LMNSchoolClassModel

    def load_data(self):
        self.data = self.lr.get(f'/schoolclasses/{self.cn}', school=self.school)

        if not self.data:
            raise Exception(f"The schoolclass {self.cn} was not found in ldap.")

        self.students_group = LMNSchoolclassGroup(self.cn, suffix="-students", schoolclass_data=self.data)
        self.teachers_group = LMNSchoolclassGroup(self.cn, suffix="-teachers", schoolclass_data=self.data)
        self.parents_group = LMNSchoolclassGroup(self.cn, suffix="-parents", schoolclass_data=self.data)

    def add_member(self, user):
        super().add_member(user)
        self.fill_group_members()

    def add_members(self, userlist):
        super().add_members(userlist)
        self.fill_group_members()

    def remove_member(self, user):
        super().remove_member(user)
        self.fill_group_members()

    def remove_members(self, userlist):
        super().remove_members(userlist)
        self.fill_group_members()

    def remove_all_teachers(self):
        try:
            new_members = []
            for member in self.data['member']:
                if ",OU=Teachers," not in member:
                    new_members.append(member)

            self.lw._setattr(self, data={'member': new_members})
            self.load_data()
            self.teachers_group.fill_members()
        except ValueError as e:
            logger.warning(f"Could not remove all teachers from {self.cn}: {str(e)}")

    def fill_group_members(self):
        """
        This method is only intended to populate subgroups like 7a-teachers,
        7a-parents and 7a-students, and will fill the membership through the
        memberships stored in CN=7a,OU=7a or OU=Student-Parents,OU=Parents.
        """


        self.students_group.fill_members()
        self.teachers_group.fill_members()
        self.parents_group.fill_members()

class LMNSchoolclasses:

    def __init__(self, school='default-school'):
        self.lr = router
        self.schoolclasses = {
            schoolclass['cn']: LMNSchoolclass(schoolclass['cn'], school=school)
            for schoolclass in self.lr.get('/schoolclasses')
        }

    def __len__(self):
        return len(self.schoolclasses)

    def keys(self):
        yield from self.schoolclasses.keys()

    def items(self):
        yield from self.schoolclasses.items()

    def __getitem__(self, schoolclass_cn):
        return self.schoolclasses[schoolclass_cn]
