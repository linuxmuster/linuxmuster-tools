from dataclasses import dataclass, field
import os
import re
import ldap
from .lmnsession import LMNSession
from .common import LMNParent

from linuxmusterTools.lmnfile import LMNFile

try:
    from aj.plugins.lmn_common.api import ldap_config as params
    webui_import = True
except ImportError as e:
    webui_import = False


@dataclass
class LMNUser(LMNParent):
    cn: str
    displayName: str
    distinguishedName: str
    givenName: str
    homeDirectory: str
    homeDrive: str
    mail: list
    memberOf: list
    name: str
    objectClass: list
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
    sophomorixIntrinsic2: list
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
    unixHomeDirectory: str
    whenChanged: str
    dn:             str  = field(init=False)
    customFields:   dict  = field(init=False)
    examMode:       bool = field(init=False)
    examTeacher:    str  = field(init=False)
    examBaseCn:     str  = field(init=False)
    internet:       bool = field(init=False)
    intranet:       bool = field(init=False)
    isAdmin:        bool = field(init=False)
    lmnsessions:    list = field(init=False)
    permissions:    list = field(init=False)
    printers:       list = field(init=False)
    printing:       bool = field(init=False)
    projects:       list = field(init=False)
    schoolclasses:  list = field(init=False)
    school:         str  = field(init=False)
    webfilter:      bool = field(init=False)
    wifi:           bool = field(init=False)

    def split_dn(self, dn):
        # 'CN=11c,OU=11c,OU=Students,OU=default-school,OU=SCHOOLS...' becomes :
        # [['CN', '11c'], ['OU', '11c'], ['OU', 'Students'],...]
        return [node.split("=") for node in dn.split(',')]

    def common_name(self, dn):
        try:
            # [['CN', '11c'], ['OU', '11c'], ['OU', 'Students'],...]
            return self.split_dn(dn)[0][1]
        except KeyError:
            return ''

    @staticmethod
    def _check_schoolclass_number(s):
        n = re.findall(r'\d+', s)
        if n:
            return int(n[0])
        else:
            return 10000000 # just a big number to come after all schoolclasses

    def extract_schoolclasses(self, membership):
        schoolclasses = []
        for dn in membership:
            if 'OU=Students' in dn:
                schoolclass = self.common_name(dn)
                if schoolclass:
                    schoolclasses.append(schoolclass)
        schoolclasses = sorted(schoolclasses, key=lambda s: (self._check_schoolclass_number(s), s))
        return schoolclasses

    def extract_projects(self, membership):
        projects = []
        for dn in membership:
            if 'OU=Projects' in dn:
                project = self.common_name(dn)
                if project:
                    projects.append(project)
        projects.sort()
        return projects

    def extract_printers(self, membership):
        printers = []
        for dn in membership:
            if 'OU=printer-groups' in dn:
                printer = self.common_name(dn)
                if printer:
                    printers.append(printer)
        printers.sort()
        return printers

    def extract_management(self):
        school_prefix = ""
        if self.sophomorixSchoolname != 'default-school':
            school_prefix = f"{self.sophomorixSchoolname}-"

        for group in ['internet', 'intranet', 'printing', 'webfilter', 'wifi']:
            setattr(self, group, False)
            for dn in self.memberOf:
                if dn.startswith(f"CN={school_prefix}{group},OU=Management"):
                    setattr(self, group, True)

    def parse_permissions(self):
        self.permissions = {}

        for perm in self.sophomorixWebuiPermissionsCalculated:
            module, value = perm.split(': ')
            self.permissions[module] = value == 'true'

    def parse_sessions(self):
        self.lmnsessions = []
        for v in self.sophomorixSessions:
            data = v.split(';')
            members = data[2].split(',') if data[2] else []
            membersCount = len(members)
            self.lmnsessions.append(LMNSession(data[0], data[1], members, membersCount))

    def parse_exam(self):
        if not self.sophomorixExamMode:
            self.examMode = False
            self.examTeacher = ''
            self.examBaseCn = ''
        elif self.sophomorixExamMode[0] == '---':
            self.examMode = False
            self.examTeacher = ''
            self.examBaseCn = ''
        else:
            self.examMode = True
            self.examTeacher = self.sophomorixExamMode[0]
            self.examBaseCn = self.cn.replace('-exam', '')

    def create_custom_fields_objects(self):
        custom_config_path = f'/etc/linuxmuster/sophomorix/{self.school}/custom_fields.yml'
        custom_config = {}
        if os.path.isfile(custom_config_path):
            with LMNFile(custom_config_path, 'r') as config:
                custom_config = config.read()

        self.customFields = {}

        proxy_add = custom_config.get('proxyAddresses', {}).get(self.sophomorixRole, {'editable': False, 'show': False, 'title':''})
        self.customFields['proxyAddresses'] = {
            'title': proxy_add['title'],
            'canRead': proxy_add['show'],
            'canWrite': proxy_add['editable'],
            'value': self.proxyAddresses
        }

        for i in range(1, 5):
            config = custom_config.get('custom', {}).get(self.sophomorixRole, {}).get(str(i), {'editable': False, 'show': False, 'title':''})
            self.customFields[f"sophomorixCustom{i}"] = {
                'title': config['title'],
                'canRead': config['show'],
                'canWrite': config['editable'],
                'value': getattr(self, f"sophomorixCustom{i}")
            }

        for i in range(1, 5):
            config = custom_config.get('customMulti', {}).get(self.sophomorixRole, {}).get(str(i), {'editable': False, 'show': False, 'title': ''})
            self.customFields[f"sophomorixCustomMulti{i}"] = {
                'title': config['title'],
                'canRead': config['show'],
                'canWrite': config['editable'],
                'value': getattr(self, f"sophomorixCustomMulti{i}")
            }

    def __post_init__(self):
        self.schoolclasses = self.extract_schoolclasses(self.memberOf)
        self.projects = self.extract_projects(self.memberOf)
        self.printers = self.extract_printers(self.memberOf)
        self.dn = self.distinguishedName
        self.school = self.sophomorixSchoolname
        self.extract_management()
        self.parse_permissions()
        self.parse_sessions()
        self.parse_exam()

        if not webui_import:
            self.create_custom_fields_objects()
        else:
            self.customFields = {}


        self.isAdmin = "administrator" in self.sophomorixRole

    def test_password(self, password=''):
        if not self.dn:
            return False

        l = ldap.initialize("ldap://localhost:389/")
        l.set_option(ldap.OPT_REFERRALS, 0)
        l.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
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

