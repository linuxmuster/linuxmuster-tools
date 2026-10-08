import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from linuxmusterTools.common import lprint, spinner, SchoolError
from linuxmusterTools.common.checks import NameChecker
from linuxmusterTools.lmnconfig import LDAP_CONTEXT
from ..models import LMNGroupModel


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNGroupCommon:
    """
    Comme group class for all group types in the linuxmuster project (Projects,
    Schoolclasses, ManagementGroup, Sophomorix Group, etc ...).
    """

    def __init__(self, cn, school='default-school'):

        # TODO if new is enabled
        # if not name_checker.check_login_name(cn):
        #     raise Exception(f"{cn} is not a valid CN")
        # Missing methods _create and _move

        self.cn = cn
        self.lw = LdapWriter()
        self.lr = router
        self.model = LMNGroupModel
        self.data = {}
        self.school = school
        self.new = False
        self.load_data()

    def load_data(self):
        self.data = self.lr.get(f'/units/{self.cn}', school=self.school)

        if not self.data:
            raise Exception(f"The group {self.cn} was not found in ldap.")

    def setattr(self, **kwargs):
        """
        Set some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """


        self.lw._setattr(self, **kwargs)
        self.load_data()

    def delattr(self, **kwargs):
        """
        Delete some attributes of the object directly in Ldap,
        only for an existing object.
        kwargs must contain a data dict with attributes/values to set.
        """


        self.lw._delattr(self, **kwargs)
        self.load_data()

    def getattr(self, attr):
        """
        Get a specific attribute of the object.
        """


        return self.data.get(attr, None)

    def delete(self):
        """
        Delete the object directly in Ldap.
        """


        self.lw._del(self.data['distinguishedName'])

    def remove_member(self, user):
        user_dn = self.lr.getval(f'/users/{user}', 'dn')

        if not user_dn:
            logger.info(f"The user {user} was not found in ldap.")
            raise Exception(f"The object {user} was not found in ldap.")

        try:
            members = self.data['member']
            if user_dn in members:
                members.remove(user_dn)
            else:
                logger.info(f"{user} is not a member of schoolclass {self.cn}")
                return
            if members:
                self.lw._setattr(self, data={'member': members})
            else:
                self.lw._delattr(self, data={'member': None})
            self.load_data()
        except ValueError as e:
            logger.warning(f"Could not remove member {user_dn} from {self.cn}: {str(e)}")

    def remove_all_members(self):
        try:
            self.lw._delattr(self, data={'member': None})
            self.load_data()
        except ValueError as e:
            logger.warning(f"Could not remove all members from {self.cn}: {str(e)}")

    def add_member(self, user):
        user_dn = self.lr.getval(f'/users/{user}', 'dn')

        if not user_dn:
            logger.info(f"The user {user} was not found in ldap.")
            raise Exception(f"The user {user} was not found in ldap.")

        members = self.data['member']

        if user_dn in members:
            logger.info(f"{user} is already a member of {self.cn}")
            return

        members.append(user_dn)

        try:
            self.lw._setattr(self, data={'member': members})
            self.load_data()
        except Exception as e:
            # A failed write must reach the caller: add_members() collects it
            # in its failures list, and a single add_member() call must not
            # report success for a membership which was never written.
            logger.warning(f"Could not append member {user_dn} to {self.cn}: {str(e)}")
            raise

    def add_members(self, userlist):
        """
        Shortcut to add all members from a given list. One invalid cn
        doesn't abort the rest of the batch: it's skipped and reported.

        :param userlist: List of valid cn
        :return: list of (user, error message) tuples for entries that
        could not be added
        """

        failures = []
        for user in userlist:
            try:
                self.add_member(user)
            except Exception as e:
                failures.append((user, str(e)))
        return failures

    def remove_members(self, userlist):
        """
        Shortcut to remove all members from a given list. One invalid cn
        doesn't abort the rest of the batch: it's skipped and reported.

        :param userlist: List of valid cn
        :return: list of (user, error message) tuples for entries that
        could not be removed
        """

        failures = []
        for user in userlist:
            try:
                self.remove_member(user)
            except Exception as e:
                failures.append((user, str(e)))
        return failures


class LMNGroup(LMNGroupCommon):
    """
    Class to handle the Sophomorix Groups (saved under the OU Projects)
    """

    def __init__(self, cn, school='default-school'):
        if school == 'global':
            raise SchoolError(
                f"LMNGroup requires a specific school, got school='global' for group '{cn}'. "
                "Sophomorix groups are always scoped to a single school."
            )
        super().__init__(cn, school=school)
        self._check_ou()

    def _check_ou(self):
        school_details = self.lr.get(f'/schools/{self.school}')
        BASE_OU = f"OU=LMNGroups,OU={self.school},{LDAP_CONTEXT}"
        if not school_details:
            raise Exception(f"School {self.school} was not found in ldap ! Failed to check {BASE_OU}")

        if "LMNGroups" not in (self.lr.getval('/ou', 'ou', school=self.school) or []):
            self.lw._add_ou(BASE_OU)

    def load_data(self):
        # This request may return groups in OU=Projects or OU=LMNGroups !
        self.data = self.lr.get(f'/groups/{self.cn}', school=self.school)

        if not self.data:
            self.new = True
            logger.info(f"The group {self.cn} was not found in ldap.")

            dn = f"CN={self.cn},OU=LMNGroups,OU={self.school},{LDAP_CONTEXT}"

            logger.info(f"His DN would be {dn}. You can create it with the method .create.")

            self.data = {
                'description': self.cn,
                'displayName': self.cn,
                'distinguishedName': dn,
                'mail': [],
                'member': [],
                'name': self.cn,
                'sAMAccountName': self.cn,
                'sophomorixAddMailQuota': [],
                'sophomorixAddQuota': [],
                'sophomorixCreationDate': '',
                'sophomorixHidden': False,
                'sophomorixJoinable': False,
                'sophomorixMailAlias': False,
                'sophomorixMailList': False,
                'sophomorixMailQuota': [],
                'sophomorixQuota': [],
                'sophomorixSchoolname': self.school,
                'sophomorixStatus': '',
                'sophomorixType': 'lmngroup',
            }

    def create(self):
        if self.new:
            self.lw._add_group(self, data=self.data)
            self.new = False
            self.load_data()
        else:
            print(f"Group {self.cn} already exists in LDAP.")

    def _get_membergroup_dn(self, group):
        """
        Resolve the dn of a group which should be a member of this group.
        Only the units of the school of this group are searched, so a
        schoolclass, a project or another group of the same school.

        :param group: cn of a group
        :type group: basestring
        :return: The dn of the group, None if no unit matches
        :rtype: basestring or None
        """


        return self.lr.getval(f'/units/{group}', 'dn', school=self.school)

    def add_membergroup(self, group):
        failures = self.add_membergroups([group])

        if failures:
            raise Exception(failures[0][1])

    def add_membergroups(self, groups):
        """
        Add groups as members of this group, in a single ldap modify.

        The dn of each group is added to the member attribute, like a user,
        so the directory resolves the nested membership itself. Targeted
        MOD_ADD operations keep a concurrent change of the member list, and
        groups already in the list are filtered out first, because the whole
        modify fails if a value is added twice.

        One invalid cn doesn't abort the rest of the batch: it's skipped and
        reported.

        :param groups: List of valid cn of groups
        :type groups: list
        :return: list of (group, error message) tuples for entries that
        could not be added
        :rtype: list
        """


        failures = []
        members_list = []
        to_add = []

        for group in groups:
            group_dn = self._get_membergroup_dn(group)

            if not group_dn:
                logger.info(f"The group {group} was not found in ldap.")
                failures.append((group, f"The group {group} was not found in ldap."))
                continue

            if group_dn.lower() == self.data['distinguishedName'].lower():
                failures.append((group, f"The group {self.cn} can not be a member of itself."))
                continue

            if group_dn in self.data['member'] or group_dn in members_list:
                logger.info(f"{group} is already a member of {self.cn}")
                continue

            members_list.append(group_dn)
            to_add.append(group)

        if not members_list:
            return failures

        try:
            self.lw._setattr(self, data={'member': members_list}, add=True)
            self.load_data()
        except Exception as e:
            logger.warning(f"Could not add member groups {members_list} to {self.cn}: {str(e)}")
            failures.extend((group, str(e)) for group in to_add)

        return failures

    def remove_membergroup(self, group):
        failures = self.remove_membergroups([group])

        if failures:
            raise Exception(failures[0][1])

    def remove_membergroups(self, groups):
        """
        Remove groups from the members of this group, in a single ldap modify.

        See add_membergroups() about why the member list is not rewritten as
        a whole. The users which are direct members are not touched, even if
        they are also members of a removed group.

        One invalid cn doesn't abort the rest of the batch: it's skipped and
        reported.

        :param groups: List of valid cn of groups
        :type groups: list
        :return: list of (group, error message) tuples for entries that
        could not be removed
        :rtype: list
        """


        failures = []
        members_list = []
        to_remove = []

        for group in groups:
            group_dn = self._get_membergroup_dn(group)

            if not group_dn:
                logger.info(f"The group {group} was not found in ldap.")
                failures.append((group, f"The group {group} was not found in ldap."))
                continue

            if group_dn not in self.data['member']:
                logger.info(f"{group} is not a member of {self.cn}")
                continue

            members_list.append(group_dn)
            to_remove.append(group)

        if not members_list:
            return failures

        try:
            self.lw._delattr(self, data={'member': members_list})
            self.load_data()
        except Exception as e:
            logger.warning(f"Could not remove member groups {members_list} from {self.cn}: {str(e)}")
            failures.extend((group, str(e)) for group in to_remove)

        return failures

    def migrate(self):
        """
        Migrate a legacy sophomorix-group entry (living in OU=Projects) to OU=LMNGroups,
        converting its sophomorixType to lmngroup.

        A move only changes the entry's DN, not its attributes: the member list is
        untouched, and memberOf on the members is a computed backlink that follows
        automatically.
        """

        if self.new:
            raise Exception(f"Group {self.cn} does not exist in ldap, nothing to migrate.")

        if self.data['sophomorixType'] == 'lmngroup':
            print(f"Group {self.cn} is already a lmngroup, nothing to migrate.")
            return

        new_ou = f"OU=LMNGroups,OU={self.school},{LDAP_CONTEXT}"
        self.lw._move(self.data['distinguishedName'], new_ou)
        self.load_data()
        self.setattr(data={'sophomorixType': 'lmngroup'})


def find_legacy_groups(school='default-school'):
    """
    List groups still living in OU=Projects (sophomorixType=sophomorix-group),
    not yet migrated to OU=LMNGroups.
    """

    return [group for group in router.get('/groups', school=school) if group['sophomorixType'] == 'sophomorix-group']
