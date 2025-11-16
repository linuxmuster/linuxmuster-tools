import csv
from dataclasses import dataclass, field
from ..urls import router as lr
from .common import LMNModel


@dataclass
class LMNSchoolClassModel(LMNModel):
    cn: str
    description: str
    displayName: str
    distinguishedName: str
    mail: list
    member: list
    memberOf: list
    name: str
    objectClass: list
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAddMailQuota: list
    sophomorixAddQuota: list
    sophomorixAdmins: list
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
    sophomorixHidden: bool
    sophomorixJoinable: bool
    sophomorixMailAlias: bool
    sophomorixMailList: bool
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

    def students_csv(self):
        path = f"/var/lib/lmntools/print/{self.cn}_liste.csv"
        with open(path, 'w') as f:
            for idx,student in enumerate(self.sophomorixMembers):
                lmnuser = lr.get(f'/users/{student}', dict=False)
                f.write(f"{idx+1};{lmnuser.sn};{lmnuser.givenName}\n")
        return path
