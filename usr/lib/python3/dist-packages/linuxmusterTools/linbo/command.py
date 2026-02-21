
from ..ldapconnector import LMNLdapReader as lr


class LinboRemote:
    """
    Generate a linbo-remote command to send to an host.
    Commands to manage actual linbo-remote processes are here not represented
    (options like -a or -l).
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
            ips=[],                     # -i
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
        self.ips = ips
        self.bypass = bypass
        self.room = room
        self.school = school
        self.onboot = onboot
        self.wol = wol
        self.broadcast = broadcast

        self.built_cmd = ''

    def _check_args(self):
        if not isinstance(self.wait, int) or not isinstance(self.wol, int):
            raise Exception(f'If given, wait and wol must be positive integer.')

        if self.wait < 0 or self.wol < 0:
            raise Exception(f'If given, wait and wol must be positive integer.')

        if self.wait and not self.wol:
            raise Exception(f'If parameter wait is given, wol must be given too.')

        if self.broadcast and not isinstance(self.broadcast, bool):
            raise Exception(f'broadcast must be a boolean.')

        if self.bypass and not isinstance(self.bypass, bool):
            raise Exception(f'bypass must be a boolean.')

        if self.school and self.school not in lr.getval('/schools', 'ou'):
            raise Exception(f'{self.school} is not a valid school.')

        # Check valid ips, group and room too ?

        if self.ips and self.group:
            raise Exception(f"group and ips are mutually exclusive.")

        if self.ips and self.room:
            raise Exception(f"room and ips are mutually exclusive.")

        if self.room and self.group:
            raise Exception(f"group and room are mutually exclusive.")

        if not self.ips and not self.room and not self.group:
            raise Exception(f"Specify at least a group, a room or an ip.")

    def _check_cmd(self):
        if not self.cmd:
            raise Exception(f'cmd must be given.')

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
                raise Exception(f'Invalid number of options for the command {cmd}')

            if name not in self.SUPPORTED_COMMANDS:
                raise Exception(f'Command {name} unknown.')

            if nr and not self.SUPPORTED_COMMANDS[name]['nr']:
                # Check linbo config too ?
                # Avoid errors like sync:5
                raise Exception(f'Command {name} does not support any option.')

            if msg and not self.SUPPORTED_COMMANDS[name]['msg']:
                raise Exception(f'Command {name} does not accept a message.')

            if name == 'initcache' and nr not in self.SUPPORTED_COMMANDS['initcache']['type']:
                raise Exception(f'Wrong type {nr} for the command initcache.')

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
            self.built_cmd += f' -i {','.join(self.ips)}'

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
        self.build()
        pass