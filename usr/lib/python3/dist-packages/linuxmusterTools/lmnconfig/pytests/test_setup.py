"""
Tests for linuxmusterTools.lmnconfig.setup.SetupConfig.
"""

# NB: the module is aliased to `lmn_setup_module` rather than `setup_module`
# -- pytest treats a top-level name literally called `setup_module` in a
# test file as its own xunit-style module setup hook, not as a plain import.
import linuxmusterTools.lmnconfig.setup as lmn_setup_module
from linuxmusterTools.lmnconfig.setup import SetupConfig

from .conftest import isfile_only_for

SETUP_PATH = '/var/lib/linuxmuster/setup.ini'


def test_file_not_found_gives_empty_config(monkeypatch):
    monkeypatch.setattr(lmn_setup_module.os.path, 'isfile', lambda path: False)

    config = SetupConfig()

    assert config.config == {}


def test_file_found_and_default_school_reads_config(monkeypatch, fake_lmnfile):
    canned = {'SCHOOL': {'name': 'default-school'}}
    monkeypatch.setattr(lmn_setup_module.os.path, 'isfile', isfile_only_for(SETUP_PATH))
    monkeypatch.setattr(lmn_setup_module, 'LMNFile', fake_lmnfile(canned))

    config = SetupConfig(school='default-school')

    assert config.config == canned


def test_file_found_but_non_default_school_is_ignored(monkeypatch, fake_lmnfile):
    # Current behavior: even though the setup.ini file exists, the config is
    # only read when school == 'default-school' (comment says "TODO: setup
    # path for multischool ?" -- multischool setups never get a config here).
    canned = {'SCHOOL': {'name': 'default-school'}}
    monkeypatch.setattr(lmn_setup_module.os.path, 'isfile', isfile_only_for(SETUP_PATH))
    monkeypatch.setattr(lmn_setup_module, 'LMNFile', fake_lmnfile(canned))

    config = SetupConfig(school='some-other-school')

    assert config.config == {}
