"""
LINBO Boot Logs — read client boot logs from /var/log/linuxmuster/linbo/.

Provides safe file listing, reading, and deletion with path traversal protection.
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = "/var/log/linuxmuster/linbo"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9._-]+$")
_IMAGE_STATUS_PATTERN = re.compile(r"^(\d{12})\s+(\w+):\s+(\S+)(?:\s+\"(\d+)\")?")


def get_host_image_status(log_dir: str | None = None) -> dict:
    """Parse _image.status files for per-host last sync info.

    Reads *_image.status files from the LINBO log directory. Each file
    contains a single line like: 202603241142 applied: win11_pro_edu.qcow2 "202601271107"

    Args:
        log_dir: Override log directory (default: /var/log/linuxmuster/linbo)

    Returns:
        Dict mapping hostname to {lastSync, action, image, imageVersion}
    """
    base = Path(log_dir) if log_dir else Path(DEFAULT_LOG_DIR)
    if not base.is_dir():
        return {}

    result = {}
    try:
        entries = os.listdir(base)
    except OSError:
        return {}

    status_files = [f for f in entries if f.endswith("_image.status")]

    for filename in sorted(status_files):
        hostname = filename.removesuffix("_image.status")
        filepath = base / filename
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue

        m = _IMAGE_STATUS_PATTERN.match(content)
        if m:
            ts = m.group(1)  # YYYYMMDDHHMI
            year, month, day = ts[0:4], ts[4:6], ts[6:8]
            hour, minute = ts[8:10], ts[10:12]

            result[hostname] = {
                "lastSync": f"{year}-{month}-{day}T{hour}:{minute}:00.000Z",
                "action": m.group(2),
                "image": m.group(3),
                "imageVersion": m.group(4) or None,
            }

    return result


class LinboBootLogs:
    """Read-only access to LINBO client boot logs."""

    def __init__(self, log_dir: str = DEFAULT_LOG_DIR):
        self.log_dir = Path(log_dir)

    def list_logs(self) -> list[dict]:
        """List all log files with metadata.

        Returns:
            List of {filename, size, modifiedAt} dicts, sorted newest first
        """
        if not self.log_dir.is_dir():
            return []

        logs = []
        for f in self.log_dir.iterdir():
            if not f.is_file():
                continue
            stat = f.stat()
            logs.append({
                "filename": f.name,
                "size": stat.st_size,
                "modifiedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })

        return sorted(logs, key=lambda x: x["modifiedAt"], reverse=True)

    def read_log(self, filename: str) -> str | None:
        """Read a log file's content.

        Args:
            filename: Name of the log file (validated for path traversal)

        Returns:
            File content as string, or None if not found

        Raises:
            ValueError: If filename contains unsafe characters
            ValueError: If file exceeds MAX_FILE_SIZE
        """
        if not _SAFE_FILENAME.match(filename):
            raise ValueError(f"Unsafe filename: {filename}")

        filepath = self.log_dir / filename
        if not filepath.is_file():
            return None

        if filepath.stat().st_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {filepath.stat().st_size} bytes (max {MAX_FILE_SIZE})")

        return filepath.read_text(encoding="utf-8", errors="replace")

    def delete_log(self, filename: str) -> bool:
        """Delete a log file.

        Args:
            filename: Name of the log file

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If filename contains unsafe characters
        """
        if not _SAFE_FILENAME.match(filename):
            raise ValueError(f"Unsafe filename: {filename}")

        filepath = self.log_dir / filename
        if not filepath.is_file():
            return False

        filepath.unlink()
        return True
