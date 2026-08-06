# linbo

Manages [LINBO](https://www.linuxmuster.net) images, backups, hardware inventories and Windows driver profiles on a linuxmuster.net server.

---

## Requirements

- Python 3.8+
- [`configobj`](https://pypi.org/project/configobj/) (via `linuxmusterTools.lmnfile`, used to read/write `match.conf`/`image.conf`)
- A LINBO server layout: `/srv/linbo/images`, `/srv/linbo/drivers`, `/var/log/linuxmuster/linbo`

---

## Image manager

`LinboImageManager` provides an object to manage all linbo images, backups and extra files (rename, delete, ... ).
The manager contains a dict of all groups in the attributes `groups`. Each group is a `LinboImageGroup` which lists all files, backups contained in the directory. You can get a dict of this description with the method `to_dict()` like bellow:

```Console
>>> from linuxmusterTools.linbo import LinboImageManager
>>> lim = LinboImageManager()
>>> lim.groups
{'ubuntu': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b6443a0>, 'focal': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b645f00>, 'test-linbo42': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b25f7f0>, 'data': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b25f7c0>}
>>> lim.rename('test-linbo42', 'test-linbo101')
>>> lim.groups
{'ubuntu': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b6443a0>, 'focal': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b645f00>, 'data': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b25f7c0>, 'test-linbo101': <linuxmusterTools.linbo.images.LinboImageGroup object at 0x7f579b61a500>}
>>> lim.groups['ubuntu'].to_dict()
{'name': 'ubuntu', 'size': 2609718272, 'desc': 'Install LaTeX and update', 'info': '["ubuntu.qcow2" Info File]\ntimestamp="202108291639"\nimage="ubuntu.qcow2"\nimagesize="2609718272"\npartition="/dev/sda1"\npartitionsize="31457280"\n', 'reg': None, 'postsync': None, 'vdi': None, 'prestart': '#! /bin/bash\n\necho "ok"\n', 'backup': False, 'diff': False, 'timestamp': '202108291639', 'date': '29/08/2021 16:39', 'diff_image': {}, 'backups': {'03/03/2022 19:03': {'name': 'ubuntu', 'size': 0, 'desc': '', 'info': 'timestamp=202203031903\ndate=voila', 'reg': None, 'postsync': None, 'vdi': None, 'prestart': None, 'backup': True, 'diff': False, 'timestamp': '202203031903', 'date': '03/03/2022 19:03'}, '29/08/2021 16:22': {'name': 'ubuntu', 'size': 3233778176, 'desc': 'Install ZSH', 'info': '[ubuntu.qcow2 Info File]\ntimestamp=202108291622\nimage=ubuntu.qcow2\nbaseimage=/dev/sda1\npartitionsize=31457159\nimagesize=3233778176\n', 'reg': None, 'postsync': None, 'vdi': None, 'prestart': '#! /bin/bash\n\necho "ok"\n', 'backup': True, 'diff': False, 'timestamp': '202108291622', 'date': '29/08/2021 16:22'}, '29/08/2021 16:17': {'name': 'ubuntu', 'size': 3233778176, 'desc': 'Install ZSH', 'info': '[ubuntu.qcow2 Info File]\ntimestamp=202108291617\nimage=ubuntu.qcow2\nbaseimage=/dev/sda1\npartitionsize=31457159\nimagesize=3233778176\n', 'reg': None, 'postsync': None, 'vdi': None, 'prestart': '#! /bin/bash\n\necho "ok"\n', 'backup': True, 'diff': False, 'timestamp': '202108291617', 'date': '29/08/2021 16:17'}}, 'selected': False}
```

`delete()`, `duplicate()` and `restore()` raise rather than fail silently:
a directory that cannot be removed propagates the underlying `OSError`, and
`duplicate()`/`restore()` raise `ImageExistsError` (a `FileExistsError`
subclass, importable from `linuxmusterTools.linbo`) if the target image or
backup directory already exists.

---

## Hardware inventories

`LinboHardwareInventoryManager` reads the `*_hwinfo.gz` files uploaded by
LINBO clients from `/var/log/linuxmuster/linbo`. Its `list()` and `get()`
methods combine DMI vendor and product information with the school-scoped
client records provided by `Devices`.

The manager is read-only. It does not create driver profiles or modify LINBO
images and can therefore be used independently by API and CLI consumers.

---

## Windows driver profiles

`LinboDriverManager` manages the metadata for hardware-specific Windows
driver profiles below `/srv/linbo/drivers`. This first, deliberately small
interface owns only profile directories and their `match.conf`; inventory,
image assignments, postsync generation and driver imports are separate
features.

Each profile contains exactly one DMI vendor and one product substring:

```ini
[match]
vendor = LENOVO
product = 21L4
```

The values use the same case-sensitive semantics as LINBO: the vendor must
match exactly and `product` must occur in the client's DMI product name. An
explicit `*` can be used as a wildcard. A short product such as `21L4` can
therefore cover multiple variants of the same hardware class.

```python
from linuxmusterTools.linbo import LinboDriverManager

drivers = LinboDriverManager()
drivers.create_profile("lenovo-21l4", "LENOVO", "21L4")
drivers.update_match("lenovo-21l4", "LENOVO", "21L4S")
```

This creates `/srv/linbo/drivers/lenovo-21l4/match.conf`. Administrators may
place an already prepared INF driver payload next to that file. Profile
updates change only `match.conf` and leave those payload files untouched. This
manager does not upload, extract, inspect or publish the payload yet.

### Image assignments

Each `LinboImageGroup` delegates its optional `image.conf` assignments and
`.driverpostsync` dispatcher to a bound `WindowsDrivers` object.
`LinboDriverManager` continues to own the image-independent profile
directories and `match.conf`. Both metadata files remain physically stored
with the profile; only their logical ownership differs:

```text
/srv/linbo/drivers/<profile>/match.conf
/srv/linbo/drivers/<profile>/image.conf
/srv/linbo/images/<image>/<image>.driverpostsync
```

```ini
[image]
name = win11
```

```python
from linuxmusterTools.linbo import LinboDriverManager, LinboImageManager

drivers = LinboDriverManager()
images = LinboImageManager(driver_manager=drivers)
images.assign_driver_profile("lenovo-21l4", "win11")
images.get_driver_profile_image("lenovo-21l4")
images.get_image_driver_profiles("win11")
dispatcher = images.render_driverpostsync("win11")
images.unassign_driver_profile("lenovo-21l4")
```

These public manager methods resolve the named `LinboImageGroup` and delegate
the image-specific work to its bound `WindowsDrivers` object.

The former standalone package's flat `image = win11` form remains readable for
upgrades and is rewritten in the canonical form by the next assignment.
Assigned profile names can be resolved in deterministic order. The
renderer returns the small `.driverpostsync` dispatcher expected by LINBO's
static `linbo_driverpostsync` runtime. The publisher atomically writes that
dispatcher into the image directory with LINBO's standard postsync mode. It
refuses to replace symlinks, non-regular files or hooks without its exact
managed header. The exact standalone v1.1.1 generator markers remain accepted
for an in-place migration. Assigning, moving or removing a profile publishes
all affected dispatchers under the same mutation lock. If publication fails,
the previous assignment is restored and the affected dispatchers are
regenerated to match it.
`publish_driverpostsync()` remains available as an explicit repair operation.
Assigned profiles must be unassigned before their profile directory can be
deleted, preventing a dispatcher from retaining a stale profile name.
