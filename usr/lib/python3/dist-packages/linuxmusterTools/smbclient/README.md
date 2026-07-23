# smbclient

A thin wrapper around the `/bin/smbclient` command-line tool for basic file operations on the linuxmuster.net fileserver.

`smbclient` exposes a single entry point — `LMNSMBClient` — which authenticates as `administrator` against a school's Samba share and runs simple `dir`/`deltree` subcommands through `subprocess`.

---

## Requirements

- Python 3.8+
- The `/bin/smbclient` binary (package `smbclient`/`samba-client` on Debian, **not** the PyPI package)
- Readable `/etc/linuxmuster/.secret/administrator` (administrator password)
- A reachable Samba/AD server (via `linuxmusterTools.lmnconfig.SAMBA_DOMAIN`)

> **Naming collision**: this module is unrelated to the PyPI package [`smbclient`](https://pypi.org/project/smbclient/) (SMB2/3 protocol client), which is used elsewhere in this codebase (see `quotas/README.md`). `linuxmusterTools.smbclient` only shells out to the `smbclient` CLI binary — it does not use the `smbclient`/`smbprotocol` Python packages.

> Module docstring: "Actually still in experimental mode."

---

## Usage

### Import

```python
from linuxmusterTools.smbclient import LMNSMBClient
```

### Instantiation

```python
client = LMNSMBClient(school='default-school')
```

The school is validated against `/schools` in LDAP on instantiation; an unknown school raises `Exception`.

### `switch(school)`

Switches the client to another school. Raises `Exception` if the school is unknown, leaving the previous school untouched.

```python
client.switch('school2')
```

### `list(path)`

Returns the content of a directory on the share as a list of dicts.

```python
client.list('students/10a/myuser/transfer')
# [
#   {'name': '.', 'type': 'directory', 'size': '0'},
#   {'name': '..', 'type': 'directory', 'size': '0'},
#   {'name': 'file1.txt', 'type': 'file', 'size': '1234'},
#   {'name': 'subdir', 'type': 'directory', 'size': '0'},
# ]
```

Raises `Exception` if `smbclient` reports an error (`smbclient` may return exit code `0` even on failure, so the result is only trusted if the first listed entry is `.`).

### `deltree(path)`

Recursively deletes the content of a directory.

```python
client.deltree('students/attic/myuser')
```
