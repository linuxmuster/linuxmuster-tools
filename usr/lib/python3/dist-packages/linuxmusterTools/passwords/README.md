# passwords

Resolves, per school and per role, the set of static composition rules a [linuxmuster.net](https://www.linuxmuster.net) password must satisfy — on top of Samba AD's own length/history/age/lockout enforcement.

---

## Requirements

- Python 3.8+
- [`PyYAML`](https://pypi.org/project/PyYAML/) (config file parsing, via `linuxmusterTools.lmnfile`)
- A reachable Samba AD domain, read via `linuxmusterTools.samba_util.DomainPasswordSettingsManager` (`samba-tool domain passwordsettings show` equivalent) — used as the live policy when the config file is absent, and as a floor otherwise

---

## Overview

`policy.py` resolves, per school and per role, the set of rules a
password must satisfy. Resolution order: school-specific override in the YAML
config > per-role default in the same config > live Samba AD domain policy
(used entirely when the config file is absent, and as a floor otherwise —
see below).

Samba's own length/history/age/lockout enforcement still applies regardless
of this module — it only covers static composition constraints (length,
character classes, forbidden substrings), which is the one part Samba cannot
express beyond its fixed on/off complexity flag.

---

## Config file: `/etc/linuxmuster/tools/password_constraints.yml`

```yaml
default:
  student:
    - {type: min_length, value: 8}
    - {type: require_classes, classes: [digit, upper], count: 1}
  teacher:
    - {type: min_length, value: 10}
    - {type: require_classes, classes: [lower, upper, digit, special], count: 3}
  staff:
    - {type: min_length, value: 10}
    - {type: require_classes, classes: [lower, upper, digit, special], count: 3}
  schooladministrator:
    - {type: min_length, value: 12}
    - {type: require_classes, classes: [lower, upper, digit, special], count: 3}

schools:
  abc:
    teacher:
      - {type: min_length, value: 12}
      - {type: require_classes, classes: [lower, upper, digit, special], count: 3}
```

If this file is absent, every role/school falls back entirely to the live
Samba AD domain policy (`samba-tool domain passwordsettings show`): minimum
length, and — if complexity is enabled — 3-of-4 character classes. A rule
rejecting passwords containing the account's username is *always* applied,
regardless of the config or of Samba's complexity flag — see below.

**The Samba policy is also enforced as a floor when a config entry exists.**
Samba applies its own minimum length/complexity at write time regardless of
what this module validates, so a weaker config would otherwise "pass" here
and still get rejected by Samba — a confusing inconsistency. Concretely: the
effective `min_length` is `max(config value, Samba's live minimum)`, and if
Samba complexity is enabled, its 3-of-4 classes rule is always added
alongside the config's own rules (exact duplicates are merged, not reported
twice). Example: `min_length: 5` in the config on a server where Samba
enforces 7 results in `at least 7 characters`, not 5.

**`forbid_username` is not a config option.** There's no legitimate case for
a school wanting "password may contain the username", so it's hardcoded as
an always-on rule instead of exposed in the YAML — `{type: forbid_username}`
in the config raises a `ValueError` telling you to remove it.

### Known limitation — Fine-Grained Password Policies (PSO) are not accounted for

`DomainPasswordSettingsManager.get()` only reads the domain-wide password
policy (`minPwdLength`/`pwdProperties` on the domain root object). It has no
notion of per-user or per-group **PSOs** (`msDS-PasswordSettings` objects,
managed with `samba-tool domain passwordsettings pso ...`), which override
the domain-wide policy for the users/groups they're applied to.

If an admin creates a PSO for a specific role/group, the Samba floor computed
here silently stops reflecting what Samba actually enforces for that
population, in either direction:
- **PSO stricter than the domain policy** → our floor is too weak: a
  password validates here but Samba still rejects it at write time.
- **PSO more permissive** → our floor is too strict: we reject a password
  Samba would actually accept.

The fix is to make the Samba read user-aware: each user object exposes a
constructed attribute `msDS-ResultantPSO` (confirmed in this domain's schema
— `systemFlags` includes `FLAG_ATTR_IS_CONSTRUCTED`) giving the
already-precedence-resolved effective PSO for that user, if any (different
attribute names than the domain-wide policy: `msDS-MinimumPasswordLength`,
`msDS-PasswordComplexityEnabled`, etc.). `DomainPasswordSettingsManager`
would need to take a username (or a representative group per role) and
follow `msDS-ResultantPSO` before falling back to the domain-wide read.

Not an issue today: no PSO exists on any known linuxmuster deployment or in
this codebase (`samba-tool domain passwordsettings pso list` → none on this
dev domain either) — but this becomes silently wrong the moment one is
created. See the `TODO` on `DomainPasswordSettingsManager` in
`samba_util/samba_tool.py`.

### Samba's out-of-the-box policy (`samba-tool domain passwordsettings set --help`)

These are Samba's shipped defaults, i.e. what a freshly provisioned domain
has until an admin runs `samba-tool domain passwordsettings set`. Always
check the actual values on a given server with `samba-tool domain
passwordsettings show` — they're commonly changed post-install.

| Setting | Samba default | Covered by this module's fallback? |
|---|---|---|
| `complexity` | `on` | Yes → `RequireClassesRule([lower, upper, digit, special], count=3)` (`ForbidUsernameRule` is always applied, independently of this flag) |
| `min-pwd-length` | `7` | Yes → `MinLengthRule(7)` |
| `history-length` | `24` | No — Samba-only, not a property of a single password |
| `min-pwd-age` | `1` day | No — not a per-password rule this module validates, readable/settable via `DomainPasswordSettingsManager` (see below) |
| `max-pwd-age` | `43` days | No — not a per-password rule this module validates, readable/settable via `DomainPasswordSettingsManager` (see below) |
| `account-lockout-threshold` | `0` (never locks out) | No — Samba-only; this is the setting usually behind "Samba's policy is too permissive" |
| `account-lockout-duration` | `30` min | No — Samba-only |
| `reset-account-lockout-after` | `30` min | No — Samba-only |

**`DomainPasswordSettingsManager.get()`/`.set()` also expose `min_pwd_age`/
`max_pwd_age`** (domain-wide, in days), read/write directly via SamDB —
`lmnapi` surfaces them for domain administration at `GET`/`POST
/v1/samba/passwordpolicy`. This is unrelated to the rule resolution this
module does: `PasswordPolicy.from_samba()` only ever translates
`min_pwd_length`/`complexity` into rules, exactly as before — age settings
aren't a property of a single password, so they stay out of
`PasswordPolicy`/`PasswordPolicyProvider` entirely, they're just readable
alongside the other two fields on the same `DomainPasswordSettings` object.

### Rule types

| `type` | Fields | Meaning |
|---|---|---|
| `min_length` | `value` (int) | Password must be at least `value` characters long |
| `require_classes` | `classes` (list of `lower`/`upper`/`digit`/`special`), `count` (int, default `len(classes)`, must be ≤ `len(classes)`) | At least `count` of the listed classes must appear — `count: 1` expresses "or", omitting `count` (or setting it to `len(classes)`) expresses "and", i.e. all listed classes required |

`forbid_username` is intentionally not listed here — see above.

---

## Usage

```python
from linuxmusterTools.passwords import PasswordPolicyProvider

provider = PasswordPolicyProvider()
result = provider.validate("Sch00l!", role="teacher", school="abc", username="jdupont")
result.ok
# False
result.violations
# ('at least 12 characters',)
provider.get_policy("teacher", "abc").as_dict()
# {'source': 'config:abc/teacher+samba-floor', 'rules': ['at least 12 characters', 'at least 3 of: lower, upper, digit, special', "must not contain the account's username"]}
```
