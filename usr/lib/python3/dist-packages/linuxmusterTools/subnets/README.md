# subnets

Reads and validates the global subnets definition file for [linuxmuster.net](https://www.linuxmuster.net), and triggers its import into DHCP, NTP and netplan configuration.

`subnets` exposes a single class, `Subnets`, for loading and validating `/etc/linuxmuster/subnets.csv`, plus the `import_subnets()` function that runs `linuxmuster-import-subnets` to apply the file to the system.

---

## Requirements

- Python 3.8+
- `linuxmusterTools.lmnfile` (used internally to read the CSV file)
- `linuxmuster-import-subnets` available on `PATH` (only required to call `import_subnets()`)

---

## Usage

### Import

```python
from linuxmusterTools.subnets import Subnets, import_subnets
```

### `Subnets`

Unlike `devices.csv`, `subnets.csv` is not per-school: there is exactly one file for the whole server.

```python
Subnets(path='/etc/linuxmuster/subnets.csv')
```

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` | Path to the CSV file (default: `/etc/linuxmuster/subnets.csv`) |

Loading the file populates these attributes:

| Attribute | Type | Description |
|---|---|---|
| `subnets` | `list[dict]` | One dict per row (comment and empty lines skipped) |
| `networks` | `list[str]` | Deduplicated list of `network` values |
| `csv_mtime` | `datetime` | UTC modification time of the CSV file |

Each row dict has the following keys, matching the CSV columns:

| Field | Description |
|---|---|
| `network` | Network in CIDR notation (e.g. `10.0.0.0/24`) |
| `routerIp` | Router/gateway IP, must be inside `network` |
| `beginRange` | Start of the DHCP range, must be inside `network` |
| `endRange` | End of the DHCP range, must be inside `network` |
| `nameServer` | Optional DNS server IP |
| `nextServer` | Optional PXE/next-server IP |
| `setupFlag` | `'SETUP'` or empty |

```python
subnets = Subnets()
subnets.subnets    # [{'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', ...}, ...]
subnets.networks   # ['10.0.0.0/24', '10.1.0.0/24']
subnets.csv_mtime  # datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
```

### `filter(networks=[])`

Returns the subnets matching the given list of networks, or all subnets if `networks` is empty.

```python
subnets.filter(networks=['10.0.0.0/24'])
```

### `get_subnet(network)`

Returns the row dict for a single network, or `None` if not found.

```python
subnets.get_subnet('10.0.0.0/24')
# {'network': '10.0.0.0/24', 'routerIp': '10.0.0.1', ...}
```

### `check_conf()`

Validates the loaded content. Returns `False` if everything is valid, otherwise a `list[str]` of human-readable error messages, one per problem found:

- `network` is not a valid CIDR network (or has host bits set)
- `routerIp`, `beginRange`, `endRange` missing, not a valid IP, or outside `network`
- `nameServer`, `nextServer` set but not a valid IP
- `setupFlag` not one of `''` or `'SETUP'`
- a `network` defined more than once

```python
report = subnets.check_conf()
if report:
    for error in report:
        print(error)
```

### `import_subnets()`

Runs `linuxmuster-import-subnets`, which regenerates the DHCP, NTP and netplan configuration from `/etc/linuxmuster/subnets.csv` and restarts the affected services.

```python
result = import_subnets()
# {'returncode': 0, 'output': '...'}
```

| Key | Type | Description |
|---|---|---|
| `returncode` | `int` | Exit code of the command |
| `output` | `str` | Combined stdout/stderr, decoded with `errors='replace'` |
