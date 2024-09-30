from configparser import ConfigParser
from configobj import ConfigObj
from subprocess import check_output
from io import StringIO

from .samba_tool import *
from .drives import *
from .dns import *


# Load samba domain
smbconf = ConfigParser()
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
    logging.warning('Config file /etc/samba/smb.conf not found')

try:
    smbconf.read('/etc/samba/smb.conf')
    LOG_LEVEL = parse_log_level(smbconf["global"].get("log level", ""))
    SAMBA_REALM = smbconf["global"]["realm"].lower()
    SAMBA_WORKGROUP = smbconf["global"]["workgroup"]
    SAMBA_NETBIOS = smbconf["global"]["netbios name"].lower()
    SAMBA_DOMAIN = f'{SAMBA_NETBIOS}.{SAMBA_REALM}'
except Exception as e:
    logging.error(f"Can not read realm and domain from smb.conf: {str(e)}")

DFS = {}

config = ConfigObj(StringIO(check_output(["/usr/bin/net", "conf", "list"], shell=False).decode()))
for share_name, share_config in config.items():
    # DFS activated ?
    if share_config.get('msdfs root', 'no') == 'yes':
        dfs_proxy = share_config.get('msdfs proxy', '')
        if dfs_proxy != '':
            # //sub.domain.lan/school to \\\\sub.domain.lan\\school
            DFS[share_name] = {
                'dfs_proxy': dfs_proxy.replace('/', '\\'),
            }
