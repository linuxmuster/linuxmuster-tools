import os
from datetime import datetime

def parse_kill_log(all=False):

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

    return result




