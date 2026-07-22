"""
Tests for attic.py: get_killdate, get_attic_status, check_attic_dir.

All external dependencies (LDAP reader, SchoolConfig, SMB client, and the
hardcoded sophomorix kill-log path) are monkeypatched so no real system
path or network resource is touched.
"""

import builtins

import pytest

import linuxmusterTools.common.attic as attic


KILL_LOG_PATH = "/var/log/sophomorix/userlog/user-kill.log"


class FakeSchoolConfig:
    """Stand-in for lmnconfig.SchoolConfig used by get_attic_status."""

    last_school = None

    def __init__(self, school='default-school', config=None):
        FakeSchoolConfig.last_school = school
        self.config = config if config is not None else {}


def _patch_kill_log(monkeypatch, tmp_path, content):
    """
    Redirect the hardcoded kill-log path to a temp file with `content`,
    leaving every other open() call untouched.
    """

    log_file = tmp_path / "user-kill.log"
    log_file.write_text(content)
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == KILL_LOG_PATH:
            return real_open(log_file, *args, **kwargs)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    return log_file


def _patch_missing_kill_log(monkeypatch):
    """Simulate the kill-log path not existing at all."""

    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == KILL_LOG_PATH:
            raise FileNotFoundError(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)


# --- get_killdate ---------------------------------------------------------

def test_get_killdate_finds_matching_user(monkeypatch, tmp_path):
    content = (
        "x::y::20081030125303.0Z::myschool::someoneelse::rest\n"
        "x::y::20200101000000.0Z::myschool::jdupont::rest\n"
    )
    _patch_kill_log(monkeypatch, tmp_path, content)

    killdate, school = attic.get_killdate("jdupont")

    assert killdate == "01 Jan 2020 00:00:00"
    assert school == "myschool"


def test_get_killdate_scans_from_the_end_of_the_file(monkeypatch, tmp_path):
    # Two lines match; reversed(list(...)) means the *last* matching line
    # in the file is returned first.
    content = (
        "x::y::20080101000000.0Z::schoolA::jdupont::rest\n"
        "x::y::20200101000000.0Z::schoolB::jdupont::rest\n"
    )
    _patch_kill_log(monkeypatch, tmp_path, content)

    killdate, school = attic.get_killdate("jdupont")

    assert killdate == "01 Jan 2020 00:00:00"
    assert school == "schoolB"


def test_get_killdate_no_matching_line_returns_none(monkeypatch, tmp_path):
    content = "x::y::20081030125303.0Z::myschool::someoneelse::rest\n"
    _patch_kill_log(monkeypatch, tmp_path, content)

    assert attic.get_killdate("jdupont") == (None, None)


def test_get_killdate_missing_log_file_returns_none(monkeypatch):
    _patch_missing_kill_log(monkeypatch)

    assert attic.get_killdate("jdupont") == (None, None)


# --- get_attic_status ------------------------------------------------------

def test_get_attic_status_no_ldap_details_but_found_in_kill_log(monkeypatch):
    monkeypatch.setattr(attic.lr, "get", lambda path: None)
    monkeypatch.setattr(attic, "get_killdate", lambda user: ("01 Jan 2020 00:00:00", "myschool"))

    result = attic.get_attic_status("jdupont")

    assert result == {
        'status': 'killed',
        'start': '01 Jan 2020 00:00:00',
        'end': '01 Jan 2020 00:00:00',
        'school': 'myschool',
    }


def test_get_attic_status_no_ldap_details_and_not_in_kill_log(monkeypatch):
    monkeypatch.setattr(attic.lr, "get", lambda path: None)
    monkeypatch.setattr(attic, "get_killdate", lambda user: (None, None))

    result = attic.get_attic_status("jdupont")

    assert result == {
        'status': 'No information found.',
        'start': '',
        'end': '',
        'school': 'Unknown',
    }


def test_get_attic_status_user_not_in_attic(monkeypatch):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'not-attic',
        'school': 'myschool',
    })

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'Activated'
    # School is only populated once we're in the "attic" branch.
    assert result['school'] == 'Unknown'


@pytest.mark.parametrize("status", ["M", "T"])
def test_get_attic_status_tolerated_with_toleration_time(monkeypatch, status):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'attic',
        'sophomorixAdminFile': 'somefile',
        'school': 'myschool',
        'sophomorixStatus': status,
        'sophomorixTolerationDate': '20200101000000.0Z',
    })
    monkeypatch.setattr(attic, "SchoolConfig", lambda school: FakeSchoolConfig(
        school, config={'userfile.somefile': {'TOLERATION_TIME': '10'}}
    ))

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'tolerated'
    assert result['school'] == 'myschool'
    assert result['start'] == '01 Jan 2020 00:00:00'
    assert result['end'] == '11 Jan 2020 00:00:00'


def test_get_attic_status_tolerated_missing_toleration_time(monkeypatch):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'attic',
        'sophomorixAdminFile': 'somefile',
        'school': 'myschool',
        'sophomorixStatus': 'M',
        'sophomorixTolerationDate': '20200101000000.0Z',
    })
    monkeypatch.setattr(attic, "SchoolConfig", lambda school: FakeSchoolConfig(school, config={}))

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'tolerated'
    assert result['end'] == 'not found'


@pytest.mark.parametrize("status", ["D", "L"])
def test_get_attic_status_deactivated_with_deactivation_time(monkeypatch, status):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'attic',
        'sophomorixAdminFile': 'somefile',
        'school': 'myschool',
        'sophomorixStatus': status,
        'sophomorixDeactivationDate': '20200101000000.0Z',
    })
    monkeypatch.setattr(attic, "SchoolConfig", lambda school: FakeSchoolConfig(
        school, config={'userfile.somefile': {'DEACTIVATION_TIME': '5'}}
    ))

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'deactivated'
    assert result['start'] == '01 Jan 2020 00:00:00'
    assert result['end'] == '06 Jan 2020 00:00:00'


def test_get_attic_status_deactivated_missing_deactivation_time(monkeypatch):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'attic',
        'sophomorixAdminFile': 'somefile',
        'school': 'myschool',
        'sophomorixStatus': 'D',
        'sophomorixDeactivationDate': '20200101000000.0Z',
    })
    monkeypatch.setattr(attic, "SchoolConfig", lambda school: FakeSchoolConfig(school, config={}))

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'deactivated'
    assert result['end'] == 'not found'


@pytest.mark.parametrize("status", ["R", "K"])
def test_get_attic_status_killable_uses_deactivation_time_for_start_and_end(monkeypatch, status):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'attic',
        'sophomorixAdminFile': 'somefile',
        'school': 'myschool',
        'sophomorixStatus': status,
        'sophomorixDeactivationDate': '20200101000000.0Z',
    })
    monkeypatch.setattr(attic, "SchoolConfig", lambda school: FakeSchoolConfig(
        school, config={'userfile.somefile': {'DEACTIVATION_TIME': '30'}}
    ))

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'killable'
    # Both start and end are computed the same way (start + DEACTIVATION_TIME).
    assert result['start'] == '31 Jan 2020 00:00:00'
    assert result['end'] == '31 Jan 2020 00:00:00'


def test_get_attic_status_killable_missing_deactivation_time(monkeypatch):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'attic',
        'sophomorixAdminFile': 'somefile',
        'school': 'myschool',
        'sophomorixStatus': 'K',
        'sophomorixDeactivationDate': '20200101000000.0Z',
    })
    monkeypatch.setattr(attic, "SchoolConfig", lambda school: FakeSchoolConfig(school, config={}))

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'killable'
    assert result['start'] == 'not found'
    assert result['end'] == 'not found'


def test_get_attic_status_unknown_status_leaves_default_status(monkeypatch):
    monkeypatch.setattr(attic.lr, "get", lambda path: {
        'sophomorixAdminClass': 'attic',
        'sophomorixAdminFile': 'somefile',
        'school': 'myschool',
        'sophomorixStatus': 'Z',
    })
    monkeypatch.setattr(attic, "SchoolConfig", lambda school: FakeSchoolConfig(school, config={}))

    result = attic.get_attic_status("jdupont")

    assert result['status'] == 'No information found.'
    assert result['school'] == 'myschool'


# --- check_attic_dir ---------------------------------------------------------

class FakeSMBClient:
    """Stand-in for LMNSMBClient used by check_attic_dir."""

    def __init__(self, *, listing):
        self.listing = listing
        self.current_school = None

    def switch(self, school):
        self.current_school = school

    def list(self, path):
        return self.listing


def test_check_attic_dir_single_school_filters_dot_entries(monkeypatch):
    fake_client = FakeSMBClient(listing=[
        {'name': '.'},
        {'name': '..'},
        {'name': 'jdupont'},
    ])
    monkeypatch.setattr(attic, "LMNSMBClient", lambda: fake_client)
    monkeypatch.setattr(attic, "get_attic_status", lambda user: {'status': 'killable', 'user': user})

    result = attic.check_attic_dir(school='myschool')

    assert fake_client.current_school == 'myschool'
    assert result == {'jdupont': {'status': 'killable', 'user': 'jdupont'}}


def test_check_attic_dir_no_school_checks_all_schools(monkeypatch):
    fake_client = FakeSMBClient(listing=[{'name': 'jdupont'}])
    monkeypatch.setattr(attic, "LMNSMBClient", lambda: fake_client)
    monkeypatch.setattr(attic.lr, "getval", lambda path, attr: ['schoolA', 'schoolB'])

    visited_schools = []
    original_switch = fake_client.switch

    def tracking_switch(school):
        visited_schools.append(school)
        original_switch(school)

    fake_client.switch = tracking_switch
    monkeypatch.setattr(attic, "get_attic_status", lambda user: {'status': 'killable', 'user': user})

    result = attic.check_attic_dir(school=None)

    assert visited_schools == ['schoolA', 'schoolB']
    # Both schools have the same single user 'jdupont' in this fake listing,
    # so the second school's result simply overwrites the first's, keyed by
    # username only (check_attic_dir does not namespace by school).
    assert result == {'jdupont': {'status': 'killable', 'user': 'jdupont'}}
