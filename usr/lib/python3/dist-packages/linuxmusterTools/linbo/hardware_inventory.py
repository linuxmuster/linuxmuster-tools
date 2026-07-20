"""Read DMI information uploaded by LINBO clients.

LINBO stores one compressed ``<hostname>_hwinfo.gz`` file per client in
``/var/log/linuxmuster/linbo``.  The inventory manager combines these files
with the school-scoped client records already provided by :class:`Devices`.
It is read-only and deliberately independent from driver profiles and hooks.
"""

from __future__ import annotations

import gzip
import logging
import re
from pathlib import Path
from typing import Any, Mapping

from ..common.checks import NameChecker
from ..common.timestamps import get_utc_mtime
from ..devices import Devices


logger = logging.getLogger(__name__)
name_checker = NameChecker()

DEFAULT_HWINFO_DIR = Path("/var/log/linuxmuster/linbo")
DEFAULT_SCHOOL = "default-school"
MAX_COMPRESSED_HWINFO_BYTES = 8 * 1024 * 1024
MAX_HWINFO_BYTES = 32 * 1024 * 1024

_DMI_TYPE_RE = re.compile(
    r"^[ \t]*type[ \t]+0x([0-9a-f]+)\b"
    r"(?:[ \t]+\[[^\]\r\n]*\])?"
    r"(?:[ \t]*:[ \t]*([0-9a-f]{2}(?:[ \t]+[0-9a-f]{2})*))?"
    r"[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_DMI_STRING_RE = re.compile(
    r'^[ \t]*str(\d+):[ \t]*"([^"\r\n]*)"[ \t]*$',
    re.IGNORECASE | re.MULTILINE,
)


def parse_dmi(text: str) -> dict[str, str | None] | None:
    """Return SMBIOS system vendor, product and version from hwinfo output."""

    blocks = list(_DMI_TYPE_RE.finditer(text))
    type_one_index = next(
        (index for index, block in enumerate(blocks) if block.group(1).lower() == "01"),
        None,
    )
    if type_one_index is None:
        return None

    type_one = blocks[type_one_index]
    raw_header = type_one.group(2)
    if raw_header is None:
        return None

    try:
        header = bytes.fromhex(raw_header)
    except ValueError:
        return None
    if len(header) < 7 or header[0] != 0x01 or header[1] < 7:
        return None

    block_end = (
        blocks[type_one_index + 1].start()
        if type_one_index + 1 < len(blocks)
        else len(text)
    )
    block_text = text[type_one.start() : block_end]
    strings = {
        int(match.group(1)): match.group(2).strip()
        for match in _DMI_STRING_RE.finditer(block_text)
    }

    def indexed_string(index: int) -> str | None:
        if index == 0:
            return None
        return strings.get(index) or None

    result = {
        "vendor": indexed_string(header[4]),
        "product": indexed_string(header[5]),
        "version": indexed_string(header[6]),
    }
    return result if any(result.values()) else None


def _read_hwinfo(path: Path) -> str:
    """Read one gzip inventory with compressed and decompressed-size limits."""

    if path.stat().st_size > MAX_COMPRESSED_HWINFO_BYTES:
        raise ValueError(
            "Compressed LINBO hardware inventory exceeds "
            f"{MAX_COMPRESSED_HWINFO_BYTES} bytes"
        )

    with gzip.open(path, "rb") as stream:
        content = stream.read(MAX_HWINFO_BYTES + 1)
    if len(content) > MAX_HWINFO_BYTES:
        raise ValueError(f"LINBO hardware inventory exceeds {MAX_HWINFO_BYTES} bytes")
    return content.decode("utf-8", errors="replace")


class LinboHardwareInventoryManager:
    """List and read school-scoped LINBO hardware inventories."""

    def __init__(
        self,
        school: str = DEFAULT_SCHOOL,
        hwinfo_dir: str | Path = DEFAULT_HWINFO_DIR,
    ) -> None:
        if not name_checker.check_group_name(school):
            raise ValueError(f"Invalid school name: {school}")

        self.school = school
        self.hwinfo_dir = Path(hwinfo_dir)
        self.devices = Devices(school=school)

    def _inventory_path(self, hostname: str) -> Path:
        if not name_checker.check_host_name(hostname):
            raise ValueError(f"Invalid hostname: {hostname}")

        inventory_hostname = hostname
        if self.school != DEFAULT_SCHOOL:
            inventory_hostname = f"{self.school}-{hostname}"
        return self.hwinfo_dir / f"{inventory_hostname}_hwinfo.gz"

    def _read_client(self, client: Mapping[str, Any]) -> dict[str, Any] | None:
        hostname = client.get("hostname")
        if not isinstance(hostname, str):
            logger.warning("Ignoring LINBO client without a valid hostname")
            return None

        try:
            path = self._inventory_path(hostname)
        except ValueError as error:
            logger.warning("Ignoring LINBO client: %s", error)
            return None

        if not path.is_file():
            return None

        try:
            dmi = parse_dmi(_read_hwinfo(path))
        except (EOFError, OSError, ValueError) as error:
            logger.warning(
                "Could not read LINBO hardware inventory %s: %s",
                path.name,
                error,
            )
            return None

        captured_at = get_utc_mtime(path)
        return {
            "hostname": hostname,
            "school": self.school,
            "room": client.get("room"),
            "group": client.get("group"),
            "mac": client.get("mac"),
            "ip": client.get("ip"),
            "capturedAt": captured_at.isoformat() if captured_at else None,
            "dmi": dmi,
        }

    def list(self) -> list[dict[str, Any]]:
        """Return readable inventories for the school's configured clients."""

        inventories = []
        for client in self.devices.get_clients():
            inventory = self._read_client(client)
            if inventory is not None:
                inventories.append(inventory)
        return inventories

    def get(self, hostname: str) -> dict[str, Any] | None:
        """Return one configured client's inventory, or ``None`` if absent."""

        if not name_checker.check_host_name(hostname):
            raise ValueError(f"Invalid hostname: {hostname}")

        client = self.devices.get_client(hostname)
        return self._read_client(client) if client is not None else None


__all__ = [
    "LinboHardwareInventoryManager",
    "parse_dmi",
]
