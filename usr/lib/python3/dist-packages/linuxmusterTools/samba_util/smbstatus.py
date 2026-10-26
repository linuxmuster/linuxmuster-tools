import json
import subprocess
from dataclasses import dataclass, field, InitVar, asdict
from datetime import datetime
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
    auth_time: str = ''

    def as_dict(self):
        return asdict(self)

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

    @staticmethod
    def _sessions():
        """
        Get the sessions listed by `smbstatus -b -j`.

        :return: all sessions, empty if smbstatus fails (e.g. not run as root)
        :rtype: list of SMBConnection
        """


        output = subprocess.getoutput('smbstatus -b -j')
        try:
            sessions = json.loads(output).get('sessions', {})
        except json.JSONDecodeError:
            return []

        connections = []
        for session in sessions.values():
            # e.g. 'ipv4:10.0.0.102:50682'
            family, _, address = session['hostname'].partition(':')
            connections.append(SMBConnection(
                auth_time=session['auth_time'],
                encryption=session['encryption']['cipher'],
                group=session['groupname'],
                hostname='No hostname found',
                ip=None if family in ('ipv4', 'ipv6') else session['hostname'],
                ip4=address if family == 'ipv4' else None,
                ip6=address if family == 'ipv6' else None,
                machine=session['remote_machine'],
                pid=session['server_id']['pid'],
                protocol=session['session_dialect'],
                room='No room found',
                signing=session['signing']['cipher'],
                username=session['username'],
                version='',
            ))
        return connections

    @staticmethod
    def _latest(connections):
        """
        Get the most recent samba connection opened on the server.
        """


        return max(connections, key=lambda c: datetime.fromisoformat(c.auth_time))

    def get_users(self):
        """
        Get the connections of the users on the clients. A client opens
        several sessions for a user, only the most recent one per ip is kept.

        - self.connections: all connections of each user, one per ip
        - self.users: the most recent connection of each user

        The connections opened by the server itself, e.g. by the Webui, are
        not taken into account.
        """


        connections = {}

        for connection in self._sessions():
            if connection.group.endswith('\\domain computers') or '\\' not in connection.username:
                continue

            if connection.machine == SERVER_IP or (connection.ip4 or '').startswith(f"{SERVER_IP}:"):
                continue

            user = connection.username.split('\\')[1]
            device = self.hostnames.get(connection.machine, {})
            connection.hostname = device.get('hostname', connection.hostname)
            connection.room = device.get('room', connection.room)
            connections.setdefault(user, {}).setdefault(connection.machine, []).append(connection)

        self.connections = {
            user: [self._latest(sessions) for sessions in by_ip.values()]
            for user, by_ip in connections.items()
        }
        self.users = {
            user: self._latest(user_connections)
            for user, user_connections in self.connections.items()
        }

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
        """
        Get the connections of the computer accounts, the most recent one for
        each machine.
        """

        machines = {}

        for connection in self._sessions():
            if not connection.group.endswith('\\domain computers'):
                continue

            machine = connection.username.split('\\')[1]
            device = self.hostnames.get(machine, {})
            connection.hostname = device.get('hostname', connection.hostname)
            connection.room = device.get('room', connection.room)
            machines.setdefault(machine, []).append(connection)

        self.machines = {
            machine: self._latest(connections)
            for machine, connections in machines.items()
        }
