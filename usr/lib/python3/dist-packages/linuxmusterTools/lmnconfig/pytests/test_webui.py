"""
Tests for linuxmusterTools.lmnconfig.webui.CustomFieldsConfig.
"""

import linuxmusterTools.lmnconfig.webui as webui_module
from linuxmusterTools.lmnconfig.webui import CustomFieldsConfig

from .conftest import isfile_only_for

ROLES = ['globaladministrators', 'schooladministrators', 'students', 'teachers']
CONFIG_TYPES = ['custom', 'customDisplay', 'customMulti', 'passwordTemplates', 'proxyAddresses']


def expected_path(school):
    return f'/etc/linuxmuster/sophomorix/{school}/custom_fields.yml'


def test_file_not_found_gives_empty_config_and_empty_role_dicts(monkeypatch):
    # A school name that certainly has no custom_fields.yml on disk.
    school = 'pytest-nonexistent-school'
    config = CustomFieldsConfig(school=school)

    assert config.config == {}
    for role in ROLES:
        role_config = getattr(config, role)
        for config_type in CONFIG_TYPES:
            assert role_config[config_type] == {}


def test_file_found_is_read_and_split_per_role(monkeypatch, fake_lmnfile):
    school = 'pytest-school'
    path = expected_path(school)

    canned = {
        'custom': {
            'students': {'field1': 'value1'},
            'teachers': {'field2': 'value2'},
        },
        'customDisplay': {
            'students': {'displayed': True},
        },
        'customMulti': {},
        'passwordTemplates': {
            'teachers': {'template': 'abc'},
        },
        'proxyAddresses': {},
    }

    monkeypatch.setattr(webui_module.os.path, 'isfile', isfile_only_for(path))
    monkeypatch.setattr(webui_module, 'LMNFile', fake_lmnfile(canned))

    config = CustomFieldsConfig(school=school)

    assert config.config == canned
    assert config.students['custom'] == {'field1': 'value1'}
    assert config.students['customDisplay'] == {'displayed': True}
    assert config.teachers['custom'] == {'field2': 'value2'}
    assert config.teachers['passwordTemplates'] == {'template': 'abc'}
    # Roles/config types absent from the canned data fall back to {}
    assert config.globaladministrators['custom'] == {}
    assert config.students['proxyAddresses'] == {}


def test_webui_import_true_short_circuits_before_role_attributes_are_set(monkeypatch, fake_lmnfile):
    # Documents current behavior: when WEBUI_IMPORT is truthy, __init__
    # returns immediately after setting self.config = {}, so none of the
    # per-role attributes (self.students, self.teachers, ...) ever get set.
    monkeypatch.setattr(webui_module, 'WEBUI_IMPORT', True)
    # Even if the file "exists" and LMNFile has content, WEBUI_IMPORT must win.
    monkeypatch.setattr(webui_module.os.path, 'isfile', isfile_only_for(expected_path('default-school')))
    monkeypatch.setattr(webui_module, 'LMNFile', fake_lmnfile({'custom': {'students': {'x': 1}}}))

    config = CustomFieldsConfig(school='default-school')

    assert config.config == {}
    for role in ROLES:
        assert not hasattr(config, role)
