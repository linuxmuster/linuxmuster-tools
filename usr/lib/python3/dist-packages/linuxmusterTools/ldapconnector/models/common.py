import ldap
import json
from dataclasses import dataclass, asdict

def check_password(dn, password=''):
    if not dn:
        return False

    l = ldap.initialize("ldaps://localhost:636/")
    l.set_option(ldap.OPT_REFERRALS, 0)
    l.set_option(ldap.OPT_RESTART, ldap.OPT_ON)
    l.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
    l.protocol_version = ldap.VERSION3

    try:
        l.bind_s(dn, password)
        return True
    except ldap.INVALID_CREDENTIALS:
        return False

@dataclass
class LMNModel:
    """
    Common parent class to gather common methods.
    """

    def as_dict(self):
        return asdict(self)

    def as_json(self):
        return json.dumps(self.as_dict())

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
class LMNOUModel(LMNModel):
    distinguishedName: str
    dn: str
    name: str
    objectCategory: list
    objectClass: list
    ou: str

    def __post_init__(self):
        self.dn = self.distinguishedName

@dataclass
class LMNGPOModel(LMNModel):
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
