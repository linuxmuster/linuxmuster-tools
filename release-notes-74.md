# 🚀 Release Notes – linuxmuster-tools 7.4

**Package version:** 7.4.1 – 7.4.18

---

## 📋 Overview

Version 7.4 has been a major feature and hardening cycle for the shared
library. Four areas dominate: a full LINBO remote-control / host-status /
image-management overhaul, a new password-management and password-constraints
layer, a long tail of correctness fixes across `ldapconnector`, `samba_util`
and `quotas` — several of them closing bugs reported by early testers — and,
late in the cycle, a packaging pass that moves the runtime dependencies to
apt and repairs the shared venv after a Python upgrade. This work is what the
API, the webui and the CLI now build on: most of the logic that used to be
duplicated in those projects has moved here.

---

## 🖥️ LINBO remote control & host status

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
- `last_sync()` takes a `timestamp` parameter. Left to its default it
  returns the epoch of the last synchronisation, as before; set to `False`
  it returns the whole status entry, which also carries the creation
  timestamp of the image that was applied. `last_sync_all()` uses it to add
  an `imageVersion` key to every entry of a host's image list, saying which
  version of the image that host actually runs, or `None` when it never
  synchronised it. Existing callers are untouched.
- `image.status`: the three duplicated parsers are merged into one,
  timestamps are exposed as UTC epoch, a missing or malformed status file no
  longer raises, and file names are matched case-insensitively (reported by
  @TomS).
- `scan_hosts()` no longer returns `lastSeen`: the field held the time of the
  probe, not a last-seen date. Recording it is the caller's job.
- Boot logs are listed with the hostname each file belongs to, `None` for a
  file naming no host (a multicast log, a client which could not identify
  itself), so that a caller can keep only the machines of one school.
- LINBO hardware inventory reader, Windows driver profile metadata, image
  driver assignments and dispatcher rendering (@amolani).

---

## 💾 LINBO images, torrents and start.conf files

- Image manager: `.hash` files are now recognized as non-editable extras
  (previously left orphaned on delete/rename); new `ImageExistsError` /
  `IncompleteImageInfoError` replace silent `print()`-and-return or crashes;
  fixed a backup-only deletion bug (`self.images[group]` instead of
  `self.groups[group]`).
- Renaming or duplicating an image left behind a `.torrent` and a `.hash`
  describing the previous name: a torrent embeds the file name it serves, so
  neither survives the rename. Both are now dropped and rebuilt with
  `linbo-torrent create`, in the background and only once the directory holds
  its final name. The image listing gained a `torrent` flag saying whether
  the file is there (closes #30, reported by @TomlDev).
- Raw `start.conf` write/delete support, plus new backup handling:
  `list_startconf_backups()`, `restore_startconf_backup()` and
  `delete_startconf_backup()`. A restore backs the current file up first, so
  it can itself be undone, and copies the backup byte for byte: comments and
  formatting are the point of keeping one.
- `list_examples()` / `read_example()` expose the example configs shipped in
  `/srv/linbo/examples`, limited to the `start.conf` templates and their
  `.reg` / `.postsync` / `.prestart` sidecars.
- `read_vdi_config()`, `write_vdi_config()` and `delete_vdi_config()` handle a
  group's `start.conf.<group>.vdi` file.
- `parse_linbo_startconf()` flushes the last stanza (closes #29, reported by
  @TomlDev). Group listing is decoupled from `start.conf` parsing and exposed
  through the new `group_ids` attribute.
- The unused `LinboImageSync` class moved to WIP.

---

## 🔑 Password management

- `LMNUser` gained `set_actual_password()` (direct SamDB write, bypassing
  `sophomorix-passwd`/`smbpasswd`), `set_first_password()`,
  `set_random_first_password()` and `test_first_password()`.
- New password-constraints module: policy provider, Samba domain floor
  (minimum length/complexity/age), YAML config.
- Removed the deprecated, buggy `samba_util.UserManager` — password
  management now lives entirely in `LMNUser`.

---

## 👥 LDAP / group management hardening

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
- A failed LDAP write while adding a member now reaches the caller instead of
  being logged and reported as a success.
- Printer members are added and removed in a single targeted LDAP modify
  instead of rewriting the whole member list: two changes landing at the same
  time can no longer overwrite each other. `LMNPrinter.add_members()` /
  `remove_members()` take users as well as groups and report their failures
  like the group writers do.
- Fixed a `ValueError` when the last member of a group was removed: an empty
  member list now goes through `delattr()` (reported by @juergen).
- Fixed the parent group lookup for student logins containing a dot (merge of
  PR #31, @Maddi02).
- Fixed custom-fields config resolution: role names were looked up singular
  against a YAML keyed plural, only fields 1–4 were read instead of 1–5, and
  the config always loaded `default-school`'s settings regardless of the
  actual user's school (closes #25). A separate `KeyError` on partial
  `custom_fields.yml` entries was fixed too.
- Added `SchoolError` (raised when instantiating a group with
  `school='global'`), fixed `setattr()` silently no-op'ing on an empty value
  (now raises `ValueError`), fixed a lowercase mismatch on group/user
  lookups and a crash on an empty `/ou` lookup result.
- New `NameChecker.validate()`, used wherever a name is used to build a path.

---

## 🏫 Schoolclasses and devices

- The `<class>-teachers` / `-students` / `-parents` subgroups are now kept in
  sync in `sophomorixAdmins` too, can be deleted, and their orphans are
  detected after a kill. New `SchoolClassExistError`.
- `Devices` exposes `hostnames`, `hostname_prefix` and `prefixed_hostnames`:
  the same hosts as anything school-agnostic writes them (LINBO logs, hwinfo
  files, AD objects), which answers "is this host mine?" for a name coming
  from outside the school.
- Install scripts: student groups are checked for every school and the attic
  is excluded. The sophomorix hooks no longer abort on a single failure and
  drop a deprecated school parameter.

---

## ⚠️ Quotas fix (breaking change)

`sophomorixCloudQuotaCalculated` and `sophomorixMailQuotaCalculated` were
typed as `list` instead of `str` in `LMNUserModel`, `LMNRawUserModel` and
`LMNObjectModel` — both are single-valued LDAP attributes
(`isSingleValued: TRUE`). This caused values to render as `["2506 MB"]` once
displayed by the webui. **Any consumer of these two fields now gets a plain
`str`, not a `list`.**

---

## 📦 Packaging and the shared venv

- `configobj`, `jinja2`, `python-ldap`, `magic`, `pexpect` and `pyyaml` are
  declared as apt dependencies instead of `requirements.txt`: pip installs
  nothing in a `--system-site-packages` venv when the system already
  satisfies the requirement, so the file never guaranteed anything (should
  close #32, reported by @HappyBasher; `pexpect` alone closes #28).
- A venv whose `pyvenv.cfg` no longer matches the running Python is rebuilt
  from scratch: it records its interpreter version once and never updates it,
  so after an Ubuntu LTS upgrade everything pip installed sits in an orphaned
  `site-packages`, off `sys.path`, and the venv looks healthy while importing
  nothing. The rebuild fires the new `linuxmuster-venv` dpkg trigger, which
  has `linuxmuster-api7`, `-cli7` and `-webui7` reinstall their own
  requirements.

---

## 📝 Logging

- Unknown `start.conf` parameters are reported at debug level through the
  module logger, instead of warning level through the root one. A
  `start.conf` holding legacy LINBO 2.x keys logged one warning per key and
  per file, and since the root logger is the one the consumers configure,
  those warnings landed straight in the output of `lmncli`: 37 lines for
  three groups before a single result was printed.
- Same treatment for the malformed lines skipped by the sophomorix log
  parsers.

---

## 🔧 Miscellaneous

- `lmnfile`: `ConfigLoader` writes are now atomic; `ConfigLoader` accepts
  negative values (a quota of `-1` stayed a string and left the quota tab
  empty, reported by @juergen); the CSV loader no longer parses comment
  lines as data.
- `lmnfile`: `StartConfLoader` opening a non-existent `start.conf.*` in `'w'`
  mode now creates a new group file instead of raising `FileNotFoundError`
  (closes linuxmuster/linuxmuster-webui7#293, the webui creating a new LINBO
  group via `with LMNFile(path, 'w') as f`).
- New `subnets` module to manage subnets and track changes (@hermanntoast).
- New `print` module features: large-card printing (36 passwords on 2
  pages), sophomorix templates converted to Jinja.
- LDAP connection pooling with implicit reconnect; dots allowed in
  usernames/logins; `datetime.utcnow()` usage replaced.
- New READMEs for `common`, `devices`, install scripts, `lmnconfig`,
  `print`, `smbclient`, `subnets`, and an updated `ldapconnector` README for
  the password-management API.

---

## ⚠️ Upgrade notes

The following changes are **breaking** for any code calling into
`linuxmuster-tools` directly (the API, the webui and the CLI have all been
updated already):

- `sophomorixCloudQuotaCalculated` / `sophomorixMailQuotaCalculated` are now
  `str`, not `list`, on `LMNUserModel`, `LMNRawUserModel` and
  `LMNObjectModel`.
- `LMNMgmtGroup` and `samba_util.UserManager` have been removed. Use
  `samba_util.GroupManager` and `LMNUser`'s password methods instead.
- `scan_hosts()` no longer returns a `lastSeen` key.
- The `image.status` parsers are unified and now return UTC epochs; callers
  reading the previous, locale-dependent strings must be adapted.
- `LinboImageSync` has moved to WIP and is no longer importable from its
  previous location.

Runtime dependencies are now apt dependencies, not `requirements.txt`
entries. After an Ubuntu LTS upgrade the shared venv is rebuilt on the next
upgrade of the package, and the `linuxmuster-venv` trigger makes the API, the
CLI and the webui reinstall their own requirements — no manual step is
needed.

---

Author: Arnaud Kientz
Co-Author: Claude
