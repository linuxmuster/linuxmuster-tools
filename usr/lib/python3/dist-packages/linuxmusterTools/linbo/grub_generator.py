"""
LINBO GRUB Config Generator — generate GRUB boot configs from data objects.

Pure template-based generation:
- Main grub.cfg (PXE boot with MAC→group mapping)
- Per-config {group}.cfg (OS menu entries)
- Hostcfg symlinks (hostname.cfg + 01-{mac}.cfg)

Device path translation, OS type detection, template variable substitution.
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

LINBO_DIR = os.environ.get("LINBO_DIR", "/srv/linbo")
GRUB_DIR = Path(LINBO_DIR) / "boot" / "grub"
HOSTCFG_DIR = GRUB_DIR / "hostcfg"


# ── Pure Helper Functions ────────────────────────────────────────────


def get_grub_part(device: str | None) -> str:
    """Convert Linux device path to GRUB partition format.

    /dev/sda1 → (hd0,1), /dev/nvme0n1p2 → (hd0,2), /dev/mmcblk0p1 → (hd0,1)
    """
    if not device:
        return "(hd0,1)"
    dev = device.replace("/dev/", "")

    m = re.match(r"^nvme(\d+)n\d+p(\d+)$", dev)
    if m:
        return f"(hd{m.group(1)},{m.group(2)})"

    m = re.match(r"^mmcblk(\d+)p(\d+)$", dev)
    if m:
        return f"(hd{m.group(1)},{m.group(2)})"

    m = re.match(r"^([shv]d)([a-z])(\d+)$", dev)
    if m:
        disk_num = ord(m.group(2)) - ord("a")
        return f"(hd{disk_num},{m.group(3)})"

    return "(hd0,1)"


def get_grub_ostype(osname: str | None) -> str:
    """Get GRUB OS type from OS name for menu icon classes."""
    if not osname:
        return "unknown"
    name = osname.lower()

    os_map = [
        ("windows 11", "win11"), ("win11", "win11"),
        ("windows 10", "win10"), ("win10", "win10"),
        ("windows 8", "win8"), ("win8", "win8"),
        ("windows 7", "win7"), ("win7", "win7"),
        ("windows", "windows"),
        ("ubuntu", "ubuntu"), ("debian", "debian"),
        ("mint", "linuxmint"), ("fedora", "fedora"),
        ("opensuse", "opensuse"), ("suse", "opensuse"),
        ("arch", "arch"), ("manjaro", "manjaro"),
        ("centos", "centos"),
        ("rhel", "rhel"), ("red hat", "rhel"),
        ("linux", "linux"),
    ]
    for pattern, ostype in os_map:
        if pattern in name:
            return ostype
    return "unknown"


def find_cache_partition(partitions: list[dict] | None) -> dict | None:
    """Find cache partition from partition list."""
    if not partitions or not isinstance(partitions, list):
        return None

    by_label = next((p for p in partitions
                     if p.get("label", "").lower() == "cache"), None)
    if by_label:
        return by_label

    return next((p for p in partitions
                 if p.get("fsType") in ("ext4", "btrfs")
                 and p.get("partitionId") not in ("ef00", "0c01")
                 and "windows" not in (p.get("label") or "").lower()
                 and "efi" not in (p.get("label") or "").lower()), None)


def get_os_partition_index(partitions: list[dict] | None, root_device: str | None) -> int:
    """Find 1-based partition index for an OS's root device."""
    if not partitions or not root_device:
        return 1
    for i, p in enumerate(partitions):
        if p.get("device") == root_device:
            return i + 1
    return 1


def hex_to_grub_rgb(hex_color: str | None) -> str:
    """Convert hex color (#RRGGBB) to GRUB RGB format (R,G,B)."""
    if not hex_color or not re.match(r"^#[0-9a-fA-F]{6}$", hex_color):
        return "42,68,87"
    return ",".join(str(int(hex_color[i:i+2], 16)) for i in (1, 3, 5))


def get_os_label(partitions: list[dict] | None, root_device: str | None) -> str:
    """Get partition label for a root device."""
    if not partitions or not root_device:
        return ""
    p = next((p for p in partitions if p.get("device") == root_device), None)
    return (p or {}).get("label", "")


def apply_template(template: str, replacements: dict) -> str:
    """Replace @@key@@ placeholders in template."""
    result = template
    for key, value in replacements.items():
        result = result.replace(f"@@{key}@@", str(value) if value is not None else "")
    return result


def mac_to_grub_filename(mac: str) -> str:
    """Convert MAC to GRUB hostcfg filename: AA:BB:CC:DD:EE:FF → 01-aa-bb-cc-dd-ee-ff"""
    return "01-" + mac.lower().replace(":", "-")


def get_linbo_setting(settings: dict | None, key: str):
    """Case-insensitive lookup in linbo settings dict."""
    if not settings:
        return None
    if key in settings:
        return settings[key]
    lower = key.lower()
    if lower in settings:
        return settings[lower]
    for k, v in settings.items():
        if k.lower() == lower:
            return v
    return None


def read_kernel_options(config_id: str, linbo_dir: str | None = None) -> str:
    """Read KernelOptions from start.conf file."""
    base = Path(linbo_dir or LINBO_DIR)
    try:
        content = (base / f"start.conf.{config_id}").read_text(encoding="utf-8")
        m = re.search(r"^\s*KernelOptions\s*=\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except OSError:
        pass
    return "quiet splash"


def build_kernel_options(raw_options: str, server: str, config_id: str) -> str:
    """Build clean kernel options string with server and group injected."""
    kopts = re.sub(r"\bserver=\S+", "", raw_options)
    kopts = re.sub(r"\bgroup=\S+", "", kopts)
    kopts = re.sub(r"\bgroup=\S+", "", kopts)
    kopts = re.sub(r"\s+", " ", kopts).strip()
    return f"{kopts} server={server} group={config_id} group={config_id}".strip()
