import re
from .lmnsession import LMNSessionModel
from linuxmusterTools.common import WEBUI_IMPORT


class LMNUserMixin:
    """
    Methods shared between LMNUserModel and LMNRawUserModel.
    """


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
            if 'OU=Students' in dn \
                and '-teachers,' not in dn \
                and '-parents,' not in dn \
                and '-students,' not in dn:
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

    def parse_sessions(self):
        self.lmnsessions = []
        for v in self.sophomorixSessions:
            data = v.split(';')
            members = data[2].split(',') if data[2] else []
            membersCount = len(members)
            self.lmnsessions.append(LMNSessionModel(data[0], data[1], members, membersCount))

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

    def create_custom_fields_objects(self, custom_config={}):
        self.customFields = {}

        # custom_fields.yml keys roles in the plural (students, teachers, ...)
        # while sophomorixRole is singular (student, teacher, ...).
        role = f"{self.sophomorixRole}s"

        proxy_add = custom_config.get('proxyAddresses', {}).get(role, {'editable': False, 'show': False, 'title':''})
        self.customFields['proxyAddresses'] = {
            'title': proxy_add['title'],
            'canRead': proxy_add['show'],
            'canWrite': proxy_add['editable'],
            'value': self.proxyAddresses
        }

        for i in range(1, 6):
            config = custom_config.get('custom', {}).get(role, {}).get(str(i), {'editable': False, 'show': False, 'title':''})
            self.customFields[f"sophomorixCustom{i}"] = {
                'title': config['title'],
                'canRead': config['show'],
                'canWrite': config['editable'],
                'value': getattr(self, f"sophomorixCustom{i}")
            }

        for i in range(1, 6):
            config = custom_config.get('customMulti', {}).get(role, {}).get(str(i), {'editable': False, 'show': False, 'title': ''})
            self.customFields[f"sophomorixCustomMulti{i}"] = {
                'title': config['title'],
                'canRead': config['show'],
                'canWrite': config['editable'],
                'value': getattr(self, f"sophomorixCustomMulti{i}")
            }
