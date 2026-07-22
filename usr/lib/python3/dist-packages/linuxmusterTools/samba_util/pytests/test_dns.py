import pytest

import linuxmusterTools.samba_util.dns as dns_module
from linuxmusterTools.samba_util.dns import SambaToolDNS


SETUP_INI_PATH = '/var/lib/linuxmuster/setup.ini'
DEVICES_CSV_PATH = '/etc/linuxmuster/sophomorix/default-school/devices.csv'


class FakeLMNFile:
    """
    Stand-in for LMNFile, keyed by the exact path SambaToolDNS hardcodes
    ('/var/lib/linuxmuster/setup.ini' and the default-school devices.csv).
    Both are real absolute paths on a live system, so rather than relying
    on the ALLOWED_PATHS/ tmp_path redirection trick (which can't work here
    since the paths are literals baked into the method bodies, not
    overridable module constants), LMNFile itself is swapped out.

    entries: {path: data_or_exception}
       - dict/list  -> used as-is for `.data`
       - Exception instance -> raised from __init__ (e.g. FileNotFoundError)
    """

    entries = {}

    def __init__(self, path, mode):
        self.path = path
        if path not in FakeLMNFile.entries:
            raise FileNotFoundError(path)
        entry = FakeLMNFile.entries[path]
        if isinstance(entry, Exception):
            raise entry
        self.data = entry

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class FakeChild:
    """Stand-in for a pexpect.spawn() child process."""

    def __init__(self, output=b''):
        self.output = output
        self.sent = None
        self.expected = None

    def expect(self, pattern):
        self.expected = pattern

    def sendline(self, line):
        self.sent = line

    def read(self):
        return self.output


class FakeSpawn:
    """Records the exact command line pexpect.spawn() was called with."""

    def __init__(self, output=b''):
        self.output = output
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(cmd)
        return FakeChild(self.output)


@pytest.fixture(autouse=True)
def patch_lmnfile(monkeypatch):
    FakeLMNFile.entries = {}
    monkeypatch.setattr(dns_module, 'LMNFile', FakeLMNFile)


def _register_setup(domainname='example.tld'):
    FakeLMNFile.entries[SETUP_INI_PATH] = {'setup': {'domainname': domainname}}


def _register_devices(rows):
    FakeLMNFile.entries[DEVICES_CSV_PATH] = rows


# --- _get_zone ---------------------------------------------------------

def test_get_zone_reads_domainname_from_setup_ini():
    _register_setup(domainname='school.example.tld')
    _register_devices([])

    instance = SambaToolDNS()

    assert instance.zone == 'school.example.tld'


def test_get_zone_defaults_to_empty_when_key_missing():
    FakeLMNFile.entries[SETUP_INI_PATH] = {'setup': {}}

    instance = SambaToolDNS()

    assert instance.zone == ''


def test_get_zone_defaults_to_empty_when_file_missing():
    # No entry registered at all -> FakeLMNFile raises FileNotFoundError
    instance = SambaToolDNS()

    assert instance.zone == ''


def test_init_skips_ignore_list_when_zone_is_empty():
    FakeLMNFile.entries[SETUP_INI_PATH] = {'setup': {}}
    # Deliberately do not register the devices.csv path: if
    # _get_ignore_list() ran anyway it would blow up with FileNotFoundError.
    instance = SambaToolDNS()

    assert instance.zone == ''
    assert not hasattr(instance, 'lmn_hosts')


# --- _get_ignore_list ----------------------------------------------------

def test_ignore_list_lowercases_and_skips_comment_rows():
    _register_setup()
    _register_devices([
        {'hostname': 'PC01'},
        {'hostname': None},  # comment/empty line in the csv
        {'hostname': 'pc02'},
    ])

    instance = SambaToolDNS()

    assert instance.lmn_hosts == ['pc01', 'pc02']


# --- _samba_tool_process --------------------------------------------------

def test_samba_tool_process_rejects_unknown_action():
    _register_setup()
    _register_devices([])
    instance = SambaToolDNS()

    # No file should be opened and no process spawned for an invalid action:
    # dns_module.open/pexpect.spawn are deliberately left unpatched here, so
    # this would blow up loudly if _samba_tool_process tried to use them.
    result = instance._samba_tool_process('nonsense', ())
    assert result is None


class _FakeSecretFile:
    def __init__(self, content):
        self._content = content

    def readline(self):
        return self._content

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_samba_tool_process_builds_command_reads_password_and_splits_output(monkeypatch):
    _register_setup(domainname='school.example.tld')
    _register_devices([])
    instance = SambaToolDNS()

    fake_spawn = FakeSpawn(output=b"line one\r\nline two")
    monkeypatch.setattr(dns_module.pexpect, 'spawn', fake_spawn)
    monkeypatch.setattr(
        dns_module, 'open',
        lambda *a, **kw: _FakeSecretFile('s3cr3t\n'),
        raising=False,
    )

    result = instance._samba_tool_process('query', ('@', 'ALL'))

    assert fake_spawn.calls == [
        "samba-tool dns query localhost school.example.tld @ ALL -U administrator"
    ]
    assert result == ["line one", "line two"]


# --- list/add/update/delete: verified against _samba_tool_process directly --

@pytest.fixture
def dns_instance():
    _register_setup(domainname='example.tld')
    _register_devices([{'hostname': 'ignoredhost'}])
    return SambaToolDNS()


def test_list_splits_root_and_sub_entries(dns_instance, monkeypatch):
    raw_output = [
        "Name=, Records=2, Children=0",
        "  SOA: ns1.example.tld. hostmaster.example.tld. 3 900 600 86400 3600 (flags=f0, serial=3, ttl=3600)",
        "  NS: ns1.example.tld. (flags=f0, serial=0, ttl=3600)",
        "Name=www,DC=example,DC=tld, Records=1, Children=0",
        "  A: 10.0.0.5 (flags=f0, serial=1, ttl=900)",
        "Name=ignoredhost,DC=example,DC=tld, Records=1, Children=0",
        "  A: 10.0.0.6 (flags=f0, serial=1, ttl=900)",
        "Name=mail,DC=example,DC=tld, Records=1, Children=0",
        "  MX: mail.example.tld. (10) (flags=f0, serial=1, ttl=3600)",
        "Name=txt,DC=example,DC=tld, Records=1, Children=0",
        "  TXT: hello ()",
    ]
    monkeypatch.setattr(dns_instance, '_samba_tool_process', lambda action, options: raw_output)

    entries = dns_instance.list()

    assert entries['root'] == [
        {'host': '', 'type': 'SOA', 'value': 'ns1.example.tld. hostmaster.example.tld. 3 900 600 86400 3600',
         'flags': 'f0', 'serial': '3', 'ttl': '3600'},
        {'host': '', 'type': 'NS', 'value': 'ns1.example.tld.', 'flags': 'f0', 'serial': '0', 'ttl': '3600'},
    ]
    # "ignoredhost" is in lmn_hosts, so its A record must not show up at all.
    assert entries['sub'] == [
        {'host': 'www', 'type': 'A', 'value': '10.0.0.5', 'flags': 'f0', 'serial': '1', 'ttl': '900'},
        {'host': 'mail', 'type': 'MX', 'value': 'mail.example.tld.',
         'flags': 'f0', 'serial': '1', 'ttl': '3600', 'priority': '10'},
        {'host': 'txt', 'type': 'TXT', 'value': 'hello'},
    ]


def test_add_appends_priority_for_mx(dns_instance, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dns_instance, '_samba_tool_process',
        lambda action, options: calls.append((action, options)) or ['ok'],
    )

    dns_instance.add({'host': 'mail', 'type': 'MX', 'value': 'mail.example.tld.', 'priority': '10'})

    assert calls == [('add', ('mail', 'MX', 'mail.example.tld.\\ 10'))]


def test_add_leaves_non_mx_value_untouched(dns_instance, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dns_instance, '_samba_tool_process',
        lambda action, options: calls.append((action, options)) or ['ok'],
    )

    dns_instance.add({'host': 'www', 'type': 'A', 'value': '10.0.0.5'})

    assert calls == [('add', ('www', 'A', '10.0.0.5'))]


def test_update_appends_priority_for_mx_on_both_old_and_new(dns_instance, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dns_instance, '_samba_tool_process',
        lambda action, options: calls.append((action, options)) or ['ok'],
    )

    old = {'host': 'mail', 'type': 'MX', 'value': 'old.example.tld.', 'priority': '5'}
    new = {'host': 'mail', 'type': 'MX', 'value': 'new.example.tld.', 'priority': '10'}
    dns_instance.update(old, new)

    assert calls == [('update', ('mail', 'MX', 'old.example.tld.\\ 5', 'new.example.tld.\\ 10'))]


def test_delete_passes_arguments_through(dns_instance, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dns_instance, '_samba_tool_process',
        lambda action, options: calls.append((action, options)) or ['ok'],
    )

    dns_instance.delete('www', 'A', '10.0.0.5')

    assert calls == [('delete', ('www', 'A', '10.0.0.5'))]
