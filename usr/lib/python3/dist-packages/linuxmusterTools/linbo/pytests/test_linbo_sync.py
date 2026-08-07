"""
Tests for linuxmusterTools.linbo.linbo_sync: building/running a linbo-remote
command (LinboRemote) and listing its running tmux sessions.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from linuxmusterTools.linbo.linbo_sync import (
    LinboRemote,
    LinboRemoteParameterError,
    attach_command,
    list_running_sessions,
)


# ── LinboRemote parameter validation ────────────────────────────────────


def make_remote(**kwargs):
    # cmd has no nr on purpose: LinboRemote.run() tests below aren't about nr
    # validation and shouldn't need to resolve a group via Devices/devices.csv.
    return LinboRemote(clients=['10.0.0.5'], cmd='reboot', **kwargs)


def test_build_rejects_mutually_exclusive_targets():
    remote = LinboRemote(clients=['10.0.0.5'], group='win10', cmd='sync:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


def test_build_rejects_no_target():
    remote = LinboRemote(cmd='sync:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


def test_build_rejects_unknown_command():
    remote = LinboRemote(clients=['10.0.0.5'], cmd='frobnicate:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


def test_build_rejects_option_on_command_without_one():
    remote = LinboRemote(clients=['10.0.0.5'], cmd='partition:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


# ── LinboRemote nr validation against start.conf ────────────────────────


OS_CONFIG = [
    {'BaseImage': 'a.qcow2', 'Root': '/dev/sda1'},
    {'BaseImage': 'b.qcow2', 'Root': '/dev/sda2'},
]


def test_check_nr_accepts_valid_os_position():
    remote = LinboRemote(group='win10', cmd='sync:2')

    with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
        remote.build()  # must not raise


def test_check_nr_rejects_out_of_range_os_position():
    remote = LinboRemote(group='win10', cmd='sync:5')

    with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
        with pytest.raises(LinboRemoteParameterError):
            remote.build()


def make_fake_startconf_mgr(group, partitions_count):
    linbo_config = MagicMock()
    linbo_config.Partitions = [MagicMock() for _ in range(partitions_count)]
    mgr = MagicMock()
    mgr.linbo_configs = {group: linbo_config}
    return mgr


def test_check_nr_accepts_valid_partition_for_format():
    remote = LinboRemote(group='win10', cmd='format:2')

    with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
        with patch(
            'linuxmusterTools.linbo.linbo_sync.LinboConfigManager',
            return_value=make_fake_startconf_mgr('win10', 2),
        ):
            remote.build()  # must not raise


def test_check_nr_rejects_unknown_partition_for_format():
    remote = LinboRemote(group='win10', cmd='format:9')

    with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
        with patch(
            'linuxmusterTools.linbo.linbo_sync.LinboConfigManager',
            return_value=make_fake_startconf_mgr('win10', 2),
        ):
            with pytest.raises(LinboRemoteParameterError):
                remote.build()


def test_check_nr_rejects_missing_start_conf():
    remote = LinboRemote(group='win10', cmd='sync:1')

    with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=None):
        with pytest.raises(LinboRemoteParameterError):
            remote.build()


def make_fake_devices(devices_list):
    fake = MagicMock()
    fake.devices = devices_list
    return fake


def test_check_nr_resolves_group_from_ip():
    devices = [{'ip': '10.0.0.5', 'hostname': 'pc001', 'group': 'win10', 'room': 'room1'}]
    remote = LinboRemote(clients=['10.0.0.5'], cmd='sync:2')

    with patch('linuxmusterTools.linbo.linbo_sync.Devices', return_value=make_fake_devices(devices)):
        with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
            remote.build()  # must not raise


def test_check_nr_resolves_group_from_hostname():
    devices = [{'ip': '10.0.0.5', 'hostname': 'pc001', 'group': 'win10', 'room': 'room1'}]
    remote = LinboRemote(clients=['pc001'], cmd='sync:2')

    with patch('linuxmusterTools.linbo.linbo_sync.Devices', return_value=make_fake_devices(devices)):
        with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
            remote.build()  # must not raise


def test_check_nr_resolves_group_from_school_prefixed_hostname():
    devices = [{'ip': '10.0.0.5', 'hostname': 'pc001', 'group': 'win10', 'room': 'room1'}]
    remote = LinboRemote(clients=['lehrer-pc001'], cmd='sync:2', school='lehrer')

    with patch('linuxmusterTools.linbo.linbo_sync.lr.getval', return_value=['lehrer']):
        with patch('linuxmusterTools.linbo.linbo_sync.Devices', return_value=make_fake_devices(devices)):
            with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
                remote.build()  # must not raise


def test_check_nr_rejects_out_of_range_for_ip_resolved_group():
    devices = [{'ip': '10.0.0.5', 'hostname': 'pc001', 'group': 'win10', 'room': 'room1'}]
    remote = LinboRemote(clients=['10.0.0.5'], cmd='sync:5')

    with patch('linuxmusterTools.linbo.linbo_sync.Devices', return_value=make_fake_devices(devices)):
        with patch('linuxmusterTools.linbo.linbo_sync.read_config', return_value=OS_CONFIG):
            with pytest.raises(LinboRemoteParameterError):
                remote.build()


def test_check_nr_checks_every_group_in_a_room():
    devices = [
        {'ip': '10.0.0.5', 'hostname': 'pc001', 'group': 'win10', 'room': 'room1'},
        {'ip': '10.0.0.6', 'hostname': 'pc002', 'group': 'linux', 'room': 'room1'},
    ]
    remote = LinboRemote(room='room1', cmd='sync:2')

    def fake_read_config(group):
        return OS_CONFIG if group == 'win10' else OS_CONFIG[:1]

    with patch('linuxmusterTools.linbo.linbo_sync.Devices', return_value=make_fake_devices(devices)):
        with patch('linuxmusterTools.linbo.linbo_sync.read_config', side_effect=fake_read_config):
            # position 2 doesn't exist for the 'linux' group (only 1 OS there)
            with pytest.raises(LinboRemoteParameterError):
                remote.build()


def test_check_nr_rejects_when_group_cannot_be_resolved():
    remote = LinboRemote(clients=['10.0.0.5'], cmd='sync:1')

    with patch('linuxmusterTools.linbo.linbo_sync.Devices', return_value=make_fake_devices([])):
        with pytest.raises(LinboRemoteParameterError):
            remote.build()


# ── LinboRemote.run() ────────────────────────────────────────────────────


def test_run_executes_the_built_command():
    remote = make_remote()

    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout='')
        remote.run()

    args, kwargs = run.call_args
    assert args[0] == '/usr/sbin/linbo-remote -i 10.0.0.5 -c reboot'.split()
    assert kwargs['stderr'] is not None
    assert kwargs['text'] is True


def test_run_returns_success_status():
    remote = make_remote()

    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout='Started with PID 123.\n')
        result = remote.run()

    assert result == {'status': 0, 'msg': 'Started with PID 123.\n'}


def test_run_detects_offline_hosts():
    remote = make_remote()
    output = 'pc001 Not online, host skipped.\npc002 Not online, host skipped.\n'

    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout=output)
        result = remote.run()

    assert result == {'status': 1, 'msg': 'Not online, host skipped: pc001,pc002'}


def test_run_raises_on_nonzero_exit():
    remote = make_remote()
    output = (
        'Usage: linbo-remote <options>\n'
        '...\n'
        '\n'
        'No hosts in group win10!'
    )

    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(returncode=1, stdout=output)
        with pytest.raises(LinboRemoteParameterError, match='No hosts in group win10!'):
            remote.run()


# ── list_running_sessions() / attach_command() ──────────────────────────


def test_attach_command_uses_underscore_separated_session_name():
    # tmux itself replaces the dot with an underscore in session names
    # (dots are significant in its session:window.pane target syntax) —
    # verified against a live tmux server, see the module docstring.
    assert attach_command('pc001') == 'tmux attach -t pc001_linbo-remote'


def test_list_running_sessions_filters_non_linbo_remote_sessions():
    ts = 1733600000
    output = f'pc001_linbo-remote|{ts}\nsome-other-session|{ts}\n'

    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(stdout=output)
        sessions = list_running_sessions()

    assert sessions == [{
        'hostname': 'pc001',
        'session': 'pc001_linbo-remote',
        'created': datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
    }]


def test_list_running_sessions_empty_when_no_sessions():
    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(stdout='')
        assert list_running_sessions() == []


def test_list_running_sessions_empty_when_no_tmux_binary():
    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run', side_effect=FileNotFoundError):
        assert list_running_sessions() == []
