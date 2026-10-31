"""
LINBO Boot Logs — read client boot logs from /var/log/linuxmuster/linbo/.

Provides safe file listing, reading, and deletion with path traversal protection.
"""

import gzip
import logging
import os
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

        # Logs rotated by logrotate are gzipped
        if filepath.suffix == ".gz":
            with gzip.open(filepath, "rb") as f:
                content = f.read(MAX_FILE_SIZE + 1)
            if len(content) > MAX_FILE_SIZE:
                raise ValueError(f"File too large: more than {MAX_FILE_SIZE} bytes uncompressed")
            return content.decode("utf-8", errors="replace")

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


_IMAGE_STATUS_PATTERN = re.compile(r'^(\d{12})\s+(\w+):\s+(\S+)(?:\s+"?(\d+)"?)?')

def _get_image_status_entries(statusfile):
    """
    Parse a ``*_image.status`` file as written by linuxmuster-linbo7's
    shell_functions log_image_status(), e.g.:
        202603241142 applied: win11_pro_edu.qcow2 "202601271107"
        202601271107 created: win11_pro_edu.qcow2 202601271107

    The trailing image timestamp is quoted on "applied" lines and bare on
    "created" ones: linbo_sync reads it back from the image .info file with
    getinfo(), which returns the raw right-hand side of timestamp="...",
    quotes included, while linbo_mkinfo passes date(1) output directly.
    Both forms are accepted.

    The file is overwritten (not appended) on every sync/creation, so it
    normally holds a single line, but every matching line is returned, in
    file order, to stay tolerant of older or hand-edited multi-line files.

    :param statusfile: Path to the ``*_image.status`` file
    :type statusfile: string
    :return: List of {timestamp, action, image, image_timestamp}
    :rtype: list of dict
    """

    if not os.path.isfile(statusfile) or os.stat(statusfile).st_size == 0:
        return []

    entries = []
    with open(statusfile, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = _IMAGE_STATUS_PATTERN.match(line.strip())
            if m:
                entries.append({
                    'timestamp': m.group(1),
                    'action': m.group(2),
                    'image': m.group(3),
                    'image_timestamp': m.group(4),
                })
    return entries

_LINBO_START_PATTERN = re.compile(r'^### (\d{8})-(\d{4})\d{2} linbo_start ')
# The name of the OS is logged just before linbo_start, by linbo_wrapper
# ("Starting <Name> ...") or by the GUI ("[+++ Chapter +++] Starting <Name>").
_OS_NAME_PATTERNS = (
    re.compile(r'^Starting (.+) \.\.\.$'),
    re.compile(r'^\[\+\+\+ Chapter \+\+\+\] Starting (.+)$'),
)

def _get_os_starts(logfile):
    """
    Parse the OS starts of a <hostname>_linbo.log, plain or gzipped by
    logrotate.

    :param logfile: Path of the log file
    :type logfile: string
    :return: List of {'timestamp': YYYYMMDDHHMI, 'os': name or None}
    :rtype: list of dict
    """


    opener = gzip.open if logfile.endswith('.gz') else open

    starts = []
    name = None
    with opener(logfile, 'rt', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            m = _LINBO_START_PATTERN.match(line)
            if m:
                # linbo_start writes seconds, linbo_timestamp_to_epoch()
                # reads the YYYYMMDDHHMI of the image status files.
                starts.append({'timestamp': m.group(1) + m.group(2), 'os': name})
                name = None
                continue

            for pattern in _OS_NAME_PATTERNS:
                m = pattern.match(line)
                if m:
                    name = m.group(1)
                    break

    return starts
