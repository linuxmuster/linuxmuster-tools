import ldap
import logging

from linuxmusterTools.common import lprint, spinner, SchoolclassExistsError
from linuxmusterTools.common.checks import NameChecker
from ..connector import LdapConnector
from ..ldap_writer import LdapWriter
from ..models import LMNSchoolClassModel
from .group import LMNGroupCommon
from ..urls.ldaprouter import router


logger = logging.getLogger(__name__)
name_checker = NameChecker()

SCHOOLCLASS_SUBGROUP_SUFFIXES = ('-students', '-teachers', '-parents')

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

        members = list(set(members))

        if members:
            self.setattr(data={'member': members})
        elif self.data.get('member'):
            # An empty member list is a valid state (e.g. a schoolclass
            # without parents accounts), setattr() would raise a ValueError.
            self.delattr(data={'member': None})


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
        self.fill_admins()

    def add_members(self, userlist):
        failures = super().add_members(userlist)
        self.fill_group_members()
        self.fill_admins()
        return failures

    def remove_member(self, user):
        super().remove_member(user)
        self.fill_group_members()
        self.fill_admins()

    def remove_members(self, userlist):
        failures = super().remove_members(userlist)
        self.fill_group_members()
        self.fill_admins()
        return failures

    def remove_all_teachers(self):
        try:
            new_members = []
            for member in self.data['member']:
                if ",OU=Teachers," not in member:
                    new_members.append(member)

            if new_members:
                self.lw._setattr(self, data={'member': new_members})
            else:
                self.lw._delattr(self, data={'member': None})
            self.load_data()
            self.teachers_group.fill_members()
            self.fill_admins()
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

    def fill_admins(self):
        """
        Set sophomorixAdmins to the teachers of the schoolclass, read from the
        same member list as the 7a-teachers subgroup.

        sophomorix stores the teachers of a class in sophomorixAdmins (as
        sAMAccountNames) and rebuilds the member attribute from it: a teacher
        who is only in member is invisible to everything reading
        sophomorixAdmins (webui and api permissions, lmncli, first passwords
        printing), and is dropped from member by the next sophomorix run
        touching this class (AD_project_sync_members). Writing both keeps the
        two views of the same fact identical.

        Students are deliberately not handled here: adding one to a class is
        not only an LDAP membership, it needs the share management which lives
        in sophomorix.
        """


        admins = sorted({
            member_dn.split(',')[0].removeprefix('CN=')
            for member_dn in self.data['member']
            if 'OU=Teachers' in member_dn and 'OU=attic' not in member_dn
        })

        if admins:
            self.setattr(data={'sophomorixAdmins': admins})
        elif self.data.get('sophomorixAdmins'):
            # An empty list is a valid state (a class without any teacher),
            # setattr() would raise a ValueError.
            self.delattr(data={'sophomorixAdmins': None})

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

def delete_schoolclass_subgroups(cn, school='default-school'):
    """
    Delete the subgroups <cn>-students, <cn>-teachers and <cn>-parents of a
    schoolclass which does not exist anymore, and the organizational unit of
    this schoolclass if nothing is left in it. That OU is the parent of the
    subgroups, so an OU left alone, without any subgroup to locate it, is not
    handled here.

    sophomorix-class --kill (and --delete-all-empty-classes) only deletes the
    schoolclass group itself: the subgroups created by LMNSchoolclassGroup are
    unknown to sophomorix and stay in LDAP with their members and their mail
    addresses, invisible to every listing (those filter sophomorixType on the
    exact value 'adminclass'), and would be reused as they are if the
    schoolclass was created again.

    :param cn: Name of the deleted schoolclass, e.g. 7a
    :type cn: string
    :param school: School of the deleted schoolclass
    :type school: string
    :return: DN of each deleted object
    :rtype: list
    """


    lw = LdapWriter()
    lc = LdapConnector()

    if router.get(f'/schoolclasses/{cn}', school=school):
        raise SchoolclassExistsError(
            f"The schoolclass {cn} still exists in {school}, refusing to delete its subgroups."
        )

    deleted = []
    ou_dn = ''

    for suffix in SCHOOLCLASS_SUBGROUP_SUFFIXES:
        subgroup = router.get(f'/units/{cn}{suffix}', school=school)

        if not subgroup:
            continue

        dn = subgroup['distinguishedName']

        # The subgroups are created in the OU of the schoolclass, so their
        # parent is the OU to clean up once they are gone.
        parent_dn = dn.split(',', 1)[1]

        if parent_dn.startswith(f'OU={cn},'):
            ou_dn = parent_dn

        lw._del(dn)
        deleted.append(dn)

    if not ou_dn:
        return deleted

    # The OU of a schoolclass also holds the accounts of its students: it may
    # only be deleted once nothing is left in it. A schoolclass killed while
    # its students still exist keeps them here until the next import.
    _, base_dn = lc._get_conn()
    children = lc._get('(objectClass=*)', scope=ldap.SCOPE_ONELEVEL,
                       subdn=ou_dn.removesuffix(base_dn))

    if children:
        logger.warning(
            f"The OU of the schoolclass {cn} still contains {len(children)} object(s), keeping it."
        )
        return deleted

    lw._del(ou_dn)
    deleted.append(ou_dn)

    return deleted

def orphan_schoolclass_subgroups(school='default-school'):
    """
    List the schoolclasses whose subgroups are still in LDAP while the
    schoolclass itself is gone, e.g. after a sophomorix-class --kill run
    before lmncli was called to clean up behind it.

    :param school: School to scan
    :type school: string
    :return: Sorted list of the names of the deleted schoolclasses
    :rtype: list
    """


    candidates = set()

    for group in router.getvalues('/units', ['cn', 'sophomorixType'], school=school):
        group_type = group['sophomorixType'] or ''

        if not group_type.startswith('adminclass-'):
            continue

        suffix = group_type.removeprefix('adminclass')

        if suffix in SCHOOLCLASS_SUBGROUP_SUFFIXES and group['cn'].endswith(suffix):
            candidates.add(group['cn'].removesuffix(suffix))

    return sorted(
        cn for cn in candidates
        if not router.get(f'/schoolclasses/{cn}', school=school)
    )
