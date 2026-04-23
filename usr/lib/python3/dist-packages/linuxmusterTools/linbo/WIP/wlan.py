"""
LINBO WLAN Configuration — manage wireless network settings for linbofs.

Reads and writes wpa_supplicant configuration for LINBO clients.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "/etc/linuxmuster/linbo/wlan.conf"


class LinboWlanConfig:
    """Manage WLAN configuration for LINBO clients."""

    def __init__(self, config_path: str | None = None):
        self.config_path = Path(config_path or DEFAULT_CONFIG_PATH)

    def get_config(self) -> dict:
        """Read WLAN configuration.

        Returns:
            {enabled, ssid, keyMgmt, hasPsk, scanSsid} — PSK is never returned
        """
        if not self.config_path.is_file():
            return {"enabled": False, "ssid": "", "keyMgmt": "NONE", "hasPsk": False}

        try:
            content = self.config_path.read_text(encoding="utf-8")
        except OSError:
            return {"enabled": False, "ssid": "", "keyMgmt": "NONE", "hasPsk": False}

        ssid = ""
        key_mgmt = "NONE"
        has_psk = False
        scan_ssid = False

        for line in content.splitlines():
            line = line.strip()
            m = re.match(r'ssid="(.+)"', line)
            if m:
                ssid = m.group(1)
            if re.match(r"key_mgmt=", line):
                key_mgmt = line.split("=", 1)[1].strip()
            if re.match(r'psk="', line) or re.match(r"psk=", line):
                has_psk = True
            if re.match(r"scan_ssid=1", line):
                scan_ssid = True

        return {
            "enabled": bool(ssid),
            "ssid": ssid,
            "keyMgmt": key_mgmt,
            "hasPsk": has_psk,
            "scanSsid": scan_ssid,
        }

    def update_config(
        self,
        ssid: str,
        key_mgmt: str = "WPA-PSK",
        psk: str | None = None,
        scan_ssid: bool = False,
    ) -> dict:
        """Write WLAN configuration.

        Args:
            ssid: Network SSID (1-32 chars)
            key_mgmt: Key management (WPA-PSK or NONE)
            psk: Pre-shared key (required for WPA-PSK)
            scan_ssid: Enable scan_ssid=1 for hidden networks

        Returns:
            Updated config dict

        Raises:
            ValueError: If parameters are invalid
        """
        if not ssid or len(ssid) > 32:
            raise ValueError("SSID must be 1-32 characters")
        if key_mgmt not in ("WPA-PSK", "NONE"):
            raise ValueError("keyMgmt must be WPA-PSK or NONE")
        if key_mgmt == "WPA-PSK" and not psk:
            raise ValueError("PSK required for WPA-PSK")
        if psk and len(psk) > 128:
            raise ValueError("PSK must be max 128 characters")

        lines = [
            "# LINBO WLAN configuration",
            "# Managed by linuxmuster-tools",
            "network={",
            f'    ssid="{ssid}"',
            f"    key_mgmt={key_mgmt}",
        ]
        if psk and key_mgmt == "WPA-PSK":
            lines.append(f'    psk="{psk}"')
        if scan_ssid:
            lines.append("    scan_ssid=1")
        lines.append("}")

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return self.get_config()

    def reset_config(self) -> bool:
        """Delete WLAN configuration.

        Returns:
            True if file was deleted
        """
        if self.config_path.is_file():
            self.config_path.unlink()
            return True
        return False
