import subprocess
import re
from dataclasses import dataclass, field, InitVar, asdict
from ..lmnfile import LMNFile
from ..lmnconfig.server import SERVER_IP


@dataclass
class SMBConnection:
    encryption: str
    ip: str
    ip4: str
    ip6: str
    group: str
    hostname: str
    machine: str
    pid: str
    protocol: str
    room: str
    signing: str
    username: str
    version: str
    rawline: str = ''

    def as_dict(self):
        return asdict(self)

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
            # Computer accounts of the other schools are prefixed in AD
            hostname_prefix = f'{self.school}-'
        else:
            prefix = ''
            hostname_prefix = ''

        devices_path = f'/etc/linuxmuster/sophomorix/{self.school}/{prefix}devices.csv'

        devices = {}
        with LMNFile(devices_path, 'r') as devices_csv:
            for device in devices_csv.read():
                devices[device['ip']] = {
                    'hostname': f"{hostname_prefix}{device['hostname']}",
                    'room': device['room'],
                }
        return devices

    def get_users(self):
        output = subprocess.getoutput('smbstatus -b').split('\n')
        self.users = {}

        for line in output:
            match = users_regex.match(line)
            if match:
                data = match.groupdict()
                user = data['username'].split('\\')[1]
                data['hostname'] = self.hostnames.get(data['machine'], {'hostname': 'No hostname found'})['hostname']
                data['room'] = self.hostnames.get(data['machine'], {'room': 'No room found'})['room']
                if SERVER_IP != data['machine'] and f"{SERVER_IP}:" not in (data['ip4'] or ''):
                    self.users[user] = SMBConnection(group='users', rawline=line, **data)

    def get_room_users(self, username):
        """
        Get the room of the client where a user is connected, and the other
        users connected in this room. The connections opened by the server
        itself, e.g. by the Webui, are not taken into account.

        :param username: login of the user
        :type username: str
        :return: room ('' if the user is not connected to a known client), and the connections of the other users in this room
        :rtype: tuple(str, dict)
        """


        connection = self.users.get(username)
        if connection is None or connection.room == 'No room found':
            return '', {}

        users = {
            user: details
            for user, details in self.users.items()
            if details.room == connection.room and user != username
        }
        return connection.room, users

    def get_machines(self):
        output = subprocess.getoutput('smbstatus -b').split('\n')

        self.machines = {}

        for line in output:
            match = machine_regex.match(line)
            if match:
                data = match.groupdict()
                machine = data['username'].split('\\')[1]
                data['hostname'] = self.hostnames.get(machine, {'hostname': 'No hostname found'})['hostname']
                data['room'] = self.hostnames.get(machine, {'room': 'No room found'})['room']
                self.machines[machine] = SMBConnection(rawline=line, **data)
