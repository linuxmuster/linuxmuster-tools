from ..lmnfile import LMNFile
from ..common.checks import NameChecker
from ..lmnconfig import SophomorixIni

sophomorix_ini = SophomorixIni()
CLIENT_ROLES = sophomorix_ini.clientrole
COMPUTER_ROLES = sophomorix_ini.computerrole

name_checker = NameChecker()

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
        # MS SOFTWARE KEYS ?
        # sophomorix Role valid + COMPUTER_ACCOUNT/HOST_GROUP/HOST_GROUP_TYPE flags

        report = []

        # Check values
        ip_rev = {}
        mac_rev = {}
        for device in self.devices:
            ip = device['ip']
            mac = device['mac']

            if ip in ip_rev:
                ip_rev[ip].append(device['hostname'])
            else:
                ip_rev[ip] = [device['hostname']]

            if mac in mac_rev:
                mac_rev[mac].append(device['hostname'])
            else:
                mac_rev[mac] = [device['hostname']]

            # Check values
            if not name_checker.check_ip_name(ip):
                report.append(f"{ip} is not a valid ip address")

            if not name_checker.normalize_mac(mac):
                report.append(f"{mac} is not a valid mac address")

            if not name_checker.check_group_name(device['group']):
                report.append(f"{device['group']} is not a valid Linbo group")

            if not name_checker.check_room_name(device['room']):
                report.append(f"{device['room']} is not a valid room name")

            if not name_checker.check_host_name(device['hostname']):
                report.append(f"{device['hostname']} is not a valid hostname")

            if device['pxeFlag'] not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                report.append(f"{device['pxeFlag']} is not a valid pxe flag")

            if device['sophomorixRole'] not in COMPUTER_ROLES:
                report.append(f"{device['sophomorixRole']} is not a valid computer role")

        # Check uniqueness
        for ip, hosts in ip_rev.items():
            if len(hosts) > 1:
                report.append(f"{','.join(hosts)} have the same ip {ip}")

        for mac, hosts in mac_rev.items():
            if len(hosts) > 1:
                report.append(f"{','.join(hosts)} have the same mac {mac}")

        return '\n'.join(report)




