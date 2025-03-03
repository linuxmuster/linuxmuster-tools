from ..lmnfile import LMNFile
from ..common.checks import NameChecker


name_checker = NameChecker()

# TODO: should be loaded, not hardcoded
CLIENT_ROLES = [
    'classroom-teachercomputer',
    'classroom-studentcomputer',
    'faculty-teachercomputer',
    'staffcomputer',
    'thinclient',
    'iponly',
]

class Devices:
    def __init__(self, school='default-school'):
        self.school = school
        self.switch(self.school)

    def switch(self, school):
        self.school = school
        if self.school != 'default-school':
            self.prefix = f'{self.school}.'
        else:
            self.prefix = 'dev-'

        self.path = f'/etc/linuxmuster/sophomorix/{self.school}/{self.prefix}devices.csv'
        self.load()

    def load(self):
        self.devices = []

        with LMNFile(self.path, 'r') as devices_csv:
            for device in devices_csv.read():
                if not device['room'].startswith('#'):
                    self.devices.append(device)

        self.groups = list(set([d['group'] for d in self.devices if d.get('group', False)]))
        self.rooms = list(set([d['room'] for d in self.devices if d.get('room', False)]))
        self.clients = self.filter(roles=CLIENT_ROLES)

    def filter(self, roles=[], groups=[]):
        if roles and groups:
            return [device for device in self.devices if device['sophomorixRole'] in roles and device['group'] in groups]
        elif roles:
            return [device for device in self.devices if device['sophomorixRole'] in roles]
        elif groups:
            return [device for device in self.devices if device['group'] in groups]
        return self.devices

    def get_hostname(self, hostname, roles=[], groups=[]):
        for device in self.filter(roles, groups):
            if device['hostname'] == hostname:
                return device
        return None

    def get_client(self, hostname, groups=[]):
        return self.get_hostname(hostname, roles=CLIENT_ROLES, groups=groups)

    def get_clients(self, groups=[]):
        return self.filter(roles=CLIENT_ROLES, groups=groups)

    def check_conf(self):
        # TODO check
        # ROOM/HOST: A-Za-z0-9\-
        # LINBO group: A-Za-z0-9\-_
        # MAC: values
        # IP: values
        # MS SOFTWARE KEYS ?
        # sophomorix Role valid + COMPUTER_ACCOUNT/HOST_GROUP/HOST_GROUP_TYPE flags
        # PXE: 0-9

        report = []

        # Check uniqueness
        ip_rev = {}
        mac_rev = {}
        for device in self.devices:
            if device['ip'] in ip_rev:
                ip_rev[device['ip']].append(device['hostname'])
            else:
                ip_rev[device['ip']] = [device['hostname']]

            if device['mac'] in mac_rev:
                mac_rev[device['mac']].append(device['hostname'])
            else:
                mac_rev[device['mac']] = [device['hostname']]

        for ip, hosts in ip_rev.items():
            if len(hosts) > 1:
                report.append(f"{','.join(hosts)} have the same ip {ip}")

        for mac, hosts in mac_rev.items():
            if len(hosts) > 1:
                report.append(f"{','.join(hosts)} have the same mac {mac}")

        return '\n'.join(report)




