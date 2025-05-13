import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNSchoolClassModel
from .group import LMNGroupCommon


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNSchoolclassGroup(LMNGroupCommon):
    """
    Class to handle subgroups of a schoolclass, like e.g. 7a-students, 7a-teachers
    and 7a-parents for the schoolclass 7a.
    """


    def __init__(self, cn, schoolclass_data=''):
        self.schoolclass_data = schoolclass_data
        super().__init__(cn)

    def load_data(self):
        self.model = LMNSchoolClassModel
        self.data = self.lr.get(f'/units/{self.cn}')

        if not self.data:
            # This kind of group must always be provided in Ldap, so if it's not
            # existing, it must be automatically created.
            logging.info(f"The group {self.cn} was not found in ldap, creating it!")

            # TODO: Check the following attributes:
            dn = self.schoolclass_data['dn'].replace(
                        f"CN={self.schoolclass_data['cn']}",
                        f"CN={self.cn}"
            )

            mail = self.schoolclass_data['mail'][0].replace(
                        self.schoolclass_data['cn'],
                        self.cn
            )

            school = self.schoolclass_data['sophomorixSchoolname']

            self.data = {
                'description': self.cn,
                'displayName': self.cn,
                'distinguishedName': dn,
                'mail': [mail],
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
                'sophomorixQuota': [f'{school}:---:---:', 'linuxmuster-global:---:---:'],
                'sophomorixSchoolname': school,
                'sophomorixStatus': '',
                'sophomorixType': 'adminclass',
            }

            self.lw._add_group(self, data=self.data)

    def delete(self):

        self.lw._del(self.data['distinguishedName'])

    def fill_members(self):
        """
        This method is only intended for subgroups like 7a-teachers, 7a-parents
        and 7a-students, and will fill the membership through the memberships
        stored in CN=7a,OU=7a.
        """


        schoolclass_members = self.schoolclass_data['member']

        if self.cn.endswith('-students'):
            for member in schoolclass_members:
                if 'OU=Students' in member:
                    cn = member.split(',')[0].split('=')[1]
                    self.add_member(cn)
        elif self.cn.endswith('-parents'):
            # TODO
            pass
        elif self.cn.endswith('-teachers'):
            for member in schoolclass_members:
                if 'OU=Teachers' in member:
                    cn = member.split(',')[0].split('=')[1]
                    self.add_member(cn)
        else:
            return



class LMNSchoolclass(LMNGroupCommon):

    def __init__(self, cn):
        super().__init__(cn)
        self.model = LMNSchoolClassModel
        self.students_group = LMNSchoolclassGroup(f"{self.cn}-students", schoolclass_data=self.data)
        self.teachers_group = LMNSchoolclassGroup(f"{self.cn}-teachers", schoolclass_data=self.data)
        self.parents_group = LMNSchoolclassGroup(f"{self.cn}-parents", schoolclass_data=self.data)

    def load_data(self):
        self.data = self.lr.get(f'/schoolclasses/{self.cn}')

        if not self.data:
            raise Exception(f"The schoolclass {self.cn} was not found in ldap.")