"""
Tests for the backup() mechanism shared by all loaders.
Uses YAMLLoader as a representative because it is the simplest write path.
"""

import os
import pytest
from linuxmusterTools.lmnfile import LMNFile


def _backups(tmp_path, name):
    return sorted(
        x for x in os.listdir(str(tmp_path))
        if x.startswith(f'.{name}.bak.')
    )


def test_backup_created_when_content_changes(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: original\n')

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'changed'
        lmn.write(data)

    assert len(_backups(tmp_path, 'config.yml')) == 1


def test_no_backup_when_content_unchanged(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        lmn.write(data)  # identical content

    assert len(_backups(tmp_path, 'config.yml')) == 0


def test_backup_content_matches_original(tmp_path):
    f = tmp_path / 'config.yml'
    original = 'key: original\n'
    f.write_text(original)

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'changed'
        lmn.write(data)

    baks = _backups(tmp_path, 'config.yml')
    backup_content = (tmp_path / baks[0]).read_text()
    assert backup_content == original


def test_backup_preserves_file_permissions(tmp_path):
    # Use CSV: CSVLoader.__enter__ does not chmod, so our explicit 0o640 is kept.
    # YAMLLoader always resets to 0o600 when running as root.
    f = tmp_path / 'data.csv'
    f.write_text('room;hostname\nroom1;pc1\n', encoding='utf-8')
    os.chmod(str(f), 0o640)

    with LMNFile(str(f), 'r', fieldnames=['room', 'hostname']) as lmn:
        rows = lmn.read()
        rows[0]['room'] = 'changed'
        lmn.write(rows)

    baks = _backups(tmp_path, 'data.csv')
    backup_perms = oct(os.stat(str(tmp_path / baks[0])).st_mode)[-3:]
    assert backup_perms == '640'


def test_backup_keeps_at_most_10_old_backups(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')

    # Pre-create 11 old backup files (timestamps in the past)
    for i in range(11):
        bak = tmp_path / f'.config.yml.bak.{1_000_000 + i}'
        bak.write_text('old')

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'changed'
        lmn.write(data)

    # backup() trims to ≤10 before adding the new one,
    # so the total after write is ≤ 11.
    assert len(_backups(tmp_path, 'config.yml')) <= 11


def test_oldest_backup_deleted_first(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')

    for i in range(11):
        bak = tmp_path / f'.config.yml.bak.{1_000_000 + i}'
        bak.write_text('old')

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'changed'
        lmn.write(data)

    # The oldest backup (lowest timestamp) must have been removed
    remaining = _backups(tmp_path, 'config.yml')
    assert '.config.yml.bak.1000000' not in remaining


def test_tmp_file_removed_after_no_change(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        lmn.write(data)

    assert not (tmp_path / 'config.yml_tmp').exists()


def test_tmp_file_removed_after_change(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'changed'
        lmn.write(data)

    assert not (tmp_path / 'config.yml_tmp').exists()
