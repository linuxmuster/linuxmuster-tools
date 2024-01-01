import os
import pwd

from ..samba_util import SAMBA_WORKGROUP


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
                        directories[directory]['files'][f] = f"{size / 1024 / 1024:.2f}"
                        break
                else:
                    directories[root] = {'total': size, 'files':{f: f"{size / 1024 / 1024:.2f}"}}

    total = 0
    for directory, details in directories.items():
        size = details['total']
        total += size
        mega = size / 1024 / 1024
        directories[directory]['total'] = f"{mega:.2f}"

    return {'directories': directories, 'total': f"{total / 1024 / 1024:.2f}"}