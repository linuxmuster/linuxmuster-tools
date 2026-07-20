import os
from pathlib import Path

import pytest

import linuxmusterTools.linbo.drivers as drivers_module
from linuxmusterTools.linbo import LinboDriverManager as ExportedDriverManager
from linuxmusterTools.linbo.drivers import (
    DriverProfileExistsError,
    LinboDriverManager,
)


def test_manager_is_exported_from_linbo_package():
    assert ExportedDriverManager is LinboDriverManager


def test_missing_profile_base_lists_no_profiles(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")

    assert manager.list_profiles() == []


def test_create_profile_writes_canonical_match_conf(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)

    profile = manager.create_profile("lenovo-21l4", "LENOVO", "21L4")

    assert (base / "lenovo-21l4/match.conf").read_text() == (
        "[match]\n"
        "vendor = LENOVO\n"
        "product = 21L4\n"
    )
    assert (base / "lenovo-21l4/match.conf").stat().st_mode & 0o777 == 0o644
    assert profile == {
        "name": "lenovo-21l4",
        "path": str(base / "lenovo-21l4"),
        "matchConf": {"vendor": "LENOVO", "product": "21L4"},
    }


@pytest.mark.parametrize(
    "value",
    ["0012", "yes", "no"],
)
def test_match_values_remain_exact_strings(tmp_path, value):
    manager = LinboDriverManager(tmp_path / "drivers")

    created = manager.create_profile(f"profile-{value}", value, value)

    assert created["matchConf"] == {"vendor": value, "product": value}


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".hidden",
        "-leading",
        "../escape",
        "bad/name",
        "trailing.",
        "CON",
        "con.txt",
        "pnputil-install.cmd",
        "a" * 101,
    ],
)
def test_create_rejects_unsafe_or_windows_reserved_names(tmp_path, name):
    manager = LinboDriverManager(tmp_path / "drivers")

    with pytest.raises(ValueError):
        manager.create_profile(name, "Dell", "Latitude")


@pytest.mark.parametrize(
    ("vendor", "product"),
    [
        ("", "Latitude"),
        ("Dell", ""),
        (None, "Latitude"),
        ("Dell", ["Latitude"]),
        ("Dell\nproduct = *", "Latitude"),
        ("Dell#Lab", "Latitude"),
        ("Dell", "Latitude|Anything"),
    ],
)
def test_create_rejects_invalid_match_values(tmp_path, vendor, product):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)

    with pytest.raises(ValueError):
        manager.create_profile("invalid-match", vendor, product)

    assert not (base / "invalid-match").exists()


def test_explicit_wildcards_are_supported(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")

    profile = manager.create_profile("all-hardware", "*", "*")

    assert profile["matchConf"] == {"vendor": "*", "product": "*"}


def test_create_does_not_replace_an_existing_profile(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")
    manager.create_profile("existing", "Original", "Model")

    with pytest.raises(DriverProfileExistsError) as error:
        manager.create_profile("existing", "Replacement", "Model")

    assert error.value.profile == "existing"
    assert manager.get_profile("existing")["matchConf"]["vendor"] == "Original"


def test_create_rejects_casefold_name_collision(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")
    manager.create_profile("Model-A", "Original", "Model")

    with pytest.raises(DriverProfileExistsError):
        manager.create_profile("model-a", "Replacement", "Model")

    assert manager.get_profile("Model-A")["matchConf"]["vendor"] == "Original"


def test_get_missing_profile_returns_none(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")

    assert manager.get_profile("missing") is None


def test_update_changes_only_match_conf(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)
    manager.create_profile("dell", "Dell", "Old")
    payload = base / "dell/Network/driver.inf"
    payload.parent.mkdir()
    payload.write_bytes(b"driver payload")

    updated = manager.update_match("dell", "Dell Inc.", "Latitude 5520")

    assert payload.read_bytes() == b"driver payload"
    assert updated["matchConf"] == {
        "vendor": "Dell Inc.",
        "product": "Latitude 5520",
    }


def test_update_missing_profile_does_not_create_it(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)

    with pytest.raises(FileNotFoundError):
        manager.update_match("missing", "Dell", "Latitude")

    assert not (base / "missing").exists()


def test_list_profiles_returns_only_complete_valid_profiles(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)
    manager.create_profile("valid", "Dell", "Latitude")
    (base / "incomplete").mkdir()
    duplicate = base / "duplicate"
    duplicate.mkdir()
    (duplicate / "match.conf").write_text(
        "[match]\n"
        "vendor = Dell\n"
        "product = Latitude\n"
        "product = OptiPlex\n"
    )
    scalar = base / "scalar"
    scalar.mkdir()
    (scalar / "match.conf").write_text("match = scalar\n")

    assert [profile["name"] for profile in manager.list_profiles()] == ["valid"]


def test_scalar_match_value_is_reported_as_invalid_configuration(tmp_path):
    base = tmp_path / "drivers"
    profile = base / "scalar"
    profile.mkdir(parents=True)
    (profile / "match.conf").write_text("match = scalar\n")
    manager = LinboDriverManager(base)

    with pytest.raises(ValueError, match=r"\[match\] must contain"):
        manager.get_profile("scalar")


@pytest.mark.parametrize(
    "content",
    [
        "[match] # note\nvendor = Dell\nproduct = Latitude\n",
        "[match]\nvendor = Dell # note\nproduct = Latitude\n",
    ],
)
def test_inline_comments_are_rejected_to_match_linbo_semantics(tmp_path, content):
    base = tmp_path / "drivers"
    profile = base / "commented"
    profile.mkdir(parents=True)
    (profile / "match.conf").write_text(content)
    manager = LinboDriverManager(base)

    with pytest.raises(ValueError, match="must not contain inline comments"):
        manager.get_profile("commented")


def test_profile_directory_symlink_is_not_followed(tmp_path):
    base = tmp_path / "drivers"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "match.conf").write_text(
        "[match]\nvendor = Dell\nproduct = Latitude\n"
    )
    base.mkdir()
    (base / "linked").symlink_to(outside, target_is_directory=True)
    manager = LinboDriverManager(base)

    with pytest.raises(ValueError, match="not a real directory"):
        manager.get_profile("linked")
    assert manager.list_profiles() == []
    assert outside.exists()


def test_match_conf_symlink_is_not_followed(tmp_path):
    base = tmp_path / "drivers"
    outside = tmp_path / "outside.conf"
    outside.write_text("[match]\nvendor = Dell\nproduct = Latitude\n")
    profile = base / "linked-match"
    profile.mkdir(parents=True)
    (profile / "match.conf").symlink_to(outside)
    manager = LinboDriverManager(base)

    with pytest.raises(ValueError, match="not a regular file"):
        manager.get_profile("linked-match")
    assert outside.read_text().startswith("[match]")


def test_driver_base_symlink_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_base = tmp_path / "drivers"
    linked_base.symlink_to(outside, target_is_directory=True)
    manager = LinboDriverManager(linked_base)

    with pytest.raises(ValueError, match="base is not a real directory"):
        manager.list_profiles()
    with pytest.raises(ValueError, match="base is not a real directory"):
        manager.get_profile("profile")
    with pytest.raises(ValueError, match="base is not a real directory"):
        manager.create_profile("profile", "Dell", "Latitude")
    assert list(outside.iterdir()) == []


def test_delete_profile_is_idempotent(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)
    manager.create_profile("delete-me", "Dell", "Latitude")
    (base / "delete-me/driver.inf").write_bytes(b"payload")

    assert manager.delete_profile("delete-me") is True
    assert manager.delete_profile("delete-me") is False
    assert not (base / "delete-me").exists()


def test_delete_refuses_unmanaged_directory(tmp_path):
    base = tmp_path / "drivers"
    unmanaged = base / "unmanaged"
    unmanaged.mkdir(parents=True)
    important = unmanaged / "important.txt"
    important.write_text("keep")
    manager = LinboDriverManager(base)

    with pytest.raises(ValueError, match="has no match.conf"):
        manager.delete_profile("unmanaged")

    assert important.read_text() == "keep"


def test_failed_delete_restores_the_profile(tmp_path, monkeypatch):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)
    manager.create_profile("keep-me", "Dell", "Latitude")

    def fail_delete(_path):
        raise OSError("simulated delete failure")

    monkeypatch.setattr(drivers_module.shutil, "rmtree", fail_delete)

    with pytest.raises(OSError, match="simulated delete failure"):
        manager.delete_profile("keep-me")

    assert manager.get_profile("keep-me")["name"] == "keep-me"
    assert not list(base.glob(".keep-me.deleting-*"))


def test_default_profile_base_is_srv_linbo():
    assert LinboDriverManager().base == Path("/srv/linbo/drivers")


def test_create_sets_profile_directory_mode(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)

    manager.create_profile("profile", "Dell", "Latitude")

    assert os.stat(base / "profile").st_mode & 0o777 == 0o755


def test_update_preserves_existing_match_conf_mode(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)
    manager.create_profile("profile", "Dell", "Latitude")
    match_conf = base / "profile/match.conf"
    match_conf.chmod(0o640)

    manager.update_match("profile", "Dell", "OptiPlex")

    assert match_conf.stat().st_mode & 0o777 == 0o640


def test_mutations_refuse_a_symlink_lock_file(tmp_path):
    base = tmp_path / "drivers"
    base.mkdir()
    outside = tmp_path / "outside.lock"
    outside.write_text("keep")
    (base / ".driver-profiles.lock").symlink_to(outside)
    manager = LinboDriverManager(base)

    with pytest.raises(OSError):
        manager.create_profile("profile", "Dell", "Latitude")

    assert outside.read_text() == "keep"
    assert not (base / "profile").exists()
