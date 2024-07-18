import re
import logging

from ..samba_util import SAMBA_REALM, LOG_LEVEL


SAMBA_LOG = '/var/log/samba/log.samba'
SAMBA_LOG_OLD = '/var/log/samba/log.samba.1'

def format_log_data(entry):
    data = re.findall(r"\[([^\]]*)\]", entry)
    if "@" in data[2]:
        return {
            'user': data[2].split("@")[0].strip('\\\\'),
            'datetime': data[3],
            'ip': data[7].split(':')[1]
        }
    return {}

def parse_log_files(log_file, pattern):
    logs = []
    with open(log_file, 'r') as f:
        for line in f.readlines():
            if pattern in line:
                data = format_log_data(line)
                if data and not data['user'].endswith("$"):
                    logs.append(data)
    return logs

def last_login(pattern):
    logs = []
    logs.extend(parse_log_files(SAMBA_LOG, pattern))
    logs.extend(parse_log_files(SAMBA_LOG_OLD, pattern))
    for entry in logs:
        print(f"{entry['user']:25}|{entry['ip']:20}|{entry['datetime']}")
    return logs

