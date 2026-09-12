"""
Tests for NameChecker: validates strings (usernames, hostnames, MACs, ...)
against the NAME_RULES regexes, plus the mac address normalizer.
"""

import pytest

from linuxmusterTools.common.checks.names import NameChecker, NAME_RULES


checker = NameChecker()


# ---------------------------------------------------------------------------
# Generic guards: type / empty / path traversal (apply to every name_type)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name_type", list(NAME_RULES))
def test_non_string_input_is_rejected(name_type):
    assert checker.check(name_type, 12345) is False
    assert checker.check(name_type, None) is False
    assert checker.check(name_type, ["a"]) is False


@pytest.mark.parametrize("name_type", list(NAME_RULES))
def test_empty_string_is_rejected(name_type):
    assert checker.check(name_type, "") is False


@pytest.mark.parametrize(
    "traversal_string",
    ["../etc/passwd", "a/b", "a\\b", "a\0b", "..", "foo..bar", "/etc"],
)
@pytest.mark.parametrize("name_type", list(NAME_RULES))
def test_path_traversal_characters_are_rejected_regardless_of_type(name_type, traversal_string):
    assert checker.check(name_type, traversal_string) is False


def test_unknown_name_type_returns_false():
    assert checker.check("does_not_exist", "abc") is False


@pytest.mark.parametrize("name_type", list(NAME_RULES))
def test_generated_check_methods_exist_and_match_check(name_type):
    method = getattr(checker, f"check_{name_type}_name")
    assert method("!!!totally-invalid-for-everything???") == checker.check(name_type, "!!!totally-invalid-for-everything???")


# ---------------------------------------------------------------------------
# password
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["abc123", "P@ssw0rd!", "a-b-c", "a{b}c", "a[b]c"])
def test_password_valid(value):
    assert checker.check_password_name(value) is True


@pytest.mark.parametrize("value", ["hello world", "abc;def", "abc'def", "abc\"def"])
def test_password_invalid(value):
    assert checker.check_password_name(value) is False


# ---------------------------------------------------------------------------
# strong_password
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["Abcdefg1", "Password1!", "Aa1234567"])
def test_strong_password_valid(value):
    assert checker.check_strong_password_name(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "abcdefg1",   # no uppercase
        "ABCDEFG1",   # no lowercase
        "Abcdefgh",   # no digit/special
        "Ab1",        # too short (< 7 chars)
    ],
)
def test_strong_password_invalid(value):
    assert checker.check_strong_password_name(value) is False


# ---------------------------------------------------------------------------
# project / group  (lowercase alnum, dash, underscore)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name_type", ["project", "group"])
@pytest.mark.parametrize("value", ["class10a", "my-project_1", "abc"])
def test_project_group_valid(name_type, value):
    assert checker.check(name_type, value) is True


@pytest.mark.parametrize("name_type", ["project", "group"])
@pytest.mark.parametrize("value", ["Class10A", "my project", "abc!"])
def test_project_group_invalid(name_type, value):
    assert checker.check(name_type, value) is False


# ---------------------------------------------------------------------------
# session / linbo_conf (case-insensitive)
# ---------------------------------------------------------------------------

def test_session_is_case_insensitive():
    assert checker.check_session_name("MySession-1") is True
    assert checker.check_session_name("my_session+1") is True


def test_session_rejects_dot():
    assert checker.check_session_name("my.session") is False


def test_linbo_conf_allows_dot_and_is_case_insensitive():
    assert checker.check_linbo_conf_name("Win10.rsync") is True


# ---------------------------------------------------------------------------
# linbo_image (requires at least one char)
# ---------------------------------------------------------------------------

def test_linbo_image_valid():
    assert checker.check_linbo_image_name("Win10_Prof.qcow2") is True


def test_linbo_image_empty_rejected():
    assert checker.check_linbo_image_name("") is False


# ---------------------------------------------------------------------------
# login (case-insensitive)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["jdupont", "j.dupont", "j-dupont_1", "JDupont"])
def test_login_valid(value):
    assert checker.check_login_name(value) is True


@pytest.mark.parametrize("value", ["j dupont", "jdupont!", "jdupont@x"])
def test_login_invalid(value):
    assert checker.check_login_name(value) is False


# ---------------------------------------------------------------------------
# comment -- NAME_RULES["comment"] has no trailing "$" anchor (see bug note
# in the final report): re.match only needs a match starting at position 0,
# and since the character class is quantified with "*", an *empty* match at
# position 0 always succeeds. That makes check_comment_name effectively
# always True for any non-empty, non-path-traversal string, regardless of
# its actual content. These tests document that real behaviour.
# ---------------------------------------------------------------------------

def test_comment_regular_content_accepted():
    assert checker.check_comment_name("Some comment 123") is True


def test_comment_bug_special_characters_are_not_actually_rejected():
    # Documents the missing "$" anchor: invalid characters after a
    # (possibly empty) valid prefix do not cause rejection.
    assert checker.check_comment_name("!!!not allowed at all???") is True
    assert checker.check_comment_name(";DROP TABLE users;") is True


# ---------------------------------------------------------------------------
# alphanum / number
# ---------------------------------------------------------------------------

def test_alphanum_valid_and_invalid():
    assert checker.check_alphanum_name("abc123") is True
    assert checker.check_alphanum_name("ABC123") is True
    assert checker.check_alphanum_name("abc-123") is False


def test_number_valid_and_invalid():
    assert checker.check_number_name("12345") is True
    assert checker.check_number_name("12a45") is False


# ---------------------------------------------------------------------------
# date  dd.mm.yyyy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["1.1.2000", "01.01.2000", "31.12.1999", "29.02.2024"])
def test_date_valid(value):
    assert checker.check_date_name(value) is True


@pytest.mark.parametrize("value", ["32.01.2000", "01.13.2000", "01.01.1899", "2000.01.01"])
def test_date_invalid(value):
    assert checker.check_date_name(value) is False


# ---------------------------------------------------------------------------
# ip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["192.168.1.1", "10.0.0.1", "255.255.255.255", "1.1.1.1"])
def test_ip_valid(value):
    assert checker.check_ip_name(value) is True


@pytest.mark.parametrize("value", ["256.1.1.1", "1.1.1.256", "1.1.1", "a.b.c.d", "0.0.0.0"])
def test_ip_invalid(value):
    assert checker.check_ip_name(value) is False


# ---------------------------------------------------------------------------
# mac1 / mac2 / mac3 + normalize_mac
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"])
def test_mac1_colon_format_valid(value):
    assert checker.check_mac1_name(value) is True


@pytest.mark.parametrize("value", ["AA-BB-CC-DD-EE-FF", "aa-bb-cc-dd-ee-ff"])
def test_mac2_hyphen_format_valid(value):
    assert checker.check_mac2_name(value) is True


@pytest.mark.parametrize("value", ["AABBCCDDEEFF", "aabbccddeeff"])
def test_mac3_no_separator_format_valid(value):
    assert checker.check_mac3_name(value) is True


@pytest.mark.parametrize(
    "value",
    ["AA:BB:CC:DD:EE", "AA:BB:CC:DD:EE:GG", "AABBCCDDEE", "AA-BB:CC-DD-EE-FF"],
)
def test_mac_invalid_across_all_formats(value):
    assert checker.check_mac1_name(value) is False
    assert checker.check_mac2_name(value) is False
    assert checker.check_mac3_name(value) is False


def test_normalize_mac_colon_format():
    assert checker.normalize_mac("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"


def test_normalize_mac_hyphen_format():
    assert checker.normalize_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"


def test_normalize_mac_no_separator_format():
    assert checker.normalize_mac("aabbccddeeff") == "AA:BB:CC:DD:EE:FF"


def test_normalize_mac_invalid_returns_none():
    assert checker.normalize_mac("not-a-mac") is None


# ---------------------------------------------------------------------------
# host / room  (requires at least one char)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name_type", ["host", "room"])
def test_host_room_valid(name_type):
    assert checker.check(name_type, "server-01") is True


@pytest.mark.parametrize("name_type", ["host", "room"])
def test_host_room_empty_rejected(name_type):
    assert checker.check(name_type, "") is False


@pytest.mark.parametrize("name_type", ["host", "room"])
def test_host_room_rejects_dot(name_type):
    assert checker.check(name_type, "server.01") is False


# ---------------------------------------------------------------------------
# domain
# ---------------------------------------------------------------------------

def test_domain_valid():
    assert checker.check_domain_name("linuxmuster.lan") is True


def test_domain_invalid():
    assert checker.check_domain_name("linuxmuster_lan!") is False


# ---------------------------------------------------------------------------
# validate(): same rules as check(), but raises instead of returning False
# ---------------------------------------------------------------------------

def test_validate_returns_the_name_unchanged():
    assert checker.validate("linbo_image", "ubuntu22.qcow2") == "ubuntu22.qcow2"
    assert checker.validate_linbo_image_name("win11.qcow2") == "win11.qcow2"


@pytest.mark.parametrize("name_type", list(NAME_RULES))
def test_validate_raises_on_path_traversal(name_type):
    for bad in ["..", "../..", "a/b", "a\\b"]:
        with pytest.raises(ValueError):
            checker.validate(name_type, bad)


@pytest.mark.parametrize("name_type", list(NAME_RULES))
def test_validate_raises_on_non_string_and_empty(name_type):
    for bad in [None, 12345, ["a"], ""]:
        with pytest.raises(ValueError):
            checker.validate(name_type, bad)


def test_validate_error_names_the_rule_and_the_value():
    with pytest.raises(ValueError, match=r"Invalid linbo_image name: '\.\.'"):
        checker.validate_linbo_image_name("..")


@pytest.mark.parametrize("name_type", list(NAME_RULES))
def test_every_rule_gets_a_validate_shortcut(name_type):
    assert hasattr(checker, f"validate_{name_type}_name")


def test_validate_agrees_with_check():
    for value in ["ubuntu.qcow2", "..", "", "a/b", "win11-diff.qdiff"]:
        if checker.check("linbo_image", value):
            assert checker.validate("linbo_image", value) == value
        else:
            with pytest.raises(ValueError):
                checker.validate("linbo_image", value)
