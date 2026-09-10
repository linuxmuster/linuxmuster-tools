"""
Tests for group_os(), last_sync_all() and get_host_image_status() in
linuxmusterTools.linbo.config.
"""

import time
from datetime import datetime, timezone

import pytest

from linuxmusterTools.linbo.config import group_os, last_sync, last_sync_all, get_host_image_status


@pytest.fixture
def berlin_tz(monkeypatch):
    """Pin the timezone: lastSync is a conversion from server-local time."""

    monkeypatch.setenv('TZ', 'Europe/Berlin')
    time.tzset()
    yield
    time.tzset()  # monkeypatch restored TZ, reload it


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


def test_group_os_partition_is_none_without_partition_sections(tmp_path):
    write_start_conf(tmp_path)  # no [Partition] section at all
    workstations = {'grp1': {'hosts': []}}

    group_os(workstations)

    assert workstations['grp1']['os'][0]['partition'] is None


START_CONF_WITH_PARTITIONS = """\
[Partition]
Dev=/dev/sda1
Size=200M
Id=ef
Label=efi
Bootable=yes
FSType=vfat

[Partition]
Dev=/dev/sda3
Size=30G
Id=83
Label=data
Bootable=no
FSType=ext4

[OS]
Name=Ubuntu
BaseImage=ubuntu.qcow2
Root=/dev/sda3
Kernel=vmlinuz
Initrd=initrd
Append=
DefaultAction=sync
Description=Ubuntu
IconName=ubuntu
SyncEnabled=yes
NewEnabled=no
StartEnabled=yes
"""


def test_group_os_partition_is_position_not_device_digit(tmp_path):
    (tmp_path / 'start.conf.grp1').write_text(START_CONF_WITH_PARTITIONS)
    workstations = {'grp1': {'hosts': []}}

    group_os(workstations)

    # Root=/dev/sda3 is the 2nd [Partition] section, not partition "3".
    assert workstations['grp1']['os'][0]['partition'] == 2


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
        f'{now} applied: ubuntu.qcow2 202601271107\n'
    )

    last_sync_all(workstations)

    host = workstations['grp1']['hosts'][0]
    assert host['image'][0]['status'] == 'success'


# ── last_sync ────────────────────────────────────────────────────────────
# last_sync() and get_host_image_status() share the same line parser
# (_parse_image_status_file); these tests pin last_sync()'s own contract:
# matching by exact image field (not by substring of the whole line) and
# accepting the .qdiff variant of the requested base image.


def test_last_sync_no_status_file_returns_false(tmp_path):
    assert last_sync('pc404', 'ubuntu.qcow2') is False


def test_last_sync_matches_requested_image(tmp_path):
    (tmp_path / 'var_log_linbo' / 'pc001_image.status').write_text(
        '202601271107 applied: ubuntu.qcow2 202601271107\n'
    )

    assert last_sync('pc001', 'ubuntu.qcow2') is not False


def test_last_sync_matches_qdiff_variant_of_requested_image(tmp_path):
    (tmp_path / 'var_log_linbo' / 'pc001_image.status').write_text(
        '202603241142 applied: ubuntu.qdiff 202601271107\n'
    )

    assert last_sync('pc001', 'ubuntu.qcow2') is not False


def test_last_sync_does_not_match_image_name_as_substring(tmp_path):
    # "ubuntu.qcow2" is a substring of "old_ubuntu.qcow2" — a naive
    # substring check on the raw line would wrongly match here.
    (tmp_path / 'var_log_linbo' / 'pc001_image.status').write_text(
        '202601271107 applied: old_ubuntu.qcow2 202601271107\n'
    )

    assert last_sync('pc001', 'ubuntu.qcow2') is False


# ── get_host_image_status ───────────────────────────────────────────────
# linuxmuster-linbo7's shell_functions log_image_status() quotes the trailing
# timestamp on "applied" lines but not on "created" ones, e.g.:
#   202603241142 applied: win11_pro_edu.qcow2 "202601271107"
#   202601271107 created: win11_pro_edu.qcow2 202601271107
# linbo_sync reads the timestamp back with getinfo(), which keeps the quotes
# of timestamp="..." in the image .info file; linbo_mkinfo passes date(1)
# output directly.


def test_get_host_image_status_reads_applied_line(tmp_path, berlin_tz):
    (tmp_path / 'var_log_linbo' / 'pc001_image.status').write_text(
        '202603241142 applied: win11_pro_edu.qcow2 "202601271107"\n'
    )

    status = get_host_image_status()

    # 11:42 CET is 10:42 UTC: the timestamp is the client's local time, and
    # relabelling those digits as UTC was the bug.
    assert status['pc001'] == {
        'lastSync': '2026-03-24T10:42:00+00:00',
        'action': 'applied',
        'image': 'win11_pro_edu.qcow2',
        'imageVersion': '202601271107',
    }


def test_get_host_image_status_and_last_sync_agree_on_the_same_instant(tmp_path, berlin_tz):
    (tmp_path / 'var_log_linbo' / 'pc001_image.status').write_text(
        '202603241142 applied: win11_pro_edu.qcow2 "202601271107"\n'
    )

    epoch = last_sync('pc001', 'win11_pro_edu.qcow2')
    from_status = get_host_image_status()['pc001']['lastSync']

    assert datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat() == from_status


def test_get_host_image_status_reads_unquoted_applied_line(tmp_path):
    # Hand-written or pre-getinfo status files carry a bare timestamp.
    (tmp_path / 'var_log_linbo' / 'pc004_image.status').write_text(
        '202603241142 applied: win11_pro_edu.qcow2 202601271107\n'
    )

    status = get_host_image_status()

    assert status['pc004']['imageVersion'] == '202601271107'


def test_get_host_image_status_reads_created_line(tmp_path):
    (tmp_path / 'var_log_linbo' / 'pc002_image.status').write_text(
        '202601271107 created: win11_pro_edu.qcow2 202601271107\n'
    )

    status = get_host_image_status()

    assert status['pc002']['action'] == 'created'


def test_get_host_image_status_skips_malformed_line(tmp_path):
    (tmp_path / 'var_log_linbo' / 'pc003_image.status').write_text('not a status line\n')

    status = get_host_image_status()

    assert 'pc003' not in status


def test_get_host_image_status_no_files_returns_empty_dict(tmp_path):
    assert get_host_image_status() == {}
