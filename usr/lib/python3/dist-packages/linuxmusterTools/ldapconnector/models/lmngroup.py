from dataclasses import dataclass, field


@dataclass
class LMNGroup:
    cn: str
    displayName: str
    distinguishedName: str
    member: list
    memberOf: list
    name: str
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
