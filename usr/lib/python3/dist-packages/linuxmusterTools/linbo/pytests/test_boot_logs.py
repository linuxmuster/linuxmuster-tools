"""
Tests for LinboBootLogs, and above all for the host a log file names: that is
what lets a caller keep only the logs of one school's machines.
"""

import pytest

from linuxmusterTools.linbo.boot_logs import LinboBootLogs


def hostname_of(tmp_path, filename):
    """The host list_logs() attributes a file to."""

    (tmp_path / filename).write_text('log\n')
    logs = {log['filename']: log['hostname'] for log in LinboBootLogs(str(tmp_path)).list_logs()}
    return logs[filename]


@pytest.mark.parametrize('filename, hostname', [
    ('client1_linbo.log', 'client1'),
    ('client1_image.log', 'client1'),
    ('client1_image.log.1.gz', 'client1'),
    ('client1_image.status', 'client1'),
    ('client1_hwinfo.gz', 'client1'),
    ('client1.linbo-remote', 'client1'),
    ('gym-pc01_linbo.log', 'gym-pc01'),
])
def test_hostname_is_read_from_the_file_name(tmp_path, filename, hostname):
    assert hostname_of(tmp_path, filename) == hostname


@pytest.mark.parametrize('filename', ['client1', '_linbo.log', '.linbo-remote'])
def test_a_name_with_nothing_before_a_separator_points_at_no_host(tmp_path, filename):
    assert hostname_of(tmp_path, filename) is None


def test_a_log_named_after_something_else_is_not_a_host(tmp_path):
    """
    Both exist on a real server: a multicast log named after an image, and a
    client that could not identify itself. Neither can be attributed to a
    school, so what they report must simply not match any inventory.
    """

    assert hostname_of(tmp_path, 'bionic.cloop_mcast.log') == 'bionic'
    assert hostname_of(tmp_path, 'UNKNOWN_hwinfo.gz') == 'UNKNOWN'


def test_list_logs_reports_every_file_with_its_host(tmp_path):
    (tmp_path / 'client1_linbo.log').write_text('boot\n')
    (tmp_path / 'bionic.cloop_mcast.log').write_text('multicast\n')

    logs = {log['filename']: log['hostname'] for log in LinboBootLogs(str(tmp_path)).list_logs()}

    assert logs == {'client1_linbo.log': 'client1', 'bionic.cloop_mcast.log': 'bionic'}


def test_list_logs_without_directory(tmp_path):
    assert LinboBootLogs(str(tmp_path / 'nothing-here')).list_logs() == []
