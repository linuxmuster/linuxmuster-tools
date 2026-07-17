from pathlib import Path

import pytest

import linuxmusterTools.linbo.images as images_module
from linuxmusterTools.linbo.driver_hooks import (
    DriverHookOwnershipError,
    DriverImageAssignedError,
)
from linuxmusterTools.linbo.drivers import LinboDriverManager


def make_image(
    images_root: Path,
    name: str,
    *,
    timestamp: str = "202607170900",
    payload: bytes = b"image",
    directory: Path | None = None,
) -> Path:
    target = directory or images_root / name
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{name}.qcow2").write_bytes(payload)
    (target / f"{name}.qcow2.info").write_text(
        f'timestamp="{timestamp}"\n'
        f'image="{name}.qcow2"\n'
        f'imagesize="{len(payload)}"\n'
        'partition="/dev/sda1"\n'
        'partitionsize="1"\n',
        encoding="utf-8",
    )
    (target / f"{name}.qcow2.desc").write_text("fixture\n", encoding="utf-8")
    return target


@pytest.fixture
def image_environment(tmp_path, monkeypatch):
    images_root = tmp_path / "images"
    drivers_root = tmp_path / "drivers"
    images_root.mkdir()
    make_image(images_root, "win11")
    monkeypatch.setattr(images_module, "LINBO_PATH", str(images_root))
    monkeypatch.setattr(
        images_module.LinboImage,
        "_torrent_stop",
        lambda _self: None,
    )

    drivers = LinboDriverManager(
        drivers_root,
        images_base=images_root,
        devices_csv=None,
    )
    drivers.create_profile("ModelA", "Fixture Systems", ["Model A"])
    images = images_module.LinboImageManager(
        driver_hook_manager=drivers.hook_manager,
    )
    return drivers, images, images_root


def test_assigned_image_cannot_be_renamed_or_deleted(image_environment):
    drivers, images, images_root = image_environment
    drivers.set_profile_image("ModelA", "win11")

    for operation in (
        lambda: images.rename("win11", "renamed"),
        lambda: images.delete("win11"),
    ):
        with pytest.raises(DriverImageAssignedError) as error:
            operation()
        assert error.value.image == "win11"
        assert error.value.profiles == ("ModelA",)

    assert (images_root / "win11/win11.qcow2").is_file()
    assert not (images_root / "renamed").exists()


@pytest.mark.parametrize("operation", ["rename", "duplicate"])
@pytest.mark.parametrize("new_name", [".", "bad name", "../escape"])
def test_invalid_target_name_does_not_mutate_image(
    image_environment,
    operation,
    new_name,
):
    drivers, images, images_root = image_environment
    drivers.set_profile_image("ModelA", "win11")
    drivers.remove_profile_image("ModelA")
    hook = images_root / "win11/win11.driverpostsync"
    original_hook = hook.read_bytes()
    original_files = sorted(path.name for path in hook.parent.iterdir())

    with pytest.raises(ValueError):
        getattr(images, operation)("win11", new_name)

    assert hook.read_bytes() == original_hook
    assert sorted(path.name for path in hook.parent.iterdir()) == original_files
    assert not (images_root.parent / "escape").exists()


@pytest.mark.parametrize("operation", ["rename", "duplicate"])
def test_existing_target_does_not_mutate_source(image_environment, operation):
    drivers, images, images_root = image_environment
    drivers.set_profile_image("ModelA", "win11")
    drivers.remove_profile_image("ModelA")
    hook = images_root / "win11/win11.driverpostsync"
    original_hook = hook.read_bytes()
    original_files = sorted(path.name for path in hook.parent.iterdir())
    occupied = images_root / "occupied"
    occupied.mkdir()
    (occupied / "marker").write_text("keep\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        getattr(images, operation)("win11", "occupied")

    assert hook.read_bytes() == original_hook
    assert sorted(path.name for path in hook.parent.iterdir()) == original_files
    assert (occupied / "marker").read_text(encoding="utf-8") == "keep\n"


def test_rename_removes_unassigned_managed_tombstone(image_environment):
    drivers, images, images_root = image_environment
    drivers.set_profile_image("ModelA", "win11")
    drivers.remove_profile_image("ModelA")
    assert (images_root / "win11/win11.driverpostsync").is_file()

    images.rename("win11", "renamed")

    assert not (images_root / "win11").exists()
    assert (images_root / "renamed/renamed.qcow2").is_file()
    renamed_hook = images_root / "renamed/renamed.driverpostsync"
    assert "No driver profiles assigned" in renamed_hook.read_text(encoding="utf-8")


def test_failed_rename_restores_managed_tombstone(
    image_environment,
    monkeypatch,
):
    drivers, images, images_root = image_environment
    drivers.set_profile_image("ModelA", "win11")
    drivers.remove_profile_image("ModelA")
    hook = images_root / "win11/win11.driverpostsync"
    original = hook.read_bytes()

    def fail_rename(_self, _new_name):
        raise RuntimeError("fixture rename failure")

    monkeypatch.setattr(images_module.LinboImageGroup, "rename", fail_rename)

    with pytest.raises(RuntimeError, match="fixture rename failure"):
        images.rename("win11", "renamed")

    assert hook.read_bytes() == original
    assert hook.stat().st_mode & 0o777 == 0o755


def test_duplicate_does_not_copy_driverpostsync(image_environment):
    drivers, images, images_root = image_environment
    drivers.set_profile_image("ModelA", "win11")

    images.duplicate("win11", "win11-copy")

    assert (images_root / "win11/win11.driverpostsync").is_file()
    assert (images_root / "win11-copy/win11-copy.qcow2").is_file()
    copied_hook = images_root / "win11-copy/win11-copy.driverpostsync"
    assert "No driver profiles assigned" in copied_hook.read_text(encoding="utf-8")
    assert copied_hook.read_bytes() != (
        images_root / "win11/win11.driverpostsync"
    ).read_bytes()
    assert drivers.get_profile_image("ModelA") == "win11"


def test_restore_keeps_current_hook_and_discards_backup_hook(image_environment):
    drivers, _images, images_root = image_environment
    backup = images_root / "win11/backups/202607170800"
    make_image(
        images_root,
        "win11",
        timestamp="202607170800",
        payload=b"old image",
        directory=backup,
    )
    drivers.set_profile_image("ModelA", "win11")
    hook = images_root / "win11/win11.driverpostsync"
    current_hook = hook.read_bytes()
    (backup / "win11.driverpostsync").write_bytes(current_hook)
    images = images_module.LinboImageManager(
        driver_hook_manager=drivers.hook_manager,
    )

    images.restore("win11", "17/07/2026 08:00")

    assert hook.read_bytes() == current_hook
    assert (images_root / "win11/win11.qcow2").read_bytes() == b"old image"
    assert not backup.exists()


def test_delete_backup_removes_managed_hook(image_environment):
    drivers, _images, images_root = image_environment
    backup = images_root / "win11/backups/202607170800"
    make_image(
        images_root,
        "win11",
        timestamp="202607170800",
        payload=b"old image",
        directory=backup,
    )
    drivers.set_profile_image("ModelA", "win11")
    (backup / "win11.driverpostsync").write_bytes(
        (images_root / "win11/win11.driverpostsync").read_bytes()
    )
    images = images_module.LinboImageManager(
        driver_hook_manager=drivers.hook_manager,
    )

    images.delete("win11", date="17/07/2026 08:00")

    assert not backup.exists()
    assert (images_root / "win11/win11.driverpostsync").is_file()


def test_nested_foreign_backup_hook_blocks_delete(image_environment):
    drivers, _images, images_root = image_environment
    backup = images_root / "win11/backups/202607170800"
    make_image(
        images_root,
        "win11",
        timestamp="202607170800",
        payload=b"old image",
        directory=backup,
    )
    foreign = backup / "nested/custom.driverpostsync"
    foreign.parent.mkdir()
    foreign.write_text("#!/bin/sh\necho custom backup hook\n", encoding="utf-8")
    images = images_module.LinboImageManager(
        driver_hook_manager=drivers.hook_manager,
    )

    with pytest.raises(DriverHookOwnershipError):
        images.delete("win11", date="17/07/2026 08:00")

    assert foreign.is_file()
    assert (backup / "win11.qcow2").read_bytes() == b"old image"


@pytest.mark.parametrize("operation", ["delete", "restore"])
def test_symlinked_backup_directory_cannot_touch_external_files(
    image_environment,
    operation,
):
    drivers, _images, images_root = image_environment
    external = images_root.parent / "external-backup"
    make_image(
        images_root,
        "win11",
        timestamp="202607170800",
        payload=b"external image",
        directory=external,
    )
    drivers.set_profile_image("ModelA", "win11")
    external_hook = external / "win11.driverpostsync"
    external_hook.write_bytes(
        (images_root / "win11/win11.driverpostsync").read_bytes()
    )
    original_hook = external_hook.read_bytes()
    backups = images_root / "win11/backups"
    backups.mkdir()
    (backups / "202607170800").symlink_to(external, target_is_directory=True)
    images = images_module.LinboImageManager(
        driver_hook_manager=drivers.hook_manager,
    )

    with pytest.raises(DriverHookOwnershipError, match="symlink or non-directory"):
        if operation == "delete":
            images.delete("win11", date="17/07/2026 08:00")
        else:
            images.restore("win11", "17/07/2026 08:00")

    assert external_hook.read_bytes() == original_hook
    assert (external / "win11.qcow2").read_bytes() == b"external image"


def test_foreign_backup_hook_blocks_restore(image_environment):
    drivers, _images, images_root = image_environment
    backup = images_root / "win11/backups/202607170800"
    make_image(
        images_root,
        "win11",
        timestamp="202607170800",
        payload=b"old image",
        directory=backup,
    )
    foreign = backup / "win11.driverpostsync"
    foreign.write_text("#!/bin/sh\necho custom backup hook\n", encoding="utf-8")
    images = images_module.LinboImageManager(
        driver_hook_manager=drivers.hook_manager,
    )

    with pytest.raises(DriverHookOwnershipError):
        images.restore("win11", "17/07/2026 08:00")

    assert (images_root / "win11/win11.qcow2").read_bytes() == b"image"
    assert foreign.is_file()


def test_restore_collision_keeps_managed_backup_hook(
    image_environment,
    monkeypatch,
):
    drivers, _images, images_root = image_environment
    backup = images_root / "win11/backups/202607170800"
    make_image(
        images_root,
        "win11",
        timestamp="202607170800",
        payload=b"old image",
        directory=backup,
    )
    drivers.set_profile_image("ModelA", "win11")
    managed_hook = backup / "win11.driverpostsync"
    managed_hook.write_bytes(
        (images_root / "win11/win11.driverpostsync").read_bytes()
    )
    images = images_module.LinboImageManager(
        driver_hook_manager=drivers.hook_manager,
    )
    fixed_now = images_module.datetime(2026, 7, 17, 10, 30)

    class FixedDatetime:
        @classmethod
        def now(cls):
            return fixed_now

    monkeypatch.setattr(images_module, "datetime", FixedDatetime)
    (images_root / "win11/backups/202607171030").mkdir()

    images.restore("win11", "17/07/2026 08:00")

    assert managed_hook.is_file()
    assert (backup / "win11.qcow2").read_bytes() == b"old image"


def test_foreign_driverpostsync_blocks_rename(image_environment):
    _drivers, images, images_root = image_environment
    foreign = images_root / "win11/win11.driverpostsync"
    foreign.write_text("#!/bin/sh\necho custom hook\n", encoding="utf-8")

    with pytest.raises(DriverHookOwnershipError):
        images.rename("win11", "renamed")

    assert foreign.is_file()
    assert (images_root / "win11/win11.qcow2").is_file()
    assert not (images_root / "renamed").exists()


def test_symlinked_image_subdirectory_blocks_rename(image_environment):
    _drivers, images, images_root = image_environment
    outside = images_root / "outside"
    outside.mkdir()
    (images_root / "win11/linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(DriverHookOwnershipError, match="symlinked directory"):
        images.rename("win11", "renamed")

    assert (images_root / "win11/linked").is_symlink()
    assert (images_root / "win11/win11.qcow2").is_file()
    assert not (images_root / "renamed").exists()
