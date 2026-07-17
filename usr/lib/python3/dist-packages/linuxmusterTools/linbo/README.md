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

## Windows driver profiles

`LinboDriverManager` manages hardware-specific Windows driver payloads below
`/srv/linbo/drivers`. A profile contains its payload and a `match.conf` with
one DMI vendor and at least one product. Use `product = *` only when a profile
is intentionally valid for every product of that vendor.

```python
from linuxmusterTools.linbo import LinboDriverManager

drivers = LinboDriverManager()
drivers.create_profile(
    "lenovo-l14-gen5",
    "LENOVO",
    ["21L4S00P00", "21L4S01A00"],
)
# Place the extracted payload below /srv/linbo/drivers/lenovo-l14-gen5/.
drivers.set_profile_image("lenovo-l14-gen5", "windows-11")
```

`create_profile` writes the manager-owned `match.conf`; image assignments add
`image.conf`. It deliberately does not upload or extract archives. Place
already extracted driver payloads below
`/srv/linbo/drivers/<profile>/` before assigning the profile, without replacing
these metadata files. Archive ingestion belongs in the API or WebUI layer.

Several profiles may reference the same image. The generated
`<image>.driverpostsync` selects matching profiles from the client's DMI data,
copies only their payloads and stages them for the persistent Windows startup
task. Profile metadata and hooks are written atomically under one shared lock.
Existing companion hooks not owned by this manager are never overwritten.
Images with assigned profiles must be unassigned before they can be renamed or
deleted. Duplicating an image does not duplicate its profile assignments, and
restoring an image backup keeps the hook derived from the current assignments.

Fully automatic installation requires the golden image to contain the
`LINBO-Driver-Install` scheduled task running as `SYSTEM` at startup and its
`C:\ProgramData\LINBO\Drivers\startup-task-ready` marker. That Windows bootstrap
is supplied by the LINBO client integration, not by this server-side manager.
Without it, the generated hook registers an administrative `RunOnce` fallback,
which only runs after an administrator logs on.

LINBO hardware inventories can also be queried by school and used to create a
profile with the detected vendor and product:

```python
drivers.create_profile_from_inventory(
    "client-01",
    school="default-school",
)
```
