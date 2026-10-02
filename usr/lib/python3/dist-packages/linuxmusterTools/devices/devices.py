import logging
from pathlib import Path

from ..lmnfile import LMNFile
from ..common.checks import NameChecker
from ..common.timestamps import get_utc_mtime
from ..lmnconfig import SophomorixIni
from .validator import InventoryValidator

sophomorix_ini = SophomorixIni()
CLIENT_ROLES = sophomorix_ini.clientrole

name_checker = NameChecker()

logger = logging.getLogger(__name__)

SOPHOMORIX_SCHOOLS_DIR = '/etc/linuxmuster/sophomorix'

class Devices:
    def __init__(self, school='default-school'):
        self.school = school
        self.switch(self.school)

    def switch(self, school):
        self.school = school
        if self.school != 'default-school':
            # Two different prefixes, do not mix them up: the inventory file
            # is <school>.devices.csv, while a host of that school is named
            # <school>-<hostname> everywhere it is seen from outside its own
            # school - sophomorix' own SCHOOLS.<school>.PREFIX.
            self.prefix = f'{self.school}.'
            self.hostname_prefix = f'{self.school}-'
        else:
            self.prefix = ''
            self.hostname_prefix = ''

        self.path = f'{SOPHOMORIX_SCHOOLS_DIR}/{self.school}/{self.prefix}devices.csv'
        self.load()

    def load(self):
        self.devices = []

        try:
            with LMNFile(self.path, 'r') as devices_csv:
                rows = devices_csv.read()
                for device, csv_line in zip(rows, devices_csv.line_numbers):
                    if not device['room'].startswith('#'):
                        # TODO: special cases for linbo docker
                        device['school'] = self.school
                        # The address as written in the file, kept beside the
                        # normalized one: normalize_mac() returns None on a
                        # malformed address, and a caller reporting it would
                        # have nothing left to name.
                        device['macRaw'] = device['mac'] or ''
                        device['mac'] = name_checker.normalize_mac(device['macRaw'])
                        # Physical line in devices.csv, so that a caller can
                        # point at the line to fix.
                        device['csvLine'] = csv_line
                        device['pxeEnabled'] = self._check_pxe_flag(device)

                        self.devices.append(device)
        except FileNotFoundError:
            # No devices.csv yet, e.g. fresh install not provisioned yet
            pass

        self.groups = list(set([d['group'] for d in self.devices if d.get('group', False)]))
        self.macs = list(set([d['mac'] for d in self.devices if d.get('mac', False)]))
        self.ips = list(set([d['ip'] for d in self.devices if d.get('ip', False)]))
        self.rooms = list(set([d['room'] for d in self.devices if d.get('room', False)]))
        self.hostnames = list(set([d['hostname'] for d in self.devices if d.get('hostname', False)]))
        # Same hosts, named as anything school-agnostic writes them: LINBO
        # logs, hwinfo files, AD objects. Answers "is this host mine?" for a
        # caller holding a name that came from outside the school.
        self.prefixed_hostnames = {f'{self.hostname_prefix}{h}' for h in self.hostnames}
        self.clients = self.filter(roles=CLIENT_ROLES)
        self.csv_mtime = get_utc_mtime(Path(self.path)) # check if I can replace all paths with Path instances

    @staticmethod
    def _check_pxe_flag(device):
        pxeflag = device['pxeFlag'].strip()
        try:
            # If pxeflag is not provided, should be 0
            int_pxeflag = int(pxeflag) if pxeflag else 0
        except ValueError:
            int_pxeflag = 0

        return int_pxeflag > 0 and device['group'].lower() != "nopxe"

    def filter(self, roles=[], groups=[], macs=[]):
        """
        Filter the devices list per attributes.
        The filters roles and groups can be combined, but the filter macs must
        be used alone.
        """


        if roles and groups:
            return [device for device in self.devices if device['sophomorixRole'] in roles and device['group'] in groups]
        elif roles:
            return [device for device in self.devices if device['sophomorixRole'] in roles]
        elif groups:
            return [device for device in self.devices if device['group'] in groups]
        elif macs:
            macs_normalized = [name_checker.normalize_mac(mac) for mac in macs]
            return [
                device
                for device in self.devices
                if name_checker.normalize_mac(device['mac']) in macs_normalized]
        return self.devices

    def get_host(self, hostname, roles=[], groups=[]):
        for device in self.filter(roles, groups):
            if device['hostname'] == hostname:
                return device
        return None

    def get_hosts_by_macs(self, macs=[]):
        return self.filter(macs=macs)

    def get_client(self, hostname, groups=[]):
        return self.get_host(hostname, roles=CLIENT_ROLES, groups=groups)

    def get_clients(self, groups=[]):
        return self.filter(roles=CLIENT_ROLES, groups=groups)

    def check_conf(self):
        """
        Validate the inventory of this school, reporting everything found
        instead of stopping at the first problem.

        Only this school is read, so a host name, a mac address or an ip
        address shared with another school can not be seen here: use
        check_all_schools() for that.

        :return: valid, counts, findings and report (see InventoryValidator.validate)
        :rtype: dict
        """


        return InventoryValidator([{
            'school': self.school,
            'file': self.path,
            'devices': self.devices,
        }]).validate()


def list_schools(root=None):
    """
    List the schools holding a devices.csv on this server.

    This reads the filesystem rather than ldap on purpose: what is
    validated here are the files, and a caller already holding the
    authoritative list of provisioned schools passes it to
    check_all_schools() instead.

    :param root: Directory holding one subdirectory per school
    :type root: string or Path
    :return: Sorted school names
    :rtype: list
    """


    root = Path(root or SOPHOMORIX_SCHOOLS_DIR)
    schools = []

    try:
        candidates = sorted(entry for entry in root.iterdir() if entry.is_dir())
    except OSError as e:
        logger.warning(f"Could not list the schools in {root}: {e}")
        return []

    for entry in candidates:
        prefix = '' if entry.name == 'default-school' else f'{entry.name}.'
        if (entry / f'{prefix}devices.csv').is_file():
            schools.append(entry.name)

    return schools


def check_all_schools(schools=None):
    """
    Validate the inventories of every school at once, which is the only way
    to see a host name or a mac address used twice in two different schools.

    :param schools: Schools to validate, discovered on disk if not given
    :type schools: list
    :return: valid, counts, findings and report (see InventoryValidator.validate)
    :rtype: dict
    """


    if schools is None:
        schools = list_schools()

    inventories = []
    for school in schools:
        devicesmgr = Devices(school=school)
        inventories.append({
            'school': school,
            'file': devicesmgr.path,
            'devices': devicesmgr.devices,
        })

    return InventoryValidator(inventories).validate()
