"""
Tests for get_utc_mtime (a file's mtime as a UTC datetime) and
linbo_timestamp_to_epoch (a LINBO YYYYMMDDHHMI timestamp as an epoch).
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from linuxmusterTools.common.timestamps import get_utc_mtime, linbo_timestamp_to_epoch


def test_get_utc_mtime_missing_file_returns_none(tmp_path):
    missing = tmp_path / "does-not-exist.txt"
    assert get_utc_mtime(missing) is None


def test_get_utc_mtime_returns_utc_datetime_matching_mtime(tmp_path):
    target = tmp_path / "somefile.txt"
    target.write_text("content")

    # Fix mtime to a known, arbitrary point in time (avoid datetime.now()).
    fixed_epoch = 1_700_000_000  # 2023-11-14T22:13:20Z
    os.utime(target, (fixed_epoch, fixed_epoch))

    result = get_utc_mtime(target)

    assert result is not None
    assert result.tzinfo == timezone.utc
    assert result == datetime.fromtimestamp(fixed_epoch, tz=timezone.utc)


def test_get_utc_mtime_reflects_mtime_updates(tmp_path):
    target = tmp_path / "somefile.txt"
    target.write_text("content")

    first_epoch = 1_600_000_000
    second_epoch = 1_700_000_000

    os.utime(target, (first_epoch, first_epoch))
    first_result = get_utc_mtime(target)

    os.utime(target, (second_epoch, second_epoch))
    second_result = get_utc_mtime(target)

    assert first_result == datetime.fromtimestamp(first_epoch, tz=timezone.utc)
    assert second_result == datetime.fromtimestamp(second_epoch, tz=timezone.utc)
    assert second_result > first_result


def test_get_utc_mtime_returns_none_on_os_error(tmp_path, monkeypatch):
    target = tmp_path / "somefile.txt"
    target.write_text("content")

    def raising_stat(self, *args, **kwargs):
        raise OSError("simulated stat failure")

    # path.exists() must still succeed so we reach the try/except around
    # path.stat() further down.
    monkeypatch.setattr(Path, "stat", raising_stat)

    assert get_utc_mtime(target) is None



# ── linbo_timestamp_to_epoch ────────────────────────────────────────
# LINBO clients write their local wall clock, which matches the server's
# local time, so the conversion depends on the server timezone: every test
# below pins TZ instead of relying on the machine running pytest.


@pytest.fixture
def tz(monkeypatch):
    def _set(name):
        monkeypatch.setenv('TZ', name)
        time.tzset()
    yield _set
    time.tzset()  # monkeypatch restored TZ, reload it


def test_linbo_timestamp_is_read_as_server_local_time(tz):
    tz('Europe/Berlin')

    epoch = linbo_timestamp_to_epoch('202608071440')

    # 14:40 CEST is 12:40 UTC.
    assert datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat() == '2026-08-07T12:40:00+00:00'


def test_linbo_timestamp_follows_dst(tz):
    tz('Europe/Berlin')

    epoch = linbo_timestamp_to_epoch('202603261226')

    # Same zone, but CET in March: one hour of offset, not two.
    assert datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat() == '2026-03-26T11:26:00+00:00'


def test_linbo_timestamp_is_identity_on_a_utc_server(tz):
    tz('UTC')

    epoch = linbo_timestamp_to_epoch('202608071440')

    assert datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat() == '2026-08-07T14:40:00+00:00'


def test_linbo_timestamp_rejects_a_malformed_value(tz):
    tz('UTC')

    with pytest.raises(ValueError):
        linbo_timestamp_to_epoch('not-a-timestamp')


def test_linbo_timestamp_restores_the_locale_after_a_malformed_value():
    import locale

    saved = locale.setlocale(locale.LC_ALL)
    try:
        with pytest.raises(ValueError):
            linbo_timestamp_to_epoch('209913451299')
        assert locale.setlocale(locale.LC_ALL) == saved
    finally:
        locale.setlocale(locale.LC_ALL, saved)
