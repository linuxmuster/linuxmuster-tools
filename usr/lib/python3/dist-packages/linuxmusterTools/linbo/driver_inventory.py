"""Read-only access to server-side LINBO hardware inventories.

LINBO writes one ``<hostname>_hwinfo.gz`` file per client below
``/var/log/linuxmuster/linbo``.  This module reads those files without invoking
external commands and optionally joins the host metadata from Sophomorix'
school-specific ``Devices`` provider.

The result dictionaries deliberately retain the existing camelCase field
names. This keeps inventory consumers data-compatible while leaving HTTP
concerns outside ``linuxmusterTools``.
"""

from __future__ import annotations

import errno
import gzip
import io
import logging
import math
import os
import re
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..devices import Devices
from .driver_storage import read_bytes_limited


logger = logging.getLogger(__name__)

DEFAULT_HWINFO_DIR = "/var/log/linuxmuster/linbo"
DEFAULT_SCHOOL = "default-school"
DEFAULT_STALE_HOURS = 7 * 24

# Real inventories are normally well below one MiB.  These limits leave ample
# headroom while preventing unexpectedly large files and gzip bombs from
# exhausting the API process.
MAX_COMPRESSED_BYTES = 8 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024

INVENTORY_FILE_RE = re.compile(
    r"^([A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?)_hwinfo\.gz$"
)
_SCHOOL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
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
_SUMMARY_BLOCK_HEADER_RE = re.compile(
    r"^(\d+):[ \t]+(\S+)[ \t]+([^:\r\n]+):[ \t]*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def validate_school_name(school: str) -> str:
    """Validate a school identifier before passing it to ``Devices``.

    Existence is intentionally an API/LDAP concern.  The tools layer still
    rejects unsafe path components so direct callers cannot make
    ``Devices(school)`` traverse outside Sophomorix' school tree.
    """

    if not isinstance(school, str):
        raise ValueError("school must be a string")
    normalized = school.strip()
    if not _SCHOOL_NAME_RE.fullmatch(normalized):
        raise ValueError(
            "school must start with an alphanumeric character, contain only "
            "[A-Za-z0-9_-], and be at most 100 characters long"
        )
    return normalized


class InventoryFileError(OSError):
    """A bounded inventory read failed with a machine-readable reason."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: os.PathLike[str] | str | None = None,
        limit: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = os.fspath(path) if path is not None else None
        self.limit = limit


def _size_error(path: os.PathLike[str] | str, limit: int) -> InventoryFileError:
    return InventoryFileError(
        f"Size limit exceeded for {Path(path).name} ({limit} bytes)",
        code="COMPRESSED_FILE_TOO_LARGE",
        path=path,
        limit=limit,
    )


def _lexical_absolute(path: os.PathLike[str] | str) -> Path:
    """Return an absolute path without resolving or following symlinks."""

    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _read_bounded_regular_file(
    path: os.PathLike[str] | str,
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    """Read through the shared storage primitive and map domain errors."""

    file_path = _lexical_absolute(path)
    try:
        return read_bytes_limited(file_path, max_bytes)
    except OSError as error:
        if error.errno == errno.EFBIG:
            raise _size_error(file_path, max_bytes) from error
        if error.errno == errno.EINVAL:
            raise InventoryFileError(
                f"Not a regular file: {file_path.name}",
                code="NOT_REGULAR_FILE",
                path=file_path,
            ) from error
        raise


def _gunzip_bounded(compressed: bytes, max_bytes: int) -> bytes:
    """Decompress gzip data while enforcing a hard output limit."""

    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
        raise ValueError("max_bytes must be a non-negative integer")

    chunks: list[bytes] = []
    total = 0
    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
        while True:
            chunk = stream.read(min(READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise InventoryFileError(
                    f"Uncompressed hardware inventory exceeds {max_bytes} bytes",
                    code="UNCOMPRESSED_FILE_TOO_LARGE",
                    limit=max_bytes,
                )
            chunks.append(chunk)
    return b"".join(chunks)


def read_server_hardware_file(
    path: os.PathLike[str] | str,
    *,
    max_compressed_bytes: int = MAX_COMPRESSED_BYTES,
    max_uncompressed_bytes: int = MAX_UNCOMPRESSED_BYTES,
) -> tuple[str, os.stat_result]:
    """Read and decompress one LINBO inventory.

    Returns the decoded text and the stat information obtained from the open
    file descriptor. Invalid UTF-8 is replaced to preserve the established
    inventory-reader behaviour.
    """

    compressed, file_stat = _read_bounded_regular_file(path, max_compressed_bytes)
    uncompressed = _gunzip_bounded(compressed, max_uncompressed_bytes)
    return uncompressed.decode("utf-8", errors="replace"), file_stat


def parse_dmi(text: str) -> dict[str, str | None] | None:
    """Parse SMBIOS system information (type 0x01) from hwinfo output."""

    type_blocks = list(_DMI_TYPE_RE.finditer(text))
    target_index = next(
        (index for index, match in enumerate(type_blocks) if match.group(1).lower() == "01"),
        None,
    )
    if target_index is None:
        return None

    start = type_blocks[target_index].start()
    end = type_blocks[target_index + 1].start() if target_index + 1 < len(type_blocks) else len(text)
    block = text[start:end]

    # SMBIOS Type 1 stores string-table indexes at offsets 4, 5 and 6.  The
    # indexes are not guaranteed to be 1, 2 and 3: index zero explicitly means
    # "not specified", and later strings can contain the serial number or SKU.
    raw_header = type_blocks[target_index].group(2)
    if raw_header is None:
        return None
    try:
        header = bytes.fromhex(raw_header)
    except ValueError:
        return None
    if len(header) < 7 or header[0] != 0x01 or header[1] < 7:
        return None

    strings: dict[int, str] = {}
    for match in _DMI_STRING_RE.finditer(block):
        strings[int(match.group(1))] = match.group(2).strip()

    def indexed_string(index: int) -> str | None:
        if index == 0:
            return None
        return strings.get(index) or None

    dmi: dict[str, str | None] = {
        "vendor": indexed_string(header[4]),
        "product": indexed_string(header[5]),
        "version": indexed_string(header[6]),
    }
    return dmi if any(dmi.values()) else None


def _field(block: str, name: str) -> str | None:
    match = re.search(
        rf"^[ \t]*{re.escape(name)}:[ \t]*(.*?)[ \t]*$",
        block,
        re.IGNORECASE | re.MULTILINE,
    )
    return match.group(1) if match else None


def _unquote(value: str | None) -> str:
    if value is None:
        return ""
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed.startswith('"') and trimmed.endswith('"'):
        return trimmed[1:-1]
    return trimmed


def _parse_bus_id(value: str | None, bus: str) -> dict[str, str | None] | None:
    if not value:
        return None
    match = re.match(
        rf"^{re.escape(bus)}\s+0x([0-9a-f]{{1,4}})(?:\s+\"([^\"]*)\")?",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    return {
        "id": match.group(1).upper().zfill(4),
        "name": match.group(2) or None,
    }


def _parse_drivers(value: str | None) -> list[str]:
    if not value:
        return []
    quoted = re.findall(r'"([^\"]+)"', value)
    if quoted:
        return quoted
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_hardware_ids(
    bus: str,
    vendor: Mapping[str, str | None] | None,
    device: Mapping[str, str | None] | None,
    sub_vendor: Mapping[str, str | None] | None,
    sub_device: Mapping[str, str | None] | None,
) -> list[str]:
    if not vendor or not device or not vendor.get("id") or not device.get("id"):
        return []

    if bus == "PCI":
        prefix = f"PCI\\VEN_{vendor['id']}&DEV_{device['id']}"
        hardware_ids: list[str] = []
        if sub_vendor and sub_device and sub_vendor.get("id") and sub_device.get("id"):
            # Windows stores SUBSYS as SubDevice followed by SubVendor.
            hardware_ids.append(
                f"{prefix}&SUBSYS_{sub_device['id']}{sub_vendor['id']}"
            )
        hardware_ids.append(prefix)
        return hardware_ids

    return [f"USB\\VID_{vendor['id']}&PID_{device['id']}"]


def parse_hardware_devices(text: str) -> list[dict[str, Any]]:
    """Parse summarized PCI and USB devices from hwinfo output."""

    headers = list(_SUMMARY_BLOCK_HEADER_RE.finditer(text))
    devices: list[dict[str, Any]] = []

    for index, header in enumerate(headers):
        bus = header.group(2).upper()
        if bus not in {"PCI", "USB"}:
            continue

        block_end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        block = text[header.start():block_end]
        vendor = _parse_bus_id(_field(block, "Vendor"), bus)
        device = _parse_bus_id(_field(block, "Device"), bus)
        sub_vendor = _parse_bus_id(_field(block, "SubVendor"), bus) if bus == "PCI" else None
        sub_device = _parse_bus_id(_field(block, "SubDevice"), bus) if bus == "PCI" else None

        # Debug sections can contain PCI-looking lines.  A summarized device
        # is usable only when both fields carry matching bus-qualified IDs.
        if not vendor or not device:
            continue

        devices.append(
            {
                "index": int(header.group(1)),
                "bus": bus,
                "address": header.group(3).strip(),
                "description": header.group(4).strip() or None,
                "hardwareClass": _field(block, "Hardware Class"),
                "model": _unquote(_field(block, "Model")) or None,
                "vendorId": vendor["id"],
                "vendorName": vendor["name"],
                "deviceId": device["id"],
                "deviceName": device["name"],
                "subVendorId": sub_vendor["id"] if sub_vendor else None,
                "subVendorName": sub_vendor["name"] if sub_vendor else None,
                "subDeviceId": sub_device["id"] if sub_device else None,
                "subDeviceName": sub_device["name"] if sub_device else None,
                "drivers": _parse_drivers(_field(block, "Driver")),
                "moduleAlias": _unquote(_field(block, "Module Alias")) or None,
                "hardwareIds": _build_hardware_ids(
                    bus, vendor, device, sub_vendor, sub_device
                ),
            }
        )

    return devices


def _inventory_hostname(school: str, device_hostname: str) -> str:
    """Return the globally unique hostname used by LINBO log uploads."""

    if school == DEFAULT_SCHOOL:
        return device_hostname
    return f"{school}-{device_hostname}"


def _metadata_from_device_records(
    records: Any,
    school: str,
) -> dict[str, dict[str, str | None]]:
    """Normalize upstream ``Devices(school).get_clients()`` records.

    Secondary-school LINBO clients use ``<school>-<hostname>`` as their global
    DNS/log name while their school-local devices.csv entry retains only
    ``hostname``.  Keying by the global name prevents identical local hostnames
    in two schools from ever being joined to the wrong inventory.
    """

    metadata: dict[str, dict[str, str | None]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        raw_hostname = record.get("hostname")
        if not isinstance(raw_hostname, str) or not raw_hostname.strip():
            continue
        device_hostname = raw_hostname.strip()
        inventory_hostname = _inventory_hostname(school, device_hostname)
        if INVENTORY_FILE_RE.fullmatch(f"{inventory_hostname}_hwinfo.gz") is None:
            logger.warning(
                "Ignoring invalid LINBO device hostname %r in school %s",
                device_hostname,
                school,
            )
            continue

        def optional_text(key: str) -> str | None:
            value = record.get(key)
            if not isinstance(value, str):
                return None
            normalized = value.strip()
            return normalized or None

        metadata[inventory_hostname.casefold()] = {
            "room": optional_text("room"),
            "hostname": device_hostname,
            "group": optional_text("group"),
            # ``Devices`` already applies NameChecker.normalize_mac().  Keep
            # that canonical value unchanged instead of normalizing it again.
            "mac": optional_text("mac"),
            "ip": optional_text("ip"),
            "school": school,
            "inventoryHostname": inventory_hostname,
        }
    return metadata


def _load_school_device_metadata(
    school: str,
) -> dict[str, dict[str, str | None]]:
    """Load one school's native host records through linuxmuster-tools."""

    try:
        devices = Devices(school=school)
        return _metadata_from_device_records(devices.get_clients(), school)
    except (OSError, ValueError) as error:
        # Native school metadata is authoritative. Returning an empty mapping
        # makes the caller expose no cross-school inventories if it is missing.
        logger.warning(
            "Could not load linuxmuster devices for school %s: %s",
            school,
            error,
        )
        return {}


def _non_negative_number(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if math.isfinite(parsed) and parsed >= 0 else fallback


def _now_milliseconds(value: datetime | int | float | None) -> int:
    if value is None:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    if isinstance(value, datetime):
        current = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return int(current.timestamp() * 1000)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("now must be a datetime or finite Unix timestamp in seconds")
    return int(value * 1000)


def _iso_from_milliseconds(value: int) -> str:
    return (
        datetime.fromtimestamp(value / 1000, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _inventory_files(
    hwinfo_dir: Path,
) -> list[tuple[str, Path]] | None:
    """Return regular inventory files without following directory symlinks."""

    try:
        with os.scandir(hwinfo_dir) as directory:
            entries = list(directory)
    except FileNotFoundError:
        return []
    except OSError as error:
        logger.warning(
            "Could not read LINBO server hardware inventory directory %s: %s",
            hwinfo_dir,
            error,
        )
        return None

    files: list[tuple[str, Path]] = []
    for entry in entries:
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
        except OSError:
            continue
        filename_match = INVENTORY_FILE_RE.fullmatch(entry.name)
        if filename_match:
            files.append((filename_match.group(1), hwinfo_dir / entry.name))
    return files


def _inventory_from_file(
    file_path: Path,
    *,
    hostname: str,
    metadata: Mapping[str, str | None],
    school: str,
    stale_hours: float,
    now_ms: int,
    max_compressed_bytes: int,
    max_uncompressed_bytes: int,
    include_devices: bool,
) -> dict[str, Any]:
    """Build one response record from exactly one safely opened hwinfo file."""

    text, file_stat = read_server_hardware_file(
        file_path,
        max_compressed_bytes=max_compressed_bytes,
        max_uncompressed_bytes=max_uncompressed_bytes,
    )
    captured_at_ms = int(file_stat.st_mtime * 1000)
    age_ms = max(0, now_ms - captured_at_ms)
    devices = parse_hardware_devices(text)

    inventory: dict[str, Any] = {
        "hostname": hostname,
        "deviceHostname": metadata.get("hostname") or hostname,
        "school": school,
        "room": metadata.get("room"),
        "group": metadata.get("group"),
        "mac": metadata.get("mac"),
        "ip": metadata.get("ip"),
        "capturedAt": _iso_from_milliseconds(captured_at_ms),
        "ageMs": age_ms,
        "ageHours": age_ms / (60 * 60 * 1000),
        "stale": age_ms > stale_hours * 60 * 60 * 1000,
        "dmi": parse_dmi(text),
        "deviceCount": len(devices),
    }
    if include_devices:
        inventory["devices"] = devices
    return inventory


def _configured_stale_hours(value: float | str | None) -> float:
    return _non_negative_number(
        value if value is not None else os.environ.get("HWINFO_STALE_HOURS"),
        DEFAULT_STALE_HOURS,
    )


def _configured_hwinfo_dir(path: os.PathLike[str] | str | None) -> Path:
    return _lexical_absolute(
        path or os.environ.get("LINBO_HWINFO_DIR") or DEFAULT_HWINFO_DIR
    )


def list_server_hardware(
    *,
    hwinfo_dir: os.PathLike[str] | str | None = None,
    school: str = DEFAULT_SCHOOL,
    stale_hours: float | str | None = None,
    max_compressed_bytes: int = MAX_COMPRESSED_BYTES,
    max_uncompressed_bytes: int = MAX_UNCOMPRESSED_BYTES,
    include_devices: bool = True,
    now: datetime | int | float | None = None,
) -> list[dict[str, Any]]:
    """List every readable server-side LINBO hardware inventory.

    Corrupt, oversized, disappearing, or otherwise unreadable individual files
    are logged and skipped.  One bad client therefore cannot break the full
    inventory view. The school-scoped native ``Devices`` provider supplies
    authoritative client metadata and filters out other schools.
    """

    configured_school = validate_school_name(school)
    configured_hwinfo_dir = _configured_hwinfo_dir(hwinfo_dir)
    configured_stale_hours = _configured_stale_hours(stale_hours)
    now_ms = _now_milliseconds(now)
    inventory_files = _inventory_files(configured_hwinfo_dir)
    if not inventory_files:
        return []

    host_metadata = _load_school_device_metadata(configured_school)
    if not host_metadata:
        return []
    inventories: list[dict[str, Any]] = []

    for hostname, file_path in inventory_files:
        metadata = host_metadata.get(hostname.casefold(), {})
        if not metadata:
            continue
        try:
            inventories.append(_inventory_from_file(
                file_path,
                hostname=hostname,
                metadata=metadata,
                school=configured_school,
                stale_hours=configured_stale_hours,
                now_ms=now_ms,
                max_compressed_bytes=max_compressed_bytes,
                max_uncompressed_bytes=max_uncompressed_bytes,
                include_devices=include_devices,
            ))
        except (OSError, EOFError, zlib.error) as error:
            logger.warning(
                "Skipping unreadable LINBO hardware inventory %s: %s",
                file_path.name,
                error,
            )

    return sorted(inventories, key=lambda item: (item["hostname"].casefold(), item["hostname"]))


def get_server_hardware(
    hostname: str,
    *,
    hwinfo_dir: os.PathLike[str] | str | None = None,
    school: str = DEFAULT_SCHOOL,
    stale_hours: float | str | None = None,
    max_compressed_bytes: int = MAX_COMPRESSED_BYTES,
    max_uncompressed_bytes: int = MAX_UNCOMPRESSED_BYTES,
    include_devices: bool = True,
    now: datetime | int | float | None = None,
) -> dict[str, Any] | None:
    """Read one school client's inventory without parsing unrelated files."""

    if not isinstance(hostname, str) or not hostname.strip():
        raise ValueError("hostname must not be empty")
    query = hostname.strip()
    configured_school = validate_school_name(school)
    host_metadata = _load_school_device_metadata(configured_school)

    metadata: Mapping[str, str | None] | None = None
    records = list(host_metadata.values())
    for key in ("inventoryHostname", "hostname"):
        metadata = next(
            (record for record in records if record.get(key) == query),
            None,
        )
        if metadata is not None:
            break
    if metadata is None:
        folded_query = query.casefold()
        for key in ("inventoryHostname", "hostname"):
            metadata = next(
                (
                    record
                    for record in records
                    if isinstance(record.get(key), str)
                    and record[key].casefold() == folded_query
                ),
                None,
            )
            if metadata is not None:
                break
    if metadata is None:
        return None

    inventory_hostname = metadata.get("inventoryHostname")
    if not isinstance(inventory_hostname, str):
        return None

    inventory_files = _inventory_files(_configured_hwinfo_dir(hwinfo_dir))
    if not inventory_files:
        return None
    selected = next(
        (item for item in inventory_files if item[0] == inventory_hostname),
        None,
    )
    if selected is None:
        folded_inventory_hostname = inventory_hostname.casefold()
        selected = next(
            (
                item
                for item in sorted(inventory_files, key=lambda item: item[0])
                if item[0].casefold() == folded_inventory_hostname
            ),
            None,
        )
    if selected is None:
        return None

    file_hostname, file_path = selected
    try:
        return _inventory_from_file(
            file_path,
            hostname=file_hostname,
            metadata=metadata,
            school=configured_school,
            stale_hours=_configured_stale_hours(stale_hours),
            now_ms=_now_milliseconds(now),
            max_compressed_bytes=max_compressed_bytes,
            max_uncompressed_bytes=max_uncompressed_bytes,
            include_devices=include_devices,
        )
    except (OSError, EOFError, zlib.error) as error:
        logger.warning(
            "Skipping unreadable LINBO hardware inventory %s: %s",
            file_path.name,
            error,
        )
        return None


__all__ = [
    "DEFAULT_HWINFO_DIR",
    "DEFAULT_SCHOOL",
    "DEFAULT_STALE_HOURS",
    "MAX_COMPRESSED_BYTES",
    "MAX_UNCOMPRESSED_BYTES",
    "InventoryFileError",
    "validate_school_name",
    "parse_dmi",
    "parse_hardware_devices",
    "read_server_hardware_file",
    "list_server_hardware",
    "get_server_hardware",
]
