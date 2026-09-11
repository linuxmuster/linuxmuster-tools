import os
import re
import time
import logging
import filecmp
from pathlib import Path
import hashlib
from glob import glob
from datetime import datetime, timezone

from .models import *
from .grub import GRUB_DIR_DEFAULT
from ..devices import Devices
from ..lmnfile import LMNFile
from ..common.checks import NameChecker
from ..common.timestamps import get_utc_mtime, linbo_timestamp_to_epoch


LINBO_PATH = '/srv/linbo'
LINBO_LOG_PATH = '/var/log/linuxmuster/linbo'
logger = logging.getLogger(__name__)
name_checker = NameChecker()

class LinboConfigManager:

    def __init__(self, school='default-school'):
        self.school = school
        self.linbo_configs = {}
        self.group_ids = self._list_group_ids()

    def _list_group_ids(self):
        """
        List the hardware group IDs with an existing, validly-named
        start.conf file. Enumeration only: independent of whether the
        file's content actually parses.
        """


        group_ids = []
        for config in sorted(glob(os.path.join(LINBO_PATH, 'start.conf.*'))):
            if not os.path.islink(config):
                group = config.replace(os.path.join(LINBO_PATH, 'start.conf.'), '')

                ## Maybe is the ignore list incomplete
                if any(s in group for s in ('.bak', '.bkp', '.tmp')) or group.endswith('~'):
                    continue

                if not name_checker.check_linbo_conf_name(group):
                    logger.warning(f"Invalid config name, this file will be ignored: {config}")
                    continue

                group_ids.append(group)
        return group_ids

    def load_linbo_startconf(self, group):
        """
        WIP. Do not use in productivity !
        Parse a single group's start.conf and cache it in linbo_configs.
        """


        config = os.path.join(LINBO_PATH, f'start.conf.{group}')
        try:
            self.linbo_configs[group] = self.parse_linbo_startconf(config)
        except TypeError as e:
            logger.error(f"Failed to load {config}: {e}")
        return self.linbo_configs.get(group)

    def load_linbo_startconfs(self):
        """
        WIP. Do not use in productivity !
        Parse every known group's start.conf.
        """


        for group in self.group_ids:
            self.load_linbo_startconf(group)

    def parse_linbo_startconf(self, config):
        """
        WIP. Do not use in productivity !
        Parse a start.conf file to a LinboConfig object.
        TODO: duplicate in lmnfile reader
        """


        if not os.path.isfile(config):
            raise FileNotFoundError(f'Linbo config file not found: {config}.')

        def flush_stanza(model, kwargs, lc):
            if model == 'LINBO':
                lc.LINBO = Linbo.from_dict(kwargs)
            elif model == 'Partition':
                lc.Partitions.append(Partition.from_dict(kwargs))
            elif model == 'OS':
                lc.OS.append(OS.from_dict(kwargs))

        with open(config, 'r') as f:
            kwargs = {'config': config}
            current_model = ''

            lc = LinboConfig(path=config, LINBO=None, Partitions=[], OS=[])

            for line in f:
                line = line.split('#')[0].strip()

                if line.startswith('['):
                    flush_stanza(current_model, kwargs, lc)
                    kwargs = {'config': config}
                    current_model = line.strip('[]')

                elif '=' in line:
                    k, v = line.split('=', 1)
                    v = v.strip()
                    if v in ['yes', 'no']:
                        v = v == 'yes'
                    kwargs[k.strip()] = v

            # Flush the last stanza: no trailing '[' ever comes to trigger it.
            flush_stanza(current_model, kwargs, lc)

            return lc

    def load_raw_startconfs(self, group_ids: list[str]) -> list[dict]:
        """
        Return raw start.conf contents, hashes, and mtimes for the requested IDs.
        """

        results = []
        for group_id in group_ids:
            if not name_checker.check_linbo_conf_name(group_id):
                continue

            conf_path = Path(LINBO_PATH) / f'start.conf.{group_id}'

            if not os.path.isfile(f"/srv/linbo/start.conf.{group_id}"):
                logger.warning(f"Startconf file start.conf.{group_id} not found.")
                continue

            try:
                content = conf_path.read_text(encoding='utf-8')
            except OSError:
                continue

            mtime = get_utc_mtime(conf_path)

            results.append({
                'id': group_id,
                'content': content,
                'hash': hashlib.sha256(content.encode()).hexdigest(),
                'updatedAt': mtime.isoformat() if mtime else None,
            })
        return results

    def write_raw_startconf(self, group_id: str, content: str) -> None:
        """
        Create or update a start.conf file from raw text content.

        Writes the content verbatim (comments and formatting preserved),
        unlike StartConfLoader.write() which rebuilds the file from parsed
        sections and drops comments.
        TODO: add a method to parse the content.
        """

        if not name_checker.check_linbo_conf_name(group_id):
            raise ValueError(f"Invalid group id: {group_id}")

        conf_path = os.path.join(LINBO_PATH, f'start.conf.{group_id}')
        tmp_path = conf_path + '_tmp'

        if os.path.isfile(conf_path):
            with LMNFile(conf_path, 'w') as lmn_file:
                with open(tmp_path, 'w', encoding=lmn_file.encoding) as f:
                    f.write(content)

                if not filecmp.cmp(tmp_path, conf_path):
                    lmn_file.backup()
                    os.rename(tmp_path, conf_path)
                else:
                    os.unlink(tmp_path)
        else:
            lmn_file = LMNFile(conf_path, 'w')
            with open(tmp_path, 'w', encoding=lmn_file.encoding) as f:
                f.write(content)
            os.rename(tmp_path, conf_path)

        os.chmod(conf_path, 0o755)

    def delete_startconf(self, group_id: str) -> None:
        """
        Delete a start.conf file and its associated GRUB config.
        """

        if not name_checker.check_linbo_conf_name(group_id):
            raise ValueError(f"Invalid group id: {group_id}")

        conf_path = os.path.join(LINBO_PATH, f'start.conf.{group_id}')
        if not os.path.isfile(conf_path):
            raise FileNotFoundError(f"Startconf file start.conf.{group_id} not found.")

        with LMNFile(conf_path, 'r') as f:
            f.backup()
        os.unlink(conf_path)

        grub_cfg_path = os.path.join(GRUB_DIR_DEFAULT, f'{group_id}.cfg')
        if os.path.isfile(grub_cfg_path):
            os.unlink(grub_cfg_path)

## The following functions need to be rewritten
## Still used in lmncli

_IMAGE_STATUS_PATTERN = re.compile(r'^(\d{12})\s+(\w+):\s+(\S+)(?:\s+"?(\d+)"?)?')

def _parse_image_status_file(statusfile):
    """
    Parse a *_image.status file as written by linuxmuster-linbo7's
    shell_functions log_image_status(), e.g.:
        202603241142 applied: win11_pro_edu.qcow2 "202601271107"
        202601271107 created: win11_pro_edu.qcow2 202601271107

    The trailing image timestamp is quoted on "applied" lines and bare on
    "created" ones: linbo_sync reads it back from the image .info file with
    getinfo(), which returns the raw right-hand side of timestamp="...",
    quotes included, while linbo_mkinfo passes date(1) output directly.
    Both forms are accepted.

    The file is overwritten (not appended) on every sync/creation, so it
    normally holds a single line, but every matching line is returned, in
    file order, to stay tolerant of older or hand-edited multi-line files.

    :param statusfile: Path to the *_image.status file
    :type statusfile: string
    :return: List of {timestamp, action, image, image_timestamp}
    :rtype: list of dict
    """

    if not os.path.isfile(statusfile) or os.stat(statusfile).st_size == 0:
        return []

    entries = []
    with open(statusfile, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = _IMAGE_STATUS_PATTERN.match(line.strip())
            if m:
                entries.append({
                    'timestamp': m.group(1),
                    'action': m.group(2),
                    'image': m.group(3),
                    'image_timestamp': m.group(4),
                })
    return entries

def last_sync(workstation, image):
    """
    Get the date of the last sync date for a workstation w.

    The status file is looked up without taking its case into account: its
    name is built by rsync-pre-download.sh from the reverse DNS resolution
    made by rsyncd, not from devices.csv, and DNS is case insensitive. Both
    PC-001_image.status and pc-001_image.status can therefore sit in the log
    directory, only one of them still being written to, so every variant is
    read and the most recent entry wins.

    :param w: Workstation
    :type w: string
    :param image: Name of the image file
    :type image: string
    :return: Last synchronisation time
    :rtype: datetime
    """


    if not os.path.isdir(LINBO_LOG_PATH):
        return False

    statusfile = f'{workstation}_image.status'.lower()
    diff_image = image.replace('.qcow2', '.qdiff')

    matches = []
    for filename in os.listdir(LINBO_LOG_PATH):
        if filename.lower() != statusfile:
            continue

        matches.extend(
            entry['timestamp']
            for entry in _parse_image_status_file(os.path.join(LINBO_LOG_PATH, filename))
            if entry['image'] in (image, diff_image)
        )

    if not matches:
        return False

    return linbo_timestamp_to_epoch(max(matches))

def get_host_image_status(log_dir=None):
    """
    Report the last logged image status for every host, read directly from
    the *_image.status files in the LINBO log directory.

    Unlike last_sync(), this does not need to know beforehand which image a
    host is expected to run: it just reports whatever the last
    log_image_status() call from linuxmuster-linbo7's shell_functions wrote
    to that host's status file, "applied" or "created".

    :param log_dir: Override log directory (default: LINBO_LOG_PATH)
    :type log_dir: string
    :return: Dict mapping hostname to {lastSync, action, image, imageVersion}
    :rtype: dict
    """

    base = Path(log_dir) if log_dir else Path(LINBO_LOG_PATH)
    if not base.is_dir():
        return {}

    try:
        filenames = os.listdir(base)
    except OSError:
        return {}

    status_files = [f for f in filenames if f.endswith('_image.status')]

    result = {}
    for filename in sorted(status_files):
        hostname = filename.removesuffix('_image.status')

        try:
            entries = _parse_image_status_file(base / filename)
        except OSError as e:
            # One unreadable file must not cost the whole report, but it is
            # reported: a host silently missing from the result would look
            # like a host which never synced.
            logger.warning(f"Could not read the image status file of {hostname}: {str(e)}")
            continue

        if not entries:
            continue

        last = entries[-1]
        # The timestamp is the client's local time, not UTC: convert it
        # instead of relabelling the raw digits with a "Z".
        epoch = linbo_timestamp_to_epoch(last['timestamp'])

        result[hostname] = {
            'lastSync': datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(),
            'action': last['action'],
            'image': last['image'],
            'imageVersion': last['image_timestamp'],
        }

    return result

def read_config(group):
    """
    Get the os config from linbo config file start.conf.<group>
    :param group: Linbo group
    :type group: string
    :return: Config as list of dict
    :rtype: list of dict
    """


    path = os.path.join(LINBO_PATH, 'start.conf.'+group)
    osConfig = []
    if os.path.isfile(path):
        for line in open(path):
            line = line.split('#')[0].strip()
            if line.startswith('['):
                section = {}
                section_name = line.strip('[]')
                if section_name == 'OS':
                    osConfig.append(section)
            elif '=' in line:
                k, v = line.split('=', 1)
                v = v.strip()
                if v in ['yes', 'no']:
                    v = v == 'yes'
                section[k.strip()] = v
        return osConfig
    return None

def group_os(workstations):
    """
    Get all os infos from linbo config file and inject it in workstations dict.
    The workstations dict is set in the function list_workstations().

    :param workstations: Dict containing all workstations
    :type workstations: dict
    :return: Completed workstations dict with linbo informations
    :rtype: dict
    """


    startconf_mgr = LinboConfigManager()

    for group in workstations.keys():
        workstations[group]['os'] = []
        config = read_config(group)
        if config is not None:
            workstations[group]['power'] = {
                'run_halt': 0,
                'timeout': 1
                }
            workstations[group]['auto'] = {
                'disable_gui': 0,
                'broadcast': 0,
                'bypass': 0,
                'wol': 0,
                'prestart': 0,
                'partition': 0,
            }

            linbo_config = startconf_mgr.load_linbo_startconf(group)
            # 1-based position among [Partition] sections, what linbo-remote's
            # format:<#> actually expects — NOT the digit in the device path
            # (Root=/dev/sda3 isn't necessarily partition 3).
            partitions = [p.Dev for p in linbo_config.Partitions] if linbo_config else []

            for osConfig in config:
                if osConfig['SyncEnabled'] or osConfig['NewEnabled']:
                    root = osConfig['Root']
                    tmpDict = {
                                'baseimage': osConfig['BaseImage'],
                                'partition': partitions.index(root) + 1 if root in partitions else None,
                                'new_enabled': osConfig['NewEnabled'],
                                'start_enabled': osConfig['StartEnabled'],
                                'run_format': 0,
                                'run_sync':0,
                                'run_start':0,
                        }
                    workstations[group]['os'].append(tmpDict)

    return workstations

def list_workstations(school='default-school', groups=[]):
    """
    Generate a dict with workstations and parameters out of devices file

    :param context: user context set in views.py
    :return: Dict with all linbo informations for all workstations.
    :rtype: dict
    """


    devices_dict = {}
    devices_manager = Devices(school=school)
    devices = devices_manager.filter(groups=groups)

    for device in devices:
        if school != 'default-school':
            if device['hostname']:
                device['hostname'] = f'{school}-{device["hostname"]}'
        if os.path.isfile(os.path.join(LINBO_PATH, 'start.conf.'+str(device['group']))):
            if device['pxeFlag'] != '1' and device['pxeFlag'] != "2":
                continue
            elif device['group'] not in devices_dict.keys():
                devices_dict[device['group']] = {'grp': device['group'], 'hosts': [device]}
            else:
                devices_dict[device['group']]['hosts'].append(device)
    return group_os(devices_dict)

def last_sync_all(workstations):
    """
    Add last synchronisation informations into the workstations dict,
    and status attribute to use as class for bootstrap.

    :param workstations: Dict of workstations set in list_workstations().
    :type workstations: dict
    :return: Completed dict of workstations
    :rtype: dict
    """


    today = time.mktime(datetime.now().timetuple())

    for group, grpDict in sorted(workstations.items()):
            for host in grpDict['hosts']:
                host['image'] = []
                for image in workstations[group]['os']:
                    last = last_sync(host['hostname'], image['baseimage'])
                    date = last if last else "Never"
                    tmpDict = {
                            'date': date,
                            'image': image['baseimage']
                    }
                    if date == "Never" or (today - date > 30*24*3600):
                        tmpDict['status'] = "danger"
                    elif today - date > 7*24*3600:
                        tmpDict['status'] = "warning"
                    else:
                        tmpDict['status'] = "success"
                    host['image'].append(tmpDict)
