import os
import pwd
import re
import subprocess
import smbclient
from datetime import datetime
from smbprotocol.exceptions import SMBAuthenticationError

from ..samba_util import SAMBA_WORKGROUP, SAMBA_DOMAIN, SAMBA_NETBIOS
from ..ldapconnector import LMNLdapReader as lr
from ..common import format_size


def timestamp2date(t):
    return datetime.fromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S")

def _get_recursive_dir_properties(path):
    """
    Get properties of folder, and call itself recursively for subfolders.

    :param path: Current SAMBA path to scan
    :type path: basestring
    :return: Files, subfolders, and their size, last modified date.
    :rtype: dict
    """

    properties = {
            'name': path.split('/')[-1],
            'type': "directory",
            'size':0,
            'lastModified': timestamp2date(smbclient.stat(path).st_mtime),
            'contents': [],
            'path': path,
    }

    for item in smbclient.scandir(path):
        if item.is_file():
            stats = item.stat()
            properties['contents'].append({
                    'name': item.name,
                    'type': "file",
                    "path": f"{path}/{item.name}",
                    'size': stats.st_size,
                    'lastModified': timestamp2date(stats.st_mtime),
                }
            )

        elif item.is_dir():
            dir_path = f"{path}/{item.name}"
            properties['contents'].append(_get_recursive_dir_properties(dir_path))

    return properties

def _sum_dir_size(d):
    for item in d['contents']:
        if item["type"] == "file":
            d['size'] += item['size']
        else:
            d['size'] += _sum_dir_size(item)
    return d['size']

def samba_root_tree(user):
    """
    Recursively list files and folder of a school root share, with size and last-modified properties.
    This function can only be called with a valid kerberos ticket.

    :param user: LDAP User
    :type user: basestring
    :return: All folders and files owned by user
    :rtype: dict
    """

    try:
        school = lr.getval(f'/users/{user}', 'sophomorixSchoolname')
        path = f'//{SAMBA_NETBIOS}/{school}'
        directories = _get_recursive_dir_properties(path)
        directories['school'] = school
        _sum_dir_size(directories)
        return directories
    except SMBAuthenticationError as e:
        print(f"Please check if you have a valid Kerberos Ticket for the user {user}.")
        return None

def _samba_dir_size(user, path=None):
    if not path:
        # Scanning from root share
        school = lr.getval(f'/users/{user}', 'sophomorixSchoolname')
        path = f'//{SAMBA_NETBIOS}/{school}'

    total = 0
    for item in smbclient.scandir(path):
        if item.is_file():
            total += item.stat().st_size
        elif item.is_dir():
            total += _samba_dir_size(user, path=item.path)
    return total

def samba_dir_size(user, path=None, raw=False):
    size = _samba_dir_size(user, path)
    if raw:
        return size
    else:
        return format_size(size)

def list_user_files(user):
    path = '/srv/samba'
    user = f'{SAMBA_WORKGROUP}\\{user}'

    directories = {}

    for root, dirs, files in os.walk(path):
        for f in files:
            stats = os.stat(os.path.join(root, f))
            owner = pwd.getpwuid(stats.st_uid).pw_name
            size = stats.st_size
            if owner == user:
                for directory, _ in directories.items():
                    if root.startswith(directory):
                        directories[directory]['total'] += size
                        directories[directory]['files'][f] = f"{format_size(size)}"
                        break
                else:
                    directories[root] = {'total': size, 'files':{f: f"{format_size(size)}"}}

    total = 0
    for directory, details in directories.items():
        size = details['total']
        total += size
        directories[directory]['total'] = f"{format_size(size)}"

    return {'directories': directories, 'total': f"{format_size(total)}"}

def get_user_quotas(user):
    # TODO: find a better way to get shares list
    sophomorixQuota = lr.getval(f'/users/{user}', 'sophomorixQuota')
    if sophomorixQuota is None:
        raise Exception(f'User {user} not found in ldap')

    quotas = {share.split(":")[0]: None for share in sophomorixQuota}

    with open('/etc/linuxmuster/.secret/administrator', 'r') as adm_pw:
        pw = adm_pw.readline().strip()

    def _format_quota(quota):
        if "NO LIMIT" in quota:
            return quota
        return round(int(quota) / 1024 /1024, 2)

    # TODO: parallel ?
    for share in quotas.keys():
        cmd = ['smbcquotas', '-U', f'administrator%{pw}', '-u', user, f'//{SAMBA_DOMAIN}/{share}']
        smbc_output = subprocess.run(cmd, capture_output=True)
        out, err = smbc_output.stdout.decode().strip(),  smbc_output.stderr.decode().strip()
        if smbc_output.returncode > 0:
            # Catch Samba error
            error_code =  err.split("(")[1].strip(")")
            quotas[share] = {
                "used": error_code,
                "soft_limit": error_code,
                "hard_limit": error_code,
            }
        else:
            used, soft, hard = [value.strip("/") for value in re.split(r"\s{2,}", out)[2:]]
            quotas[share] = {
                "used": _format_quota(used),
                "soft_limit": _format_quota(soft),
                "hard_limit": _format_quota(hard),
            }

    pw = ''

    return quotas