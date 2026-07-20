"""
Tests for ConfigLoader: INI/conf parsing, type conversion on read/write,
multi-section files.
"""

import os
import stat

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


def test_read_without_value_conversion_preserves_strings(tmp_path):
    content = '[setup]\ncode = 0012\nenabled = yes\ndisabled = no\n'
    f = make_ini(tmp_path, content)

    with LMNFile(str(f), 'r', convert_values=False) as lmn:
        data = lmn.read()

    assert data['setup']['code'] == '0012'
    assert data['setup']['enabled'] == 'yes'
    assert data['setup']['disabled'] == 'no'


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


def test_write_without_value_conversion_preserves_values(tmp_path):
    f = make_ini(tmp_path, '[setup]\ncode = 0012\nenabled = yes\n')

    with LMNFile(str(f), 'r', convert_values=False) as lmn:
        data = lmn.read()
        data['setup']['python_bool'] = True
        lmn.write(data)

    content = f.read_text(encoding='utf-8')
    assert 'code = 0012' in content
    assert 'enabled = yes' in content
    assert 'python_bool = True' in content


def test_write_creates_backup_on_change(tmp_path):
    f = make_ini(tmp_path, '[school]\nname = Old\n')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['school']['name'] = 'New'
        lmn.write(data)
    backups = [x for x in os.listdir(str(tmp_path)) if x.startswith('.setup.ini.bak.')]
    assert len(backups) == 1


def test_write_creates_missing_conf(tmp_path):
    f = tmp_path / 'new.conf'

    with LMNFile(str(f), 'w') as lmn:
        lmn.write({'section': {'enabled': True}})

    with LMNFile(str(f), 'r') as lmn:
        result = lmn.read()

    assert result['section']['enabled'] is True
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert not list(tmp_path.glob('.new.conf.bak.*'))


def test_write_uses_same_directory_atomic_replace(tmp_path, monkeypatch):
    f = make_ini(tmp_path, '[school]\nname = Old\n')
    original_replace = os.replace
    replace_call = {}

    def track_replace(source, destination):
        replace_call['source'] = source
        replace_call['destination'] = destination
        assert os.path.dirname(source) == str(tmp_path)
        assert f.read_text(encoding='utf-8') == '[school]\nname = Old\n'
        original_replace(source, destination)

    monkeypatch.setattr(os, 'replace', track_replace)

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['school']['name'] = 'New'
        lmn.write(data)

    assert replace_call['destination'] == str(f)
    assert 'name = New' in f.read_text(encoding='utf-8')


def test_atomic_write_preserves_permissions(tmp_path):
    f = make_ini(tmp_path, '[school]\nname = Old\n')
    f.chmod(0o640)

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['school']['name'] = 'New'
        lmn.write(data)

    assert stat.S_IMODE(f.stat().st_mode) == 0o640


def test_atomic_write_preserves_owner_and_group(tmp_path, monkeypatch):
    f = make_ini(tmp_path, '[school]\nname = Old\n')
    original_metadata = f.stat()
    original_chown = os.chown
    chown_call = {}

    def track_chown(path, uid, gid):
        chown_call['uid'] = uid
        chown_call['gid'] = gid
        original_chown(path, uid, gid)

    monkeypatch.setattr(os, 'chown', track_chown)

    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
        data['school']['name'] = 'New'
        lmn.write(data)

    assert chown_call == {
        'uid': original_metadata.st_uid,
        'gid': original_metadata.st_gid,
    }
    assert f.stat().st_uid == original_metadata.st_uid
    assert f.stat().st_gid == original_metadata.st_gid


def test_atomic_write_preserves_configuration_symlink(tmp_path):
    target = make_ini(
        tmp_path, '[school]\nname = Old\n', name='target.conf'
    )
    link = tmp_path / 'linked.conf'
    link.symlink_to(target)

    with LMNFile(str(link), 'r') as lmn:
        data = lmn.read()
        data['school']['name'] = 'New'
        lmn.write(data)

    assert link.is_symlink()
    assert link.resolve() == target
    assert 'name = New' in target.read_text(encoding='utf-8')


def test_failed_replace_leaves_original_file(tmp_path, monkeypatch):
    original = '[school]\nname = Old\n'
    f = make_ini(tmp_path, original)

    def fail_replace(source, destination):
        raise OSError('replace failed')

    monkeypatch.setattr(os, 'replace', fail_replace)

    with pytest.raises(OSError, match='replace failed'):
        with LMNFile(str(f), 'r') as lmn:
            data = lmn.read()
            data['school']['name'] = 'New'
            lmn.write(data)

    assert f.read_text(encoding='utf-8') == original
    assert not list(tmp_path.glob('.setup.ini.*.tmp'))


# ── conf extension ────────────────────────────────────────────────────────────

def test_conf_file_readable(tmp_path):
    f = make_ini(tmp_path, '[section]\nkey = value\n', name='app.conf')
    with LMNFile(str(f), 'r') as lmn:
        data = lmn.read()
    assert data['section']['key'] == 'value'
