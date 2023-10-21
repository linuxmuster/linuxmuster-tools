import subprocess
import re
from dataclasses import dataclass


@dataclass
class SMBConnection:
    encryption: str
    ip: str
    ip4: str
    ip6: str
    group: str
    machine: str
    pid: str
    protocol: str
    signing: str
    username: str
    version: str

users_regex = re.compile(
    r"(?P<pid>[0-9]+)\s+"
    r"(?P<username>\S+)\s+"
    r"users\s+"
    r"(?P<machine>\S+)\s+"
    r"\(((?P<ip>[0-9a-fA-F.:]+)|"
    r"ipv4:(?P<ip4>[0-9a-fA-F.:]+)|"
    r"ipv6:(?P<ip6>[0-9a-fA-F:]+))\)\s+"
    r"(?P<protocol>\S+)\s+"
    r"(?P<version>.*)\s+"
    r"(?P<encryption>\S+)\s+"
    r"(?P<signing>\S+)\s*"
)

machine_regex = re.compile(
    r"(?P<pid>[0-9]+)\s+"
    r"(?P<username>\S+)\s+"
    r"(?P<group>[a-zA-Z0-9\-._]+\\domain computers)\s+"
    r"(?P<machine>\S+)\s+" 
    r"\(((?P<ip>[0-9a-fA-F.:]+)|"
    r"ipv4:(?P<ip4>[0-9a-fA-F.:]+)|"
    r"ipv6:(?P<ip6>[0-9a-fA-F:]+))\)\s+"
    r"(?P<protocol>\S+)\s+"
    r"(?P<version>.*)\s+"
    r"(?P<encryption>\S+)\s+"
    r"(?P<signing>\S+)\s*"
)

def get_logged_users():
    output = subprocess.getoutput('smbstatus -b').split('\n')

    users = []

    for line in output:
        match = users_regex.match(line)
        if match:
            data = match.groupdict()
            users.append(SMBConnection(group='users', **data))

    return users

def get_logged_machines():
    output = subprocess.getoutput('smbstatus -b').split('\n')

    machines = []

    for line in output:
        match = machine_regex.match(line)
        if match:
            data = match.groupdict()
            machines.append(SMBConnection(**data))

    return machines
