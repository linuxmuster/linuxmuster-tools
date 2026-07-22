# linuxmusterTools

Shared Python library used by the linuxmuster.net webui, API and CLI: LDAP access, configuration file handling, Samba/AD integration, LINBO image management and more.

Each submodule has its own README with usage details:

| Module | Role |
|---|---|
| [`ldapconnector`](ldapconnector/README.md) | URL-based LDAP client — read-only queries and a high-level object API for writing |
| [`lmnfile`](lmnfile/README.md) | Unified file handler for YAML, CSV, INI/conf and LINBO files |
| [`lmnconfig`](lmnconfig/README.md) | System configuration loaded at import time (Samba, server, setup, sophomorix, webui) |
| [`samba_util`](samba_util/README.md) | Samba AD backend: password policy, GPOs/drives, DNS, groups/users/devices, `smbstatus` |
| [`linbo`](linbo/README.md) | LINBO image manager: images, backups, hardware inventories, Windows driver profiles |
| [`devices`](devices/README.md) | Device inventory and online/OS detection |
| [`quotas`](quotas/README.md) | Disk usage and Samba share quotas for users |
| [`passwords`](passwords/README.md) | Password constraint policy resolution (config + Samba AD floor) |
| [`print`](print/README.md) | PDF generation (password lists, schoolclass lists) |
| [`smbclient`](smbclient/README.md) | Thin wrapper around the `smbclient` CLI |
| [`common`](common/README.md) | Shared utilities: archiving, checks, shell colors, log parsers |
| [`subnets`](subnets/README.md) | Reads and validates `/etc/linuxmuster/subnets.csv` |
| [`install-scripts`](install-scripts/README.md) | Standalone maintenance scripts and sophomorix hooks, not an importable package |

Please refer to each module's README for more details.
