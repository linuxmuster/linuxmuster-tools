from configobj import ConfigObj
from subprocess import check_output
from io import StringIO

from ..lmnconfig.samba import *
from .samba_tool import *
from .drives import *
from .dns import *


DFS = {}

config = ConfigObj(StringIO(check_output(["/usr/bin/net", "conf", "list"], shell=False).decode()))

SHARES_LIST = list(config.keys())

for share_name, share_config in config.items():
    # DFS activated ?
    if share_config.get('msdfs root', 'no') == 'yes':
        dfs_proxy = share_config.get('msdfs proxy', '')
        if dfs_proxy != '':
            # //sub.domain.lan/school to \\\\sub.domain.lan\\school
            DFS[share_name] = {
                'dfs_proxy': dfs_proxy.replace('/', '\\'),
            }
