import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
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
                logging.info(f"{user} is not a member of schoolclass {self.cn}")
                return
            self.lw._setattr(self, data={'member': members})
        except ValueError as e:
            logger.warning(f"Could not remove member {user_dn} from {self.cn}: {str(e)}")

    def add_member(self, user):
        user_dn = self.lr.getval(f'/users/{user}', 'dn')

        if not user_dn:
            logger.info(f"The user {user} was not found in ldap.")
            raise Exception(f"The user {user} was not found in ldap.")

        try:
            members = self.data['member']
            members.append(user_dn)
            self.lw._setattr(self, data={'member': members})
        except Exception as e:
            logger.warning(f"Could not append member {user_dn} to {self.cn}: {str(e)}")


class LMNGroup(LMNGroupCommon):
    """
    Class to handle the Sophomorix Groups (saved under the OU Projects)
    """

    def __init__(self, cn, school='default-school'):
        super().__init__(cn, school=school)

    def load_data(self):
        self.data = self.lr.get(f'/groups/{self.cn}', school=self.school)

        if not self.data:
            raise Exception(f"The group {self.cn} was not found in ldap.")
