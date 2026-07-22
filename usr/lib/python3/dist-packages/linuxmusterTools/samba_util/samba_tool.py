import os
import re
import string
import base64
import random
import logging
import subprocess
from dataclasses import dataclass

from .drives import DriveManager
from ..ldapconnector import LMNLdapReader as lr
from ..lmnconfig import LDAP_CONTEXT


logger = logging.getLogger(__name__)

try:
    from samba.auth import system_session
    from samba.credentials import Credentials
    from samba.param import LoadParm
    from samba.samdb import SamDB
    from samba.netcmd.gpo import get_gpo_info
    from ldb import LdbError, SCOPE_BASE, SCOPE_SUBTREE, Message, MessageElement, FLAG_MOD_REPLACE, Dn

    lp = LoadParm()
    creds = Credentials()
    creds.guess(lp)
except ImportError as e:
    logger.error(f"Samba doesn't seem to be installed, this module can not be used: {str(e)}")

SAMDB_PATH = '/var/lib/samba/private/sam.ldb'

# pwdProperties bit flag, see MS-ADTS 6.1.6.1 (DOMAIN_PASSWORD_COMPLEX)
DOMAIN_PASSWORD_COMPLEX = 0x00000001

# AD sentinel for maxPwdAge meaning "password never expires"
NEVER_TIMESTAMP = -0x8000000000000000

# minPwdAge/maxPwdAge are stored as negative 100ns ticks relative to now
_TICKS_PER_DAY = 24 * 60 * 60 * 10 ** 7


def _days_to_ticks(days):
    return -int(days * _TICKS_PER_DAY)


def _ticks_to_days(ticks):
    ticks = int(ticks)
    if ticks == NEVER_TIMESTAMP:
        return 0
    return int(-ticks / _TICKS_PER_DAY)


@dataclass(frozen=True, slots=True)
class DomainPasswordSettings:
    min_pwd_length: int
    complexity: bool
    min_pwd_age: int
    max_pwd_age: int

class DomainPasswordSettingsManager:
    """
    Reads the domain-wide Samba AD password policy (minimum length,
    complexity) directly via SamDB, equivalent to `samba-tool domain
    passwordsettings show` but without shelling out to it.

    TODO: this only reads the domain-wide policy and ignores Fine-Grained
    Password Policies (PSOs, `samba-tool domain passwordsettings pso ...`),
    which override it for the users/groups they're applied to. If a PSO
    exists for a given role/group, callers using `get()` as a floor will be
    silently wrong (too weak if the PSO is stricter than the domain policy,
    too strict if it's more permissive). Fixing this means taking a username
    (or representative group) and reading that user's constructed attribute
    `msDS-ResultantPSO` (confirmed present in the schema — `systemFlags`
    includes `FLAG_ATTR_IS_CONSTRUCTED`) first, falling back to the
    domain-wide read only if absent. Not an issue today: no PSO is used
    anywhere in this codebase or known deployment. See
    `linuxmusterTools/passwords/README.md` for the full writeup.
    """

    def __init__(self):
        self.samdb = None
        if os.path.isfile(SAMDB_PATH):
            try:
                self.samdb = SamDB(url=SAMDB_PATH, session_info=system_session(), credentials=creds, lp=lp)
            except Exception:
                logger.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ? Are we running as root ?')
        else:
            logger.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')

    def get(self) -> DomainPasswordSettings:
        if self.samdb is None:
            raise RuntimeError(
                f'Cannot read domain password policy: {SAMDB_PATH} could not be opened. '
                'This requires root (SamDB direct access) — call this from a still-privileged '
                'context (e.g. before an Ajenti worker demotes) rather than a demoted worker.'
            )
        base_dn = self.samdb.get_default_basedn()
        result = self.samdb.search(
            base_dn, scope=SCOPE_BASE, attrs=['minPwdLength', 'pwdProperties'],
        )[0]
        min_pwd_length = int(result['minPwdLength'][0])
        pwd_properties = int(result['pwdProperties'][0])
        return DomainPasswordSettings(
            min_pwd_length=min_pwd_length,
            complexity=bool(pwd_properties & DOMAIN_PASSWORD_COMPLEX),
            min_pwd_age=_ticks_to_days(self.samdb.get_minPwdAge()),
            max_pwd_age=_ticks_to_days(self.samdb.get_maxPwdAge()),
        )

    def set(self, *, min_pwd_length=None, min_pwd_age=None, max_pwd_age=None, complexity=None):
        """
        Set the domain-wide password policy, mirroring `samba-tool domain
        passwordsettings set`. Only the given fields are changed; history
        length, lockout settings and PSOs are left untouched.
        Use it very carefully!

        :param min_pwd_length: minimum password length, 0-14
        :param min_pwd_age: minimum password age in days, 0-998
        :param max_pwd_age: maximum password age in days, 0-999 (0 = never expires)
        :param complexity: enable/disable Samba's fixed complexity check
        """

        m = Message()
        m.dn = Dn(self.samdb, str(self.samdb.get_default_basedn()))

        if min_pwd_length is not None:
            if not 0 <= min_pwd_length <= 14:
                raise ValueError("min_pwd_length must be between 0 and 14")
            m["minPwdLength"] = MessageElement(str(min_pwd_length), FLAG_MOD_REPLACE, "minPwdLength")

        if min_pwd_age is not None:
            if not 0 <= min_pwd_age <= 998:
                raise ValueError("min_pwd_age must be between 0 and 998 days")
            m["minPwdAge"] = MessageElement(str(_days_to_ticks(min_pwd_age)), FLAG_MOD_REPLACE, "minPwdAge")

        if max_pwd_age is not None:
            if not 0 <= max_pwd_age <= 999:
                raise ValueError("max_pwd_age must be between 0 and 999 days")
            ticks = NEVER_TIMESTAMP if max_pwd_age == 0 else _days_to_ticks(max_pwd_age)
            m["maxPwdAge"] = MessageElement(str(ticks), FLAG_MOD_REPLACE, "maxPwdAge")

        if complexity is not None:
            current_props = int(self.samdb.get_pwdProperties())
            if complexity:
                new_props = current_props | DOMAIN_PASSWORD_COMPLEX
            else:
                new_props = current_props & ~DOMAIN_PASSWORD_COMPLEX
            m["pwdProperties"] = MessageElement(str(new_props), FLAG_MOD_REPLACE, "pwdProperties")

        if len(m) == 0:
            raise ValueError("At least one setting must be provided")

        if min_pwd_age is not None or max_pwd_age is not None:
            effective_min_days = min_pwd_age if min_pwd_age is not None else _ticks_to_days(self.samdb.get_minPwdAge())
            effective_max_days = max_pwd_age if max_pwd_age is not None else _ticks_to_days(self.samdb.get_maxPwdAge())
            if effective_max_days != 0 and effective_min_days >= effective_max_days:
                raise ValueError(
                    f"max_pwd_age ({effective_max_days}) must be greater than "
                    f"min_pwd_age ({effective_min_days})"
                )

        self.samdb.modify(m)

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
                logger.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ?')
        else:
            logger.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')
        
        self.gpos = {}
        
        for gpo in gpos_infos:
            gpo_id = gpo['name'][0].decode()
            name = gpo['displayName'][0].decode()
            path = gpo['gPCFileSysPath'][0].decode()
            unix_path = "/var/lib/samba/" + '/'.join(path.split('\\')[3:])
            try:
                drivemgr = DriveManager(unix_path)
                self.gpos[name] = GPO(str(gpo.dn), drivemgr, gpo_id, name, path, unix_path)
            except Exception as e:
                logging.error(str(e))

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
                logger.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ?')
        else:
            logger.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')

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

        self.samdb.add_remove_group_members(f"{self.school_prefix}{group}", members=members, add_members_operation=False)
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
                self.samdb.add_remove_group_members(f"{self.school_prefix}{group}", members=[member], add_members_operation=True)
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
                logger.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ?')
        else:
            logger.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')

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
            logger.error(e.args[1])
            raise Exception(e.args[1])

class DeviceManager:
    """
    Sample class to manage samba devices via samba-tool.
    """


    def __init__(self):
        self.POST_HOOK_DIR = '/etc/linuxmuster/tools/hooks/user-manager'

        if os.path.isfile(SAMDB_PATH):
            try:
                self.samdb = SamDB(url=SAMDB_PATH, session_info=system_session(),credentials=creds, lp=lp)
            except Exception:
                logger.error(f'Could not load {SAMDB_PATH}, is linuxmuster installed ?')
        else:
            logger.warning(f'{SAMDB_PATH} not found, is linuxmuster installed ?')

    def get_credentials(self, device_cn, school='default-school'):
        result = self.samdb.search(
            f"OU={school},{LDAP_CONTEXT}",
            SCOPE_SUBTREE,
            expression=f"sAMAccountName={device_cn.upper()}$",
            attrs=['unicodePwd', 'supplementalCredentials']
        )

        if result:
            # More than one result should not happen
            return {
                'unicodePwd': base64.b64encode(result[0]['unicodePwd'][0]).decode(),
                'supplementalCredentials': base64.b64encode(result[0]['supplementalCredentials'][0]).decode(),
            }

        return {}

    def set_credentials(self, device_cn, HashunicodePwd, HashsupplementalCredentials, school='default-school'):
        """
        Directly set unicodePwd and supplementalCredentials for a device using
        ldbmodify.

        :param HashunicodePwd: Hashed unicodePwd
        :type HashunicodePwd: basestring
        :param HashsupplementalCredentials: Hashed supplementalCredentials
        :type HashsupplementalCredentials: basestring
        """


        # Check hashes to avoid injection
        BASE64_CHARS = re.compile(r'^[A-Za-z0-9+/=]*$')

        if re.match(BASE64_CHARS, HashunicodePwd) is None:
            raise Exception(f"{HashunicodePwd} is not a valid hash.")

        if re.match(BASE64_CHARS, HashsupplementalCredentials) is None:
            raise Exception(f"{HashsupplementalCredentials} is not a valid hash.")

        device_dn = lr.getval(f'/devices/{device_cn}', 'distinguishedName', school=school)

        if not device_dn:
            raise Exception(f"{device_cn} was not found in ldap.")

        ldif = f"""
dn: {device_dn}
changetype: modify
replace: unicodePwd
unicodePwd:: {HashunicodePwd}
replace: supplementalCredentials
supplementalCredentials:: {HashsupplementalCredentials}
-
"""
        self.samdb.modify_ldif(
            ldif,
            controls=['relax:0', 'local_oid:1.3.6.1.4.1.7165.4.3.7:0', 'local_oid:1.3.6.1.4.1.7165.4.3.12:0']
        )

