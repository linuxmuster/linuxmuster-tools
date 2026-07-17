"""Filesystem primitives for LINBO driver profiles.

All mutating helpers operate inside a caller-provided driver base directory.
Writes use a temporary file in the destination directory followed by
``os.replace`` so readers see either the old or the complete new file.
"""

from __future__ import annotations

import errno
import fcntl
import os
import re
import shutil
import stat
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


__all__ = [
    "StorageSecurityError",
    "atomic_write",
    "atomic_write_text",
    "delete_profile_directory",
    "file_lock",
    "fsync_directory",
    "iter_profile_directories",
    "list_regular_files",
    "mutation_lock",
    "profile_path",
    "read_bytes_limited",
    "read_text_limited",
    "require_profile_directory",
    "require_regular_file",
    "validate_profile_name",
]


_SAFE_PROFILE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$")
_LOCK_FILENAME = ".driver-profiles.lock"


class StorageSecurityError(ValueError):
    """Raised when a path is unsafe for profile operations."""


def validate_profile_name(name: str) -> str:
    """Validate and normalize a driver profile directory name."""

    if not isinstance(name, str):
        raise ValueError("profile name must be a string")
    normalized = name.strip()
    if not _SAFE_PROFILE_NAME.fullmatch(normalized):
        raise ValueError(
            "profile name must start with an alphanumeric character, contain "
            "only [a-zA-Z0-9._-], and be at most 100 characters long"
        )
    return normalized


def _ensure_base_directory(base: Path) -> Path:
    base = Path(base)
    if not os.path.lexists(base):
        # ``exist_ok`` closes the normal first-writer race between API worker
        # processes.  The lstat below still rejects a symlink or non-directory
        # that won the race.
        base.mkdir(parents=True, mode=0o755, exist_ok=True)
    mode = base.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise StorageSecurityError(f"driver base is not a real directory: {base}")
    return base


def profile_path(base: Path, name: str) -> Path:
    """Return a profile path after validating its single path component."""

    safe_name = validate_profile_name(name)
    return Path(base) / safe_name


def require_profile_directory(base: Path, name: str) -> Path:
    """Return an existing, non-symlink profile directory."""

    path = profile_path(base, name)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(f"driver profile not found: {validate_profile_name(name)}")
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise StorageSecurityError(f"profile path is not a real directory: {path.name}")
    return path


def require_regular_file(path: Path) -> Path:
    """Require a non-symlink regular file."""

    path = Path(path)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(f"file not found: {path}")
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise StorageSecurityError(f"path is not a regular file: {path}")
    return path


def read_bytes_limited(
    path: Path,
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    """Read a bounded regular file without following the final symlink.

    The returned metadata comes from the opened descriptor, not from a
    separate path lookup.  File-type, size, and symlink rejections use plain
    ``OSError`` values so domain-specific callers can translate them into
    their own public errors.
    """

    if (
        not isinstance(max_bytes, int)
        or isinstance(max_bytes, bool)
        or max_bytes < 0
    ):
        raise ValueError("max_bytes must be a non-negative integer")

    file_path = Path(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow:
        flags |= no_follow

    # Linux provides O_NOFOLLOW.  Keep a fail-closed fallback for platforms
    # and unit tests that do not expose it.  Comparing the opened descriptor
    # with the preceding lstat also detects a path replacement during open.
    fallback_stat: os.stat_result | None = None
    if not no_follow:
        fallback_stat = os.lstat(file_path)
        if stat.S_ISLNK(fallback_stat.st_mode):
            raise OSError(
                errno.ELOOP,
                "Too many levels of symbolic links",
                str(file_path),
            )
        if not stat.S_ISREG(fallback_stat.st_mode):
            raise OSError(errno.EINVAL, "Not a regular file", str(file_path))

    file_fd = os.open(str(file_path), flags)

    try:
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError(errno.EINVAL, "Not a regular file", str(file_path))
        if fallback_stat is not None and not os.path.samestat(
            fallback_stat,
            metadata,
        ):
            raise OSError(
                errno.ELOOP,
                "File changed while it was being opened",
                str(file_path),
            )
        if metadata.st_size > max_bytes:
            raise OSError(
                errno.EFBIG,
                f"File exceeds {max_bytes} bytes",
                str(file_path),
            )

        payload = bytearray()
        while len(payload) <= max_bytes:
            chunk = os.read(file_fd, min(64 * 1024, max_bytes + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > max_bytes:
            raise OSError(
                errno.EFBIG,
                f"File exceeds {max_bytes} bytes",
                str(file_path),
            )
        return bytes(payload), metadata
    finally:
        os.close(file_fd)


def read_text_limited(path: Path, max_bytes: int) -> str:
    """Read a UTF-8 regular file while preserving storage error semantics."""

    file_path = Path(path)
    try:
        payload, _ = read_bytes_limited(file_path, max_bytes)
    except FileNotFoundError:
        raise FileNotFoundError(f"file not found: {file_path}") from None
    except OSError as exc:
        if exc.errno == errno.EFBIG:
            raise ValueError(
                f"file is too large: more than {max_bytes} bytes (max {max_bytes})"
            ) from exc
        if exc.errno == errno.EINVAL:
            raise StorageSecurityError(
                f"path is not a regular file: {file_path}"
            ) from exc
        raise StorageSecurityError(
            f"cannot safely open file: {file_path}: {exc}"
        ) from exc
    return payload.decode("utf-8")


def fsync_directory(directory: Path) -> None:
    """Persist directory metadata after an atomic rename or unlink."""

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    directory_fd = os.open(str(directory), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def atomic_write(path: Path, content: str | bytes, mode: int = 0o644) -> None:
    """Atomically replace a text or byte file and remove failed temporaries."""

    if isinstance(content, str):
        payload = content.encode("utf-8")
    elif isinstance(content, bytes):
        payload = content
    else:
        raise TypeError("content must be a string or bytes")

    target = Path(path)
    parent = target.parent
    parent_mode = parent.lstat().st_mode
    if stat.S_ISLNK(parent_mode) or not stat.S_ISDIR(parent_mode):
        raise StorageSecurityError(f"target parent is not a real directory: {parent}")
    if os.path.lexists(target):
        target_mode = target.lstat().st_mode
        if stat.S_ISLNK(target_mode) or not stat.S_ISREG(target_mode):
            raise StorageSecurityError(f"target is not a regular file: {target}")

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp-",
        dir=str(parent),
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, mode)
        offset = 0
        while offset < len(payload):
            offset += os.write(fd, payload[offset:])
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(temporary, target)
        fsync_directory(parent)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_write_text(path: Path, content: str, mode: int = 0o644) -> None:
    """Atomically replace a UTF-8 text file and remove failed temporaries."""

    if not isinstance(content, str):
        raise TypeError("content must be a string")
    atomic_write(path, content, mode)


@contextmanager
def file_lock(lock_path: Path, *, create_parent: bool = False) -> Iterator[Path]:
    """Hold an exclusive process lock on a real, non-symlink regular file."""

    path = Path(lock_path)
    parent = path.parent
    if create_parent:
        _ensure_base_directory(parent)
    else:
        try:
            parent_mode = parent.lstat().st_mode
        except FileNotFoundError:
            raise StorageSecurityError(f"lock parent does not exist: {parent}") from None
        if stat.S_ISLNK(parent_mode) or not stat.S_ISDIR(parent_mode):
            raise StorageSecurityError(f"lock parent is not a real directory: {parent}")

    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        lock_fd = os.open(str(path), flags, 0o600)
    except OSError as exc:
        raise StorageSecurityError(f"cannot open lock file {path}: {exc}") from exc

    locked = False
    try:
        metadata = os.fstat(lock_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise StorageSecurityError(f"lock is not a regular file: {path}")
        os.fchmod(lock_fd, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        locked = True
        yield path
    finally:
        if locked:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


@contextmanager
def mutation_lock(base: Path) -> Iterator[Path]:
    """Serialize profile mutations across API worker processes."""

    directory = _ensure_base_directory(Path(base))
    with file_lock(directory / _LOCK_FILENAME):
        yield directory


def iter_profile_directories(base: Path) -> Iterator[Path]:
    """Yield visible, syntactically valid, non-symlink profile directories."""

    directory = Path(base)
    if not os.path.lexists(directory):
        return
    mode = directory.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise StorageSecurityError(f"driver base is not a real directory: {directory}")

    for entry in sorted(directory.iterdir(), key=lambda item: item.name):
        if entry.name.startswith("."):
            continue
        try:
            validate_profile_name(entry.name)
            entry_mode = entry.lstat().st_mode
        except (ValueError, OSError):
            continue
        if stat.S_ISDIR(entry_mode) and not stat.S_ISLNK(entry_mode):
            yield entry


def list_regular_files(
    directory: Path,
    *,
    excluded_relative_paths: frozenset[str] = frozenset(),
) -> list[dict]:
    """List regular files recursively without following symbolic links."""

    root = Path(directory)
    root_mode = root.lstat().st_mode
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise StorageSecurityError(f"path is not a real directory: {root}")

    result = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for dirname in list(dirnames):
            candidate = current_path / dirname
            if candidate.is_symlink():
                raise StorageSecurityError(f"symbolic link in driver profile: {candidate}")
        dirnames.sort()

        for filename in sorted(filenames):
            candidate = current_path / filename
            relative = candidate.relative_to(root).as_posix()
            if relative in excluded_relative_paths:
                continue
            candidate_mode = candidate.lstat().st_mode
            if stat.S_ISLNK(candidate_mode):
                raise StorageSecurityError(f"symbolic link in driver profile: {candidate}")
            if not stat.S_ISREG(candidate_mode):
                raise StorageSecurityError(f"special file in driver profile: {candidate}")
            result.append({"name": relative, "size": candidate.stat().st_size})
    return result


def delete_profile_directory(base: Path, name: str) -> None:
    """Remove a profile via a reversible same-filesystem quarantine rename."""

    profile = require_profile_directory(base, name)
    quarantine = Path(base) / f".{profile.name}.deleting-{uuid.uuid4().hex}"
    os.rename(profile, quarantine)
    fsync_directory(Path(base))
    try:
        shutil.rmtree(quarantine)
        fsync_directory(Path(base))
    except Exception:
        if not os.path.lexists(profile) and os.path.lexists(quarantine):
            os.rename(quarantine, profile)
            fsync_directory(Path(base))
        raise
