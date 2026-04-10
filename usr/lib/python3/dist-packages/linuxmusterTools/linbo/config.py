import hashlib
import locale
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from .models import *
from ._validation import check_linbo_conf_name
from .hosts import get_mtime
from ..devices import Devices


LINBO_PATH = '/srv/linbo'
logger = logging.getLogger(__name__)


def _validate_safe_name(name: str) -> str:
    """Validate a LINBO-safe config name and return it unchanged."""
    if not isinstance(name, str) or not name:
        raise ValueError('LINBO config name must not be empty')
    if not check_linbo_conf_name(name):
        raise ValueError(f'Unsafe LINBO config name: {name}')
    return name

class LinboConfigManager:

    def __init__(self, school='default-school', linbo_dir=LINBO_PATH):
        self.school = school
        self.linbo_dir = Path(linbo_dir)
        self.linbo_configs = {}

        self.load_linbo_config()

    def load_linbo_config(self):
        self.linbo_configs = {}
        for config in sorted(self.linbo_dir.glob('start.conf.*')):
            if not config.is_symlink():
                group = config.name.removeprefix('start.conf.')
                try:
                    self.linbo_configs[group] = self.read_linbo_config(config)
                except TypeError as e:
                    logger.error(f"Failed to load {config}: {e}")

    def read_linbo_config(self, config):
        config = Path(config)
        if not config.is_file():
            raise FileNotFoundError(f'Linbo config file not found: {config}.')

        with config.open('r', encoding='utf-8') as f:
            kwargs = {'config': str(config)}
            current_model = ''

            lc = LinboConfig(path=str(config), LINBO=None, Partitions=[], OS=[])

            for line in f:
                line = line.split('#')[0].strip()

                if line.startswith('['):
                    if current_model == 'LINBO':
                        lc.LINBO = Linbo.from_dict(kwargs)
                    elif current_model == 'Partition':
                        lc.Partitions.append(Partition.from_dict(kwargs))
                    elif current_model == 'OS':
                        lc.OS.append(OS.from_dict(kwargs))

                    kwargs = {'config': config}
                    current_model = line.strip('[]')

                elif '=' in line:
                    k, v = line.split('=', 1)
                    v = v.strip()
                    if v in ['yes', 'no']:
                        v = v == 'yes'
                    kwargs[k.strip()] = v

            return lc

    def linbo_groups(self):
        return list(self.linbo_configs.keys())

    def list_startconf_ids(self) -> list[str]:
        """Return sorted start.conf IDs from the LINBO directory."""
        ids = []
        for conf_path in sorted(self.linbo_dir.glob('start.conf.*')):
            if conf_path.is_symlink():
                continue
            group_id = conf_path.name.removeprefix('start.conf.')
            if group_id and check_linbo_conf_name(group_id):
                ids.append(group_id)
        return ids

    def get_raw_startconfs(self, ids: list[str]) -> list[dict]:
        """Return raw start.conf contents, hashes, and mtimes for the requested IDs."""
        results = []
        for group_id in ids:
            try:
                safe_id = _validate_safe_name(group_id)
            except ValueError:
                continue

            conf_path = self.linbo_dir / f'start.conf.{safe_id}'
            if not conf_path.is_file():
                continue

            try:
                content = conf_path.read_text(encoding='utf-8')
            except OSError:
                continue

            mtime = get_mtime(conf_path)
            results.append({
                'id': safe_id,
                'content': content,
                'hash': hashlib.sha256(content.encode()).hexdigest(),
                'updatedAt': mtime.isoformat() if mtime else None,
            })

        return results

    def get_startconf_mtime(self, group_id: str):
        """Return the mtime of a specific start.conf file, or None if missing."""
        safe_id = _validate_safe_name(group_id)
        conf_path = self.linbo_dir / f'start.conf.{safe_id}'
        return get_mtime(conf_path)

## The following functions need to be rewritten
## Still used in lmncli

def last_sync(workstation, image):
    """
    Get the date of the last sync date for a workstation w.

    :param w: Workstation
    :type w: string
    :param image: Name of the image file
    :type image: string
    :return: Last synchronisation time
    :rtype: datetime
    """


    statusfile = f'/var/log/linuxmuster/linbo/{workstation}_image.status'
    image_last_sync, diff_last_sync = '0','0'
    diff_image = image.replace('.qcow2', '.qdiff')

    if os.path.isfile(statusfile) and os.stat(statusfile).st_size != 0:
        for line in open(statusfile, 'r').readlines():
            if image in line:
                image_last_sync = line.rstrip().split(' ')[0]
            if diff_image in line:
                diff_last_sync = line.strip().split(' ')[0]

    last = max(image_last_sync, diff_last_sync)

    if last == '0':
        return False

    ## Linbo locale is en_GB, not necessarily the server locale
    saved = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    last = datetime.strptime(last, '%Y%m%d%H%M')
    locale.setlocale(locale.LC_ALL, saved)

    last = time.mktime(last.timetuple())
    return last

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
                'bypass': 0,
                'wol': 0,
                'prestart': 0,
                'partition': 0,
            }
            for osConfig in config:
                if osConfig['SyncEnabled'] or osConfig['NewEnabled']:
                    tmpDict = {
                                'baseimage': osConfig['BaseImage'],
                                'partition': osConfig['Root'][-1],
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
                host['images'] = []
                host['sync'] = {}
                for image in workstations[group]['os']:
                    last = last_sync(host['hostname'], image['baseimage'])
                    date = last if last else "Never"
                    tmpDict = {
                            'date': date,
                    }
                    if date == "Never" or (today - date > 30*24*3600):
                        tmpDict['status'] = "danger"
                    elif today - date > 7*24*3600:
                        tmpDict['status'] = "warning"
                    else:
                        tmpDict['status'] = "success"
                    host['sync'][image['baseimage']] = tmpDict
                    host['images'].append(image['baseimage'])
