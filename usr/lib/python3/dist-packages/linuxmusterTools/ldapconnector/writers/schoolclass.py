import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNSchoolClassModel
from .group import LMNGroupCommon


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNSchoolclassGroup(LMNGroupCommon):

    def __init__(self, cn):
        super().__init__(cn)

    def load_data(self):
        self.data = self.lr.get(f'/units/{self.cn}')

        if not self.data:
            logging.warning(f"The group {self.cn} was not found in ldap.")

class LMNSchoolclass(LMNGroupCommon):

    def __init__(self, cn):
        super().__init__(cn)
        self.model = LMNSchoolClassModel
        self.students_group = LMNSchoolclassGroup(f"{self.cn}-students")
        self.teachers_group = LMNSchoolclassGroup(f"{self.cn}-teachers")
        self.parents_group = LMNSchoolclassGroup(f"{self.cn}-parents")

    def load_data(self):
        self.data = self.lr.get(f'/schoolclasses/{self.cn}')

        if not self.data:
            raise Exception(f"The schoolclass {self.cn} was not found in ldap.")