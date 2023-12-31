from configparser import ConfigParser
import logging
import os

from .samba_tool import *
from .drives import *
from .dns import *


# Load samba domain
smbconf = ConfigParser()
SAMBA_DOMAIN, SAMBA_REALM, SAMBA_NETBIOS, SAMBA_WORKGROUP = [''] * 4

if not os.path.isfile('/etc/samba/smb.conf'):
    logging.warning('Config file /etc/samba/smb.conf not found')

try:
    smbconf.read('/etc/samba/smb.conf')
    SAMBA_REALM = smbconf["global"]["realm"].lower()
    SAMBA_WORKGROUP = smbconf["global"]["workgroup"]
    SAMBA_NETBIOS = smbconf["global"]["netbios name"].lower()
    SAMBA_DOMAIN = f'{SAMBA_NETBIOS}.{SAMBA_REALM}'
except Exception as e:
    logging.error(f"Can not read realm and domain from smb.conf: {str(e)}")