"""
Tests for linuxmusterTools.lmnconfig.sophomorix:
SchoolConfig, MultiOrderedDict, SophomorixIni, SophomorixConf.
"""

import configparser

import pytest

import linuxmusterTools.lmnconfig.sophomorix as sophomorix_module
from linuxmusterTools.lmnconfig.sophomorix import (
    SchoolConfig,
    MultiOrderedDict,
    SophomorixIni,
    SophomorixConf,
)

from .conftest import isfile_only_for


# ---------------------------------------------------------------------------
# SchoolConfig
# ---------------------------------------------------------------------------

def test_school_config_default_school_path_has_no_prefix(monkeypatch, fake_lmnfile):
    path = '/etc/linuxmuster/sophomorix/default-school/school.conf'
    canned = {'global': {'SCHOOLNAME': 'Default School'}}

    monkeypatch.setattr(sophomorix_module.os.path, 'isfile', isfile_only_for(path))
    lmnfile = fake_lmnfile(canned)
    monkeypatch.setattr(sophomorix_module, 'LMNFile', lmnfile)

    config = SchoolConfig(school='default-school')

    assert config.config == canned
    assert lmnfile.path == path


def test_school_config_other_school_path_has_school_prefix(monkeypatch, fake_lmnfile):
    path = '/etc/linuxmuster/sophomorix/myschool/myschool.school.conf'
    canned = {'global': {'SCHOOLNAME': 'My School'}}

    monkeypatch.setattr(sophomorix_module.os.path, 'isfile', isfile_only_for(path))
    lmnfile = fake_lmnfile(canned)
    monkeypatch.setattr(sophomorix_module, 'LMNFile', lmnfile)

    config = SchoolConfig(school='myschool')

    assert config.config == canned
    assert lmnfile.path == path


def test_school_config_file_not_found_gives_empty_config(monkeypatch):
    monkeypatch.setattr(sophomorix_module.os.path, 'isfile', lambda path: False)

    config = SchoolConfig(school='pytest-nonexistent-school')

    assert config.config == {}


# ---------------------------------------------------------------------------
# MultiOrderedDict
# ---------------------------------------------------------------------------

def test_multi_ordered_dict_first_assignment_of_list_is_plain_set():
    d = MultiOrderedDict()
    d['a'] = ['x']
    assert d['a'] == ['x']


def test_multi_ordered_dict_second_list_assignment_extends():
    d = MultiOrderedDict()
    d['a'] = ['x']
    d['a'] = ['y']
    assert d['a'] == ['x', 'y']


def test_multi_ordered_dict_non_list_value_overwrites_normally():
    d = MultiOrderedDict()
    d['a'] = 'x'
    d['a'] = 'y'
    assert d['a'] == 'y'


def test_multi_ordered_dict_list_then_non_list_overwrites():
    d = MultiOrderedDict()
    d['a'] = ['x']
    d['a'] = 'y'
    assert d['a'] == 'y'


# ---------------------------------------------------------------------------
# SophomorixIni.sanitize (pure static method, no file access needed)
# ---------------------------------------------------------------------------

def test_sanitize_scalar_without_comment():
    assert SophomorixIni.sanitize('value') == 'value'


def test_sanitize_scalar_strips_inline_comment():
    assert SophomorixIni.sanitize('value # a comment') == 'value'


def test_sanitize_scalar_strips_surrounding_whitespace():
    assert SophomorixIni.sanitize('  value  # comment') == 'value'


def test_sanitize_multiline_value_splits_and_strips_each_line():
    value = 'line1 # c1\nline2 # c2\nline3'
    assert SophomorixIni.sanitize(value) == ['line1', 'line2', 'line3']


def test_sanitize_multiline_value_without_any_comments():
    value = 'line1\nline2'
    assert SophomorixIni.sanitize(value) == ['line1', 'line2']


# ---------------------------------------------------------------------------
# SophomorixIni.get() and __init__ (ConfigParser().read() is monkeypatched
# so the test is hermetic and does not depend on the real
# /usr/share/sophomorix/devel/sophomorix.ini file on this machine).
# ---------------------------------------------------------------------------

SYNTHETIC_INI = """
[ROLE_USER]
teacher = Teacher
student = Student

[computerrole.classroom-studentcomputer]
somekey = somevalue

[computerrole.faculty-teachercomputer]
otherkey = othervalue

[SOME_SECTION]
single = value # trailing comment
multi = line1 # c1
    line2 # c2
"""


@pytest.fixture
def synthetic_ini(tmp_path):
    ini_file = tmp_path / 'sophomorix.ini'
    ini_file.write_text(SYNTHETIC_INI)
    return ini_file


@pytest.fixture
def sophomorix_ini(monkeypatch, synthetic_ini):
    """
    A real SophomorixIni instance, but with ConfigParser.read redirected to
    the synthetic temp file instead of the hardcoded production path, so the
    test is independent of what's actually installed on this machine.
    """
    real_read = configparser.ConfigParser.read

    def fake_read(self, filenames, encoding=None):
        return real_read(self, str(synthetic_ini), encoding=encoding)

    monkeypatch.setattr(configparser.ConfigParser, 'read', fake_read)
    return SophomorixIni()


def test_sophomorix_ini_sections_are_parsed(sophomorix_ini):
    assert 'ROLE_USER' in sophomorix_ini.sections
    assert 'SOME_SECTION' in sophomorix_ini.sections


def test_sophomorix_ini_computerrole_strips_prefix(sophomorix_ini):
    assert set(sophomorix_ini.computerrole) == {
        'classroom-studentcomputer',
        'faculty-teachercomputer',
    }


def test_sophomorix_ini_userrole_comes_from_role_user_section(sophomorix_ini):
    assert set(sophomorix_ini.userrole) == {'teacher', 'student'}


def test_sophomorix_ini_dict_values_are_sanitized(sophomorix_ini):
    assert sophomorix_ini.dict['SOME_SECTION']['single'] == 'value'
    assert sophomorix_ini.dict['SOME_SECTION']['multi'] == ['line1', 'line2']


def test_sophomorix_ini_get_returns_sanitized_value(sophomorix_ini):
    assert sophomorix_ini.get('SOME_SECTION', 'single') == 'value'
    assert sophomorix_ini.get('SOME_SECTION', 'multi') == ['line1', 'line2']


def test_sophomorix_ini_get_missing_section_raises_key_error(sophomorix_ini):
    with pytest.raises(KeyError):
        sophomorix_ini.get('NO_SUCH_SECTION', 'single')


def test_sophomorix_ini_get_missing_key_raises_key_error(sophomorix_ini):
    with pytest.raises(KeyError):
        sophomorix_ini.get('SOME_SECTION', 'no_such_key')


def test_sophomorix_ini_clientrole_is_hardcoded_list(sophomorix_ini):
    assert sophomorix_ini.clientrole == [
        'classroom-teachercomputer',
        'classroom-studentcomputer',
        'faculty-teachercomputer',
        'staffcomputer',
        'thinclient',
        'iponly',
    ]


# ---------------------------------------------------------------------------
# SophomorixConf
# ---------------------------------------------------------------------------

SOPHOMORIX_CONF_PATH = '/etc/linuxmuster/sophomorix/sophomorix.conf'


def test_sophomorix_conf_file_not_found_gives_empty_data(monkeypatch):
    monkeypatch.setattr(sophomorix_module.os.path, 'isfile', lambda path: False)

    config = SophomorixConf()

    assert config.data == {}


def test_sophomorix_conf_file_found_reads_data_attribute(monkeypatch, fake_lmnfile):
    canned = {'global': {'LANG': 'DE'}}
    monkeypatch.setattr(sophomorix_module.os.path, 'isfile', isfile_only_for(SOPHOMORIX_CONF_PATH))
    monkeypatch.setattr(sophomorix_module, 'LMNFile', fake_lmnfile(canned))

    config = SophomorixConf()

    # Note: SophomorixConf reads config.data (not config.read()), unlike the
    # other classes in this module.
    assert config.data == canned
