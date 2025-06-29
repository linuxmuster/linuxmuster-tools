import os
import logging
from datetime import datetime, timedelta


KILL_LOG_PATH = '/var/log/sophomorix/userlog/user-kill.log'
ADD_LOG_PATH = '/var/log/sophomorix/userlog/user-add.log'
UPDATE_LOG_PATH = '/var/log/sophomorix/userlog/user-update.log'

def parse_kill_log(all=False, epoch=None, today=False, lastweek=False):

    if (all and today) or (all and lastweek) or (today and lastweek):
        logging.error("Parameter all, today and lastweek are mutually exclusives! Please pick only one of them.")
        raise Exception("Parameter all, today and lastweek are mutually exclusives! Please pick only one of them.")

    now = datetime.now().timestamp()
    last_year = now - 86400*365

    if not os.path.isfile(KILL_LOG_PATH):
        raise Exception(f"File {KILL_LOG_PATH} does not exist.")

    result = {}

    with open(KILL_LOG_PATH, 'r') as log:
        for line in log:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            entries = line.split('::')
            timestamp = int(entries[1])

            # Only get the entries of last year per default
            if not all and timestamp < last_year:
                continue

            # If flag today is set, only the changes of the current day
            if today and not datetime.fromtimestamp(timestamp).date() == datetime.today().date():
                continue

            # If flag lastweek is set, only the changes of the last week
            if lastweek and not datetime.fromtimestamp(timestamp).date() >= datetime.today().date() + timedelta(days=-7):
                continue

            if timestamp not in result:
                result[timestamp] = []

            result[timestamp].append({
                'school': entries[3],
                'user': entries[4],
                'firstname': entries[6],
                'lastname': entries[5],
                'adminclass': entries[7],
                'role': entries[8],
                'first_password': entries[9],
                'home_deleted': 'TRUE' in entries[10],
            })

    if epoch is not None:
        try:
            epoch = int(epoch)
        except ValueError:
            raise Exception(f"Given epoch ({epoch}) should be an integer!")
        return result.get(epoch, [])

    return result

def parse_add_log(all=False, epoch=None, today=False, lastweek=False):

    if (all and today) or (all and lastweek) or (today and lastweek):
        logging.error("Parameter all, today and lastweek are mutually exclusives! Please pick only one of them.")
        raise Exception("Parameter all, today and lastweek are mutually exclusives! Please pick only one of them.")

    now = datetime.now().timestamp()
    last_year = now - 86400*365

    if not os.path.isfile(ADD_LOG_PATH):
        raise Exception(f"File {ADD_LOG_PATH} does not exist.")

    result = {}

    with open(ADD_LOG_PATH, 'r') as log:
        for line in log:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            entries = line.split('::')
            timestamp = int(entries[1])

            # Only get the entries of last year per default
            if not all and timestamp < last_year:
                continue

            # If flag today is set, only the changes of the current day
            if today and not datetime.fromtimestamp(timestamp).date() == datetime.today().date():
                continue

            # If flag lastweek is set, only the changes of the last week
            if lastweek and not datetime.fromtimestamp(timestamp).date() >= datetime.today().date() + timedelta(days=-7):
                continue

            if timestamp not in result:
                result[timestamp] = []

            result[timestamp].append({
                'school': entries[3],
                'user': entries[4],
                'firstname': entries[6],
                'lastname': entries[5],
                'adminclass': entries[7],
                'role': entries[8],
                'first_password': entries[9],
            })

    if epoch is not None:
        try:
            epoch = int(epoch)
        except ValueError:
            raise Exception(f"Given epoch ({epoch}) should be an integer!")
        return result.get(epoch, [])

    return result


def parse_update_log(all=False, epoch=None, today=False, lastweek=False, list_changes=True ):

    if (all and today) or (all and lastweek) or (today and lastweek):
        logging.error("Parameter all, today and lastweek are mutually exclusives! Please pick only one of them.")
        raise Exception("Parameter all, today and lastweek are mutually exclusives! Please pick only one of them.")

    now = datetime.now().timestamp()
    last_year = now - 86400*365

    if not os.path.isfile(UPDATE_LOG_PATH):
        raise Exception(f"File {UPDATE_LOG_PATH} does not exist.")

    result = {}

    with open(UPDATE_LOG_PATH, 'rb') as log:
        for line in log:
            line = line.strip()

            if not line or line.startswith(b'#'):
                continue

            entries = line.split(b'::')
            timestamp = int(entries[1])

            # Only get the entries of last year per default
            if not all and timestamp < last_year:
                continue

            # If flag today is set, only the changes of the current day
            if today and not datetime.fromtimestamp(timestamp).date() == datetime.today().date():
                continue

            # If flag lastweek is set, only the changes of the last week
            if lastweek and not datetime.fromtimestamp(timestamp).date() >= datetime.today().date() + timedelta(days=-7):
                continue

            if timestamp not in result:
                result[timestamp] = []

            changes = {}
            if list_changes:
                for change in entries[7].split(b','):
                    change = change.strip(b'"')
                    if b'GROUP:' in change or b'ROLE:' in change:
                        key, move = change.split(b':')
                        changes[key.decode().lower()] = move.decode()
                    else:
                        if b'=' in change:
                            key, value = change.split(b'=', 1)
                            if b'unicodePwd' in key:
                                changes['unicodePwd'] = "CHANGED-VALUE HIDDEN"
                            else:
                                changes[key.decode()] = value.decode()

            result[timestamp].append({
                'school': entries[3].decode(),
                'user': entries[5].decode(),
                'changes': changes,
            })

    if epoch is not None:
        try:
            epoch = int(epoch)
        except ValueError:
            raise Exception(f"Given epoch ({epoch}) should be an integer!")
        return result.get(epoch, [])

    return result
