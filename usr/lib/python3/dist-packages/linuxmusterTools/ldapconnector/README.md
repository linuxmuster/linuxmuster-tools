# ldapconnector

A URL-based LDAP client for [linuxmuster.net](https://www.linuxmuster.net), providing both a read-only query interface and a high-level object API for writing.

`ldapconnector` exposes two entry points: `LMNLdapReader` for querying the LDAP tree via URL-style paths, and a set of writer classes (`LMNUser`, `LMNSchoolclass`, `LMNProject`, …) for modifying entries.

---

## Requirements

- Python 3.8+
- [`python-ldap`](https://pypi.org/project/python-ldap/)
- A reachable Samba/AD LDAP server (configured via `linuxmuster.net` setup)

Connecting as root (or outside the webui) requires Samba to already be provisioned (`linuxmuster-setup` run). If it isn't yet — fresh install, setup wizard not completed — `LdapConnector._connect()` raises `linuxmusterTools.common.LdapNotProvisionedError` instead of a raw `FileNotFoundError` on the missing `.secret/administrator`; catch it to redirect to the setup wizard / return a clear "not provisioned" error instead of a 500.

---

## Reading — `LMNLdapReader`

### Import

```python
from linuxmusterTools.ldapconnector import LMNLdapReader as lr
```

### `get(url, **kwargs)`

Main method. Returns a `dict` (single entry) or `list[dict]` (collection) by default.

```python
lr.get(url, attributes=[], sortkey=None, as_dict=True, school='default-school')
```

| Parameter | Type | Description |
|---|---|---|
| `url` | `str` | URL path (see [Available routes](#available-routes)) |
| `attributes` | `list[str]` | Restrict returned fields (default: all) |
| `sortkey` | `str` | Sort results by this attribute |
| `as_dict` | `bool` | `True` → dict(s), `False` → dataclass object(s) |
| `school` | `str` | Target school in multi-school setups (default: `'default-school'`, `'global'` for global admins) |

### `getval(url, attribute)`

Returns the value of a single attribute.

```python
lr.getval('/users/johndoe', 'mail')       # 'johndoe@example.com'
lr.getval('/schoolclasses', 'cn')         # ['5a', '7b', '10a', ...]
```

### `getvalues(url, attributes)`

Returns a subset of attributes.

```python
lr.getvalues('/users/johndoe', ['cn', 'mail', 'sophomorixRole'])
# {'cn': 'johndoe', 'mail': 'johndoe@example.com', 'sophomorixRole': 'teacher'}
```

### `ascsv(url, delimiter=';', csvfile=None, attributes=[], header=True, **kwargs)`

Exports results to a CSV file. If `csvfile` is not provided, the file is written to `/tmp/`.

```python
lr.ascsv('/users', attributes=['cn', 'mail', 'sophomorixRole'])
```

---

## Examples

### Get all schoolclasses (names only, sorted)

```python
lr.get('/schoolclasses', attributes=['cn'], sortkey='cn')
# [{'cn': '5a'}, {'cn': '7b'}, {'cn': '10a'}, ...]
```

### Get a single user

```python
lr.get('/users/johndoe')
# {'cn': 'johndoe', 'mail': 'johndoe@example.com', 'sophomorixRole': 'teacher', ...}
```

### Get a user as a dataclass object

```python
user = lr.get('/users/johndoe', as_dict=False)
# LMNUserModel(cn='johndoe', mail='johndoe@example.com', ...)
print(user.sophomorixRole)
```

### Search users

```python
# Search students whose cn/sn/givenName contains 'mueller'
lr.get('/users/search/student/mueller', attributes=['cn', 'sophomorixAdminClass'])
```

Valid `SELECTION` values: `all`, `admins`, `teacher`, `student`, `parent`, `staff`, `globaladministrator`, `schooladministrator`.

### Batch lookup

```python
# Multiple users by comma-separated CNs
lr.get('/batch_users/johndoe,janedoe,jsmith', attributes=['cn', 'mail'])
```

---

## Available routes

Routes returning a single entry are marked **S**, collections **C**.

### Users

| URL | Type | Description |
|---|---|---|
| `/users` | C | All users (full model) |
| `/users/USERNAME` | S | Single user |
| `/users/exam` | C | All exam users |
| `/users/exam/NAME` | S | Single exam user (`NAME` or `NAME-exam`) |
| `/users/search/SELECTION/QUERY` | C | Search by role and login/name fragment |
| `/rawusers` | C | All users (raw model, fewer fields) |
| `/rawusers/USERNAME` | S | Single user (raw model) |
| `/batch_users/U1,U2,...` | C | Multiple users by CN list |
| `/batch_rawusers/U1,U2,...` | C | Multiple raw users by CN list |

### Roles

| URL | Type | Description |
|---|---|---|
| `/roles/ROLE` | C | All users in a sophomorix role |
| `/rawroles/ROLE` | C | Same, raw model |
| `/globaladministrators` | C | All global admins |
| `/globaladministrators/USERNAME` | S | Single global admin |
| `/schooladministrators` | C | All school admins |
| `/schooladministrators/USERNAME` | S | Single school admin |

Valid `ROLE` values: `teacher`, `student`, `parent`, `staff`, `globaladministrator`, `schooladministrator`, `examuser`.

### Schoolclasses

| URL | Type | Description |
|---|---|---|
| `/schoolclasses` | C | All schoolclasses |
| `/schoolclasses/SCHOOLCLASS` | S | Single schoolclass |
| `/schoolclasses/SCHOOLCLASS/students` | C | Students of a schoolclass |
| `/schoolclasses/search/QUERY` | C | Schoolclasses whose name contains QUERY |
| `/extraclasses` | C | All extra classes |
| `/extraclasses/SCHOOLCLASS` | S | Single extra class |
| `/empty_schoolclasses` | C | Schoolclasses with no members |

### Groups

| URL | Type | Description |
|---|---|---|
| `/groups` | C | All sophomorix groups |
| `/groups/NAME` | S | Single group |
| `/managementgroups` | C | All management groups |
| `/managementgroups/NAME` | S | Single management group |
| `/printers` | C | All printer groups |
| `/printers/NAME` | S | Single printer group |
| `/projects` | C | All projects |
| `/projects/PROJECT` | S | Single project |
| `/rooms` | C | All room groups |
| `/rooms/NAME` | S | Single room group |
| `/empty_rooms` | C | Rooms with no members |

### Devices

| URL | Type | Description |
|---|---|---|
| `/devices` | C | All devices |
| `/devices/NAME` | S | Single device |
| `/devices/search/SELECTION/QUERY` | C | Devices matching role and CN fragment |

Valid `SELECTION` values: `all`, or a specific role like `printer`.

### Schools

| URL | Type | Description |
|---|---|---|
| `/schools` | C | All schools |
| `/schools/SCHOOL` | S | Single school |

### System / OU

| URL | Type | Description |
|---|---|---|
| `/ou` | C | All OUs |
| `/ou/parents` | S | Parents OU |
| `/ou/rooms` | S | Rooms OU |
| `/ou/staff` | S | Staff OU |
| `/ou/students` | S | Students OU |
| `/units` | C | All units (catch-all group search) |
| `/units/NAME` | S | Single unit by CN |
| `/gpos` | C | All GPOs |
| `/gpos/NAME` | S | Single GPO |
| `/search/QUERY` | C | Generic LDAP search |
| `/dn/DN` | S | Lookup by full distinguished name |
| `/globalbindusers` | C | Global bind users |
| `/globalbindusers/USERNAME` | S | Single global bind user |
| `/schoolbindusers` | C | School bind users |
| `/schoolbindusers/USERNAME` | S | Single school bind user |

---

## Writing — object API

Writer classes load an LDAP entry on instantiation and expose methods to modify it. All changes are applied immediately.

### Import

```python
from linuxmusterTools.ldapconnector import (
    LMNUser, LMNStudent, LMNTeacher, LMNParent, LMNStaff,
    LMNSchoolAdmin, LMNGlobalAdmin,
    LMNSchoolclass, LMNSchoolclasses,
    LMNProject, LMNProjects,
    LMNGroup,
)
```

### Common interface

All writer classes share this interface:

```python
obj = LMNUser('johndoe')           # loads entry from LDAP
obj.data                           # dict of all LDAP attributes
obj.setattr(data={'mail': 'new@example.com'})   # modify attributes
obj.delattr(data={'mail': ''})                  # delete attributes
obj.getattr('mail')                             # read one attribute
obj.delete()                                    # delete the entry
```

### Password management

```python
user = LMNUser('johndoe')
user.test_first_password()               # True / False

user.set_actual_password('N3wP@ssw0rd')  # sets the current password (unicodePwd) only
user.set_first_password('N3wP@ssw0rd')   # sets sophomorixFirstPassword *and* the current password
user.set_random_first_password()         # generates a policy-compliant password, returns it
```

`test_first_password()` performs a real LDAP bind against `user.dn` using the stored `sophomorixFirstPassword`, to check whether the user is still using their initial password. It does not read or modify `unicodePwd`. Raises if the bind itself cannot be attempted (e.g. LDAP unreachable) rather than returning `False`.

`set_actual_password()`/`set_first_password()`/`set_random_first_password()` write the account's real password directly via Samba's `SamDB` (`unicodePwd`), bypassing `sophomorix-passwd`/`smbpasswd` entirely — no password ever transits through a subprocess argv or a shell pipe. This requires root (opens `/var/lib/samba/private/sam.ldb`): call these from an already-privileged process (e.g. lmnapi), never from a demoted webui worker. `set_random_first_password()` resolves the applicable policy via [`passwords.PasswordPolicyProvider`](../passwords/README.md) (domain policy + per-school/role config) and generates a password exactly at that policy's minimum length — there's no length argument, the policy is the only source of truth for it. Raises `RuntimeError` if no candidate satisfies the policy after 100 attempts.

### Group management

`LMNGroup`, `LMNSchoolclass`, and `LMNProject` also expose:

```python
group = LMNSchoolclass('7b')
group.add_member('johndoe')
group.remove_member('johndoe')
group.add_members(['johndoe', 'janedoe'])
group.remove_members(['johndoe', 'janedoe'])
group.remove_all_members()
```

`LMNSchoolclass` automatically keeps the `7b-students`, `7b-teachers`, and `7b-parents` subgroups in sync after every membership change, and `fill_admins()` keeps `sophomorixAdmins` — where sophomorix stores the teachers of a class, as sAMAccountNames — equal to the members under `OU=Teachers`.

That second sync matters because sophomorix treats `sophomorixMembers`/`sophomorixAdmins` as the source of truth and rebuilds `member` from them: a teacher written only into `member` is invisible to the webui and API permissions, to `lmncli schoolclass teachers` and to first passwords printing, and is silently dropped from the class by the next sophomorix run. Students are not handled this way: putting one in a class is not only an LDAP membership, it needs the share management which lives in sophomorix.

Those subgroups belong to `linuxmusterTools`, not to sophomorix:
`sophomorix-class --kill` only deletes the schoolclass group itself and leaves
them, and the OU of the schoolclass, in the directory. Two functions clean
that up (both used by `lmncli schoolclass cleanup`, which `sophomorix-class`
calls after a kill):

```python
from linuxmusterTools.ldapconnector import (
    delete_schoolclass_subgroups, orphan_schoolclass_subgroups,
)

orphan_schoolclass_subgroups()
# ['16e']  schoolclasses which are gone but whose subgroups are still there

delete_schoolclass_subgroups('16e')
# ['CN=16e-students,OU=16e,...', ..., 'OU=16e,OU=Students,...']
```

`delete_schoolclass_subgroups()` raises `SchoolclassExistsError` if the
schoolclass still exists, and deletes the OU of the schoolclass only once
nothing is left in it — a class killed while its students still existed keeps
their accounts there until the next import. That OU is located as the parent
of the subgroups, so an OU which is left alone is not cleaned up.

`add_member()` is idempotent: adding a cn which already is a member is a no-op, not an error. A failed LDAP write raises, it is never reported as a success.

`add_members()`/`remove_members()` never abort partway through the list: an entry which fails — an invalid cn as well as a rejected LDAP write — is skipped rather than stopping the batch, and the call returns a list of `(cn, error_message)` tuples for the entries that failed (empty list if everything succeeded).

### Students

```python
student = LMNStudent('johndoe')
student.move('8a')                           # move to another schoolclass
student.add_parent('johndoe-parent')         # link a parent account
student.remove_parent('johndoe-parent')
```

### Projects

```python
project = LMNProject('robotics')
if project.new:
    project.create()                         # create if not yet in LDAP
project.add_member('johndoe')
```

### Bulk iteration

```python
for cn, schoolclass in LMNSchoolclasses().items():
    print(cn, len(schoolclass.data['member']))

for cn, user in LMNUsers().items():
    print(user.data['sophomorixRole'])
```

Available collection classes: `LMNUsers`, `LMNStudents`, `LMNTeachers`, `LMNParents`, `LMNStaffs`, `LMNSchoolAdmins`, `LMNGlobalAdmins`, `LMNSchoolclasses`, `LMNProjects`.

---

## Multi-school support

Most routes and writer classes accept a `school` parameter. Use `'global'` to search across all schools (valid for global administrators only).

```python
lr.get('/schoolclasses', school='secondary')
LMNSchoolclass('7b', school='secondary')
```

**Always pass `school` explicitly on a multi-school server.** What omitting it does depends on the route:

| Route kind | `school` omitted |
|---|---|
| Route with a school-scoped subdn (`/units`, `/groups`, `/printers`, `/rooms`, `/ou`, …) | searched under `OU=default-school` |
| Any other route (`/schoolclasses`, `/users`, `/projects`, …) | **no filtering at all** — entries of every school are returned |

The reason is that the reader filters on the DN only when it actually receives a `school` (`school_node = f"OU={school},"`); the default `'default-school'` is used to substitute the subdn marker, not to filter the results. So `lr.getval('/schoolclasses', 'cn')` lists the schoolclasses of *all* schools, while `lr.getval('/schoolclasses', 'cn', school='default-school')` lists only that school's ones.

### Validating a school

```python
from linuxmusterTools.ldapconnector.checks import is_valid_school, valid_schools

valid_schools()                     # ['default-school', 'secondary']
is_valid_school('secondary')        # True
is_valid_school('global')           # False, 'global' is a routing marker, not a school
```

Both read `/schools` on each call (no caching). `'global'` is never a valid school: it is the marker telling that a global administrator is not scoped to a single school, and passing it to a writer instead of a real school name writes bogus school-scoped attributes.
