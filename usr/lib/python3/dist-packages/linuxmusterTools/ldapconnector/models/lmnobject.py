from dataclasses import dataclass, field


@dataclass
class LMNObject:
    """
    Common linuxmuster.net object with all attributes for global search queries.
    """

    cn: str
    description: str
    displayName: str
    distinguishedName: str
    givenName: str
    homeDirectory: str
    homeDrive: str
    mail: list
    member: list
    memberOf: list
    name: str
    objectClass: list
    ou: str
    proxyAddresses: list
    sAMAccountName: str
    sAMAccountType: str
    sn: str
    sophomorixAddMailQuota: list
    sophomorixAddQuota: list
    sophomorixAdminClass: str
    sophomorixAdminFile: str
    sophomorixAdminGroups: list
    sophomorixAdmins: list
    sophomorixBirthdate: str
    sophomorixCloudQuotaCalculated: list
    sophomorixComment: str
    sophomorixComputerIP: str
    sophomorixComputerMAC: str
    sophomorixComputerRoom: str
    sophomorixCreationDate: str
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
    sophomorixHidden: bool
    sophomorixIntrinsic2: list
    sophomorixIntrinsicMulti1: list
    sophomorixJoinable: bool
    sophomorixMailAlias: bool
    sophomorixMailAlias: list
    sophomorixMailList: bool
    sophomorixMailList: list
    sophomorixMailQuotaCalculated: list
    sophomorixMailQuota: list
    sophomorixMaxMembers: int
    sophomorixMemberGroups: list
    sophomorixMembers: list
    sophomorixQuota: list
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixSessions: list
    sophomorixStatus: str
    sophomorixSurnameASCII: str
    sophomorixSurnameInitial: str
    sophomorixTolerationDate: str # datetime
    sophomorixType: str
    sophomorixUnid: str
    sophomorixUserToken: str
    sophomorixWebuiDashboard: list
    sophomorixWebuiPermissionsCalculated: list
    unixHomeDirectory: str
    whenChanged: str
    dn:   str = field(init=False)
    type: str = field(init=False)

    def split_dn(self):
        # 'CN=11c,OU=11c,OU=Students,OU=default-school,OU=SCHOOLS...' becomes :
        # [['CN', '11c'], ['OU', '11c'], ['OU', 'Students'],...]
        return [node.split("=") for node in self.dn.split(',')]

    def get_type(self):
        objtypes = ['Devices', 'Teachers', 'Projects', 'Students']
        for objtype in objtypes:
            if self.dn.startswith(f'CN={objtype.lower()},OU={objtype},'):
                return f'ADGroup {objtype}'

            if f'OU={objtype},' in self.dn:
                return objtype.lower()[:-1]

        return 'unknown'

    def __post_init__(self):
        self.dn = self.distinguishedName
        self.type = self.get_type()