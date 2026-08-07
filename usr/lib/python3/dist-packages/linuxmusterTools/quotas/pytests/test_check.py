"""
Tests for linuxmusterTools.quotas.check.

The module under test talks to real SMB shares, real LDAP, and shells out to
`smbcquotas` in production. Here every external boundary is replaced by a
fake:

- `smbclient.scandir`/`smbclient.stat` -> synthetic in-memory directory tree
  (see `fake_smb_tree` in conftest.py).
- `LMNLdapReader` (imported as `lr`) -> a `types.SimpleNamespace` with fake
  `get`/`getval` callables.
- `subprocess.run` -> a fake that returns a canned `smbcquotas`-shaped
  completed-process object.
- The Samba constants (`SAMBA_WORKGROUP`, `SAMBA_DOMAIN`, `SAMBA_NETBIOS`,
  `DFS`, `SHARES_LIST`) -> deterministic values via the autouse
  `patch_samba_config` fixture in conftest.py.

No real subprocess, SMB connection, or LDAP query is ever executed.
"""

import io
import os
import time
import types

import pytest

from linuxmusterTools.common import format_size


# ---------------------------------------------------------------------------
# timestamp2date
# ---------------------------------------------------------------------------

def test_timestamp2date_format_shape(check):
    result = check.timestamp2date(1_700_000_000)
    assert isinstance(result, str)
    # YYYY-MM-DDTHH:MM:SS
    parts = result.split('T')
    assert len(parts) == 2
    date_part, time_part = parts
    assert len(date_part.split('-')) == 3
    assert len(time_part.split(':')) == 3


def test_timestamp2date_relative_delta_is_preserved(check):
    from datetime import datetime, timedelta

    t1 = 1_700_000_000
    delta_seconds = 3661  # 1h 1m 1s
    t2 = t1 + delta_seconds

    d1 = datetime.strptime(check.timestamp2date(t1), "%Y-%m-%dT%H:%M:%S")
    d2 = datetime.strptime(check.timestamp2date(t2), "%Y-%m-%dT%H:%M:%S")

    assert d2 - d1 == timedelta(seconds=delta_seconds)


def test_timestamp2date_known_value_utc(check):
    """Pin TZ=UTC to get a fully deterministic, timezone-independent assertion."""
    original_tz = os.environ.get('TZ')
    os.environ['TZ'] = 'UTC'
    time.tzset()
    try:
        assert check.timestamp2date(0) == '1970-01-01T00:00:00'
    finally:
        if original_tz is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = original_tz
        time.tzset()


# ---------------------------------------------------------------------------
# _get_recursive_dir_properties / _sum_dir_size
# ---------------------------------------------------------------------------

TREE_SPEC = {
    'mtime': 1_700_000_000,
    'entries': {
        'file1.txt': {'mtime': 1_700_000_001, 'size': 100},
        'subdir': {
            'mtime': 1_700_000_002,
            'entries': {
                'file2.txt': {'mtime': 1_700_000_003, 'size': 250},
                'nested': {
                    'mtime': 1_700_000_004,
                    'entries': {
                        'file3.txt': {'mtime': 1_700_000_005, 'size': 10},
                    },
                },
            },
        },
    },
}


def _install_tree(check, monkeypatch, fake_smb_tree, spec, base_path):
    fake_stat, fake_scandir, stat_map, scandir_map = fake_smb_tree(spec, base_path)
    monkeypatch.setattr(check.smbclient, 'stat', fake_stat)
    monkeypatch.setattr(check.smbclient, 'scandir', fake_scandir)
    return stat_map, scandir_map


def test_get_recursive_dir_properties_structure(check, monkeypatch, fake_smb_tree):
    base_path = '//testnb/school'
    _install_tree(check, monkeypatch, fake_smb_tree, TREE_SPEC, base_path)

    result = check._get_recursive_dir_properties(base_path)

    assert result['name'] == 'school'
    assert result['type'] == 'directory'
    assert result['path'] == base_path
    # size is not aggregated by this function, only by _sum_dir_size
    assert result['size'] == 0
    assert len(result['contents']) == 2

    files = {c['name']: c for c in result['contents'] if c['type'] == 'file'}
    dirs = {c['name']: c for c in result['contents'] if c['type'] == 'directory'}

    assert files['file1.txt']['size'] == 100
    assert files['file1.txt']['path'] == f'{base_path}/file1.txt'

    subdir = dirs['subdir']
    assert subdir['path'] == f'{base_path}/subdir'
    assert len(subdir['contents']) == 2

    subdir_files = {c['name']: c for c in subdir['contents'] if c['type'] == 'file'}
    subdir_dirs = {c['name']: c for c in subdir['contents'] if c['type'] == 'directory'}
    assert subdir_files['file2.txt']['size'] == 250

    nested = subdir_dirs['nested']
    assert nested['contents'][0]['name'] == 'file3.txt'
    assert nested['contents'][0]['size'] == 10


def test_get_recursive_dir_properties_last_modified_uses_timestamp2date(check, monkeypatch, fake_smb_tree):
    base_path = '//testnb/school'
    _install_tree(check, monkeypatch, fake_smb_tree, TREE_SPEC, base_path)

    result = check._get_recursive_dir_properties(base_path)

    assert result['lastModified'] == check.timestamp2date(1_700_000_000)
    file1 = next(c for c in result['contents'] if c['name'] == 'file1.txt')
    assert file1['lastModified'] == check.timestamp2date(1_700_000_001)


def test_sum_dir_size_aggregates_recursively(check, monkeypatch, fake_smb_tree):
    base_path = '//testnb/school'
    _install_tree(check, monkeypatch, fake_smb_tree, TREE_SPEC, base_path)

    tree = check._get_recursive_dir_properties(base_path)
    total = check._sum_dir_size(tree)

    # 100 (file1) + 250 (file2) + 10 (file3)
    assert total == 360
    assert tree['size'] == 360

    subdir = next(c for c in tree['contents'] if c['name'] == 'subdir')
    assert subdir['size'] == 260  # 250 + 10

    nested = next(c for c in subdir['contents'] if c['name'] == 'nested')
    assert nested['size'] == 10


def test_sum_dir_size_empty_directory_is_zero(check, monkeypatch, fake_smb_tree):
    empty_spec = {'mtime': 1000, 'entries': {}}
    base_path = '//testnb/emptyschool'
    _install_tree(check, monkeypatch, fake_smb_tree, empty_spec, base_path)

    tree = check._get_recursive_dir_properties(base_path)
    assert check._sum_dir_size(tree) == 0
    assert tree['contents'] == []


# ---------------------------------------------------------------------------
# samba_root_tree
# ---------------------------------------------------------------------------

def _fake_lr_getval(school_name):
    return types.SimpleNamespace(
        getval=lambda path, attr: school_name,
        get=lambda path, attributes=None: None,
    )


def test_samba_root_tree_success(check, monkeypatch, fake_smb_tree):
    monkeypatch.setattr(check, 'lr', _fake_lr_getval('myschool'))
    base_path = '//testnb/myschool'  # SAMBA_NETBIOS patched to 'testnb'
    _install_tree(check, monkeypatch, fake_smb_tree, TREE_SPEC, base_path)

    result = check.samba_root_tree('someuser')

    assert result is not None
    assert result['school'] == 'myschool'
    assert result['path'] == base_path
    assert result['size'] == 360  # aggregated by _sum_dir_size


def test_samba_root_tree_authentication_error_returns_none(check, monkeypatch, capsys):
    monkeypatch.setattr(check, 'lr', _fake_lr_getval('myschool'))

    def raise_auth_error(path):
        raise check.SMBAuthenticationError("bad kerberos ticket")

    monkeypatch.setattr(check.smbclient, 'stat', raise_auth_error)

    result = check.samba_root_tree('baduser')

    assert result is None
    captured = capsys.readouterr()
    assert 'baduser' in captured.out


# ---------------------------------------------------------------------------
# _samba_dir_size / samba_dir_size
# ---------------------------------------------------------------------------

def test_samba_dir_size_raw_total_from_root(check, monkeypatch, fake_smb_tree):
    monkeypatch.setattr(check, 'lr', _fake_lr_getval('myschool'))
    base_path = '//testnb/myschool'
    _, fake_scandir, _, _ = fake_smb_tree(TREE_SPEC, base_path)
    monkeypatch.setattr(check.smbclient, 'scandir', fake_scandir)

    total = check._samba_dir_size('someuser')
    assert total == 360


def test_samba_dir_size_explicit_path_skips_ldap_lookup(check, monkeypatch, fake_smb_tree):
    def explode(path, attr):
        raise AssertionError("lr.getval should not be called when path is given explicitly")

    monkeypatch.setattr(check, 'lr', types.SimpleNamespace(getval=explode, get=explode))

    base_path = '//testnb/someshare/subdir'
    small_spec = {
        'mtime': 1,
        'entries': {
            'a.txt': {'mtime': 1, 'size': 5},
            'b.txt': {'mtime': 1, 'size': 7},
        },
    }
    _, fake_scandir, _, _ = fake_smb_tree(small_spec, base_path)
    monkeypatch.setattr(check.smbclient, 'scandir', fake_scandir)

    total = check._samba_dir_size('someuser', path=base_path)
    assert total == 12


def test_samba_dir_size_public_wrapper_raw_vs_formatted(check, monkeypatch, fake_smb_tree):
    monkeypatch.setattr(check, 'lr', _fake_lr_getval('myschool'))
    base_path = '//testnb/myschool'
    _, fake_scandir, _, _ = fake_smb_tree(TREE_SPEC, base_path)
    monkeypatch.setattr(check.smbclient, 'scandir', fake_scandir)

    assert check.samba_dir_size('someuser', raw=True) == 360
    assert check.samba_dir_size('someuser', raw=False) == format_size(360)


# ---------------------------------------------------------------------------
# list_user_files
# ---------------------------------------------------------------------------

class _FakeOsStat:
    def __init__(self, st_uid, st_size):
        self.st_uid = st_uid
        self.st_size = st_size


class _FakePwEntry:
    def __init__(self, pw_name):
        self.pw_name = pw_name


def test_list_user_files_filters_by_owner_and_aggregates_sizes(check, monkeypatch):
    # SAMBA_WORKGROUP is patched to 'TESTDOM' by the autouse fixture.
    sizes = {'a.txt': 100, 'b.txt': 200, 'c.txt': 50, 'z.txt': 999}
    walk_data = [
        ('/srv/samba/school1/alice', [], ['a.txt', 'b.txt']),
        ('/srv/samba/school1/alice/sub', [], ['c.txt']),
        ('/srv/samba/school1/bob', [], ['z.txt']),
    ]

    monkeypatch.setattr(check.os, 'walk', lambda path: iter(walk_data))

    def fake_stat(full_path):
        fname = os.path.basename(full_path)
        uid = 1000 if 'alice' in full_path else 2000
        return _FakeOsStat(st_uid=uid, st_size=sizes[fname])

    monkeypatch.setattr(check.os, 'stat', fake_stat)

    def fake_getpwuid(uid):
        return _FakePwEntry(pw_name='TESTDOM\\alice' if uid == 1000 else 'TESTDOM\\bob')

    monkeypatch.setattr(check.pwd, 'getpwuid', fake_getpwuid)

    result = check.list_user_files('alice')

    assert set(result['directories'].keys()) == {'/srv/samba/school1/alice'}
    bucket = result['directories']['/srv/samba/school1/alice']
    assert bucket['total'] == format_size(350)  # 100 + 200 + 50, bob's file excluded
    assert bucket['files']['a.txt'] == format_size(100)
    assert bucket['files']['b.txt'] == format_size(200)
    assert bucket['files']['c.txt'] == format_size(50)
    assert result['total'] == format_size(350)


def test_list_user_files_prefix_boundary_bug(check, monkeypatch):
    """
    Documents current behaviour of the `root.startswith(directory)` check:
    it has no path-separator boundary, so a sibling directory whose name is
    merely prefixed by an already-seen directory name gets merged into it.
    See bug note in the final report.
    """
    sizes = {'a.txt': 10, 'old.txt': 20}
    walk_data = [
        ('/srv/samba/school1/alice', [], ['a.txt']),
        ('/srv/samba/school1/alice-archive', [], ['old.txt']),
    ]
    monkeypatch.setattr(check.os, 'walk', lambda path: iter(walk_data))

    def fake_stat(full_path):
        return _FakeOsStat(st_uid=1000, st_size=sizes[os.path.basename(full_path)])

    monkeypatch.setattr(check.os, 'stat', fake_stat)
    monkeypatch.setattr(check.pwd, 'getpwuid', lambda uid: _FakePwEntry(pw_name='TESTDOM\\alice'))

    result = check.list_user_files('alice')

    # Current (buggy) behaviour: only one bucket, 'alice-archive' merged into 'alice'.
    assert set(result['directories'].keys()) == {'/srv/samba/school1/alice'}
    bucket = result['directories']['/srv/samba/school1/alice']
    assert bucket['files'].keys() == {'a.txt', 'old.txt'}


# ---------------------------------------------------------------------------
# get_user_quotas
# ---------------------------------------------------------------------------

def _fake_lr_get(attributes):
    # NB: check.py calls `lr.get(path, attributes=[...])` where `attributes`
    # is the *requested attribute names*, not our fake return value -- so we
    # must not reuse that keyword name for our captured fixture data, or the
    # caller's keyword argument would shadow it.
    return types.SimpleNamespace(
        get=lambda path, attributes=None, _fake_result=attributes: _fake_result,
        getval=lambda path, attr: None,
    )


def _fake_run_factory(out, returncode=0, err=''):
    calls = []

    def fake_run(cmd, capture_output=True):
        calls.append(cmd)
        return types.SimpleNamespace(
            returncode=returncode,
            stdout=out.encode(),
            stderr=err.encode(),
        )

    return fake_run, calls


def _patch_admin_secret(check, monkeypatch, secret='testpw123'):
    monkeypatch.setattr(check, 'open', lambda *a, **k: io.StringIO(secret + '\n'), raising=False)


def test_get_user_quotas_non_admin_success(check, monkeypatch):
    attributes = {
        'sophomorixCloudQuotaCalculated': '500 MB',
        'sophomorixMailQuotaCalculated': '200',
        'sophomorixSchoolname': 'default-school',
        'sophomorixRole': 'teacher',
    }
    monkeypatch.setattr(check, 'lr', _fake_lr_get(attributes))
    _patch_admin_secret(check, monkeypatch)

    out = "Get quota  User  1048576/  2097152/  3145728/"
    fake_run, calls = _fake_run_factory(out)
    monkeypatch.setattr(check.subprocess, 'run', fake_run)

    result = check.get_user_quotas('alice')

    assert set(result.keys()) == {'default-school', 'linuxmuster-global', 'cloud', 'mail'}
    assert result['default-school'] == {'used': 1.0, 'soft_limit': 2.0, 'hard_limit': 3.0}
    assert result['linuxmuster-global'] == {'used': 1.0, 'soft_limit': 2.0, 'hard_limit': 3.0}
    assert result['cloud'] == '500'
    assert result['mail'] == '200'

    # Non-DFS share path is built as //SAMBA_DOMAIN/share
    joined = [' '.join(c) for c in calls]
    assert any('//testdom.example.org/default-school' in c for c in joined)
    assert any('administrator%testpw123' in c for c in joined)


def test_get_user_quotas_admin_role_uses_shares_list(check, monkeypatch):
    attributes = {
        'sophomorixCloudQuotaCalculated': '0 MB',
        'sophomorixMailQuotaCalculated': '0',
        'sophomorixSchoolname': 'default-school',
        'sophomorixRole': 'schooladministrator',
    }
    monkeypatch.setattr(check, 'lr', _fake_lr_get(attributes))
    _patch_admin_secret(check, monkeypatch)

    out = "Get quota  User  1048576/  2097152/  3145728/"
    fake_run, calls = _fake_run_factory(out)
    monkeypatch.setattr(check.subprocess, 'run', fake_run)

    result = check.get_user_quotas('someadmin')

    # SHARES_LIST is patched (autouse) to ['default-school', 'linuxmuster-global']
    assert 'default-school' in result
    assert 'linuxmuster-global' in result
    assert len(calls) == len(check.SHARES_LIST)


def test_get_user_quotas_dfs_path_used_when_available(check, monkeypatch):
    attributes = {
        'sophomorixCloudQuotaCalculated': '0 MB',
        'sophomorixMailQuotaCalculated': '0',
        'sophomorixSchoolname': 'default-school',
        'sophomorixRole': 'teacher',
    }
    monkeypatch.setattr(check, 'lr', _fake_lr_get(attributes))
    _patch_admin_secret(check, monkeypatch)
    monkeypatch.setattr(check, 'DFS', {'default-school': {'dfs_proxy': r'\\dfsserver\default-school'}})

    out = "Get quota  User  1048576/  2097152/  3145728/"
    fake_run, calls = _fake_run_factory(out)
    monkeypatch.setattr(check.subprocess, 'run', fake_run)

    check.get_user_quotas('alice')

    joined = [' '.join(c) for c in calls]
    assert any(r'\\dfsserver\default-school' in c for c in joined)


def test_get_user_quotas_smbcquotas_error_branch(check, monkeypatch):
    attributes = {
        'sophomorixCloudQuotaCalculated': '0 MB',
        'sophomorixMailQuotaCalculated': '0',
        'sophomorixSchoolname': 'default-school',
        'sophomorixRole': 'teacher',
    }
    monkeypatch.setattr(check, 'lr', _fake_lr_get(attributes))
    _patch_admin_secret(check, monkeypatch)

    fake_run, calls = _fake_run_factory(
        "NT_STATUS_ACCESS_DENIED", returncode=1, err="NT_STATUS_ACCESS_DENIED"
    )
    monkeypatch.setattr(check.subprocess, 'run', fake_run)

    result = check.get_user_quotas('alice')

    assert result['default-school']['ERROR']['code'] == 1
    assert result['default-school']['ERROR']['error'] == "NT_STATUS_ACCESS_DENIED"


def test_get_user_quotas_no_limit_passthrough(check, monkeypatch):
    attributes = {
        'sophomorixCloudQuotaCalculated': '0 MB',
        'sophomorixMailQuotaCalculated': '0',
        'sophomorixSchoolname': 'default-school',
        'sophomorixRole': 'teacher',
    }
    monkeypatch.setattr(check, 'lr', _fake_lr_get(attributes))
    _patch_admin_secret(check, monkeypatch)

    out = "Get quota  User  1048576/  NO LIMIT/  NO LIMIT/"
    fake_run, calls = _fake_run_factory(out)
    monkeypatch.setattr(check.subprocess, 'run', fake_run)

    result = check.get_user_quotas('alice')

    assert result['default-school']['used'] == 1.0
    assert result['default-school']['soft_limit'] == 'NO LIMIT'
    assert result['default-school']['hard_limit'] == 'NO LIMIT'


def test_get_user_quotas_missing_user_raises(check, monkeypatch):
    monkeypatch.setattr(check, 'lr', _fake_lr_get(None))
    with pytest.raises(Exception, match='not found in ldap'):
        check.get_user_quotas('ghost')
