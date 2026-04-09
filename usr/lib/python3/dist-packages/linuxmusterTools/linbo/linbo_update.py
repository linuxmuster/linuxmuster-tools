"""
LINBO Update Service — check and install linuxmuster-linbo7 package updates.

Uses APT package management to check for updates, download, and install.
Supports version comparison and status tracking.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PACKAGE_NAME = "linuxmuster-linbo7"
STATE_FILE = Path(os.environ.get("CONFIG_DIR", "/etc/linuxmuster/linbo")) / "update_state.json"


class LinboUpdateManager:
    """Manage LINBO package updates."""

    def check_version(self) -> dict:
        """Check installed and available LINBO versions.

        Returns:
            {installed, available, updateAvailable}
        """
        installed = self._get_installed_version()
        available = self._get_available_version()

        update_available = False
        if installed and available and installed != available:
            update_available = self._version_gt(available, installed)

        return {
            "installed": installed,
            "available": available,
            "updateAvailable": update_available,
        }

    def start_update(self, timeout: int = 600) -> dict:
        """Run apt-get install to update the LINBO package.

        Args:
            timeout: Max seconds for the update (default: 10 min)

        Returns:
            {success, output, errors, duration, installedVersion}
        """
        state = self._read_state()
        if state.get("status") == "running":
            return {"success": False, "errors": "Update already in progress"}

        self._write_state({"status": "running", "startedAt": datetime.now(timezone.utc).isoformat()})

        start = datetime.now(timezone.utc)
        try:
            # Update package lists first
            subprocess.run(
                ["apt-get", "update", "-qq"],
                capture_output=True, text=True, timeout=120,
            )

            # Install/upgrade
            result = subprocess.run(
                ["apt-get", "install", "-y", "--only-upgrade", PACKAGE_NAME],
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
            )

            duration = (datetime.now(timezone.utc) - start).total_seconds()
            installed = self._get_installed_version()

            self._write_state({
                "status": "completed" if result.returncode == 0 else "failed",
                "completedAt": datetime.now(timezone.utc).isoformat(),
                "installedVersion": installed,
                "exitCode": result.returncode,
            })

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr if result.returncode != 0 else None,
                "duration": duration,
                "installedVersion": installed,
            }

        except subprocess.TimeoutExpired:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            self._write_state({"status": "failed", "error": f"Timeout after {timeout}s"})
            return {"success": False, "errors": f"Timeout after {timeout}s", "duration": duration}

        except Exception as e:
            self._write_state({"status": "failed", "error": str(e)})
            return {"success": False, "errors": str(e)}

    def get_status(self) -> dict:
        """Get current update status."""
        return self._read_state()

    def _get_installed_version(self) -> str | None:
        """Get installed package version via dpkg."""
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Version}", PACKAGE_NAME],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _get_available_version(self) -> str | None:
        """Get available package version via apt-cache."""
        try:
            result = subprocess.run(
                ["apt-cache", "policy", PACKAGE_NAME],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                m = re.search(r"Candidate:\s+(\S+)", result.stdout)
                if m and m.group(1) != "(none)":
                    return m.group(1)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    @staticmethod
    def _version_gt(a: str, b: str) -> bool:
        """Compare Debian version strings (simplified)."""
        try:
            result = subprocess.run(
                ["dpkg", "--compare-versions", a, "gt", b],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return a > b

    def _read_state(self) -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "idle"}

    def _write_state(self, updates: dict):
        state = {**self._read_state(), **updates}
        fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=str(STATE_FILE.parent))
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2)
            os.rename(tmp, str(STATE_FILE))
        except Exception:
            os.unlink(tmp)
            raise
