"""
Tests for the permissions of the files the image serving helpers write.

The .macct file of an image holds the Samba machine account secrets of the
client it was taken from, and the [linbo] rsync module serves the whole
LINBO directory without login as nobody. Every .macct the helpers stage,
move into place or back up has to be 0600, the staging directory closed
while an upload waits there, and the other image files left as they are.
"""

import errno
import os
import stat

import pytest

import linuxmusterTools.linbo.image_sync as image_sync_module
from linuxmusterTools.linbo.image_sync import (
    finalize_upload,
    receive_upload_chunk,
)


IMAGE = "ubuntu22"
MACCT = "ubuntu22.qcow2.macct"
QCOW2 = "ubuntu22.qcow2"


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture(autouse=True)
def usual_umask():
    """The umask a service usually runs with, which leaves files 0644."""

    previous = os.umask(0o022)
    yield
    os.umask(previous)


@pytest.fixture
def staging_dir(tmp_path):
    return tmp_path / ".incoming" / IMAGE


def test_first_chunk_creates_the_macct_owner_only(tmp_path, staging_dir):
    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"unicodePwd:: secret")
    assert mode(staging_dir / MACCT) == 0o600


def test_first_chunk_creates_the_macct_without_a_later_chmod(tmp_path, staging_dir, monkeypatch):
    # Without chmod the file keeps the mode it was created with: 0600 here
    # means it never existed readable by others, not even for a moment.
    monkeypatch.setattr(image_sync_module.os, "chmod", lambda *args, **kwargs: None)
    monkeypatch.setattr(image_sync_module.os, "fchmod", lambda *args, **kwargs: None)
    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"unicodePwd:: secret")
    assert mode(staging_dir / MACCT) == 0o600


def test_resumed_chunk_closes_a_macct_staged_readable(tmp_path, staging_dir):
    staging_dir.mkdir(parents=True)
    staged = staging_dir / MACCT
    staged.write_bytes(b"unicodePwd:: ")
    staged.chmod(0o644)

    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"secret", offset=len(b"unicodePwd:: "))

    assert staged.read_bytes() == b"unicodePwd:: secret"
    assert mode(staged) == 0o600


def test_first_chunk_replaces_a_macct_staged_readable(tmp_path, staging_dir):
    staging_dir.mkdir(parents=True)
    staged = staging_dir / MACCT
    staged.write_bytes(b"old")
    staged.chmod(0o644)

    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"new")

    assert staged.read_bytes() == b"new"
    assert mode(staged) == 0o600


def test_image_chunk_keeps_the_usual_mode(tmp_path, staging_dir):
    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"qcow2")
    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"-more", offset=5)
    assert (staging_dir / QCOW2).read_bytes() == b"qcow2-more"
    assert mode(staging_dir / QCOW2) == 0o644


def test_staging_directories_are_closed(tmp_path, staging_dir):
    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"qcow2")
    assert mode(tmp_path / ".incoming") == 0o700
    assert mode(staging_dir) == 0o700


def test_staging_directories_created_open_are_closed_again(tmp_path, staging_dir):
    staging_dir.mkdir(parents=True)
    (tmp_path / ".incoming").chmod(0o755)
    staging_dir.chmod(0o755)

    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"qcow2")

    assert mode(tmp_path / ".incoming") == 0o700
    assert mode(staging_dir) == 0o700


def test_finalize_moves_the_macct_owner_only(tmp_path):
    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"qcow2")
    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"secret")

    finalize_upload(tmp_path, IMAGE)

    assert (tmp_path / IMAGE / MACCT).read_bytes() == b"secret"
    assert mode(tmp_path / IMAGE / MACCT) == 0o600
    assert mode(tmp_path / IMAGE / QCOW2) == 0o644


def test_finalize_closes_a_macct_staged_readable(tmp_path, staging_dir):
    staging_dir.mkdir(parents=True)
    (staging_dir / MACCT).write_bytes(b"secret")
    (staging_dir / MACCT).chmod(0o644)

    finalize_upload(tmp_path, IMAGE)

    assert mode(tmp_path / IMAGE / MACCT) == 0o600


def test_finalize_closes_a_staged_macct_before_moving_it(tmp_path, staging_dir, monkeypatch):
    staging_dir.mkdir(parents=True)
    (staging_dir / MACCT).write_bytes(b"secret")
    (staging_dir / MACCT).chmod(0o644)
    moved_modes = {}
    move = image_sync_module.shutil.move

    def recording_move(src, dst, **kwargs):
        moved_modes[os.path.basename(src)] = stat.S_IMODE(os.stat(src).st_mode)
        return move(src, dst, **kwargs)

    monkeypatch.setattr(image_sync_module.shutil, "move", recording_move)

    finalize_upload(tmp_path, IMAGE)

    assert moved_modes == {MACCT: 0o600}


def test_finalize_moves_the_macct_across_filesystems_owner_only(tmp_path, monkeypatch):
    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"qcow2")
    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"secret")

    # rename() fails like it does across filesystems, so shutil.move()
    # copies. Without chmod the copy keeps the mode it was created with.
    def rename(src, dst):
        raise OSError(errno.EXDEV, os.strerror(errno.EXDEV))

    monkeypatch.setattr(image_sync_module.os, "rename", rename)
    monkeypatch.setattr(image_sync_module.os, "chmod", lambda *args, **kwargs: None)
    monkeypatch.setattr(image_sync_module.os, "fchmod", lambda *args, **kwargs: None)

    finalize_upload(tmp_path, IMAGE)

    assert (tmp_path / IMAGE / MACCT).read_bytes() == b"secret"
    assert mode(tmp_path / IMAGE / MACCT) == 0o600
    assert not (tmp_path / ".incoming" / IMAGE / MACCT).exists()
    assert (tmp_path / IMAGE / QCOW2).read_bytes() == b"qcow2"


def test_finalize_backs_up_the_macct_owner_only(tmp_path):
    target_dir = tmp_path / IMAGE
    target_dir.mkdir()
    (target_dir / QCOW2).write_bytes(b"old qcow2")
    (target_dir / MACCT).write_bytes(b"old secret")
    (target_dir / MACCT).chmod(0o644)
    os.utime(target_dir / MACCT, (1_000_000_000, 1_000_000_000))
    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"new qcow2")
    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"new secret")

    result = finalize_upload(tmp_path, IMAGE)

    backup_dir = tmp_path / result["backup"]
    assert (backup_dir / MACCT).read_bytes() == b"old secret"
    assert mode(backup_dir / MACCT) == 0o600
    assert (backup_dir / MACCT).stat().st_mtime == 1_000_000_000
    assert mode(backup_dir / QCOW2) == 0o644
    assert mode(target_dir / MACCT) == 0o600


def test_finalize_closes_a_macct_the_upload_left_in_place(tmp_path):
    target_dir = tmp_path / IMAGE
    target_dir.mkdir()
    (target_dir / MACCT).write_bytes(b"secret")
    (target_dir / MACCT).chmod(0o644)
    receive_upload_chunk(tmp_path, IMAGE, QCOW2, b"qcow2")

    finalize_upload(tmp_path, IMAGE)

    assert mode(target_dir / MACCT) == 0o600


def test_macct_and_staging_become_root_owned_when_running_as_root(tmp_path, monkeypatch):
    owned = []

    def chown(path, uid, gid):
        owned.append((os.path.relpath(path, tmp_path), uid, gid))

    def fchown(fd, uid, gid):
        chown(os.readlink(f"/proc/self/fd/{fd}"), uid, gid)

    monkeypatch.setattr(image_sync_module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(image_sync_module.os, "chown", chown)
    monkeypatch.setattr(image_sync_module.os, "fchown", fchown)

    target_dir = tmp_path / IMAGE
    target_dir.mkdir()
    (target_dir / QCOW2).write_bytes(b"old qcow2")
    (target_dir / MACCT).write_bytes(b"old secret")
    receive_upload_chunk(tmp_path, IMAGE, MACCT, b"new secret")

    assert set(owned) == {
        (".incoming", 0, 0),
        (f".incoming/{IMAGE}", 0, 0),
        (f".incoming/{IMAGE}/{MACCT}", 0, 0),
    }

    owned.clear()
    result = finalize_upload(tmp_path, IMAGE)
    backup = os.path.relpath(result["backup"], tmp_path)

    assert set(owned) == {
        (f".incoming/{IMAGE}/{MACCT}", 0, 0),
        (f"{backup}/{MACCT}", 0, 0),
        (f"{IMAGE}/{MACCT}", 0, 0),
    }
