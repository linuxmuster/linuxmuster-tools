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

    staging_dir = images_dir / INCOMING_DIR_NAME / image_name
    staging_dir.mkdir(parents=True, exist_ok=True)
    file_path = staging_dir / filename

    if offset is not None and offset > 0:
        if not file_path.exists():
            raise ValueError("Cannot resume upload without an existing staged file")
        current_size = file_path.stat().st_size
        if current_size != offset:
            raise ValueError(f"Offset mismatch: expected {current_size}, got {offset}")
        with open(file_path, "r+b") as f:
            f.seek(offset)
            f.write(data)
    else:
        file_path.write_bytes(data)

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
                    shutil.copy2(str(f), str(backup_dir / f.name))
                except OSError as e:
                    logger.warning("Backup failed for %s: %s", f.name, e)

        logger.info("Backed up existing image to %s", backup_dir)

    # Move staged files to target
    moved = []
    for f in staging_dir.iterdir():
        if f.is_file():
            target = target_dir / f.name
            shutil.move(str(f), str(target))
            moved.append(f.name)

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
