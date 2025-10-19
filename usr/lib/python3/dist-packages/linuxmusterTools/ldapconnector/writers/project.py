import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from ..models import LMNProjectModel
from .group import LMNGroupCommon
from ..urls.ldaprouter import router


logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LMNProject(LMNGroupCommon):

    def __init__(self, cn, school='default-school'):
        super().__init__(cn, school=school)
        self.model = LMNProjectModel

    def load_data(self):
        self.data = self.lr.get(f'/projects/{self.cn}', school=self.school)

        if not self.data:
            raise Exception(f"The project {self.cn} was not found in ldap.")

class LMNProjects:

    def __init__(self, school='default-school'):
        self.lr = router
        self.projects = {
            project['cn']: LMNProject(project['cn'], school=school)
            for project in self.lr.get('/projects', school=school)
        }

    def __len__(self):
        return len(self.projects)

    def keys(self):
        yield from self.projects.keys()

    def items(self):
        yield from self.projects.items()

    def __getitem__(self, project_cn):
        return self.projects[project_cn]
