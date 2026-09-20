# install-scripts

Standalone deployment and hook scripts for [linuxmuster.net](https://www.linuxmuster.net), run by the `linuxmuster-tools7` Debian package during installation/upgrade and by sophomorix during its own lifecycle events.

Unlike the other `linuxmusterTools` modules, this directory is **not an importable Python package** — there is no `__init__.py`. Each file is a self-contained script with its own shebang, meant to be executed directly, not imported.

---

## Contents

| Path | Role |
|---|---|
| `create_students_groups.py` | **Deprecated.** Rebuilt schoolclass/parents group membership in LDAP. No longer run by `debian/postinst`; nothing calls it. |
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

> **Deprecated, may be removed in a future release.** Nothing calls this script any more — `debian/postinst` used to run it on every install and upgrade. Use `lmncli schoolclass sync -c <class> -s <school> --groups` to repair one class, or `lmncli schoolclass sync --all -s <school>` for the full sweep this script used to do.

Iterates all schoolclasses and calls `LMNSchoolclass.fill_group_members()` on each, to (re)build the `<class>-students`, `<class>-teachers` and `<class>-parents` groups. It then instantiates a dummy `LMNParentsGroup` per school, which was meant to ensure the `Student-Parents` OU exists for every school.

Why the sweep is redundant:

| Path | What keeps the subgroups in sync |
|---|---|
| `sophomorix-add` / `-update` | The hooks below; instantiating `LMNSchoolclass` creates any missing subgroup |
| Teacher joins/leaves a class | `sophomorix-class --addadmins/--removeadmins` calls back `lmncli schoolclass sync` |
| Student added/removed outside an import | `sophomorix-class --addmembers/--removemembers`, same callback |
| Class deleted | `sophomorix-class` calls `lmncli schoolclass cleanup` |

Both callbacks need **sophomorix4 >= 7.4.4**, which is guaranteed in practice: an installation pulls `linuxmuster-webui7`, which depends on sophomorix.

The `LMNParentsGroup('')` half never worked: `load_data()` calls `_check_ou()` before assigning `self.student`, and `_check_ou()` reads `self.student['dn']`, so an actually missing OU raises `AttributeError` — caught and logged as a failure. The OU is created on demand by any real `LMNParentsGroup(<student>)`.

Errors are caught and logged with `lprint.danger()` rather than raised, so a failure here does not abort the package installation.

### Usage

```bash
/opt/linuxmuster/bin/python3 \
    /usr/lib/python3/dist-packages/linuxmusterTools/install-scripts/create_students_groups.py
```

No arguments. It prints a deprecation warning and, when `/etc/linuxmuster/webui/config.yml` is absent (a brand-new install, no LDAP tree to check yet), does nothing.

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
