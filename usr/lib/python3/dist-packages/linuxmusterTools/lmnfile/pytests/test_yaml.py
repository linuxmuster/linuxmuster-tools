"""
Tests for YAMLLoader: read, write, unicode, backup behaviour.
"""

import os
import yaml
import pytest
from linuxmusterTools.lmnfile import LMNFile


def make_yaml(tmp_path, content):
    f = tmp_path / 'config.yml'
    f.write_text(content, encoding='utf-8')
    return f


# ── Read ──────────────────────────────────────────────────────────────────────

def test_read_simple_values(tmp_path):
    f = make_yaml(tmp_path, 'name: school\nport: 8080\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['name'] == 'school'
    assert data['port'] == 8080


def test_read_nested_dict(tmp_path):
    f = make_yaml(tmp_path, 'server:\n  host: 10.0.0.1\n  port: 22\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['server']['host'] == '10.0.0.1'
    assert data['server']['port'] == 22


def test_read_list(tmp_path):
    f = make_yaml(tmp_path, 'items:\n  - a\n  - b\n  - c\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['items'] == ['a', 'b', 'c']


def test_read_empty_file_returns_none(tmp_path):
    f = make_yaml(tmp_path, '')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data is None


def test_read_unicode(tmp_path):
    f = make_yaml(tmp_path, 'name: école\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['name'] == 'école'


# ── Write ─────────────────────────────────────────────────────────────────────

def test_write_modifies_file(tmp_path):
    f = make_yaml(tmp_path, 'key: old\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'new'
        lmn.write(data)
    assert yaml.safe_load(f.read_text())['key'] == 'new'


def test_write_unicode_value(tmp_path):
    f = make_yaml(tmp_path, 'key: value\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['name'] = 'école'
        lmn.write(data)
    assert yaml.safe_load(f.read_text())['name'] == 'école'


def test_write_new_key(tmp_path):
    f = make_yaml(tmp_path, 'key: value\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['extra'] = 42
        lmn.write(data)
    result = yaml.safe_load(f.read_text())
    assert result['extra'] == 42


def test_write_does_not_create_backup_when_unchanged(tmp_path):
    f = make_yaml(tmp_path, 'key: value\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        lmn.write(data)
    backups = [x for x in os.listdir(str(tmp_path)) if '.config.yml.bak.' in x]
    assert len(backups) == 0


def test_write_creates_backup_when_changed(tmp_path):
    f = make_yaml(tmp_path, 'key: value\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'changed'
        lmn.write(data)
    backups = [x for x in os.listdir(str(tmp_path)) if x.startswith('.config.yml.bak.')]
    assert len(backups) == 1


def test_write_does_not_leave_tmp_file(tmp_path):
    f = make_yaml(tmp_path, 'key: value\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['key'] = 'changed'
        lmn.write(data)
    assert not (tmp_path / 'config.yml_tmp').exists()
