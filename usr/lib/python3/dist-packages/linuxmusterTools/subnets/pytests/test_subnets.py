"""
Tests for Subnets: loading/validating /etc/linuxmuster/subnets.csv and
triggering linuxmuster-import-subnets.
"""

import os
from datetime import datetime, timezone

import linuxmusterTools.subnets.subnets as subnets_module
from linuxmusterTools.subnets.subnets import Subnets, import_subnets, SETUP_FLAGS

FIELDNAMES = ['network', 'routerIp', 'beginRange', 'endRange', 'nameServer', 'nextServer', 'setupFlag']


def make_row(
    network='10.0.0.0/24',
    routerIp='10.0.0.1',
    beginRange='10.0.0.10',
    endRange='10.0.0.100',
    nameServer='',
    nextServer='',
    setupFlag='',
):
    return ';'.join([network, routerIp, beginRange, endRange, nameServer, nextServer, setupFlag])


def write_csv(tmp_path, lines, filename='subnets.csv'):
    """
    Write a semicolon-delimited subnets.csv with an explicit header row.
    The header is required here because, unlike the real
    /etc/linuxmuster/subnets.csv path, a tmp_path file does not match
    csv_fieldnames' automatic model detection (which requires the file to
    live under /etc/linuxmuster/), so LMNFile falls back to fieldnames=None
    and csv.DictReader needs a header row to know the field names.
    """
    path = tmp_path / filename
    header = ';'.join(FIELDNAMES)
    content = header + '\n' + '\n'.join(lines) + ('\n' if lines else '')
    path.write_text(content, encoding='utf-8')
    return path


def make_subnets(tmp_path, lines):
    csv_path = write_csv(tmp_path, lines)
    return Subnets(path=str(csv_path))


# ── load() ──────────────────────────────────────────────────────────────────

def test_load_parses_valid_rows(tmp_path):
    rows = [
        make_row(network='10.0.0.0/24', setupFlag=''),
        make_row(network='10.1.0.0/24', setupFlag='SETUP'),
    ]
    s = make_subnets(tmp_path, rows)
    assert len(s.subnets) == 2
    assert s.subnets[0]['network'] == '10.0.0.0/24'
    assert s.subnets[1]['setupFlag'] == 'SETUP'


def test_load_skips_comment_lines(tmp_path):
    rows = [
        '# this is a comment',
        make_row(network='10.0.0.0/24'),
    ]
    s = make_subnets(tmp_path, rows)
    assert len(s.subnets) == 1
    assert s.subnets[0]['network'] == '10.0.0.0/24'


def test_load_skips_empty_lines(tmp_path):
    rows = [
        make_row(network='10.0.0.0/24'),
        '',
        make_row(network='10.1.0.0/24'),
    ]
    s = make_subnets(tmp_path, rows)
    assert len(s.subnets) == 2


def test_networks_list_is_deduplicated(tmp_path):
    rows = [
        make_row(network='10.0.0.0/24', routerIp='10.0.0.1'),
        make_row(network='10.0.0.0/24', routerIp='10.0.0.2'),
    ]
    s = make_subnets(tmp_path, rows)
    assert len(s.subnets) == 2
    assert s.networks == ['10.0.0.0/24']


def test_csv_mtime_reflects_file_mtime(tmp_path):
    csv_path = write_csv(tmp_path, [make_row()])
    ts = 1700000000
    os.utime(csv_path, (ts, ts))
    s = Subnets(path=str(csv_path))
    expected = datetime.fromtimestamp(ts, tz=timezone.utc)
    assert s.csv_mtime == expected


def test_default_path_used_when_no_path_given(tmp_path, monkeypatch):
    csv_path = write_csv(tmp_path, [make_row()])
    monkeypatch.setattr(subnets_module, 'SUBNETS_PATH', str(csv_path))
    # __init__'s default argument was bound at import time, so we also need
    # to patch the bound default directly for Subnets() to pick up the change.
    monkeypatch.setattr(subnets_module.Subnets.__init__, '__defaults__', (str(csv_path),))

    s = subnets_module.Subnets()

    assert s.path == str(csv_path)
    assert len(s.subnets) == 1


# ── filter() / get_subnet() ──────────────────────────────────────────────────

def test_filter_returns_all_when_no_networks_given(tmp_path):
    rows = [
        make_row(network='10.0.0.0/24'),
        make_row(network='10.1.0.0/24'),
    ]
    s = make_subnets(tmp_path, rows)
    assert s.filter() == s.subnets


def test_filter_returns_matching_subset(tmp_path):
    rows = [
        make_row(network='10.0.0.0/24'),
        make_row(network='10.1.0.0/24'),
        make_row(network='10.2.0.0/24'),
    ]
    s = make_subnets(tmp_path, rows)
    filtered = s.filter(networks=['10.1.0.0/24'])
    assert len(filtered) == 1
    assert filtered[0]['network'] == '10.1.0.0/24'


def test_get_subnet_returns_matching_dict(tmp_path):
    rows = [make_row(network='10.0.0.0/24'), make_row(network='10.1.0.0/24')]
    s = make_subnets(tmp_path, rows)
    subnet = s.get_subnet('10.1.0.0/24')
    assert subnet is not None
    assert subnet['network'] == '10.1.0.0/24'


def test_get_subnet_returns_none_when_missing(tmp_path):
    s = make_subnets(tmp_path, [make_row(network='10.0.0.0/24')])
    assert s.get_subnet('192.168.0.0/24') is None


# ── check_conf() ──────────────────────────────────────────────────────────────

def test_check_conf_valid_configuration_returns_false(tmp_path):
    rows = [
        make_row(network='10.0.0.0/24', routerIp='10.0.0.1', beginRange='10.0.0.10',
                 endRange='10.0.0.100', nameServer='10.0.0.1', nextServer='10.0.0.1', setupFlag=''),
        make_row(network='10.1.0.0/24', routerIp='10.1.0.1', beginRange='10.1.0.10',
                 endRange='10.1.0.100', nameServer='', nextServer='', setupFlag='SETUP'),
    ]
    s = make_subnets(tmp_path, rows)
    assert s.check_conf() is False


def test_check_conf_invalid_cidr_reports_error(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': 'not-a-network', 'routerIp': '10.0.0.1', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': '',
    }]
    report = s.check_conf()
    assert report is not False
    assert "not-a-network is not a valid network in CIDR notation" in report


def test_check_conf_host_bits_set_reports_error(tmp_path):
    # 10.0.0.5/24 is not a valid network address (host bits set), so
    # ipaddress.ip_network(..., strict=True) raises ValueError.
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': '10.0.0.5/24', 'routerIp': '10.0.0.1', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': '',
    }]
    report = s.check_conf()
    assert report is not False
    assert "10.0.0.5/24 is not a valid network in CIDR notation" in report


def test_check_conf_router_ip_outside_network(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': '10.0.0.0/24', 'routerIp': '192.168.1.1', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': '',
    }]
    report = s.check_conf()
    assert report is not False
    assert "192.168.1.1 (routerIp) is not part of network 10.0.0.0/24" in report


def test_check_conf_invalid_ip_format_for_required_field(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': '10.0.0.0/24', 'routerIp': 'not-an-ip', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': '',
    }]
    report = s.check_conf()
    assert report is not False
    assert "not-an-ip is not a valid ip address (routerIp of 10.0.0.0/24)" in report


def test_check_conf_empty_required_field_reports_error(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', 'beginRange': '',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': '',
    }]
    report = s.check_conf()
    assert report is not False
    assert "10.0.0.0/24: beginRange must not be empty" in report


def test_check_conf_optional_fields_empty_are_valid(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': '',
    }]
    assert s.check_conf() is False


def test_check_conf_invalid_optional_ip_reports_error(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': 'bogus-ip', 'nextServer': '', 'setupFlag': '',
    }]
    report = s.check_conf()
    assert report is not False
    assert "bogus-ip is not a valid ip address (nameServer of 10.0.0.0/24)" in report


def test_check_conf_invalid_setup_flag_reports_error(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    s.subnets = [{
        'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': 'BOGUS',
    }]
    report = s.check_conf()
    assert report is not False
    assert "BOGUS is not a valid setup flag for 10.0.0.0/24 (allowed: SETUP or empty)" in report


def test_check_conf_accepts_all_setup_flags(tmp_path):
    for flag in SETUP_FLAGS:
        s = make_subnets(tmp_path, [make_row()])
        s.subnets = [{
            'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', 'beginRange': '10.0.0.2',
            'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': flag,
        }]
        assert s.check_conf() is False


def test_check_conf_duplicate_network_reports_error(tmp_path):
    s = make_subnets(tmp_path, [make_row()])
    row_a = {
        'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', 'beginRange': '10.0.0.2',
        'endRange': '10.0.0.3', 'nameServer': '', 'nextServer': '', 'setupFlag': '',
    }
    row_b = dict(row_a, routerIp='10.0.0.4')
    s.subnets = [row_a, row_b]
    report = s.check_conf()
    assert report == ['10.0.0.0/24 is defined 2 times']


# ── import_subnets() ──────────────────────────────────────────────────────────

def test_import_subnets_success(monkeypatch):
    captured = {}

    class FakeCompletedProcess:
        returncode = 0
        stdout = b'all good\n'

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        captured['kwargs'] = kwargs
        return FakeCompletedProcess()

    monkeypatch.setattr(subnets_module.subprocess, 'run', fake_run)

    result = import_subnets()

    assert result == {'returncode': 0, 'output': 'all good\n'}
    assert captured['cmd'] == [subnets_module.IMPORT_COMMAND]
    assert captured['kwargs']['stdout'] == subnets_module.subprocess.PIPE
    assert captured['kwargs']['stderr'] == subnets_module.subprocess.STDOUT


def test_import_subnets_reports_nonzero_returncode(monkeypatch):
    class FakeCompletedProcess:
        returncode = 1
        stdout = b'something failed\n'

    monkeypatch.setattr(subnets_module.subprocess, 'run', lambda *a, **k: FakeCompletedProcess())

    result = import_subnets()

    assert result['returncode'] == 1
    assert result['output'] == 'something failed\n'


def test_import_subnets_decodes_invalid_utf8_with_replace(monkeypatch):
    class FakeCompletedProcess:
        returncode = 0
        stdout = b'\xff\xfe garbled'

    monkeypatch.setattr(subnets_module.subprocess, 'run', lambda *a, **k: FakeCompletedProcess())

    result = import_subnets()

    # Must not raise UnicodeDecodeError thanks to errors='replace'.
    assert isinstance(result['output'], str)
    assert result['returncode'] == 0
