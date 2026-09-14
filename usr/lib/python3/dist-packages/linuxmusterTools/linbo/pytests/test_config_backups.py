"""
Tests for the start.conf backup accessors of LinboConfigManager:
list_startconf_backups(), restore_startconf_backup() and
delete_startconf_backup().
"""

import os
import glob

import pytest

from linuxmusterTools.linbo.config import LinboConfigManager


CONTENT = '[LINBO]\nGroup = mygroup\n# a comment a restore must bring back\n'


def write_backup(tmp_path, timestamp, group_id='mygroup', content=CONTENT):
    path = tmp_path / f'.start.conf.{group_id}.bak.{timestamp}'
    path.write_text(content)
    return path


# ── list_startconf_backups ───────────────────────────────────────────────────


def test_list_reports_backups_newest_first(tmp_path):
    for timestamp in (1619126558, 1632669598, 1619165448):
        write_backup(tmp_path, timestamp)

    backups = LinboConfigManager().list_startconf_backups('mygroup')

    assert [backup['timestamp'] for backup in backups] == [1632669598, 1619165448, 1619126558]


def test_list_reports_size_and_date(tmp_path):
    write_backup(tmp_path, 1632669598)

    backup = LinboConfigManager().list_startconf_backups('mygroup')[0]

    assert backup['size'] == len(CONTENT)
    assert backup['createdAt'] == '2021-09-26T15:19:58+00:00'


def test_list_ignores_the_backups_of_a_group_whose_name_starts_the_same(tmp_path):
    """
    101, 101-test and 101b coexist on a real server.
    """

    write_backup(tmp_path, 1632669598, group_id='101')
    write_backup(tmp_path, 1632669599, group_id='101-test')
    write_backup(tmp_path, 1632669600, group_id='101b')

    backups = LinboConfigManager().list_startconf_backups('101')

    assert [backup['timestamp'] for backup in backups] == [1632669598]


def test_list_ignores_the_vdi_config_backups(tmp_path):
    write_backup(tmp_path, 1632669598)
    (tmp_path / '.start.conf.mygroup.vdi.bak.1632669599').write_text('activated: true\n')

    backups = LinboConfigManager().list_startconf_backups('mygroup')

    assert [backup['timestamp'] for backup in backups] == [1632669598]


def test_list_ignores_a_name_that_does_not_end_on_an_epoch(tmp_path):
    write_backup(tmp_path, 1632669598)
    (tmp_path / '.start.conf.mygroup.bak.1632669599.old').write_text(CONTENT)

    backups = LinboConfigManager().list_startconf_backups('mygroup')

    assert [backup['timestamp'] for backup in backups] == [1632669598]


def test_list_returns_empty_without_backups(tmp_path):
    assert LinboConfigManager().list_startconf_backups('mygroup') == []


def test_list_rejects_invalid_group_id(tmp_path):
    with pytest.raises(ValueError):
        LinboConfigManager().list_startconf_backups('../etc')


# ── restore_startconf_backup ─────────────────────────────────────────────────


def test_restore_puts_the_backup_back(tmp_path):
    write_backup(tmp_path, 1632669598)
    conf = tmp_path / 'start.conf.mygroup'
    conf.write_text('[LINBO]\nGroup = broken\n')

    LinboConfigManager().restore_startconf_backup('mygroup', 1632669598)

    assert conf.read_text() == CONTENT


def test_restore_backs_the_current_file_up_first(tmp_path):
    write_backup(tmp_path, 1632669598)
    conf = tmp_path / 'start.conf.mygroup'
    conf.write_text('[LINBO]\nGroup = broken\n')

    LinboConfigManager().restore_startconf_backup('mygroup', 1632669598)

    saved = [
        path
        for path in glob.glob(str(tmp_path / '.start.conf.mygroup.bak.*'))
        if not path.endswith('1632669598')
    ]
    assert len(saved) == 1
    assert open(saved[0]).read() == '[LINBO]\nGroup = broken\n'


def test_restore_of_the_oldest_backup_survives_the_rotation(tmp_path):
    """
    Backing the current file up drops the oldest backup when eleven exist,
    and the oldest may be the one being restored: it has to be read first.
    """

    for index in range(11):
        write_backup(tmp_path, 1600000000 + index, content=f'version {index}\n')
    (tmp_path / 'start.conf.mygroup').write_text('[LINBO]\nGroup = broken\n')

    LinboConfigManager().restore_startconf_backup('mygroup', 1600000000)

    assert (tmp_path / 'start.conf.mygroup').read_text() == 'version 0\n'
    # The rotation really did drop it, so the restore could only work by
    # having read it beforehand.
    assert not (tmp_path / '.start.conf.mygroup.bak.1600000000').exists()


def test_restore_creates_the_startconf_if_it_was_deleted(tmp_path):
    write_backup(tmp_path, 1632669598)

    LinboConfigManager().restore_startconf_backup('mygroup', 1632669598)

    assert (tmp_path / 'start.conf.mygroup').read_text() == CONTENT


def test_restore_sets_executable_permission(tmp_path):
    write_backup(tmp_path, 1632669598)

    LinboConfigManager().restore_startconf_backup('mygroup', 1632669598)

    assert os.access(str(tmp_path / 'start.conf.mygroup'), os.X_OK)


def test_restore_keeps_the_backup(tmp_path):
    backup = write_backup(tmp_path, 1632669598)

    LinboConfigManager().restore_startconf_backup('mygroup', 1632669598)

    assert backup.is_file()


def test_restore_missing_backup_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        LinboConfigManager().restore_startconf_backup('mygroup', 1632669598)


def test_restore_rejects_a_timestamp_that_is_not_one(tmp_path):
    with pytest.raises(ValueError):
        LinboConfigManager().restore_startconf_backup('mygroup', '../../start.conf.other')


def test_restore_rejects_invalid_group_id(tmp_path):
    with pytest.raises(ValueError):
        LinboConfigManager().restore_startconf_backup('../etc', 1632669598)


# ── delete_startconf_backup ──────────────────────────────────────────────────


def test_delete_removes_only_that_backup(tmp_path):
    write_backup(tmp_path, 1632669598)
    kept = write_backup(tmp_path, 1632669599)

    LinboConfigManager().delete_startconf_backup('mygroup', 1632669598)

    assert not (tmp_path / '.start.conf.mygroup.bak.1632669598').exists()
    assert kept.is_file()


def test_delete_leaves_the_startconf_untouched(tmp_path):
    write_backup(tmp_path, 1632669598)
    conf = tmp_path / 'start.conf.mygroup'
    conf.write_text(CONTENT)

    LinboConfigManager().delete_startconf_backup('mygroup', 1632669598)

    assert conf.is_file()


def test_delete_missing_backup_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        LinboConfigManager().delete_startconf_backup('mygroup', 1632669598)


def test_delete_rejects_invalid_group_id(tmp_path):
    with pytest.raises(ValueError):
        LinboConfigManager().delete_startconf_backup('../etc', 1632669598)
