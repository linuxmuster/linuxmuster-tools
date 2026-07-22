import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest

import linuxmusterTools.lmnfile.lmnfile as lmnfile_module
import linuxmusterTools.devices.devices as devices_module
from linuxmusterTools.lmnfile import LMNFile as RealLMNFile
from linuxmusterTools.lmnfile.fieldnames import csv_fieldnames

DEVICES_FIELDNAMES = csv_fieldnames['devices']


def _real_devices_path(school):
    """
    Mirror the hardcoded path formula used in Devices.switch(), so tests can
    compute where a given school's inventory file "really" lives before it
    gets redirected under tmp_path.
    """
    prefix = f'{school}.' if school != 'default-school' else ''
    return f'/etc/linuxmuster/sophomorix/{school}/{prefix}devices.csv'


@pytest.fixture(autouse=True)
def patch_allowed_paths(tmp_path, monkeypatch):
    """
    Replace ALLOWED_PATHS with the test's temporary directory so every test
    can read and write files without needing real system paths.
    The monkeypatch fixture automatically restores the original value after
    each test.
    """
    monkeypatch.setattr(lmnfile_module, 'ALLOWED_PATHS', [str(tmp_path)])


@pytest.fixture(autouse=True)
def redirect_devices_storage(tmp_path, monkeypatch):
    """
    Devices.switch() builds its inventory path as a hardcoded literal
    (f'/etc/linuxmuster/sophomorix/{school}/{prefix}devices.csv') instead of
    going through any configurable setting, so it can't be pointed at
    tmp_path directly. Wrap the LMNFile name as imported into the devices
    module so every call transparently reads/writes an equivalent path
    rooted at tmp_path instead of the real system inventory.

    Also inject the devices.csv fieldnames explicitly: LMNFile normally
    infers them by checking that the path starts with '/etc/linuxmuster/',
    which is no longer true once the path is redirected under tmp_path.
    """

    def factory(file, mode, delimiter=';', fieldnames=None, convert_values=True):
        redirected = str(tmp_path / file.lstrip('/'))
        if fieldnames is None and file.endswith('devices.csv'):
            fieldnames = DEVICES_FIELDNAMES
        return RealLMNFile(
            redirected, mode, delimiter=delimiter,
            fieldnames=fieldnames, convert_values=convert_values
        )

    monkeypatch.setattr(devices_module, 'LMNFile', factory)


@pytest.fixture
def devices_path(tmp_path):
    """
    Return a function mapping a school name to the tmp_path location that
    Devices() will actually read/write for that school (mirrors the
    redirection performed by redirect_devices_storage).
    """

    def _path(school='default-school'):
        return tmp_path / _real_devices_path(school).lstrip('/')

    return _path


def _row(**overrides):
    """
    Build one devices.csv data row (as a list of string fields, in the
    order expected by csv_fieldnames['devices']) with sane defaults that
    pass NameChecker validation, overridable per test.
    """
    defaults = {
        'room': 'r101',
        'hostname': 'pc01',
        'group': 'g-pcs',
        'mac': 'AA:BB:CC:DD:EE:01',
        'ip': '10.16.1.10',
        'officeKey': '',
        'windowsKey': '',
        'dhcpOptions': '',
        'sophomorixRole': 'classroom-studentcomputer',
        'lmnReserved10': '',
        'pxeFlag': '1',
        'lmnReserved12': '',
        'lmnReserved13': '',
        'lmnReserved14': '',
        'sophomorixComment': '',
        'options': '',
    }
    defaults.update(overrides)
    return [str(defaults[field]) for field in DEVICES_FIELDNAMES]


@pytest.fixture
def make_device_row():
    return _row


@pytest.fixture
def write_devices_csv(devices_path):
    """
    Write a devices.csv-like file (semicolon separated, no header row) for
    the given school, creating parent directories as needed, and return the
    path it was written to.

    :param rows: list of rows, each produced by make_device_row()
    :param school: school name (defaults to 'default-school')
    """

    def _write(rows, school='default-school'):
        path = devices_path(school)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = '\n'.join(';'.join(row) for row in rows) + '\n'
        path.write_text(content, encoding='utf-8')
        return path

    return _write
