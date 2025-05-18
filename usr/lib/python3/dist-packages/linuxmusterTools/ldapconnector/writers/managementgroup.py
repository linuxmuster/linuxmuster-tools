import logging

from .group import LMNGroupCommon


logger = logging.getLogger(__name__)

class LMNMgmtGroup(LMNGroupCommon):
    """
    Class to handle the management groups
    """

    def __init__(self, cn):
        super().__init__(cn)

    def load_data(self):
        self.data = self.lr.get(f'/managementgroups/{self.cn}')

        if not self.data:
            raise Exception(f"The group {self.cn} was not found in ldap.")
