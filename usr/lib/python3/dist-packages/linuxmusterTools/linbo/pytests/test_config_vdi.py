"""
Tests for LinboConfigManager's VDI config accessors:
read_vdi_config(), write_vdi_config() and delete_vdi_config().
"""

import os
import glob

import pytest
import yaml

from linuxmusterTools.linbo.config import LinboConfigManager


CONFIG = {
    'activated': True,
    'name': 'vdi-master',
    'bios': 'ovmf',
    'ostype': 'l26',
    'boot': 'order=scsi0',
    'hostname': 'vdi01',
    'ip': '10.0.0.50',
    'mac': 'AA:BB:CC:DD:EE:FF',
    'bridge': 'vmbr0',
    'tag': 42,
    'cores': 4,
    'memory': 4096,
    'size': '32G',
    'storage': 'local-lvm',
    'vmids': [101, 102],
}


def vdi_path(tmp_path, group_id='mygroup'):
    return tmp_path / f'start.conf.{group_id}.vdi'


# ── write_vdi_config ─────────────────────────────────────────────────────────


def test_write_creates_file_if_absent(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    assert vdi_path(tmp_path).is_file()


def test_write_serializes_as_yaml(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    # The legacy webui wrote JSON into a file it read back as YAML. JSON is
    # valid YAML so both parse, but what is written here must be plain YAML.
    raw = vdi_path(tmp_path).read_text()
    assert not raw.lstrip().startswith('{')
    assert yaml.safe_load(raw) == CONFIG


def test_write_sets_owner_only_permission(tmp_path):
    """
    600, not the umask default YAMLLoader's own rename would leave behind.
    """

    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    assert oct(os.stat(str(vdi_path(tmp_path))).st_mode & 0o777) == '0o600'


def test_write_keeps_permission_on_update(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)
    mgr.write_vdi_config('mygroup', {'activated': False})

    assert oct(os.stat(str(vdi_path(tmp_path))).st_mode & 0o777) == '0o600'


def test_write_replaces_the_whole_config(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    mgr.write_vdi_config('mygroup', {'activated': False})

    assert mgr.read_vdi_config('mygroup') == {'activated': False}


def test_write_creates_backup_on_update(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)
    mgr.write_vdi_config('mygroup', {'activated': False})

    assert glob.glob(str(tmp_path / '.start.conf.mygroup.vdi.bak.*'))


def test_write_leaves_the_startconf_untouched(tmp_path):
    startconf = tmp_path / 'start.conf.mygroup'
    startconf.write_text('[LINBO]\nGroup = mygroup\n')

    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    assert startconf.read_text() == '[LINBO]\nGroup = mygroup\n'


def test_write_rejects_invalid_group_id(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(ValueError):
        mgr.write_vdi_config('../etc/passwd', CONFIG)

    assert glob.glob(str(tmp_path / '*passwd*')) == []


# ── read_vdi_config ──────────────────────────────────────────────────────────


def test_read_returns_the_written_config(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    assert mgr.read_vdi_config('mygroup') == CONFIG


def test_read_keeps_value_types(tmp_path):
    """
    The file must go through the YAML loader, not the start.conf parser:
    booleans, integers and lists have to survive the round trip.
    """

    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    config = mgr.read_vdi_config('mygroup')
    assert config['activated'] is True
    assert config['cores'] == 4
    assert config['vmids'] == [101, 102]


def test_read_returns_empty_dict_on_empty_file(tmp_path):
    vdi_path(tmp_path).write_text('')

    mgr = LinboConfigManager()

    assert mgr.read_vdi_config('mygroup') == {}


def test_read_missing_config_raises_file_not_found(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(FileNotFoundError):
        mgr.read_vdi_config('mygroup')


def test_read_rejects_invalid_group_id(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(ValueError):
        mgr.read_vdi_config('../../etc/passwd')


# ── delete_vdi_config ────────────────────────────────────────────────────────


def test_delete_removes_the_config(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    mgr.delete_vdi_config('mygroup')

    assert not vdi_path(tmp_path).exists()


def test_delete_creates_backup(tmp_path):
    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)

    mgr.delete_vdi_config('mygroup')

    assert glob.glob(str(tmp_path / '.start.conf.mygroup.vdi.bak.*'))


def test_delete_leaves_the_startconf_untouched(tmp_path):
    startconf = tmp_path / 'start.conf.mygroup'
    startconf.write_text('[LINBO]\nGroup = mygroup\n')

    mgr = LinboConfigManager()
    mgr.write_vdi_config('mygroup', CONFIG)
    mgr.delete_vdi_config('mygroup')

    assert startconf.is_file()


def test_delete_missing_config_raises_file_not_found(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(FileNotFoundError):
        mgr.delete_vdi_config('mygroup')


def test_delete_rejects_invalid_group_id(tmp_path):
    mgr = LinboConfigManager()
    with pytest.raises(ValueError):
        mgr.delete_vdi_config('../etc/passwd')
