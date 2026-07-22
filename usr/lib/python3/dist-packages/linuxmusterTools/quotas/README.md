# quotas

Utility functions to inspect disk usage and Samba share quotas for [linuxmuster.net](https://www.linuxmuster.net) users.

---

## Requirements

- Python 3.8+
- [`smbclient`](https://pypi.org/project/smbclient/) and [`smbprotocol`](https://pypi.org/project/smbprotocol/) (SMB access, Kerberos-authenticated)
- `smbcquotas` (Samba client tools) available on `$PATH`
- A readable `/etc/linuxmuster/.secret/administrator` password file

---

## Usage

### Import

```python
from linuxmusterTools.quotas import list_user_files, get_user_quotas, samba_root_tree, samba_dir_size
```

### `list_user_files(user)`

Walks `/srv/samba` on the local filesystem and returns every file owned by `user`, grouped by directory.

```Console
>>> from linuxmusterTools.quotas import list_user_files
>>> list_user_files('kiar')
{
    'directories': {
        '/srv/samba/default-school/students/8a': {
            'files': {'report.odt': '128.0 KB', 'photo.jpg': '2.3 MB'},
            'total': '2.4 MB'
        },
    },
    'total': '2.4 MB',
}
```

### `get_user_quotas(user)`

Runs `smbcquotas` against every share relevant to `user` (all shares for administrators, the user's own school and `linuxmuster-global` otherwise), plus the cloud and mail quotas read from LDAP.

```Console
>>> from linuxmusterTools.quotas import get_user_quotas
>>> get_user_quotas('jdupont')
{
    'default-school': {'used': 12.34, 'soft_limit': 500.0, 'hard_limit': 550.0},
    'linuxmuster-global': {'used': 0.5, 'soft_limit': 'NO LIMIT', 'hard_limit': 'NO LIMIT'},
    'cloud': '0',
    'mail': '1024',
}
```

Raises an `Exception` if `user` is not found in LDAP. A share whose `smbcquotas` call fails is reported as `{'ERROR': {'output': ..., 'error': ..., 'code': ...}}` instead of raising.

### `samba_root_tree(user)`

Recursively lists files and folders of `user`'s school root share over SMB, with size and last-modified metadata for every entry. Requires a valid Kerberos ticket for the calling process; returns `None` (and logs a message) if authentication fails.

```Console
>>> from linuxmusterTools.quotas import samba_root_tree
>>> samba_root_tree('jdupont')
{
    'name': 'default-school',
    'type': 'directory',
    'size': 5242880,
    'lastModified': '2026-07-20T08:12:00',
    'contents': [...],
    'path': '//SAMBA-NETBIOS/default-school',
    'school': 'default-school',
}
```

### `samba_dir_size(user, path=None, raw=False)`

Returns the total size of `path` over SMB (defaults to `user`'s school root share). Returns a human-readable string by default; pass `raw=True` to get the size in bytes.

```Console
>>> from linuxmusterTools.quotas import samba_dir_size
>>> samba_dir_size('jdupont')
'5.0 MB'
>>> samba_dir_size('jdupont', raw=True)
5242880
```
