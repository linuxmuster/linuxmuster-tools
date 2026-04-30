from dataclasses import dataclass
from ..urls import router as lr


@dataclass
class LMNSessionModel:
    sid: str
    name: str
    members: list
    membersCount: int

    def get_first_passwords(self):
        response = {}

        for member in self.members:
            lmnuser = lr.get(f'/users/{member}', as_dict=False)
            response[member] = {
                'firstPassword': lmnuser.sophomorixFirstPassword,
                'firstPasswordStillSet': lmnuser.test_first_password(),
            }
        return response

    def __str__(self):
        return f"{self.sid};{self.name};{','.join(self.members)};"
