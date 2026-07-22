import base64
import dataclasses

import ldb
import pytest

import linuxmusterTools.samba_util.samba_tool as st
from linuxmusterTools.samba_util.samba_tool import (
    DomainPasswordSettings,
    DomainPasswordSettingsManager,
    GPOManager,
    GroupManager,
    UserManager,
    DeviceManager,
    GPO,
    _days_to_ticks,
    _ticks_to_days,
    NEVER_TIMESTAMP,
)


# --- pure tick/day conversions ----------------------------------------------

def test_days_to_ticks_is_negative_and_scales_linearly():
    assert _days_to_ticks(0) == 0
    one_day = _days_to_ticks(1)
    assert one_day < 0
    assert _days_to_ticks(2) == 2 * one_day


def test_ticks_to_days_roundtrips_with_days_to_ticks():
    for days in (0, 1, 7, 42, 998):
        assert _ticks_to_days(_days_to_ticks(days)) == days


def test_ticks_to_days_never_timestamp_means_zero():
    assert _ticks_to_days(NEVER_TIMESTAMP) == 0


def test_ticks_to_days_accepts_string_ticks():
    # samdb.get_minPwdAge()/get_maxPwdAge() results get passed through
    # int(...) so callers can hand over strings too.
    assert _ticks_to_days(str(_days_to_ticks(10))) == 10


# --- DomainPasswordSettings dataclass ---------------------------------------

def test_domain_password_settings_is_frozen_and_slotted():
    settings = DomainPasswordSettings(min_pwd_length=8, complexity=True, min_pwd_age=1, max_pwd_age=42)

    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.min_pwd_length = 9

    assert not hasattr(settings, '__dict__')


# --- DomainPasswordSettingsManager.__init__ ---------------------------------

def test_manager_init_samdb_none_when_path_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(st, 'SAMDB_PATH', str(tmp_path / 'missing.ldb'))

    manager = DomainPasswordSettingsManager()

    assert manager.samdb is None


def test_manager_init_samdb_none_when_samdb_constructor_raises(tmp_path, monkeypatch):
    samdb_path = tmp_path / 'sam.ldb'
    samdb_path.write_text('not a real db')
    monkeypatch.setattr(st, 'SAMDB_PATH', str(samdb_path))
    monkeypatch.setattr(st, 'SamDB', lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))

    manager = DomainPasswordSettingsManager()

    assert manager.samdb is None


def test_manager_init_samdb_set_on_success(tmp_path, monkeypatch):
    samdb_path = tmp_path / 'sam.ldb'
    samdb_path.write_text('not a real db')
    sentinel = object()
    monkeypatch.setattr(st, 'SAMDB_PATH', str(samdb_path))
    monkeypatch.setattr(st, 'SamDB', lambda **kw: sentinel)

    manager = DomainPasswordSettingsManager()

    assert manager.samdb is sentinel


# --- DomainPasswordSettingsManager.get --------------------------------------

class FakeSamDB:
    def __init__(self, search_result, min_pwd_age_ticks, max_pwd_age_ticks, pwd_properties=0):
        self._search_result = search_result
        self._min_pwd_age_ticks = min_pwd_age_ticks
        self._max_pwd_age_ticks = max_pwd_age_ticks
        self._pwd_properties = pwd_properties
        self.modify_calls = []

    def get_default_basedn(self):
        return 'DC=example,DC=tld'

    def search(self, base_dn, scope=None, attrs=None):
        return [self._search_result]

    def get_minPwdAge(self):
        return self._min_pwd_age_ticks

    def get_maxPwdAge(self):
        return self._max_pwd_age_ticks

    def get_pwdProperties(self):
        return self._pwd_properties

    def modify(self, m):
        self.modify_calls.append(m)


def _manager_with_fake_samdb(fake_samdb):
    manager = DomainPasswordSettingsManager.__new__(DomainPasswordSettingsManager)
    manager.samdb = fake_samdb
    return manager


def test_get_raises_runtime_error_when_samdb_is_none():
    manager = _manager_with_fake_samdb(None)
    with pytest.raises(RuntimeError):
        manager.get()


def test_get_reads_length_complexity_and_ages():
    fake_samdb = FakeSamDB(
        search_result={'minPwdLength': [b'8'], 'pwdProperties': [b'1']},
        min_pwd_age_ticks=_days_to_ticks(1),
        max_pwd_age_ticks=_days_to_ticks(42),
        pwd_properties=1,
    )
    manager = _manager_with_fake_samdb(fake_samdb)

    settings = manager.get()

    assert settings == DomainPasswordSettings(
        min_pwd_length=8, complexity=True, min_pwd_age=1, max_pwd_age=42,
    )


def test_get_complexity_false_when_bit_unset():
    fake_samdb = FakeSamDB(
        search_result={'minPwdLength': [b'7'], 'pwdProperties': [b'0']},
        min_pwd_age_ticks=0,
        max_pwd_age_ticks=NEVER_TIMESTAMP,
    )
    manager = _manager_with_fake_samdb(fake_samdb)

    settings = manager.get()

    assert settings.complexity is False
    assert settings.max_pwd_age == 0


# --- DomainPasswordSettingsManager.set --------------------------------------

class FakeMessage(dict):
    def __init__(self):
        super().__init__()
        self.dn = None


class FakeMessageElement:
    def __init__(self, value, flag, name):
        self.value = value
        self.flag = flag
        self.name = name


@pytest.fixture(autouse=True)
def patch_ldb_helpers(monkeypatch):
    """
    DomainPasswordSettingsManager.set() unconditionally builds an ldb.Dn from
    self.samdb before any validation runs; ldb.Dn's C constructor requires a
    real ldb.Ldb connection, which FakeSamDB is not. Replace Message/Dn/
    MessageElement with plain-Python stand-ins so `set()`'s own logic can be
    exercised without a real samba AD connection.
    """
    monkeypatch.setattr(st, 'Message', FakeMessage)
    monkeypatch.setattr(st, 'Dn', lambda samdb, dn_string: dn_string)
    monkeypatch.setattr(st, 'MessageElement', FakeMessageElement)


def _manager_for_set():
    fake_samdb = FakeSamDB(
        search_result={'minPwdLength': [b'7'], 'pwdProperties': [b'0']},
        min_pwd_age_ticks=_days_to_ticks(1),
        max_pwd_age_ticks=_days_to_ticks(42),
        pwd_properties=0,
    )
    return _manager_with_fake_samdb(fake_samdb), fake_samdb


@pytest.mark.parametrize('kwargs, match', [
    ({'min_pwd_length': -1}, 'min_pwd_length'),
    ({'min_pwd_length': 15}, 'min_pwd_length'),
    ({'min_pwd_age': -1}, 'min_pwd_age'),
    ({'min_pwd_age': 999}, 'min_pwd_age'),
    ({'max_pwd_age': -1}, 'max_pwd_age'),
    ({'max_pwd_age': 1000}, 'max_pwd_age'),
])
def test_set_validates_ranges(kwargs, match):
    manager, _ = _manager_for_set()
    with pytest.raises(ValueError, match=match):
        manager.set(**kwargs)


def test_set_requires_at_least_one_argument():
    manager, _ = _manager_for_set()
    with pytest.raises(ValueError, match='At least one setting'):
        manager.set()


def test_set_rejects_min_age_greater_or_equal_to_max_age():
    manager, _ = _manager_for_set()
    with pytest.raises(ValueError, match='max_pwd_age'):
        manager.set(min_pwd_age=10, max_pwd_age=10)


def test_set_allows_max_pwd_age_zero_meaning_never_expires():
    manager, fake_samdb = _manager_for_set()
    manager.set(min_pwd_age=10, max_pwd_age=0)
    assert len(fake_samdb.modify_calls) == 1


def test_set_writes_only_the_given_fields():
    manager, fake_samdb = _manager_for_set()

    manager.set(min_pwd_length=10)

    m = fake_samdb.modify_calls[0]
    assert list(m.keys()) == ['minPwdLength']
    assert m['minPwdLength'].value == '10'


def test_set_complexity_toggles_bit_using_current_properties():
    manager, fake_samdb = _manager_for_set()
    fake_samdb._pwd_properties = 0

    manager.set(complexity=True)

    m = fake_samdb.modify_calls[0]
    assert m['pwdProperties'].value == str(st.DOMAIN_PASSWORD_COMPLEX)


# --- GPOManager --------------------------------------------------------------

class FakeGpoEntry(dict):
    def __init__(self, dn, **kw):
        super().__init__(**kw)
        self.dn = dn


def test_gpo_manager_no_samdb_path_yields_no_gpos(tmp_path, monkeypatch):
    monkeypatch.setattr(st, 'SAMDB_PATH', str(tmp_path / 'missing.ldb'))

    manager = GPOManager()

    assert manager.gpos == {}


def test_gpo_manager_parses_gpo_info_into_drivemanager(tmp_path, monkeypatch):
    samdb_path = tmp_path / 'sam.ldb'
    samdb_path.write_text('not a real db')
    monkeypatch.setattr(st, 'SAMDB_PATH', str(samdb_path))
    monkeypatch.setattr(st, 'SamDB', lambda **kw: object())

    gpo_entry = FakeGpoEntry(
        dn='CN={GUID},CN=Policies,CN=System,DC=example,DC=tld',
        name=[b'{GUID}'],
        displayName=[b'Default Domain Policy'],
        gPCFileSysPath=[b'\\\\example.tld\\SysVol\\example.tld\\Policies\\{GUID}'],
    )
    monkeypatch.setattr(st, 'get_gpo_info', lambda samdb, x: [gpo_entry])

    manager = GPOManager()

    assert list(manager.gpos.keys()) == ['Default Domain Policy']
    gpo = manager.gpos['Default Domain Policy']
    assert isinstance(gpo, GPO)
    assert gpo.gpo == '{GUID}'
    assert gpo.unix_path == '/var/lib/samba/SysVol/example.tld/Policies/{GUID}'
    assert gpo.drivemgr.drives == []  # Drives.xml doesn't exist under tmp_path


def test_gpo_manager_skips_gpo_when_drivemanager_construction_fails(tmp_path, monkeypatch):
    samdb_path = tmp_path / 'sam.ldb'
    samdb_path.write_text('not a real db')
    monkeypatch.setattr(st, 'SAMDB_PATH', str(samdb_path))
    monkeypatch.setattr(st, 'SamDB', lambda **kw: object())

    gpo_entry = FakeGpoEntry(
        dn='CN={GUID},CN=Policies,CN=System,DC=example,DC=tld',
        name=[b'{GUID}'],
        displayName=[b'Broken Policy'],
        gPCFileSysPath=[b'\\\\example.tld\\SysVol\\example.tld\\Policies\\{GUID}'],
    )
    monkeypatch.setattr(st, 'get_gpo_info', lambda samdb, x: [gpo_entry])
    monkeypatch.setattr(st, 'DriveManager', lambda path: (_ for _ in ()).throw(Exception("bad policy path")))

    manager = GPOManager()

    assert manager.gpos == {}


# --- GroupManager --------------------------------------------------------

def test_group_manager_init_without_samdb_path(tmp_path, monkeypatch):
    monkeypatch.setattr(st, 'SAMDB_PATH', str(tmp_path / 'missing.ldb'))

    manager = GroupManager()

    assert not hasattr(manager, 'samdb')


def _group_manager(tmp_path, monkeypatch, samdb=None):
    samdb_path = tmp_path / 'sam.ldb'
    samdb_path.write_text('not a real db')
    monkeypatch.setattr(st, 'SAMDB_PATH', str(samdb_path))
    monkeypatch.setattr(st, 'SamDB', lambda **kw: samdb if samdb is not None else object())
    # Never touch the real hook directory or spawn real scripts.
    monkeypatch.setattr(st.os, 'listdir', lambda path: [])
    return GroupManager()


def test_group_manager_list_groups_by_sophomorix_type(tmp_path, monkeypatch):
    manager = _group_manager(tmp_path, monkeypatch)
    monkeypatch.setattr(
        st, 'lr',
        type('FakeLr', (), {'get': staticmethod(lambda path, attributes=None, school=None: [
            {'cn': 'teachers', 'sophomorixType': 'teachers'},
            {'cn': '9a', 'sophomorixType': 'schoolclasses'},
            {'cn': '9b', 'sophomorixType': 'schoolclasses'},
        ])})(),
    )

    groups = manager.list()

    assert groups == {
        'teachers': ['teachers'],
        'schoolclasses': ['9a', '9b'],
    }


def test_group_manager_remove_members_calls_samdb_and_post_hook(tmp_path, monkeypatch):
    calls = []
    fake_samdb = type('FakeSamDB', (), {
        'add_remove_group_members': lambda self, group, members, add_members_operation: calls.append(
            (group, members, add_members_operation)
        ),
    })()
    manager = _group_manager(tmp_path, monkeypatch, samdb=fake_samdb)

    manager.remove_members('9a', ['jdupont'])

    assert calls == [('9a', ['jdupont'], False)]


def test_group_manager_add_members_swallows_duplicate_member_error(tmp_path, monkeypatch):
    calls = []

    def fake_add(self, group, members, add_members_operation):
        calls.append(members)
        raise Exception("Attribute member already exists for target GUID ... (68, ...)")

    fake_samdb = type('FakeSamDB', (), {'add_remove_group_members': fake_add})()
    manager = _group_manager(tmp_path, monkeypatch, samdb=fake_samdb)

    # Must not raise: error code 68 (already a member) is expected/benign.
    manager.add_members('9a', ['jdupont'])

    assert calls == [['jdupont']]


def test_group_manager_add_members_swallows_unrelated_errors_too():
    """
    Known bug: the except clause in GroupManager.add_members() only *checks*
    for the LDAP "already exists" code 68 inside `if "(68," in str(e): pass`
    but has no `else: raise`, so ANY exception raised by
    add_remove_group_members (not just the intended idempotent-add case) is
    silently swallowed. This documents the current (buggy) behavior rather
    than the presumably-intended one.
    """
    manager = GroupManager.__new__(GroupManager)
    manager.school_prefix = ''
    manager.POST_HOOK_DIR = '/nonexistent'

    def fake_add(group, members, add_members_operation):
        raise Exception("totally unrelated failure, not an LDAP code 68")

    manager.samdb = type('FakeSamDB', (), {'add_remove_group_members': staticmethod(fake_add)})()
    manager._run_post_hook = lambda action, group, members: None

    # Does not raise, even though the failure has nothing to do with the
    # "member already exists" case the `if` was meant to special-case.
    manager.add_members('9a', ['jdupont'])


# --- UserManager -------------------------------------------------------------

def test_user_manager_init_without_samdb_path(tmp_path, monkeypatch):
    monkeypatch.setattr(st, 'SAMDB_PATH', str(tmp_path / 'missing.ldb'))
    manager = UserManager()
    assert not hasattr(manager, 'samdb')


@pytest.mark.parametrize('password, expected_weak', [
    ('short1A', False),   # 7 chars, upper+lower+digit -> considered strong
    ('alllower1', True),  # no uppercase
    ('ALLUPPER1', True),  # no lowercase
    ('Ab', True),         # too short
])
def test_check_password_strength(password, expected_weak):
    manager = UserManager.__new__(UserManager)
    assert manager._check_password_strength(password) is expected_weak


def test_generate_password_is_actually_always_weak():
    """
    Known bug: `_check_password_strength()` returns True when the password
    is WEAK (`re.match(...) is None`), yet `_generate_password()`'s loop is
    `while not password_check: ... password_check =
    self._check_password_strength(password)`. That inverts the intended
    behavior: the loop keeps re-rolling as long as it draws a *strong*
    password (password_check False -> `not False` True -> loop again) and
    stops the instant it draws a *weak* one (password_check True -> `not
    True` False -> exit), returning that weak password. Empirically this is
    the deterministic outcome, not a rare corner case (reproduced 200/200
    times locally) -- so `_generate_password()` reliably violates its own
    documented complexity contract.
    """
    manager = UserManager.__new__(UserManager)
    for _ in range(20):
        password = manager._generate_password()
        assert len(password) == 8
        assert manager._check_password_strength(password) is True


def test_set_password_success():
    calls = []
    manager = UserManager.__new__(UserManager)
    manager.samdb = type('FakeSamDB', (), {
        'setpassword': lambda self, dn, password: calls.append((dn, password)),
    })()

    manager.set_password('jdupont', 'S3curePass!')

    assert calls == [('samaccountname=jdupont', 'S3curePass!')]


def test_set_password_wraps_ldb_error():
    manager = UserManager.__new__(UserManager)

    def raise_ldb_error(self, dn, password):
        raise ldb.LdbError(1, "Password does not meet complexity requirements")

    manager.samdb = type('FakeSamDB', (), {'setpassword': raise_ldb_error})()

    with pytest.raises(Exception, match="complexity requirements"):
        manager.set_password('jdupont', 'weak')


# --- DeviceManager -------------------------------------------------------

def test_device_manager_init_without_samdb_path(tmp_path, monkeypatch):
    monkeypatch.setattr(st, 'SAMDB_PATH', str(tmp_path / 'missing.ldb'))
    manager = DeviceManager()
    assert manager.samdb is None


def test_get_credentials_raises_runtime_error_without_samdb():
    manager = DeviceManager.__new__(DeviceManager)
    manager.samdb = None

    with pytest.raises(RuntimeError, match="Cannot read device credentials"):
        manager.get_credentials('pc01')


def test_get_credentials_returns_encoded_hashes(monkeypatch):
    manager = DeviceManager.__new__(DeviceManager)
    raw = {
        'unicodePwd': [b'\x00\x01'],
        'supplementalCredentials': [b'\x02\x03'],
    }
    manager.samdb = type('FakeSamDB', (), {'search': lambda self, *a, **kw: [raw]})()

    result = manager.get_credentials('pc01')

    import base64
    assert result == {
        'unicodePwd': base64.b64encode(b'\x00\x01').decode(),
        'supplementalCredentials': base64.b64encode(b'\x02\x03').decode(),
    }


def test_get_credentials_returns_empty_dict_when_device_not_found():
    manager = DeviceManager.__new__(DeviceManager)
    manager.samdb = type('FakeSamDB', (), {'search': lambda self, *a, **kw: []})()

    assert manager.get_credentials('pc01') == {}


def test_set_credentials_rejects_invalid_base64_hash():
    manager = DeviceManager.__new__(DeviceManager)

    with pytest.raises(Exception, match="not a valid hash"):
        manager.set_credentials('pc01', 'not base64!!', 'AAAA==')


def test_set_credentials_raises_when_device_not_found(monkeypatch):
    manager = DeviceManager.__new__(DeviceManager)
    monkeypatch.setattr(st, 'lr', type('FakeLr', (), {'getval': staticmethod(lambda path, attr, school=None: None)})())

    with pytest.raises(Exception, match="not found in ldap"):
        manager.set_credentials('pc01', 'AAAA==', 'BBBB==')


def test_set_credentials_calls_modify_ldif_with_expected_content(monkeypatch):
    calls = []
    manager = DeviceManager.__new__(DeviceManager)
    manager.samdb = type('FakeSamDB', (), {
        'modify_ldif': lambda self, ldif, controls=None: calls.append((ldif, controls)),
    })()
    monkeypatch.setattr(
        st, 'lr',
        type('FakeLr', (), {'getval': staticmethod(
            lambda path, attr, school=None: 'CN=pc01,OU=default-school,DC=example,DC=tld'
        )})(),
    )

    unicode_pwd = base64.b64encode(b'unicode-pwd-bytes').decode()
    supplemental = base64.b64encode(b'supplemental-bytes').decode()

    manager.set_credentials('pc01', unicode_pwd, supplemental)

    assert len(calls) == 1
    ldif, controls = calls[0]
    assert 'dn: CN=pc01,OU=default-school,DC=example,DC=tld' in ldif
    assert f'unicodePwd:: {unicode_pwd}' in ldif
    assert f'supplementalCredentials:: {supplemental}' in ldif
    assert controls == ['relax:0', 'local_oid:1.3.6.1.4.1.7165.4.3.7:0', 'local_oid:1.3.6.1.4.1.7165.4.3.12:0']
