"""
LINBO image serving — serve images to caching servers.

Resolve, upload, stage and finalize image files under the LINBO images
directory. The client-side download counterpart lives in WIP/.
"""

import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from linuxmusterTools.common.checks import NameChecker


name_checker = NameChecker()
logger = logging.getLogger(__name__)

IMAGES_DIR = Path(os.environ.get("LINBO_DIR", "/srv/linbo")) / "images"


# =============================================================================
# Image Serving (server-side: serve images TO caching servers)
# =============================================================================


IMAGE_EXTS = {".qcow2", ".qdiff", ".cloop"}
INCOMING_DIR_NAME = ".incoming"

# The .macct file of an image holds the Samba secrets (unicodePwd,
# supplementalCredentials) of the client the image was taken from. The
# [linbo] rsync module serves the whole LINBO directory without login, as
# nobody, so this file has to stay root:root 0600, like linuxmuster-linbo7
# keeps it (rsync-post-upload.sh, linbo-torrent). The staging directory lies
# in that module too, and is closed as a whole while an upload waits there.
MACCT_EXT = ".macct"
MACCT_MODE = 0o600
STAGING_DIR_MODE = 0o700


def _restrict(path: Path, mode: int) -> None:
    """Set the mode of a path, and make it root's when running as root."""


    os.chmod(path, mode)
    if os.geteuid() == 0:
        os.chown(path, 0, 0)


def _staging_dir(images_dir: Path, image_name: str) -> Path:
    """Create the staging directory of an image, closed to other users.

    Both .incoming and its image subdirectory are set on every call, so a
    directory created before, or opened again by a recursive chown, is
    closed again.
    """


    incoming_dir = images_dir / INCOMING_DIR_NAME
    staging_dir = incoming_dir / image_name
    staging_dir.mkdir(mode=STAGING_DIR_MODE, parents=True, exist_ok=True)
    for directory in (incoming_dir, staging_dir):
        _restrict(directory, STAGING_DIR_MODE)
    return staging_dir


def _open_for_write(file_path: Path, flags: int):
    """Open a file for writing, a .macct one created and kept 0600.

    The mode is given to os.open() so a new .macct file never exists with a
    wider one, then set again on the descriptor for a file that already
    existed, or a umask that took the owner bits away.
    """


    flags |= os.O_WRONLY
    if file_path.suffix != MACCT_EXT:
        return os.fdopen(os.open(file_path, flags, 0o666), "wb")

    fd = os.open(file_path, flags, MACCT_MODE)
    try:
        os.fchmod(fd, MACCT_MODE)
        if os.geteuid() == 0:
            os.fchown(fd, 0, 0)
    except OSError:
        os.close(fd)
        raise
    return os.fdopen(fd, "wb")


def _copy_file(source: str | Path, target: str | Path) -> None:
    """Copy a file like shutil.copy2(), a .macct one without widening its mode.

    shutil.copy2() creates the copy with the umask default and copies the
    mode of the source afterwards: a .macct would be readable while it is
    written, and stay so if the source was. It is copied into a file opened
    0600 instead, keeping the times like copy2() does. Used for the backup,
    and by shutil.move() when the staged file lies on another filesystem.
    """


    source, target = Path(source), Path(target)
    if source.suffix != MACCT_EXT:
        shutil.copy2(str(source), str(target))
        return

    with open(source, "rb") as src, \
            _open_for_write(target, os.O_CREAT | os.O_TRUNC) as dst:
        shutil.copyfileobj(src, dst)
    stat = source.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def resolve_image_file(images_dir: Path, image_name: str, filename: str) -> Path:
    """Resolve and validate an image file path.

    Returns the absolute Path if valid and file exists.
    Raises ValueError for invalid paths, FileNotFoundError if missing.
    """


    image_name = name_checker.validate_linbo_image_name(image_name)
    filename = name_checker.validate_linbo_image_name(filename)

    file_path = (images_dir / image_name / filename).resolve()
    if not file_path.is_relative_to(images_dir.resolve()):
        raise ValueError("Path escapes images directory")
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {filename}")
    return file_path


def get_image_file_info(file_path: Path) -> dict:
    """Get metadata for an image file.

    Returns {size, mtime_ts, etag, last_modified}.
    """


    stat = file_path.stat()
    etag = hashlib.md5(
        f"{file_path}:{stat.st_mtime}:{stat.st_size}".encode()
    ).hexdigest()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return {
        "size": stat.st_size,
        "mtime_ts": stat.st_mtime,
        "etag": etag,
        "last_modified": mtime.strftime("%a, %d %b %Y %H:%M:%S GMT"),
    }


def receive_upload_chunk(
    images_dir: Path, image_name: str, filename: str,
    data: bytes, offset: int | None = None,
) -> dict:
    """Write a chunk of upload data to the staging directory.

    Args:
        images_dir: Base images directory
        image_name: Target image name
        filename: Target filename
        data: Chunk bytes
        offset: Byte offset for ranged writes (None = overwrite)

    Returns {received, offset}.
    """


    image_name = name_checker.validate_linbo_image_name(image_name)
    filename = name_checker.validate_linbo_image_name(filename)

    staging_dir = _staging_dir(images_dir, image_name)
    file_path = staging_dir / filename

    if offset is not None and offset > 0:
        if not file_path.exists():
            raise ValueError("Cannot resume upload without an existing staged file")
        current_size = file_path.stat().st_size
        if current_size != offset:
            raise ValueError(f"Offset mismatch: expected {current_size}, got {offset}")
        with _open_for_write(file_path, 0) as f:
            f.seek(offset)
            f.write(data)
    else:
        with _open_for_write(file_path, os.O_CREAT | os.O_TRUNC) as f:
            f.write(data)

    return {"received": len(data), "offset": (offset or 0) + len(data)}


def get_upload_status(images_dir: Path, image_name: str, filename: str) -> dict:
    """Check how many bytes have been received for a staged upload.

    Returns {bytesReceived, complete}.
    """


    image_name = name_checker.validate_linbo_image_name(image_name)
    filename = name_checker.validate_linbo_image_name(filename)

    file_path = images_dir / INCOMING_DIR_NAME / image_name / filename
    if not file_path.is_file():
        return {"bytesReceived": 0, "complete": False}
    return {"bytesReceived": file_path.stat().st_size, "complete": False}


def finalize_upload(images_dir: Path, image_name: str) -> dict:
    """Move staged files to final directory with backup.

    Backs up existing image files to a timestamped subdirectory
    before replacing them.

    Returns {finalized, files, backup}.
    Raises FileNotFoundError if no staged files exist.
    """


    image_name = name_checker.validate_linbo_image_name(image_name)

    staging_dir = images_dir / INCOMING_DIR_NAME / image_name
    if not staging_dir.is_dir():
        raise FileNotFoundError("No staged files found")

    target_dir = images_dir / image_name
    target_dir.mkdir(parents=True, exist_ok=True)

    # Backup existing image files before overwriting
    backup_dir = None
    existing_images = [
        f for f in target_dir.iterdir()
        if f.is_file() and f.suffix in IMAGE_EXTS
    ]
    if existing_images:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_dir = target_dir / "backup" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        for f in target_dir.iterdir():
            if f.is_file():
                try:
                    _copy_file(f, backup_dir / f.name)
                except OSError as e:
                    logger.warning("Backup failed for %s: %s", f.name, e)

        logger.info("Backed up existing image to %s", backup_dir)

    # Move staged files to target
    moved = []
    for f in staging_dir.iterdir():
        if f.is_file():
            target = target_dir / f.name
            # Before the move, which keeps the mode: a file staged before
            # the staging directory was closed can still be wider.
            if f.suffix == MACCT_EXT:
                _restrict(f, MACCT_MODE)
            shutil.move(str(f), str(target), copy_function=_copy_file)
            moved.append(f.name)

    # A .macct left from an earlier upload or an older version is closed too.
    for f in target_dir.iterdir():
        if f.is_file() and f.suffix == MACCT_EXT:
            _restrict(f, MACCT_MODE)

    try:
        staging_dir.rmdir()
    except OSError:
        pass

    logger.info("Image upload finalized: %s (%d files)", image_name, len(moved))
    return {
        "finalized": True,
        "files": moved,
        "backup": str(backup_dir) if backup_dir else None,
    }


def cancel_upload(images_dir: Path, image_name: str) -> dict:
    """Clean up staged upload files.

    Returns {cleaned, detail?}.
    """


    image_name = name_checker.validate_linbo_image_name(image_name)

    staging_dir = images_dir / INCOMING_DIR_NAME / image_name
    if staging_dir.is_dir():
        shutil.rmtree(str(staging_dir))
        return {"cleaned": True}
    return {"cleaned": False, "detail": "No staging directory found"}
