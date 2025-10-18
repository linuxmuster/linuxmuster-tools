from dataclasses import dataclass, field
from .common import LMNModel


@dataclass
class LMNObjectModel(LMNModel):
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
    sophomorixJoinable: bool
    sophomorixMailAlias: bool
    sophomorixMailList: bool
    sophomorixMailQuotaCalculated: list
    sophomorixMailQuota: list
    sophomorixMaxMembers: int
    sophomorixMemberGroups: list
    sophomorixMembers: list
    sophomorixQuota: list
    sophomorixRole: str
    sophomorixRoomComputers: list
    sophomorixRoomIPs: list
    sophomorixRoomMACs: list
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

    def get_type(self):

        ## OU
        if self.dn.startswith('OU='):
            return 'Organizational Unit'



        ## Schoolclasses
        if self.sophomorixType == 'adminclass':
            return 'schoolclass'
        elif self.sophomorixType == 'adminclass-parents':
            return 'parents'
        elif self.sophomorixType == 'adminclass-teachers':
            return 'teachers'
        elif self.sophomorixType == 'adminclass-students':
            return 'students'


        ## Staff
        if self.dn.startswith(f'CN={self.cn},OU={self.cn},OU=Staff'):
            return 'ADGroup Staff'

        objtypes = ['Devices', 'Teachers', 'Projects', 'Students', 'Parents', 'Staff']
        for objtype in objtypes:
            if self.dn.startswith(f'CN={objtype.lower()},OU={objtype},'):
                return f'{objtype.lower()}' if objtype != 'Staff' else 'staffmembers'

            if f'OU={objtype},' in self.dn:
                return objtype.lower()[:-1] if objtype != 'Staff' else 'staff'

        return 'unknown'

    def __post_init__(self):
        self.dn = self.distinguishedName
        self.type = self.get_type()
