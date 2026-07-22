from unittest.mock import mock_open, patch

import pytest

import linuxmusterTools.smbclient.smbclient as smbclient_module
from linuxmusterTools.smbclient.smbclient import LMNSMBClient


# ---------------------------------------------------------------------------
# __init__ / switch()
# ---------------------------------------------------------------------------

def test_init_with_default_school():
    client = LMNSMBClient()
    assert client.school == 'default-school'


def test_init_with_valid_school():
    client = LMNSMBClient('school2')
    assert client.school == 'school2'


def test_init_with_invalid_school_raises():
    with pytest.raises(Exception, match="not found"):
        LMNSMBClient('unknown-school')


def test_switch_to_valid_school():
    client = LMNSMBClient()
    client.switch('school2')
    assert client.school == 'school2'


def test_switch_to_invalid_school_raises():
    client = LMNSMBClient()
    with pytest.raises(Exception, match="not found"):
        client.switch('unknown-school')
    # the previous, valid school should be left untouched
    assert client.school == 'default-school'


# ---------------------------------------------------------------------------
# _execute()
# ---------------------------------------------------------------------------

def test_execute_reads_secret_and_runs_smbclient(monkeypatch):
    captured = {}

    class FakeProcess:
        def communicate(self):
            return (b'some smbclient output', b'')

    def fake_popen(cmd, stdout=None, stderr=None, shell=None):
        captured['cmd'] = cmd
        captured['stdout'] = stdout
        captured['stderr'] = stderr
        captured['shell'] = shell
        return FakeProcess()

    monkeypatch.setattr(smbclient_module.subprocess, 'Popen', fake_popen)

    client = LMNSMBClient('default-school')

    with patch('builtins.open', mock_open(read_data='s3cr3t\n')):
        result = client._execute('dir "foo/*";')

    assert result == b'some smbclient output'

    cmd = captured['cmd']
    assert cmd[0] == '/bin/smbclient'
    assert cmd[1] == '-U administrator%s3cr3t'
    assert cmd[2] == f'//{smbclient_module.SAMBA_DOMAIN}/default-school'
    assert cmd[3] == '-c'
    assert cmd[4] == 'dir "foo/*";'
    assert captured['shell'] is False


def test_execute_strips_secret_newline_and_whitespace(monkeypatch):
    captured = {}

    class FakeProcess:
        def communicate(self):
            return (b'', b'')

    def fake_popen(cmd, stdout=None, stderr=None, shell=None):
        captured['cmd'] = cmd
        return FakeProcess()

    monkeypatch.setattr(smbclient_module.subprocess, 'Popen', fake_popen)

    client = LMNSMBClient('default-school')

    # trailing whitespace/newline in the secret file must be stripped
    with patch('builtins.open', mock_open(read_data='  topsecret  \n')):
        client._execute('deltree "x";')

    assert captured['cmd'][1] == '-U administrator%topsecret'


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------

def _dir_output(*lines):
    return ('\n'.join(lines)).encode()


def test_list_returns_files_and_directories(monkeypatch):
    output = _dir_output(
        '  .                                   D        0  Mon Jan  1 00:00:00 2024',
        '  ..                                  D        0  Mon Jan  1 00:00:00 2024',
        '  file1.txt                           N     1234  Mon Jan  1 00:00:00 2024',
        '  subdir                              D        0  Mon Jan  1 00:00:00 2024',
        '',
        '\t\t36330 blocks of size 1024. 12345 blocks available',
    )

    client = LMNSMBClient('default-school')
    monkeypatch.setattr(client, '_execute', lambda cmd: output)

    result = client.list('students/10a/myuser/transfer')

    assert result == [
        {'name': '.', 'type': 'directory', 'size': '0'},
        {'name': '..', 'type': 'directory', 'size': '0'},
        {'name': 'file1.txt', 'type': 'file', 'size': '1234'},
        {'name': 'subdir', 'type': 'directory', 'size': '0'},
    ]


def test_list_builds_correct_dir_command(monkeypatch):
    captured = {}

    def fake_execute(cmd):
        captured['cmd'] = cmd
        return _dir_output(
            '  .                                   D        0  Mon Jan  1 00:00:00 2024',
            '',
        )

    client = LMNSMBClient('default-school')
    monkeypatch.setattr(client, '_execute', fake_execute)

    client.list('students/10a/myuser/transfer')

    assert captured['cmd'] == 'dir "students/10a/myuser/transfer/*";'


def test_list_raises_when_first_entry_is_not_dot(monkeypatch):
    # smbclient can return exit code 0 even on error; the only tell is that
    # the first listed entry isn't '.'
    output = _dir_output(
        'NT_STATUS_ACCESS_DENIED listing \\students\\10a\\myuser\\transfer\\*',
        '',
    )

    client = LMNSMBClient('default-school')
    monkeypatch.setattr(client, '_execute', lambda cmd: output)

    with pytest.raises(Exception, match="There was a problem"):
        client.list('students/10a/myuser/transfer')


def test_list_stops_on_malformed_trailing_line(monkeypatch):
    # a well-formed first entry followed by a line with too few fields:
    # parsing should stop (IndexError -> break) instead of raising or
    # including bogus/partial entries, and entries after the malformed
    # line are never reached.
    output = _dir_output(
        '  .                                   D        0  Mon Jan  1 00:00:00 2024',
        '  truncated',
        '  file1.txt                           N     1234  Mon Jan  1 00:00:00 2024',
    )

    client = LMNSMBClient('default-school')
    monkeypatch.setattr(client, '_execute', lambda cmd: output)

    result = client.list('students/10a/myuser/transfer')

    assert result == [{'name': '.', 'type': 'directory', 'size': '0'}]


# ---------------------------------------------------------------------------
# deltree()
# ---------------------------------------------------------------------------

def test_deltree_builds_correct_command(monkeypatch):
    captured = {}

    def fake_execute(cmd):
        captured['cmd'] = cmd
        return b''

    client = LMNSMBClient('default-school')
    monkeypatch.setattr(client, '_execute', fake_execute)

    result = client.deltree('students/attic/myuser')

    assert captured['cmd'] == 'deltree "students/attic/myuser";'
    assert result is None
