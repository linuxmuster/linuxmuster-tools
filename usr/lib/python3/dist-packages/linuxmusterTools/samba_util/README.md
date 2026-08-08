# samba_util

Read and write access to the Samba 4 AD backend of a [linuxmuster.net](https://www.linuxmuster.net) server: domain password policy, GPOs and drive maps, DNS zone, group/user/device management, and `smbstatus` connections.

---

## Requirements

- Python 3.8+
- Samba's own `samba` Python bindings (`samba.auth`, `samba.credentials`, `samba.samdb`, `samba.netcmd.gpo`, `ldb`) — only available on a provisioned linuxmuster.net server
- [`pexpect`](https://pypi.org/project/pexpect/) (used by `SambaToolDNS` to drive `samba-tool dns`)
- Read access to `/var/lib/samba/private/sam.ldb` and `/etc/linuxmuster/.secret/administrator` — most classes require root

---

## Domain password policy — `DomainPasswordSettingsManager`

Reads and writes the domain-wide Samba AD password policy (minimum length, complexity, min/max password age) directly via `SamDB`, equivalent to `samba-tool domain passwordsettings show`/`set` without shelling out.

```python
from linuxmusterTools.samba_util import DomainPasswordSettingsManager

mgr = DomainPasswordSettingsManager()
settings = mgr.get()
# DomainPasswordSettings(min_pwd_length=7, complexity=True, min_pwd_age=1, max_pwd_age=43)

mgr.set(min_pwd_length=10, complexity=True)
```

Only the domain-wide policy is read — Fine-Grained Password Policies (PSOs) are not accounted for. See [`passwords/README.md`](../passwords/README.md) for the full writeup of this limitation and how it interacts with `PasswordPolicyProvider`.

---

## GPOs and drive maps — `GPOManager`

```python
from linuxmusterTools.samba_util import GPOManager

mgr = GPOManager()
mgr.gpos
# {'Default Domain Policy': GPO(dn='...', gpo='{31B2F340-...}', name='Default Domain Policy',
#                                path='\\\\linuxmuster.lan\\sysvol\\...', unix_path='/var/lib/samba/sysvol/...',
#                                drivemgr=<DriveManager>), ...}

mgr.gpos['Default Domain Policy'].unix_path
mgr.gpos['Default Domain Policy'].drivemgr.drives
# [Drive(disabled=False, filters={}, label='Programs', letter='K', ...), ...]
```

Each `GPO` bundles a `DriveManager`, which parses that policy's `Drives.xml` into `Drive` dataclass instances.

---

## Group, user and device management

```python
from linuxmusterTools.samba_util import GroupManager, DeviceManager

groups = GroupManager(school='default-school')
groups.list()                              # {sophomorixType: [cn, ...], ...}
groups.add_members('7b', ['jdupont'])
groups.remove_members('7b', ['jdupont'])
```

`GroupManager` runs every script in `/etc/linuxmuster/tools/hooks/group-manager/` after each membership change.

```python
devices = DeviceManager()
creds = devices.get_credentials('client01')       # base64-encoded unicodePwd / supplementalCredentials
devices.set_credentials('client01', hash_pwd_b64, hash_supplemental_b64)
```

User password management (setting `unicodePwd`/`sophomorixFirstPassword`) has moved to `LMNUser` in [`ldapconnector`](../ldapconnector/README.md#password-management) — see `set_actual_password()`/`set_first_password()`/`set_random_first_password()`. `load_samba_bindings()` (this module) is what `LMNUser` calls internally to open its own `SamDB` connection, since `ldapconnector` can't import `samba_util` at module level without creating a cycle.

---

## DNS — `SambaToolDNS`

```python
from linuxmusterTools.samba_util import SambaToolDNS

dns = SambaToolDNS()
dns.list()
# {'root': [{'host': '', 'type': 'SOA', 'value': '...'}, ...],
#  'sub':  [{'host': 'mail', 'type': 'A', 'value': '10.0.0.3'}, ...]}

dns.add({'host': 'test', 'type': 'A', 'value': '10.0.1.1'})
dns.update({'host': 'test', 'type': 'A', 'value': '10.0.1.1'}, {'host': 'test', 'type': 'A', 'value': '10.0.1.2'})
dns.delete('test', 'A', '10.0.1.2')
```

`list()` drives `samba-tool dns query` and filters out entries belonging to known linuxmuster devices (from `devices.csv`), since that list would otherwise be too long to be useful. If `devices.csv` doesn't exist yet (fresh install, school not provisioned yet), the ignore list is simply left empty instead of raising.

---

## SMB connections — `smbstatus`

```python
from linuxmusterTools.samba_util import smbstatus

conn = smbstatus.SMBConnections()
conn.users
# {'kiar': SMBConnection(username='LINUXMUSTER\\kiar', ip4='10.0.0.1:38402', machine='10.0.0.1',
#                         protocol='SMB3_11', signing='AES-128-GMAC', ...)}
conn.get_machines()
conn.machines
```

---

## Authentication logs — `samba_util.log`

Not re-exported from `samba_util/__init__.py`; import it directly from the submodule.

```python
from linuxmusterTools.samba_util import log

log.last_login('jdupont')             # sorted list of {'user', 'datetime', 'ip'}, most recent first
log.last_login('jdupont', include_gz=True)   # also scan rotated, gzipped logs
```

Requires Samba's `auth_audit` (or `general`) log level set to at least `3` in `smb.conf` — `check_audit_level()` returns `False` and logs an error otherwise.
