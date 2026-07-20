# Linbo image manager

This module provides an object to manage all linbo images, backups and extra files (rename, delete, ... ).
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

## Hardware inventories

`LinboHardwareInventoryManager` reads the `*_hwinfo.gz` files uploaded by
LINBO clients from `/var/log/linuxmuster/linbo`. Its `list()` and `get()`
methods combine DMI vendor and product information with the school-scoped
client records provided by `Devices`.

The manager is read-only. It does not create driver profiles or modify LINBO
images and can therefore be used independently by API and CLI consumers.

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

### Read-only image assignments

`LinboImageManager` can read an optional `image.conf` from a driver profile:

```ini
[image]
name = win11
```

```python
from linuxmusterTools.linbo import LinboDriverManager, LinboImageManager

drivers = LinboDriverManager()
images = LinboImageManager(driver_manager=drivers)
images.get_driver_profile_image("lenovo-21l4")
```

The former standalone package's flat `image = win11` form remains readable for
upgrades. This interface is deliberately read-only: assigning profiles and
generating `.driverpostsync` files follow in a separate change.
