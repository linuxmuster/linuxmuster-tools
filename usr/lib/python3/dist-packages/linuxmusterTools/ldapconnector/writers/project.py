import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNProjectModel
from .group import LMNGroupCommon


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNPrinter(LMNGroupCommon):

    def __init__(self, cn):
        super().__init__(cn)
        self.model = LMNProjectModel

    def load_data(self):
        self.data = self.lr.get(f'/projects/{self.cn}')

        if not self.data:
            raise Exception(f"The project {self.cn} was not found in ldap.")
