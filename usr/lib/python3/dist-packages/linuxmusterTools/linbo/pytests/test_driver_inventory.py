import errno
import gzip
import logging
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

import linuxmusterTools.linbo.driver_inventory as inventory_module
from linuxmusterTools.linbo.driver_inventory import (
    InventoryFileError,
    list_server_hardware,
    parse_devices_csv,
    parse_dmi,
    parse_hardware_devices,
    read_server_hardware_file,
    validate_school_name,
)


HWINFO = """
============ start debug info ============
  type 0x03 [0x0300]: 03 16 00 03
       str1: "Wrong chassis vendor"
       str2: "Wrong chassis product"
  type 0x01 [0x0100]: 01 1b 00 01
       str1: "QEMU"
       str2: "Standard PC (Q35 + ICH9, 2009)"
       str3: "pc-q35-9.0"
  type 0x04 [0x0400]: 04 2a 00 04
       str1: "CPU 0"

17: PCI 1f.2: 0106 SATA controller (AHCI 1.0)
  Hardware Class: storage
  Model: "Red Hat QEMU Virtual Machine"
  Vendor: pci 0x8086 "Intel Corporation"
  Device: pci 0x2922 "ICH9 SATA Controller"
  SubVendor: pci 0x1af4 "Red Hat, Inc."
  SubDevice: pci 0x1100 "QEMU Virtual Machine"
  Driver: "ahci"
  Module Alias: "pci:v00008086d00002922sv00001AF4sd00001100bc01sc06i01"

18: USB 00.0: 10503 USB Mouse
  Hardware Class: mouse
  Model: "Adomax QEMU USB Tablet"
  Vendor: usb 0x0627 "Adomax Technology Co., Ltd"
  Device: usb 0x0001 "QEMU USB Tablet"
  Driver: "usbhid", "hid-generic"
  Module Alias: "usb:v0627p0001d0000"

19: None 00.0: 10103 CPU
  Hardware Class: cpu
  Vendor: "GenuineIntel"
  Device: 0x0001
"""


@pytest.fixture
def inventory_paths(tmp_path: Path) -> tuple[Path, Path]:
    inventory_dir = tmp_path / "inventories"
    inventory_dir.mkdir()
    return inventory_dir, tmp_path / "devices.csv"


def write_inventory(inventory_dir: Path, hostname: str, text: str = HWINFO) -> Path:
    target = inventory_dir / f"{hostname}_hwinfo.gz"
    target.write_bytes(gzip.compress(text.encode("utf-8")))
    return target


def test_parse_dmi_uses_only_smbios_system_type() -> None:
    assert parse_dmi(HWINFO) == {
        "vendor": "QEMU",
        "product": "Standard PC (Q35 + ICH9, 2009)",
        "version": "pc-q35-9.0",
    }
    assert parse_dmi('type 0x03\n  str1: "Chassis"') is None


def test_parse_dmi_does_not_leak_strings_from_following_type() -> None:
    text = """
type 0x01 [0x0100]
  str1: "Vendor only"
type 0x02 [0x0200]
  str2: "Must not become the product"
"""
    assert parse_dmi(text) == {
        "vendor": "Vendor only",
        "product": None,
        "version": None,
    }


def test_parse_pci_and_usb_devices_with_windows_hardware_ids() -> None:
    devices = parse_hardware_devices(HWINFO)

    assert len(devices) == 2
    assert devices[0] == {
        "index": 17,
        "bus": "PCI",
        "address": "1f.2",
        "description": "0106 SATA controller (AHCI 1.0)",
        "hardwareClass": "storage",
        "model": "Red Hat QEMU Virtual Machine",
        "vendorId": "8086",
        "vendorName": "Intel Corporation",
        "deviceId": "2922",
        "deviceName": "ICH9 SATA Controller",
        "subVendorId": "1AF4",
        "subVendorName": "Red Hat, Inc.",
        "subDeviceId": "1100",
        "subDeviceName": "QEMU Virtual Machine",
        "drivers": ["ahci"],
        "moduleAlias": "pci:v00008086d00002922sv00001AF4sd00001100bc01sc06i01",
        "hardwareIds": [
            "PCI\\VEN_8086&DEV_2922&SUBSYS_11001AF4",
            "PCI\\VEN_8086&DEV_2922",
        ],
    }
    assert devices[1]["bus"] == "USB"
    assert devices[1]["vendorId"] == "0627"
    assert devices[1]["deviceId"] == "0001"
    assert devices[1]["drivers"] == ["usbhid", "hid-generic"]
    assert devices[1]["hardwareIds"] == ["USB\\VID_0627&PID_0001"]


def test_parse_devices_ignores_non_bus_qualified_debug_entries() -> None:
    text = """
1: PCI 00.0: incomplete debug entry
  Vendor: "not a bus id"
  Device: pci 0x1234
2: PCI 00.1: valid entry
  Vendor: pci 0x1
  Device: pci 0xab
  Driver: ahci, nvme
"""
    devices = parse_hardware_devices(text)
    assert len(devices) == 1
    assert devices[0]["vendorId"] == "0001"
    assert devices[0]["deviceId"] == "00AB"
    assert devices[0]["drivers"] == ["ahci", "nvme"]


def test_parse_devices_csv_handles_bom_quotes_and_escaped_quotes() -> None:
    metadata = parse_devices_csv(
        '\ufeff"room;west";Client-A;win11;AA:BB:CC:DD:EE:FF;10.0.0.42;;;;\n'
        '"Room ""North""";newserver;nopxe;00:11:22:33:44:55;10.0.0.14;;;;\n'
        "# comment\n"
    )

    assert metadata["client-a"] == {
        "room": "room;west",
        "hostname": "Client-A",
        "group": "win11",
        "mac": "aa:bb:cc:dd:ee:ff",
        "ip": "10.0.0.42",
    }
    assert metadata["newserver"]["room"] == 'Room "North"'


def test_read_enforces_compressed_and_uncompressed_limits(
    inventory_paths: tuple[Path, Path],
) -> None:
    inventory_dir, _ = inventory_paths
    inventory = write_inventory(inventory_dir, "limited", "x" * 4096)

    with pytest.raises(InventoryFileError) as compressed_error:
        read_server_hardware_file(inventory, max_compressed_bytes=4)
    assert compressed_error.value.code == "COMPRESSED_FILE_TOO_LARGE"
    assert compressed_error.value.limit == 4

    with pytest.raises(InventoryFileError) as uncompressed_error:
        read_server_hardware_file(inventory, max_uncompressed_bytes=32)
    assert uncompressed_error.value.code == "UNCOMPRESSED_FILE_TOO_LARGE"
    assert uncompressed_error.value.limit == 32


def test_read_uses_no_follow_for_direct_symlinks(
    inventory_paths: tuple[Path, Path],
) -> None:
    inventory_dir, _ = inventory_paths
    target = write_inventory(inventory_dir, "target")
    symlink = inventory_dir.parent / "symlink_hwinfo.gz"
    symlink.symlink_to(target)

    with pytest.raises(OSError) as error:
        read_server_hardware_file(symlink)
    assert error.value.errno == errno.ELOOP


def test_list_joins_metadata_and_reports_age_and_staleness(
    inventory_paths: tuple[Path, Path],
) -> None:
    inventory_dir, devices_csv = inventory_paths
    inventory = write_inventory(inventory_dir, "Client-A")
    captured_at = datetime(2026, 7, 10, 10, 0, tzinfo=timezone.utc)
    os.utime(inventory, (captured_at.timestamp(), captured_at.timestamp()))
    devices_csv.write_text(
        "room-1;client-a;win11;AA:BB:CC:DD:EE:FF;10.0.0.42;;;;\n",
        encoding="utf-8",
    )

    inventories = list_server_hardware(
        hwinfo_dir=inventory_dir,
        devices_csv=devices_csv,
        stale_hours=24,
        now=datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc),
    )

    assert len(inventories) == 1
    result = inventories[0]
    assert result["hostname"] == "Client-A"
    assert result["room"] == "room-1"
    assert result["group"] == "win11"
    assert result["mac"] == "aa:bb:cc:dd:ee:ff"
    assert result["ip"] == "10.0.0.42"
    assert result["capturedAt"] == "2026-07-10T10:00:00.000Z"
    assert result["ageMs"] == 48 * 60 * 60 * 1000
    assert result["ageHours"] == 48
    assert result["stale"] is True
    assert result["dmi"] == {
        "vendor": "QEMU",
        "product": "Standard PC (Q35 + ICH9, 2009)",
        "version": "pc-q35-9.0",
    }
    assert result["deviceCount"] == 2
    assert len(result["devices"]) == 2


def test_native_devices_provider_is_school_scoped_and_uses_global_log_names(
    inventory_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory_dir, _ = inventory_paths
    write_inventory(inventory_dir, "client")
    write_inventory(inventory_dir, "school-b-client")
    write_inventory(inventory_dir, "unmanaged")
    calls: list[str] = []

    class FakeDevices:
        def __init__(self, school: str) -> None:
            calls.append(school)
            self.devices = [
                {
                    "hostname": "client",
                    "room": f"room-{school}",
                    "group": f"group-{school}",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "ip": "10.0.0.42",
                }
            ]

    devices_module = types.ModuleType("linuxmusterTools.devices")
    devices_module.Devices = FakeDevices
    monkeypatch.setitem(sys.modules, "linuxmusterTools.devices", devices_module)
    default_inventory = list_server_hardware(
        hwinfo_dir=inventory_dir,
        school="default-school",
        include_devices=False,
    )
    branch_inventory = list_server_hardware(
        hwinfo_dir=inventory_dir,
        school="school-b",
        include_devices=False,
    )

    assert calls == ["default-school", "school-b"]
    assert [entry["hostname"] for entry in default_inventory] == ["client"]
    assert default_inventory[0]["deviceHostname"] == "client"
    assert default_inventory[0]["school"] == "default-school"
    assert default_inventory[0]["room"] == "room-default-school"
    assert [entry["hostname"] for entry in branch_inventory] == [
        "school-b-client"
    ]
    assert branch_inventory[0]["deviceHostname"] == "client"
    assert branch_inventory[0]["school"] == "school-b"
    assert branch_inventory[0]["room"] == "room-school-b"


@pytest.mark.parametrize("school", ["../school", "school/name", "school.name", ""])
def test_school_name_validation_rejects_unsafe_components(school: str) -> None:
    with pytest.raises(ValueError, match="school"):
        validate_school_name(school)


def test_native_school_metadata_failure_exposes_no_other_school_inventory(
    inventory_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory_dir, _ = inventory_paths
    write_inventory(inventory_dir, "client")
    monkeypatch.setattr(
        inventory_module,
        "_load_school_device_metadata",
        lambda _school: {},
    )

    assert list_server_hardware(hwinfo_dir=inventory_dir) == []


def test_list_can_omit_device_details_but_keeps_count(
    inventory_paths: tuple[Path, Path],
) -> None:
    inventory_dir, _ = inventory_paths
    write_inventory(inventory_dir, "client")

    result = list_server_hardware(
        hwinfo_dir=inventory_dir,
        devices_csv=None,
        include_devices=False,
    )[0]

    assert result["deviceCount"] == 2
    assert "devices" not in result


def test_list_uses_environment_overrides_and_stable_casefold_order(
    inventory_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory_dir, devices_csv = inventory_paths
    write_inventory(inventory_dir, "zeta")
    write_inventory(inventory_dir, "Alpha")
    devices_csv.write_text("room;Alpha;group;aa:bb;10.0.0.1\n", encoding="utf-8")
    monkeypatch.setenv("LINBO_HWINFO_DIR", str(inventory_dir))
    monkeypatch.setenv("HWINFO_STALE_HOURS", "0")

    inventories = list_server_hardware(
        devices_csv=devices_csv,
        now=datetime.now(timezone.utc).timestamp() + 1,
    )

    assert [entry["hostname"] for entry in inventories] == ["Alpha", "zeta"]
    assert all(entry["stale"] for entry in inventories)


def test_list_skips_corrupt_symlinked_and_unrelated_files(
    inventory_paths: tuple[Path, Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    inventory_dir, _ = inventory_paths
    valid = write_inventory(inventory_dir, "valid")
    (inventory_dir / "broken_hwinfo.gz").write_bytes(b"not gzip")
    (inventory_dir / "notes.txt").write_text("ignored", encoding="utf-8")
    (inventory_dir / "linked_hwinfo.gz").symlink_to(valid)
    (inventory_dir / "directory_hwinfo.gz").mkdir()

    package_logger = logging.getLogger("linuxmusterTools")
    old_propagate = package_logger.propagate
    package_logger.propagate = False
    package_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING):
            inventories = list_server_hardware(
                hwinfo_dir=inventory_dir,
                devices_csv=None,
            )
    finally:
        package_logger.removeHandler(caplog.handler)
        package_logger.propagate = old_propagate

    assert [entry["hostname"] for entry in inventories] == ["valid"]
    skipped = [record for record in caplog.records if "Skipping unreadable" in record.message]
    assert len(skipped) == 1
    assert "broken_hwinfo.gz" in skipped[0].message


def test_bad_optional_devices_csv_does_not_hide_inventories(
    inventory_paths: tuple[Path, Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    inventory_dir, devices_csv = inventory_paths
    write_inventory(inventory_dir, "client")
    devices_csv.write_text("x" * 256, encoding="utf-8")

    package_logger = logging.getLogger("linuxmusterTools")
    old_propagate = package_logger.propagate
    package_logger.propagate = False
    package_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING):
            inventories = list_server_hardware(
                hwinfo_dir=inventory_dir,
                devices_csv=devices_csv,
                max_devices_csv_bytes=8,
            )
    finally:
        package_logger.removeHandler(caplog.handler)
        package_logger.propagate = old_propagate

    assert [entry["hostname"] for entry in inventories] == ["client"]
    assert inventories[0]["room"] is None
    assert any("devices.csv" in record.message for record in caplog.records)


def test_missing_inventory_directory_returns_empty_list(tmp_path: Path) -> None:
    assert list_server_hardware(
        hwinfo_dir=tmp_path / "missing",
        devices_csv=None,
    ) == []
