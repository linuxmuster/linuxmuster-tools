"""Centralized validation helpers backed by upstream NameChecker."""

from linuxmusterTools.common.checks import NameChecker

_checker = NameChecker()


def _check_segmented_name(name: str, check_part) -> bool:
    """Allow dot-separated names while validating each segment upstream-style."""
    if not isinstance(name, str) or not name:
        return False
    if "/" in name or "\\" in name or "\0" in name or ".." in name:
        return False

    parts = name.split(".")
    return all(part and check_part(part) for part in parts)


def check_ip(ip: str) -> bool:
    """Validate IPv4 address."""
    return _checker.check_ip_name(ip)


def check_mac(mac: str) -> bool:
    """Validate MAC address (colon or hyphen separated)."""
    if not isinstance(mac, str) or not mac:
        return False
    value = mac.strip()
    return _checker.check_mac1_name(value) or _checker.check_mac2_name(value)


def normalize_mac(mac: str) -> str | None:
    """Normalize MAC to uppercase colon-separated. Returns None if invalid."""
    if not isinstance(mac, str) or not mac:
        return None
    normalized = _checker.normalize_mac(mac.strip())
    if normalized is None:
        return None
    return normalized.upper()


def check_linbo_image_name(name: str) -> bool:
    """Validate LINBO image name."""
    return _check_segmented_name(name, _checker.check_linbo_image_name)


def check_linbo_conf_name(name: str) -> bool:
    """Validate LINBO config / group name."""
    return _check_segmented_name(name, _checker.check_linbo_conf_name)
