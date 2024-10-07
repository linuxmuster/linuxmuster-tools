from dataclasses import dataclass

@dataclass
class LMNSchool:
    # TODO: should it be a OU or a CN ?

    objectClass: list
    ou: str
    displayName: str
    distinguishedName: str