# common

Shared low-level helpers for [linuxmuster.net](https://www.linuxmuster.net): name/certificate validation, colored shell output, value conversion, sophomorix log parsing and a couple of small utilities used across the other `linuxmusterTools` modules.

`common` has no single entry point like `LMNLdapReader` or `LMNFile`. Instead, its `__init__.py` re-exports a handful of ready-to-use instances and helper functions directly under `linuxmusterTools.common`.

---

## Requirements

- Python 3.8+
- No third-party dependencies — only the standard library is used (`re`, `ssl`, `socket`, `logging`, `itertools`, `threading`, `time`, `math`, `datetime`, `pathlib`, `functools`, `os`).
- `common/attic.py` additionally imports `lmnconfig`, `ldapconnector` and `smbclient` from `linuxmusterTools` itself (internal, not third-party) to look up user and file information.

---

## Usage

```python
from linuxmusterTools.common import Validator, lprint, lcolor, spinner
```

`Validator`, `lprint`, `lcolor` and `spinner` are singleton instances created once in `__init__.py`; import and use them directly rather than instantiating the underlying classes again.

---

## Name validation — `Validator`

`Validator` is a ready-to-use `NameChecker` instance. For every rule declared in `NAME_RULES`, a `check_<name>_name(string)` method is generated automatically.

```python
Validator.check_login_name('jdoe')                 # True
Validator.check_ip_name('10.0.0.5')                # True
Validator.check_mac1_name('AA:BB:CC:DD:EE:FF')      # True
Validator.normalize_mac('aa-bb-cc-dd-ee-ff')        # 'AA:BB:CC:DD:EE:FF'
```

`check(name_type, string)` (and its `check_*_name` shortcuts) always reject non-string/empty input and any string containing `/`, `\`, `\0` or `..` (path traversal guard), before matching it against the rule's regex.

| Rule | Typical use |
|---|---|
| `password` | Allowed characters in a password |
| `strong_password` | Password with lower/upper case, digit or symbol, 7+ chars |
| `project` / `group` | Project or sophomorix group name |
| `session` | Session name |
| `linbo_conf` | LINBO config name |
| `linbo_image` | LINBO image name |
| `login` | User login |
| `comment` | `sophomorixComment` field |
| `alphanum` | Generic config name |
| `number` | Digits only |
| `date` | `dd.mm.yyyy` |
| `ip` | IPv4 address |
| `mac1` / `mac2` / `mac3` | MAC address, colon-, hyphen- or non-separated |
| `host` / `room` | Hostname or room name |
| `domain` | Domain name |

`normalize_mac(mac)` accepts any of the three MAC formats and returns it uppercased and colon-separated, or `None` if the input matches none of them.

---

## Certificate expiry — `DomCert`

```python
from linuxmusterTools.common import DomCert

cert = DomCert('linuxmuster.example.com', 443)
cert.isvalid()    # True/False, refreshes the certificate first
cert.expires()    # '87 days (Jan 15 12:00:00 2027 GMT)' or 'Expired since ...'
```

`DomCert(hostname, port)` fetches the peer certificate over SSL on instantiation; `.notAfter`, `.notAfter_timestamp`, `.issuer` and `.valid` are then available as attributes.

---

## Colored shell output — `lcolor` / `lprint`

```python
from linuxmusterTools.common import lcolor, lprint

lcolor.green('OK')          # wraps the text in an ANSI color, returns a string
lprint.success('Done')      # prints the colorized text directly
```

| `ColorShell` method | `PrintShell` method | Color |
|---|---|---|
| `red(text)` | `danger(result, end="\n")` | danger (red) |
| `orange(text)` | `alert(result, end="\n")` | alert (orange) |
| `yellow(text)` | `warning(result, end="\n")` | warning (yellow) |
| `blue(text)` | `info(result, end="\n")` | info (cyan) |
| `green(text)` | `success(result, end="\n")` | success (green) |
| `lmn(text)` | `lmn(result, end="\n")` | linuxmuster brand color (bold orange) |

`PrintShell.printsh(color, text, end="\n")` prints with any raw ANSI escape sequence, for colors not covered above.

---

## Terminal spinner — `spinner`

```python
from linuxmusterTools.common import spinner

with spinner:
    spinner.print('Updating LDAP entries...')
    # long-running work
    spinner.print('Rebuilding indexes...')
```

`Spinner(color=SHELL_COLOR_WARNING, progress=False)` animates a Braille spinner on a background thread. It is a no-op when stdout is not a TTY (e.g. redirected to a file). With `progress=True`, each `print()` call leaves the previous line on screen with a checkmark instead of overwriting it.

---

## Value conversion

```python
from linuxmusterTools.common import format_size, convert_sophomorix_time, convert_sophomorix_status

format_size(1536)                                # '1.50 KiB'
format_size(1500, base=10)                        # '1.50 KB'
convert_sophomorix_time('20081030125303.0Z')      # '30 Oct 2008 12:53:03'
convert_sophomorix_status('T')                    # 'Tolerated'
```

| Function | Description |
|---|---|
| `format_size(num, suffix='B', base=2)` | Human-readable size, binary (`base=2`, Ki/Mi/Gi...) or decimal (`base=10`, K/M/G...) |
| `convert_sophomorix_time(t)` | Sophomorix timestamp (`20081030125303.0Z`) → readable date; returns the input unchanged if it cannot be parsed |
| `convert_sophomorix_status(s)` | Sophomorix status letter (`T`, `D`, `K`, ...) → readable label; returns `'Unknown'` for unrecognized codes |

---

## Sophomorix log parsing

```python
from linuxmusterTools.common import parse_kill_log, parse_add_log, parse_update_log

parse_kill_log(today=True)
parse_add_log(lastweek=True)
parse_update_log(all=True, list_changes=True)
```

| Function | Log file |
|---|---|
| `parse_kill_log(all=False, epoch=None, today=False, lastweek=False)` | `/var/log/sophomorix/userlog/user-kill.log` |
| `parse_add_log(all=False, epoch=None, today=False, lastweek=False)` | `/var/log/sophomorix/userlog/user-add.log` |
| `parse_update_log(all=False, epoch=None, today=False, lastweek=False, list_changes=True)` | `/var/log/sophomorix/userlog/user-update.log` |

Each function returns a `dict` keyed by timestamp. `all`, `today` and `lastweek` are mutually exclusive (an exception is raised otherwise); without any of them, only entries from the last year are kept. Pass `epoch` to filter on one specific timestamp instead — the result is then a `list` for that timestamp only.

---

## Exceptions

```python
from linuxmusterTools.common import SchoolError, LdapNotProvisionedError

raise SchoolError("'global' is not a valid school scope here")
raise LdapNotProvisionedError("Samba not provisioned yet")
```

`SchoolError` is raised when an operation is given an invalid or unresolvable school scope (e.g. `'global'` where a single, concrete school is required).

`LdapNotProvisionedError` is raised by [`ldapconnector`](../ldapconnector/README.md) when LDAP/Samba credentials are requested before `linuxmuster-setup` has provisioned the domain (fresh install, setup wizard not completed yet).

---

## Provisioning status

```python
from linuxmusterTools.common import is_samba_provisioned

if not is_samba_provisioned():
    ...  # redirect to the setup wizard instead of touching LDAP
```

`is_samba_provisioned(admin_secret_path='/etc/linuxmuster/.secret/administrator')` returns whether `samba-tool domain provision` has actually run, based on the AD administrator secret it creates. `/var/lib/linuxmuster/setup.ini` (used by the setup wizard to decide whether to show the welcome screen) is not a reliable signal here: it's written by `linuxmuster-setup`'s very first module, well before Samba is provisioned, so it exists for most of the setup run while LDAP is still unusable.

---

## Webui integration flag

```python
from linuxmusterTools.common import WEBUI_IMPORT

if WEBUI_IMPORT:
    from linuxmusterTools.common import params   # ldap_config from the Ajenti webui plugin
```

`WEBUI_IMPORT` is `True` when `common` is imported from within the Ajenti webui process (i.e. `aj.plugins.lmn_common.api` is importable), `False` otherwise (CLI, API). `params` only exists when `WEBUI_IMPORT` is `True`.

---

## Temp directory helper

```python
from linuxmusterTools.common import check_tmp_dir

check_tmp_dir()   # ensures /tmp/lmntool exists with mode 0o600
```

---

## Submodules not re-exported at package level

The following helpers are not imported into `linuxmusterTools.common`'s namespace and must be imported from their own submodule.

### `common.attic`

```python
from linuxmusterTools.common.attic import get_attic_status, check_attic_dir
```

| Function | Description |
|---|---|
| `get_attic_status(user)` | Status (tolerated/deactivated/killable/killed) and start/end dates of a user in attic. Single-school only. |
| `check_attic_dir(school='default-school')` | Lists all users under `students/attic` for one school (or every school if `school` is `None`) with their attic status. Experimental. |

### `common.timestamps`

```python
from linuxmusterTools.common.timestamps import get_utc_mtime, linbo_timestamp_to_epoch

get_utc_mtime(Path('/etc/linuxmuster/sophomorix/default-school/students.csv'))
# datetime(..., tzinfo=timezone.utc), or None if the file does not exist

linbo_timestamp_to_epoch('202608071440')
# 1786106400.0
```

| Function | Description |
|---|---|
| `get_utc_mtime(path)` | A file's mtime as a UTC datetime, or `None` if the file does not exist. |
| `linbo_timestamp_to_epoch(timestamp)` | A LINBO `YYYYMMDDHHMI` timestamp as a Unix epoch. LINBO clients write their local wall clock, which matches the server's local time, so the timestamp is read as server-local — never as UTC. Raises `ValueError` on a malformed timestamp. |
