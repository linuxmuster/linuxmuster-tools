"""
Tests for edge cases:
  - Unsupported file extensions
  - Non-existent files (instantiation vs. __enter__)
  - Encoding detection and handling
"""

import os
import logging
import pytest
from unittest.mock import patch
from linuxmusterTools.lmnfile import LMNFile


# ── Unsupported extension ─────────────────────────────────────────────────────

class TestUnsupportedExtension:

    def test_unknown_extension_returns_none(self, tmp_path):
        f = tmp_path / 'data.xyz'
        f.write_text('content\n')
        assert LMNFile(str(f), 'r') is None

    def test_no_extension_returns_none(self, tmp_path):
        f = tmp_path / 'noextension'
        f.write_text('content\n')
        assert LMNFile(str(f), 'r') is None

    def test_wrong_extension_returns_none(self, tmp_path):
        # .json is not a supported format
        f = tmp_path / 'config.json'
        f.write_text('{"key": "value"}\n')
        assert LMNFile(str(f), 'r') is None

    def test_unknown_extension_fails_as_context_manager(self, tmp_path):
        f = tmp_path / 'data.xyz'
        f.write_text('content\n')
        # None has no __enter__ → AttributeError
        with pytest.raises((AttributeError, TypeError)):
            with LMNFile(str(f), 'r') as lmn:
                pass

    def test_yaml_with_wrong_extension_not_parsed(self, tmp_path):
        # A YAML-formatted file with .txt extension returns None
        f = tmp_path / 'config.txt'
        f.write_text('key: value\n')
        assert LMNFile(str(f), 'r') is None


# ── Non-existent files ────────────────────────────────────────────────────────

class TestNonExistentFile:

    def test_instantiation_does_not_raise_for_absent_yaml(self, tmp_path):
        # __init__ must not raise: detect_encoding returns utf-8, check_allowed_path passes
        f = tmp_path / 'absent.yml'
        assert not f.exists()
        lmn = LMNFile(str(f), 'r')
        assert lmn is not None

    def test_instantiation_does_not_raise_for_absent_csv(self, tmp_path):
        f = tmp_path / 'absent.csv'
        assert not f.exists()
        lmn = LMNFile(str(f), 'r', fieldnames=['a', 'b'])
        assert lmn is not None

    def test_instantiation_does_not_raise_for_absent_ini(self, tmp_path):
        f = tmp_path / 'absent.ini'
        assert not f.exists()
        lmn = LMNFile(str(f), 'r')
        assert lmn is not None

    def test_instantiation_does_not_raise_for_absent_startconf(self, tmp_path):
        f = tmp_path / 'start.conf'
        assert not f.exists()
        lmn = LMNFile(str(f), 'r')
        assert lmn is not None

    def test_instantiation_does_not_raise_for_absent_linbo(self, tmp_path):
        f = tmp_path / 'image.desc'
        assert not f.exists()
        lmn = LMNFile(str(f), 'r')
        assert lmn is not None

    def test_yaml_absent_file_created_as_root(self, tmp_path):
        f = tmp_path / 'new.yml'
        assert not f.exists()
        with patch('os.geteuid', return_value=0):
            with LMNFile(str(f), 'r') as lmn:
                data = lmn.read()
        assert f.exists()
        assert data is None  # empty file

    def test_yaml_absent_file_gets_restricted_permissions(self, tmp_path):
        f = tmp_path / 'new.yml'
        with patch('os.geteuid', return_value=0):
            with LMNFile(str(f), 'r') as lmn:
                lmn.read()
        assert oct(os.stat(str(f)).st_mode)[-3:] == '600'

    def test_yaml_absent_file_raises_as_non_root(self, tmp_path):
        f = tmp_path / 'absent.yml'
        lmn = LMNFile(str(f), 'r')
        with patch('os.geteuid', return_value=1000):
            with pytest.raises(FileNotFoundError):
                lmn.__enter__()

    def test_csv_absent_file_raises_on_enter(self, tmp_path):
        f = tmp_path / 'absent.csv'
        lmn = LMNFile(str(f), 'r', fieldnames=['a', 'b'])
        with pytest.raises(FileNotFoundError):
            lmn.__enter__()

    def test_config_absent_file_raises_on_enter(self, tmp_path):
        f = tmp_path / 'absent.ini'
        lmn = LMNFile(str(f), 'r')
        with pytest.raises(FileNotFoundError):
            lmn.__enter__()

    def test_startconf_absent_file_raises_on_enter(self, tmp_path):
        f = tmp_path / 'start.conf'
        lmn = LMNFile(str(f), 'r')
        with pytest.raises(FileNotFoundError):
            lmn.__enter__()

    def test_linbo_absent_file_raises_on_enter(self, tmp_path):
        f = tmp_path / 'image.desc'
        lmn = LMNFile(str(f), 'r')
        with pytest.raises(FileNotFoundError):
            lmn.__enter__()

    def test_absent_csv_has_bom_false(self, tmp_path):
        # has_BOM must be initialized to False even when the file does not exist
        f = tmp_path / 'absent.csv'
        lmn = LMNFile(str(f), 'r', fieldnames=['a'])
        assert lmn.has_BOM is False


# ── Encoding detection ────────────────────────────────────────────────────────

class TestEncoding:

    def test_encoding_defaults_to_utf8_for_absent_file(self, tmp_path):
        f = tmp_path / 'absent.yml'
        lmn = LMNFile(str(f), 'r')
        assert lmn.encoding == 'utf-8'

    def test_encoding_detected_for_utf8_file(self, tmp_path):
        f = tmp_path / 'config.yml'
        f.write_text('key: value\n', encoding='utf-8')
        lmn = LMNFile(str(f), 'r')
        # magic returns 'us-ascii' for pure ASCII, treated as utf-8
        assert lmn.encoding == 'utf-8'

    def test_encoding_detected_for_utf8_with_unicode(self, tmp_path):
        f = tmp_path / 'config.yml'
        f.write_text('name: école\n', encoding='utf-8')
        lmn = LMNFile(str(f), 'r')
        assert lmn.encoding == 'utf-8'

    def test_latin1_file_encoding_detected(self, tmp_path):
        f = tmp_path / 'data.csv'
        f.write_bytes('Müller;pc1\n'.encode('latin-1'))
        lmn = LMNFile(str(f), 'r', fieldnames=['name', 'host'])
        # magic should NOT return utf-8 for raw latin-1 bytes
        assert lmn.encoding != 'utf-8'

    def test_latin1_csv_readable_without_error(self, tmp_path):
        f = tmp_path / 'data.csv'
        f.write_bytes('Müller;pc1\nSchmidt;pc2\n'.encode('latin-1'))
        with LMNFile(str(f), 'r', fieldnames=['name', 'host']) as l:
            rows = l.read()
        assert len(rows) == 2

    def test_latin1_yaml_raises_unicode_error(self, tmp_path):
        # YAMLLoader opens the file without specifying encoding (always uses the
        # system default, UTF-8 on modern Linux). A latin-1 encoded YAML file
        # will therefore raise UnicodeDecodeError. This test documents that
        # limitation: YAML files must always be UTF-8.
        f = tmp_path / 'config.yml'
        f.write_bytes('name: Müller\n'.encode('latin-1'))
        with pytest.raises(UnicodeDecodeError):
            with LMNFile(str(f), 'r') as lmn:
                lmn.read()

    def test_bom_with_non_utf8_encoding_logs_info(self, tmp_path, caplog):
        # Simulate the case where has_BOM is True but encoding is not utf-8:
        # fix_bom() must log a warning instead of crashing.
        f = tmp_path / 'data.csv'
        f.write_bytes(b'\xef\xbb\xbf' + b'room;hostname\nroom1;pc1\n')
        lmn = LMNFile(str(f), 'r', fieldnames=['room', 'hostname'])
        assert lmn.has_BOM is True

        # Force a non-utf-8 encoding to trigger the warning branch
        lmn.encoding = 'iso-8859-1'
        # linuxmusterTools sets propagate=False, so caplog's root handler never
        # sees records from this package. Attach caplog.handler directly there.
        lmn_root_logger = logging.getLogger('linuxmusterTools')
        lmn_root_logger.addHandler(caplog.handler)
        try:
            with caplog.at_level(logging.INFO, logger='linuxmusterTools.lmnfile.lmnfile'):
                lmn.fix_bom()
        finally:
            lmn_root_logger.removeHandler(caplog.handler)

        assert any('Can not fix BOM' in r.message for r in caplog.records)

    def test_binary_file_treated_as_utf8(self, tmp_path):
        # magic returns 'binary' for binary files; lmnfile must fall back to utf-8
        f = tmp_path / 'image.desc'
        f.write_bytes(b'\x00\x01\x02\x03')
        lmn = LMNFile(str(f), 'r')
        assert lmn.encoding == 'utf-8'
