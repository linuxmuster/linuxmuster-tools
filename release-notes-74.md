# Release Notes – linuxmuster-tools 7.4

**Package version:** 7.4.1 – 7.4.13

---

## Overview

Version 7.4 has been a major feature and hardening cycle for the shared
library. Three areas dominate: a full LINBO remote-control / host-status /
image-management overhaul, a new password-management and password-constraints
layer, and a long tail of correctness fixes across `ldapconnector`,
`samba_util` and `quotas` — several of them closing bugs reported by early
testers. This work is what the API, the webui and the CLI now build on: most
of the logic that used to be duplicated in those projects has moved here.

---

## LINBO remote control & host status

- New `LinboRemote` (`linbo_sync.py`): builds and runs `linbo-remote` commands
  against a group, a room, or an explicit list of clients (IP or hostname),
  with parameter validation and the target's `nr` checked against its
  `start.conf` before running. Raises `LinboRemoteParameterError` instead of
  silently building a wrong command.
- Session tracking: `list_running_sessions()` / `attach_command()` follow
  `linbo-remote`'s tmux sessions. Fixed a naming bug in the process — tmux
  silently replaces the dot in `<hostname>.linbo-remote` with an underscore,
  so sessions were never actually matched.
- `classify_host()`: synchronous boot-state probe (Off / Linbo / OS Linux /
  OS Windows / OS Unknown) using plain blocking sockets — no `nmap`, no
  `asyncio`, safe to call from the webui's gevent-based code.
- Fixed `format:<nr>` partition numbering: it now uses the partition's
  position in `start.conf`'s `[Partition]` list instead of the digit in its
  device path (the two diverge once partitions aren't defined in device
  order).
- `last_sync_all()`'s return shape aligned with the webui's:
  `host['image']` (list of `{date, status, image}`).
- Image manager: `.hash` files are now recognized as non-editable extras
  (previously left orphaned on delete/rename); new `ImageExistsError` /
  `IncompleteImageInfoError` replace silent `print()`-and-return or crashes;
  fixed a backup-only deletion bug (`self.images[group]` instead of
  `self.groups[group]`).
- LINBO hardware inventory reader, Windows driver profile metadata, image
  driver assignments and dispatcher rendering (@amolani).
- Raw `start.conf` write/delete support.

---

## Password management

- `LMNUser` gained `set_actual_password()` (direct SamDB write, bypassing
  `sophomorix-passwd`/`smbpasswd`), `set_first_password()`,
  `set_random_first_password()` and `test_first_password()`.
- New password-constraints module: policy provider, Samba domain floor
  (minimum length/complexity/age), YAML config.
- Removed the deprecated, buggy `samba_util.UserManager` — password
  management now lives entirely in `LMNUser`.

---

## LDAP / group management hardening

- **Breaking change:** removed the deprecated `LMNMgmtGroup` class, superseded
  by `samba_util.GroupManager`, which reports LDAP errors instead of
  swallowing them.
- `add_members()`/`remove_members()` no longer hide per-member failures — one
  invalid `cn` used to hide the rest of the batch; failures are now collected
  and returned as a list.
- `GroupManager.add_members()` now only swallows the benign "already a
  member" LDAP error (code 68); every other exception used to be dropped
  too. Each post-hook script now runs in its own try/except, logged on
  failure instead of failing the whole call.
- Fixed custom-fields config resolution: role names were looked up singular
  against a YAML keyed plural, only fields 1–4 were read instead of 1–5, and
  the config always loaded `default-school`'s settings regardless of the
  actual user's school (closes #25). A separate `KeyError` on partial
  `custom_fields.yml` entries was fixed too.
- Added `SchoolError` (raised when instantiating a group with
  `school='global'`), fixed `setattr()` silently no-op'ing on an empty value
  (now raises `ValueError`), fixed a lowercase mismatch on group/user
  lookups and a crash on an empty `/ou` lookup result.

---

## Quotas fix (breaking change)

`sophomorixCloudQuotaCalculated` and `sophomorixMailQuotaCalculated` were
typed as `list` instead of `str` in `LMNUserModel`, `LMNRawUserModel` and
`LMNObjectModel` — both are single-valued LDAP attributes
(`isSingleValued: TRUE`). This caused values to render as `["2506 MB"]` once
displayed by the webui. **Any consumer of these two fields now gets a plain
`str`, not a `list`.**

---

## Miscellaneous

- `lmnfile`: `ConfigLoader` writes are now atomic.
- New `subnets` module to manage subnets and track changes (@hermanntoast).
- New `print` module features: large-card printing (36 passwords on 2
  pages), sophomorix templates converted to Jinja.
- LDAP connection pooling with implicit reconnect; dots allowed in
  usernames/logins; `configobj` added as a dependency; `datetime.utcnow()`
  usage replaced.
- New READMEs for `common`, `devices`, install scripts, `lmnconfig`,
  `print`, `smbclient`, `subnets`, and an updated `ldapconnector` README for
  the password-management API.

---

## Upgrade notes

Two changes in this cycle are **breaking** for any code calling into
`linuxmuster-tools` directly (the API, the webui and the CLI have all been
updated already):

- `sophomorixCloudQuotaCalculated` / `sophomorixMailQuotaCalculated` are now
  `str`, not `list`, on `LMNUserModel`, `LMNRawUserModel` and
  `LMNObjectModel`.
- `LMNMgmtGroup` and `samba_util.UserManager` have been removed. Use
  `samba_util.GroupManager` and `LMNUser`'s password methods instead.

---

Author: Arnaud Kientz
Co-Author: Claude
