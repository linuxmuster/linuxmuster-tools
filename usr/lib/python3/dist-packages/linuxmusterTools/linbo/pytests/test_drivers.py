import importlib
import re
from pathlib import Path

import pytest

from linuxmusterTools.linbo.driver_matching import MatchConfigError
from linuxmusterTools.linbo.driver_storage import StorageSecurityError
import linuxmusterTools.linbo.drivers as drivers_module
from linuxmusterTools.linbo.drivers import LinboDriverManager


def test_public_package_exports_driver_manager():
    import linuxmusterTools.linbo as linbo_package
    from linuxmusterTools.linbo import (
        DriverHookOwnershipError,
        DriverHookTransactionError,
        DriverImageAssignedError,
        LinboDriverManager as PublicDriverManager,
        StorageSecurityError as PublicStorageSecurityError,
    )
    from linuxmusterTools.linbo.driver_hooks import (
        DriverHookOwnershipError as InternalOwnershipError,
        DriverHookTransactionError as InternalTransactionError,
        DriverImageAssignedError as InternalAssignedError,
    )

    assert PublicDriverManager is LinboDriverManager
    assert DriverHookOwnershipError is InternalOwnershipError
    assert DriverHookTransactionError is InternalTransactionError
    assert DriverImageAssignedError is InternalAssignedError
    assert PublicStorageSecurityError is StorageSecurityError
    assert not hasattr(linbo_package, "LinboDriverHookManager")
    assert not hasattr(linbo_package, "validate_image_name")


def test_list_profiles_is_empty_when_base_does_not_exist(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")
    assert manager.list_profiles() == []


def test_create_profile_writes_canonical_match_atomically(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)

    profile = manager.create_profile("Dell-5520", "Dell Inc.", ["Latitude 5520"])

    match_path = base / "Dell-5520" / "match.conf"
    assert match_path.read_text(encoding="utf-8") == (
        "[match]\n"
        "vendor = Dell Inc.\n"
        "product = Latitude 5520\n"
    )
    assert match_path.stat().st_mode & 0o777 == 0o644
    assert profile["name"] == "Dell-5520"
    assert profile["matchConf"] == {
        "vendor": "Dell Inc.",
        "products": ["Latitude 5520"],
        "schema": "canonical",
    }
    assert profile["files"] == []
    assert profile["totalSize"] == 0
    assert profile["image"] is None


def test_create_never_overwrites_existing_profile(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")
    manager.create_profile("Existing", "Original", ["*"])

    with pytest.raises(drivers_module.DriverProfileExistsError) as error:
        manager.create_profile("Existing", "Replacement", ["*"])

    assert isinstance(error.value, drivers_module.DriverProfileConflictError)
    assert isinstance(error.value, FileExistsError)
    assert error.value.profile == "Existing"
    assert manager.get_profile("Existing")["matchConf"]["vendor"] == "Original"


def test_create_rejects_case_insensitive_windows_profile_collision(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")
    manager.create_profile("ModelA", "Original", ["*"])

    with pytest.raises(drivers_module.DriverProfileExistsError):
        manager.create_profile("modela", "Other", ["*"])

    assert manager.get_profile("ModelA")["matchConf"]["vendor"] == "Original"


def test_invalid_create_input_leaves_no_profile(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)

    with pytest.raises(MatchConfigError):
        manager.create_profile("Unsafe", "Dell\nproduct = *")

    assert not (base / "Unsafe").exists()


def test_get_profile_reads_legacy_schema(tmp_path):
    base = tmp_path / "drivers"
    profile_dir = base / "Legacy"
    profile_dir.mkdir(parents=True)
    (profile_dir / "match.conf").write_text(
        "[match]\nsys_vendor = LENOVO\nproduct_name = 21L4\n",
        encoding="utf-8",
    )

    profile = LinboDriverManager(base).get_profile("Legacy")

    assert profile["matchConf"] == {
        "vendor": "LENOVO",
        "products": ["21L4"],
        "schema": "legacy",
    }


def test_list_profiles_skips_incomplete_and_mixed_alias_profiles(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)
    manager.create_profile("Valid", "Dell", ["*"])
    (base / "Incomplete").mkdir()
    mixed = base / "Mixed"
    mixed.mkdir()
    (mixed / "match.conf").write_text(
        "[match]\nsys_vendor = Dell\nproduct = Latitude\n",
        encoding="utf-8",
    )

    assert [profile["name"] for profile in manager.list_profiles()] == ["Valid"]
    with pytest.raises(MatchConfigError, match="must not be mixed"):
        manager.get_profile("Mixed")


def test_update_match_migrates_legacy_profile_to_canonical(tmp_path):
    base = tmp_path / "drivers"
    profile_dir = base / "Legacy"
    profile_dir.mkdir(parents=True)
    (profile_dir / "match.conf").write_text(
        "[match]\nsys_vendor = LENOVO\nproduct_name = Old\n",
        encoding="utf-8",
    )
    manager = LinboDriverManager(base)

    updated = manager.update_match("Legacy", "LENOVO", ["21L4", "21L5"])

    content = (profile_dir / "match.conf").read_text(encoding="utf-8")
    assert "sys_vendor" not in content
    assert "product_name" not in content
    assert content.count("product =") == 2
    assert updated["matchConf"]["schema"] == "canonical"


def test_assigning_legacy_profile_migrates_rule_before_hook_publication(tmp_path):
    drivers_base = tmp_path / "drivers"
    images_base = tmp_path / "images"
    profile = drivers_base / "Legacy"
    image = images_base / "win11"
    profile.mkdir(parents=True)
    image.mkdir(parents=True)
    (profile / "match.conf").write_text(
        "[match]\nsys_vendor = LENOVO\nproduct_name = 21L4\n",
        encoding="utf-8",
    )
    (profile / "driver.inf").write_bytes(b"driver fixture")
    (image / "win11.qcow2").write_bytes(b"qcow")
    manager = LinboDriverManager(drivers_base, images_base=images_base)

    result = manager.set_profile_image("Legacy", "win11")

    assert result == {"folder": "Legacy", "image": "win11"}
    canonical = (profile / "match.conf").read_text(encoding="utf-8")
    assert "vendor = LENOVO" in canonical
    assert "product = 21L4" in canonical
    assert "sys_vendor" not in canonical
    assert "product_name" not in canonical


def test_invalid_image_does_not_mutate_legacy_match_rule(tmp_path):
    drivers_base = tmp_path / "drivers"
    profile = drivers_base / "Legacy"
    profile.mkdir(parents=True)
    legacy = "[match]\nsys_vendor = LENOVO\nproduct_name = 21L4\n"
    match_path = profile / "match.conf"
    match_path.write_text(legacy, encoding="utf-8")
    manager = LinboDriverManager(drivers_base, images_base=tmp_path / "images")

    with pytest.raises(ValueError, match="dots are not supported"):
        manager.set_profile_image("Legacy", "bad.image")

    assert match_path.read_text(encoding="utf-8") == legacy


def test_update_missing_profile_raises_without_creating_it(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)

    with pytest.raises(FileNotFoundError):
        manager.update_match("Missing", "Dell", ["*"])

    assert not (base / "Missing").exists()


def test_get_profile_lists_payload_but_excludes_profile_metadata(tmp_path):
    base = tmp_path / "drivers"
    manager = LinboDriverManager(base)
    manager.create_profile("Payload", "Dell", ["*"])
    payload = base / "Payload" / "Network"
    payload.mkdir()
    (payload / "driver.inf").write_bytes(b"12345")
    (base / "Payload" / "image.conf").write_text(
        "image = test-image\n", encoding="utf-8"
    )

    profile = manager.get_profile("Payload")

    assert profile["files"] == [{"name": "Network/driver.inf", "size": 5}]
    assert profile["totalSize"] == 5
    assert profile["image"] == "test-image"


def test_delete_profile_is_idempotent_for_missing_profile(tmp_path):
    manager = LinboDriverManager(tmp_path / "drivers")

    manager.create_profile("DeleteMe", "Dell", ["*"])
    assert manager.delete_profile("DeleteMe") is True
    assert manager.delete_profile("DeleteMe") is False
    assert manager.get_profile("DeleteMe") is None


def test_delete_refuses_directory_without_valid_ownership_marker(tmp_path):
    base = tmp_path / "drivers"
    arbitrary = base / "Unmanaged"
    arbitrary.mkdir(parents=True)
    (arbitrary / "important.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        LinboDriverManager(base).delete_profile("Unmanaged")

    assert (arbitrary / "important.txt").read_text(encoding="utf-8") == "keep"


def test_profile_symlink_is_never_followed(tmp_path):
    base = tmp_path / "drivers"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "match.conf").write_text(
        "[match]\nvendor = Dell\nproduct = *\n", encoding="utf-8"
    )
    base.mkdir()
    (base / "Linked").symlink_to(outside, target_is_directory=True)
    manager = LinboDriverManager(base)

    assert manager.list_profiles() == []
    with pytest.raises(StorageSecurityError):
        manager.get_profile("Linked")
    assert outside.exists()


def test_default_base_matches_linbo_server_tree():
    manager = LinboDriverManager()
    assert manager.base == Path("/srv/linbo/drivers")
    assert manager.images_base == Path("/srv/linbo/images")


def test_explicit_images_base_is_wired_into_hook_manager(tmp_path):
    manager = LinboDriverManager(
        tmp_path / "drivers",
        images_base=tmp_path / "images",
    )

    assert manager.images_base == tmp_path / "images"
    assert manager.hook_manager.drivers_root == (tmp_path / "drivers").absolute()
    assert manager.hook_manager.images_root == (tmp_path / "images").absolute()
    assert manager.hook_manager.lock_path == (
        tmp_path / "drivers" / ".driver-profiles.lock"
    ).absolute()


def test_default_base_follows_linbo_dir_environment(monkeypatch):
    with monkeypatch.context() as environment:
        environment.setenv("LINBO_DIR", "/custom/linbo")
        environment.delenv("DRIVERS_BASE", raising=False)
        environment.delenv("IMAGE_DIR", raising=False)
        reloaded = importlib.reload(drivers_module)
        manager = reloaded.LinboDriverManager()
        assert manager.base == Path("/custom/linbo/drivers")
        assert manager.images_base == Path("/custom/linbo/images")

    importlib.reload(drivers_module)


def test_drivers_base_environment_overrides_linbo_dir(monkeypatch):
    with monkeypatch.context() as environment:
        environment.setenv("LINBO_DIR", "/custom/linbo")
        environment.setenv("DRIVERS_BASE", "/dedicated/driver-store")
        reloaded = importlib.reload(drivers_module)
        assert reloaded.LinboDriverManager().base == Path("/dedicated/driver-store")

    importlib.reload(drivers_module)


def test_image_dir_environment_overrides_linbo_dir(monkeypatch):
    with monkeypatch.context() as environment:
        environment.setenv("LINBO_DIR", "/custom/linbo")
        environment.setenv("IMAGE_DIR", "/dedicated/image-store")
        reloaded = importlib.reload(drivers_module)
        assert reloaded.LinboDriverManager().images_base == Path(
            "/dedicated/image-store"
        )

    importlib.reload(drivers_module)


def test_hook_facade_delegates_without_changing_return_contract(tmp_path, monkeypatch):
    calls = []

    class FakeHookManager:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def list_available_images(self):
            calls.append(("list",))
            return [{"name": "win11", "filename": "win11.qcow2"}]

        def read_image_conf(self, profile):
            calls.append(("get", profile))
            return "win11"

        def set_profile_image(self, profile, image):
            calls.append(("set", profile, image))
            return {"folder": profile, "image": image}

        def remove_profile_image(self, profile):
            calls.append(("remove", profile))
            return {"folder": profile, "image": None}

        def reconcile_all_postsync(self):
            calls.append(("reconcile",))
            return {"regenerated": ["win11"], "failed": []}

    monkeypatch.setattr(drivers_module, "LinboDriverHookManager", FakeHookManager)
    profile = tmp_path / "drivers" / "Dell"
    profile.mkdir(parents=True)
    (profile / "match.conf").write_text(
        "[match]\nvendor = Dell\nproduct = *\n", encoding="utf-8"
    )
    manager = drivers_module.LinboDriverManager(
        tmp_path / "drivers",
        images_base=tmp_path / "images",
    )

    assert calls[0] == (
        "init",
        {
            "drivers_root": tmp_path / "drivers",
            "images_root": tmp_path / "images",
            "lock_path": tmp_path / "drivers" / ".driver-profiles.lock",
        },
    )
    assert manager.list_available_images() == [
        {"name": "win11", "filename": "win11.qcow2"}
    ]
    assert manager.get_profile_image("Dell") == "win11"
    assert manager.set_profile_image("Dell", "win11") == {
        "folder": "Dell",
        "image": "win11",
    }
    assert manager.remove_profile_image("Dell") == {
        "folder": "Dell",
        "image": None,
    }
    assert manager.reconcile_driver_hooks() == {
        "regenerated": ["win11"],
        "failed": [],
    }
    assert calls[1:] == [
        ("list",),
        ("get", "Dell"),
        ("set", "Dell", "win11"),
        ("remove", "Dell"),
        ("reconcile",),
    ]


def test_assigned_profile_must_be_unassigned_before_delete(tmp_path):
    drivers_base = tmp_path / "drivers"
    images_base = tmp_path / "images"
    image_directory = images_base / "win11"
    image_directory.mkdir(parents=True)
    (image_directory / "win11.qcow2").write_bytes(b"qcow2")
    manager = drivers_module.LinboDriverManager(
        drivers_base,
        images_base=images_base,
    )
    manager.create_profile("Dell", "Dell Inc.", ["Latitude 5520"])
    (drivers_base / "Dell/driver.inf").write_bytes(b"driver fixture")

    assert manager.list_available_images() == [
        {"name": "win11", "filename": "win11.qcow2"}
    ]
    assert manager.set_profile_image("Dell", "win11") == {
        "folder": "Dell",
        "image": "win11",
    }
    assert manager.get_profile("Dell")["image"] == "win11"
    assert manager.get_profile("Dell")["files"] == [
        {"name": "driver.inf", "size": len(b"driver fixture")}
    ]

    with pytest.raises(drivers_module.DriverProfileAssignedError) as error:
        manager.delete_profile("Dell")

    assert isinstance(error.value, drivers_module.DriverProfileConflictError)
    assert isinstance(error.value, FileExistsError)
    assert error.value.profile == "Dell"
    assert error.value.image == "win11"
    assert manager.get_profile("Dell")["image"] == "win11"

    assert manager.remove_profile_image("Dell") == {
        "folder": "Dell",
        "image": None,
    }
    hook = image_directory / "win11.driverpostsync"
    assert "cleanup tombstone" in hook.read_text(encoding="utf-8")
    assert manager.delete_profile("Dell") is True


def test_inventory_facade_forwards_constructor_and_call_parameters(tmp_path, monkeypatch):
    list_calls = []
    get_calls = []
    inventory = {
        "hostname": "Client-A",
        "dmi": {"vendor": "Dell", "product": "5520"},
    }

    def fake_list_server_hardware(**kwargs):
        list_calls.append(kwargs)
        return [inventory]

    def fake_get_server_hardware(hostname, **kwargs):
        get_calls.append((hostname, kwargs))
        return inventory

    monkeypatch.setattr(drivers_module, "list_server_hardware", fake_list_server_hardware)
    monkeypatch.setattr(drivers_module, "get_server_hardware", fake_get_server_hardware)
    manager = drivers_module.LinboDriverManager(
        tmp_path / "drivers",
        hwinfo_dir=tmp_path / "hwinfo",
        stale_hours="12.5",
    )

    assert manager.list_inventory() == [
        {"hostname": "Client-A", "dmi": {"vendor": "Dell", "product": "5520"}}
    ]
    assert list_calls[-1] == {
        "hwinfo_dir": tmp_path / "hwinfo",
        "school": "default-school",
        "stale_hours": "12.5",
        "include_devices": False,
    }

    assert manager.get_inventory("client-a", include_devices=True)["hostname"] == "Client-A"
    assert get_calls[-1] == (
        "client-a",
        {
            "hwinfo_dir": tmp_path / "hwinfo",
            "school": "default-school",
            "stale_hours": "12.5",
            "include_devices": True,
        },
    )


def test_inventory_lookup_delegates_single_hostname(monkeypatch):
    calls = []
    monkeypatch.setattr(
        drivers_module,
        "get_server_hardware",
        lambda hostname, **kwargs: calls.append((hostname, kwargs))
        or {"hostname": "Client"},
    )
    manager = drivers_module.LinboDriverManager()

    assert manager.get_inventory("client")["hostname"] == "Client"
    assert calls[-1][0] == "client"


def test_inventory_facade_forwards_school_and_accepts_school_local_hostname(
    tmp_path,
    monkeypatch,
):
    calls = []
    inventory = {
        "hostname": "school-b-Client-A",
        "deviceHostname": "Client-A",
        "school": "school-b",
        "dmi": {"vendor": "Dell", "product": "Latitude 5520"},
    }
    monkeypatch.setattr(
        drivers_module,
        "get_server_hardware",
        lambda hostname, **kwargs: calls.append((hostname, kwargs)) or inventory,
    )
    manager = drivers_module.LinboDriverManager(tmp_path / "drivers")

    assert manager.get_inventory("client-a", school="school-b") == inventory
    assert calls[-1][1]["school"] == "school-b"

    created = manager.create_profile_from_inventory(
        "Client-A",
        school="school-b",
    )
    assert created["matchConf"]["products"] == ["Latitude 5520"]
    assert calls[-1][1]["school"] == "school-b"


def test_inventory_facade_rejects_unsafe_school_before_listing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        drivers_module,
        "list_server_hardware",
        lambda **_kwargs: pytest.fail("unsafe school reached inventory reader"),
    )
    manager = drivers_module.LinboDriverManager(tmp_path / "drivers")

    with pytest.raises(ValueError, match="school"):
        manager.list_inventory(school="../school")


def test_profile_name_suggestions_are_safe_and_deterministic():
    first = drivers_module.LinboDriverManager.suggest_profile_names(
        "Acme+", "Model #1"
    )
    second = drivers_module.LinboDriverManager.suggest_profile_names(
        "Acme+", "Model #1"
    )
    punctuation_only = drivers_module.LinboDriverManager.suggest_profile_names(
        "+++", "###"
    )

    assert first == second
    assert first["preferred"] == "Acme_Model_1"
    assert re.fullmatch(r"Acme_Model_1-[0-9a-f]{64}", first["fallback"])
    assert len(first["fallback"]) <= 100
    assert punctuation_only["preferred"] is None
    assert re.fullmatch(r"profile-[0-9a-f]{64}", punctuation_only["fallback"])


def test_create_from_inventory_uses_hash_fallback_on_readable_slug_collision(
    tmp_path,
    monkeypatch,
):
    inventory = {
        "hostname": "Client-A",
        "dmi": {"vendor": "Acme#", "product": "Model +1"},
    }
    monkeypatch.setattr(
        drivers_module,
        "get_server_hardware",
        lambda _hostname, **_kwargs: inventory,
    )
    manager = drivers_module.LinboDriverManager(tmp_path / "drivers")
    suggestions = manager.suggest_profile_names("Acme#", "Model +1")
    manager.create_profile(suggestions["preferred"], "Different", ["Hardware"])

    created = manager.create_profile_from_inventory("client-a")
    repeated = manager.create_profile_from_inventory("CLIENT-A")

    assert created["name"] == suggestions["fallback"]
    assert repeated["name"] == created["name"]
    assert created["matchConf"]["vendor"] == "Acme#"
    assert created["matchConf"]["products"] == ["Model +1"]


def test_create_from_inventory_honors_explicit_profile_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        drivers_module,
        "get_server_hardware",
        lambda _hostname, **_kwargs: {
            "hostname": "Client-A",
            "dmi": {"vendor": "Dell Inc.", "product": "Latitude 5520"},
        },
    )
    manager = drivers_module.LinboDriverManager(tmp_path / "drivers")

    created = manager.create_profile_from_inventory("CLIENT-a", name="Room1-Dell")

    assert created["name"] == "Room1-Dell"
    with pytest.raises(drivers_module.DriverProfileExistsError):
        manager.create_profile_from_inventory("client-a", name="Room1-Dell")


@pytest.mark.parametrize(
    "dmi",
    [None, {}, {"vendor": None, "product": "Model"}, {"vendor": "Dell", "product": None}],
)
def test_create_from_inventory_rejects_missing_dmi_fields(tmp_path, monkeypatch, dmi):
    monkeypatch.setattr(
        drivers_module,
        "get_server_hardware",
        lambda _hostname, **_kwargs: {"hostname": "client", "dmi": dmi},
    )
    manager = drivers_module.LinboDriverManager(tmp_path / "drivers")

    with pytest.raises(ValueError, match="DMI"):
        manager.create_profile_from_inventory("client")

    assert manager.list_profiles() == []


def test_create_from_inventory_raises_when_host_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(
        drivers_module,
        "get_server_hardware",
        lambda _hostname, **_kwargs: None,
    )
    manager = drivers_module.LinboDriverManager(tmp_path / "drivers")

    with pytest.raises(drivers_module.DriverInventoryNotFoundError) as error:
        manager.create_profile_from_inventory("missing", school="school-a")

    assert isinstance(error.value, FileNotFoundError)
    assert error.value.school == "school-a"
    assert error.value.hostname == "missing"
    assert str(error.value) == "hardware inventory not found: school-a/missing"
