"""
LINBO Host Provider — reads host data from devices.csv.

Provides school-aware access to host records with MAC normalization,
IP validation, and batch lookup functionality.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from ._validation import check_mac, check_ip, normalize_mac

logger = logging.getLogger(__name__)


def validate_school(school: str) -> bool:
    """Validate school name to prevent path traversal."""
    from ._validation import check_linbo_conf_name
    return check_linbo_conf_name(school)


def get_mtime(path: Path) -> datetime | None:
    """Return file mtime as UTC datetime, or None if missing."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def devices_csv_path(school: str = "default-school") -> Path:
    """Resolve devices.csv path for a given school (LMN convention)."""
    if school != "default-school":
        prefix = f"{school}."
    else:
        prefix = ""
    return Path(f"/etc/linuxmuster/sophomorix/{school}/{prefix}devices.csv")


class LinboHostProvider:
    """Read-only host provider from devices.csv."""

    def __init__(self, school: str = "default-school"):
        self.school = school

    def parse_devices_csv(self) -> tuple[list[dict], datetime | None]:
        """Parse devices.csv into a list of host dicts.

        Returns (hosts, file_mtime). Skips comment lines and invalid MACs.
        CSV columns (semicolon-separated):
          0=room, 1=hostname, 2=hostgroup, 3=mac, 4=ip, 10=pxeFlag

        Raises FileNotFoundError if devices.csv does not exist.
        """
        csv_path = devices_csv_path(self.school)
        text = csv_path.read_text(encoding="utf-8")
        mtime = get_mtime(csv_path)
        hosts = []

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            fields = line.split(";")
            if len(fields) < 5:
                continue

            while len(fields) < 15:
                fields.append("")

            mac = normalize_mac(fields[3])
            if mac is None:
                continue

            raw_ip = fields[4].strip()
            ip = raw_ip if raw_ip and check_ip(raw_ip) else None
            config = fields[2].strip()

            try:
                pxe_flag = int(fields[10].strip()) if fields[10].strip() else 1
            except ValueError:
                pxe_flag = 1

            pxe_enabled = pxe_flag > 0 and config.lower() != "nopxe"

            hosts.append({
                "mac": mac,
                "hostname": fields[1].strip(),
                "ip": ip,
                "room": fields[0].strip(),
                "school": self.school,
                "hostgroup": config,
                "pxeEnabled": pxe_enabled,
                "pxeFlag": pxe_flag,
                "dhcpOptions": "",
                "startConfId": config,
                "updatedAt": mtime.isoformat() if mtime else None,
            })

        return hosts, mtime

    def get_hosts_by_macs(self, macs: list[str]) -> list[dict]:
        """Return host records matching the given MAC addresses."""
        hosts, _ = self.parse_devices_csv()
        macs_upper = {m.upper().replace("-", ":") for m in macs}
        return [h for h in hosts if h["mac"] in macs_upper]

    def get_all_host_macs(self) -> list[str]:
        """Return all known MAC addresses."""
        hosts, _ = self.parse_devices_csv()
        return [h["mac"] for h in hosts]

    def get_school_groups(self) -> set[str]:
        """Return set of unique hostgroup names for this school."""
        hosts, _ = self.parse_devices_csv()
        return {h["hostgroup"] for h in hosts}
