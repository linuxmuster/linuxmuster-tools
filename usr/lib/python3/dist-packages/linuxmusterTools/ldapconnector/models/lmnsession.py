from dataclasses import dataclass
from datetime import datetime
from ..urls import router as lr


@dataclass
class LMNSession:
    sid: str
    name: str
    members: list
    membersCount: int

    def get_first_passwords(self):
        response = {}

        for member in self.members:
            lmnuser = lr.get(f'/users/{member}', dict=False)
            response[member] = {
                'firstPassword': lmnuser.sophomorixFirstPassword,
                'firstPasswordStillSet': lmnuser.test_first_password(),
            }
        return response
