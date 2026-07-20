import gzip
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

import linuxmusterTools.linbo.hardware_inventory as inventory_module
from linuxmusterTools.linbo.hardware_inventory import (
    LinboHardwareInventoryManager,
    parse_dmi,
)


HWINFO = """
============ start debug info ============
  type 0x03 [0x0003]: 03 16 03 00 01 02 03
       str1: "Wrong chassis vendor"
       str2: "Wrong chassis product"
  type 0x01 [0x0001]: 01 1b 01 00 01 02 00 03 00 e2 0e d7
       str1: "Hewlett-Packard"
       str2: "HP ProDesk 600 G1 TWR"
       str3: "CZC43638T2"
  type 0x02 [0x0002]: 02 0f 02 00 01 02 00
       str1: "Must not replace the system vendor"
"""


def write_inventory(directory: Path, hostname: str, content: str = HWINFO) -> Path:
    path = directory / f"{hostname}_hwinfo.gz"
    path.write_bytes(gzip.compress(content.encode("utf-8")))
    return path


def use_devices(
    monkeypatch: pytest.MonkeyPatch,
    records: list[dict],
) -> list[str]:
    schools = []

    class FakeDevices:
        def __init__(self, school: str) -> None:
            schools.append(school)

        def get_clients(self) -> list[dict]:
            return records

        def get_client(self, hostname: str) -> dict | None:
            return next(
                (record for record in records if record.get("hostname") == hostname),
                None,
            )

    monkeypatch.setattr(inventory_module, "Devices", FakeDevices)
    return schools


def test_parse_dmi_uses_smbios_type_one_string_indexes() -> None:
    assert parse_dmi(HWINFO) == {
        "vendor": "Hewlett-Packard",
        "product": "HP ProDesk 600 G1 TWR",
        "version": None,
    }

    reordered = """
type 0x01 [0x0001]: 01 1b 01 00 03 01 02 04
  str1: "Product from index one"
  str2: "Version from index two"
  str3: "Vendor from index three"
  str4: "Serial number, not version"
"""
    assert parse_dmi(reordered) == {
        "vendor": "Vendor from index three",
        "product": "Product from index one",
        "version": "Version from index two",
    }


@pytest.mark.parametrize(
    "content",
    [
        'type 0x03 [0x0003]: 03 16 03 00 01 02 03\n  str1: "Chassis"',
        'type 0x01 [0x0001]\n  str1: "Vendor"',
        'type 0x01 [0x0001]: 01 06 01 00 01 02\n  str1: "Vendor"',
    ],
)
def test_parse_dmi_rejects_missing_or_invalid_type_one(content: str) -> None:
    assert parse_dmi(content) is None


def test_list_combines_devices_dmi_and_existing_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory = write_inventory(tmp_path, "client-a")
    captured_at = datetime(2026, 7, 10, 10, 0, tzinfo=timezone.utc)
    os.utime(inventory, (captured_at.timestamp(), captured_at.timestamp()))
    schools = use_devices(
        monkeypatch,
        [
            {
                "hostname": "client-a",
                "room": "room-1",
                "group": "win11",
                "mac": "AA:BB:CC:DD:EE:FF",
                "ip": "10.0.0.42",
            },
            {"hostname": "client-without-inventory"},
        ],
    )

    inventories = LinboHardwareInventoryManager(
        hwinfo_dir=tmp_path,
    ).list()

    assert schools == ["default-school"]
    assert inventories == [
        {
            "hostname": "client-a",
            "school": "default-school",
            "room": "room-1",
            "group": "win11",
            "mac": "AA:BB:CC:DD:EE:FF",
            "ip": "10.0.0.42",
            "capturedAt": "2026-07-10T10:00:00+00:00",
            "dmi": {
                "vendor": "Hewlett-Packard",
                "product": "HP ProDesk 600 G1 TWR",
                "version": None,
            },
        }
    ]


@pytest.mark.parametrize("school", ["school-b", "school_b"])
def test_branch_school_uses_global_linbo_inventory_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    school: str,
) -> None:
    write_inventory(tmp_path, f"{school}-client-a")
    write_inventory(
        tmp_path,
        "client-a",
        HWINFO.replace("Hewlett-Packard", "Wrong unprefixed inventory"),
    )
    schools = use_devices(monkeypatch, [{"hostname": "client-a"}])

    inventory = LinboHardwareInventoryManager(
        school=school,
        hwinfo_dir=tmp_path,
    ).get("client-a")

    assert schools == [school]
    assert inventory is not None
    assert inventory["hostname"] == "client-a"
    assert inventory["school"] == school
    assert inventory["dmi"]["vendor"] == "Hewlett-Packard"


def test_get_returns_none_for_unknown_client_or_missing_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_devices(monkeypatch, [{"hostname": "known-client"}])
    manager = LinboHardwareInventoryManager(hwinfo_dir=tmp_path)

    assert manager.get("unknown-client") is None
    assert manager.get("known-client") is None


def test_list_skips_corrupt_and_oversized_inventories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_inventory(tmp_path, "good")
    (tmp_path / "broken_hwinfo.gz").write_bytes(b"not gzip")
    max_bytes = len(HWINFO.encode("utf-8"))
    write_inventory(tmp_path, "large", "x" * (max_bytes + 1))
    use_devices(
        monkeypatch,
        [
            {"hostname": "good"},
            {"hostname": "broken"},
            {"hostname": "large"},
        ],
    )
    monkeypatch.setattr(inventory_module, "MAX_HWINFO_BYTES", max_bytes)

    inventories = LinboHardwareInventoryManager(hwinfo_dir=tmp_path).list()

    assert [inventory["hostname"] for inventory in inventories] == ["good"]


def test_list_skips_oversized_compressed_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory = write_inventory(tmp_path, "large-compressed")
    use_devices(monkeypatch, [{"hostname": "large-compressed"}])
    monkeypatch.setattr(
        inventory_module,
        "MAX_COMPRESSED_HWINFO_BYTES",
        inventory.stat().st_size - 1,
    )

    assert LinboHardwareInventoryManager(hwinfo_dir=tmp_path).list() == []


def test_name_checker_protects_school_and_inventory_filenames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="school"):
        LinboHardwareInventoryManager(
            school="../school",
            hwinfo_dir=tmp_path,
        )

    use_devices(monkeypatch, [{"hostname": "../client"}])
    manager = LinboHardwareInventoryManager(hwinfo_dir=tmp_path)
    assert manager.list() == []
    with pytest.raises(ValueError, match="hostname"):
        manager.get("../client")
