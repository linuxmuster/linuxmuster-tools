"""
LINBO Image Sync — download QCOW2 images from remote server.

Supports HTTP Range requests for resume capability, MD5 verification,
and atomic directory swap on completion.
"""

import hashlib
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

IMAGES_DIR = Path(os.environ.get("LINBO_DIR", "/srv/linbo")) / "images"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


class LinboImageSync:
    """Download and verify LINBO images from a remote server."""

    def __init__(self, images_dir: str | None = None):
        self.images_dir = Path(images_dir) if images_dir else IMAGES_DIR

    def compare_manifests(self, local_images: list[dict], remote_images: list[dict]) -> dict:
        """Compare local and remote image lists.

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

    @staticmethod
    def _validate_image_name(name: str) -> str:
        """Validate image name for path safety."""
        if not name or not isinstance(name, str):
            raise ValueError("Image name must not be empty")
        if "/" in name or "\\" in name or ".." in name or "\0" in name:
            raise ValueError(f"Unsafe image name: {name}")
        from ._validation import check_linbo_image_name
        if not check_linbo_image_name(name):
            raise ValueError(f"Invalid image name characters: {name}")
        return name

    def download_image(
        self,
        url: str,
        image_name: str,
        expected_md5: str | None = None,
        headers: dict | None = None,
        on_progress=None,
    ) -> dict:
        """Download an image file with resume support.

        Args:
            url: Full URL to the image file
            image_name: Target image name (e.g. "ubuntu22.qcow2")
            expected_md5: Expected MD5 for verification
            headers: Additional HTTP headers (e.g. auth)
            on_progress: Callback(bytes_received, total_bytes)

        Returns:
            {success, path, size, md5, duration}
        """
        image_name = self._validate_image_name(image_name)
        base = image_name.rsplit(".", 1)[0] if "." in image_name else image_name
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

            # Hash the complete file (not just new bytes) for correct
            # verification after resumed downloads
            md5_hash = hashlib.md5()
            with open(target_file, "rb") as f:
                while True:
                    block = f.read(CHUNK_SIZE)
                    if not block:
                        break
                    md5_hash.update(block)
            actual_md5 = md5_hash.hexdigest()

            # Verify MD5
            if expected_md5 and actual_md5 != expected_md5:
                logger.error("MD5 mismatch for %s: expected %s, got %s",
                             image_name, expected_md5, actual_md5)
                return {
                    "success": False,
                    "error": f"MD5 mismatch: expected {expected_md5}, got {actual_md5}",
                    "duration": duration,
                }

            # Backup existing image before overwriting
            target_dir.mkdir(parents=True, exist_ok=True)
            final_path = target_dir / image_name
            if final_path.is_file():
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
                backup_dir = target_dir / "backup" / timestamp
                backup_dir.mkdir(parents=True, exist_ok=True)
                for existing in target_dir.iterdir():
                    if existing.is_file():
                        shutil.copy2(str(existing), str(backup_dir / existing.name))
                logger.info("Backed up existing image to %s", backup_dir)

            # Move new image into place
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
        """Delete an image and its directory."""
        image_name = self._validate_image_name(image_name)
        base = image_name.rsplit(".", 1)[0] if "." in image_name else image_name
        target_dir = self.images_dir / base
        if target_dir.is_dir():
            shutil.rmtree(str(target_dir))
            return True
        return False


# =============================================================================
# Image Serving (server-side: serve images TO caching servers)
# =============================================================================


IMAGE_EXTS = {".qcow2", ".qdiff", ".cloop"}
INCOMING_DIR_NAME = ".incoming"


def validate_image_path(name: str) -> None:
    """Validate an image or filename for path safety.

    Raises ValueError if unsafe.
    """
    if not name or not isinstance(name, str):
        raise ValueError("Name must not be empty")
    if "/" in name or "\\" in name or ".." in name or "\0" in name:
        raise ValueError(f"Unsafe path component: {name}")


def resolve_image_file(images_dir: Path, image_name: str, filename: str) -> Path:
    """Resolve and validate an image file path.

    Returns the absolute Path if valid and file exists.
    Raises ValueError for invalid paths, FileNotFoundError if missing.
    """
    validate_image_path(image_name)
    validate_image_path(filename)

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
    validate_image_path(image_name)
    validate_image_path(filename)

    staging_dir = images_dir / INCOMING_DIR_NAME / image_name
    staging_dir.mkdir(parents=True, exist_ok=True)
    file_path = staging_dir / filename

    if offset is not None and offset > 0 and file_path.exists():
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
    validate_image_path(image_name)
    validate_image_path(filename)

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
    validate_image_path(image_name)

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
    validate_image_path(image_name)

    staging_dir = images_dir / INCOMING_DIR_NAME / image_name
    if staging_dir.is_dir():
        shutil.rmtree(str(staging_dir))
        return {"cleaned": True}
    return {"cleaned": False, "detail": "No staging directory found"}


# =============================================================================
# Filesystem scanning
# =============================================================================


def parse_info_file(info_path) -> dict:
    """Parse a .info sidecar file into a dict of key=value pairs."""
    result = {}
    try:
        p = Path(info_path) if not isinstance(info_path, Path) else info_path
        for line in p.read_text(encoding="utf-8").splitlines():
            match = re.match(r'^(\w+)="(.*)"', line)
            if match:
                result[match.group(1)] = match.group(2)
    except OSError:
        pass
    return result


def scan_images(images_dir: str | None = None) -> list[dict]:
    """Scan images directory for QCOW2/QDIFF/CLOOP images with metadata.

    Args:
        images_dir: Override images directory (default: /srv/linbo/images)

    Returns:
        List of image dicts with name, size, md5, info, sidecars, files, updatedAt.
        Skips backup directories and hidden directories.
    """
    images_path = Path(images_dir) if images_dir else IMAGES_DIR
    images = []
    if not images_path.is_dir():
        return images

    for subdir in sorted(images_path.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("."):
            continue

        for img_file in sorted(subdir.iterdir()):
            if img_file.suffix not in IMAGE_EXTS:
                continue
            if "backup" in str(img_file.relative_to(images_path)):
                continue

            stat = img_file.stat()
            name = img_file.name
            base = subdir.name
            rel_path = f"images/{base}/{name}"

            # Read .md5 sidecar
            md5 = None
            md5_path = img_file.with_suffix(img_file.suffix + ".md5")
            try:
                md5 = md5_path.read_text().strip().split()[0]
            except OSError:
                pass

            # Read .info sidecar
            info = parse_info_file(img_file.with_suffix(img_file.suffix + ".info"))

            # Read .desc sidecar
            desc = None
            desc_path = img_file.with_suffix(img_file.suffix + ".desc")
            try:
                desc = desc_path.read_text(encoding="utf-8").strip()
            except OSError:
                pass

            # List available sidecars
            sidecars = []
            for sc in [".md5", ".info", ".desc", ".torrent", ".macct", ".reg",
                        ".prestart", ".postsync"]:
                for candidate in [img_file.with_suffix(img_file.suffix + sc),
                                   subdir / f"{base}{sc}"]:
                    if candidate.is_file():
                        sidecars.append(sc.lstrip("."))
                        break

            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

            # Build files list
            files = [{"name": name, "size": stat.st_size, "type": "image"}]
            for sc in sidecars:
                sc_ext = f".{sc}"
                for candidate in [img_file.with_suffix(img_file.suffix + sc_ext),
                                   subdir / f"{base}{sc_ext}"]:
                    if candidate.is_file():
                        sc_stat = candidate.stat()
                        files.append({
                            "name": candidate.name,
                            "size": sc_stat.st_size,
                            "type": "sidecar",
                        })
                        break

            images.append({
                "name": name,
                "filename": name,
                "base": base,
                "path": rel_path,
                "size": stat.st_size,
                "md5": md5,
                "info": info if info else None,
                "description": desc,
                "sidecars": sidecars,
                "files": files,
                "updatedAt": mtime.isoformat(),
            })

    return images
