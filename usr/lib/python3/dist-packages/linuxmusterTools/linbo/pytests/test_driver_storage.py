import errno
import multiprocessing
import os
from pathlib import Path

import pytest

import linuxmusterTools.linbo.driver_storage as storage
from linuxmusterTools.linbo.driver_storage import (
    StorageSecurityError,
    atomic_write,
    atomic_write_text,
    file_lock,
    list_regular_files,
    read_bytes_limited,
    read_text_limited,
    validate_driver_payload,
    validate_profile_name,
)


def _hold_lock(lock_path: str, entered, release) -> None:
    with file_lock(Path(lock_path)):
        entered.set()
        release.wait(timeout=5)


def _make_driver_payload(tmp_path: Path, name: str = "Profile") -> Path:
    tmp_path.chmod(0o755)
    profile = tmp_path / name
    profile.mkdir(mode=0o755)
    profile.chmod(0o755)
    match_conf = profile / "match.conf"
    match_conf.write_text("[match]\nvendor = Dell\nproduct = Latitude\n")
    match_conf.chmod(0o644)
    return profile


def test_atomic_write_creates_complete_file_with_requested_mode(tmp_path):
    target = tmp_path / "match.conf"

    atomic_write_text(target, "[match]\nvendor = Dell\n", mode=0o640)

    assert target.read_text(encoding="utf-8") == "[match]\nvendor = Dell\n"
    assert target.stat().st_mode & 0o777 == 0o640
    assert list(tmp_path.glob(".match.conf.tmp-*")) == []


def test_atomic_write_supports_exact_binary_restore_payloads(tmp_path):
    target = tmp_path / "image.conf"

    atomic_write(target, b"image = win11\n", mode=0o600)

    assert target.read_bytes() == b"image = win11\n"
    assert target.stat().st_mode & 0o777 == 0o600


def test_failed_replace_preserves_original_and_cleans_temporary(tmp_path, monkeypatch):
    target = tmp_path / "match.conf"
    target.write_text("original\n", encoding="utf-8")

    def fail_replace(_source, _target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(storage.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        atomic_write_text(target, "replacement\n")

    assert target.read_text(encoding="utf-8") == "original\n"
    assert list(tmp_path.glob(".match.conf.tmp-*")) == []


def test_atomic_write_refuses_symlink_target(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("unchanged", encoding="utf-8")
    target = tmp_path / "match.conf"
    target.symlink_to(outside)

    with pytest.raises(StorageSecurityError, match="not a regular file"):
        atomic_write_text(target, "changed")

    assert outside.read_text(encoding="utf-8") == "unchanged"


def test_file_lock_never_follows_a_symlink(tmp_path):
    outside = tmp_path / "outside-lock"
    outside.write_text("unchanged", encoding="utf-8")
    linked_lock = tmp_path / "linked-lock"
    linked_lock.symlink_to(outside)

    with pytest.raises(StorageSecurityError, match="cannot open lock file"):
        with file_lock(linked_lock):
            pass

    assert outside.read_text(encoding="utf-8") == "unchanged"


def test_file_lock_serializes_independent_worker_processes(tmp_path):
    context = multiprocessing.get_context("fork")
    lock_path = tmp_path / "workers.lock"
    first_entered = context.Event()
    second_entered = context.Event()
    release = context.Event()
    first = context.Process(
        target=_hold_lock,
        args=(str(lock_path), first_entered, release),
    )
    second = context.Process(
        target=_hold_lock,
        args=(str(lock_path), second_entered, release),
    )

    first.start()
    assert first_entered.wait(timeout=2)
    second.start()
    assert not second_entered.wait(timeout=0.2)

    release.set()
    assert second_entered.wait(timeout=2)
    first.join(timeout=2)
    second.join(timeout=2)

    assert first.exitcode == 0
    assert second.exitcode == 0


def test_bounded_reader_rejects_oversized_file(tmp_path):
    target = tmp_path / "match.conf"
    target.write_bytes(b"x" * 11)

    with pytest.raises(ValueError, match="too large"):
        read_text_limited(target, 10)


def test_bounded_binary_reader_returns_descriptor_metadata(tmp_path):
    target = tmp_path / "payload.bin"
    target.write_bytes(b"driver payload")

    payload, metadata = read_bytes_limited(target, 1024)

    assert payload == b"driver payload"
    assert metadata.st_ino == target.stat().st_ino
    assert metadata.st_size == len(payload)


def test_bounded_binary_reader_uses_neutral_file_errors(tmp_path):
    oversized = tmp_path / "oversized.bin"
    oversized.write_bytes(b"xx")
    linked = tmp_path / "linked.bin"
    linked.symlink_to(oversized)

    with pytest.raises(OSError) as not_regular:
        read_bytes_limited(tmp_path, 1024)
    assert not_regular.value.errno == errno.EINVAL

    with pytest.raises(OSError) as too_large:
        read_bytes_limited(oversized, 1)
    assert too_large.value.errno == errno.EFBIG

    with pytest.raises(OSError) as symlinked:
        read_bytes_limited(linked, 1024)
    assert symlinked.value.errno == errno.ELOOP


def test_bounded_binary_reader_fallback_rejects_symlinks(
    tmp_path,
    monkeypatch,
):
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"secret")
    linked = tmp_path / "linked.bin"
    linked.symlink_to(outside)
    monkeypatch.setattr(storage.os, "O_NOFOLLOW", 0)

    with pytest.raises(OSError) as error:
        read_bytes_limited(linked, 1024)

    assert error.value.errno == errno.ELOOP


def test_bounded_reader_never_follows_a_symlink(tmp_path):
    outside = tmp_path / "outside.conf"
    outside.write_text("secret", encoding="utf-8")
    target = tmp_path / "match.conf"
    target.symlink_to(outside)

    with pytest.raises(StorageSecurityError, match="cannot safely open"):
        read_text_limited(target, 1024)


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        ".hidden",
        "name/child",
        "name\\child",
        "",
        "x" * 101,
        "CON",
        "lpt1.vendor",
        "Profile.",
        "PNPUTIL-INSTALL.CMD",
    ],
)
def test_profile_name_validation_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        validate_profile_name(name)


def test_profile_name_validation_normalizes_outer_whitespace():
    assert validate_profile_name("  Dell-5520  ") == "Dell-5520"


def test_recursive_listing_rejects_payload_symlinks(tmp_path):
    profile = tmp_path / "Profile"
    profile.mkdir()
    outside = tmp_path / "outside.inf"
    outside.write_text("driver", encoding="utf-8")
    (profile / "linked.inf").symlink_to(outside)

    with pytest.raises(StorageSecurityError, match="symbolic link"):
        list_regular_files(profile)


def test_payload_preflight_returns_bounded_totals_and_excludes_metadata(tmp_path):
    profile = _make_driver_payload(tmp_path)
    network = profile / "Network"
    network.mkdir(mode=0o755)
    network.chmod(0o755)
    inf = network / "driver.INF"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)
    catalog = network / "driver.cat"
    catalog.write_bytes(b"catalog")
    catalog.chmod(0o644)

    summary = validate_driver_payload(profile)

    assert summary.file_count == 2
    assert summary.directory_count == 1
    assert summary.total_size == len(b"drivercatalog")
    assert summary.inf_count == 1


def test_payload_preflight_accepts_owner_permissions_for_rsync_identity(tmp_path):
    profile = _make_driver_payload(tmp_path)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    profile.chmod(0o700)
    (profile / "match.conf").chmod(0o600)
    inf.chmod(0o600)

    summary = validate_driver_payload(
        profile,
        reader_uid=os.getuid(),
        reader_gid=os.getgid(),
    )

    assert summary.inf_count == 1


def test_payload_preflight_rejects_file_unreadable_by_rsync_nobody(tmp_path):
    profile = _make_driver_payload(tmp_path)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o640)

    with pytest.raises(ValueError, match="not readable by rsync nobody:nogroup"):
        validate_driver_payload(profile)


def test_payload_preflight_rejects_profile_unreadable_by_rsync_nobody(tmp_path):
    profile = _make_driver_payload(tmp_path)
    profile.chmod(0o750)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)

    with pytest.raises(ValueError, match="not readable and traversable"):
        validate_driver_payload(profile)


def test_payload_preflight_rejects_untraversable_profile_storage(tmp_path):
    profile = _make_driver_payload(tmp_path)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)
    tmp_path.chmod(0o700)

    with pytest.raises(ValueError, match="not readable and traversable"):
        validate_driver_payload(profile)


def test_payload_preflight_rejects_directory_not_traversable_by_rsync(tmp_path):
    profile = _make_driver_payload(tmp_path)
    nested = profile / "Network"
    nested.mkdir(mode=0o755)
    nested.chmod(0o744)
    inf = nested / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)

    with pytest.raises(ValueError, match="not readable and traversable"):
        validate_driver_payload(profile)


def test_payload_preflight_validates_metadata_rsync_permissions(tmp_path):
    profile = _make_driver_payload(tmp_path)
    (profile / "match.conf").chmod(0o600)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)

    with pytest.raises(ValueError, match="match.conf"):
        validate_driver_payload(profile)


def test_payload_preflight_rejects_symlinks_and_special_files(tmp_path):
    profile = _make_driver_payload(tmp_path)
    outside = tmp_path / "outside.inf"
    outside.write_bytes(b"driver")
    linked = profile / "linked.inf"
    linked.symlink_to(outside)

    with pytest.raises(StorageSecurityError, match="symbolic link"):
        validate_driver_payload(profile)

    linked.unlink()
    fifo = profile / "driver.inf"
    os.mkfifo(fifo, mode=0o644)
    with pytest.raises(StorageSecurityError, match="special file"):
        validate_driver_payload(profile)


@pytest.mark.parametrize(
    "invalid_name",
    [
        "CON.inf",
        "aux.txt",
        "COM¹.inf",
        "LPT².cat",
        "bad-name. ",
        "bad:name.inf",
        "contains\\separator.inf",
    ],
)
def test_payload_preflight_rejects_windows_incompatible_names(
    tmp_path,
    invalid_name,
):
    profile = _make_driver_payload(tmp_path)
    valid_inf = profile / "driver.inf"
    valid_inf.write_bytes(b"driver")
    valid_inf.chmod(0o644)
    invalid = profile / invalid_name
    invalid.write_bytes(b"invalid")
    invalid.chmod(0o644)

    with pytest.raises(ValueError, match="Windows"):
        validate_driver_payload(profile)


def test_payload_preflight_rejects_case_insensitive_windows_collisions(tmp_path):
    profile = _make_driver_payload(tmp_path)
    first = profile / "Network.inf"
    second = profile / "network.INF"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    first.chmod(0o644)
    second.chmod(0o644)

    with pytest.raises(ValueError, match="case-insensitive Windows path collision"):
        validate_driver_payload(profile)


@pytest.mark.parametrize("profile_name", ["CON", "PNPUTIL-INSTALL.CMD"])
def test_payload_preflight_rejects_windows_incompatible_profile_name(
    tmp_path,
    profile_name,
):
    profile = _make_driver_payload(tmp_path, profile_name)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)

    with pytest.raises(ValueError, match="Windows|managed installer"):
        validate_driver_payload(profile)


def test_payload_preflight_allows_installer_name_inside_profile(tmp_path):
    profile = _make_driver_payload(tmp_path)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)
    nested_installer = profile / "PnPUtil-Install.CMD"
    nested_installer.write_bytes(b"vendor helper")
    nested_installer.chmod(0o644)

    summary = validate_driver_payload(profile)

    assert summary.file_count == 2


def test_payload_preflight_requires_at_least_one_inf(tmp_path):
    profile = _make_driver_payload(tmp_path)
    catalog = profile / "driver.cat"
    catalog.write_bytes(b"catalog")
    catalog.chmod(0o644)

    with pytest.raises(ValueError, match="contains no INF file"):
        validate_driver_payload(profile)


def test_payload_preflight_enforces_entry_and_byte_limits(tmp_path):
    profile = _make_driver_payload(tmp_path)
    inf = profile / "driver.inf"
    inf.write_bytes(b"driver")
    inf.chmod(0o644)

    with pytest.raises(ValueError, match="more than 1 entries"):
        validate_driver_payload(profile, max_entries=1)

    with pytest.raises(ValueError, match="exceeds 5 bytes"):
        validate_driver_payload(profile, max_bytes=5)
