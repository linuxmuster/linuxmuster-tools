import re
import glob
import gzip
import logging
from datetime import datetime

from ..samba_util import SAMBA_REALM, LOG_LEVEL
from ..devices import Devices, list_schools


logger = logging.getLogger(__name__)

SAMBA_LOG = '/var/log/samba/log.samba'
SAMBA_LOG_OLD = '/var/log/samba/log.samba.1'

def check_audit_level():
    auth_audit = LOG_LEVEL.get('auth_audit', 1)
    general = LOG_LEVEL.get('general', 1)

    if auth_audit > 2:
        return True

    if general > 2:
        return True

    logger.error("Can not parse log files from samba, you need to set the log level of auth_audit at least at 3.")
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

def parse_log_content(content, pattern):
    logs = []

    for line in content:
        if isinstance(line, bytes):
            line = line.decode()

        if pattern in line:
            data = format_log_data(line)
            # Ignore machine accounts, duplicates and administrator
            if (data
                and not data['user'].endswith("$")
                and data['user'].lower() != 'administrator'
                and not data in logs):
                logs.append(data)

    return logs

def last_login(pattern, include_gz=False):
    logs = []

    if check_audit_level():
        for log_file in [SAMBA_LOG, SAMBA_LOG_OLD]:
            with open(log_file, 'r') as f:
                logs.extend(parse_log_content(f.readlines(), pattern))

        if include_gz:
            for log_file in glob.glob('/var/log/samba/log.samba*gz'):
                with gzip.open(log_file, 'rb') as f:
                    logs.extend(parse_log_content(f.readlines(), pattern))

        hostnames = {}
        for school in list_schools():
            devicesmgr = Devices(school=school)
            for device in devicesmgr.devices:
                hostnames[device['ip']] = f"{devicesmgr.hostname_prefix}{device['hostname']}"

        for entry in logs:
            entry['hostname'] = hostnames.get(entry['ip'])

    return sorted(logs, key=lambda d: d["datetime"], reverse=True)
