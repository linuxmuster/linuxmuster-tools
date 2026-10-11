"""
LINBO Boot Logs — read client boot logs from /var/log/linuxmuster/linbo/.

Provides safe file listing, reading, and deletion with path traversal protection.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from ..common.checks import NameChecker

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = "/var/log/linuxmuster/linbo"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9._-]+$")
# Clients name their logs after themselves, with either separator:
# <hostname>_linbo.log, <hostname>_image.status, <hostname>.linbo-remote,
# <hostname>_linbo-remote_<YYYYmmddHHMMSS>.log.
# A hostname holds no '_' and no '.', so the first one of either ends it.
_LOG_HOSTNAME = re.compile(r"^(?P<hostname>[a-zA-Z0-9-]+)[._]")
# Since linuxmuster-linbo7 7.4.18, linbo-remote writes one log per run;
# before, a single <hostname>.linbo-remote overwritten by each run.
_REMOTE_LOG_TIMESTAMP = re.compile(r"_linbo-remote_(?P<timestamp>\d{14})\.log$")

name_checker = NameChecker()


class LinboBootLogs:
    """Read-only access to LINBO client boot logs."""

    def __init__(self, log_dir: str = DEFAULT_LOG_DIR):
        self.log_dir = Path(log_dir)

    def list_logs(self) -> list[dict]:
        """List all log files with metadata.

        Returns:
            List of {filename, hostname, size, modifiedAt} dicts, sorted
            newest first. hostname is None for a file whose name says nothing
            about a host; it is a name no inventory matches for the ones that
            belong to no machine anyway, like a multicast log
            (bionic.cloop_mcast.log) or a client that could not identify
            itself (UNKNOWN_linbo.log).
        """


        if not self.log_dir.is_dir():
            return []

        logs = []
        for f in self.log_dir.iterdir():
            if not f.is_file():
                continue
            stat = f.stat()
            hostname = _LOG_HOSTNAME.match(f.name)
            logs.append({
                "filename": f.name,
                "hostname": hostname.group("hostname") if hostname else None,
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

    def latest_remote_log(self, hostname: str) -> str | None:
        """Name of the log of a host's last linbo-remote run.

        The newest <hostname>_linbo-remote_<YYYYmmddHHMMSS>.log, ordered on
        the timestamp of its name, or the <hostname>.linbo-remote written by
        linuxmuster-linbo7 before 7.4.18 if the host has no other.

        Args:
            hostname: Name of the host

        Returns:
            File name to pass to read_log(), or None if the host has no
            linbo-remote log

        Raises:
            ValueError: If hostname is not a valid host name
        """


        name_checker.validate_host_name(hostname)

        if not self.log_dir.is_dir():
            return None

        runs = []
        for f in self.log_dir.glob(f"{hostname}_linbo-remote_*.log"):
            timestamp = _REMOTE_LOG_TIMESTAMP.search(f.name)
            if timestamp and f.is_file():
                runs.append((timestamp.group("timestamp"), f.name))

        if runs:
            return max(runs)[1]

        # Fallback for older versions of linbo
        legacy = f"{hostname}.linbo-remote"
        return legacy if (self.log_dir / legacy).is_file() else None

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
