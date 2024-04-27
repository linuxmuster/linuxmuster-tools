from dataclasses import dataclass, field


@dataclass
class LMNGroup:
    cn: str
    displayName: str
    distinguishedName: str
    member: list
    memberOf: list
    name: str
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAdminClass: str
    sophomorixCreationDate: str
    sophomorixHidden: bool
    sophomorixJoinable: bool
    sophomorixMembers: list
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixStatus: str
    sophomorixType: str
