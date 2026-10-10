"""
Tests for the modes of the files an image upload leaves behind.

A .macct holds the Samba secrets of a client, and the [linbo] rsync module
serves the LINBO directory without login: it has to stay 0600, in the image
directory and in its backups, and the staging directory 0700.
"""

import stat

from linuxmusterTools.linbo.image_sync import finalize_upload, receive_upload_chunk


IMAGE = "ubuntu"


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def stage(images_dir):
    for filename in (f"{IMAGE}.qcow2", f"{IMAGE}.qcow2.macct"):
        receive_upload_chunk(images_dir, IMAGE, filename, b"data")


def test_staging_dir_is_closed(tmp_path):
    stage(tmp_path)
    assert mode(tmp_path / ".incoming") == 0o700
    assert mode(tmp_path / ".incoming" / IMAGE) == 0o700


def test_finalized_macct_is_owner_only(tmp_path):
    stage(tmp_path)
    finalize_upload(tmp_path, IMAGE)
    assert mode(tmp_path / IMAGE / f"{IMAGE}.qcow2.macct") == 0o600


def test_backed_up_macct_is_owner_only(tmp_path):
    target = tmp_path / IMAGE
    target.mkdir()
    (target / f"{IMAGE}.qcow2").write_bytes(b"old")
    old_macct = target / f"{IMAGE}.qcow2.macct"
    old_macct.write_bytes(b"old")
    old_macct.chmod(0o644)

    stage(tmp_path)
    result = finalize_upload(tmp_path, IMAGE)

    backup = tmp_path / IMAGE / "backup"
    (backup_macct,) = backup.glob(f"*/{IMAGE}.qcow2.macct")
    assert result["backup"]
    assert mode(backup_macct) == 0o600


def test_other_files_keep_their_mode(tmp_path):
    stage(tmp_path)
    finalize_upload(tmp_path, IMAGE)
    assert mode(tmp_path / IMAGE / f"{IMAGE}.qcow2") != 0o600
