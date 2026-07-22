import gzip
from datetime import datetime

import pytest

import linuxmusterTools.samba_util.log as log_module
from linuxmusterTools.samba_util.log import (
    check_audit_level,
    format_log_data,
    parse_log_content,
    last_login,
)


# Real sample lines captured from an actual `log.samba` audit trail (dates
# adjusted to keep the fixtures self-contained).
KERBEROS_OK_LINE = (
    "  Auth: [Kerberos KDC,ENC-TS Pre-authentication] user [(null)]\\[ga@UNPEUD.INFO] "
    "at [Wed, 22 Jul 2026 15:42:08.629671 CEST] with [aes256-cts-hmac-sha1-96] "
    "status [NT_STATUS_OK] workstation [(null)] remote host [ipv4:10.0.0.1:52256] "
    "became [UNPEUD]\\[ga] [S-1-5-21-2783324004-2870359872-1600671279-2248]. local host [NULL] "
)
KERBEROS_FAILED_LINE = (
    "  Auth: [Kerberos KDC,ENC-TS Pre-authentication] user [(null)]\\[ga@UNPEUD.INFO] "
    "at [Wed, 22 Jul 2026 15:42:08.635994 CEST] with [aes256-cts-hmac-sha1-96] "
    "status [NT_STATUS_PROTOCOL_UNREACHABLE] workstation [(null)] remote host [ipv4:10.0.0.1:53890] "
    "mapped to [UNPEUD]\\[ga]. local host [NULL] "
)
MACHINE_ACCOUNT_LINE = (
    "  Auth: [Kerberos KDC,ENC-TS Pre-authentication] user [(null)]\\[PC01$@UNPEUD.INFO] "
    "at [Thu, 23 Jul 2026 08:00:00.000000 CEST] with [aes256-cts-hmac-sha1-96] "
    "status [NT_STATUS_OK] workstation [(null)] remote host [ipv4:10.0.0.9:12345] "
    "became [UNPEUD]\\[PC01$] [S-1-5-21-0000000000-0000000000-0000000000-1234]. local host [NULL] "
)


# --- check_audit_level -----------------------------------------------------

def test_check_audit_level_true_when_auth_audit_high(monkeypatch):
    monkeypatch.setattr(log_module, 'LOG_LEVEL', {'auth_audit': 3, 'general': 1})
    assert check_audit_level() is True


def test_check_audit_level_true_when_general_high(monkeypatch):
    monkeypatch.setattr(log_module, 'LOG_LEVEL', {'general': 3})
    assert check_audit_level() is True


def test_check_audit_level_false_when_both_low(monkeypatch, caplog):
    monkeypatch.setattr(log_module, 'LOG_LEVEL', {'auth_audit': 2, 'general': 1})
    assert check_audit_level() is False


def test_check_audit_level_uses_defaults_when_keys_missing(monkeypatch):
    monkeypatch.setattr(log_module, 'LOG_LEVEL', {})
    assert check_audit_level() is False


# --- format_log_data --------------------------------------------------------

def test_format_log_data_parses_successful_kerberos_line():
    data = format_log_data(KERBEROS_OK_LINE)
    assert data == {
        'user': 'ga',
        'datetime': datetime(2026, 7, 22, 15, 42, 8),
        'ip': '10.0.0.1',
    }


def test_format_log_data_parses_failed_kerberos_line():
    data = format_log_data(KERBEROS_FAILED_LINE)
    assert data['user'] == 'ga'
    assert data['ip'] == '10.0.0.1'


def test_format_log_data_returns_empty_for_non_kerberos_line():
    line = "  Auth: [NTLMSSP] user [(null)]\\[ga@UNPEUD.INFO] at [Wed, 22 Jul 2026 15:42:08.629671 CEST]"
    assert format_log_data(line) == {}


def test_format_log_data_returns_empty_when_no_at_sign():
    line = "  Auth: [Kerberos KDC,ENC-TS Pre-authentication] user [(null)]\\[ga_no_domain] at [x]"
    assert format_log_data(line) == {}


def test_format_log_data_returns_empty_for_short_line():
    assert format_log_data("no brackets here") == {}
    assert format_log_data("only [one]") == {}


# --- parse_log_content -------------------------------------------------------

def test_parse_log_content_filters_by_pattern_and_dedupes():
    lines = [
        KERBEROS_OK_LINE,
        KERBEROS_OK_LINE,  # exact duplicate within the same second: ignored
        "some unrelated line without the pattern",
        KERBEROS_FAILED_LINE,
    ]
    logs = parse_log_content(lines, "became")

    assert len(logs) == 1
    assert logs[0]['user'] == 'ga'


def test_parse_log_content_skips_machine_accounts():
    logs = parse_log_content([MACHINE_ACCOUNT_LINE], "became")
    assert logs == []


def test_parse_log_content_decodes_bytes_lines():
    logs = parse_log_content([KERBEROS_OK_LINE.encode()], "became")
    assert len(logs) == 1
    assert logs[0]['user'] == 'ga'


def test_parse_log_content_ignores_lines_without_match():
    logs = parse_log_content(["irrelevant"], "became")
    assert logs == []


# --- last_login --------------------------------------------------------------

def _write(path, content):
    path.write_text(content, encoding='utf-8')


def test_last_login_returns_empty_when_audit_level_too_low(tmp_path, monkeypatch):
    monkeypatch.setattr(log_module, 'LOG_LEVEL', {'auth_audit': 1, 'general': 1})
    # Point at files that don't exist: if last_login() tried to open them
    # despite the low audit level, this would raise instead of returning [].
    monkeypatch.setattr(log_module, 'SAMBA_LOG', str(tmp_path / 'missing.samba'))
    monkeypatch.setattr(log_module, 'SAMBA_LOG_OLD', str(tmp_path / 'missing.samba.1'))

    assert last_login("became") == []


def test_last_login_merges_and_sorts_current_and_old_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(log_module, 'LOG_LEVEL', {'auth_audit': 3})

    current_log = tmp_path / 'log.samba'
    old_log = tmp_path / 'log.samba.1'

    older_line = KERBEROS_OK_LINE.replace("22 Jul 2026 15:42:08", "20 Jul 2026 09:00:00")
    newer_line = KERBEROS_OK_LINE.replace("22 Jul 2026 15:42:08", "23 Jul 2026 09:00:00")

    _write(current_log, newer_line + "\n")
    _write(old_log, older_line + "\n")

    monkeypatch.setattr(log_module, 'SAMBA_LOG', str(current_log))
    monkeypatch.setattr(log_module, 'SAMBA_LOG_OLD', str(old_log))
    monkeypatch.setattr(log_module.glob, 'glob', lambda pattern: [])

    logs = last_login("became")

    assert [l['datetime'] for l in logs] == sorted(
        (l['datetime'] for l in logs), reverse=True
    )
    assert logs[0]['datetime'] == datetime(2026, 7, 23, 9, 0, 0)
    assert logs[-1]['datetime'] == datetime(2026, 7, 20, 9, 0, 0)


def test_last_login_includes_gz_files_only_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(log_module, 'LOG_LEVEL', {'auth_audit': 3})

    current_log = tmp_path / 'log.samba'
    old_log = tmp_path / 'log.samba.1'
    _write(current_log, "")
    _write(old_log, "")

    gz_line = KERBEROS_OK_LINE.replace("22 Jul 2026 15:42:08", "01 Jan 2026 00:00:00")
    gz_path = tmp_path / 'log.samba.2.gz'
    with gzip.open(gz_path, 'wb') as f:
        f.write((gz_line + "\n").encode())

    monkeypatch.setattr(log_module, 'SAMBA_LOG', str(current_log))
    monkeypatch.setattr(log_module, 'SAMBA_LOG_OLD', str(old_log))
    # log.py globs a hardcoded absolute path ('/var/log/samba/log.samba*gz')
    # instead of deriving it from SAMBA_LOG, so it can't be redirected to
    # tmp_path just by patching SAMBA_LOG/SAMBA_LOG_OLD: the glob() call
    # itself has to be patched too.
    monkeypatch.setattr(log_module.glob, 'glob', lambda pattern: [str(gz_path)])

    assert last_login("became", include_gz=False) == []

    logs = last_login("became", include_gz=True)
    assert len(logs) == 1
    assert logs[0]['datetime'] == datetime(2026, 1, 1, 0, 0, 0)
