"""
Tests for linuxmusterTools.lmnconfig.webui.CustomFieldsConfig.
"""

import pytest

import linuxmusterTools.lmnconfig.webui as webui_module
from linuxmusterTools.lmnconfig.webui import CustomFieldsConfig

ROLES = ['globaladministrators', 'schooladministrators', 'students', 'teachers']
CONFIG_TYPES = ['custom', 'customDisplay', 'customMulti', 'passwordTemplates', 'proxyAddresses']


def expected_path(school):
    return f'/etc/linuxmuster/sophomorix/{school}/custom_fields.yml'


@pytest.fixture(autouse=True)
def empty_cache(monkeypatch):
    monkeypatch.setattr(webui_module, '_CACHE', {})


def mtime_only_for(path, mtime=1):
    """
    Replacement for webui.get_utc_mtime: only the given path exists, with a
    mtime which can be changed afterwards through the returned dict.
    """

    state = {'mtime': mtime}

    def get_mtime(candidate):
        return state['mtime'] if str(candidate) == path else None

    return get_mtime, state


class CountingLMNFile:
    """
    Wrap a FakeLMNFile to count how many times the file is opened.
    """

    def __init__(self, fake):
        self.fake = fake
        self.opened = 0

    def __call__(self, path, mode, *args, **kwargs):
        self.opened += 1
        return self.fake(path, mode, *args, **kwargs)


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

    monkeypatch.setattr(webui_module, 'get_utc_mtime', mtime_only_for(path)[0])
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
    monkeypatch.setattr(webui_module, 'get_utc_mtime', mtime_only_for(expected_path('default-school'))[0])
    monkeypatch.setattr(webui_module, 'LMNFile', fake_lmnfile({'custom': {'students': {'x': 1}}}))

    config = CustomFieldsConfig(school='default-school')

    assert config.config == {}
    for role in ROLES:
        assert not hasattr(config, role)


def test_unchanged_file_is_parsed_only_once(monkeypatch, fake_lmnfile):
    path = expected_path('pytest-school')
    counting = CountingLMNFile(fake_lmnfile({'custom': {'students': {'1': {'title': 'a'}}}}))
    monkeypatch.setattr(webui_module, 'get_utc_mtime', mtime_only_for(path)[0])
    monkeypatch.setattr(webui_module, 'LMNFile', counting)

    first = CustomFieldsConfig(school='pytest-school')
    second = CustomFieldsConfig(school='pytest-school')

    assert counting.opened == 1
    assert second.config == first.config
    assert second.students['custom'] == {'1': {'title': 'a'}}


def test_changed_mtime_reads_the_file_again(monkeypatch, fake_lmnfile):
    # The webui edits custom_fields.yml while lmnapi keeps running.
    path = expected_path('pytest-school')
    counting = CountingLMNFile(fake_lmnfile({'custom': {}}))
    get_mtime, state = mtime_only_for(path)
    monkeypatch.setattr(webui_module, 'get_utc_mtime', get_mtime)
    monkeypatch.setattr(webui_module, 'LMNFile', counting)

    CustomFieldsConfig(school='pytest-school')
    state['mtime'] = 2
    CustomFieldsConfig(school='pytest-school')

    assert counting.opened == 2


def test_cache_is_per_school(monkeypatch, fake_lmnfile):
    counting = CountingLMNFile(fake_lmnfile({'custom': {}}))
    monkeypatch.setattr(webui_module, 'get_utc_mtime', lambda path: 1)
    monkeypatch.setattr(webui_module, 'LMNFile', counting)

    CustomFieldsConfig(school='school-a')
    CustomFieldsConfig(school='school-b')
    CustomFieldsConfig(school='school-a')

    assert counting.opened == 2


def test_deleted_file_gives_empty_config(monkeypatch, fake_lmnfile):
    path = expected_path('pytest-school')
    get_mtime, state = mtime_only_for(path)
    monkeypatch.setattr(webui_module, 'get_utc_mtime', get_mtime)
    monkeypatch.setattr(webui_module, 'LMNFile', fake_lmnfile({'custom': {'students': {'x': 1}}}))

    CustomFieldsConfig(school='pytest-school')
    state['mtime'] = None

    assert CustomFieldsConfig(school='pytest-school').config == {}
