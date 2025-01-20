import logging
import os
from configparser import ConfigParser


logger = logging.getLogger(__name__)

# Load samba domain
smbconf = ConfigParser(delimiters=("=",))
SAMBA_DOMAIN, SAMBA_REALM, SAMBA_NETBIOS, SAMBA_WORKGROUP = [''] * 4

def parse_log_level(level):
    """
    A level entry should look like

        log level = auth_audit:2
    or
        log level = 2
    or
        log level = 1 auth_audit:3 winbind:5
    """

    log_level = {'general':1}
    entries = level.split()
    for entry in entries:
        if ':' not in entry:
            log_level["general"] = int(entry)
        else:
            key, value = entry.split(':')
            log_level[key] = int(value)

    return log_level

if not os.path.isfile('/etc/samba/smb.conf'):
    logger.warning('Config file /etc/samba/smb.conf not found')

try:
    smbconf.read('/etc/samba/smb.conf')
    LOG_LEVEL = parse_log_level(smbconf["global"].get("log level", ""))
    SAMBA_REALM = smbconf["global"]["realm"].lower()
    SAMBA_WORKGROUP = smbconf["global"]["workgroup"]
    SAMBA_NETBIOS = smbconf["global"]["netbios name"].lower()
    SAMBA_DOMAIN = f'{SAMBA_NETBIOS}.{SAMBA_REALM}'
    SAMBA_TLD = SAMBA_REALM.split('.')[-1].upper()
    LDAP_CONTEXT = f"OU=SCHOOLS,DC={SAMBA_WORKGROUP},DC={SAMBA_TLD}"
except Exception as e:
    logger.error(f"Can not read realm and domain from smb.conf: {str(e)}")