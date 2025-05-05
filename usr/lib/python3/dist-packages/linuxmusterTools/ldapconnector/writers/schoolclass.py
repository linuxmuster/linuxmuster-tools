import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNSchoolClassModel
from .group import LMNGroupCommon


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNSchoolclass(LMNGroupCommon):

    def __init__(self, cn):
        super().__init__(cn)
        self.model = LMNSchoolClassModel

    def load_data(self):
        self.data = self.lr.get(f'/schoolclasses/{self.cn}')

        if not self.data:
            raise Exception(f"The schoolclass {self.cn} was not found in ldap.")