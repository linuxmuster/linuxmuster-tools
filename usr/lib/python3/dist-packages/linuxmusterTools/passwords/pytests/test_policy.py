"""
Tests for password constraint resolution: rule defaults, and the Samba
floor being enforced regardless of what the YAML config says.
"""

import pytest

from linuxmusterTools.passwords import (
    CharClass,
    RequireClassesRule,
    PasswordRules,
    PasswordPolicy,
    PasswordPolicyProvider,
)
from linuxmusterTools.samba_util import DomainPasswordSettings


def test_require_classes_default_count_is_all_listed_classes():
    rule = PasswordRules.build({"type": "require_classes", "classes": ["digit", "upper"]})
    assert rule.count == 2
    assert rule.classes == (CharClass.DIGIT, CharClass.UPPER)


def test_require_classes_explicit_count_still_respected():
    rule = PasswordRules.build({"type": "require_classes", "classes": ["digit", "upper"], "count": 1})
    assert rule.count == 1


def test_require_classes_count_cannot_exceed_number_of_classes():
    with pytest.raises(ValueError):
        RequireClassesRule(classes=(CharClass.DIGIT, CharClass.UPPER), count=3)


def test_default_count_all_classes_required():
    rule = RequireClassesRule(classes=(CharClass.DIGIT, CharClass.UPPER))
    assert rule.check("abc1") is False  # digit only, missing upper
    assert rule.check("ABC1") is True   # both digit and upper present


def test_merge_dedupes_require_classes_rule_regardless_of_class_order():
    same_constraint_different_order = RequireClassesRule(
        classes=(CharClass.SPECIAL, CharClass.DIGIT, CharClass.UPPER, CharClass.LOWER), count=3
    )
    samba_floor_rule = RequireClassesRule(
        classes=(CharClass.LOWER, CharClass.UPPER, CharClass.DIGIT, CharClass.SPECIAL), count=3
    )

    # Regression guard: a plain set()/`in` on the raw dataclasses would NOT
    # catch this as a duplicate, since `classes` is a tuple and therefore
    # order-sensitive for equality/hash, despite being the same constraint.
    assert same_constraint_different_order != samba_floor_rule
    assert hash(same_constraint_different_order) != hash(samba_floor_rule)

    merged = PasswordRules.merge((same_constraint_different_order,), (samba_floor_rule,))
    require_classes_rules = [r for r in merged if isinstance(r, RequireClassesRule)]
    assert len(require_classes_rules) == 1

    policy = PasswordPolicy(rules=merged)
    result = policy.validate("a", username="jdupont")
    # Exactly one require_classes violation, not the same constraint twice
    # under two different class orderings.
    assert sum(1 for v in result.violations if v.startswith("at least 3 of")) == 1


def _weak_config_rule():
    # Deliberately weaker than Samba's 3-of-4: satisfied by a single digit.
    return RequireClassesRule(classes=(CharClass.DIGIT,), count=1)


def test_samba_floor_enforced_when_complexity_on():
    samba_policy = PasswordPolicy.from_samba(
        DomainPasswordSettings(min_pwd_length=7, complexity=True, min_pwd_age=1, max_pwd_age=42)
    )
    merged = PasswordRules.merge((_weak_config_rule(),), samba_policy.rules)
    policy = PasswordPolicy(rules=merged)

    # Satisfies the weak config rule (has a digit) but not Samba's 3-of-4
    # (only digits, no lower/upper/special) -> must still be rejected.
    result = policy.validate("1234567", username="jdupont")
    assert result.ok is False

    # Satisfies Samba's 3-of-4 as well -> accepted.
    result = policy.validate("Abcdef1!", username="jdupont")
    assert result.ok is True


def test_no_classes_floor_when_complexity_off():
    samba_policy = PasswordPolicy.from_samba(
        DomainPasswordSettings(min_pwd_length=7, complexity=False, min_pwd_age=1, max_pwd_age=42)
    )
    assert not any(isinstance(r, RequireClassesRule) for r in samba_policy.rules)

    merged = PasswordRules.merge((_weak_config_rule(),), samba_policy.rules)
    policy = PasswordPolicy(rules=merged)

    # Only the weak config rule and the length floor apply now.
    result = policy.validate("1234567", username="jdupont")
    assert result.ok is True


def test_provider_end_to_end_floor_via_config_file(tmp_path, monkeypatch):
    config_path = tmp_path / "password_constraints.yml"
    config_path.write_text(
        "default:\n"
        "  student:\n"
        "    - {type: min_length, value: 5}\n"
        "    - {type: require_classes, classes: [digit], count: 1}\n"
    )

    import linuxmusterTools.passwords.policy as policy_module

    class FakeSambaManager:
        def get(self):
            return DomainPasswordSettings(min_pwd_length=7, complexity=True, min_pwd_age=1, max_pwd_age=42)

    monkeypatch.setattr(policy_module, "DomainPasswordSettingsManager", FakeSambaManager)

    provider = PasswordPolicyProvider(config_path=config_path)

    # Weaker than Samba on every axis (length 6 < 7, only a digit) -> rejected.
    result = provider.validate("123456", role="student", username="jdupont")
    assert result.ok is False

    # Meets Samba's floor -> accepted.
    result = provider.validate("Abcdef1!", role="student", username="jdupont")
    assert result.ok is True
