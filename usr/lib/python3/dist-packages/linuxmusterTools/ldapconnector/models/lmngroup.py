from dataclasses import dataclass, asdict


@dataclass
class LMNGroup:
    cn: str
    description: str
    displayName: str
    distinguishedName: str
    member: list
    memberOf: list
    name: str
    objectClass: list
    proxyAddresses: list
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAdminClass: str
    sophomorixCreationDate: str
    sophomorixHidden: bool
    sophomorixIntrinsicMulti1: list
    sophomorixJoinable: bool
    sophomorixMembers: list
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixStatus: str
    sophomorixType: str

    def __post_init__(self):
        self.dn = self.distinguishedName
        self.all_members = []
        self.membersCount = -1

    def asdict(self):
        return asdict(self)
