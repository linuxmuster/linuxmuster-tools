import os
import time
from types import SimpleNamespace

import pytest

import linuxmusterTools.linbo.changes as changes_module
from linuxmusterTools.common.timestamps import get_utc_mtime


@pytest.fixture
def linbo_tree(tmp_path, monkeypatch):
    """
    A school with two hosts in group 'room1', the start.conf and grub cfg of
    that group, and subnets.conf, every file dated an hour ago.
    """

    devices_csv = tmp_path / "devices.csv"
    subnets = tmp_path / "subnets.conf"
    startconf = tmp_path / "start.conf.room1"
    grub_dir = tmp_path / "grub"
    grub_dir.mkdir()
    grub_cfg = grub_dir / "room1.cfg"
    for path in (devices_csv, subnets, startconf, grub_cfg):
        path.write_text("x")
        old = time.time() - 3600
        os.utime(path, (old, old))

    devices = SimpleNamespace(
        load=lambda: setattr(devices, "csv_mtime", get_utc_mtime(devices_csv)),
        groups=["room1"],
        macs=["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"],
        csv_mtime=None,
    )
    grub_reader = SimpleNamespace(
        list_grub_cfg_ids=lambda: ["room1"],
        get_cfg_mtime=lambda group: get_utc_mtime(grub_dir / f"{group}.cfg"),
    )
    monkeypatch.setattr(changes_module, "Devices", lambda school: devices)
    monkeypatch.setattr(changes_module, "LinboConfigManager", lambda: SimpleNamespace(group_ids=["room1"]))
    monkeypatch.setattr(changes_module, "LinboGrubReader", lambda: grub_reader)
    monkeypatch.setattr(changes_module, "DHCP_SUBNETS_PATH", subnets)
    monkeypatch.setattr(changes_module, "LINBO_PATH", str(tmp_path))

    return SimpleNamespace(
        devices_csv=devices_csv, subnets=subnets, startconf=startconf, grub_cfg=grub_cfg,
    )


def touch(path, when):
    os.utime(path, (when, when))


def test_full_snapshot_reports_everything(linbo_tree):
    changes = changes_module.LinboChangeTracker().get_changes("0")

    assert changes["hostsChanged"] == ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
    assert changes["startConfsChanged"] == ["room1"]
    assert changes["configsChanged"] == ["room1"]
    assert changes["dhcpChanged"] is True


def test_nothing_changed_since_the_cursor(linbo_tree):
    cursor = str(int(time.time()))

    changes = changes_module.LinboChangeTracker().get_changes(cursor)

    assert changes["hostsChanged"] == []
    assert changes["startConfsChanged"] == []
    assert changes["configsChanged"] == []
    assert changes["dhcpChanged"] is False
    assert changes["allStartConfIds"] == ["room1"]


def test_deleted_fields_are_gone(linbo_tree):
    changes = changes_module.LinboChangeTracker().get_changes("0")

    assert "deletedHosts" not in changes
    assert "deletedStartConfs" not in changes


def test_a_file_written_on_the_cursor_second_is_reported(linbo_tree):
    cursor = int(time.time()) - 10
    touch(linbo_tree.startconf, cursor)

    changes = changes_module.LinboChangeTracker().get_changes(str(cursor))

    assert changes["startConfsChanged"] == ["room1"]


def test_a_file_written_during_the_scan_is_reported_next_time(linbo_tree, monkeypatch):
    # The scan starts at second T and ends 5 seconds later; the start.conf is
    # written at T + 0.3, while devices.csv is being read.
    T = int(time.time()) - 60
    clock = {"now": T}
    monkeypatch.setattr(changes_module.time, "time", lambda: clock["now"])

    tracker = changes_module.LinboChangeTracker()
    load = tracker.devices_mgr.load

    def load_then_write():
        load()
        touch(linbo_tree.startconf, T + 0.3)
        clock["now"] = T + 5

    monkeypatch.setattr(tracker.devices_mgr, "load", load_then_write)
    first = tracker.get_changes(str(T))

    monkeypatch.setattr(tracker.devices_mgr, "load", load)
    second = tracker.get_changes(first["nextCursor"])

    assert second["startConfsChanged"] == ["room1"]


@pytest.mark.parametrize("field, name", [
    ("startConfsChanged", "startconf"),
    ("configsChanged", "grub_cfg"),
])
def test_an_unreadable_mtime_counts_as_changed(linbo_tree, monkeypatch, field, name):
    path = getattr(linbo_tree, name)
    real = changes_module.get_utc_mtime
    monkeypatch.setattr(changes_module, "get_utc_mtime", lambda p: None if p == path else real(p))
    tracker = changes_module.LinboChangeTracker()
    monkeypatch.setattr(tracker.grub_reader, "get_cfg_mtime", lambda group: None if path == linbo_tree.grub_cfg else real(linbo_tree.grub_cfg))

    changes = tracker.get_changes(str(int(time.time())))

    assert changes[field] == ["room1"]
