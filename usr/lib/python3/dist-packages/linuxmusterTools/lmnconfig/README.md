# lmnconfig

System configuration loader for [linuxmuster.net](https://www.linuxmuster.net), exposing Samba, sophomorix, setup, server and webui settings as ready-to-use Python constants and small config objects.

`lmnconfig` has no factory or single entry point: each submodule reads its own configuration source (`smb.conf`, `setup.ini`, `sophomorix.conf`, …) at import time or on instantiation, and everything is re-exported at the package level via `from linuxmusterTools.lmnconfig import ...`.

---

## Requirements

- Python 3.8+
- [`configobj`](https://pypi.org/project/configobj/)
- A configured Samba/AD server (`/etc/samba/smb.conf`, `net conf list`) for `samba.py`
- A running [linuxmuster.net](https://www.linuxmuster.net) setup for `setup.py` and `sophomorix.py` (`/var/lib/linuxmuster/setup.ini`, `/etc/linuxmuster/sophomorix/`)

---

## Usage

```python
from linuxmusterTools.lmnconfig import SAMBA_REALM, SAMBA_DOMAIN, LDAP_CONTEXT
```

### `samba.py` — module-level constants

Computed once at import time by parsing `/etc/samba/smb.conf` and the output of `net conf list`.

| Name | Type | Description |
|---|---|---|
| `SAMBA_REALM` | `str` | Kerberos realm, lowercased (`school.lan`) |
| `SAMBA_WORKGROUP` | `str` | Samba workgroup |
| `SAMBA_NETBIOS` | `str` | NetBIOS name, lowercased |
| `SAMBA_DOMAIN` | `str` | `f'{SAMBA_NETBIOS}.{SAMBA_REALM}'` |
| `SAMBA_TLD` | `str` | Top-level domain component of the realm, uppercased |
| `LDAP_DC` | `str` | Realm as LDAP `DC=` components (`DC=SCHOOL,DC=LAN`) |
| `LDAP_CONTEXT` | `str` | `f'OU=SCHOOLS,{LDAP_DC}'` |
| `LOG_LEVEL` | `dict` | Parsed `log level` directive, e.g. `{'general': 1, 'auth_audit': 3}` |
| `SHARES_LIST` | `list[str]` | All share names from `net conf list` |
| `DFS` | `dict` | Shares with `msdfs root = yes`, mapped to their `dfs_proxy` (UNC form) |

```python
from linuxmusterTools.lmnconfig import SAMBA_REALM, SAMBA_DOMAIN, LDAP_CONTEXT

print(SAMBA_DOMAIN)      # 'server.school.lan'
print(LDAP_CONTEXT)      # 'OU=SCHOOLS,DC=SCHOOL,DC=LAN'
```

If `/etc/samba/smb.conf` is missing or unreadable, all constants above default to `''` (or `{}`/`[]`) and a warning/error is logged — the module never raises on import.

### `server.py` — module-level constants

| Name | Type | Description |
|---|---|---|
| `SERVER_HOSTNAME` | `str` | Result of `socket.gethostname()` |
| `SERVER_IP` | `str` | First non-loopback IP of the server, or an error string if none is found |

### `setup.py` — `SetupConfig`

Reads `/var/lib/linuxmuster/setup.ini` (installer configuration).

```python
from linuxmusterTools.lmnconfig import SetupConfig

setup = SetupConfig(school='default-school')
setup.config['setup']['schoolname']
```

`config` is `{}` if the school is not `'default-school'` or the file does not exist.

### `sophomorix.py` — school and sophomorix configuration

```python
from linuxmusterTools.lmnconfig import SchoolConfig, SophomorixIni, SophomorixConf

school = SchoolConfig(school='default-school')
school.config['global']['SCHOOLNAME']

ini = SophomorixIni()
ini.get('ROLE_USER', 'teacher')
ini.userrole          # ['teacher', 'student', ...], keys of section ROLE_USER
ini.computerrole       # computer roles, 'computerrole.' prefix stripped
ini.clientrole         # hardcoded list of LINBO client roles

conf = SophomorixConf()
conf.data['global']['LANG']
```

| Class | Source file | Description |
|---|---|---|
| `SchoolConfig` | `/etc/linuxmuster/sophomorix/{school}/[{school}.]school.conf` | Per-school sophomorix settings, `.config` dict |
| `SophomorixIni` | `/usr/share/sophomorix/devel/sophomorix.ini` | Parsed sophomorix reference INI: roles, computer roles, sections |
| `SophomorixConf` | `/etc/linuxmuster/sophomorix/sophomorix.conf` | Global sophomorix settings, `.data` dict |
| `MultiOrderedDict` | — | `OrderedDict` variant used by `SophomorixIni`: re-assigning a list key extends it instead of overwriting it |

All three config classes fall back to an empty dict (`.config`/`.data` == `{}`) and log a warning if their file is missing.

### `webui.py` — `CustomFieldsConfig`

Reads `/etc/linuxmuster/sophomorix/{school}/custom_fields.yml` and splits it per role.

```python
from linuxmusterTools.lmnconfig import CustomFieldsConfig

fields = CustomFieldsConfig(school='default-school')
fields.students['custom']              # {'field1': 'value1', ...}
fields.teachers['passwordTemplates']
```

Each of `globaladministrators`, `schooladministrators`, `students`, `teachers` is set as an attribute holding a dict with the keys `custom`, `customDisplay`, `customMulti`, `passwordTemplates`, `proxyAddresses` — missing entries default to `{}`.

> When `linuxmusterTools.common.WEBUI_IMPORT` is `True` (module imported from inside the webui process), `__init__` returns immediately with `config = {}` and none of the per-role attributes are set.

---

## Import-time side effects

`samba.py` and `server.py` perform their reads at **import time**, not on instantiation — importing `linuxmusterTools.lmnconfig` (or any of its constants) triggers a `smb.conf` parse, a `net conf list` subprocess call, and a hostname/IP lookup. `setup.py`, `sophomorix.py` and `webui.py` only read their files when their classes are instantiated.
