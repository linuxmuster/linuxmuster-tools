"""
Tests for group_os() and last_sync_all() in linuxmusterTools.linbo.config.
"""

from datetime import datetime

from linuxmusterTools.linbo.config import group_os, last_sync_all


START_CONF = """\
[OS]
BaseImage=ubuntu.qcow2
Root=/dev/sda1
SyncEnabled=yes
NewEnabled=no
StartEnabled=yes
"""


def write_start_conf(tmp_path, group='grp1'):
    (tmp_path / f'start.conf.{group}').write_text(START_CONF)


# ── group_os ─────────────────────────────────────────────────────────────


def test_group_os_default_auto_includes_broadcast(tmp_path):
    write_start_conf(tmp_path)
    workstations = {'grp1': {'hosts': []}}

    group_os(workstations)

    assert workstations['grp1']['auto']['broadcast'] == 0


def test_group_os_extracts_baseimage(tmp_path):
    write_start_conf(tmp_path)
    workstations = {'grp1': {'hosts': []}}

    group_os(workstations)

    assert workstations['grp1']['os'][0]['baseimage'] == 'ubuntu.qcow2'


def test_group_os_no_startconf_leaves_empty_os(tmp_path):
    workstations = {'grp1': {'hosts': []}}

    group_os(workstations)

    assert workstations['grp1']['os'] == []
    assert 'auto' not in workstations['grp1']


# ── last_sync_all ────────────────────────────────────────────────────────


def test_last_sync_all_sets_image_list(tmp_path):
    write_start_conf(tmp_path)
    workstations = {'grp1': {'hosts': [{'hostname': 'pc001'}]}}
    group_os(workstations)

    last_sync_all(workstations)

    host = workstations['grp1']['hosts'][0]
    assert host['image'] == [{'date': 'Never', 'image': 'ubuntu.qcow2', 'status': 'danger'}]


def test_last_sync_all_does_not_use_legacy_shape(tmp_path):
    write_start_conf(tmp_path)
    workstations = {'grp1': {'hosts': [{'hostname': 'pc001'}]}}
    group_os(workstations)

    last_sync_all(workstations)

    host = workstations['grp1']['hosts'][0]
    assert 'images' not in host
    assert 'sync' not in host


def test_last_sync_all_reads_status_file(tmp_path):
    write_start_conf(tmp_path)
    workstations = {'grp1': {'hosts': [{'hostname': 'pc001'}]}}
    group_os(workstations)

    now = datetime.now().strftime('%Y%m%d%H%M')
    (tmp_path / 'var_log_linbo' / 'pc001_image.status').write_text(
        f'{now} applied: ubuntu.qcow2 "202601271107"\n'
    )

    last_sync_all(workstations)

    host = workstations['grp1']['hosts'][0]
    assert host['image'][0]['status'] == 'success'
