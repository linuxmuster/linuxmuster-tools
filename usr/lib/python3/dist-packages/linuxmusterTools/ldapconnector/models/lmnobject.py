from dataclasses import dataclass, field


@dataclass
class LMNObject:
    """
    Common minimalistic object for global search queries.
    """

    cn: str
    description: str
    displayName: str
    distinguishedName: str
    givenName: str
    mail: str
    objectClass: list
    sAMAccountName: str
    sAMAccountType: str
    sn: str
    sophomorixAddMailQuota: str
    sophomorixAddQuota: list
    sophomorixCreationDate: str
    sophomorixHidden: bool
    sophomorixJoinable: bool
    sophomorixMailAlias: bool
    sophomorixMailList: bool
    sophomorixMailQuota: str
    sophomorixQuota: str
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixStatus: str
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