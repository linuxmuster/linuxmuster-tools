import logging

from ..ldap_writer import LdapWriter
from ..urls.ldaprouter import router
from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNSchoolClassModel


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNSchoolclass:

    def __init__(self, cn):

        # TODO if new is enabled
        # if not name_checker.check_login_name(cn):
        #     raise Exception(f"{cn} is not a valid CN")

        self.cn = cn
        self.lw = LdapWriter()
        self.lr = router
        self.model = LMNSchoolClassModel
        self.data = {}
        self.load_data()

    def load_data(self):
        self.data = self.lr.get(f'/schoolclasses/{self.cn}')

        if not self.data:
            raise Exception(f"The schoolclass {self.cn} was not found in ldap.")

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