from dataclasses import dataclass, field
from datetime import datetime
from typing import List
import ldap
import re

@dataclass
class LMNDevice:
    cn: str
    displayName: str
    distinguishedName: str
    memberOf: list
    name: str
    proxyAddresses: list
    sAMAccountName: str
    sAMAccountType: str
    sophomorixAdminClass: str
    sophomorixAdminFile: str
    sophomorixComment: str
    sophomorixComputerIP: str
    sophomorixComputerMAC: str
    sophomorixComputerRoom: str
    sophomorixCreationDate: str
    sophomorixRole: str
    sophomorixSchoolname: str
    sophomorixSchoolPrefix: str
    sophomorixStatus: str
