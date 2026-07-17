import pytest

from linuxmusterTools.linbo.driver_matching import (
    MatchConfigError,
    MatchRule,
    build_match_rule,
    matches_dmi,
    parse_match_conf,
    serialize_match_conf,
)


def test_parses_canonical_repeated_products():
    rule = parse_match_conf(
        "[match]\n"
        "vendor = LENOVO\n"
        "product = 21L4\n"
        "product = 21L5\n"
    )

    assert rule.vendor == "LENOVO"
    assert rule.products == ("21L4", "21L5")
    assert rule.schema == "canonical"


def test_parses_consistent_legacy_schema():
    rule = parse_match_conf(
        "[match]\n"
        "sys_vendor = Dell Inc.\n"
        "product_name = Latitude 5520\n"
        "product_name = Latitude 5530\n"
    )

    assert rule.as_dict() == {
        "vendor": "Dell Inc.",
        "products": ["Latitude 5520", "Latitude 5530"],
        "schema": "legacy",
    }


@pytest.mark.parametrize(
    "content",
    [
        "[match]\nsys_vendor = Dell\nproduct = Latitude\n",
        "[match]\nvendor = Dell\nproduct_name = Latitude\n",
        "[match]\nvendor = Dell\nsys_vendor = Dell\n",
    ],
)
def test_rejects_mixed_alias_families(content):
    with pytest.raises(MatchConfigError, match="must not be mixed"):
        parse_match_conf(content)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("vendor = Dell\n", r"missing \[match\]"),
        ("[match]\nproduct = X1\n", "missing vendor"),
        ("[match]\nvendor = Dell\nvendor = HP\n", "duplicate vendor"),
        ("[match]\nvendor = Dell\nunknown = X1\n", "unsupported match key"),
        ("[match]\nvendor = Dell\nproduct\n", "malformed match entry"),
        ("[match]\nvendor = \n", "must not be empty"),
        ("[match]\nvendor = Dell\nproduct = \n", "must not be empty"),
    ],
)
def test_malformed_configuration_fails_closed(content, message):
    with pytest.raises(MatchConfigError, match=message):
        parse_match_conf(content)


def test_ignores_other_ini_sections_and_accepts_comments():
    rule = parse_match_conf(
        "# generated\n"
        "[other]\n"
        "vendor = ignored\n"
        "[Match]\n"
        "; administrator note\n"
        "vendor = Micro-Star International Co., Ltd.\n"
        "product = *\n"
    )

    assert rule.vendor == "Micro-Star International Co., Ltd."
    assert rule.products == ("*",)


def test_serializer_always_writes_canonical_schema():
    content = serialize_match_conf("Dell Inc.", ["Latitude 5520", "Latitude 5530"])

    assert content == (
        "[match]\n"
        "vendor = Dell Inc.\n"
        "product = Latitude 5520\n"
        "product = Latitude 5530\n"
    )
    assert "sys_vendor" not in content
    assert "product_name" not in content


def test_structured_products_are_deduplicated_in_order():
    rule = build_match_rule("Dell", ["5520", "5520", "5530"])
    assert rule.products == ("5520", "5530")


@pytest.mark.parametrize("products", [None, []])
def test_structured_rules_require_an_explicit_product(products):
    with pytest.raises(MatchConfigError, match="explicit wildcard"):
        build_match_rule("Dell", products)


def test_parsed_rules_require_an_explicit_product():
    with pytest.raises(MatchConfigError, match="product = \\*"):
        parse_match_conf("[match]\nvendor = Dell\n")


@pytest.mark.parametrize(
    "value",
    ["Dell\nproduct = *", "Dell; rm -rf /", "Dell$USER", "Dell[abc]"],
)
def test_rejects_unsafe_structured_values(value):
    with pytest.raises(MatchConfigError):
        build_match_rule(value)


def test_matching_semantics_are_exact_vendor_and_product_or_substrings():
    rule = build_match_rule("LENOVO", ["21L4", "ThinkPad X1"])

    assert matches_dmi(rule, "LENOVO", "21L4S00P00") is True
    assert matches_dmi(rule, "LENOVO", "ThinkPad X1 Carbon Gen 12") is True
    assert matches_dmi(rule, "lenovo", "21L4S00P00") is False
    assert matches_dmi(rule, "LENOVO", "ThinkCentre M90") is False


def test_matching_wildcards_require_explicit_product_wildcard():
    assert matches_dmi(build_match_rule("*", ["Latitude"]), "Dell", "Latitude 5520") is True
    assert matches_dmi(build_match_rule("Dell", ["*"]), "Dell", "Anything") is True
    assert matches_dmi(build_match_rule("*", ["Never"]), "Dell", "Latitude") is False
    assert matches_dmi(MatchRule(vendor="Dell", products=()), "Dell", "Anything") is False
