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
