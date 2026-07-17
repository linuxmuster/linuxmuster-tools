import errno
import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

import linuxmusterTools.linbo.driver_hooks as driver_hooks
from linuxmusterTools.linbo.driver_hooks import (
    MANAGED_HEADER,
    DriverAssignmentScanError,
    DriverHookOwnershipError,
    DriverHookTransactionError,
    LinboDriverHookManager,
    render_driverpostsync,
    validate_image_name,
    validate_profile_name,
)
from linuxmusterTools.linbo.driver_storage import StorageSecurityError


@pytest.fixture
def hook_environment(tmp_path: Path) -> tuple[LinboDriverHookManager, Path, Path]:
    drivers_root = tmp_path / "drivers"
    images_root = tmp_path / "images"
    drivers_root.mkdir()
    images_root.mkdir()
    manager = LinboDriverHookManager(
        drivers_root=drivers_root,
        images_root=images_root,
        lock_path=tmp_path / "driver-hooks.lock",
    )
    return manager, drivers_root, images_root


def make_image(images_root: Path, name: str) -> Path:
    image_directory = images_root / name
    image_directory.mkdir()
    (image_directory / f"{name}.qcow2").write_bytes(b"qcow fixture")
    return image_directory


def make_profile(drivers_root: Path, name: str, image: str | None = None) -> Path:
    profile_directory = drivers_root / name
    profile_directory.mkdir()
    (profile_directory / "match.conf").write_text(
        "[match]\nvendor = Fixture\nproduct = *\n", encoding="utf-8"
    )
    if image is not None:
        (profile_directory / "image.conf").write_text(
            f"# Image assignment for driver profile\nimage = {image}\n",
            encoding="utf-8",
        )
    return profile_directory


def hook_path(image_directory: Path) -> Path:
    return image_directory / f"{image_directory.name}.driverpostsync"


def assert_shell_syntax(path: Path) -> None:
    interpreters = [["/bin/sh", "-n", os.fspath(path)]]
    busybox = shutil.which("busybox")
    if busybox is not None:
        interpreters.append([busybox, "sh", "-n", os.fspath(path)])

    for command in interpreters:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{command[0]}: {result.stderr}"


def test_multi_profile_hook_is_complete_sorted_executable_and_shell_valid(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    make_image(images_root, "other")
    make_profile(drivers_root, "Zulu", "win11")
    make_profile(drivers_root, "alpha", "win11")
    make_profile(drivers_root, "Beta", "win11")
    make_profile(drivers_root, "NotForThisImage", "other")

    result = manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    content = generated.read_text(encoding="utf-8")

    assert result["profiles"] == ["alpha", "Beta", "Zulu"]
    assert result["tombstone"] is False
    assert content.startswith("#!/bin/sh\n")
    assert content.splitlines()[1] == MANAGED_HEADER
    assert "# Profiles: alpha, Beta, Zulu" in content
    assert 'DRIVERPOSTSYNC_PROFILES="alpha Beta Zulu"' in content
    assert "NotForThisImage" not in content
    assert "$LINBOSERVER::linbo/drivers/$FOLDER/match.conf" in content
    assert 'rsync -a --delete --timeout=120 "$LINBOSERVER::linbo/drivers/$FOLDER/"' in content
    assert '.previous-$FOLDER-$$' in content
    assert 'C:\\\\Drivers\\\\LINBO\\\\*.inf /subdirs /install' in content
    assert 'if "%%LINBO_RC%%"=="259" goto no_action' in content
    assert 'if "%%LINBO_RC%%"=="1641" goto success' in content
    assert 'if "%%LINBO_RC%%"=="3010" goto success' in content
    assert "FOUND_PRODUCT=0" in content
    assert '[ "$FOUND_PRODUCT" != "1" ]' in content
    assert "no product restriction" not in content
    assert 'if [ "$FOUND_MATCH_SECTION" = "1" ]; then' in content
    assert 'SECTION_NAME=${line#\\[}' in content
    assert '""|*[!a-zA-Z0-9_.-]*)' in content
    assert "LINBO SYSTEM driver startup task v1" in content
    assert "LINBO-Patchless SYSTEM startup task v1" in content
    assert "LINBO-Driver-Install" in content
    assert '"!LinboDriverInstall"="cmd.exe /d /s /c C:\\\\Drivers' in content
    assert 'return "$DRIVERPOSTSYNC_RC"' in content
    assert stat.S_IMODE(generated.stat().st_mode) == 0o755
    assert_shell_syntax(generated)


def test_zero_profiles_publish_cleanup_tombstone_with_registry_contract(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, _, images_root = hook_environment
    image_directory = make_image(images_root, "win11")

    result = manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    content = generated.read_text(encoding="utf-8")

    assert result["profiles"] == []
    assert result["tombstone"] is True
    assert content.startswith("#!/bin/sh\n")
    assert "Auto-generated driverpostsync tombstone" in content
    assert 'rm -rf "$DRIVERPOSTSYNC_TARGET" "$DRIVERPOSTSYNC_CACHE"' in content
    assert '"LinboDriverInstall"=-' in content
    assert '"!LinboDriverInstall"=-' in content
    assert "Non-Windows target detected; cleanup tombstone skipped." in content
    assert 'return "$DRIVERPOSTSYNC_RC"' in content
    assert stat.S_IMODE(generated.stat().st_mode) == 0o755
    assert_shell_syntax(generated)


def test_rendering_is_deterministic_and_deduplicates_profiles() -> None:
    first = render_driverpostsync("win11", ["Zulu", "alpha", "Beta", "alpha"])
    second = render_driverpostsync("win11", ["Beta", "Zulu", "alpha"])

    assert first == second
    assert first.startswith("#!/bin/sh\n")
    assert '# Profiles: alpha, Beta, Zulu' in first
    assert 'DRIVERPOSTSYNC_PROFILES="alpha Beta Zulu"' in first
    assert "@@IMAGE@@" not in first
    assert "@@PROFILE" not in first


def test_full_hook_matches_reviewed_golden_digest() -> None:
    rendered = render_driverpostsync(
        "win11.24.04",
        ["Zulu", "alpha", "Beta", "alpha"],
    )
    fixture = (
        Path(__file__).with_name("fixtures")
        / "win11-multi-profile.driverpostsync.sha256"
    )

    assert hashlib.sha256(rendered.encode("utf-8")).hexdigest() == (
        fixture.read_text(encoding="ascii").strip()
    )


def test_assignment_move_and_removal_regenerate_all_affected_hooks(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_a = make_image(images_root, "image_a")
    image_b = make_image(images_root, "image_b")
    profile = make_profile(drivers_root, "ModelA")

    assert manager.set_profile_image("ModelA", "image_a") == {
        "folder": "ModelA",
        "image": "image_a",
    }
    assert "image = image_a" in (profile / "image.conf").read_text(encoding="utf-8")
    assert 'DRIVERPOSTSYNC_PROFILES="ModelA"' in hook_path(image_a).read_text(
        encoding="utf-8"
    )

    manager.set_profile_image("ModelA", "image_b")
    assert "image = image_b" in (profile / "image.conf").read_text(encoding="utf-8")
    assert "driverpostsync tombstone" in hook_path(image_a).read_text(encoding="utf-8")
    assert 'DRIVERPOSTSYNC_PROFILES="ModelA"' in hook_path(image_b).read_text(
        encoding="utf-8"
    )

    manager.remove_profile_image("ModelA")
    assert not (profile / "image.conf").exists()
    assert "driverpostsync tombstone" in hook_path(image_b).read_text(encoding="utf-8")
    assert_shell_syntax(hook_path(image_a))
    assert_shell_syntax(hook_path(image_b))


def test_legacy_match_profile_must_be_migrated_before_direct_assignment(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    make_image(images_root, "win11")
    profile = make_profile(drivers_root, "Legacy")
    (profile / "match.conf").write_text(
        "[match]\nsys_vendor = LENOVO\nproduct_name = 21L4\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="legacy match keys"):
        manager.set_profile_image("Legacy", "win11")

    assert not (profile / "image.conf").exists()


def test_foreign_hook_is_preserved_and_assignment_is_rolled_back(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    profile = make_profile(drivers_root, "ModelA")
    foreign_hook = hook_path(image_directory)
    foreign_content = "#!/bin/sh\necho administrator-owned\n"
    foreign_hook.write_text(foreign_content, encoding="utf-8")

    with pytest.raises(DriverHookOwnershipError):
        manager.regenerate_postsync("win11")
    assert foreign_hook.read_text(encoding="utf-8") == foreign_content

    with pytest.raises(DriverHookTransactionError) as transaction:
        manager.set_profile_image("ModelA", "win11")
    assert isinstance(transaction.value.cause, DriverHookOwnershipError)
    assert not (profile / "image.conf").exists()
    assert foreign_hook.read_text(encoding="utf-8") == foreign_content


def test_legacy_patchless_hook_is_recognized_as_owned_for_migration(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, _, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    legacy = hook_path(image_directory)
    legacy.write_text(
        "#!/bin/sh\n"
        "# =============================================================================\n"
        "# Auto-generated driverpostsync script for image: win11\n"
        "# Generated by LINBO Patchless — DO NOT EDIT MANUALLY\n"
        "# Profiles: old\n",
        encoding="utf-8",
    )

    manager.regenerate_postsync("win11")

    assert hook_path(image_directory).read_text(encoding="utf-8").splitlines()[1] == MANAGED_HEADER


def test_atomic_replace_failure_keeps_previous_hook_and_removes_temporary_file(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    previous = generated.read_bytes()
    make_profile(drivers_root, "ModelA", "win11")
    real_replace = driver_hooks.os.replace

    def fail_hook_replace(source: os.PathLike[str], destination: os.PathLike[str]) -> None:
        if Path(destination) == generated:
            raise OSError(errno.EIO, "injected hook replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(driver_hooks.os, "replace", fail_hook_replace)

    with pytest.raises(OSError, match="injected hook replacement failure"):
        manager.regenerate_postsync("win11")

    assert generated.read_bytes() == previous
    assert list(image_directory.glob(f".{generated.name}.tmp-*")) == []


def test_global_assignment_scan_failure_preserves_hook_and_blocks_lifecycle(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    profile = make_profile(drivers_root, "ModelA", "win11")
    manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    previous = generated.read_bytes()
    previous_assignment = (profile / "image.conf").read_bytes()
    real_scandir = driver_hooks.os.scandir

    def fail_driver_scan(path):
        if Path(path) == drivers_root:
            raise OSError(errno.EIO, "injected assignment scan failure")
        return real_scandir(path)

    monkeypatch.setattr(driver_hooks.os, "scandir", fail_driver_scan)

    with pytest.raises(DriverAssignmentScanError):
        manager.regenerate_postsync("win11")
    with pytest.raises(DriverAssignmentScanError):
        with manager.unassigned_image_lifecycle("win11"):
            pass

    result = manager.reconcile_all_postsync()
    assert result["regenerated"] == []
    assert any("injected assignment scan failure" in item["message"] for item in result["failed"])
    assert generated.read_bytes() == previous
    assert (profile / "image.conf").read_bytes() == previous_assignment
    assert (image_directory / "win11.qcow2").is_file()


def test_unassigned_incomplete_profile_directories_do_not_block_hooks(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    (drivers_root / "Empty").mkdir()
    payload_only = drivers_root / "PayloadOnly"
    payload_only.mkdir()
    (payload_only / "driver.inf").write_bytes(b"fixture")

    manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    assert "driverpostsync tombstone" in generated.read_text(encoding="utf-8")

    result = manager.reconcile_all_postsync()
    assert result == {"regenerated": ["win11"], "failed": []}

    with manager.unassigned_image_lifecycle("win11"):
        pass
    assert not generated.exists()


@pytest.mark.parametrize(
    "invalid_content",
    [
        "",
        "image = win11\nimage = other\n",
        "unknown = win11\n",
        "not an assignment\n",
    ],
)
def test_invalid_image_conf_never_becomes_an_empty_assignment(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
    invalid_content: str,
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    profile = make_profile(drivers_root, "ModelA", "win11")
    manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    previous = generated.read_bytes()
    image_conf = profile / "image.conf"
    image_conf.write_text(invalid_content, encoding="utf-8")

    with pytest.raises(DriverAssignmentScanError):
        manager.regenerate_postsync("win11")
    with pytest.raises(DriverAssignmentScanError):
        with manager.unassigned_image_lifecycle("win11"):
            pass
    with pytest.raises(ValueError):
        manager.remove_profile_image("ModelA")

    assert generated.read_bytes() == previous
    assert image_conf.read_text(encoding="utf-8") == invalid_content
    assert (image_directory / "win11.qcow2").is_file()


def test_invalid_image_reference_blocks_all_hook_publication(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    profile = make_profile(drivers_root, "ModelA", "win11")
    manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    previous = generated.read_bytes()
    image_conf = profile / "image.conf"
    broken_assignment = "image = win11..broken\n"
    image_conf.write_text(broken_assignment, encoding="utf-8")

    with pytest.raises(DriverAssignmentScanError):
        manager.regenerate_postsync("win11")
    with pytest.raises(DriverAssignmentScanError):
        with manager.unassigned_image_lifecycle("win11"):
            pass

    result = manager.reconcile_all_postsync()
    assert result["regenerated"] == []
    assert any(failure.get("fatal") is True for failure in result["failed"])
    assert generated.read_bytes() == previous
    assert image_conf.read_text(encoding="utf-8") == broken_assignment
    assert (image_directory / "win11.qcow2").is_file()


def test_unreadable_image_conf_preserves_existing_hook(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, drivers_root, images_root = hook_environment
    image_directory = make_image(images_root, "win11")
    profile = make_profile(drivers_root, "ModelA", "win11")
    manager.regenerate_postsync("win11")
    generated = hook_path(image_directory)
    previous = generated.read_bytes()
    image_conf = profile / "image.conf"
    previous_assignment = image_conf.read_bytes()
    real_read = driver_hooks._read_regular_file

    def fail_image_conf(path, max_bytes):
        if Path(path) == image_conf:
            raise OSError(errno.EIO, "injected image.conf read failure")
        return real_read(path, max_bytes)

    monkeypatch.setattr(driver_hooks, "_read_regular_file", fail_image_conf)

    with pytest.raises(DriverAssignmentScanError):
        manager.regenerate_postsync("win11")
    with pytest.raises(DriverAssignmentScanError):
        with manager.unassigned_image_lifecycle("win11"):
            pass

    assert generated.read_bytes() == previous
    assert image_conf.read_bytes() == previous_assignment
    assert (image_directory / "win11.qcow2").is_file()


def test_traversal_profile_image_and_hook_symlinks_are_rejected(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
    tmp_path: Path,
) -> None:
    manager, drivers_root, images_root = hook_environment
    with pytest.raises(ValueError):
        validate_profile_name("../escape")
    assert validate_image_name("win11.24.04") == "win11.24.04"
    assert validate_image_name("_recovery.-staged") == "_recovery.-staged"
    assert validate_image_name(".recovery") == ".recovery"
    assert validate_image_name("win11.") == "win11."
    for invalid_image in (".", "../escape", "win11..24", "win11/24", "win11\\24"):
        with pytest.raises(ValueError):
            validate_image_name(invalid_image)

    outside_profile = tmp_path / "outside-profile"
    outside_profile.mkdir()
    (outside_profile / "match.conf").write_text(
        "[match]\nvendor = X\nproduct = *\n", encoding="utf-8"
    )
    (drivers_root / "LinkedProfile").symlink_to(outside_profile, target_is_directory=True)
    make_image(images_root, "realimage")
    with pytest.raises(ValueError):
        manager.set_profile_image("LinkedProfile", "realimage")

    outside_image = tmp_path / "outside-image"
    outside_image.mkdir()
    (outside_image / "linkedimage.qcow2").write_bytes(b"qcow")
    (images_root / "linkedimage").symlink_to(outside_image, target_is_directory=True)
    with pytest.raises(ValueError):
        manager.regenerate_postsync("linkedimage")

    image_directory = images_root / "realimage"
    outside_hook = tmp_path / "outside-hook"
    outside_hook.write_text("do not replace", encoding="utf-8")
    hook_path(image_directory).symlink_to(outside_hook)
    with pytest.raises(DriverHookOwnershipError):
        manager.regenerate_postsync("realimage")
    assert outside_hook.read_text(encoding="utf-8") == "do not replace"


def test_symlinked_lock_file_is_never_followed(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
    tmp_path: Path,
) -> None:
    _, drivers_root, images_root = hook_environment
    make_image(images_root, "win11")
    outside = tmp_path / "outside-lock"
    outside.write_text("unchanged", encoding="utf-8")
    lock_link = tmp_path / "linked-lock"
    lock_link.symlink_to(outside)
    manager = LinboDriverHookManager(
        drivers_root=drivers_root,
        images_root=images_root,
        lock_path=lock_link,
    )

    with pytest.raises(StorageSecurityError, match="cannot open lock file"):
        manager.regenerate_postsync("win11")
    assert outside.read_text(encoding="utf-8") == "unchanged"


def test_default_lock_is_shared_with_profile_storage(tmp_path: Path) -> None:
    drivers_root = tmp_path / "drivers"
    manager = LinboDriverHookManager(
        drivers_root=drivers_root,
        images_root=tmp_path / "images",
    )

    assert manager.lock_path == drivers_root / ".driver-profiles.lock"


def test_list_available_images_returns_only_real_complete_qcow2_bases(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
    tmp_path: Path,
) -> None:
    manager, _, images_root = hook_environment
    make_image(images_root, "zeta")
    make_image(images_root, "Alpha")

    incomplete = images_root / "incomplete"
    incomplete.mkdir()
    (incomplete / "different.qcow2").write_bytes(b"wrong basename")

    make_image(images_root, "win.11")

    for housekeeping in ("tmp", "backups"):
        directory = images_root / housekeeping
        directory.mkdir()
        (directory / f"{housekeeping}.qcow2").write_bytes(b"housekeeping")

    outside_directory = tmp_path / "outside-image-directory"
    outside_directory.mkdir()
    (outside_directory / "linked.qcow2").write_bytes(b"outside")
    (images_root / "linked").symlink_to(outside_directory, target_is_directory=True)

    symlinked_file_directory = images_root / "symlinkedfile"
    symlinked_file_directory.mkdir()
    outside_qcow = tmp_path / "outside.qcow2"
    outside_qcow.write_bytes(b"outside")
    (symlinked_file_directory / "symlinkedfile.qcow2").symlink_to(outside_qcow)

    assert manager.list_available_images() == [
        {"name": "Alpha", "filename": "Alpha.qcow2"},
        {"name": "win.11", "filename": "win.11.qcow2"},
        {"name": "zeta", "filename": "zeta.qcow2"},
    ]


def test_failure_after_new_hook_publish_restores_assignment_and_safe_new_state(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    old_image = make_image(images_root, "oldimage")
    new_image = make_image(images_root, "newimage")
    profile = make_profile(drivers_root, "ModelA", "oldimage")
    foreign_content = "#!/bin/sh\necho custom old hook\n"
    hook_path(old_image).write_text(foreign_content, encoding="utf-8")

    with pytest.raises(DriverHookTransactionError) as transaction:
        manager.set_profile_image("ModelA", "newimage")

    assert isinstance(transaction.value.cause, DriverHookOwnershipError)
    assert "image = oldimage" in (profile / "image.conf").read_text(encoding="utf-8")
    assert hook_path(old_image).read_text(encoding="utf-8") == foreign_content
    assert "driverpostsync tombstone" in hook_path(new_image).read_text(encoding="utf-8")
    assert transaction.value.rollback_failures


def test_reconcile_claims_only_assignments_and_existing_owned_hooks(
    hook_environment: tuple[LinboDriverHookManager, Path, Path],
) -> None:
    manager, drivers_root, images_root = hook_environment
    assigned = make_image(images_root, "assigned")
    owned = make_image(images_root, "owned")
    unrelated = make_image(images_root, "unrelated")
    foreign = make_image(images_root, "foreign")
    make_profile(drivers_root, "ModelA", "assigned")
    hook_path(owned).write_text(render_driverpostsync("owned", []), encoding="utf-8")
    foreign_content = "#!/bin/sh\necho custom\n"
    hook_path(foreign).write_text(foreign_content, encoding="utf-8")

    result = manager.reconcile_all_postsync()

    assert result["regenerated"] == ["assigned", "owned"]
    assert any(failure.get("image") == "foreign" for failure in result["failed"])
    assert hook_path(assigned).exists()
    assert "driverpostsync tombstone" in hook_path(owned).read_text(encoding="utf-8")
    assert not hook_path(unrelated).exists()
    assert hook_path(foreign).read_text(encoding="utf-8") == foreign_content
    assert_shell_syntax(hook_path(assigned))
    assert_shell_syntax(hook_path(owned))
