from dataclasses import dataclass, field
from datetime import datetime
from ..urls import router as lr


@dataclass
class LMNSchoolClass:
    cn: str
    description: str
    distinguishedName: str
    mail: list
    member: list
    memberOf: list
    name: str
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAddMailQuota: list
    sophomorixAddQuota: list
    sophomorixAdmins: list
    sophomorixCreationDate: str # datetime
    sophomorixHidden: bool
    sophomorixJoinable: bool
    sophomorixMailAlias: list
    sophomorixMailList: list
    sophomorixMailQuota: list
    sophomorixMaxMembers: int
    sophomorixMembers: list
    sophomorixQuota: list
    sophomorixSchoolname: str
    sophomorixStatus: str
    sophomorixType: str
    membersCount: int = field(init=False)
    dn: str = field(init=False)

    def __post_init__(self):
        self.dn = self.distinguishedName
        self.membersCount = len(self.sophomorixMembers)

    def get_first_passwords(self):
        response = {}

        for student in self.sophomorixMembers:
            lmnuser = lr.get(f'/users/{student}', dict=False)
            response[student] = {
                'firstPassword': lmnuser.sophomorixFirstPassword,
                'firstPasswordStillSet': lmnuser.test_first_password(),
            }
        return response