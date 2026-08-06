from datetime import datetime

import pytest

import linuxmusterTools.linbo.images as images_module
from linuxmusterTools.linbo.drivers import LinboDriverManager
from linuxmusterTools.linbo.images import (
    ImageExistsError,
    LinboImageManager,
    TIMESTAMP_FMT,
    timestamp2date,
)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    images_root = tmp_path / "images"
    images_root.mkdir()
    drivers = LinboDriverManager(tmp_path / "drivers")
    monkeypatch.setattr(images_module, "LINBO_PATH", str(images_root))
    return images_root, LinboImageManager(driver_manager=drivers)


def _write_info(image_dir, filename, **fields):
    """Write a .info file with exactly the given key/value pairs."""

    content = "".join(f"{key}={value}\n" for key, value in fields.items())
    (image_dir / f"{filename}.info").write_text(content)


def _create_broken_image(images_root, name):
    """A base image with no .info file at all."""

    image_dir = images_root / name
    image_dir.mkdir()
    (image_dir / f"{name}.qcow2").touch()
    return image_dir


def _create_image(images_root, name, timestamp="202601010000"):
    """A complete, valid base image: .qcow2 plus a fully populated .info."""

    image_dir = _create_broken_image(images_root, name)
    _write_info(
        image_dir,
        f"{name}.qcow2",
        timestamp=timestamp,
        image=f"{name}.qcow2",
        imagesize="10",
        partition="/dev/sda1",
        partitionsize="20",
    )
    return image_dir


def _create_backup(image_dir, name, backup_timestamp):
    """A backup as restore()/the upload flow actually leaves one on disk.

    LinboImage(backup=True) never reads this .info (it gets its timestamp
    from the directory name instead), but restore() moves it wholesale along
    with the .qcow2 when swapping a backup back in as the base image — which
    then does need a complete .info to be loaded again.
    """

    backup_dir = image_dir / "backups" / backup_timestamp
    backup_dir.mkdir(parents=True)
    (backup_dir / f"{name}.qcow2").write_bytes(b"y" * 5)
    _write_info(
        backup_dir,
        f"{name}.qcow2",
        timestamp=backup_timestamp,
        image=f"{name}.qcow2",
        imagesize="5",
        partition="/dev/sda1",
        partitionsize="20",
    )
    return backup_dir


# ── parse_info_file / IncompleteImageInfoError ──────────────────────


def test_missing_info_file_reports_all_fields_missing(environment):
    images_root, images = environment
    _create_broken_image(images_root, "broken")

    images.list()

    group = images.groups["broken"]
    assert group.base is None
    assert "missing timestamp, image, imagesize, partition, partitionsize" in group.error


def test_legacy_info_file_reports_only_the_actually_missing_fields(environment):
    images_root, images = environment
    image_dir = _create_broken_image(images_root, "legacy")
    # Older format: "baseimage" instead of "partition", no timestamp.
    _write_info(
        image_dir,
        "legacy.qcow2",
        image="legacy.qcow2",
        baseimage="/dev/sda1",
        partitionsize="20",
        imagesize="10",
    )

    images.list()

    group = images.groups["legacy"]
    assert group.base is None
    assert "missing timestamp, partition" in group.error


def test_complete_info_file_parses_without_error(environment):
    images_root, images = environment
    _create_image(images_root, "ubuntu")

    images.list()

    group = images.groups["ubuntu"]
    assert group.base is not None
    assert group.error is None
    assert group.base.info_file.partition == "/dev/sda1"


# ── Isolation: one broken image must not break the whole listing ───


def test_broken_image_does_not_crash_manager_list(environment):
    images_root, images = environment
    _create_image(images_root, "good")
    _create_broken_image(images_root, "broken")

    images.list()

    assert set(images.groups) == {"good", "broken"}
    assert images.groups["good"].base is not None
    assert images.groups["broken"].base is None


def test_broken_image_group_to_dict_reports_error_without_crashing(environment):
    images_root, images = environment
    _create_broken_image(images_root, "broken")
    images.list()

    result = images.groups["broken"].to_dict()

    assert result["name"] == "broken"
    assert "missing" in result["error"]
    assert result["selected"] is False


def test_healthy_image_to_dict_is_unaffected_by_a_broken_sibling(environment):
    images_root, images = environment
    _create_image(images_root, "good")
    _create_broken_image(images_root, "broken")
    images.list()

    result = images.groups["good"].to_dict()

    assert result["name"] == "good"
    assert "error" not in result


# ── Refusing to mutate a broken group ───────────────────────────────


def test_rename_refuses_on_broken_group(environment):
    images_root, images = environment
    _create_broken_image(images_root, "broken")
    images.list()

    with pytest.raises(RuntimeError, match="Cannot rename image group broken"):
        images.groups["broken"].rename("renamed")

    # Nothing touched: the original directory is still there under its name.
    assert (images_root / "broken").is_dir()
    assert not (images_root / "renamed").exists()


def test_delete_refuses_on_broken_group(environment):
    images_root, images = environment
    _create_broken_image(images_root, "broken")
    images.list()

    with pytest.raises(RuntimeError, match="Cannot delete image group broken"):
        images.groups["broken"].delete()

    assert (images_root / "broken").is_dir()


def test_save_extras_refuses_on_broken_group(environment):
    images_root, images = environment
    _create_broken_image(images_root, "broken")
    images.list()

    with pytest.raises(RuntimeError, match="Cannot save extras for image group broken"):
        images.save_extras("broken", {"desc": "test"})


def test_save_extras_refuses_when_no_diff_image_exists(environment):
    images_root, images = environment
    _create_image(images_root, "ubuntu")
    images.list()
    assert images.groups["ubuntu"].diff_image is None

    with pytest.raises(RuntimeError, match="Image group ubuntu has no differential image"):
        images.save_extras("ubuntu", {"desc": "test"}, diff=True)


# ── LinboImage.delete() / LinboImageGroup.delete() propagate OSError ─


def test_base_image_delete_propagates_oserror_on_nonempty_directory(environment):
    images_root, images = environment
    image_dir = _create_image(images_root, "ubuntu")
    # A file delete_files() does not know about: os.rmdir() must then fail.
    (image_dir / "stray.txt").write_text("leftover")
    images.list()

    with pytest.raises(OSError):
        images.groups["ubuntu"].base.delete()

    assert image_dir.exists()


def test_group_delete_propagates_oserror_when_backups_dir_not_empty(environment):
    images_root, images = environment
    image_dir = _create_image(images_root, "ubuntu")
    (image_dir / "backups").mkdir()
    # A stray file directly under backups/, not inside any timestamp dir: no
    # LinboImage will ever unlink it, so the final os.rmdir() must fail.
    (image_dir / "backups" / "stray.txt").write_text("leftover")
    images.list()

    with pytest.raises(OSError):
        images.groups["ubuntu"].delete()


# ── Manager.delete() — the self.images/self.groups regression ──────


def test_delete_specific_backup_by_date(environment):
    images_root, images = environment
    image_dir = _create_image(images_root, "ubuntu")
    backup_ts = "202512241000"
    _create_backup(image_dir, "ubuntu", backup_ts)
    images.list()
    date_key = timestamp2date(backup_ts)
    assert date_key in images.groups["ubuntu"].backups

    # This is exactly the path that used to raise AttributeError on the
    # undefined self.images.
    images.delete("ubuntu", date=date_key)

    assert date_key not in images.groups["ubuntu"].backups
    assert not (image_dir / "backups" / backup_ts).exists()
    # The base image itself must be untouched.
    assert (image_dir / "ubuntu.qcow2").exists()


def test_delete_whole_group(environment):
    images_root, images = environment
    image_dir = _create_image(images_root, "ubuntu")
    images.list()

    images.delete("ubuntu")

    assert "ubuntu" not in images.groups
    assert not image_dir.exists()


def test_delete_diff_image(environment):
    images_root, images = environment
    image_dir = _create_image(images_root, "ubuntu")
    (image_dir / "ubuntu.qdiff").write_bytes(b"z" * 5)
    _write_info(
        image_dir,
        "ubuntu.qdiff",
        timestamp="202601020000",
        image="ubuntu.qdiff",
        imagesize="5",
        partition="/dev/sda1",
        partitionsize="20",
    )
    images.list()
    assert images.groups["ubuntu"].diff_image is not None

    images.delete("ubuntu", diff=True)

    assert not (image_dir / "ubuntu.qdiff").exists()


# ── Manager.duplicate() ──────────────────────────────────────────────


def test_duplicate_creates_an_independent_copy(environment):
    images_root, images = environment
    _create_image(images_root, "ubuntu")
    images.list()

    images.duplicate("ubuntu", "ubuntu-copy")

    assert "ubuntu-copy" in images.groups
    assert (images_root / "ubuntu-copy" / "ubuntu-copy.qcow2").exists()
    # Original left untouched.
    assert (images_root / "ubuntu" / "ubuntu.qcow2").exists()


def test_duplicate_rejects_an_existing_target(environment):
    images_root, images = environment
    _create_image(images_root, "ubuntu")
    _create_image(images_root, "existing")
    images.list()

    with pytest.raises(ImageExistsError):
        images.duplicate("ubuntu", "existing")

    # Refused before touching anything: the target is exactly as it was.
    assert (images_root / "existing" / "existing.qcow2").exists()
    assert not (images_root / "existing" / "ubuntu.qcow2").exists()


# ── Manager.restore() ────────────────────────────────────────────────


def test_restore_swaps_base_and_backup(environment):
    images_root, images = environment
    image_dir = _create_image(images_root, "ubuntu", timestamp="202601010000")
    backup_ts = "202512240000"
    _create_backup(image_dir, "ubuntu", backup_ts)
    images.list()
    date_key = timestamp2date(backup_ts)

    images.restore("ubuntu", date_key)

    group = images.groups["ubuntu"]
    # The former backup is now the base image.
    assert group.base.timestamp == backup_ts
    # The former base image now lives under backups/ at today's timestamp.
    assert date_key not in group.backups
    assert len(group.backups) == 1


def test_restore_rejects_a_same_minute_collision(environment):
    images_root, images = environment
    image_dir = _create_image(images_root, "ubuntu")
    backup_ts = "202512240000"
    _create_backup(image_dir, "ubuntu", backup_ts)
    images.list()
    date_key = timestamp2date(backup_ts)

    # Pre-create the exact directory restore() is about to mkdir: the backup
    # timestamp it generates has minute resolution (TIMESTAMP_FMT), so this
    # collision is deterministic within the same test run.
    collision_ts = datetime.now().strftime(TIMESTAMP_FMT)
    (image_dir / "backups" / collision_ts).mkdir()

    with pytest.raises(ImageExistsError):
        images.restore("ubuntu", date_key)

    # Refused before moving anything: original backup is still a backup.
    assert date_key in images.groups["ubuntu"].backups
