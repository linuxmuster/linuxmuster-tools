import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from linuxmusterTools.common import lprint, spinner
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
            self.lw._setattr(self, data={'member': members})
            self.load_data()
        except ValueError as e:
            logger.warning(f"Could not remove member {user_dn} from {self.cn}: {str(e)}")

    def remove_all_members(self):
        try:
            self.lw._setattr(self, data={'member': []})
            self.load_data()
        except ValueError as e:
            logger.warning(f"Could not remove all members from {self.cn}: {str(e)}")

    def add_member(self, user):
        user_dn = self.lr.getval(f'/users/{user}', 'dn')

        if not user_dn:
            logger.info(f"The user {user} was not found in ldap.")
            raise Exception(f"The user {user} was not found in ldap.")

        try:
            members = self.data['member']
            members.append(user_dn)
            self.lw._setattr(self, data={'member': members})
            self.load_data()
        except Exception as e:
            logger.warning(f"Could not append member {user_dn} to {self.cn}: {str(e)}")

    def add_members(self, userlist):
        """
        Shortcut to add all members from a given list

        :param userlist: List of valid cn
        """


        for user in userlist:
            self.add_member(user)

    def remove_members(self, userlist):
        """
        Shortcut to remove all members from a given list

        :param userlist: List of valid cn
        """

        for user in userlist:
            self.remove_member(user)


class LMNGroup(LMNGroupCommon):
    """
    Class to handle the Sophomorix Groups (saved under the OU Projects)
    """

    def __init__(self, cn, school='default-school'):
        super().__init__(cn, school=school)
        self._check_ou()

    def _check_ou(self):
        school_details = self.lr.get(f'/schools/{self.school}')
        BASE_OU = f"OU=LMNGroups,OU={self.school},{LDAP_CONTEXT}"
        if not school_details:
            raise Exception(f"School {self.school} was not found in ldap ! Failed to check {BASE_OU}")

        if not BASE_OU in self.lr.getval('/ou', 'dn', school=self.school):
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
