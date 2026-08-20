"""
Tests for LinboConfigManager.write_raw_startconf() and .delete_startconf().
"""

import os
import glob

import pytest

from linuxmusterTools.linbo.config import LinboConfigManager


CONTENT = """\
[LINBO]
Server = 10.0.0.1
Group = mygroup
# a comment that must survive a raw write

[Partition]
Dev = /dev/sda1
Label = efi
"""


def start_conf_path(tmp_path, group_id='mygroup'):
    return tmp_path / f'start.conf.{group_id}'


# ── write_raw_startconf ─────────────────────────────────────────────────────


def test_write_creates_file_if_absent(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    f = start_conf_path(tmp_path)
    assert f.is_file()
    assert f.read_text() == CONTENT


def test_write_preserves_comments(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    assert '# a comment that must survive a raw write' in start_conf_path(tmp_path).read_text()


def test_write_sets_executable_permission(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    assert os.access(str(start_conf_path(tmp_path)), os.X_OK)


def test_write_updates_existing_file(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    updated = CONTENT.replace('10.0.0.1', '192.168.0.1')
    mgr.write_raw_startconf('mygroup', updated)

    assert start_conf_path(tmp_path).read_text() == updated


def test_write_creates_backup_on_update(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    updated = CONTENT.replace('10.0.0.1', '192.168.0.1')
    mgr.write_raw_startconf('mygroup', updated)

    backups = glob.glob(str(tmp_path / '.start.conf.mygroup.bak.*'))
    assert len(backups) == 1


def test_write_no_backup_on_creation(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    backups = glob.glob(str(tmp_path / '.start.conf.mygroup.bak.*'))
    assert backups == []


def test_write_no_backup_when_content_unchanged(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)
    mgr.write_raw_startconf('mygroup', CONTENT)

    backups = glob.glob(str(tmp_path / '.start.conf.mygroup.bak.*'))
    assert backups == []


def test_write_no_leftover_tmp_file(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)
    mgr.write_raw_startconf('mygroup', CONTENT.replace('10.0.0.1', '192.168.0.1'))

    assert not (tmp_path / 'start.conf.mygroup_tmp').exists()


def test_write_rejects_invalid_group_id(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(ValueError):
        mgr.write_raw_startconf('../etc/passwd', CONTENT)

    assert glob.glob(str(tmp_path / '*passwd*')) == []


# ── delete_startconf ─────────────────────────────────────────────────────────


def test_delete_removes_startconf(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    mgr.delete_startconf('mygroup')

    assert not start_conf_path(tmp_path).exists()


def test_delete_creates_backup(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    mgr.delete_startconf('mygroup')

    backups = glob.glob(str(tmp_path / '.start.conf.mygroup.bak.*'))
    assert len(backups) == 1


def test_delete_removes_associated_grub_config(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    grub_cfg = tmp_path / 'boot' / 'grub' / 'mygroup.cfg'
    grub_cfg.write_text('menuentry ...\n')

    mgr.delete_startconf('mygroup')

    assert not grub_cfg.exists()


def test_delete_without_grub_config_does_not_fail(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', CONTENT)

    mgr.delete_startconf('mygroup')  # no .cfg file created, should not raise


def test_delete_missing_group_raises_file_not_found(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(FileNotFoundError):
        mgr.delete_startconf('doesnotexist')


def test_delete_rejects_invalid_group_id(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(ValueError):
        mgr.delete_startconf('../etc/passwd')


# ── parse_linbo_startconf ─────────────────────────────────────────────────────


FULL_CONTENT = """\
[LINBO]
Server = 10.0.0.1
Group = mygroup
Cache = /dev/sda1

[Partition]
Dev = /dev/sda2
Label = system
Size = 30G
Id = 83
Bootable = no
FSType = ext4

[OS]
Name = Ubuntu
BaseImage = ubuntu.qcow2
Root = /dev/sda2
Kernel = vmlinuz
Initrd = initrd
Append =
DefaultAction = sync
Description = Ubuntu
IconName = ubuntu
"""


def test_parse_keeps_last_os_stanza(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', FULL_CONTENT)

    lc = mgr.parse_linbo_startconf(str(start_conf_path(tmp_path)))

    assert len(lc.OS) == 1
    assert lc.OS[0].Name == 'Ubuntu'


def test_parse_keeps_last_partition_stanza_when_file_ends_there(tmp_path):
    content = FULL_CONTENT.split('[OS]')[0]
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', content)

    lc = mgr.parse_linbo_startconf(str(start_conf_path(tmp_path)))

    assert len(lc.Partitions) == 1
    assert lc.Partitions[0].Dev == '/dev/sda2'


# ── group_ids / load_linbo_startconf(s) ──────────────────────────────────────


INCOMPLETE_CONTENT = """\
[LINBO]
Server = 10.0.0.1
Group = mygroup

[Partition]
Dev = /dev/sda1
Label = efi
"""


def test_group_ids_lists_group_with_unparsable_startconf(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', INCOMPLETE_CONTENT)  # missing Cache

    mgr = LinboConfigManager()  # re-instantiate now that the file exists on disk

    assert mgr.group_ids == ['mygroup']
    assert mgr.linbo_configs == {}


def test_load_linbo_startconf_returns_none_on_missing_field(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', INCOMPLETE_CONTENT)  # missing Cache

    result = mgr.load_linbo_startconf('mygroup')

    assert result is None
    assert 'mygroup' not in mgr.linbo_configs


def test_load_linbo_startconf_returns_parsed_config_on_success(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('mygroup', FULL_CONTENT)

    result = mgr.load_linbo_startconf('mygroup')

    assert result is not None
    assert result.LINBO.Group == 'mygroup'
    assert mgr.linbo_configs['mygroup'] is result


def test_load_linbo_startconfs_populates_only_parsable_groups(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_raw_startconf('goodgroup', FULL_CONTENT)
    mgr.write_raw_startconf('badgroup', INCOMPLETE_CONTENT)

    mgr = LinboConfigManager()  # re-instantiate to discover both files
    mgr.load_linbo_startconfs()

    assert set(mgr.group_ids) == {'goodgroup', 'badgroup'}
    assert set(mgr.linbo_configs.keys()) == {'goodgroup'}
