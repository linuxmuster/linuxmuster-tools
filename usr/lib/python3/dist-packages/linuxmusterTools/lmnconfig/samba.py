import logging
import os
from configparser import ConfigParser
from configobj import ConfigObj
from subprocess import check_output
from io import StringIO


logger = logging.getLogger(__name__)

# Load samba domain
smbconf = ConfigParser(delimiters=("=",))
SAMBA_DOMAIN, SAMBA_REALM, SAMBA_NETBIOS, SAMBA_WORKGROUP = [''] * 4
SAMBA_TLD, LDAP_CONTEXT = [''] * 2

def parse_log_level(level):
    """
    A level entry should look like one of these::

        log level = auth_audit:2
        log level = 2
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
    # TODO: use smb.conf or the output of testparm -sv ?
    smbconf.read('/etc/samba/smb.conf')
    LOG_LEVEL = parse_log_level(smbconf["global"].get("log level", ""))
    SAMBA_REALM = smbconf["global"]["realm"].lower()
    SAMBA_WORKGROUP = smbconf["global"]["workgroup"]
    SAMBA_NETBIOS = smbconf["global"]["netbios name"].lower()
    SAMBA_DOMAIN = f'{SAMBA_NETBIOS}.{SAMBA_REALM}'
    SAMBA_TLD = SAMBA_REALM.split('.')[-1].upper()

    # fandom.example.org --> 'DC=FANDOM,DC=EXAMPLE,DC=ORG'
    LDAP_DC = ','.join([f"DC={comp}" for comp in SAMBA_REALM.upper().split(".") if comp])
    LDAP_CONTEXT = f"OU=SCHOOLS,{LDAP_DC}"

except Exception as e:
    logger.error(f"Can not read realm and domain from smb.conf: {str(e)}. Is linuxmuster.net installed and configured ?")

DFS = {}
SHARES_LIST = []

def load_shares():
    """
    Read the shares and their DFS targets from 'net conf list' into
    SHARES_LIST and DFS. Both are filled in place, so that every module which
    imported them sees a reload.

    Done once at import: a long running process like linuxmuster-api keeps
    the shares it found at start. Call it again after a share has been moved
    to a fileserver (DFS).
    """

    config = ConfigObj(StringIO(check_output(["/usr/bin/net", "conf", "list"], shell=False).decode()))

    SHARES_LIST[:] = config.keys()
    DFS.clear()

    for share_name, share_config in config.items():
        # DFS activated ?
        if share_config.get('msdfs root', 'no') == 'yes':
            dfs_proxy = share_config.get('msdfs proxy', '')
            if dfs_proxy != '':
                # //sub.domain.lan/school to \\\\sub.domain.lan\\school
                DFS[share_name] = {
                    'dfs_proxy': dfs_proxy.replace('/', '\\'),
                }

load_shares()
