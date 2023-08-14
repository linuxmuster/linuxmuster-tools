# LMNFile

`LMNFile` is a common interface to open, parse and write some common confgurations files on a linuxmuster.net's server.

It's possible to open:
  * `yaml` files, like the configuration file of the Webui
  * Linbo's `start.conf` files
  * `csv` files, like e.g. the teachers' list. For these common `csv` files, the fieldnames are automatically set
  * the common Linbo files: .desc, .reg, .postsync, .info, .macct, .prestart (those are not parsed)
  * .ini and .conf files.

`LMNFile` can be used in `with` statements, supporting read/write modes, in plaintext or binary.

## Examples

### Linbo start.conf file

```Console
>>> from linuxmusterTools.lmnfile import LMNFile
>>> with LMNFile('/srv/linbo/start.conf.101', 'r') as f:
...     data = f.data
... 
>>> data
{'config': {'LINBO': {'SystemType': 'efi64', 'KernelOptions': 'irqpoll dhcpretry=25 forcegrub', 'Cache': '/dev/sda4', 'Server': '10.0.0.1', 'Group': '101', 'RootTimeout': '600', 'Autopartition': False, 'AutoFormat': False, 'AutoInitCache': False, 'DownloadType': 'torrent', 'BackgroundFontColor': 'white', 'ConsoleFontColorStdout': 'white', 'ConsoleFontColorStderr': 'red'}}, 'partitions': [{'Dev': '/dev/sda1', 'Label': 'efi', 'Size': '200M', 'Id': 'ef', 'FSType': 'vfat', 'Bootable': True}, {'Dev': '/dev/sda2', 'Label': 'ubuntu', 'Size': '35G', 'Id': '83', 'FSType': 'ext4', 'Bootable': True}, {'Dev': '/dev/sda3', 'Label': 'data', 'Size': '35G', 'Id': '83', 'FSType': 'ext4', 'Bootable': False}, {'Dev': '/dev/sda4', 'Label': 'cache', 'Size': '', 'Id': '83', 'FSType': 'ext4', 'Bootable': False}], 'os': [{'Name': 'Ubuntu Mate', 'Version': 'Focal', 'Description': 'Ubuntu Mate', 'IconName': 'ubuntu.png', 'Image': '', 'BaseImage': 'focal.qcow2', 'Boot': '/dev/sda2', 'Root': '/dev/sda2', 'Kernel': '/boot/vmlinuz', 'Initrd': '/boot/initrd.img', 'Append': 'ro splash', 'StartEnabled': True, 'SyncEnabled': True, 'NewEnabled': True, 'Hidden': True, 'Autostart': False, 'AutostartTimeout': '15', 'DefaultAction': 'start'}, {'Name': 'Data', 'Version': '', 'Description': 'Data', 'IconName': 'ubuntu.png', 'Image': '', 'BaseImage': 'data.qcow2', 'Boot': '/dev/sda3', 'Root': '/dev/sda3', 'Kernel': 'vmlinuz', 'Initrd': 'initrd.img', 'Append': 'ro splash', 'StartEnabled': False, 'SyncEnabled': True, 'NewEnabled': False, 'Hidden': True, 'Autostart': False, 'AutostartTimeout': '15', 'DefaultAction': 'sync'}]}
```

### devices.csv

```Console
>>> from linuxmusterTools.lmnfile import LMNFile
>>> with LMNFile('/etc/linuxmuster/sophomorix/default-school/devices.csv', 'r') as f:
...     data = f.data
... 
>>> with LMNFile('/etc/linuxmuster/sophomorix/default-school/devices.csv', 'r') as f:
...     data = f.data
... 
>>> for device in data:
...     if device['room'] == 'pxclient':
...             print(device)
... 
{'room': 'pxclient', 'hostname': 'client2453457', 'group': 'test_linbo43', 'mac': '3a:98:3e:68:9e:c9', 'ip': '10.0.0.108', 'officeKey': '', 'windowsKey': '', 'dhcpOptions': '', 'sophomorixRole': 'staffcomputer', 'lmnReserved10': '', 'pxeFlag': '1', 'lmnReserved12': '', 'lmnReserved13': '', 'lmnReserved14': '', 'sophomorixComment': '', 'options': ''}
{'room': 'pxclient', 'hostname': 'client245345', 'group': 'test_linbo43', 'mac': '3a:97:3e:68:9e:c9', 'ip': '10.0.0.107', 'officeKey': '', 'windowsKey': '', 'dhcpOptions': '', 'sophomorixRole': 'staffcomputer', 'lmnReserved10': '', 'pxeFlag': '1', 'lmnReserved12': '', 'lmnReserved13': '', 'lmnReserved14': '', 'sophomorixComment': '', 'options': ''}
{'room': 'pxclient', 'hostname': 'client3', 'group': 'lz', 'mac': '31:fb:96:33:fd:96', 'ip': '10.0.0.102', 'officeKey': '', 'windowsKey': '', 'dhcpOptions': '', 'sophomorixRole': 'staffcomputer', 'lmnReserved10': '', 'pxeFlag': '1', 'lmnReserved12': '', 'lmnReserved13': '', 'lmnReserved14': '', 'sophomorixComment': '', 'options': ''}
```

### holidays.yml

```Console
>>> from linuxmusterTools.lmnfile import LMNFile
>>> with LMNFile('/etc/linuxmuster/sophomorix/default-school/holidays.yml', 'r') as f:
...     data = f.data
... 
>>> data
{'automn': {'end': '01.11.2021', 'start': '25.10.2021'}, 'hiver': {'end': '04.02.2022', 'start': '31.01.2022'}, 'noël': {'end': '10.01.2022', 'start': '20.12.2021'}, 'pentecôte': {'end': '15.06.2022', 'start': '01.06.2022'}}
>>> data['automn']['start'] = '26.10.2021' # New start date
>>> with LMNFile('/etc/linuxmuster/sophomorix/default-school/holidays.yml', 'w') as f:
...     f.write(data) # Saving to file
```
