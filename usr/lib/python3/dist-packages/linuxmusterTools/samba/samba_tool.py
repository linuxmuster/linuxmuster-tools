import os
import logging
from dataclasses import dataclass, field, asdict
from .drives import DriveManager


try:
    from samba.auth import system_session
    from samba.credentials import Credentials
    from samba.param import LoadParm
    from samba.samdb import SamDB
    from samba.netcmd.gpo import get_gpo_info

    lp = LoadParm()
    creds = Credentials()
    creds.guess(lp)
except ImportError as e:
    logging.error(f"Samba doesn't seem to be installed, this module can not be used: {str(e)}")

SAMDB_PATH = '/var/lib/samba/private/sam.ldb'

@dataclass
class GPO:
    dn: str
    drivemgr: DriveManager
    gpo: str
    name: str
    path: str
    unix_path: str

class GPOManager:
    """
    Sample object to manage all GPOs informations.
    """

    def __init__(self):

        gpos_infos = {}

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
            unix_path = "/var/lib/samba/" + '/'.join(path.split('\\')[3:])
            drivemgr = DriveManager(unix_path)
            self.gpos[name] = GPO(str(gpo.dn), drivemgr, gpo_id, name, path, unix_path)
