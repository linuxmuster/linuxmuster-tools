"""
LINBO Boot Logs — read client boot logs from /var/log/linuxmuster/linbo/.

Provides safe file listing, reading, and deletion with path traversal protection.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = "/var/log/linuxmuster/linbo"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9._-]+$")


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
