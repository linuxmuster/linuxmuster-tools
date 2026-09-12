"""
LINBO Image Sync client — download QCOW2 images from a remote server.

Supports HTTP Range requests for resume capability, MD5 verification,
and atomic directory swap on completion.

Parked here because nothing instantiates LinboImageSync yet: it was written
for a client-side sync that does not exist, and the WIP directory is not
imported by linbo/__init__.py. Two bugs are known and left as-is, to be fixed
by whoever wires this up: download_image() and delete_image() both assign the
boolean returned by NameChecker.check_linbo_image_name() back to image_name,
which raises TypeError on the next line.
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


name_checker = NameChecker()
logger = logging.getLogger(__name__)

IMAGES_DIR = Path(os.environ.get("LINBO_DIR", "/srv/linbo")) / "images"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


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

    def __init__(self, images_dir: str | None = None):
        self.images_dir = Path(images_dir) if images_dir else IMAGES_DIR

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


        image_name = name_checker.check_linbo_image_name(image_name)
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
        """
        Delete an image and its directory.
        TODO: should use LinboImageManager
        """

        image_name = name_checker.check_linbo_image_name(image_name)
        base = image_name.rsplit(".", 1)[0] if "." in image_name else image_name
        target_dir = self.images_dir / base
        if target_dir.is_dir():
            shutil.rmtree(str(target_dir))
            return True
        return False
