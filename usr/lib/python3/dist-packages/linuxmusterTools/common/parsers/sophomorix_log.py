import os
from datetime import datetime


def parse_kill_log(all=False, epoch=None):

    log_path = '/var/log/sophomorix/userlog/user-kill.log'
    now = datetime .now().timestamp()
    last_year = now - 86400*365

    if not os.path.isfile(log_path):
        raise Exception(f"File {log_path} does not exist.")

    result = {}

    with open(log_path, 'r') as log:
        for line in log:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            entries = line.split('::')
            timestamp = int(entries[1])

            # Only get the entries of last year per default
            if not all and timestamp < last_year:
                continue

            if timestamp not in result:
                result[timestamp] = {}

            result[timestamp] = {
                'school': entries[3],
                'user': entries[4],
                'firstname': entries[6],
                'lastname': entries[5],
                'adminclass': entries[7],
                'role': entries[8],
                'first_password': entries[9],
                'home_deleted': 'TRUE' in entries[10],
            }

    if epoch is not None:
        try:
            epoch = int(epoch)
        except ValueError:
            raise Exception(f"Given epoch ({epoch}) should be an integer!")
        return result.get(epoch, {})

    return result

def parse_add_log(all=False, epoch=None):

    log_path = '/var/log/sophomorix/userlog/user-add.log'
    now = datetime .now().timestamp()
    last_year = now - 86400*365

    if not os.path.isfile(log_path):
        raise Exception(f"File {log_path} does not exist.")

    result = {}

    with open(log_path, 'r') as log:
        for line in log:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            entries = line.split('::')
            timestamp = int(entries[1])

            # Only get the entries of last year per default
            if not all and timestamp < last_year:
                continue

            if timestamp not in result:
                result[timestamp] = {}

            result[timestamp] = {
                'school': entries[3],
                'user': entries[4],
                'firstname': entries[6],
                'lastname': entries[5],
                'adminclass': entries[7],
                'role': entries[8],
                'first_password': entries[9],
            }

    if epoch is not None:
        try:
            epoch = int(epoch)
        except ValueError:
            raise Exception(f"Given epoch ({epoch}) should be an integer!")
        return result.get(epoch, {})

    return result


def parse_update_log(all=False, epoch=None):

    log_path = '/var/log/sophomorix/userlog/user-update.log'
    now = datetime .now().timestamp()
    last_year = now - 86400*365

    if not os.path.isfile(log_path):
        raise Exception(f"File {log_path} does not exist.")

    result = {}

    with open(log_path, 'rb') as log:
        for line in log:
            line = line.strip()

            if not line or line.startswith(b'#'):
                continue

            entries = line.split(b'::')
            timestamp = int(entries[1])

            # Only get the entries of last year per default
            if not all and timestamp < last_year:
                continue

            if timestamp not in result:
                result[timestamp] = {}

            changes = {}
            for change in entries[7].split(b','):
                if b'GROUP:' in change or b'ROLE:' in change:
                    key, move = change.split(b':')
                    changes[key.decode().lower()] = move.decode()
                else:
                    if b'=' in change:
                        key, value = change.split(b'=', 1)
                        if key == 'unicodePwd':
                            change['unicodePwd'] = "CHANGED-VALUE HIDDEN"
                        else:
                            changes[key.decode()] = value.decode()

            result[timestamp] = {
                'school': entries[3].decode(),
                'user': entries[5].decode(),
                'changes': changes,
            }

    if epoch is not None:
        try:
            epoch = int(epoch)
        except ValueError:
            raise Exception(f"Given epoch ({epoch}) should be an integer!")
        return result.get(epoch, {})

    return result
