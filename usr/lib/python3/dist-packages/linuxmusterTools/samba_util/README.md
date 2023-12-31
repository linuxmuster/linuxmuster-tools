# Samba utilities

This module get some useful informations on a linuxmuster.net server.
Actually, it provides: 

- the GPOs in use, as a dataclass object,
- DNS entries,
- drives list,
- smbstatus output,

## Examples of GPOS and drives

```Python
>>> from linuxmusterTools.samba_util import GPOManager
>>> mgr = GPOManager()
>>> mgr.gpos
{'Default Domain Controllers Policy': GPO(dn='CN={6AC1786C-016F-11D2-945F-00C04FB984F9},CN=Policies,CN=System,DC=linuxmuster,DC=lan', gpo='{6AC1786C-016F-11D2-945F-00C04FB984F9}', name='Default Domain Controllers Policy', path='\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{6AC1786C-016F-11D2-945F-00C04FB984F9}', unix_path='/var/lib/samba/sysvol/linuxmuster.lan/Policies/{6AC1786C-016F-11D2-945F-00C04FB984F9}'), 'Default Domain Policy': GPO(dn='CN={31B2F340-016D-11D2-945F-00C04FB984F9},CN=Policies,CN=System,DC=linuxmuster,DC=lan', gpo='{31B2F340-016D-11D2-945F-00C04FB984F9}', name='Default Domain Policy', path='\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{31B2F340-016D-11D2-945F-00C04FB984F9}', unix_path='/var/lib/samba/sysvol/linuxmuster.lan/Policies/{31B2F340-016D-11D2-945F-00C04FB984F9}'), 'sophomorix:school:default-school': GPO(dn='CN={D8D248A8-A5BA-4209-882D-E15969E3B856},CN=Policies,CN=System,DC=linuxmuster,DC=lan', gpo='{D8D248A8-A5BA-4209-882D-E15969E3B856}', name='sophomorix:school:default-school', path='\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{D8D248A8-A5BA-4209-882D-E15969E3B856}', unix_path='/var/lib/samba/sysvol/linuxmuster.lan/Policies/{D8D248A8-A5BA-4209-882D-E15969E3B856}')}
>>> # UNIX PATH OF A GIVEN POLICY
>>> mgr.gpos['sophomorix:school:default-school'].unix_path
'/var/lib/samba/sysvol/linuxmuster.lan/Policies/{D8D248A8-A5BA-4209-882D-E15969E3B856}'
>>> # DRIVES OF A GIVEN POLICY
>>> mgr.gpos['sophomorix:school:default-school'].drivemgr.drives
[Drive(disabled=False, filters={}, label='Programs', letter='K', properties={'useLetter': True, 'letter': 'K', 'label': 'Programs', 'path': '\\\\lmn\\default-school\\program'}, userLetter=True, id='program'), Drive(disabled=False, filters={}, label='Projects', letter='P', properties={'useLetter': True, 'letter': 'P', 'label': 'Projects', 'path': '\\\\lmn\\default-school\\share\\projects'}, userLetter=True, id='projects'), Drive(disabled=False, filters={'teachers': {'bool': 'AND', 'negation': False}}, label='Student-bla', letter='B', properties={'useLetter': True, 'letter': 'B', 'label': 'Student-bla', 'path': '\\\\lmn\\default-school\\students'}, userLetter=True, id='students'), Drive(disabled=False, filters={}, label='Shares', letter='T', properties={'useLetter': True, 'letter': 'T', 'label': 'Shares', 'path': '\\\\lmn\\default-school\\share'}, userLetter=True, id='share'), Drive(disabled=True, filters={}, label='ISO', letter='F', properties={'useLetter': False, 'letter': 'F', 'label': 'ISO', 'path': '\\\\lmn\\default-school\\iso'}, userLetter=False, id='iso')]
```

## Examples of DNS entries

```Python
>>> from linuxmusterTools.samba_util import SambaToolDNS
>>> SambaToolDNS().list()
{'root': [{'host': '', 'type': 'SOA', 'value': 'serial=123, refresh=900, retry=600, expire=86400, minttl=3600, ns=lmn.linuxmuster.lan., email=hostmaster.linuxmuster.lan.', 'flags': '600000f0', 'serial': '123', 'ttl': '3600'}, {'host': '', 'type': 'NS', 'value': 'lmn.linuxmuster.lan.', 'flags': '600000f0', 'serial': '110', 'ttl': '900'}, {'host': '', 'type': 'A', 'value': '10.0.0.1', 'flags': '600000f0', 'serial': '110', 'ttl': '900'}], 'sub': [{'host': 'bla', 'type': 'A', 'value': '8.8.8.9', 'flags': 'f0', 'serial': '100', 'ttl': '900'}, {'host': 'mail', 'type': 'A', 'value': '10.0.0.3', 'flags': 'f0', 'serial': '2', 'ttl': '900'}, {'host': 'test', 'type': 'A', 'value': '10.0.1.1', 'flags': 'f0', 'serial': '54', 'ttl': '900'}, {'host': 'test', 'type': 'A', 'value': '1.1.1.1', 'flags': 'f0', 'serial': '57', 'ttl': '900'}, {'host': 'test2', 'type': 'A', 'value': '1.1.1.1', 'flags': 'f0', 'serial': '122', 'ttl': '900'}]}
```

## Example of SMBStatus

```Python
>>> from linuxmusterTools.samba_util import smbstatus
>>> conn = smbstatus.SMBConnections()
>>> print(conn.users)
{'kiar': SMBConnection(encryption='-', ip=None, ip4='10.0.0.1:38402', ip6=None, group='users', machine='10.0.0.1', pid='2942516', protocol='SMB3_11', signing='AES-128-GMAC', username='LINUXMUSTER\\kiar', version='', hostname='lmn')}
>>> conn.get_machines()
>>> print(conn.machines)
```