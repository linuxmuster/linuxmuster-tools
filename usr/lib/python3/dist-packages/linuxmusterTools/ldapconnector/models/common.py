import json
from dataclasses import dataclass, asdict


@dataclass
class LMNModel:
    """
    Common parent class to gather common methods.
    """

    def asdict(self):
        return asdict(self)

    def asjson(self):
        return json.dumps(self.asdict())

    @staticmethod
    def split_dn(dn):
        # 'CN=11c,OU=11c,OU=Students,OU=default-school,OU=SCHOOLS...' becomes :
        # [['CN', '11c'], ['OU', '11c'], ['OU', 'Students'],...]
        return [node.split("=") for node in dn.split(',')]

    def common_name(self, dn):
        try:
            # [['CN', '11c'], ['OU', '11c'], ['OU', 'Students'],...]
            return self.split_dn(dn)[0][1]
        except KeyError:
            return ''

@dataclass
class LMNOU(LMNModel):
    distinguishedName: str
    dn: str
    name: str
    objectCategory: list
    objectClass: list
    ou: str

    def __post_init__(self):
        self.dn = self.distinguishedName

@dataclass
class LMNGPO(LMNModel):
    cn: str
    distinguishedName: str
    displayName: str
    dn: str
    gPCFileSysPath: str
    name: str
    objectCategory: list
    objectClass: list

    def __post_init__(self):
        self.dn = self.distinguishedName