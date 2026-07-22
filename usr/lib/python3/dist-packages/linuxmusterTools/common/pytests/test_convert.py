"""
Tests for the pure conversion helpers: format_size, convert_sophomorix_time,
convert_sophomorix_status.
"""

import pytest

from linuxmusterTools.common.convert import (
    format_size,
    convert_sophomorix_time,
    convert_sophomorix_status,
)


# --- format_size -------------------------------------------------------

@pytest.mark.parametrize("num, suffix, expected", [
    (0, 'B', '0 B'),
    (0, 'o', '0 o'),
])
def test_format_size_zero_is_special_cased(num, suffix, expected):
    assert format_size(num, suffix=suffix) == expected


@pytest.mark.parametrize("num, expected", [
    (1, '1.00 B'),
    (500, '500.00 B'),
    (1023, '1023.00 B'),
    (1024, '1.00 KiB'),
    (1536, '1.50 KiB'),
    (1024 ** 2, '1.00 MiB'),
    (1024 ** 3, '1.00 GiB'),
    (1024 ** 4, '1.00 TiB'),
    (1024 ** 5, '1.00 PiB'),
    (1024 ** 6, '1.00 EiB'),
    (1024 ** 7, '1.00 ZiB'),
])
def test_format_size_base2_typical_and_boundary_values(num, expected):
    assert format_size(num) == expected


@pytest.mark.parametrize("num, expected", [
    (1, '1.00 B'),
    (1500, '1.50 KB'),
    (1000, '1.00 KB'),
    (1000 ** 2, '1.00 MB'),
])
def test_format_size_base10(num, expected):
    assert format_size(num, base=10) == expected


def test_format_size_scale_above_seven_falls_back_to_yotta():
    # 1024**8 bytes: scale (floor(log_1024(num))) is exactly 8, which is
    # beyond the last entry of the `units` table (index 7 == 'Zi'), so the
    # function falls back to a hardcoded 'Yi' suffix.
    assert format_size(1024 ** 8) == '1.00 YiB'


def test_format_size_custom_suffix_is_applied():
    assert format_size(2048, suffix='o') == '2.00 Kio'


def test_format_size_invalid_base_raises():
    with pytest.raises(Exception, match="Please use 2 or 10 as base"):
        format_size(100, base=16)


def test_format_size_negative_number_raises_value_error():
    # math.log() on a negative number raises ValueError ("expected a
    # positive input"); format_size does not guard against this.
    with pytest.raises(ValueError):
        format_size(-100)


# --- convert_sophomorix_time --------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ('20081030125303.0Z', '30 Oct 2008 12:53:03'),
    ('20240101000000.0Z', '01 Jan 2024 00:00:00'),
])
def test_convert_sophomorix_time_valid_input(raw, expected):
    assert convert_sophomorix_time(raw) == expected


@pytest.mark.parametrize("raw", [
    'not-a-date',
    '',
    '2008103012',
])
def test_convert_sophomorix_time_invalid_input_returns_as_is(raw):
    assert convert_sophomorix_time(raw) == raw


# --- convert_sophomorix_status -------------------------------------------

@pytest.mark.parametrize("code, expected", [
    ('A', 'Activated'),
    ('U', 'Usable'),
    ('P', 'Permanent'),
    ('E', 'Enabled'),
    ('S', 'Self-activated'),
    ('T', 'Tolerated'),
    ('L', 'Locked'),
    ('D', 'Deactivated'),
    ('F', 'Frozen'),
    ('R', 'Removable'),
    ('K', 'Killable'),
    ('X', 'Exam'),
    ('M', 'Managed'),
])
def test_convert_sophomorix_status_known_codes(code, expected):
    assert convert_sophomorix_status(code) == expected


@pytest.mark.parametrize("code", ['', 'Z', 'unknown', None])
def test_convert_sophomorix_status_unknown_code_returns_unknown(code):
    assert convert_sophomorix_status(code) == 'Unknown'
