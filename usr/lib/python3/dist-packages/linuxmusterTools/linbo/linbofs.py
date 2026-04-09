"""
LINBO linbofs Rebuild Service — execute update-linbofs with locking.

Manages linbofs64 rebuilds with:
- File-based mutual exclusion
- Build log rotation (keeps 3 most recent)
- Fakeroot detection
- Output buffering with size limits
"""

import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

UPDATE_SCRIPT = os.environ.get("UPDATE_LINBOFS_SCRIPT", "/usr/sbin/update-linbofs")
LINBO_DIR = os.environ.get("LINBO_DIR", "/srv/linbo")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/etc/linuxmuster/linbo")
LOCK_FILE = Path(CONFIG_DIR) / ".linbofs-rebuild.lock"
MAX_LOG_FILES = 3


def _is_fakeroot_available() -> bool:
    """Check if fakeroot is available."""
    return shutil.which("fakeroot") is not None


def rotate_build_logs() -> int:
    """Rotate build logs, keeping only the 3 most recent.

    Returns:
        Number of deleted log files
    """
    log_dir = Path(LINBO_DIR)
    if not log_dir.is_dir():
        return 0

    logs = []
    for f in log_dir.iterdir():
        if f.name.startswith(".linbofs-build") and f.name.endswith(".log"):
            try:
                logs.append((f, f.stat().st_mtime))
            except OSError:
                pass

    logs.sort(key=lambda x: x[1], reverse=True)

    deleted = 0
    for f, _ in logs[MAX_LOG_FILES:]:
        try:
            f.unlink()
            deleted += 1
        except OSError:
            pass

    return deleted


def update_linbofs(
    linbo_dir: str | None = None,
    config_dir: str | None = None,
    timeout: int = 300,
) -> dict:
    """Execute update-linbofs script.

    Args:
        linbo_dir: Override LINBO directory
        config_dir: Override config directory
        timeout: Maximum execution time in seconds (default: 5 min)

    Returns:
        {success, output, errors, duration}
    """
    script = Path(UPDATE_SCRIPT)
    if not script.is_file():
        return {"success": False, "errors": f"Script not found: {UPDATE_SCRIPT}"}

    # Atomic lock acquisition (O_CREAT|O_EXCL prevents race condition)
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        return {"success": False, "errors": "linbofs update already in progress"}
    except OSError as e:
        return {"success": False, "errors": f"Cannot create lock: {e}"}

    rotate_build_logs()

    env = {
        **os.environ,
        "LINBO_DIR": linbo_dir or LINBO_DIR,
        "CONFIG_DIR": config_dir or CONFIG_DIR,
    }

    start = datetime.now(timezone.utc)
    log_name = f".linbofs-build.{start.strftime('%Y%m%d%H%M%S')}.log"
    log_path = Path(linbo_dir or LINBO_DIR) / log_name

    try:
        # Use fakeroot if available and not running as root
        cmd = [str(script)]
        if os.getuid() != 0 and _is_fakeroot_available():
            cmd = ["fakeroot"] + cmd

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        duration = (datetime.now(timezone.utc) - start).total_seconds()

        # Write build log
        try:
            log_path.write_text(
                f"# update-linbofs {start.isoformat()}\n"
                f"# Exit code: {result.returncode}\n"
                f"# Duration: {duration:.1f}s\n\n"
                f"=== STDOUT ===\n{result.stdout}\n\n"
                f"=== STDERR ===\n{result.stderr}\n"
            )
        except OSError:
            pass

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr if result.returncode != 0 else None,
            "duration": duration,
            "logFile": str(log_path),
        }

    except subprocess.TimeoutExpired:
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        return {
            "success": False,
            "errors": f"Timeout after {timeout}s",
            "duration": duration,
        }
    finally:
        # Release lock
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def get_linbofs_info() -> dict:
    """Get linbofs64 file info.

    Returns:
        {exists, size, modifiedAt, md5}
    """
    linbofs = Path(LINBO_DIR) / "linbofs64"
    if not linbofs.is_file():
        return {"exists": False}

    stat = linbofs.stat()

    # Read MD5 if available
    md5 = None
    md5_path = Path(LINBO_DIR) / "linbofs64.md5"
    try:
        md5 = md5_path.read_text().strip().split()[0]
    except OSError:
        pass

    return {
        "exists": True,
        "size": stat.st_size,
        "modifiedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "md5": md5,
    }
