"""Strict parsing and matching for LINBO Windows driver profiles.

The canonical on-disk format is::

    [match]
    vendor = LENOVO
    product = 21L4
    product = 21L5

For migration purposes the legacy ``sys_vendor``/``product_name`` spelling is
accepted when it is used consistently.  Mixing legacy and canonical keys is
rejected so a manually edited profile can never broaden its match silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


__all__ = [
    "MatchConfigError",
    "MatchRule",
    "build_match_rule",
    "matches_dmi",
    "parse_match_conf",
    "serialize_match_conf",
]


MAX_MATCH_CONF_BYTES = 64 * 1024
MAX_MATCH_VALUE_LENGTH = 512
MAX_PRODUCTS = 256

_MATCH_VALUE_RE = re.compile(r"^[a-zA-Z0-9 .,()/_+#-]*$")
_SECTION_RE = re.compile(r"^\[([a-zA-Z0-9_.-]+)\]$")
_CANONICAL_KEYS = {"vendor", "product"}
_LEGACY_KEYS = {"sys_vendor", "product_name"}


class MatchConfigError(ValueError):
    """Raised when a ``match.conf`` is malformed or ambiguous."""


@dataclass(frozen=True)
class MatchRule:
    """Normalized DMI matching rule.

    ``schema`` records how a file was read.  Newly serialized configurations
    always use ``canonical``.
    """

    vendor: str
    products: tuple[str, ...]
    schema: str = "canonical"

    def as_dict(self) -> dict:
        """Return an API-friendly representation."""

        return {
            "vendor": self.vendor,
            "products": list(self.products),
            "schema": self.schema,
        }


def _normalize_value(value: str, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise MatchConfigError(f"{field} must be a string")

    normalized = value.strip()
    if not normalized and not allow_empty:
        raise MatchConfigError(f"{field} must not be empty")
    if len(normalized) > MAX_MATCH_VALUE_LENGTH:
        raise MatchConfigError(
            f"{field} is too long ({len(normalized)} characters, "
            f"max {MAX_MATCH_VALUE_LENGTH})"
        )
    if normalized != "*" and not _MATCH_VALUE_RE.fullmatch(normalized):
        raise MatchConfigError(f"{field} contains unsupported characters")
    return normalized


def _normalize_products(products: Sequence[str] | None) -> tuple[str, ...]:
    if products is None:
        raise MatchConfigError(
            "at least one product rule is required; use '*' for an explicit wildcard"
        )
    if isinstance(products, (str, bytes)):
        raise MatchConfigError("products must be a sequence of strings")
    if not products:
        raise MatchConfigError(
            "at least one product rule is required; use '*' for an explicit wildcard"
        )
    if len(products) > MAX_PRODUCTS:
        raise MatchConfigError(
            f"too many product rules ({len(products)}, max {MAX_PRODUCTS})"
        )

    normalized = []
    seen = set()
    for index, product in enumerate(products):
        value = _normalize_value(product, f"product[{index}]")
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    return tuple(normalized)


def build_match_rule(
    vendor: str,
    products: Sequence[str] | None = None,
) -> MatchRule:
    """Validate structured input and build a canonical matching rule."""

    return MatchRule(
        vendor=_normalize_value(vendor, "vendor"),
        products=_normalize_products(products),
        schema="canonical",
    )


def parse_match_conf(content: str) -> MatchRule:
    """Parse ``match.conf`` strictly and fail closed on ambiguity.

    Entries outside ``[match]`` are ignored for compatibility with ordinary
    INI files.  Inside ``[match]`` only one complete key family is allowed:
    ``vendor``/``product`` or ``sys_vendor``/``product_name``.
    """

    if not isinstance(content, str):
        raise MatchConfigError("match.conf content must be a string")
    if len(content.encode("utf-8")) > MAX_MATCH_CONF_BYTES:
        raise MatchConfigError(
            f"match.conf is too large (max {MAX_MATCH_CONF_BYTES} bytes)"
        )

    in_match = False
    found_match = False
    vendor = None
    products: list[str] = []
    schema = None

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue

        if line.startswith("["):
            section = _SECTION_RE.fullmatch(line)
            if section is None:
                raise MatchConfigError(f"malformed section at line {line_number}")
            section_name = section.group(1).lower()
            if section_name == "match":
                if found_match:
                    raise MatchConfigError("duplicate [match] section")
                found_match = True
                in_match = True
            else:
                in_match = False
            continue

        if not in_match:
            continue
        if "=" not in line:
            raise MatchConfigError(f"malformed match entry at line {line_number}")

        raw_key, raw_value = line.split("=", 1)
        key = raw_key.strip().lower()
        if key in _CANONICAL_KEYS:
            key_schema = "canonical"
        elif key in _LEGACY_KEYS:
            key_schema = "legacy"
        else:
            raise MatchConfigError(
                f"unsupported match key '{key or '<empty>'}' at line {line_number}"
            )

        if schema is None:
            schema = key_schema
        elif schema != key_schema:
            raise MatchConfigError("canonical and legacy match keys must not be mixed")

        if key in {"vendor", "sys_vendor"}:
            if vendor is not None:
                raise MatchConfigError("duplicate vendor entry")
            vendor = _normalize_value(raw_value, "vendor")
        else:
            if len(products) >= MAX_PRODUCTS:
                raise MatchConfigError(f"too many product rules (max {MAX_PRODUCTS})")
            products.append(_normalize_value(raw_value, f"product at line {line_number}"))

    if not found_match:
        raise MatchConfigError("missing [match] section")
    if vendor is None:
        raise MatchConfigError("missing vendor entry")
    if not products:
        raise MatchConfigError(
            "missing product entry; use product = * for an explicit wildcard"
        )

    return MatchRule(vendor=vendor, products=tuple(products), schema=schema or "canonical")


def serialize_match_conf(
    vendor: str,
    products: Sequence[str] | None = None,
) -> str:
    """Serialize structured input using the canonical key spelling."""

    rule = build_match_rule(vendor, products)
    lines = ["[match]", f"vendor = {rule.vendor}"]
    lines.extend(f"product = {product}" for product in rule.products)
    return "\n".join(lines) + "\n"


def matches_dmi(rule: MatchRule, sys_vendor: str, product_name: str) -> bool:
    """Return whether a normalized rule matches the supplied DMI values.

    Vendor comparison is exact and case-sensitive.  Product rules are
    case-sensitive substring matches combined with OR.  Product matching is
    fail-closed: only an explicit ``*`` accepts every product of a matching
    vendor.
    """

    if not isinstance(rule, MatchRule):
        raise TypeError("rule must be a MatchRule")
    if not isinstance(sys_vendor, str) or not isinstance(product_name, str):
        return False

    current_vendor = sys_vendor.strip()
    current_product = product_name.strip()
    if rule.vendor != "*" and rule.vendor != current_vendor:
        return False
    if not rule.products:
        return False
    return any(
        product == "*" or product in current_product
        for product in rule.products
    )
