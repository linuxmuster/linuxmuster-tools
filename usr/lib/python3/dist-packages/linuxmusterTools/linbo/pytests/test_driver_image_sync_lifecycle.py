import io
import threading
from pathlib import Path

import pytest

import linuxmusterTools.linbo.image_sync as image_sync_module
from linuxmusterTools.linbo.driver_hooks import (
    DriverHookOwnershipError,
    DriverImageAssignedError,
)
from linuxmusterTools.linbo.drivers import LinboDriverManager
from linuxmusterTools.linbo.image_sync import (
    LinboImageSync,
    finalize_upload,
    get_upload_status,
    receive_upload_chunk,
    resolve_image_file,
)


def make_image(images_root: Path, name: str, payload: bytes = b"old image") -> Path:
    image_dir = images_root / name
    image_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / f"{name}.qcow2").write_bytes(payload)
    (image_dir / f"{name}.qcow2.desc").write_text(
        "fixture\n",
        encoding="utf-8",
    )
    return image_dir


@pytest.fixture
def sync_environment(tmp_path):
    images_root = tmp_path / "images"
    drivers_root = tmp_path / "drivers"
    images_root.mkdir()
    make_image(images_root, "win11")

    drivers = LinboDriverManager(
        drivers_root,
        images_base=images_root,
    )
    drivers.create_profile("ModelA", "Fixture Systems", ["Model A"])
    sync = LinboImageSync(
        images_dir=str(images_root),
        driver_hook_manager=drivers.hook_manager,
    )
    return drivers, sync, images_root


@pytest.mark.parametrize(
    "operation",
    [
        lambda root: receive_upload_chunk(
            root,
            "win11",
            "win11.driverpostsync",
            b"foreign",
        ),
        lambda root: get_upload_status(
            root,
            "win11",
            "win11.driverpostsync",
        ),
    ],
)
def test_generic_transport_rejects_driverpostsync(operation, tmp_path):
    images_root = tmp_path / "images"
    images_root.mkdir()

    with pytest.raises(ValueError, match="cannot be transferred"):
        operation(images_root)

    assert not (images_root / ".incoming").exists()


def test_authenticated_file_resolution_can_serve_managed_driverpostsync(
    tmp_path,
):
    images_root = tmp_path / "images"
    image = make_image(images_root, "win11")
    hook = image / "win11.driverpostsync"
    hook.write_text("#!/bin/sh\nreturn 0\n", encoding="utf-8")

    assert resolve_image_file(
        images_root,
        "win11",
        "win11.driverpostsync",
    ) == hook


def test_dotted_image_basename_is_not_truncated(tmp_path):
    images_root = tmp_path / "images"
    drivers_root = tmp_path / "drivers"
    make_image(images_root, "win11.24")
    manager = LinboDriverManager(drivers_root, images_base=images_root)
    sync = LinboImageSync(
        images_dir=str(images_root),
        driver_hook_manager=manager.hook_manager,
    )

    assert sync.delete_image("win11.24.qcow2") is True
    assert not (images_root / "win11.24").exists()


def test_download_rejects_driverpostsync_before_network_access(
    sync_environment,
    monkeypatch,
):
    _drivers, sync, images_root = sync_environment

    def unexpected_urlopen(*_args, **_kwargs):
        raise AssertionError("network access must not happen")

    monkeypatch.setattr(image_sync_module, "urlopen", unexpected_urlopen)

    with pytest.raises(ValueError, match="cannot be transferred"):
        sync.download_image("https://invalid.test/hook", "win11.driverpostsync")

    assert not (images_root / ".incoming").exists()


def test_invalid_namechecker_result_is_not_used_as_a_filename(
    sync_environment,
):
    _drivers, sync, images_root = sync_environment

    with pytest.raises(ValueError):
        sync.delete_image("../win11.qcow2")
    with pytest.raises(ValueError):
        receive_upload_chunk(images_root, "../win11", "win11.qcow2", b"x")

    assert (images_root / "win11/win11.qcow2").is_file()


def test_assigned_image_cannot_be_deleted_through_sync(sync_environment):
    drivers, sync, images_root = sync_environment
    drivers.set_profile_image("ModelA", "win11")

    with pytest.raises(DriverImageAssignedError) as error:
        sync.delete_image("win11.qcow2")

    assert error.value.image == "win11"
    assert error.value.profiles == ("ModelA",)
    assert (images_root / "win11/win11.qcow2").read_bytes() == b"old image"
    assert (images_root / "win11/win11.driverpostsync").is_file()


def test_sync_delete_removes_unassigned_managed_tombstone(sync_environment):
    drivers, sync, images_root = sync_environment
    drivers.set_profile_image("ModelA", "win11")
    drivers.remove_profile_image("ModelA")
    assert (images_root / "win11/win11.driverpostsync").is_file()

    assert sync.delete_image("win11.qcow2") is True

    assert not (images_root / "win11").exists()


def test_sync_delete_refuses_foreign_hook(sync_environment):
    _drivers, sync, images_root = sync_environment
    foreign = images_root / "win11/win11.driverpostsync"
    foreign.write_text("#!/bin/sh\necho administrator-owned\n", encoding="utf-8")

    with pytest.raises(DriverHookOwnershipError):
        sync.delete_image("win11.qcow2")

    assert foreign.is_file()
    assert (images_root / "win11/win11.qcow2").read_bytes() == b"old image"


def test_finalize_preserves_managed_hook_and_excludes_it_from_backup(
    sync_environment,
):
    drivers, _sync, images_root = sync_environment
    drivers.set_profile_image("ModelA", "win11")
    hook = images_root / "win11/win11.driverpostsync"
    original_hook = hook.read_bytes()
    receive_upload_chunk(images_root, "win11", "win11.qcow2", b"new image")
    receive_upload_chunk(images_root, "win11", "win11.qcow2.desc", b"new desc\n")

    result = finalize_upload(
        images_root,
        "win11",
        driver_hook_manager=drivers.hook_manager,
    )

    assert result["finalized"] is True
    assert sorted(result["files"]) == ["win11.qcow2", "win11.qcow2.desc"]
    assert (images_root / "win11/win11.qcow2").read_bytes() == b"new image"
    assert hook.read_bytes() == original_hook
    backup = Path(result["backup"])
    assert (backup / "win11.qcow2").read_bytes() == b"old image"
    assert not (backup / "win11.driverpostsync").exists()


def test_finalize_refuses_foreign_hook_before_mutation(sync_environment):
    drivers, _sync, images_root = sync_environment
    foreign = images_root / "win11/win11.driverpostsync"
    foreign_content = b"#!/bin/sh\necho administrator-owned\n"
    foreign.write_bytes(foreign_content)
    receive_upload_chunk(images_root, "win11", "win11.qcow2", b"new image")

    with pytest.raises(DriverHookOwnershipError):
        finalize_upload(
            images_root,
            "win11",
            driver_hook_manager=drivers.hook_manager,
        )

    assert (images_root / "win11/win11.qcow2").read_bytes() == b"old image"
    assert foreign.read_bytes() == foreign_content
    assert (
        images_root / ".incoming/win11/win11.qcow2"
    ).read_bytes() == b"new image"
    assert not (images_root / "win11/backup").exists()


def test_finalize_rejects_manually_staged_hook_before_mutation(sync_environment):
    drivers, _sync, images_root = sync_environment
    staging = images_root / ".incoming/win11"
    staging.mkdir(parents=True)
    (staging / "win11.qcow2").write_bytes(b"new image")
    (staging / "win11.driverpostsync").write_text(
        "#!/bin/sh\necho staged\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not contain"):
        finalize_upload(
            images_root,
            "win11",
            driver_hook_manager=drivers.hook_manager,
        )

    assert (images_root / "win11/win11.qcow2").read_bytes() == b"old image"
    assert (staging / "win11.driverpostsync").is_file()
    assert not (images_root / "win11/backup").exists()


def test_download_preserves_managed_hook_and_excludes_it_from_backup(
    sync_environment,
    monkeypatch,
):
    drivers, sync, images_root = sync_environment
    drivers.set_profile_image("ModelA", "win11")
    hook = images_root / "win11/win11.driverpostsync"
    original_hook = hook.read_bytes()

    class Response(io.BytesIO):
        headers = {"Content-Length": "9"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        image_sync_module,
        "urlopen",
        lambda *_args, **_kwargs: Response(b"new image"),
    )

    result = sync.download_image("https://fixture.test/win11", "win11.qcow2")

    assert result["success"] is True
    assert (images_root / "win11/win11.qcow2").read_bytes() == b"new image"
    assert hook.read_bytes() == original_hook
    backups = list((images_root / "win11/backup").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "win11.qcow2").read_bytes() == b"old image"
    assert not (backups[0] / "win11.driverpostsync").exists()


def test_download_refuses_foreign_hook_before_local_mutation(
    sync_environment,
    monkeypatch,
):
    _drivers, sync, images_root = sync_environment
    foreign = images_root / "win11/win11.driverpostsync"
    foreign_content = b"#!/bin/sh\necho administrator-owned\n"
    foreign.write_bytes(foreign_content)

    class Response(io.BytesIO):
        headers = {"Content-Length": "9"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        image_sync_module,
        "urlopen",
        lambda *_args, **_kwargs: Response(b"new image"),
    )

    with pytest.raises(DriverHookOwnershipError):
        sync.download_image("https://fixture.test/win11", "win11.qcow2")

    assert (images_root / "win11/win11.qcow2").read_bytes() == b"old image"
    assert foreign.read_bytes() == foreign_content
    assert (
        images_root / ".incoming/win11/win11.qcow2"
    ).read_bytes() == b"new image"
    assert not (images_root / "win11/backup").exists()


def test_new_image_becomes_assignable_only_after_sidecars_are_published(
    sync_environment,
    monkeypatch,
):
    drivers, _sync, images_root = sync_environment
    receive_upload_chunk(images_root, "fresh", "fresh.qcow2", b"new image")
    receive_upload_chunk(images_root, "fresh", "fresh.qcow2.desc", b"new desc\n")
    move_order = []
    real_move = image_sync_module.shutil.move

    def record_move(source, destination):
        move_order.append(Path(source).name)
        return real_move(source, destination)

    monkeypatch.setattr(image_sync_module.shutil, "move", record_move)

    result = finalize_upload(
        images_root,
        "fresh",
        driver_hook_manager=drivers.hook_manager,
    )

    assert result["finalized"] is True
    assert move_order == ["fresh.qcow2.desc", "fresh.qcow2"]
    assert (images_root / "fresh/fresh.qcow2.desc").read_bytes() == b"new desc\n"
    assert (images_root / "fresh/fresh.qcow2").read_bytes() == b"new image"


def test_new_image_finalize_serializes_concurrent_assignment(
    sync_environment,
    monkeypatch,
):
    drivers, _sync, images_root = sync_environment
    receive_upload_chunk(images_root, "fresh", "fresh.qcow2", b"new image")
    entered_move = threading.Event()
    release_move = threading.Event()
    assignment_started = threading.Event()
    assignment_finished = threading.Event()
    failures = []
    real_move = image_sync_module.shutil.move

    def blocking_move(source, destination):
        if Path(source).name == "fresh.qcow2":
            entered_move.set()
            if not release_move.wait(timeout=5):
                raise TimeoutError("fixture did not release staged move")
        return real_move(source, destination)

    monkeypatch.setattr(image_sync_module.shutil, "move", blocking_move)

    def finalize():
        try:
            finalize_upload(
                images_root,
                "fresh",
                driver_hook_manager=drivers.hook_manager,
            )
        except Exception as error:  # pragma: no cover - asserted below
            failures.append(error)

    def assign():
        assignment_started.set()
        try:
            drivers.set_profile_image("ModelA", "fresh")
        except Exception as error:  # pragma: no cover - asserted below
            failures.append(error)
        finally:
            assignment_finished.set()

    finalize_thread = threading.Thread(target=finalize)
    finalize_thread.start()
    assert entered_move.wait(timeout=5)

    assignment_thread = threading.Thread(target=assign)
    assignment_thread.start()
    assert assignment_started.wait(timeout=5)
    assert not assignment_finished.wait(timeout=0.2)

    release_move.set()
    finalize_thread.join(timeout=5)
    assignment_thread.join(timeout=5)

    assert not finalize_thread.is_alive()
    assert not assignment_thread.is_alive()
    assert failures == []
    assert (images_root / "fresh/fresh.qcow2").read_bytes() == b"new image"
    assert drivers.get_profile_image("ModelA") == "fresh"
    assert (images_root / "fresh/fresh.driverpostsync").is_file()
