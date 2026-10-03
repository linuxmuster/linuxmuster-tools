# devices

Inventory and reachability checks for the devices registered in [linuxmuster.net](https://www.linuxmuster.net) (`devices.csv`).

`devices` exposes two classes: `Devices`, which loads and queries the per-school device inventory, and `UPChecker`, which probes hosts over the network to determine whether they are online and what they are running (LINBO, Linux, Windows). The `validator` submodule holds the validation rules applied to an inventory, one function per value.

---

## Requirements

- Python 3.8+
- `nmap` command-line tool available on `PATH` (used by `UPChecker.test_online()`)
- Standard library only otherwise (`subprocess`, `xml.etree.ElementTree`, `concurrent.futures`, `pathlib`)

---

## Usage

### Import

```python
from linuxmusterTools.devices import Devices, UPChecker
```

### `Devices` — inventory

Loads `/etc/linuxmuster/sophomorix/SCHOOL/[SCHOOL.]devices.csv` on instantiation. If that file doesn't exist yet (fresh install, school not provisioned yet), `devices`/`groups`/`macs`/`ips`/`rooms`/`hostnames` are simply left empty instead of raising.

Two different prefixes come with a school and must not be confused: `prefix` (`'school1.'`) names the inventory **file**, `hostname_prefix` (`'school1-'`) names a **host** as seen from outside its own school - it is sophomorix' own `SCHOOLS.<school>.PREFIX`. Use `prefixed_hostnames` to answer "does this host, named by something that doesn't know about schools, belong to this school?" rather than rebuilding the name at the call site.

```python
devicesmgr = Devices(school='default-school')
```

| Parameter | Type | Description |
|---|---|---|
| `school` | `str` | School whose inventory to load (default: `'default-school'`) |

#### Attributes populated after load

| Attribute | Type | Description |
|---|---|---|
| `devices` | `list[dict]` | All rows of `devices.csv`, enriched (see below); comment lines (`room` starting with `#`) are skipped |
| `groups` | `list[str]` | Unique LINBO groups found in the inventory, in natural order |
| `macs` | `list[str]` | Unique normalized MAC addresses, in natural order |
| `ips` | `list[str]` | Unique IP addresses, in natural order (`10.0.0.2` before `10.0.0.10`) |
| `rooms` | `list[str]` | Unique room names, in natural order |
| `hostnames` | `list[str]` | Unique host names, as written in the inventory, in natural order (`r1-pc5` before `r1-pc10`, see `common.sort_naturally`) |
| `prefixed_hostnames` | `set[str]` | The same hosts named `<school>-<hostname>`, the form used outside their own school (LINBO logs, hwinfo files, AD objects); identical to `hostnames` for `default-school` |
| `hostname_prefix` | `str` | `'<school>-'`, or `''` for `default-school` |
| `clients` | `list[dict]` | Devices whose `sophomorixRole` is a client role (from `sophomorix.ini`) |
| `csv_mtime` | `datetime` | Last modification time of the CSV file (UTC) |

Each device `dict` is enriched on load with:

- `school` — the school it was loaded for
- `mac` — normalized to `AA:BB:CC:DD:EE:FF` uppercase colon form (`None` if invalid)
- `macRaw` — the address exactly as written in the file, always a `str`. `mac` is `None` for a malformed address, which names nothing in an error message
- `csvLine` — `int`, the physical line of the device in `devices.csv`, comments and empty lines included, so a caller can point at the line to fix
- `pxeEnabled` — `bool`, `True` only if `pxeFlag` is a positive integer and `group` is not `nopxe` (case-insensitive)

#### Methods

| Method | Description |
|---|---|
| `switch(school)` | Reload the inventory for another school |
| `load()` | Reload the current school's inventory from disk |
| `filter(roles=[], groups=[], macs=[])` | Filter devices; `roles`/`groups` can be combined, `macs` must be used alone |
| `get_host(hostname, roles=[], groups=[])` | Return a single device dict by hostname, or `None` |
| `get_hosts_by_macs(macs=[])` | Shortcut for `filter(macs=macs)` |
| `get_client(hostname, groups=[])` | `get_host()` restricted to client roles |
| `get_clients(groups=[])` | `filter()` restricted to client roles |
| `check_conf()` | Validate this school's inventory; returns a result `dict` (see [Validation](#validation)) |

```python
devicesmgr = Devices()
devicesmgr.filter(roles=['classroom-studentcomputer'], groups=['g-pcs'])
devicesmgr.get_client('pc01')

devicesmgr.switch('school1')          # reload for another school
```

### Module level functions

| Function | Description |
|---|---|
| `list_schools(root=None)` | Schools holding a `devices.csv`, read from disk (default root: `/etc/linuxmuster/sophomorix`) |
| `check_all_schools(schools=None)` | Validate every school at once; discovers the schools with `list_schools()` if none are given |

`check_all_schools()` is not a loop over `check_conf()`: host names and MAC addresses are unique over the whole installation, and a value used twice in two different schools can not be seen from one school alone. A caller already holding the authoritative list of provisioned schools (`ldapconnector.checks.schools.valid_schools()`) passes it rather than letting the filesystem answer.

### `UPChecker` — reachability checks

Wraps `nmap` scans on top of `Devices` to determine a host's status.

```python
checker = UPChecker(school='default-school')
```

| Parameter | Type | Description |
|---|---|---|
| `school` | `str` | School whose client devices to check (default: `'default-school'`) |

#### Methods

| Method | Description |
|---|---|
| `checkhost(hostname)` | Check a single known client by hostname; `{}` if not found |
| `check(groups=[])` | Check all client devices (optionally restricted to `groups`), in parallel via a thread pool |
| `test_online(device)` | Run `nmap` against a device dict's `ip` and classify the result |
| `get_os_from_ports(ports)` | Classify a `{port: state}` dict into an OS string |

`test_online()`/`check()` return one of: `"Off"`, `"No response"`, `"Linbo"`, `"OS Linux"`, `"OS Windows"`, `"OS Unknown"`.

```python
checker = UPChecker()
checker.checkhost('pc01')
# {'10.16.1.10': 'Linbo'}

checker.check(groups=['g-pcs'])
# {'10.16.1.10': 'Linbo', '10.16.1.11': 'Off', ...}
```

---

## Classification logic

`nmap` is run against ports `2222` (LINBO), `22` (SSH) and `135` (RPC):

| Signature | Criteria |
|---|---|
| `Linbo` | Only port `2222` is open |
| `OS Linux` | Port `22` open/filtered, port `135` not open |
| `OS Windows` | Port `135` open/filtered, port `22` not open |
| `OS Unknown` | None of the above |
| `No response` | All three ports filtered |
| `Off` | `nmap` reports zero hosts up |

`Linbo` takes precedence when a host could match more than one signature.

---

## Validation

`check_conf()` and `check_all_schools()` report **everything** they find instead of stopping at the first problem, and both return the same `dict`:

| Key | Type | Description |
|---|---|---|
| `valid` | `bool` | `True` when no finding has the `error` severity; warnings do not make an inventory invalid |
| `counts` | `dict` | `schools`, `devices`, `errors`, `warnings` |
| `findings` | `list[dict]` | One entry per problem, see below |
| `report` | `list[str]` | The same problems as flat strings, for a caller that only prints what it gets |

```python
>>> from linuxmusterTools.devices import Devices, check_all_schools
>>> result = Devices().check_conf()
>>> result['valid']
False
>>> result['counts']
{'schools': 1, 'devices': 45, 'errors': 1, 'warnings': 0}
>>> result['report'][0]
'ERROR: pc02: 999.999.999.999 is not a valid ip address (/etc/linuxmuster/sophomorix/default-school/devices.csv, line 12)'
>>> result['findings'][0]['code']
'ip.invalid'
```

Each finding carries:

| Key | Type | Description |
|---|---|---|
| `severity` | `str` | `'error'` or `'warning'` |
| `code` | `str` | Stable identifier of the rule, e.g. `'hostname.too_long'` — branch and translate on this, never on `message` |
| `message` | `str` | The problem in English, built here and therefore not translatable by the caller |
| `field` | `str` | Field of `devices.csv` concerned |
| `value` | `str` | The offending value, as written in the file |
| `school`, `file`, `line` | `str`, `str`, `int` | Where to fix it; `line` is the physical line of `devices.csv` |
| `subject` | `str` | What the finding is about, unprefixed — the host name here, a login in another inventory |
| `related` | `list[dict]` | For a duplicate, the other devices sharing the value (`school`, `subject`, `line`, `file`) |

### Rules

| Code | Severity | Rule |
|---|---|---|
| `room.invalid` | error | `^[a-zA-Z0-9\-]+$` |
| `hostname.invalid` | error | `^[a-zA-Z0-9\-]+$` |
| `hostname.all_digits` | error | A name may not consist only of digits |
| `hostname.leading_character` | error | Must start with a letter or a digit |
| `hostname.trailing_hyphen` | error | Must not end with a hyphen |
| `hostname.too_long` | error | `<school>-<hostname>` over 15 characters, for the roles whose `COMPUTER_ACCOUNT` is `TRUE` in `sophomorix.ini` |
| `hostname.duplicate` | error | Same name twice, globally, compared on the prefixed name ignoring case |
| `group.invalid` | error | LINBO group name: `^[a-z0-9_\-]+$`, case-insensitive (no `.` nor `+`, refused by sophomorix and LINBO) |
| `mac.invalid` | error | None of the three accepted forms (`AA:BB:…`, `AA-BB-…`, `AABB…`) |
| `mac.duplicate` | error | Same address twice, globally, compared normalized |
| `ip.invalid` | error | Not an IPv4 address, `DHCP` excepted |
| `ip.duplicate` | error | Same address twice **within one school** |
| `ip.duplicate_across_schools` | warning | Same address in two schools — a fileserver legitimately carries the same one in each |
| `pxe.invalid` | error | Not a digit, `ml`, or empty |
| `role.unknown` | error | Not a `computerrole.*` of `sophomorix.ini`; an empty field means `COMPUTERROLE_DEFAULT` |

The naming rules come from the [AD naming conventions](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/naming-conventions-for-computer-domain-site-ou), not from what sophomorix, this library or the web ui happen to implement. Upper case is **accepted and never rewritten**: sophomorix lower cases the DNS node and upper cases the machine account out of the same field, which is why uniqueness is compared on the folded form.

The `dhcpOptions` field is **not checked**: sophomorix ignores it, but `linuxmuster-import-devices` writes it into the DHCP configuration as is.

### Validating a single value

Every rule is a function taking one value and returning a `list[Finding]`, so that code writing a single attribute into the AD checks exactly what the inventory check checks:

```python
>>> from linuxmusterTools.devices.validator import validate_hostname
>>> validate_hostname('pc0123456789', role='staffcomputer', school='school2')
[Finding(severity='error', code='hostname.too_long', ...)]
>>> validate_hostname('pc01', role='staffcomputer', school='school2')
[]
```

| Function | Parameters |
|---|---|
| `validate_room(room)` | |
| `validate_hostname(hostname, role='', school='default-school', roles=None)` | `role` decides whether the length limit applies, `school` gives the prefix |
| `validate_group(group)` | |
| `validate_mac(mac)` | Any of the three accepted forms |
| `validate_ip(ip)` | |
| `validate_pxe_flag(pxe_flag)` | |
| `validate_role(role, roles=None)` | |
| `validate_device(device, school, file, line, roles=None)` | Every rule above, on one row of `devices.csv` |

A `Finding` is a dataclass; `as_dict()` gives the form listed above.

### Validating a whole inventory

`InventoryValidator(inventories, roles=None).validate()` returns the result `dict` described above. `inventories` is a list of `{'school', 'file', 'devices'}`, and passing several of them at once is what makes the cross-school rules work — a host name or a mac address used in two schools cannot be seen from one of them alone. This is what `check_conf()` and `check_all_schools()` call.

```python
>>> from linuxmusterTools.devices.validator import InventoryValidator
>>> InventoryValidator([{'school': 'school2', 'file': path, 'devices': rows}]).validate()
```

### Where the roles come from

`roles` is a `ComputerRoles`, the `SophomorixIni.computer_roles` attribute (see the `lmnconfig` README). Left out, it is read from the installed file at call time. Pass one to pin what the rules read:

```python
>>> from linuxmusterTools.lmnconfig import ComputerRoles
>>> roles = ComputerRoles(accounts=('staffcomputer',), default='staffcomputer')
>>> validate_role('printer', roles=roles)
[Finding(severity='error', code='role.unknown', ...)]
```
