from dataclasses import dataclass, field
from datetime import datetime
import os
import locale
import time

from ..devices import Devices


@dataclass
class Partition:
    Bootable: bool
    Dev: str
    FSType: str
    Id: int
    Label: str
    Size: str

@dataclass
class OS:
    Append: str
    Autostart: bool
    AutostartTimeout: int
    BaseImage: str
    Boot: str
    DefaultAction: str
    Description: str
    Hidden: bool
    IconName: str
    Initrd: str
    Kernel: str
    NewEnabled: bool
    Root: str
    StartEnabled: bool
    SyncEnabled: bool
    Version: str

@dataclass
class Linbo:
    AutoFormat: bool
    AutoInitCache: bool
    AutoPartition: bool
    Cache: str
    DownloadType: str
    Group: str
    GuiDisabled: bool
    KernelOptions: str
    Locale: str
    RootTimeout: int
    Server: str
    SystemType: str
    UseMinimalLayout: bool

@dataclass
class LinboConfig:
    LINBO: Linbo
    Partitions: list
    OS: list

class LinboConfigManager:
    pass

## The following functions need to be rewritten

LINBO_PATH = '/srv/linbo'

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