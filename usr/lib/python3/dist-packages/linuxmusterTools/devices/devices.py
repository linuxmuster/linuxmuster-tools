from ..lmnfile import LMNFile


class Devices:
    def __init__(self, school='default-school'):
        self.school = school
        self.switch(self.school)

    def switch(self, school):
        self.school = school
        if self.school != 'default-school':
            self.prefix = f'{self.school}.'
        else:
            self.prefix = ''

        self.path = f'/etc/linuxmuster/sophomorix/{self.school}/{self.prefix}devices.csv'
        self.load()

    def load(self):
        self.devices = []

        with LMNFile(self.path, 'r') as devices_csv:
            for device in devices_csv.read():
                self.devices.append(device)

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
