"""
LINBO Image Sync — download QCOW2 images from remote server.

Supports HTTP Range requests for resume capability, MD5 verification,
and atomic directory swap on completion.
"""

import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from linuxmusterTools.common.checks import NameChecker

from .driver_hooks import (
    LinboDriverHookManager as _LinboDriverHookManager,
    validate_image_name as _validate_image_name,
)


name_checker = NameChecker()
logger = logging.getLogger(__name__)

IMAGES_DIR = Path(os.environ.get("LINBO_DIR", "/srv/linbo")) / "images"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB
IMAGE_EXTS = {".qcow2", ".qdiff", ".cloop"}
INCOMING_DIR_NAME = ".incoming"


def _validate_image_filename(filename: str) -> str:
    """Validate a generic LINBO image filename used for transport."""

    if not name_checker.check_linbo_image_name(filename):
        raise ValueError(f"Invalid LINBO image filename: {filename!r}")
    return filename


def _validate_upload_filename(filename: str) -> str:
    """Reject generated hooks from all image-ingestion paths.

    ``NameChecker`` returns a boolean; it never returns a sanitized name.
    Per-image ``.driverpostsync`` files are generated locally from the current
    profile assignments. They may be served to an authenticated cache server,
    but must never enter a local upload or remote-download ingestion path.
    """

    filename = _validate_image_filename(filename)
    if filename.endswith(".driverpostsync"):
        raise ValueError("driverpostsync hooks cannot be transferred as image files")
    return filename


def _image_base_from_filename(filename: str) -> str:
    """Return and validate the image-directory basename for ``filename``."""

    checked = _validate_upload_filename(filename)
    suffix = Path(checked).suffix.lower()
    base = checked[: -len(suffix)] if suffix in IMAGE_EXTS else checked
    return _validate_image_name(base)


def _contains_driverpostsync(directory: Path) -> bool:
    """Return whether a staging tree contains a companion hook name."""

    for _root, directories, files in os.walk(directory, followlinks=False):
        if any(name.endswith(".driverpostsync") for name in directories):
            return True
        if any(name.endswith(".driverpostsync") for name in files):
            return True
    return False


def _image_content_lifecycle(
    hook_manager: _LinboDriverHookManager,
    image_name: str,
):
    """Serialize image ingestion with profile-assignment mutations.

    The target directory is created by the caller before entering. Existing
    companion hooks remain ownership-protected even while a missing or broken
    canonical QCOW2 is being repaired.
    """

    return hook_manager.image_content_lifecycle(
        image_name,
        require_complete=False,
    )


def _file_md5(path: Path) -> str:
    """Return the MD5 of a file without loading it fully into memory."""
    md5_hash = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


class LinboImageSync:
    """
    Download and verify LINBO images from a remote server.
    """

    def __init__(
        self,
        images_dir: str | None = None,
        driver_hook_manager: _LinboDriverHookManager | None = None,
    ):
        self.images_dir = Path(images_dir) if images_dir else IMAGES_DIR
        self.driver_hook_manager = driver_hook_manager or _LinboDriverHookManager(
            images_root=self.images_dir,
        )

    def compare_manifests(self, local_images: list[dict], remote_images: list[dict]) -> dict:
        """
        Compare local and remote image lists.

        Returns:
            {toDownload, toDelete, upToDate} — lists of image names
        """


        local_map = {img["name"]: img for img in local_images}
        remote_map = {img["name"]: img for img in remote_images}

        to_download = []
        up_to_date = []

        for name, remote in remote_map.items():
            local = local_map.get(name)
            if not local:
                to_download.append(name)
            elif local.get("md5") != remote.get("md5"):
                to_download.append(name)
            else:
                up_to_date.append(name)

        to_delete = [name for name in local_map if name not in remote_map]

        return {
            "toDownload": to_download,
            "toDelete": to_delete,
            "upToDate": up_to_date,
        }

    def download_image(
        self,
        url: str,
        image_name: str,
        expected_md5: str | None = None,
        headers: dict | None = None,
        on_progress=None,
    ) -> dict:
        """
        Download an image file with resume support.

        Args:
            url: Full URL to the image file
            image_name: Target image name (e.g. "ubuntu22.qcow2")
            expected_md5: Expected MD5 for verification
            headers: Additional HTTP headers (e.g. auth)
            on_progress: Callback(bytes_received, total_bytes)

        Returns:
            {success, path, size, md5, duration}
        """


        image_name = _validate_upload_filename(image_name)
        base = _image_base_from_filename(image_name)
        target_dir = self.images_dir / base
        incoming_dir = self.images_dir / ".incoming" / base
        incoming_dir.mkdir(parents=True, exist_ok=True)
        target_file = incoming_dir / image_name

        start = datetime.now(timezone.utc)

        # Resume support
        resume_offset = 0
        if target_file.is_file():
            resume_offset = target_file.stat().st_size

        req_headers = dict(headers or {})
        if resume_offset > 0:
            req_headers["Range"] = f"bytes={resume_offset}-"

        try:
            req = Request(url, headers=req_headers)
            with urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0)) + resume_offset
                mode = "ab" if resume_offset > 0 else "wb"

                received = resume_offset

                with open(target_file, mode) as f:
                    while True:
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)
                        if on_progress:
                            on_progress(received, total)

            duration = (datetime.now(timezone.utc) - start).total_seconds()
            actual_md5 = _file_md5(target_file)

            # Verify MD5
            if expected_md5 and actual_md5 != expected_md5:
                logger.error("MD5 mismatch for %s: expected %s, got %s",
                             image_name, expected_md5, actual_md5)
                return {
                    "success": False,
                    "error": f"MD5 mismatch: expected {expected_md5}, got {actual_md5}",
                    "duration": duration,
                }

            # Publish under the same assignment lock used by the native image
            # lifecycle. Companion hooks are neither backed up nor replaced.
            target_dir.mkdir(parents=True, exist_ok=True)
            final_path = target_dir / image_name
            with _image_content_lifecycle(
                self.driver_hook_manager,
                base,
            ):
                if final_path.is_file():
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
                    backup_dir = target_dir / "backup" / timestamp
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    for existing in target_dir.iterdir():
                        if (
                            existing.is_file()
                            and not existing.name.endswith(".driverpostsync")
                        ):
                            shutil.copy2(
                                str(existing),
                                str(backup_dir / existing.name),
                            )
                    logger.info("Backed up existing image to %s", backup_dir)

                # The downloaded image is the final mutation for a new image,
                # so it becomes assignable only after publication is complete.
                shutil.move(str(target_file), str(final_path))

            # Cleanup incoming dir
            try:
                incoming_dir.rmdir()
            except OSError:
                pass

            return {
                "success": True,
                "path": str(final_path),
                "size": received,
                "md5": actual_md5,
                "duration": duration,
            }

        except (URLError, OSError) as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return {
                "success": False,
                "error": str(e),
                "duration": duration,
            }

    def delete_image(self, image_name: str) -> bool:
        """
        Delete an image and its directory through the native hook lifecycle.
        """

        base = _image_base_from_filename(image_name)
        target_dir = self.images_dir / base
        if target_dir.is_dir():
            # This holds the assignment lock for the entire removal, rejects
            # assigned images and foreign hooks, and removes/restores managed
            # tombstones transactionally on failure.
            with self.driver_hook_manager.unassigned_image_lifecycle(base):
                shutil.rmtree(str(target_dir))
            return True
        return False


# =============================================================================
# Image Serving (server-side: serve images TO caching servers)
# =============================================================================


def resolve_image_file(images_dir: Path, image_name: str, filename: str) -> Path:
    """Resolve and validate an image file path.

    Returns the absolute Path if valid and file exists.
    Raises ValueError for invalid paths, FileNotFoundError if missing.
    """


    image_name = _validate_image_name(image_name)
    filename = _validate_image_filename(filename)

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


    image_name = _validate_image_name(image_name)
    filename = _validate_upload_filename(filename)

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


    image_name = _validate_image_name(image_name)
    filename = _validate_upload_filename(filename)

    file_path = images_dir / INCOMING_DIR_NAME / image_name / filename
    if not file_path.is_file():
        return {"bytesReceived": 0, "complete": False}
    return {"bytesReceived": file_path.stat().st_size, "complete": False}


def finalize_upload(
    images_dir: Path,
    image_name: str,
    driver_hook_manager: _LinboDriverHookManager | None = None,
) -> dict:
    """Move staged files to final directory with backup.

    Backs up existing image files to a timestamped subdirectory
    before replacing them.

    Returns {finalized, files, backup}.
    Raises FileNotFoundError if no staged files exist.
    """


    image_name = _validate_image_name(image_name)

    staging_dir = images_dir / INCOMING_DIR_NAME / image_name
    if not staging_dir.is_dir():
        raise FileNotFoundError("No staged files found")
    if _contains_driverpostsync(staging_dir):
        raise ValueError("Staged uploads must not contain driverpostsync hooks")

    target_dir = images_dir / image_name
    target_dir.mkdir(parents=True, exist_ok=True)
    hook_manager = driver_hook_manager or _LinboDriverHookManager(
        images_root=images_dir,
    )

    with _image_content_lifecycle(hook_manager, image_name):
        # Backup existing image files before overwriting. The generated
        # companion hook represents live assignments, not image history.
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
                if f.is_file() and not f.name.endswith(".driverpostsync"):
                    try:
                        shutil.copy2(str(f), str(backup_dir / f.name))
                    except OSError as e:
                        logger.warning("Backup failed for %s: %s", f.name, e)

            logger.info("Backed up existing image to %s", backup_dir)

        # For an incomplete/new image move its canonical QCOW2 last. Native
        # assignments cannot target it until every other staged file is live.
        staged_files = [f for f in staging_dir.iterdir() if f.is_file()]
        canonical_name = f"{image_name}.qcow2"
        staged_files.sort(key=lambda path: path.name == canonical_name)
        moved = []
        for f in staged_files:
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


    image_name = _validate_image_name(image_name)

    staging_dir = images_dir / INCOMING_DIR_NAME / image_name
    if staging_dir.is_dir():
        shutil.rmtree(str(staging_dir))
        return {"cleaned": True}
    return {"cleaned": False, "detail": "No staging directory found"}
