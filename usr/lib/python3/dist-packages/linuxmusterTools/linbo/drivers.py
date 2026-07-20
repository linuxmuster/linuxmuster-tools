"""Manage the metadata of hardware-specific LINBO driver profiles.

This module deliberately owns only profile directories and their canonical
``match.conf``.  Hardware inventory, image assignments, postsync generation,
archive extraction and driver payload validation belong to separate changes.
"""

import fcntl
import logging
import os
import re
import shutil
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path

from configobj import ConfigObjError

from ..common.checks import NameChecker
from ..lmnfile import LMNFile


__all__ = ["DriverProfileExistsError", "LinboDriverManager"]


logger = logging.getLogger(__name__)
name_checker = NameChecker()

DEFAULT_DRIVERS_BASE = Path(
    os.environ.get("DRIVERS_BASE", "/srv/linbo/drivers")
)
MATCH_CONF_FILENAME = "match.conf"
MAX_MATCH_VALUE_LENGTH = 512
MUTATION_LOCK_FILENAME = ".driver-profiles.lock"

_MATCH_VALUE = re.compile(r"^[a-zA-Z0-9 .,()/_+-]+$")
_WINDOWS_RESERVED_STEMS = frozenset(
    {
        "aux",
        "con",
        "nul",
        "prn",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
)


class DriverProfileExistsError(FileExistsError):
    """Raised when a new profile would replace an existing path."""

    def __init__(self, profile):
        super().__init__(f"Driver profile already exists: {profile}")
        self.profile = profile


def _validated_profile_name(name):
    """Return a profile name compatible with LMN paths and Windows."""

    if not isinstance(name, str):
        raise ValueError("Profile name must be a string.")

    normalized = name.strip()
    if (
        not name_checker.check_linbo_image_name(normalized)
        or not normalized[0].isalnum()
        or len(normalized) > 100
        or normalized.endswith(".")
    ):
        raise ValueError(
            "Profile name must start with an alphanumeric character, contain "
            "only [a-zA-Z0-9._-], and be at most 100 characters long."
        )

    windows_stem = normalized.partition(".")[0].casefold()
    if (
        windows_stem in _WINDOWS_RESERVED_STEMS
        or normalized.casefold() == "pnputil-install.cmd"
    ):
        raise ValueError(f"Windows-reserved profile name: {normalized}")
    return normalized


def _validated_match(vendor, product):
    """Validate one canonical DMI vendor/product pair."""

    result = {}
    for field, value in (("vendor", vendor), ("product", product)):
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string.")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field} must not be empty.")
        if len(normalized) > MAX_MATCH_VALUE_LENGTH:
            raise ValueError(
                f"{field} is too long (max {MAX_MATCH_VALUE_LENGTH} characters)."
            )
        if normalized != "*" and not _MATCH_VALUE.fullmatch(normalized):
            raise ValueError(f"{field} contains unsupported characters.")
        result[field] = normalized
    return result


@contextmanager
def _mutation_lock(base):
    """Serialize the short profile metadata mutations between API workers."""

    lock_path = Path(base) / MUTATION_LOCK_FILENAME
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    lock_fd = os.open(str(lock_path), flags, 0o600)
    locked = False
    try:
        metadata = os.fstat(lock_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Driver profile lock is not a regular file: {lock_path}")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        locked = True
        yield
    finally:
        if locked:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


class LinboDriverManager:
    """Create, read, update and delete LINBO driver profile metadata."""

    def __init__(self, drivers_base=None):
        self.base = (
            Path(drivers_base)
            if drivers_base is not None
            else DEFAULT_DRIVERS_BASE
        )

    def _ensure_base_directory(self):
        if os.path.lexists(self.base):
            mode = self.base.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise ValueError(
                    f"Driver profile base is not a real directory: {self.base}"
                )
            return

        self.base.mkdir(parents=True, mode=0o755, exist_ok=True)
        mode = self.base.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ValueError(
                f"Driver profile base is not a real directory: {self.base}"
            )

    @staticmethod
    def _write_match_conf(path, match):
        is_new = not os.path.lexists(path)
        with LMNFile(
            str(path),
            "w",
            convert_values=False,
        ) as match_file:
            data = match_file.read()
            data.clear()
            data["match"] = match
            match_file.write(data)
        if is_new:
            path.chmod(0o644)

    def list_profiles(self):
        """Return every complete, valid profile sorted by name."""

        if not os.path.lexists(self.base):
            return []
        self._ensure_base_directory()

        profiles = []
        for candidate in sorted(self.base.iterdir(), key=lambda path: path.name):
            if candidate.name.startswith("."):
                continue
            try:
                profile = self.get_profile(candidate.name)
            except (OSError, ValueError, ConfigObjError) as error:
                logger.warning(
                    "Ignoring invalid driver profile %s: %s",
                    candidate.name,
                    error,
                )
                continue
            if profile is not None:
                profiles.append(profile)
        return profiles

    def get_profile(self, name):
        """Return one valid profile or ``None`` when its path is absent."""

        safe_name = _validated_profile_name(name)
        if not os.path.lexists(self.base):
            return None
        self._ensure_base_directory()
        profile_path = self.base / safe_name
        try:
            profile_mode = profile_path.lstat().st_mode
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(profile_mode) or not stat.S_ISDIR(profile_mode):
            raise ValueError(
                f"Driver profile path is not a real directory: {safe_name}"
            )

        match_path = profile_path / MATCH_CONF_FILENAME
        try:
            match_mode = match_path.lstat().st_mode
        except FileNotFoundError as error:
            raise ValueError(
                f"Driver profile has no {MATCH_CONF_FILENAME}: {safe_name}"
            ) from error
        if stat.S_ISLNK(match_mode) or not stat.S_ISREG(match_mode):
            raise ValueError(
                f"Driver profile {MATCH_CONF_FILENAME} is not a regular file: "
                f"{safe_name}"
            )

        try:
            with LMNFile(
                str(match_path),
                "r",
                convert_values=False,
            ) as match_file:
                data = match_file.read()
        except ConfigObjError as error:
            raise ValueError(
                f"Invalid {MATCH_CONF_FILENAME} for driver profile {safe_name}: "
                f"{error}"
            ) from error

        if set(data.keys()) != {"match"}:
            raise ValueError(
                f"{MATCH_CONF_FILENAME} must contain exactly one [match] section."
            )
        if data.inline_comments.get("match"):
            raise ValueError(
                f"{MATCH_CONF_FILENAME} must not contain inline comments."
            )
        section = data["match"]
        if (
            not isinstance(section, dict)
            or set(section.keys()) != {"vendor", "product"}
        ):
            raise ValueError(
                "[match] must contain exactly one vendor and one product."
            )
        if any(section.inline_comments.get(key) for key in section):
            raise ValueError(
                f"{MATCH_CONF_FILENAME} must not contain inline comments."
            )
        match = _validated_match(section["vendor"], section["product"])

        return {
            "name": safe_name,
            "path": str(profile_path),
            "matchConf": match,
        }

    def create_profile(self, name, vendor, product):
        """Create a profile without replacing any existing path."""

        safe_name = _validated_profile_name(name)
        match = _validated_match(vendor, product)
        self._ensure_base_directory()

        with _mutation_lock(self.base):
            with os.scandir(self.base) as entries:
                collision = any(
                    entry.name.casefold() == safe_name.casefold()
                    or entry.name.casefold().startswith(
                        f".{safe_name.casefold()}.deleting-"
                    )
                    for entry in entries
                )
            if collision:
                raise DriverProfileExistsError(safe_name)

            profile_path = self.base / safe_name
            try:
                profile_path.mkdir(mode=0o755)
            except FileExistsError as error:
                raise DriverProfileExistsError(safe_name) from error

            try:
                self._write_match_conf(
                    profile_path / MATCH_CONF_FILENAME,
                    match,
                )
            except Exception:
                try:
                    profile_path.rmdir()
                except OSError:
                    pass
                raise

        return self.get_profile(safe_name)

    def update_match(self, name, vendor, product):
        """Replace only ``match.conf`` and preserve all driver payload files."""

        match = _validated_match(vendor, product)
        if not os.path.lexists(self.base):
            raise FileNotFoundError(f"Driver profile not found: {name}")
        self._ensure_base_directory()
        with _mutation_lock(self.base):
            profile = self.get_profile(name)
            if profile is None:
                raise FileNotFoundError(f"Driver profile not found: {name}")

            self._write_match_conf(
                Path(profile["path"]) / MATCH_CONF_FILENAME,
                match,
            )
        return self.get_profile(profile["name"])

    def delete_profile(self, name):
        """Delete a valid managed profile and return whether it existed."""

        if not os.path.lexists(self.base):
            return False
        self._ensure_base_directory()
        with _mutation_lock(self.base):
            profile = self.get_profile(name)
            if profile is None:
                return False
            profile_path = Path(profile["path"])
            quarantine = self.base / (
                f".{profile['name']}.deleting-{uuid.uuid4().hex}"
            )
            profile_path.rename(quarantine)

        try:
            shutil.rmtree(quarantine)
        except Exception:
            with _mutation_lock(self.base):
                if not os.path.lexists(profile_path) and os.path.lexists(quarantine):
                    quarantine.rename(profile_path)
            raise
        return True
