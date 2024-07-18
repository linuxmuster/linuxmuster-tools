import re
import logging
from datetime import datetime

from ..samba_util import SAMBA_REALM, LOG_LEVEL


SAMBA_LOG = '/var/log/samba/log.samba'
SAMBA_LOG_OLD = '/var/log/samba/log.samba.1'

def check_audit_level():
    auth_audit = LOG_LEVEL.get('auth_audit', 1)
    general = LOG_LEVEL.get('general', 1)

    if auth_audit > 2:
        return True

    if general > 2:
        return True

    logging.error("Can not parse log files from samba, you need to set the log level of auth_audit at least at 3.")
    return False

def format_log_data(entry):
    data = re.findall(r"\[([^\]]*)\]", entry)
    if len(data) > 1 and "Kerberos" in data[0] and "@" in data[2]:
        date = datetime.strptime(data[3].split(".")[0], "%a, %d %b %Y %H:%M:%S")
        return {
            'user': data[2].split("@")[0].strip('\\\\'),
            'datetime': date,
            'ip': data[7].split(':')[1]
        }
    return {}

def parse_log_files(log_file, pattern):
    logs = []
    with open(log_file, 'r') as f:
        for line in f.readlines():
            if pattern in line:
                data = format_log_data(line)
                # Datetime of logging is cut to the second
                # By login to a linux client, a log entry can occur many times
                # in a second, so we ignore duplicates
                if data and not data['user'].endswith("$") and not data in logs:
                    logs.append(data)
    return logs

def last_login(pattern):

    if check_audit_level():
        logs = []
        logs.extend(parse_log_files(SAMBA_LOG, pattern))
        logs.extend(parse_log_files(SAMBA_LOG_OLD, pattern))
        return logs

    return
