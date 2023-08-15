# Samba tool

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
