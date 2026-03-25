"""
LINBO Firmware Management — detect missing firmware and manage config.

Combines dmesg parsing, filesystem scanning, and firmware config file
management for LINBO client firmware provisioning.
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

FIRMWARE_DIR = Path("/lib/firmware")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/etc/linuxmuster/linbo")
FIRMWARE_CONFIG = Path(CONFIG_DIR) / "firmware"
LINBO_LOG_DIR = Path(os.environ.get("LINBO_LOG_DIR", "/var/log/linuxmuster/linbo"))

# dmesg patterns
_MISSING_PATTERNS = [
    re.compile(r"firmware:\s+failed to load\s+(\S+)", re.IGNORECASE),
    re.compile(r"Direct firmware load for\s+(\S+)\s+failed", re.IGNORECASE),
    re.compile(r"request_firmware\s+failed.*?:\s+(\S+)", re.IGNORECASE),
]
_LOADED_PATTERN = re.compile(r"loaded firmware\s+(?:version\s+)?(\S+)", re.IGNORECASE)
_DRIVER_PATTERN = re.compile(r"\]\s+(\S+)\s+\S+:\s+(?:firmware|Direct firmware)")
_SAFE_PATH = re.compile(r"^[a-zA-Z0-9._/-]+$")


def _clean_filename(raw: str) -> str:
    """Clean firmware filename from dmesg output."""
    name = raw
    if name.startswith("/lib/firmware/"):
        name = name[len("/lib/firmware/"):]
    name = re.sub(r"[,;:)]+$", "", name)
    return name


def parse_dmesg_firmware(output: str) -> list[dict]:
    """Parse dmesg output for firmware events.

    Args:
        output: Raw dmesg output

    Returns:
        List of {filename, driver, status} dicts
    """
    if not output or not isinstance(output, str):
        return []

    events = []
    seen = set()

    for line in output.splitlines():
        if not line.strip():
            continue

        matched = False
        for pattern in _MISSING_PATTERNS:
            m = pattern.search(line)
            if m:
                filename = _clean_filename(m.group(1))
                driver_m = _DRIVER_PATTERN.search(line)
                driver = driver_m.group(1) if driver_m else None
                key = f"missing:{filename}"
                if key not in seen:
                    seen.add(key)
                    events.append({"filename": filename, "driver": driver, "status": "missing"})
                matched = True
                break

        if not matched:
            m = _LOADED_PATTERN.search(line)
            if m:
                filename = _clean_filename(m.group(1))
                driver_m = _DRIVER_PATTERN.search(line)
                driver = driver_m.group(1) if driver_m else None
                key = f"loaded:{filename}"
                if key not in seen:
                    seen.add(key)
                    events.append({"filename": filename, "driver": driver, "status": "loaded"})

    return events


def extract_missing_firmware_paths(output: str) -> list[str]:
    """Extract sorted, deduplicated list of missing firmware paths."""
    events = parse_dmesg_firmware(output)
    return sorted({e["filename"] for e in events if e["status"] == "missing"})


_FW_FAILED_PATTERN = re.compile(r"for\s+(\S+)\s+failed", re.IGNORECASE)


def get_firmware_health(log_dir: str | Path | None = None) -> dict:
    """Parse LINBO client boot logs for firmware errors.

    Reads *_linbo.log files from the log directory and extracts missing
    firmware names using the same regex as update-linbofs parse_firmware_logs.
    Falls back to compressed .1.gz logs if the current log is empty.

    Args:
        log_dir: Override log directory (default: /var/log/linuxmuster/linbo)

    Returns:
        {clients: [{hostname, status, missingFirmware}], summary: {total, ok, missing, noLog}}
    """
    base = Path(log_dir) if log_dir else LINBO_LOG_DIR
    if not base.is_dir():
        return {"clients": [], "summary": {"total": 0, "ok": 0, "missing": 0, "noLog": 0}}

    results = []
    try:
        entries = os.listdir(base)
    except OSError:
        return {"clients": [], "summary": {"total": 0, "ok": 0, "missing": 0, "noLog": 0}}

    log_files = [f for f in entries if f.endswith("_linbo.log") and not f.startswith("UNKNOWN")]

    for log_file in sorted(log_files):
        hostname = log_file.removesuffix("_linbo.log")
        log_path = base / log_file
        compressed_path = base / (log_file + ".1.gz")

        log_content = ""
        try:
            log_content = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

        # Fallback to compressed previous log
        if not log_content.strip():
            try:
                import gzip
                with gzip.open(compressed_path, "rt", encoding="utf-8", errors="replace") as gz:
                    log_content = gz.read()
            except (OSError, ImportError):
                pass

        if not log_content.strip():
            results.append({"hostname": hostname, "status": "no-log", "missingFirmware": []})
            continue

        # Parse firmware errors
        missing_firmware = []
        seen = set()
        for line in log_content.splitlines():
            lower = line.lower()
            if "firmware" in lower and ("failed" in lower or "error" in lower):
                m = _FW_FAILED_PATTERN.search(line)
                if m and m.group(1) not in seen:
                    seen.add(m.group(1))
                    missing_firmware.append(m.group(1))

        results.append({
            "hostname": hostname,
            "status": "missing" if missing_firmware else "ok",
            "missingFirmware": missing_firmware,
        })

    ok = sum(1 for r in results if r["status"] == "ok")
    missing = sum(1 for r in results if r["status"] == "missing")
    no_log = sum(1 for r in results if r["status"] == "no-log")

    return {
        "clients": results,
        "summary": {"total": len(results), "ok": ok, "missing": missing, "noLog": no_log},
    }


class LinboFirmwareManager:
    """Manage LINBO firmware configuration."""

    def __init__(self, config_path: str | None = None):
        self.config_path = Path(config_path) if config_path else FIRMWARE_CONFIG

    def read_config(self) -> list[str]:
        """Read firmware config (list of firmware paths, one per line)."""
        try:
            text = self.config_path.read_text(encoding="utf-8")
            return [l.strip() for l in text.splitlines()
                    if l.strip() and not l.strip().startswith("#")]
        except FileNotFoundError:
            return []

    def write_config(self, entries: list[str]) -> None:
        """Write firmware config file.

        Args:
            entries: List of firmware paths

        Raises:
            ValueError: If any entry contains unsafe characters
        """
        for entry in entries:
            if not _SAFE_PATH.match(entry):
                raise ValueError(f"Unsafe firmware path: {entry}")
            if ".." in entry or "\0" in entry:
                raise ValueError(f"Path traversal not allowed: {entry}")

        header = f"# LINBO firmware config — generated {datetime.now(timezone.utc).isoformat()}\n"
        self.config_path.write_text(
            header + "\n".join(entries) + "\n",
            encoding="utf-8",
        )

    def add_entry(self, entry: str) -> list[str]:
        """Add a firmware entry. Returns updated list."""
        entries = self.read_config()
        if entry not in entries:
            entries.append(entry)
            self.write_config(entries)
        return entries

    def remove_entry(self, entry: str) -> list[str]:
        """Remove a firmware entry. Returns updated list."""
        entries = self.read_config()
        entries = [e for e in entries if e != entry]
        self.write_config(entries)
        return entries

    def validate_entry(self, entry: str) -> dict:
        """Check if a firmware file exists on disk.

        Returns:
            {path, exists, zstExists}
        """
        fw_path = FIRMWARE_DIR / entry
        zst_path = FIRMWARE_DIR / f"{entry}.zst"
        return {
            "path": entry,
            "exists": fw_path.is_file(),
            "zstExists": zst_path.is_file(),
        }

    def scan_available(self, base_dir: str | None = None, max_depth: int = 3) -> list[str]:
        """Scan /lib/firmware/ for available firmware files.

        Args:
            base_dir: Override firmware directory
            max_depth: Maximum directory depth

        Returns:
            Sorted list of relative firmware paths
        """
        root = Path(base_dir) if base_dir else FIRMWARE_DIR
        if not root.is_dir():
            return []

        results = []
        for dirpath, _dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth > max_depth:
                continue
            for f in filenames:
                rel = str(Path(dirpath, f).relative_to(root))
                results.append(rel)

        return sorted(results)
