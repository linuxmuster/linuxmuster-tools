# devices

Inventory and reachability checks for the devices registered in [linuxmuster.net](https://www.linuxmuster.net) (`devices.csv`).

`devices` exposes two classes: `Devices`, which loads and queries the per-school device inventory, and `UPChecker`, which probes hosts over the network to determine whether they are online and what they are running (LINBO, Linux, Windows).

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

Loads `/etc/linuxmuster/sophomorix/SCHOOL/[SCHOOL.]devices.csv` on instantiation.

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
| `groups` | `list[str]` | Unique LINBO groups found in the inventory |
| `macs` | `list[str]` | Unique normalized MAC addresses |
| `ips` | `list[str]` | Unique IP addresses |
| `rooms` | `list[str]` | Unique room names |
| `clients` | `list[dict]` | Devices whose `sophomorixRole` is a client role (from `sophomorix.ini`) |
| `csv_mtime` | `datetime` | Last modification time of the CSV file (UTC) |

Each device `dict` is enriched on load with:

- `school` — the school it was loaded for
- `mac` — normalized to `AA:BB:CC:DD:EE:FF` uppercase colon form (`None` if invalid)
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
| `check_conf()` | Validate the inventory; returns `False` if valid, else a `list[str]` of error messages |

```python
devicesmgr = Devices()
devicesmgr.filter(roles=['classroom-studentcomputer'], groups=['g-pcs'])
devicesmgr.get_client('pc01')

devicesmgr.switch('school1')          # reload for another school
report = devicesmgr.check_conf()
if report:
    for line in report:
        print(line)
```

`check_conf()` reports invalid IPs, MACs, group/room/hostnames, PXE flags, unknown `sophomorixRole` values, and duplicate IPs/MACs across the inventory.

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
