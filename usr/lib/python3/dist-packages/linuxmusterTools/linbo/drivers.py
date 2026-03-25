"""
LINBO Driver Management — driver profile creation and match.conf handling.

Manages driver profiles that match hardware (via DMI vendor/product)
to driver sets for injection into linbofs64.
"""

import configparser
import logging
import os
import re
import shutil
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

DRIVERS_BASE = os.environ.get("DRIVERS_BASE", "/var/lib/linbo/drivers")
MAX_ZIP_ENTRIES = 50_000
MAX_ZIP_SIZE = 4 * 1024 * 1024 * 1024  # 4 GB

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$")
_SAFE_REL_PATH = re.compile(r"^[a-zA-Z0-9._/-]+$")


def sanitize_name(name: str) -> str:
    """Validate and return a sanitized driver profile name.

    Raises:
        ValueError: If name is invalid
    """
    if not name or not isinstance(name, str):
        raise ValueError("Name must not be empty")
    name = name.strip()
    if not _SAFE_NAME.match(name):
        raise ValueError(
            "Name must start with alphanumeric, contain only [a-zA-Z0-9._-], max 100 chars"
        )
    return name


def sanitize_relative_path(rel_path: str) -> str:
    """Validate a relative file path (no traversal).

    Raises:
        ValueError: If path is unsafe
    """
    if not rel_path or not isinstance(rel_path, str):
        raise ValueError("Path must not be empty")
    rel_path = rel_path.strip()

    if rel_path.startswith("/"):
        raise ValueError("Absolute paths not allowed")
    if "\\" in rel_path:
        raise ValueError("Backslashes not allowed")
    if "\0" in rel_path:
        raise ValueError("NUL bytes not allowed")
    for seg in rel_path.split("/"):
        if seg == "..":
            raise ValueError("Path traversal not allowed")

    return re.sub(r"/+", "/", rel_path).rstrip("/")


class LinboDriverManager:
    """Manage LINBO driver profiles."""

    def __init__(self, drivers_base: str | None = None):
        self.base = Path(drivers_base or DRIVERS_BASE)

    def list_profiles(self) -> list[dict]:
        """List all driver profiles with match.conf info.

        Returns:
            List of {name, path, hasMatchConf, matchConf} dicts
        """
        if not self.base.is_dir():
            return []

        profiles = []
        for d in sorted(self.base.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            match_conf = d / "match.conf"
            profile = {
                "name": d.name,
                "path": str(d),
                "hasMatchConf": match_conf.is_file(),
            }
            if match_conf.is_file():
                profile["matchConf"] = self._parse_match_conf(match_conf)
            profiles.append(profile)

        return profiles

    def get_profile(self, name: str) -> dict | None:
        """Get a single profile by name."""
        name = sanitize_name(name)
        profile_dir = self.base / name
        if not profile_dir.is_dir():
            return None

        match_conf = profile_dir / "match.conf"
        files = self._list_files(profile_dir)

        return {
            "name": name,
            "path": str(profile_dir),
            "hasMatchConf": match_conf.is_file(),
            "matchConf": self._parse_match_conf(match_conf) if match_conf.is_file() else None,
            "files": files,
            "totalSize": sum(f["size"] for f in files),
        }

    def create_profile(self, name: str, vendor: str = "", product: str = "") -> dict:
        """Create a new driver profile with match.conf.

        Args:
            name: Profile name
            vendor: DMI sys_vendor string
            product: DMI product_name string

        Returns:
            Created profile dict
        """
        name = sanitize_name(name)
        profile_dir = self.base / name
        profile_dir.mkdir(parents=True, exist_ok=True)

        match_conf = profile_dir / "match.conf"
        match_conf.write_text(
            f"[match]\n"
            f"sys_vendor = {vendor}\n"
            f"product_name = {product}\n",
            encoding="utf-8",
        )

        return self.get_profile(name)

    def delete_profile(self, name: str) -> bool:
        """Delete a driver profile entirely."""
        name = sanitize_name(name)
        profile_dir = self.base / name
        if not profile_dir.is_dir():
            return False
        shutil.rmtree(str(profile_dir))
        return True

    def extract_archive(self, name: str, archive_path: str) -> dict:
        """Extract a ZIP archive into a driver profile.

        Args:
            name: Profile name
            archive_path: Path to ZIP file

        Returns:
            {extracted, totalSize}

        Raises:
            ValueError: If archive exceeds limits
        """
        name = sanitize_name(name)
        profile_dir = self.base / name
        profile_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as zf:
            entries = zf.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ValueError(f"Too many entries: {len(entries)} (max {MAX_ZIP_ENTRIES})")

            total_size = sum(e.file_size for e in entries)
            if total_size > MAX_ZIP_SIZE:
                raise ValueError(f"Archive too large: {total_size} bytes (max {MAX_ZIP_SIZE})")

            # Validate paths (no traversal)
            for entry in entries:
                if entry.filename.startswith("/") or ".." in entry.filename:
                    raise ValueError(f"Unsafe path in archive: {entry.filename}")

            zf.extractall(str(profile_dir))

        return {
            "extracted": len(entries),
            "totalSize": total_size,
        }

    def _parse_match_conf(self, path: Path) -> dict:
        """Parse match.conf INI file."""
        result = {}
        try:
            cp = configparser.ConfigParser()
            cp.read(str(path))
            if cp.has_section("match"):
                result = dict(cp["match"])
        except configparser.Error:
            pass
        return result

    def _list_files(self, directory: Path) -> list[str]:
        """List files in a profile directory (excluding match.conf)."""
        files = []
        for f in sorted(directory.rglob("*")):
            if f.is_file() and f.name != "match.conf":
                stat = f.stat()
                files.append({
                    "name": str(f.relative_to(directory)),
                    "size": stat.st_size,
                })
        return files
