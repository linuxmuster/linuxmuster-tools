"""
LINBO Change Tracker — cursor-based delta detection via filesystem mtimes.

Compares file modification times against a unix-timestamp cursor to
determine which hosts, start.confs, and configs have changed.
"""

import logging
import time
from pathlib import Path
from datetime import datetime, timezone

from linuxmusterTools.devices import Devices
from .config import LinboConfigManager
from .grub import LinboGrubReader
from ..common.timestamps import get_utc_mtime
from ..subnets import Subnets


logger = logging.getLogger(__name__)

class LinboChangeTracker:
    """
    Cursor-based change detection using filesystem mtimes.
    """


    def __init__(self, school: str = "default-school"):
        self.school = school
        self.devices_mgr = Devices(school=school)
        self.config_manager = LinboConfigManager()
        self.grub_reader = LinboGrubReader()
        self.subnets_mgr = Subnets()

    def get_changes(self, since_cursor: str = "0") -> dict:
        """Compare filesystem state against cursor, return delta.

        Args:
            since_cursor: Unix timestamp string. '0' = full snapshot.

        Returns:
            Dict with nextCursor, hostsChanged, startConfsChanged,
            configsChanged, dhcpChanged, deletedHosts, deletedStartConfs,
            allHostMacs, allStartConfIds, allConfigIds.
        """


        try:
            cursor_ts = int(since_cursor) if since_cursor else 0
        except ValueError:
            cursor_ts = 0

        cursor_dt = (
            datetime.fromtimestamp(cursor_ts, tz=timezone.utc) if cursor_ts > 0
            else None
        )

        # Reload devices list and subnets definition
        self.devices_mgr.load()
        self.subnets_mgr.load()

        school_groups = self.devices_mgr.groups
        all_hosts_macs = self.devices_mgr.macs

        # Parse ids
        all_startconf_ids = [
            id for id in self.config_manager.linbo_groups()
            if id in school_groups
        ]
        all_config_ids = [
            id for id in self.grub_reader.list_grub_cfg_ids()
            if id in school_groups
        ]

        # Detect host changes via devices.csv mtime
        devices_csv_mtime = self.devices_mgr.csv_mtime
        hosts_changed_macs: list[str] = []
        deleted_hosts: list[str] = []

        devices_modified = (
            cursor_dt is None
            or devices_csv_mtime is None
            or (devices_csv_mtime > cursor_dt)
        )

        subnets_csv_mtime = self.subnets_mgr.csv_mtime
        subnets_modified = (
            cursor_dt is None
            or subnets_csv_mtime is None
            or (subnets_csv_mtime > cursor_dt)
        )

        if devices_modified:
            hosts_changed_macs = list(all_hosts_macs)

        dhcp_changed = devices_modified or subnets_modified

        # Check start.conf files
        startconfs_changed: list[str] = []
        deleted_startconfs: list[str] = []
        for group in all_startconf_ids:
            startconf_path = Path(f'/srv/linbo/start.conf.{group}')
            mtime = get_utc_mtime(startconf_path)
            if cursor_dt is None or (mtime and mtime > cursor_dt):
                startconfs_changed.append(group)

        # Check GRUB configs
        configs_changed: list[str] = []
        for group in all_config_ids:
            mtime = self.grub_reader.get_cfg_mtime(group)
            if cursor_dt is None or (mtime and mtime > cursor_dt):
                configs_changed.append(group)

        next_cursor = str(int(time.time()))

        return {
            "nextCursor": next_cursor,
            "hostsChanged": hosts_changed_macs,
            "startConfsChanged": startconfs_changed,
            "configsChanged": configs_changed,
            "dhcpChanged": dhcp_changed,
            "deletedHosts": deleted_hosts,
            "deletedStartConfs": deleted_startconfs,
            "allHostMacs": all_hosts_macs,
            "allStartConfIds": all_startconf_ids,
            "allConfigIds": all_config_ids,
        }
