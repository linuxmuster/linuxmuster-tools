"""
Password constraint policies for linuxmuster.net.

Resolves, per school and per role, the set of rules a password must satisfy.
Resolution order: school-specific override in the YAML config > per-role
default in the same config > live Samba AD domain policy (used entirely when
the config file is absent).

The live Samba policy is also used as a FLOOR even when a YAML config exists:
Samba enforces its own minimum length/complexity at write time regardless of
what this module thinks is acceptable, so a config weaker than Samba would
only produce a confusing failure downstream (accepted here, rejected by
Samba). Resolved policies are therefore always at least as strict as Samba's.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from linuxmusterTools.lmnfile import LMNFile
from linuxmusterTools.samba_util import DomainPasswordSettings, DomainPasswordSettingsManager

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("/etc/linuxmuster/tools/password_constraints.yml")


class CharClass(str, Enum):
    LOWER = "lower"
    UPPER = "upper"
    DIGIT = "digit"
    SPECIAL = "special"

    def matches(self, char: str) -> bool:
        if self is CharClass.LOWER:
            return char.islower()
        if self is CharClass.UPPER:
            return char.isupper()
        if self is CharClass.DIGIT:
            return char.isdigit()
        return not char.isalnum()


@dataclass(frozen=True, slots=True)
class MinLengthRule:
    length: int

    def check(self, password: str, *, username: str | None = None) -> bool:
        return len(password) >= self.length

    def describe(self) -> str:
        return f"at least {self.length} characters"


@dataclass(frozen=True, slots=True)
class RequireClassesRule:
    """
    At least `count` of `classes` must appear at least once.

    count=1 with two classes expresses an "or" (e.g. digit OR uppercase).
    Omitting count (or setting it to len(classes)) expresses an "and" (one
    of each listed class) — this is the default, since it's the only one
    that's always valid regardless of how many classes are listed (a fixed
    number like Samba's "3 of 4" only makes sense for exactly 4 classes).
    """

    classes: tuple[CharClass, ...]
    count: int | None = None

    def __post_init__(self):
        if self.count is None:
            object.__setattr__(self, "count", len(self.classes))
        elif self.count > len(self.classes):
            raise ValueError(
                f"RequireClassesRule: count ({self.count}) cannot exceed "
                f"the number of listed classes ({len(self.classes)})"
            )

    def check(self, password: str, *, username: str | None = None) -> bool:
        satisfied = sum(any(cls.matches(c) for c in password) for cls in self.classes)
        return satisfied >= self.count

    def describe(self) -> str:
        names = [c.value for c in self.classes]
        if self.count == 1:
            return f"at least one of: {' or '.join(names)}"
        return f"at least {self.count} of: {', '.join(names)}"


@dataclass(frozen=True, slots=True)
class ForbidUsernameRule:
    """
    Rejects passwords containing the target account's username.

    Always applied by `PasswordPolicyProvider`, independently of Samba's
    complexity setting and not exposed as a config rule type: there's no
    legitimate reason for a school to want this off.
    """

    def check(self, password: str, *, username: str | None = None) -> bool:
        if not username:
            return True
        return username.lower() not in password.lower()

    def describe(self) -> str:
        return "must not contain the account's username"


class PasswordRules:
    """
    Pure rule construction and combination logic — no I/O, no state.
    """

    _CLASS_ALIASES = {
        "lower": CharClass.LOWER, "lowercase": CharClass.LOWER,
        "upper": CharClass.UPPER, "uppercase": CharClass.UPPER,
        "digit": CharClass.DIGIT, "number": CharClass.DIGIT,
        "special": CharClass.SPECIAL, "symbol": CharClass.SPECIAL,
    }

    @staticmethod
    def build(entry: dict):
        rule_type = entry.get("type")
        if rule_type == "min_length":
            return MinLengthRule(length=int(entry["value"]))
        if rule_type == "require_classes":
            classes = tuple(PasswordRules._CLASS_ALIASES[c] for c in entry["classes"])
            count = int(entry["count"]) if "count" in entry else None
            return RequireClassesRule(classes=classes, count=count)
        if rule_type == "forbid_username":
            raise ValueError(
                "forbid_username is always applied automatically and is not a "
                "configurable rule type — remove it from the config"
            )
        raise ValueError(f"Unknown password rule type: {rule_type!r}")

    @staticmethod
    def _dedup_key(rule):
        """
        Canonical key used to drop exact duplicates when merging rule sets.

        Ignores the order `classes` was listed in, so a config rule and a
        Samba floor rule expressing the same constraint don't both show up
        as separate (duplicate) violations. `MinLengthRule` isn't covered
        here — it's merged by taking the maximum length instead, see `merge`.
        """

        if isinstance(rule, RequireClassesRule):
            return ("require_classes", frozenset(rule.classes), rule.count)
        if isinstance(rule, ForbidUsernameRule):
            return ("forbid_username",)
        return None

    @staticmethod
    def merge(*rule_groups):
        """
        Combine several rule groups into one, keeping the strictest of each.

        `MinLengthRule`s collapse to a single rule with their maximum length.
        Everything else is kept, with exact duplicates (by `_dedup_key`)
        removed so a rule already covered by one group isn't reported twice.
        """

        all_rules = [rule for group in rule_groups for rule in group]
        lengths = [rule.length for rule in all_rules if isinstance(rule, MinLengthRule)]

        merged = [MinLengthRule(max(lengths))] if lengths else []
        seen = set()
        for rule in all_rules:
            if isinstance(rule, MinLengthRule):
                continue
            key = PasswordRules._dedup_key(rule)
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            merged.append(rule)

        return tuple(merged)


@dataclass(frozen=True, slots=True)
class PasswordValidationResult:
    ok: bool
    violations: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {"ok": self.ok, "violations": list(self.violations)}


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    """
    An immutable, ordered set of rules a password must satisfy.
    """

    rules: tuple
    source: str = "config"  # e.g. "config:school-x/student" or "samba-fallback"

    def validate(self, password: str, *, username: str | None = None) -> PasswordValidationResult:
        violations = tuple(
            rule.describe() for rule in self.rules
            if not rule.check(password, username=username)
        )
        return PasswordValidationResult(ok=not violations, violations=violations)

    def as_dict(self) -> dict:
        return {"source": self.source, "rules": [r.describe() for r in self.rules]}

    @classmethod
    def from_samba(cls, settings: DomainPasswordSettings) -> "PasswordPolicy":
        # ForbidUsernameRule is unconditional — unlike the 3-of-4 classes
        # rule, it doesn't depend on Samba's complexity flag, see
        # ForbidUsernameRule.
        rules = [MinLengthRule(settings.min_pwd_length), ForbidUsernameRule()]
        if settings.complexity:
            # Mirrors Microsoft's fixed algorithm: 3 of the 4 character classes.
            rules.append(RequireClassesRule(
                classes=(CharClass.LOWER, CharClass.UPPER, CharClass.DIGIT, CharClass.SPECIAL),
                count=3,
            ))
        return cls(rules=tuple(rules), source="samba-fallback")

class PasswordPolicyProvider:
    """
    Resolves the applicable password policy for a given role and school.
    """

    def __init__(self, config_path: Path | str = CONFIG_PATH):
        self.config_path = Path(config_path)
        self._samba_settings: DomainPasswordSettings | None = None
        self._raw_config: dict = self._load_config()
        self._cache: dict[tuple[str, str], PasswordPolicy] = {}

    def _load_config(self) -> dict:
        # Check existence ourselves: YAMLLoader creates an empty file on open
        # when running as root (lmnfile/lmnfile.py:229-234) — never call
        # LMNFile on a path we haven't confirmed exists.
        if not self.config_path.is_file():
            logger.info(
                "No password constraints config at %s, using Samba policy only",
                self.config_path,
            )
            return {}
        with LMNFile(str(self.config_path), "r") as config:
            return config.read() or {}

    def _samba_policy(self) -> PasswordPolicy:
        if self._samba_settings is None:
            self._samba_settings = DomainPasswordSettingsManager().get()
        return PasswordPolicy.from_samba(self._samba_settings)

    def get_policy(self, role: str, school: str = "default-school") -> PasswordPolicy:
        cache_key = (school, role)
        if cache_key in self._cache:
            return self._cache[cache_key]

        entries = None
        source = None
        if self._raw_config:
            entries = self._raw_config.get("schools", {}).get(school, {}).get(role)
            source = f"config:{school}/{role}"
            if entries is None:
                entries = self._raw_config.get("default", {}).get(role)
                source = f"config:default/{role}"

        samba_policy = self._samba_policy()
        if entries:
            config_rules = tuple(PasswordRules.build(e) for e in entries)
            # Samba is always applied as a floor: a config weaker than the
            # live domain policy would otherwise validate here and still be
            # rejected by Samba at write time.
            merged_rules = PasswordRules.merge(config_rules, samba_policy.rules)
            policy = PasswordPolicy(rules=merged_rules, source=f"{source}+samba-floor")
        else:
            policy = samba_policy

        self._cache[cache_key] = policy
        return policy

    def validate(
        self, password: str, role: str, school: str = "default-school", *, username: str | None = None
    ) -> PasswordValidationResult:
        return self.get_policy(role, school).validate(password, username=username)
