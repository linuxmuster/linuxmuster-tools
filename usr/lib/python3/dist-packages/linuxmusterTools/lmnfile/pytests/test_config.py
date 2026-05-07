"""
Tests for ConfigLoader: INI/conf parsing, type conversion on read/write,
multi-section files.
"""

import pytest
from linuxmusterTools.lmnfile import LMNFile


def make_ini(tmp_path, content, name='setup.ini'):
    f = tmp_path / name
    f.write_text(content, encoding='utf-8')
    return f


# ── Read ──────────────────────────────────────────────────────────────────────

def test_read_string_value(tmp_path):
    f = make_ini(tmp_path, '[school]\nname = MySchool\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['school']['name'] == 'MySchool'


def test_read_converts_yes_to_true(tmp_path):
    f = make_ini(tmp_path, '[setup]\nenabled = yes\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['setup']['enabled'] is True


def test_read_converts_no_to_false(tmp_path):
    f = make_ini(tmp_path, '[setup]\nenabled = no\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['setup']['enabled'] is False


def test_read_converts_digit_string_to_int(tmp_path):
    f = make_ini(tmp_path, '[setup]\nport = 8080\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['setup']['port'] == 8080
    assert isinstance(data['setup']['port'], int)


def test_read_multiple_sections(tmp_path):
    content = '[school]\nname = MySchool\n[network]\nip = 10.0.0.1\n'
    f = make_ini(tmp_path, content)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert 'school' in data
    assert 'network' in data
    assert data['network']['ip'] == '10.0.0.1'


def test_read_multiple_values_in_section(tmp_path):
    content = '[setup]\nname = school\nport = 443\nenabled = yes\n'
    f = make_ini(tmp_path, content)
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['setup']['name'] == 'school'
    assert data['setup']['port'] == 443
    assert data['setup']['enabled'] is True


# ── Write ─────────────────────────────────────────────────────────────────────

def test_write_string_value(tmp_path):
    f = make_ini(tmp_path, '[school]\nname = Old\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['school']['name'] = 'New'
        lmn.write(data)
    with LMNFile(str(f), 'r') as lmn:
        result = lmn.read()
    assert result['school']['name'] == 'New'


def test_write_converts_true_to_yes(tmp_path):
    f = make_ini(tmp_path, '[setup]\nenabled = no\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['setup']['enabled'] = True
        lmn.write(data)
    assert 'enabled = yes' in f.read_text()


def test_write_converts_false_to_no(tmp_path):
    f = make_ini(tmp_path, '[setup]\nenabled = yes\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['setup']['enabled'] = False
        lmn.write(data)
    assert 'enabled = no' in f.read_text()


def test_write_int_value_preserved(tmp_path):
    f = make_ini(tmp_path, '[setup]\nport = 80\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['setup']['port'] = 443
        lmn.write(data)
    with LMNFile(str(f), 'r') as lmn:
        result = lmn.read()
    assert result['setup']['port'] == 443


def test_write_creates_backup_on_change(tmp_path):
    import os
    f = make_ini(tmp_path, '[school]\nname = Old\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['school']['name'] = 'New'
        lmn.write(data)
    backups = [x for x in os.listdir(str(tmp_path)) if x.startswith('.setup.ini.bak.')]
    assert len(backups) == 1


# ── conf extension ────────────────────────────────────────────────────────────

def test_conf_file_readable(tmp_path):
    f = make_ini(tmp_path, '[section]\nkey = value\n', name='app.conf')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['section']['key'] == 'value'
