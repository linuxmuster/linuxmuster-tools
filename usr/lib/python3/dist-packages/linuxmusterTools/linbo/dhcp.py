"""
LINBO DHCP Exporter — generates and reads DHCP config data.

Supports dnsmasq proxy-DHCP config generation from host data,
and ISC DHCP config reading from linuxmuster-generated files.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .hosts import get_mtime

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"[^a-zA-Z0-9_-]")

DHCP_SUBNETS_PATH = Path("/etc/dhcp/subnets.conf")
DHCP_DEVICES_DIR = Path("/etc/dhcp/devices")


def _get_server_ip() -> str:
    """Auto-detect server IP from setup.ini.

    Raises RuntimeError if setup.ini is missing or has no serverip.
    """
    from linuxmusterTools.lmnfile import LMNFile

    with LMNFile("/var/lib/linuxmuster/setup.ini", "r") as setup:
        data = setup.read()
    ini = data.get("setup", {}) if isinstance(data, dict) else {}
    ip = ini.get("serverip", "")
    if ip:
        return ip
    raise RuntimeError(
        "Cannot determine server IP: /var/lib/linuxmuster/setup.ini "
        "missing or has no 'serverip' entry"
    )


class LinboDhcpExporter:
    """Generate and read DHCP configurations."""

    def generate_dnsmasq_proxy(
        self,
        hosts: list[dict],
        server_ip: str | None = None,
    ) -> str:
        """Generate dnsmasq proxy-DHCP config from host list.

        Args:
            hosts: List of host dicts with 'pxeEnabled', 'mac', 'hostgroup'
            server_ip: TFTP/boot server IP (auto-detected from setup.ini if None)

        Returns:
            The complete dnsmasq configuration as a string.
        """
        if server_ip is None:
            server_ip = _get_server_ip()

        # Derive network address from server IP (replace last octet with 0)
        parts = server_ip.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid server IP format: {server_ip}")
        dhcp_range = f"{parts[0]}.0"

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        pxe_hosts = [h for h in hosts if h["pxeEnabled"]]

        lines = [
            "#",
            "# LINBO - dnsmasq Configuration (proxy mode)",
            f"# Generated: {ts}",
            f"# Hosts: {len(pxe_hosts)}",
            "#",
            "",
            "# Proxy DHCP mode - no IP assignment, PXE only",
            "port=0",
            f"dhcp-range={dhcp_range},proxy",
            "log-dhcp",
            "",
            "interface=eth0",
            "bind-interfaces",
            "",
            "# PXE boot architecture detection",
            "dhcp-match=set:bios,option:client-arch,0",
            "dhcp-match=set:efi32,option:client-arch,6",
            "dhcp-match=set:efi64,option:client-arch,7",
            "dhcp-match=set:efi64,option:client-arch,9",
            "",
            f"dhcp-boot=tag:bios,boot/grub/i386-pc/core.0,{server_ip}",
            f"dhcp-boot=tag:efi32,boot/grub/i386-efi/core.efi,{server_ip}",
            f"dhcp-boot=tag:efi64,boot/grub/x86_64-efi/core.efi,{server_ip}",
            "",
        ]

        if pxe_hosts:
            config_groups: dict[str, list[dict]] = {}
            for h in pxe_hosts:
                config_groups.setdefault(h["hostgroup"], []).append(h)

            lines.append("# Host config assignments")
            for h in pxe_hosts:
                tag = _TAG_RE.sub("_", h["hostgroup"])
                lines.append(f"dhcp-host={h['mac']},set:{tag}")
            lines.append("")

            lines.append("# Config name via NIS-Domain (Option 40)")
            for config_name in config_groups:
                if config_name:
                    tag = _TAG_RE.sub("_", config_name)
                    lines.append(f"dhcp-option=tag:{tag},40,{config_name}")
            lines.append("")

        return "\n".join(lines)

    def get_isc_dhcp(self, school: str = "default-school") -> dict:
        """Read ISC DHCP config files for a school.

        Returns dict with subnets, devices content, and mtimes.
        subnets.conf is shared (not per-school).
        devices/{school}.conf is per-school.
        """
        devices_path = DHCP_DEVICES_DIR / f"{school}.conf"

        subnets = ""
        if DHCP_SUBNETS_PATH.is_file():
            try:
                subnets = DHCP_SUBNETS_PATH.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read subnets.conf: %s", exc)

        devices = ""
        if devices_path.is_file():
            try:
                devices = devices_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read %s: %s", devices_path, exc)
        else:
            logger.info("No DHCP devices config for school %s at %s", school, devices_path)

        subnets_mtime = get_mtime(DHCP_SUBNETS_PATH)
        devices_mtime = get_mtime(devices_path)

        return {
            "school": school,
            "subnets": subnets,
            "devices": devices,
            "subnetsUpdatedAt": subnets_mtime.isoformat() if subnets_mtime else None,
            "devicesUpdatedAt": devices_mtime.isoformat() if devices_mtime else None,
        }

    @staticmethod
    def content_etag(content: str) -> str:
        """Generate ETag for content string."""
        return hashlib.md5(content.encode()).hexdigest()
