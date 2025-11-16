import logging

from linuxmusterTools.common import lprint, spinner
from linuxmusterTools.common.checks import NameChecker
from linuxmusterTools.lmnconfig import LDAP_CONTEXT
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
            logging.info(f"The project {self.cn} was not found in ldap.")

            prefix = "p_"
            if self.school != "default-school":
                prefix = f"p_{self.school}-"

            dn = f"CN={prefix}{self.cn},OU=Projects,OU={self.school},{LDAP_CONTEXT}"

            logging.info(f"His DN would be {dn}. You can create it with the method .create.")

            self.data = {
                'description': self.cn,
                'displayName': self.cn,
                'distinguishedName': dn,
                'mail': [],
                'member': [],
                'name': self.cn,
                'sAMAccountName': self.cn,
                'sophomorixAddMailQuota': '---',
                'sophomorixAddQuota': '---',
                'sophomorixCreationDate': '',
                'sophomorixHidden': False,
                'sophomorixJoinable': False,
                'sophomorixMailAlias': False,
                'sophomorixMailList': False,
                'sophomorixMailQuota': '---:---:',
                'sophomorixQuota': [f'{self.school}:---:---:', 'linuxmuster-global:---:---:'],
                'sophomorixSchoolname': self.school,
                'sophomorixStatus': '',
                'sophomorixType': f"project",
            }

    def create(self):
        self.lw._add_group(self, data=self.data)

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
