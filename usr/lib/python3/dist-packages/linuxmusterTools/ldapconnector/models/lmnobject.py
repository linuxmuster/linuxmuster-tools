from dataclasses import dataclass, field


@dataclass
class LMNObject:
    """
    Common minimalistic object for global search queries.
    """

    cn: str
    distinguishedName: str
    sAMAccountName: str
    sAMAccountType: str
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
        objtypes = ['Devices', 'Teachers', 'Projects']
        for objtype in objtypes:
            if f'OU={objtype},' in self.dn:
                return objtype.lower()[:-1]

        if f'OU=Students,' in self.dn:
            splitted_dn = self.split_dn()
            if splitted_dn[0][1] == splitted_dn[1][1]:
                return 'schoolclass'
            return 'student'

        return 'unknown'

    def __post_init__(self):
        self.dn = self.distinguishedName
        self.type = self.get_type()