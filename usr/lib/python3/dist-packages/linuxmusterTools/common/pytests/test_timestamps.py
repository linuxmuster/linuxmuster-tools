"""
Tests for get_utc_mtime: converting a file's mtime to a UTC datetime.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from linuxmusterTools.common.timestamps import get_utc_mtime


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
