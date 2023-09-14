from dataclasses import dataclass, field


@dataclass
class LMNGroup:
    cn: str
    displayName: str
    distinguishedName: str
    memberOf: list
    name: str
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAdminClass: str
    sophomorixCreationDate: str
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixStatus: str
    sophomorixType: str
