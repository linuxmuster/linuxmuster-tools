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
    return LinboRemote(ips=['10.0.0.5'], cmd='sync:1', **kwargs)


def test_build_rejects_mutually_exclusive_targets():
    remote = LinboRemote(ips=['10.0.0.5'], group='win10', cmd='sync:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


def test_build_rejects_no_target():
    remote = LinboRemote(cmd='sync:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


def test_build_rejects_unknown_command():
    remote = LinboRemote(ips=['10.0.0.5'], cmd='frobnicate:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


def test_build_rejects_option_on_command_without_one():
    remote = LinboRemote(ips=['10.0.0.5'], cmd='partition:1')

    with pytest.raises(LinboRemoteParameterError):
        remote.build()


# ── LinboRemote.run() ────────────────────────────────────────────────────


def test_run_executes_the_built_command():
    remote = make_remote()

    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(returncode=0, stdout='')
        remote.run()

    args, kwargs = run.call_args
    assert args[0] == '/usr/sbin/linbo-remote -i 10.0.0.5 -c sync:1'.split()
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


def test_attach_command_uses_dot_separated_session_name():
    assert attach_command('pc001') == 'tmux attach -t pc001.linbo-remote'


def test_list_running_sessions_filters_non_linbo_remote_sessions():
    ts = 1733600000
    output = f'pc001.linbo-remote|{ts}\nsome-other-session|{ts}\n'

    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(stdout=output)
        sessions = list_running_sessions()

    assert sessions == [{
        'hostname': 'pc001',
        'session': 'pc001.linbo-remote',
        'created': datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
    }]


def test_list_running_sessions_empty_when_no_sessions():
    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run') as run:
        run.return_value = MagicMock(stdout='')
        assert list_running_sessions() == []


def test_list_running_sessions_empty_when_no_tmux_binary():
    with patch('linuxmusterTools.linbo.linbo_sync.subprocess.run', side_effect=FileNotFoundError):
        assert list_running_sessions() == []
