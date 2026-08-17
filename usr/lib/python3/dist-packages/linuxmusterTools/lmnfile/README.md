# lmnfile

A unified Python file handler for all configuration file formats used in [linuxmuster.net](https://www.linuxmuster.net).

`lmnfile` provides a single entry point — `LMNFile` — that automatically selects the right parser based on the file extension. All handlers implement the context manager protocol and share a common backup mechanism.

---

## Supported formats

| Extension(s) | Handler | Description |
|---|---|---|
| `.yml`, `.vdi` | `YAMLLoader` | YAML configuration files |
| `.csv` | `CSVLoader` | Semicolon-delimited CSV files (sophomorix-compatible) |
| `.ini`, `.conf` | `ConfigLoader` | INI-style configuration files |
| `start.conf` | `StartConfLoader` | Linbo start configuration files |
| `.desc`, `.reg`, `.postsync`, `.info`, `.macct`, `.prestart` | `LinboLoader` | Linbo image metadata files (plain text) |

---

## Requirements

- Python 3.8+
- [`python-magic`](https://pypi.org/project/python-magic/)
- [`PyYAML`](https://pypi.org/project/PyYAML/)
- [`configobj`](https://pypi.org/project/configobj/)

---

## Usage

All handlers are accessed through the same `LMNFile` factory class, used as a context manager.

```python
from linuxmusterTools.lmnfile import LMNFile

with LMNFile('/path/to/file.yml', 'r') as f:
    data = f.read()
```

### Parameters

```python
LMNFile(file, mode, delimiter=';', fieldnames=None, convert_values=True)
```

| Parameter | Type | Description |
|---|---|---|
| `file` | `str` | Absolute path to the file |
| `mode` | `str` | Open mode: `'r'` (read), `'w'` (write), `'r+'` (read+write) |
| `delimiter` | `str` | Delimiter for CSV files (default: `';'`) |
| `fieldnames` | `list[str]` | Column names for CSV files without a header row |
| `convert_values` | `bool` | Convert INI/conf values to Python types (default: `True`) |

---

## Examples

### YAML

```python
with LMNFile('/etc/linuxmuster/api/config.yml', 'r') as f:
    config = f.read()
    # config is a dict

with LMNFile('/etc/linuxmuster/api/config.yml', 'r') as f:
    data = f.read()
    data['key'] = 'value'
    f.write(data)
```

> When running as root, `YAMLLoader` automatically creates the file if it does not exist and sets permissions to `0o600`.

### CSV

```python
with LMNFile('/etc/linuxmuster/sophomorix/default-school/devices.csv', 'r') as f:
    rows = f.read()
    # rows is a list of dicts, one per line

with LMNFile('/etc/linuxmuster/sophomorix/default-school/devices.csv', 'r') as f:
    rows = f.read()
    rows[0]['room'] = 'server'
    f.write(rows)
```

Field names for standard linuxmuster CSV files (`devices`, `students`, `teachers`, `staff`, `parents`, `extrastudents`, `extraclasses`, `subnets`) are detected automatically from the filename.

For other CSV files, pass `fieldnames` explicitly:

```python
with LMNFile('/path/to/custom.csv', 'r', fieldnames=['col1', 'col2']) as f:
    rows = f.read()
```

#### CSV special features

- **BOM**: UTF-8 BOM is detected and removed automatically for sophomorix compatibility.
- **Inline header**: A CSV file can declare its own field names with a special marker line:
  ```
  #HEADERS#col1;col2;col3
  ```
- **Empty lines and comments**: Lines starting with `#` and empty lines are preserved on write.

### INI / Config

```python
with LMNFile('/var/lib/linuxmuster/setup.ini', 'r') as f:
    config = f.read()
    # config is a nested dict: config[section][key]
    print(config['setup']['schoolname'])

with LMNFile('/var/lib/linuxmuster/setup.ini', 'r') as f:
    config = f.read()
    config['setup']['schoolname'] = 'My School'
    f.write(config)
```

String values are automatically converted on read:
- `'yes'` → `True`
- `'no'` → `False`
- Digit strings → `int`

And converted back on write.

Pass `convert_values=False` to preserve values such as `0012`, `yes` and `no`
as strings when reading and writing.

New INI/conf files created in write mode use permissions `0o600`. Replacing an
existing file preserves its owner, group and permissions. Configuration
symlinks stay intact while their resolved targets are updated atomically.

### Linbo start.conf

```python
with LMNFile('/srv/linbo/start.conf', 'r') as f:
    data = f.read()
    # data = {
    #   'config': {'LINBO': {...}, 'GUI': {...}, ...},
    #   'partitions': [{...}, ...],
    #   'os': [{...}, ...]
    # }

with LMNFile('/srv/linbo/start.conf', 'r') as f:
    data = f.read()
    data['config']['LINBO']['Server'] = '10.0.0.1'
    f.write(data)

with LMNFile('/srv/linbo/start.conf.newgroup', 'w') as f:
    f.write({'config': {'LINBO': {'Server': '10.0.0.1'}}, 'partitions': [], 'os': []})
```

> Opening a non-existent `start.conf.*` in `'w'` mode creates a new group file instead of raising `FileNotFoundError`.

### Linbo metadata files

```python
with LMNFile('/srv/linbo/ubuntu.desc', 'r') as f:
    content = f.read()     # returns the raw file object
    text = content.read()
```

---

## Security

Access is restricted to a whitelist of allowed paths:

```
/etc/linuxmuster/api/config.yml
/etc/linuxmuster/webui/config.yml
/etc/linuxmuster/sophomorix/
/srv/linbo
/etc/linuxmuster/subnets.csv
/etc/linuxmuster/holidays.yml
/var/lib/linuxmuster/setup.ini
/tmp/setup.ini
/usr/lib/linuxmuster-webui/plugins
```

Any path outside this list, or containing `..`, raises `IOError: Access refused.`

---

## Backup

Before overwriting a file, `lmnfile` automatically creates a timestamped backup:

```
/path/to/.filename.bak.<unix_timestamp>
```

- Only the **10 most recent** backups are kept; older ones are deleted automatically.
- Backup files inherit the **permissions** of the original file.
- No backup is created if the file content has not changed.

---

## Predefined CSV field names

The following CSV filenames are recognised automatically (matched against `/etc/linuxmuster/`):

| Filename | Fields |
|---|---|
| `devices.csv` | `room`, `hostname`, `group`, `mac`, `ip`, `officeKey`, `windowsKey`, `dhcpOptions`, `sophomorixRole`, `lmnReserved10`, `pxeFlag`, `lmnReserved12–14`, `sophomorixComment`, `options` |
| `students.csv` | `class`, `last_name`, `first_name`, `birthday`, `id` |
| `teachers.csv` | `class`, `last_name`, `first_name`, `birthday`, `login`, `password`, `usertoken`, `quota`, `mailquota`, `reserved`, `extra01`–`extra20` |
| `staff.csv` | `class`, `last_name`, `first_name`, `birthday`, `id` |
| `parents.csv` | `class`, `last_name`, `first_name`, `birthday`, `id`, `students_ref` |
| `extrastudents.csv` | `class`, `last_name`, `first_name`, `birthday`, `login`, `reserved` |
| `extraclasses.csv` | `course`, `base_name`, `count`, `birthday`, `gecos`, `password`, `removal_date` |
| `subnets.csv` | `network`, `routerIp`, `beginRange`, `endRange`, `nameServer`, `nextServer`, `setupFlag` |

---

## File encoding

The encoding of each file is detected automatically using `libmagic`. ASCII and binary files are treated as UTF-8. If the file does not yet exist, UTF-8 is assumed.
