"""
Centralized validation — delegates to upstream NameChecker when available.

Uses linuxmusterTools.common.checks.NameChecker for name/IP/MAC validation
with local regex fallback for development environments without upstream.
"""

import re

try:
    from linuxmusterTools.common.checks import NameChecker
    _checker = NameChecker()
    UPSTREAM_AVAILABLE = True
except ImportError:
    _checker = None
    UPSTREAM_AVAILABLE = False

# Fallback regex (only used when upstream is not installed)
_MAC_RE = re.compile(r"^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$")
_IP_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def check_ip(ip: str) -> bool:
    """Validate IPv4 address."""
    if not ip:
        return False
    if _checker:
        return _checker.check_ip_name(ip)
    return bool(_IP_RE.match(ip))


def check_mac(mac: str) -> bool:
    """Validate MAC address (colon or hyphen separated)."""
    if not mac:
        return False
    if _checker:
        return _checker.check_mac1_name(mac.strip()) or _checker.check_mac2_name(mac.strip())
    return bool(_MAC_RE.match(mac.strip()))


def normalize_mac(mac: str) -> str | None:
    """Normalize MAC to uppercase colon-separated. Returns None if invalid."""
    if not mac:
        return None
    if _checker:
        return _checker.normalize_mac(mac)
    mac = mac.strip()
    if not _MAC_RE.match(mac):
        return None
    return mac.upper().replace("-", ":")


def check_linbo_image_name(name: str) -> bool:
    """Validate LINBO image name."""
    if not name:
        return False
    if _checker:
        return _checker.check_linbo_image_name(name)
    return bool(_SAFE_NAME_RE.match(name))


def check_linbo_conf_name(name: str) -> bool:
    """Validate LINBO config / group name."""
    if not name:
        return False
    if _checker:
        return _checker.check_linbo_conf_name(name)
    return bool(_SAFE_NAME_RE.match(name))
