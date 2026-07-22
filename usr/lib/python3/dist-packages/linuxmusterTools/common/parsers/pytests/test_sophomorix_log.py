"""
Tests for the sophomorix user-{kill,add,update} log parsers.

Log line shapes are inferred directly from the field indices the parsing
code accesses (entries[1], entries[3], ... split on '::'), since no sample
log fixtures ship in this repo.
"""

from datetime import datetime, timedelta

import pytest

from linuxmusterTools.common.parsers.sophomorix_log import (
    parse_kill_log,
    parse_add_log,
    parse_update_log,
)


NOW = int(datetime.now().timestamp())
THREE_DAYS_AGO = int((datetime.now() - timedelta(days=3)).timestamp())
TEN_DAYS_AGO = int((datetime.now() - timedelta(days=10)).timestamp())
OVER_A_YEAR_AGO = int((datetime.now() - timedelta(days=400)).timestamp())


def _kill_line(
    ts=NOW,
    school="default-school",
    user="jdupont",
    lastname="Dupont",
    firstname="Jean",
    adminclass="5a",
    role="student",
    first_password="Xa8!fjse",
    home_deleted=True,
):
    flag = "TRUE" if home_deleted else "FALSE"
    return f"utc-str::{ts}::junk::{school}::{user}::{lastname}::{firstname}::{adminclass}::{role}::{first_password}::{flag}"


def _add_line(
    ts=NOW,
    school="default-school",
    user="jdupont",
    lastname="Dupont",
    firstname="Jean",
    adminclass="5a",
    role="student",
    unid="---",
):
    return f"utc-str::{ts}::junk::{school}::{user}::{lastname}::{firstname}::{adminclass}::{role}::{unid}"


def _update_line(ts=NOW, school="default-school", user="jdupont", changes=""):
    return f"utc-str::{ts}::junk::{school}::junk::{user}::junk::{changes}"


# ---------------------------------------------------------------------------
# parse_kill_log
# ---------------------------------------------------------------------------

def test_parse_kill_log_basic_fields(log_paths):
    log_paths["kill"].write_text(_kill_line() + "\n")

    result = parse_kill_log(all=True)

    assert NOW in result
    entry = result[NOW][0]
    assert entry == {
        "school": "default-school",
        "user": "jdupont",
        "firstname": "Jean",
        "lastname": "Dupont",
        "adminclass": "5a",
        "role": "student",
        "first_password": "Xa8!fjse",
        "home_deleted": True,
    }


def test_parse_kill_log_home_deleted_false(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=NOW, home_deleted=False) + "\n")

    result = parse_kill_log(all=True)

    assert result[NOW][0]["home_deleted"] is False


def test_parse_kill_log_skips_blank_and_comment_lines(log_paths):
    content = "\n".join(["", "# a comment", "   ", _kill_line()])
    log_paths["kill"].write_text(content + "\n")

    result = parse_kill_log(all=True)

    assert len(result) == 1


def test_parse_kill_log_skips_malformed_line_missing_fields(log_paths, caplog):
    content = "\n".join(["utc::123::tooshort", _kill_line()])
    log_paths["kill"].write_text(content + "\n")

    with caplog.at_level("WARNING"):
        result = parse_kill_log(all=True)

    # Production quirk: result[timestamp] = [] is set *before* the
    # IndexError is raised while building the entry dict, so a malformed
    # line still leaves a stray empty-list entry under its own timestamp
    # instead of being fully skipped. See production bug note.
    assert result.get(123) == []
    assert len(result[NOW]) == 1
    assert "Malformed line in kill log" in caplog.text


def test_parse_kill_log_skips_malformed_line_non_integer_timestamp(log_paths):
    bad_line = "utc-str::not-an-int::junk::default-school::baduser::Bad::User::5a::student::Xa8!fjse::TRUE"
    log_paths["kill"].write_text(bad_line + "\n" + _kill_line() + "\n")

    result = parse_kill_log(all=True)

    assert len(result) == 1
    assert NOW in result


def test_parse_kill_log_default_filters_out_entries_older_than_a_year(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=OVER_A_YEAR_AGO) + "\n" + _kill_line(ts=NOW) + "\n")

    result = parse_kill_log()  # all=False by default

    assert OVER_A_YEAR_AGO not in result
    assert NOW in result


def test_parse_kill_log_all_flag_includes_old_entries(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=OVER_A_YEAR_AGO) + "\n")

    result = parse_kill_log(all=True)

    assert OVER_A_YEAR_AGO in result


def test_parse_kill_log_today_flag_filters_to_current_day_only(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=NOW) + "\n" + _kill_line(ts=TEN_DAYS_AGO) + "\n")

    result = parse_kill_log(today=True)

    assert NOW in result
    assert TEN_DAYS_AGO not in result


def test_parse_kill_log_lastweek_flag_filters_correctly(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=THREE_DAYS_AGO) + "\n" + _kill_line(ts=TEN_DAYS_AGO) + "\n")

    result = parse_kill_log(lastweek=True)

    assert THREE_DAYS_AGO in result
    assert TEN_DAYS_AGO not in result


@pytest.mark.parametrize(
    "kwargs",
    [
        {"all": True, "today": True},
        {"all": True, "lastweek": True},
        {"today": True, "lastweek": True},
    ],
)
def test_parse_kill_log_mutually_exclusive_flags_raise(log_paths, kwargs):
    log_paths["kill"].write_text(_kill_line() + "\n")

    with pytest.raises(Exception):
        parse_kill_log(**kwargs)


def test_parse_kill_log_missing_file_raises(log_paths):
    # log_paths["kill"] was never written -> file does not exist
    with pytest.raises(Exception):
        parse_kill_log(all=True)


def test_parse_kill_log_epoch_lookup(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=NOW) + "\n")

    result = parse_kill_log(all=True, epoch=NOW)

    assert isinstance(result, list)
    assert result[0]["user"] == "jdupont"


def test_parse_kill_log_epoch_lookup_as_string(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=NOW) + "\n")

    result = parse_kill_log(all=True, epoch=str(NOW))

    assert len(result) == 1


def test_parse_kill_log_epoch_lookup_unknown_returns_empty_list(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=NOW) + "\n")

    result = parse_kill_log(all=True, epoch=NOW + 999999)

    assert result == []


def test_parse_kill_log_epoch_invalid_raises(log_paths):
    log_paths["kill"].write_text(_kill_line(ts=NOW) + "\n")

    with pytest.raises(Exception):
        parse_kill_log(all=True, epoch="not-an-epoch")


def test_parse_kill_log_multiple_entries_same_timestamp_accumulate(log_paths):
    content = _kill_line(ts=NOW, user="user1") + "\n" + _kill_line(ts=NOW, user="user2") + "\n"
    log_paths["kill"].write_text(content)

    result = parse_kill_log(all=True)

    assert len(result[NOW]) == 2
    users = {entry["user"] for entry in result[NOW]}
    assert users == {"user1", "user2"}


def test_parse_kill_log_handles_non_ascii_names(log_paths):
    log_paths["kill"].write_text(
        _kill_line(ts=NOW, firstname="François", lastname="Élève") + "\n",
        encoding="utf-8",
    )

    result = parse_kill_log(all=True)

    assert result[NOW][0]["firstname"] == "François"
    assert result[NOW][0]["lastname"] == "Élève"


# ---------------------------------------------------------------------------
# parse_add_log
# ---------------------------------------------------------------------------

def test_parse_add_log_basic_fields(log_paths):
    log_paths["add"].write_text(_add_line(unid="U12345") + "\n")

    result = parse_add_log(all=True)

    entry = result[NOW][0]
    assert entry == {
        "school": "default-school",
        "user": "jdupont",
        "firstname": "Jean",
        "lastname": "Dupont",
        "adminclass": "5a",
        "role": "student",
        "unid": "U12345",
    }


def test_parse_add_log_unid_placeholder_becomes_none(log_paths):
    log_paths["add"].write_text(_add_line(unid="---") + "\n")

    result = parse_add_log(all=True)

    assert result[NOW][0]["unid"] is None


def test_parse_add_log_default_filters_old_entries(log_paths):
    log_paths["add"].write_text(_add_line(ts=OVER_A_YEAR_AGO) + "\n" + _add_line(ts=NOW) + "\n")

    result = parse_add_log()

    assert OVER_A_YEAR_AGO not in result
    assert NOW in result


def test_parse_add_log_mutually_exclusive_flags_raise(log_paths):
    log_paths["add"].write_text(_add_line() + "\n")

    with pytest.raises(Exception):
        parse_add_log(all=True, today=True)


def test_parse_add_log_missing_file_raises(log_paths):
    with pytest.raises(Exception):
        parse_add_log(all=True)


def test_parse_add_log_skips_malformed_line(log_paths, caplog):
    content = "\n".join(["utc::123::too::short", _add_line()])
    log_paths["add"].write_text(content + "\n")

    with caplog.at_level("WARNING"):
        result = parse_add_log(all=True)

    # Same stray-empty-list quirk as parse_kill_log (see other test note).
    assert result.get(123) == []
    assert len(result[NOW]) == 1
    assert "Malformed line in add log" in caplog.text


def test_parse_add_log_epoch_lookup(log_paths):
    log_paths["add"].write_text(_add_line(ts=NOW) + "\n")

    result = parse_add_log(all=True, epoch=NOW)

    assert result[0]["user"] == "jdupont"


# ---------------------------------------------------------------------------
# parse_update_log
# ---------------------------------------------------------------------------

def test_parse_update_log_group_and_role_change(log_paths):
    changes = '"GROUP:teachers->students","ROLE:teacher->student"'
    log_paths["update"].write_bytes((_update_line(changes=changes) + "\n").encode("utf-8"))

    result = parse_update_log(all=True)

    entry = result[NOW][0]
    assert entry["school"] == "default-school"
    assert entry["user"] == "jdupont"
    assert entry["changes"]["group"] == "teachers->students"
    assert entry["changes"]["role"] == "teacher->student"


def test_parse_update_log_attribute_changes(log_paths):
    changes = '"givenName=Jean","sn=Dupont"'
    log_paths["update"].write_bytes((_update_line(changes=changes) + "\n").encode("utf-8"))

    result = parse_update_log(all=True)

    entry = result[NOW][0]
    assert entry["changes"]["givenName"] == "Jean"
    assert entry["changes"]["sn"] == "Dupont"


def test_parse_update_log_masks_unicode_password_value(log_paths):
    changes = '"unicodePwd=SomeSecretBinaryLookingValue"'
    log_paths["update"].write_bytes((_update_line(changes=changes) + "\n").encode("utf-8"))

    result = parse_update_log(all=True)

    assert result[NOW][0]["changes"]["unicodePwd"] == "CHANGED-VALUE HIDDEN"


def test_parse_update_log_list_changes_false_returns_empty_changes_dict(log_paths):
    changes = '"givenName=Jean"'
    log_paths["update"].write_bytes((_update_line(changes=changes) + "\n").encode("utf-8"))

    result = parse_update_log(all=True, list_changes=False)

    assert result[NOW][0]["changes"] == {}


def test_parse_update_log_malformed_change_drops_entire_entry(log_paths, caplog):
    # "GROUP:a:b" has two colons -> split(':') yields 3 parts, cannot unpack
    # into key, move -> ValueError -> the whole line (not just this change)
    # is skipped.
    changes = '"GROUP:a:b"'
    log_paths["update"].write_bytes((_update_line(changes=changes) + "\n").encode("utf-8"))

    with caplog.at_level("WARNING"):
        result = parse_update_log(all=True)

    # Same stray-empty-list quirk: result[timestamp] = [] is set before the
    # unpacking ValueError is raised, so the timestamp key survives with an
    # empty list even though the whole line was meant to be dropped.
    assert result == {NOW: []}
    assert "Malformed line in update log" in caplog.text


def test_parse_update_log_skips_blank_and_comment_lines(log_paths):
    content = b"\n# a comment\n\n" + (_update_line(changes='"givenName=Jean"') + "\n").encode("utf-8")
    log_paths["update"].write_bytes(content)

    result = parse_update_log(all=True)

    assert len(result) == 1


def test_parse_update_log_default_filters_old_entries(log_paths):
    old_line = _update_line(ts=OVER_A_YEAR_AGO, changes='"givenName=Old"')
    new_line = _update_line(ts=NOW, changes='"givenName=New"')
    log_paths["update"].write_bytes((old_line + "\n" + new_line + "\n").encode("utf-8"))

    result = parse_update_log()

    assert OVER_A_YEAR_AGO not in result
    assert NOW in result


def test_parse_update_log_mutually_exclusive_flags_raise(log_paths):
    log_paths["update"].write_bytes((_update_line(changes='"givenName=Jean"') + "\n").encode("utf-8"))

    with pytest.raises(Exception):
        parse_update_log(all=True, lastweek=True)


def test_parse_update_log_missing_file_raises(log_paths):
    with pytest.raises(Exception):
        parse_update_log(all=True)


def test_parse_update_log_epoch_lookup(log_paths):
    log_paths["update"].write_bytes((_update_line(ts=NOW, changes='"givenName=Jean"') + "\n").encode("utf-8"))

    result = parse_update_log(all=True, epoch=NOW)

    assert result[0]["user"] == "jdupont"


def test_parse_update_log_epoch_invalid_raises(log_paths):
    log_paths["update"].write_bytes((_update_line(ts=NOW, changes='"givenName=Jean"') + "\n").encode("utf-8"))

    with pytest.raises(Exception):
        parse_update_log(all=True, epoch="nope")
