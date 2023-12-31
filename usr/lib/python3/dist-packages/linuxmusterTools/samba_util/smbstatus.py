import subprocess
import re
from dataclasses import dataclass, field, InitVar
from ..lmnfile import LMNFile


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
    hostnames: InitVar[dict]
    hostname: str = field(init=False)

    def __post_init__(self, hostnames):
        self.hostname = hostnames.get(self.machine, 'No hostname found')

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

class SMBConnections:
    def __init__(self, school='default-school'):
        self.school = school
        self.hostnames = self.load_hostnames()
        self.get_users()

    def switch(self, school):
        self.school = school
        self.hostnames = self.load_hostnames()

    def load_hostnames(self):
        if self.school != 'default-school':
            prefix = f'{self.school}.'
        else:
            prefix = ''

        devices_path = f'/etc/linuxmuster/sophomorix/{self.school}/{prefix}devices.csv'
        devices = {}
        with LMNFile(devices_path, 'r') as devices_csv:
            for device in devices_csv.read():
                devices[device['ip']] = device['hostname']
        return devices

    def get_users(self):
        output = subprocess.getoutput('smbstatus -b').split('\n')

        self.users = {}

        for line in output:
            match = users_regex.match(line)
            if match:
                data = match.groupdict()
                user = data['username'].split('\\')[1]
                self.users[user] = SMBConnection(group='users', hostnames=self.hostnames, **data)

    def get_machines(self):
        output = subprocess.getoutput('smbstatus -b').split('\n')

        self.machines = {}

        for line in output:
            match = machine_regex.match(line)
            if match:
                data = match.groupdict()
                machine = data['username'].split('\\')[1]
                self.machines[machine] = SMBConnection(hostnames=self.hostnames, **data)
