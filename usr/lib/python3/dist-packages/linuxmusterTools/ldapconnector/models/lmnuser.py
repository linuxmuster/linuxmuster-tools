from dataclasses import dataclass, field, InitVar
import ldap
from ..urls import router as lr
from .common import LMNModel
from .lmnusermixin import LMNUserMixin

from linuxmusterTools.common import WEBUI_IMPORT


@dataclass
class LMNUserModel(LMNUserMixin, LMNModel):
    cn: str
    custom_fields_config: InitVar[dict]
    displayName: str
    distinguishedName: str
    givenName: str
    homeDirectory: str
    homeDrive: str
    mail: list
    memberOf: list
    name: str
    objectClass: list
    preferredLanguage: str
    proxyAddresses: list
    sAMAccountName: str
    sAMAccountType: str
    sn: str
    sophomorixAdminClass: str
    sophomorixAdminFile: str
    sophomorixBirthdate: str
    sophomorixCloudQuotaCalculated: list
    sophomorixComment: str
    sophomorixCreationDate: str # datetime
    sophomorixCustom1: str
    sophomorixCustom2: str
    sophomorixCustom3: str
    sophomorixCustom4: str
    sophomorixCustom5: str
    sophomorixCustomMulti1: list
    sophomorixCustomMulti2: list
    sophomorixCustomMulti3: list
    sophomorixCustomMulti4: list
    sophomorixCustomMulti5: list
    sophomorixDeactivationDate: str # datetime
    sophomorixExamMode: list
    sophomorixExitAdminClass: str
    sophomorixFirstnameASCII: str
    sophomorixFirstnameInitial: str
    sophomorixFirstPassword: str
    sophomorixIntrinsic1: str
    sophomorixIntrinsic2: str
    sophomorixIntrinsic3: str
    sophomorixIntrinsic4: str
    sophomorixIntrinsic5: str
    sophomorixIntrinsicMulti1: list
    sophomorixIntrinsicMulti2: list
    sophomorixIntrinsicMulti3: list
    sophomorixIntrinsicMulti4: list
    sophomorixIntrinsicMulti5: list
    sophomorixMailQuotaCalculated: list
    sophomorixMailQuota: list
    sophomorixQuota: list
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixSessions: list
    sophomorixStatus: str
    sophomorixSurnameASCII: str
    sophomorixSurnameInitial: str
    sophomorixTolerationDate: str # datetime
    sophomorixUnid: str
    sophomorixUserToken: str
    sophomorixWebuiDashboard: list
    sophomorixWebuiPermissionsCalculated: list
    thumbnailPhoto: str
    unixHomeDirectory: str
    userAccountControl: int
    whenChanged: str
    dn:             str  = field(init=False)
    children:       dict = field(init=False)
    customFields:   dict = field(init=False)
    examMode:       bool = field(init=False)
    examTeacher:    str  = field(init=False)
    examBaseCn:     str  = field(init=False)
    internet:       bool = field(init=False)
    intranet:       bool = field(init=False)
    isAdmin:        bool = field(init=False)
    lmnsessions:    list = field(init=False)
    parents:        list = field(init=False)
    permissions:    list = field(init=False)
    printers:       list = field(init=False)
    printing:       bool = field(init=False)
    projects:       list = field(init=False)
    schoolclasses:  list = field(init=False)
    school:         str  = field(init=False)
    webfilter:      bool = field(init=False)
    wifi:           bool = field(init=False)

    def parse_permissions(self):
        self.permissions = {}

        for perm in self.sophomorixWebuiPermissionsCalculated:
            module, value = perm.split(': ')
            self.permissions[module] = value == 'true'

    def get_parents(self):
        self.parents = []
        if self.sophomorixRole == 'student':
            parents_group = lr.getval(f'/units/{self.cn}-parents', 'member', school=self.school) or []
            self.parents = [dn.split(',')[0].split('=')[1]
                for dn in parents_group
            ]

    def get_children(self):
        self.children = []
        if self.sophomorixRole != 'student':
            memberships = [m for m in self.memberOf if 'Student-Parents' in m]
            self.children = [
                m.split(',')[0].split('=')[1].replace('-parents', '')
                for m in memberships
            ]

    def __post_init__(self, custom_fields_config={}):
        self.schoolclasses = self.extract_schoolclasses(self.memberOf)
        self.projects = self.extract_projects(self.memberOf)
        self.printers = self.extract_printers(self.memberOf)
        self.dn = self.distinguishedName
        self.school = self.sophomorixSchoolname
        self.extract_management()
        self.parse_permissions()
        self.parse_sessions()
        self.parse_exam()
        self.get_children()
        self.get_parents()

        if not WEBUI_IMPORT:
            self.create_custom_fields_objects(custom_fields_config)
        else:
            self.customFields = {}


        self.isAdmin = "administrator" in self.sophomorixRole

    def test_password(self, password=''):
        if not self.dn:
            return False

        l = ldap.initialize("ldaps://localhost:636/")
        l.set_option(ldap.OPT_REFERRALS, 0)
        l.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
        l.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
        l.protocol_version = ldap.VERSION3

        try:
            l.bind_s(self.dn, password)
            return True
        except ldap.INVALID_CREDENTIALS:
            return False

    def test_first_password(self):
        if self.sophomorixFirstPassword:
            return self.test_password(self.sophomorixFirstPassword)
        return 'Insufficient permissions to read first password from LDAP.'

