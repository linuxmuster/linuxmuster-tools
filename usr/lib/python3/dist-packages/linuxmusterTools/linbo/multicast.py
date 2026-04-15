"""
LINBO Multicast Service — wrapper around /usr/sbin/linbo-multicast.

Controls multicast image distribution for fast client provisioning.
"""

import logging
import subprocess
from pathlib import Path

from linuxmusterTools.common.checks import NameChecker


name_checker = NameChecker()
logger = logging.getLogger(__name__)

MULTICAST_BIN = "/usr/sbin/linbo-multicast"
CONFIG_PATH = "/etc/default/linbo-multicast"


class LinboMulticast:
    """Manage multicast image distribution."""

    def status(self) -> list[dict]:
        """Get active multicast sessions.

        Returns:
            List of {image, port, pid, startedAt} dicts
        """
        try:
            result = subprocess.run(
                [MULTICAST_BIN, "status"],
                capture_output=True, text=True, timeout=10,
            )
            return self._parse_status(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning("multicast status failed: %s", e)
            return []

    @staticmethod
    def _validate_image(image: str) -> str:
        if not name_checker.check_linbo_image_name(image):
            raise ValueError(f"Unsafe image name: {image}")
        return image

    def start(self, image: str | None = None) -> dict:
        """Start multicast seeding.

        Args:
            image: Specific image name, or None for all images

        Returns:
            {success, message}
        """
        cmd = [MULTICAST_BIN, "start"]
        if image:
            cmd.append(self._validate_image(image))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "success": result.returncode == 0,
            "message": result.stdout.strip() or result.stderr.strip(),
        }

    def stop(self, image: str | None = None) -> dict:
        """Stop multicast seeding.

        Args:
            image: Specific image, or None for all

        Returns:
            {success, message}
        """
        cmd = [MULTICAST_BIN, "stop"]
        if image:
            cmd.append(self._validate_image(image))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "success": result.returncode == 0,
            "message": result.stdout.strip() or result.stderr.strip(),
        }

    def get_config(self) -> dict:
        """Read multicast configuration from /etc/default/linbo-multicast."""
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

    def _parse_status(self, output: str) -> list[dict]:
        """Parse linbo-multicast status output."""
        sessions = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format varies, parse what we can
            parts = line.split()
            if len(parts) >= 2:
                sessions.append({
                    "image": parts[0],
                    "info": " ".join(parts[1:]),
                })
        return sessions
