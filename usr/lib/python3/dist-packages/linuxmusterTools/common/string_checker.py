import re
import logging
from functools import partialmethod


STRING_RULES = {
    'password': re.compile(r"^[a-zA-Z0-9?!@#§+\-$%&*{}()\]\[]+$"),
    'strong_password': re.compile(r"(?=.*[a-z])(?=.*[A-Z])(?=.*[?!@#§+\-$%&*{}()]|(?=.*\d)).{7,}"),
    'project': re.compile(r"^[a-z0-9_\-]*$"),
    "session": re.compile(r"^[a-z0-9\+\-_]*$", re.IGNORECASE),
    "linbo_conf": re.compile(r"^[a-z0-9\+\-_]*$", re.IGNORECASE),
    "linbo_image": re.compile(r"^[a-zA-Z0-9_\-]+$"),
    "login": re.compile(r"^[a-z0-9\-_]*$", re.IGNORECASE),
    "comment": re.compile(r"^[a-z0-9\-_ ]*", re.IGNORECASE), # sophomorixComment
    "alphanum": re.compile(r"^[a-z0-9]*$", re.IGNORECASE),   # config names
    "number": re.compile(r"^([0-9]*)$"),
    "date": re.compile(r"^([1-9]|0[1-9]|[12][0-9]|3[01])[.]([1-9]|0[1-9]|1[012])[.](19|20)\d\d$", re.IGNORECASE),
    "ip": re.compile(r"^(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[1-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[1-9])$"),
    "mac1": re.compile(r"^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$"), # Colon separated mac
    "mac2": re.compile(r"^([0-9A-Fa-f]{2}[-]){5}([0-9A-Fa-f]{2})$"), # Hyphen separated mac
    "mac3": re.compile(r"^[0-9A-Fa-f]{12}$"),                        # Mac without separation
    "host": re.compile(r"^[a-zA-Z0-9\-]+$"),
    "room": re.compile(r"^[a-zA-Z0-9\-]+$"),
    "domain": re.compile(r"^[a-zA-Z0-9\-.]*$"),
}

# Bad hardcoded list, should be read in ldap or from a config file
ROLES = [
    'switch',
    'addc',
    'wlan',
    'staffcomputer',
    'mobile',
    'printer',
    'classroom-teachercomputer',
    'server',
    'iponly',
    'faculty-teachercomputer',
    'voip',
    'byod',
    'classroom-studentcomputer',
    'thinclient',
    'router'
]

def set_check_method(cls, *args):
    for string_type in STRING_RULES:
        setattr(cls, f"check_{string_type}", partialmethod(cls.check, string_type))
    return cls

@set_check_method
class StringChecker:

    def check(self, string_type, string):
        pattern = STRING_RULES.get(string_type, None)
        if pattern:
            return re.match(pattern, string) is not None
        return False

    def check_role(self, role):
        return role in ROLES

    def normalize_mac(self, mac):
        # TODO: all upper ?
        if self.check_mac1(mac):
            return mac
        elif self.check_mac2(mac):
            return mac.replace("-", ":")
        elif self.check_mac3(mac):
            return ":".join(re.findall(r"..", mac))
        logging.warning(f"Mac addresse {mac} does not correspond to any valid mac address.")
        return None


