"""
LINBO remote commands — build, run and track linbo-remote sessions.

linbo-remote sends actions (format/sync/start/halt/...) to hosts over ssh.
Each run happens in a detached tmux session, in a script-visible variable
named "<hostname>.linbo-remote".
"""

import subprocess
from datetime import datetime, timezone

from ..devices import Devices
from ..ldapconnector import LMNLdapReader as lr
from .config import LinboConfigManager, read_config


SESSION_SUFFIX = '_linbo-remote'


class LinboRemoteParameterError(ValueError):
    """Raised when LinboRemote is given an invalid or inconsistent parameter."""


# TODO:
#  - add support for remote linbo server (per ssh)

class LinboRemote:
    """
    Build and run a linbo-remote command against a host, group or room.
    """


    BASE_COMMAND = '/usr/sbin/linbo-remote'
    SUPPORTED_COMMANDS = {
        'partition': {'nr': False, 'msg': False},
        'label': {'nr': False, 'msg': False},
        'format': {'nr': True, 'msg': False},
        'initcache': {'nr': False, 'msg': False, 'type': ['rsync', 'multicast', 'torrent']},
        'sync': {'nr': True, 'msg': False},
        'new': {'nr': True, 'msg': False},
        'postsync': {'nr': True, 'msg': False},
        'start': {'nr': True, 'msg': False},
        'prestart': {'nr': True, 'msg': False},
        'create_image': {'nr': True, 'msg': True},
        'upload_image': {'nr': True, 'msg': False},
        'create_qdiff': {'nr': True, 'msg': True},
        'upload_qdiff': {'nr': True, 'msg': False},
        'reboot': {'nr': False, 'msg': False},
        'halt': {'nr': False, 'msg': False},
    }


    def __init__(
            self,
            wait=0,                     # -b
            cmd='',                     # -c
            disable_gui=False,          # -d
            group=None,                 # -g
            clients=[],                 # -i, ip or hostname
            bypass=None,                # -n
            room=None,                  # -r
            school=None,                # -s
            onboot=False,               # -p
            wol=0,                      # -w
            broadcast=None,             # -u
    ):
        self.wait = wait
        self.cmd = cmd
        self.disable_gui = disable_gui
        self.group = group
        self.clients = clients
        self.bypass = bypass
        self.room = room
        self.school = school
        self.onboot = onboot
        self.wol = wol
        self.broadcast = broadcast

        self.built_cmd = ''

    def _check_args(self):
        if not isinstance(self.wait, int) or not isinstance(self.wol, int):
            raise LinboRemoteParameterError(f'If given, wait and wol must be positive integer.')

        if self.wait < 0 or self.wol < 0:
            raise LinboRemoteParameterError(f'If given, wait and wol must be positive integer.')

        if self.wait and not self.wol:
            raise LinboRemoteParameterError(f'If parameter wait is given, wol must be given too.')

        if self.broadcast and not isinstance(self.broadcast, bool):
            raise LinboRemoteParameterError(f'broadcast must be a boolean.')

        if self.bypass and not isinstance(self.bypass, bool):
            raise LinboRemoteParameterError(f'bypass must be a boolean.')

        if self.school and self.school not in lr.getval('/schools', 'ou'):
            raise LinboRemoteParameterError(f'{self.school} is not a valid school.')

        if self.clients and self.group:
            raise LinboRemoteParameterError(f"group and clients are mutually exclusive.")

        if self.clients and self.room:
            raise LinboRemoteParameterError(f"room and clients are mutually exclusive.")

        if self.room and self.group:
            raise LinboRemoteParameterError(f"group and room are mutually exclusive.")

        if not self.clients and not self.room and not self.group:
            raise LinboRemoteParameterError(f"Specify at least a group, a room or a client.")

    # Commands whose nr is a position in start.conf's [OS] list, not a partition number.
    NR_OS_POSITION_COMMANDS = {
        'new', 'sync', 'postsync', 'start', 'prestart',
        'create_image', 'upload_image', 'create_qdiff', 'upload_qdiff',
    }

    def _target_groups(self):
        """
        Resolve the linbo group(s) actually targeted by this command, so nr
        can be checked against every start.conf involved — a room or a
        clients list can span hosts from different groups.

        clients is matched against ip, hostname and school-prefixed
        hostname, since -i (like this method) accepts either an ip or a
        hostname.

        :return: Set of group names.
        :rtype: set of str
        """

        if self.group:
            return {self.group}

        school = self.school or 'default-school'
        devices = Devices(school=school)

        if self.room:
            return {d['group'] for d in devices.devices if d['room'] == self.room}

        def is_targeted(device):
            if device['ip'] in self.clients:
                return True
            hostname = device['hostname']
            prefixed = f'{school}-{hostname}' if school != 'default-school' else hostname
            return hostname in self.clients or prefixed in self.clients

        return {d['group'] for d in devices.devices if is_targeted(d)}

    def _check_nr(self, name, nr):
        """
        Check that nr matches an actual position in the start.conf of every
        group targeted by this command.
        """

        if not nr.isdigit():
            raise LinboRemoteParameterError(f'{nr} is not a valid position for {name}.')

        groups = self._target_groups()
        if not groups:
            raise LinboRemoteParameterError(f'Could not resolve any group for the given target.')

        # Only needed for 'format': the partition count of a group, from its
        # [Partition] sections (nr for other commands is an [OS] position,
        # already available from read_config below).
        startconf_mgr = LinboConfigManager() if name == 'format' else None

        for group in groups:
            config = read_config(group)
            if not config:
                raise LinboRemoteParameterError(f'No start.conf for group {group}.')

            if name == 'format':
                linbo_config = startconf_mgr.linbo_configs.get(group)
                nr_partitions = len(linbo_config.Partitions) if linbo_config else 0
                if not (1 <= int(nr) <= nr_partitions):
                    raise LinboRemoteParameterError(f'No partition {nr} in start.conf.{group}.')
            elif name in self.NR_OS_POSITION_COMMANDS and not (1 <= int(nr) <= len(config)):
                raise LinboRemoteParameterError(f'No OS at position {nr} in start.conf.{group}.')

    def _check_cmd(self):
        if not self.cmd:
            raise LinboRemoteParameterError(f'cmd must be given.')

        for cmd in self.cmd.split(','):
            args = cmd.split(':')
            if len(args) == 3:
                name, nr, msg = args
            elif len(args) == 2:
                name, nr = args
                msg = None
            elif len(args) == 1:
                name, nr, msg = args[0], None, None
            else:
                # Wrong number of args
                raise LinboRemoteParameterError(f'Invalid number of options for the command {cmd}')

            if name not in self.SUPPORTED_COMMANDS:
                raise LinboRemoteParameterError(f'Command {name} unknown.')

            if nr and not self.SUPPORTED_COMMANDS[name]['nr']:
                raise LinboRemoteParameterError(f'Command {name} does not support any option.')

            if msg and not self.SUPPORTED_COMMANDS[name]['msg']:
                raise LinboRemoteParameterError(f'Command {name} does not accept a message.')

            if name == 'initcache' and nr not in self.SUPPORTED_COMMANDS['initcache']['type']:
                raise LinboRemoteParameterError(f'Wrong type {nr} for the command initcache.')

            if nr and name != 'initcache':
                self._check_nr(name, nr)

    def build(self):
        self._check_args()
        self._check_cmd()

        self.built_cmd = self.BASE_COMMAND

        if self.wait:
            self.built_cmd += f' -b {self.wait} -w {self.wol}'
        elif self.wol:
            self.built_cmd += f' -w {self.wol}'

        if self.broadcast:
            self.built_cmd += f' -u'

        if self.bypass:
            self.built_cmd += f' -n'

        if self.room:
            self.built_cmd += f' -r {self.room}'
        elif self.group:
            self.built_cmd += f' -g {self.group}'
        else:
            self.built_cmd += f' -i {','.join(self.clients)}'

        if self.school:
            self.built_cmd += f' -s {self.school}'

        if self.disable_gui:
            self.built_cmd += f' -d'

        if self.onboot:
            self.built_cmd += f' -p'
        else:
            self.built_cmd += f' -c'

        self.built_cmd += f' {self.cmd}'

    def run(self):
        """
        Build and run the linbo-remote command.

        :return: Status dict {'status': 0, 'msg': <command output>} on success,
            or {'status': 1, 'msg': <error>} if some hosts were offline.
        :rtype: dict
        :raises LinboRemoteParameterError: if linbo-remote itself rejected the
            command line (e.g. unknown group/room, no valid host in a -i list,
            missing command) — it validates clients/group/room and exits
            non-zero before running anything in that case.
        """

        self.build()

        result = subprocess.run(
            self.built_cmd.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output = result.stdout

        if result.returncode != 0:
            error = output.strip().splitlines()[-1] if output.strip() else 'linbo-remote failed with no output.'
            raise LinboRemoteParameterError(error)

        if 'Not online, host skipped.' in output:
            offline_hosts = [
                line.split()[0]
                for line in output.split('\n')
                if 'Not online, host skipped.' in line
            ]
            return {'status': 1, 'msg': f"Not online, host skipped: {','.join(offline_hosts)}"}

        return {'status': 0, 'msg': output}


def list_running_sessions() -> list[dict]:
    """
    List currently running linbo-remote tmux sessions.

    :return: List of {hostname, session, created} dicts, one per active
        linbo-remote session. Empty list if none are running, or if no
        tmux server is running at all.
    :rtype: list of dict
    """

    try:
        result = subprocess.run(
            ['tmux', 'list-sessions', '-F', '#{session_name}|#{session_created}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        return []

    sessions = []
    for line in result.stdout.splitlines():
        name, _, created = line.partition('|')
        if not created or not name.endswith(SESSION_SUFFIX):
            continue
        sessions.append({
            'hostname': name[:-len(SESSION_SUFFIX)],
            'session': name,
            'created': datetime.fromtimestamp(int(created), tz=timezone.utc).isoformat(),
        })
    return sessions


def attach_command(hostname: str) -> str:
    """
    Build the tmux attach command for a host's running linbo-remote session.

    Not meant to be run through a web request: `tmux attach` needs an
    interactive terminal (a pty), which a stateless HTTP call can't provide.
    Exposed so a future terminal-in-browser feature (websocket + pty) has
    the exact session name to attach to.

    :param hostname: Hostname whose session to attach to
    :type hostname: str
    :return: Shell command string, e.g. "tmux attach -t pc001_linbo-remote"
    :rtype: str
    """

    return f'tmux attach -t {hostname}{SESSION_SUFFIX}'
