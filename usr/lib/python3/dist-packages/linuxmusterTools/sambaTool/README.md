# Samba tool

This module should later get some useful informations on a linuxmuster.net server.
Actually, it only gives the GPOs in use, as a dict:

```Console
>>> from linuxmusterTools.sambaTool import GPOS
>>> GPOS
{'Default Domain Controllers Policy': {'dn': 'CN={6A1786C-016F-11D2-945F-00C04FB984F9},CN=Policies,CN=System,DC=linuxmuster,DC=lan', 'path': '\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{6AC1786C-016F-11D2-945F-00C04FB984F9}', 'gpo': '{6AC1786C-016F-11D2-945F-00C04FB984F9}'}, 'Default Domain Policy': {'dn': 'CN={31B2F340-016D-11D2-945F-00C04FB984F9},CN=Policies,CN=System,DC=linuxmuster,DC=lan', 'path': '\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{31B2F340-016D-11D2-945F-00C04FB984F9}', 'gpo': '{31B2F340-016D-11D2-945F-00C04FB984F9}'}, 'sophomorix:school:default-school': {'dn': 'CN={D8D248A8-A5BA-4209-882D-E15969E3B856},CN=Policies,CN=System,DC=linuxmuster,DC=lan', 'path': '\\\\linuxmuster.lan\\sysvol\\linuxmuster.lan\\Policies\\{D8D248A8-A5BA-4209-882D-E15969E3B856}', 'gpo': '{D8D248A8-A5BA-4209-882D-E15969E3B856}'}}
```
