"""
Tests for StartConfLoader: parsing [LINBO]/[GUI]/[Partition]/[OS] sections,
bool conversion, write round-trip, underscore key filtering.
"""

import os
import pytest
from linuxmusterTools.lmnfile import LMNFile

START_CONF = """\
[LINBO]
Server = 10.0.0.1
Group = mygroup
Autopartition = no
AutoFormat = yes
DownloadType = torrent

[GUI]
ShowApps = yes

[Partition]
Dev = /dev/sda1
Label = efi
Bootable = yes

[Partition]
Dev = /dev/sda2
Label = ubuntu
Bootable = no

[OS]
Name = Ubuntu
BaseImage = ubuntu.qcow2
StartEnabled = yes
SyncEnabled = no
"""


def make_start_conf(tmp_path, content=None, name='start.conf'):
    f = tmp_path / name
    f.write_text(content or START_CONF, encoding='utf-8')
    return f


# ── Read ──────────────────────────────────────────────────────────────────────

def test_read_returns_three_keys(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert set(data.keys()) == {'config', 'partitions', 'os'}


def test_read_config_section(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert 'LINBO' in data['config']
    assert data['config']['LINBO']['Server'] == '10.0.0.1'
    assert data['config']['LINBO']['Group'] == 'mygroup'


def test_read_bool_no_converted_to_false(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['config']['LINBO']['Autopartition'] is False


def test_read_bool_yes_converted_to_true(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['config']['LINBO']['AutoFormat'] is True


def test_read_partitions_count(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert len(data['partitions']) == 2


def test_read_partition_fields(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['partitions'][0]['Dev'] == '/dev/sda1'
    assert data['partitions'][0]['Label'] == 'efi'
    assert data['partitions'][0]['Bootable'] is True
    assert data['partitions'][1]['Bootable'] is False


def test_read_os_sections(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert len(data['os']) == 1
    assert data['os'][0]['Name'] == 'Ubuntu'
    assert data['os'][0]['StartEnabled'] is True
    assert data['os'][0]['SyncEnabled'] is False


def test_read_inline_comments_ignored(tmp_path):
    content = '[LINBO]\nServer = 10.0.0.1 # main server\n'
    f = make_start_conf(tmp_path, content)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['config']['LINBO']['Server'] == '10.0.0.1'


def test_read_full_line_comments_ignored(tmp_path):
    content = '# full comment\n[LINBO]\nServer = 10.0.0.1\n'
    f = make_start_conf(tmp_path, content)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['config']['LINBO']['Server'] == '10.0.0.1'


def test_read_multiple_config_sections(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert 'LINBO' in data['config']
    assert 'GUI' in data['config']


# ── Write ─────────────────────────────────────────────────────────────────────

def test_write_round_trip_preserves_server(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['config']['LINBO']['Server'] = '192.168.0.1'
        lmn.write(data)
    with LMNFile(str(f), 'r') as lmn:
        result = lmn.read()
    assert result['config']['LINBO']['Server'] == '192.168.0.1'


def test_write_round_trip_preserves_partition_count(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        lmn.write(data)
    with LMNFile(str(f), 'r') as lmn:
        result = lmn.read()
    assert len(result['partitions']) == 2


def test_write_bool_converted_to_yes(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['config']['LINBO']['Autopartition'] = True
        lmn.write(data)
    assert 'Autopartition = yes' in f.read_text()


def test_write_bool_converted_to_no(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['config']['LINBO']['AutoFormat'] = False
        lmn.write(data)
    assert 'AutoFormat = no' in f.read_text()


def test_write_filters_underscore_keys_in_partitions(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['partitions'][0]['_internal'] = 'hidden'
        lmn.write(data)
    assert '_internal' not in f.read_text()


def test_write_filters_underscore_keys_in_os(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['os'][0]['_meta'] = 'hidden'
        lmn.write(data)
    assert '_meta' not in f.read_text()


def test_write_sets_executable_permission(tmp_path):
    f = make_start_conf(tmp_path)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        lmn.write(data)
    assert os.access(str(f), os.X_OK)


def test_write_creates_file_if_absent(tmp_path):
    # Instantiate without opening (__enter__ not called): write() handles the
    # absent-file case by skipping backup and directly renaming the tmp file.
    f = tmp_path / 'start.conf.newgroup'
    assert not f.exists()

    data = {
        'config': {'LINBO': {'Server': '10.0.0.1'}},
        'partitions': [],
        'os': [],
    }

    # LMNFile() routes to StartConfLoader and calls __init__ only, not __enter__
    lmn = LMNFile(str(f), 'w')
    lmn.write(data)

    assert f.exists()
    assert 'Server = 10.0.0.1' in f.read_text()


# ── File name variants ─────────────────────────────────────────────────────────

def test_start_conf_with_numeric_suffix(tmp_path):
    f = make_start_conf(tmp_path, name='start.conf.101')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['config']['LINBO']['Server'] == '10.0.0.1'
