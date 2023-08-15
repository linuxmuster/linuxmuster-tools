import os
import logging
from dataclasses import dataclass
from samba.auth import system_session
from samba.credentials import Credentials
from samba.param import LoadParm
from samba.samdb import SamDB
from samba.netcmd.gpo import get_gpo_info

lp = LoadParm()
creds = Credentials()
creds.guess(lp)
gpos_infos = {}

SAMDB_PATH = '/var/lib/samba/private/sam.ldb'

@dataclass
class GPO:
    dn: str
    gpo: str
    name: str
    path: str
    unix_path: str

class GPOManager:
    """
    Sample object to manage all GPOs informations.
    """

    def __init__(self):
        if os.path.isfile(SAMDB_PATH):
            try:
                samdb = SamDB(url=SAMDB_PATH, session_info=system_session(),credentials=creds, lp=lp)
                gpos_infos = get_gpo_info(samdb, None)
            except Exception:
                logging.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ?')
        else:
            logging.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')
        
        self.gpos = {}
        
        for gpo in gpos_infos:
            gpo_id = gpo['name'][0].decode()
            name = gpo['displayName'][0].decode()
            path = gpo['gPCFileSysPath'][0].decode()
            unix_path = f"/var/lib/samba/sysvol/unpeud.info/Policies/{{{gpo_id[1:-1]}}}"
            self.gpos[name] = GPO(str(gpo.dn), gpo_id, name, path, unix_path)
