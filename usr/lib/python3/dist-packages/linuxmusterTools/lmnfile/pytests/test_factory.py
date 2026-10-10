"""
Tests for the LMNFile factory: verify that each file extension routes
to the correct loader subclass.
"""

import pytest
from linuxmusterTools.lmnfile import LMNFile
from linuxmusterTools.lmnfile.lmnfile import (
    YAMLLoader, CSVLoader, ConfigLoader, StartConfLoader, LinboLoader,
)


def test_yml_routes_to_yaml_loader(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')
    assert isinstance(LMNFile(str(f), 'r'), YAMLLoader)


def test_vdi_routes_to_yaml_loader(tmp_path):
    f = tmp_path / 'image.vdi'
    f.write_text('key: value\n')
    assert isinstance(LMNFile(str(f), 'r'), YAMLLoader)


def test_csv_routes_to_csv_loader(tmp_path):
    f = tmp_path / 'data.csv'
    f.write_text('a;b\n1;2\n')
    assert isinstance(LMNFile(str(f), 'r', fieldnames=['a', 'b']), CSVLoader)


def test_ini_routes_to_config_loader(tmp_path):
    f = tmp_path / 'setup.ini'
    f.write_text('[section]\nkey = value\n')
    assert isinstance(LMNFile(str(f), 'r'), ConfigLoader)


def test_conf_routes_to_config_loader(tmp_path):
    f = tmp_path / 'app.conf'
    f.write_text('[section]\nkey = value\n')
    assert isinstance(LMNFile(str(f), 'r'), ConfigLoader)


def test_start_conf_routes_to_startconf_loader(tmp_path):
    f = tmp_path / 'start.conf'
    f.write_text('[LINBO]\nServer = 10.0.0.1\n')
    assert isinstance(LMNFile(str(f), 'r'), StartConfLoader)


def test_start_conf_with_numeric_suffix_routes_to_startconf_loader(tmp_path):
    f = tmp_path / 'start.conf.101'
    f.write_text('[LINBO]\nServer = 10.0.0.1\n')
    assert isinstance(LMNFile(str(f), 'r'), StartConfLoader)


def test_path_object_is_accepted(tmp_path):
    f = tmp_path / 'config.yml'
    f.write_text('key: value\n')
    with LMNFile(f, 'r') as loaded:
        assert loaded.file == str(f)
        assert loaded.read() == {'key': 'value'}


def test_start_conf_path_object_routes_to_startconf_loader(tmp_path):
    f = tmp_path / 'start.conf.101'
    f.write_text('[LINBO]\nServer = 10.0.0.1\n')
    assert isinstance(LMNFile(f, 'r'), StartConfLoader)


def test_start_conf_vdi_routes_to_yaml_loader(tmp_path):
    # start.conf.vdi has .vdi extension → YAMLLoader, not StartConfLoader
    f = tmp_path / 'start.conf.vdi'
    f.write_text('key: value\n')
    assert isinstance(LMNFile(str(f), 'r'), YAMLLoader)


@pytest.mark.parametrize('ext', ['.desc', '.reg', '.postsync', '.info', '.macct', '.prestart'])
def test_linbo_extensions_route_to_linbo_loader(tmp_path, ext):
    f = tmp_path / f'image{ext}'
    f.write_text('some content\n')
    assert isinstance(LMNFile(str(f), 'r'), LinboLoader)


@pytest.mark.parametrize('name', ['test.yml', 'start.conf.group'])
def test_init_runs_once(tmp_path, monkeypatch, name):
    calls = []
    monkeypatch.setattr(LMNFile, 'detect_encoding', lambda self: calls.append(1) or 'utf-8')
    f = tmp_path / name
    f.write_text('')
    LMNFile(f, 'r')
    assert len(calls) == 1
