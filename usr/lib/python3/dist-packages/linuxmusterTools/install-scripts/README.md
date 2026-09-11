# install-scripts

Standalone deployment and hook scripts for [linuxmuster.net](https://www.linuxmuster.net), run by the `linuxmuster-tools7` Debian package during installation/upgrade and by sophomorix during its own lifecycle events.

Unlike the other `linuxmusterTools` modules, this directory is **not an importable Python package** — there is no `__init__.py`. Each file is a self-contained script with its own shebang, meant to be executed directly, not imported.

---

## Contents

| Path | Role |
|---|---|
| `create_students_groups.py` | Rebuilds schoolclass/parents group membership in LDAP. Run once by `debian/postinst`. |
| `sophomorix-hooks/sophomorix-add.d/00-update-schoolclasses-groups.py` | Sophomorix `add` hook template. |
| `sophomorix-hooks/sophomorix-update.d/00-update-schoolclasses-groups.py` | Sophomorix `update` hook template. |
| `sophomorix-hooks/sophomorix-kill.d/00-update-schoolclasses-groups.py` | Sophomorix `kill` hook template. |

---

## Requirements

- Must run under the linuxmuster.net virtualenv interpreter, `/opt/linuxmuster/bin/python3` (created by `debian/postinst`), not the system `python3` — `linuxmusterTools` and its dependencies are installed there.
- Must run as **root**: the scripts write to LDAP (`ldapconnector`) and read from `/etc/linuxmuster/`.
- A reachable Samba/AD LDAP server, already provisioned by sophomorix (schoolclasses, users, OUs must exist).

---

## `create_students_groups.py`

Iterates all schoolclasses and calls `LMNSchoolclass.fill_group_members()` on each, to (re)build the `<class>-students`, `<class>-teachers` and `<class>-parents` groups. It then instantiates a dummy `LMNParentsGroup` per school, which as a side effect ensures the `Student-Parents` OU/group structure exists for every school.

Errors are caught and logged with `lprint.danger()` rather than raised, so a failure here does not abort the package installation.

### Usage

```bash
/opt/linuxmuster/bin/python3 \
    /usr/lib/python3/dist-packages/linuxmusterTools/install-scripts/create_students_groups.py
```

No arguments. In practice you never run this by hand — `debian/postinst` invokes it automatically on `install|configure`, and only when `/etc/linuxmuster/webui/config.yml` already exists. On a brand-new install that file is absent (there is no LDAP tree yet to check), so the script is skipped; it only runs on package **upgrades** of an already-provisioned server.

---

## `sophomorix-hooks/`

Templates for sophomorix's own hook mechanism, not executed from here directly. `debian/postinst` copies each file into the live hooks directory and makes it executable:

```bash
cp -a install-scripts/sophomorix-hooks/sophomorix-add.d/00-update-schoolclasses-groups.py \
    /etc/linuxmuster/sophomorix/default-school/hooks/sophomorix-add.d/
# ... same for sophomorix-update.d and sophomorix-kill.d
chmod +x /etc/linuxmuster/sophomorix/default-school/hooks/sophomorix-*.d/00-update-schoolclasses-groups.py
```

Each installed copy is then called automatically by sophomorix (Perl) after the matching operation, with two positional arguments:

```bash
00-update-schoolclasses-groups.py EPOCH SCHOOL
```

| Argument | Description |
|---|---|
| `EPOCH` | Unix timestamp identifying the sophomorix log entry batch to process. |
| `SCHOOL` | School the operation applies to. **Ignored by these hooks**: the sophomorix logs are global files which carry the school of every entry, so each hook reads the school from the log and handles all the schools at once. A single copy in `default-school` is therefore enough — copying them into every school's hook directory would only run them once per school on the same log. |

Each hook re-reads the corresponding sophomorix log (`parse_add_log`, `parse_update_log`, `parse_kill_log` from `linuxmusterTools.common`) for that `EPOCH`, works out which `<class>-students` / `<class>-teachers` / `<class>-parents` groups are affected, and refreshes their membership via `LMNSchoolclass(...).students_group.fill_members()` (and `.teachers_group` / `.parents_group`).

| Hook | Triggered on | Effect |
|---|---|---|
| `sophomorix-add.d/00-update-schoolclasses-groups.py` | New user added | Refreshes the `-students` group of any schoolclass that gained a student. |
| `sophomorix-update.d/00-update-schoolclasses-groups.py` | User attributes changed (class move, role move to/from `attic`) | Refreshes `-students`/`-teachers`/`-parents` groups on both sides of a move; deletes/updates the student's `Student-Parents` entry when a parent or student is archived. |
| `sophomorix-kill.d/00-update-schoolclasses-groups.py` | User definitively deleted | Currently a no-op placeholder — the log is parsed but nothing is done. |

> Each hook file carries a `# DO NOT EDIT OR REMOVE IT !` header — sophomorix expects these exact filenames in its hook directories.

---

## Logging

All scripts use `lprint` from `linuxmusterTools.common` (`lprint.info`, `lprint.lmn`, `lprint.danger`) rather than `print`, consistent with the rest of the codebase.
