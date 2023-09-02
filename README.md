<h1 align="center">
    Linuxmuster-tools7
</h1>

<p align="center">
    <a href="https://raw.githubusercontent.com/ajenti/ajenti/master/LICENSE">
        <img src="https://img.shields.io/badge/Python-v3-green" alt="Badge License" />
    </a>
    <a href="https://raw.githubusercontent.com/ajenti/ajenti/master/LICENSE"> 
        <img src="https://img.shields.io/github/license/linuxmuster/linuxmuster-tools?label=License" alt="Badge License" />
    </a>
    <a href="https://ask.linuxmuster.net">
        <img src="https://img.shields.io/discourse/users?logo=discourse&logoColor=white&server=https%3A%2F%2Fask.linuxmuster.net" alt="Community Forum"/>
    </a>
</p>

## Features

This module groups some useful modules used in the linuxmuster.net's Webui:

  * `ldapconnector` : make some basics requests to the ldap server
  * `sambaTool` : get informations from the samba backend, actually only the GPOs
  * `lmnfile` : parse the common configurations file used on linuxmuster.net's server a provide an unique interface to handle yaml, csv and conf files.
  * `linbo` : manager for all linbo images, backups, differential images and files.

## Maintenance Details

Linuxmuster.net official | ✅  YES
:---: | :---: 
[Community support](https://ask.linuxmuster.net) | ✅  YES*
Actively developed | ✅  YES
Maintainer organisation |  Linuxmuster.net
Primary maintainer | arnaud@linuxmuster.net
    
\* The linuxmuster community consits of people who are nice and happy to help. They are not directly involved in the development though, and might not be able to help in all cases.

## Installation

### 1. Import key:

```bash
wget -qO- "https://deb.linuxmuster.net/pub.gpg" | gpg --dearmour -o /usr/share/keyrings/linuxmuster.net.gpg
```

### 2. Add repo:

##### Linuxmuster 7.2 ( testing )

```bash
sudo sh -c 'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/linuxmuster.net.gpg] https://deb.linuxmuster.net/ lmn72 main" > /etc/apt/sources.list.d/lmn72.list'
```

### 3. Apt update

```bash
sudo apt update && sudo apt install linuxmuster-tools7
```

## LDAPConnector

LdapConnector is a simple way to get data from the ldap tree in the linuxmsuter.net's project, used in the Webui to accelerate some response time.

### Examples

#### Filter atributes in a response

Just import the LdapReader obejct to start send requests.
By default, a request will ship all attributes specified in the models, but you can filter it with the parameter list `attributes`:

```Console
>>> from linuxmusterTools.ldapconnector import LMNLdapReader as lr
>>> # Getting all schoolclasses
>>> lr.get('/schoolclasses', attributes=['cn'])
[{'cn': '8b'}, {'cn': '8d'}, {'cn': '12b'}, {'cn': '10b migrated'}, {'cn': '10atest'}, {'cn': '5a'}, ...]
>>> # Searching student with 'bla' in cn
>>> lr.get('/users/search/student/bla', attributes=['cn', 'homeDirectory'])
[{'cn': 'bla2', 'homeDirectory': '\\\\lmn\\default-school\\students\\15z\\bla2'}, {'cn': 'bla', 'homeDirectory': '\\\\lmn\\default-school\\students\\attic\\bla'}, {'cn': 'bla1', 'homeDirectory': '\\\\lmn\\default-school\\students\\15z\\bla1'}, {'cn': 'blatrule', 'homeDirectory': '\\\\lmn\\default-school\\students\\10a\\blatrule'}, {'cn': 'mablat', 'homeDirectory': '\\\\lmn\\default-school\\students\\blabla\\mablat'}]
```

#### Sorting

When getting many objects, you can use the parameter `sortkey`:

```Console
>>> lr.get('/schoolclasses', attributes=['cn'], sortkey='cn')
[{'cn': '5a'}, {'cn': '8b'}, {'cn': '8d'}, {'cn': '10atest'}, {'cn': '10b migrated'}, {'cn': '12b'}, ...]
```

#### Output type

If a response contains many items, you get a list of dict, but with the boolean parameter `dict`, you can switch to a dataclass object:

```Console
>>> lr.get('/schools', dict=False)
[LMNSchool(ou='default-school', distinguishedName='OU=default-school,OU=SCHOOLS,DC=linuxmuster,DC=lan')]
```

The object models are all defined in the models subdirectory.

### Available requests

At this point, the following requests are available:

  * `/devices` : get all devices
  * `/devices/NAME` : get all informations about the device `NAME` ( as `cn` )
  * `/devices/search/SELECTION/QUERY` : get all devices matching the `SELECTION` and `QUERY` criterias. `SELECTION` is role-based and can be set to `all` or a specific role like `printer`. `QUERY` is string which should be contained in the `cn`.
  * `/projects` : get all projects
  * `/projects/PROJECT` : get all informations about a single project named `PROJECT`
  * `/roles/ROLE` : get all users in a specific `ROLE` ( `ROLE` can be e.g. `teacher`, `globaladministrator`, ... ) 
  * `/schoolclasses` : get all schoolclasses
  * `/schoolclasses/SCHOOLCLASS` : get all informations about a single schoolclass named `SCHOOLCLASS`
  * `/schoolclasses/SCHOOLCLASS/students` : get all students informations about a single schoolclass named `SCHOOLCLASS`
  * `/schoolclasses/search/QUERY` : if `QUERY` is e.g. 10, search all schoolclasses whose names contain 10
  * `/schools` : get a collection of all schools in a multischool environment, models.LMNSchool, subdn='OU=SCHOOLS,')
  * `/users` : get all users
  * `/users/USERNAME` : get all informations about the user `USERNAME` ( as `cn` )
  * `/users/search/SELECTION/QUERY` : get all users matching the `SELECTION` and `QUERY` criterias. `SELECTION` is role-based and can be set to `all`, `admins` or a specific role like `student`. `QUERY` is string which should be contained in the `cn`.

## LMNFile

`LMNFile` is a common interface to open, parse and write some common confgurations files on a linuxmuster.net's server.

It's possible to open:
  * `yaml` files, like the configuration file of the Webui
  * Linbo's `start.conf` files
  * `csv` files, like e.g. the teachers' list. For these common `csv` files, the fieldnames are automatically set
  * the common Linbo files: .desc, .reg, .postsync, .info, .macct, .prestart (those are not parsed)
  * .ini and .conf files.

`LMNFile` can be used in `with` statements, supporting read/write modes, in plaintext or binary.

### Examples

#### Linbo start.conf file

```Console
>>> from linuxmusterTools.lmnfile import LMNFile
>>> with LMNFile('/srv/linbo/start.conf.101', 'r') as f:
...     data = f.data
... 
>>> data
{'config': {'LINBO': {'SystemType': 'efi64', 'KernelOptions': 'irqpoll dhcpretry=25 forcegrub', 'Cache': '/dev/sda4', 'Server': '10.0.0.1', 'Group': '101', 'RootTimeout': '600', 'Autopartition': False, 'AutoFormat': False, 'AutoInitCache': False, 'DownloadType': 'torrent', 'BackgroundFontColor': 'white', 'ConsoleFontColorStdout': 'white', 'ConsoleFontColorStderr': 'red'}}, 'partitions': [{'Dev': '/dev/sda1', 'Label': 'efi', 'Size': '200M', 'Id': 'ef', 'FSType': 'vfat', 'Bootable': True}, {'Dev': '/dev/sda2', 'Label': 'ubuntu', 'Size': '35G', 'Id': '83', 'FSType': 'ext4', 'Bootable': True}, {'Dev': '/dev/sda3', 'Label': 'data', 'Size': '35G', 'Id': '83', 'FSType': 'ext4', 'Bootable': False}, {'Dev': '/dev/sda4', 'Label': 'cache', 'Size': '', 'Id': '83', 'FSType': 'ext4', 'Bootable': False}], 'os': [{'Name': 'Ubuntu Mate', 'Version': 'Focal', 'Description': 'Ubuntu Mate', 'IconName': 'ubuntu.png', 'Image': '', 'BaseImage': 'focal.qcow2', 'Boot': '/dev/sda2', 'Root': '/dev/sda2', 'Kernel': '/boot/vmlinuz', 'Initrd': '/boot/initrd.img', 'Append': 'ro splash', 'StartEnabled': True, 'SyncEnabled': True, 'NewEnabled': True, 'Hidden': True, 'Autostart': False, 'AutostartTimeout': '15', 'DefaultAction': 'start'}, {'Name': 'Data', 'Version': '', 'Description': 'Data', 'IconName': 'ubuntu.png', 'Image': '', 'BaseImage': 'data.qcow2', 'Boot': '/dev/sda3', 'Root': '/dev/sda3', 'Kernel': 'vmlinuz', 'Initrd': 'initrd.img', 'Append': 'ro splash', 'StartEnabled': False, 'SyncEnabled': True, 'NewEnabled': False, 'Hidden': True, 'Autostart': False, 'AutostartTimeout': '15', 'DefaultAction': 'sync'}]}
```

#### devices.csv

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

#### holidays.yml

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


## Samba tool

This module should later get some useful informations on a linuxmuster.net server.
Actually, it only gives the GPOs in use, as a dataclass object:

```Console
>>> from linuxmusterTools.sambaTool import GPOManager
>>> mgr = GPOManager()
>>> mgr.gpos
{'Default Domain Controllers Policy': GPO(dn='CN={6AC1786C-016F-11D2-945F-00C04FB984F9},CN=Policies,CN=System,DC=linuxmuster,DC=lan', gpo='{6AC1786C-016F-11D2-945F-00C04FB984F9}', name='Default Domain Controllers Policy', path='\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{6AC1786C-016F-11D2-945F-00C04FB984F9}', unix_path='/var/lib/samba/sysvol/linuxmuster.lan/Policies/{6AC1786C-016F-11D2-945F-00C04FB984F9}'), 'Default Domain Policy': GPO(dn='CN={31B2F340-016D-11D2-945F-00C04FB984F9},CN=Policies,CN=System,DC=linuxmuster,DC=lan', gpo='{31B2F340-016D-11D2-945F-00C04FB984F9}', name='Default Domain Policy', path='\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{31B2F340-016D-11D2-945F-00C04FB984F9}', unix_path='/var/lib/samba/sysvol/linuxmuster.lan/Policies/{31B2F340-016D-11D2-945F-00C04FB984F9}'), 'sophomorix:school:default-school': GPO(dn='CN={D8D248A8-A5BA-4209-882D-E15969E3B856},CN=Policies,CN=System,DC=linuxmuster,DC=lan', gpo='{D8D248A8-A5BA-4209-882D-E15969E3B856}', name='sophomorix:school:default-school', path='\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{D8D248A8-A5BA-4209-882D-E15969E3B856}', unix_path='/var/lib/samba/sysvol/linuxmuster.lan/Policies/{D8D248A8-A5BA-4209-882D-E15969E3B856}')}
>>> mgr.gpos['sophomorix:school:default-school'].unix_path
'/var/lib/samba/sysvol/linuxmuster.lan/Policies/{D8D248A8-A5BA-4209-882D-E15969E3B856}'
```
