from dataclasses import dataclass

@dataclass
class LMNSchoolModel:
    # TODO: should it be a OU or a CN ?

    objectClass: list
    ou: str
    displayName: str
    distinguishedName: str