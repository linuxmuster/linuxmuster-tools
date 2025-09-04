import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from .group import LMNGroupCommon


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNPrinter(LMNGroupCommon):

    def __init__(self, cn, school='default-school'):
        super().__init__(cn, school=school)

    def load_data(self):
        self.data = self.lr.get(f'/printers/{self.cn}', school=self.school)

        if not self.data:
            raise Exception(f"The printer {self.cn} was not found in ldap.")
