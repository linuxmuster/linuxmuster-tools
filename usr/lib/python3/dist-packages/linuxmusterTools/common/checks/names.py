import re
import logging
from functools import partialmethod


logger = logging.getLogger(__name__)

NAME_RULES = {
    'password': re.compile(r"^[a-zA-Z0-9?!@#§+\-$%&*{}()\]\[]+$"),
    'strong_password': re.compile(r"(?=.*[a-z])(?=.*[A-Z])(?=.*[?!@#§+\-$%&*{}()\d]).{7,}"),
    'project': re.compile(r"^[a-z0-9_\-]*$"),
    'group': re.compile(r"^[a-z0-9_\-]*$"),
    "session": re.compile(r"^[a-z0-9\+\-_]*$", re.IGNORECASE),
    "linbo_conf": re.compile(r"^[a-z0-9\+\-_\.]*$", re.IGNORECASE),
    "linbo_image": re.compile(r"^[a-zA-Z0-9_\-\.]+$"),
    "login": re.compile(r"^[a-z0-9\-_\.]*$", re.IGNORECASE),
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

def set_check_method(cls, *args):
    for name_type in NAME_RULES:
        setattr(cls, f"check_{name_type}_name", partialmethod(cls.check, name_type))
    return cls

@set_check_method
class NameChecker:

    def check(self, name_type, string):
        # Wrong types and empty strings are not allowed.
        if not isinstance(string, str) or not string:
            return False

        # Avoid path transversal
        if "/" in string or "\\" in string or "\0" in string or ".." in string:
            return False

        pattern = NAME_RULES.get(name_type, None)
        if pattern:
            return re.match(pattern, string) is not None
        return False

    def normalize_mac(self, mac):
        """
        Return a mac address in the colon-format  AA:BB:CC:DD:EE:FF
        """


        if self.check_mac1_name(mac):
            return mac.upper()
        elif self.check_mac2_name(mac):
            return mac.replace("-", ":").upper()
        elif self.check_mac3_name(mac):
            return ":".join(re.findall(r"..", mac)).upper()
        else:
            # logger.warning(f"Mac address {mac} does not correspond to any valid mac address.")
            return None


