import os
import string
import random
import logging
import subprocess
from dataclasses import dataclass, field, asdict
from .drives import DriveManager
from ..ldapconnector import LMNLdapReader as lr

try:
    from samba.auth import system_session
    from samba.credentials import Credentials
    from samba.param import LoadParm
    from samba.samdb import SamDB
    from samba.netcmd.gpo import get_gpo_info
    from ldb import LdbError

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

class GroupManager:
    """
    Samble class to manage samba groups via samba-tool.
    """

    def __init__(self, school='default-school'):
        self.POST_HOOK_DIR = '/etc/linuxmuster/tools/hooks/group-manager'
        self.school = school
        self.school_prefix = "" if self.school == 'default-school' else f"{school}-"

        if os.path.isfile(SAMDB_PATH):
            try:
                self.samdb = SamDB(url=SAMDB_PATH, session_info=system_session(),credentials=creds, lp=lp)
            except Exception:
                logging.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ?')
        else:
            logging.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')

    def _run_post_hook(self, action, group, members):
        """
        Runs alls the scripts located in self.POST_HOOK_DIR in alphanum order, passing 3 arguments:

        :param action: actually 'remove' or 'add'
        :type action: basestring
        :param group: group name
        :type group: basestring
        :param members: members list, will be given coma separated as argument
        :type members: list
        """

        for script in sorted(os.listdir(self.POST_HOOK_DIR)):
            print(f"Executing {os.path.join(self.POST_HOOK_DIR, script)}")
            subprocess.run([os.path.join(self.POST_HOOK_DIR, script), action, group, ','.join(members)])

    def list(self):
        raw_groups = lr.get('/groups', attributes=['cn', 'sophomorixType'], school=self.school)
        groups = {}

        for group in raw_groups:
            if group['sophomorixType'] not in groups:
                groups[group['sophomorixType']] = []
            groups[group['sophomorixType']].append(group['cn'])

        return groups

    def remove_members(self, group, members):
        """
        Remove members from a group. samdb throw an Exception if the group or the user
        does not exist.

        :param group: group name
        :type group: basestring
        :param members: members list
        :type members: list
        """

        self.samdb.add_remove_group_members(groupname=f"{self.school_prefix}{group}", members=members, add_members_operation=False)
        self._run_post_hook('remove', group, members)

    def add_members(self, group, members):
        """
        Add members to a group. samdb throw an Exception if the group or the user
        does not exist.

        :param group: group name
        :type group: basestring
        :param members: members list
        :type members: list
        """

        for member in members:
            try:
                self.samdb.add_remove_group_members(groupname=f"{self.school_prefix}{group}", members=[member], add_members_operation=True)
            except Exception as e:
                if "(68," in str(e):
                    # Attribute member already exists for target GUID ... already in group, passing error
                    pass

        self._run_post_hook('add', group, members)

class UserManager:
    """
    Sample class to manage samba users via samba-tool.
    """

    def __init__(self):
        self.POST_HOOK_DIR = '/etc/linuxmuster/tools/hooks/user-manager'

        if os.path.isfile(SAMDB_PATH):
            try:
                self.samdb = SamDB(url=SAMDB_PATH, session_info=system_session(),credentials=creds, lp=lp)
            except Exception:
                logging.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ?')
        else:
            logging.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')

    def _check_password_strength(self, password):
        """
        Passwords must contain at least one lowercase, one uppercase, one special char or number, and at least 7 chars.
        """

        regexp = re.compile(r"(?=.*[a-z])(?=.*[A-Z])(?=.*[?!@#§+\-$%&*{}()]|(?=.*\d)).{7,}")
        return re.match(regexp, password) is None

    def _generate_password(self):
        """
        Passwords must contain at least one lowercase, one uppercase, one special char or number, and at least 7 chars.
        """

        charlist = string.ascii_letters + string.digits + "?!@#§+-$%&*{}()]["
        password_check = False
        while not password_check:
            password = ''.join(random.choices(charlist, k=8))
            password_check = self._check_password_strength(password)

        return password

    def set_password(self, username, password):
        try:
            self.samdb.setpassword(f"samaccountname={username}", password)
        except LdbError as e:
            logging.error(e.args[1])
            raise Exception(e.args[1])

