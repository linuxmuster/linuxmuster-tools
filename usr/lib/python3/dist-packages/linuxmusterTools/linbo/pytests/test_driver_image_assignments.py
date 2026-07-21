import subprocess
from pathlib import Path

import pytest

import linuxmusterTools.linbo.images as images_module
from linuxmusterTools.linbo.drivers import LinboDriverManager
from linuxmusterTools.linbo.images import LinboImageManager


@pytest.fixture
def environment(tmp_path, monkeypatch):
    images_root = tmp_path / "images"
    images_root.mkdir()
    drivers = LinboDriverManager(tmp_path / "drivers")
    monkeypatch.setattr(images_module, "LINBO_PATH", str(images_root))
    return drivers, LinboImageManager(driver_manager=drivers)


def _profile(drivers, name="model"):
    return drivers.create_profile(name, "Vendor", "Product")


def _image_conf(profile):
    return Path(profile["path"]) / "image.conf"


def _known_image(images, name):
    images.groups[name] = object()


def test_manager_uses_injected_driver_manager(environment):
    drivers, images = environment

    assert images.driver_manager is drivers


def test_profile_without_assignment_returns_none(environment):
    drivers, images = environment
    _profile(drivers)

    assert images.get_driver_profile_image("model") is None


@pytest.mark.parametrize("image", ["win11", "0012", "yes", "no"])
def test_canonical_assignment_preserves_exact_string(environment, image):
    drivers, images = environment
    profile = _profile(drivers)
    image_conf = _image_conf(profile)
    content = f"[image]\nname = {image}\n"
    image_conf.write_text(content)

    assert images.get_driver_profile_image("model") == image
    assert image_conf.read_text() == content


def test_legacy_flat_assignment_remains_readable(environment):
    drivers, images = environment
    profile = _profile(drivers)
    image_conf = _image_conf(profile)
    content = "# Legacy standalone assignment\nimage = win11\n"
    image_conf.write_text(content)

    assert images.get_driver_profile_image("model") == "win11"
    assert image_conf.read_text() == content


def test_missing_profile_is_reported(environment):
    _, images = environment

    with pytest.raises(FileNotFoundError, match="missing"):
        images.get_driver_profile_image("missing")


@pytest.mark.parametrize(
    "content",
    [
        "image = win11\nextra = value\n",
        "[image]\nname = win11\nextra = value\n",
        "[image] # comment\nname = win11\n",
        "[image]\nname = win11 # comment\n",
        "[image]\n",
        "[image\nname = win11\n",
        "[other]\nname = win11\n",
        "[image]\nname = win.11\n",
        f"[image]\nname = {'a' * 101}\n",
    ],
)
def test_malformed_or_unsupported_assignment_is_rejected(environment, content):
    drivers, images = environment
    profile = _profile(drivers)
    _image_conf(profile).write_text(content)

    with pytest.raises(ValueError):
        images.get_driver_profile_image("model")


def test_symlink_image_conf_is_not_followed(environment, tmp_path):
    drivers, images = environment
    profile = _profile(drivers)
    outside = tmp_path / "outside.conf"
    outside.write_text("[image]\nname = win11\n")
    _image_conf(profile).symlink_to(outside)

    with pytest.raises(ValueError, match="not a regular file"):
        images.get_driver_profile_image("model")

    assert outside.read_text() == "[image]\nname = win11\n"


def test_directory_image_conf_is_rejected(environment):
    drivers, images = environment
    profile = _profile(drivers)
    _image_conf(profile).mkdir()

    with pytest.raises(ValueError, match="not a regular file"):
        images.get_driver_profile_image("model")


@pytest.mark.parametrize("image", ["win11", "0012", "yes", "no"])
def test_assign_writes_canonical_image_conf(environment, image):
    drivers, images = environment
    profile = _profile(drivers)
    _known_image(images, image)

    assert images.assign_driver_profile("model", image) == {
        "profile": "model",
        "image": image,
    }
    assert _image_conf(profile).read_text() == f"[image]\nname = {image}\n"
    assert _image_conf(profile).stat().st_mode & 0o777 == 0o644
    assert images.get_driver_profile_image("model") == image


def test_assign_canonicalizes_legacy_assignment(environment):
    drivers, images = environment
    profile = _profile(drivers)
    image_conf = _image_conf(profile)
    image_conf.write_text("# Standalone format\nimage = old\n")
    _known_image(images, "win11")

    images.assign_driver_profile("model", "win11")

    assert image_conf.read_text() == (
        "# Standalone format\n[image]\nname = win11\n"
    )


def test_reassign_preserves_mode_and_driver_payload(environment):
    drivers, images = environment
    profile = _profile(drivers)
    image_conf = _image_conf(profile)
    image_conf.write_text("[image]\nname = old\n")
    image_conf.chmod(0o640)
    payload = Path(profile["path"], "Network", "driver.inf")
    payload.parent.mkdir()
    payload.write_bytes(b"driver payload")
    _known_image(images, "win11")

    images.assign_driver_profile("model", "win11")

    assert image_conf.read_text() == "[image]\nname = win11\n"
    assert image_conf.stat().st_mode & 0o777 == 0o640
    assert payload.read_bytes() == b"driver payload"


def test_missing_profile_or_image_does_not_create_assignment(environment):
    drivers, images = environment
    _known_image(images, "win11")

    with pytest.raises(FileNotFoundError, match="missing"):
        images.assign_driver_profile("missing", "win11")
    assert not drivers.base.exists()

    profile = _profile(drivers)
    with pytest.raises(FileNotFoundError, match="missing"):
        images.assign_driver_profile("model", "missing")

    assert not _image_conf(profile).exists()


def test_missing_target_image_preserves_existing_assignment(environment):
    drivers, images = environment
    profile = _profile(drivers)
    image_conf = _image_conf(profile)
    content = "[image]\nname = old\n"
    image_conf.write_text(content)

    with pytest.raises(FileNotFoundError, match="missing"):
        images.assign_driver_profile("model", "missing")

    assert image_conf.read_text() == content


@pytest.mark.parametrize("image", ["win.11", "a" * 101, None])
def test_assign_rejects_unsupported_image_name(environment, image):
    drivers, images = environment
    profile = _profile(drivers)
    _known_image(images, image)

    with pytest.raises(ValueError):
        images.assign_driver_profile("model", image)

    assert not _image_conf(profile).exists()


def test_assign_does_not_replace_malformed_image_conf(environment):
    drivers, images = environment
    profile = _profile(drivers)
    image_conf = _image_conf(profile)
    content = "[image]\nname = old\nextra = value\n"
    image_conf.write_text(content)
    _known_image(images, "win11")

    with pytest.raises(ValueError):
        images.assign_driver_profile("model", "win11")
    with pytest.raises(ValueError):
        images.unassign_driver_profile("model")

    assert image_conf.read_text() == content


def test_assign_does_not_follow_image_conf_symlink(
    environment, tmp_path
):
    drivers, images = environment
    profile = _profile(drivers)
    outside = tmp_path / "outside.conf"
    outside.write_text("[image]\nname = old\n")
    _image_conf(profile).symlink_to(outside)
    _known_image(images, "win11")

    with pytest.raises(ValueError, match="not a regular file"):
        images.assign_driver_profile("model", "win11")
    with pytest.raises(ValueError, match="not a regular file"):
        images.unassign_driver_profile("model")

    assert _image_conf(profile).is_symlink()
    assert outside.read_text() == "[image]\nname = old\n"


def test_unassign_removes_only_assignment_and_is_idempotent(environment):
    drivers, images = environment
    profile = _profile(drivers)
    image_conf = _image_conf(profile)
    image_conf.write_text("image = vanished\n")
    payload = Path(profile["path"], "Network", "driver.inf")
    payload.parent.mkdir()
    payload.write_bytes(b"driver payload")

    expected = {"profile": "model", "image": None}
    assert images.unassign_driver_profile("model") == expected
    assert images.unassign_driver_profile("model") == expected

    assert not image_conf.exists()
    assert Path(profile["path"], "match.conf").exists()
    assert payload.read_bytes() == b"driver payload"


def test_unassign_missing_profile_is_reported(environment):
    drivers, images = environment

    with pytest.raises(FileNotFoundError, match="missing"):
        images.unassign_driver_profile("missing")

    assert not drivers.base.exists()


def test_assignment_uses_existing_driver_mutation_lock(
    environment, tmp_path
):
    drivers, images = environment
    profile = _profile(drivers)
    lock = drivers.base / ".driver-profiles.lock"
    lock.unlink()
    outside = tmp_path / "outside.lock"
    outside.write_text("keep")
    lock.symlink_to(outside)
    _known_image(images, "win11")

    with pytest.raises(OSError):
        images.assign_driver_profile("model", "win11")

    assert not _image_conf(profile).exists()
    assert outside.read_text() == "keep"


def test_image_profiles_include_only_assignments_for_requested_image(
    environment,
):
    drivers, images = environment
    _known_image(images, "win11")
    _known_image(images, "other")
    assignments = {
        "Zulu": "[image]\nname = win11\n",
        "alpha": "image = win11\n",
        "Beta": "[image]\nname = win11\n",
        "other-model": "[image]\nname = other\n",
        "unassigned": None,
    }
    for name, content in assignments.items():
        profile = _profile(drivers, name)
        if content is not None:
            _image_conf(profile).write_text(content)

    assert images.get_image_driver_profiles("win11") == [
        "alpha",
        "Beta",
        "Zulu",
    ]
    assert images.get_image_driver_profiles("other") == ["other-model"]


def test_image_profiles_require_an_existing_image(environment):
    drivers, images = environment

    with pytest.raises(FileNotFoundError, match="missing"):
        images.get_image_driver_profiles("missing")

    assert not drivers.base.exists()


def test_invalid_profile_blocks_image_profile_resolution(environment):
    drivers, images = environment
    _known_image(images, "win11")
    drivers.base.mkdir()
    (drivers.base / "incomplete").mkdir()

    with pytest.raises(ValueError, match="has no match.conf"):
        images.get_image_driver_profiles("win11")


def test_invalid_assignment_blocks_image_profile_resolution(environment):
    drivers, images = environment
    _known_image(images, "win11")
    profile = _profile(drivers)
    _image_conf(profile).write_text("[image]\nname = win11\nextra = value\n")

    with pytest.raises(ValueError, match="exactly one name"):
        images.get_image_driver_profiles("win11")


def test_case_colliding_profile_names_are_rejected(environment):
    drivers, images = environment
    _known_image(images, "win11")
    first = _profile(drivers, "Model")
    _image_conf(first).write_text("[image]\nname = win11\n")
    second = drivers.base / "model"
    second.mkdir()
    (second / "match.conf").write_text(
        "[match]\nvendor = Vendor\nproduct = Product\n"
    )
    (second / "image.conf").write_text("[image]\nname = win11\n")

    with pytest.raises(ValueError, match="differ only by case"):
        images.get_image_driver_profiles("win11")


def test_render_driverpostsync_matches_static_runtime_contract(environment):
    drivers, images = environment
    _known_image(images, "win11")
    for name in ("Zulu", "alpha", "Beta"):
        profile = _profile(drivers, name)
        _image_conf(profile).write_text("[image]\nname = win11\n")

    content = images.render_driverpostsync("win11")

    assert content == (
        "#!/bin/sh\n"
        "# Managed-By: linuxmusterTools.linbo.driver_hooks v1\n"
        "# Image: win11\n"
        "# Profiles: alpha, Beta, Zulu\n\n"
        "if ! command -v linbo_driverpostsync >/dev/null 2>&1; then\n"
        '    echo "LINBO driver runtime is missing." >&2\n'
        "    return 1\n"
        "fi\n\n"
        'linbo_driverpostsync "win11" "alpha" "Beta" "Zulu"\n'
        "return $?\n"
    )
    assert subprocess.run(
        ["/bin/sh", "-n"],
        input=content,
        text=True,
        check=False,
    ).returncode == 0


def test_render_driverpostsync_without_profiles_is_a_cleanup_dispatcher(
    environment,
):
    drivers, images = environment
    _known_image(images, "win11")

    content = images.render_driverpostsync("win11")

    assert content == (
        "#!/bin/sh\n"
        "# Managed-By: linuxmusterTools.linbo.driver_hooks v1\n"
        "# Image: win11\n"
        "# Profiles: (none)\n\n"
        "if ! command -v linbo_driverpostsync >/dev/null 2>&1; then\n"
        '    echo "LINBO driver runtime is missing." >&2\n'
        "    return 1\n"
        "fi\n\n"
        'linbo_driverpostsync "win11"\n'
        "return $?\n"
    )
    assert not drivers.base.exists()
