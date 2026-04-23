"""
LINBO Torrent Service — wrapper around /usr/sbin/linbo-torrent.

Controls BitTorrent seeding for peer-to-peer image distribution.
"""

import logging
import subprocess
from pathlib import Path

from linuxmusterTools.common.checks import NameChecker


name_checker = NameChecker()
logger = logging.getLogger(__name__)

TORRENT_BIN = "/usr/sbin/linbo-torrent"
CONFIG_PATH = "/etc/default/linbo-torrent"


class LinboTorrent:
    """Manage BitTorrent image seeding."""

    @staticmethod
    def _validate_image(image: str) -> str:
        if not name_checker.check_linbo_image_name(image):
            raise ValueError(f"Unsafe image name: {image}")
        return image

    def status(self) -> list[dict]:
        """Get active torrent sessions.

        Returns:
            List of {image, info} dicts
        """
        try:
            result = subprocess.run(
                [TORRENT_BIN, "status"],
                capture_output=True, text=True, timeout=10,
            )
            sessions = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts:
                    sessions.append({
                        "image": parts[0],
                        "info": " ".join(parts[1:]) if len(parts) > 1 else "",
                    })
            return sessions
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning("torrent status failed: %s", e)
            return []

    def start(self, image: str | None = None) -> dict:
        """Start torrent seeding.

        Args:
            image: Specific image, or None for all

        Returns:
            {success, message}
        """
        cmd = [TORRENT_BIN, "start"]
        if image:
            cmd.append(self._validate_image(image))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "success": result.returncode == 0,
            "message": result.stdout.strip() or result.stderr.strip(),
        }

    def stop(self, image: str | None = None) -> dict:
        """Stop torrent seeding.

        Args:
            image: Specific image, or None for all

        Returns:
            {success, message}
        """
        cmd = [TORRENT_BIN, "stop"]
        if image:
            cmd.append(self._validate_image(image))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "success": result.returncode == 0,
            "message": result.stdout.strip() or result.stderr.strip(),
        }

    def get_config(self) -> dict:
        """Read torrent configuration."""
        config = {}
        try:
            for line in Path(CONFIG_PATH).read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    config[key.strip()] = value.strip().strip('"')
        except OSError:
            pass
        return config
