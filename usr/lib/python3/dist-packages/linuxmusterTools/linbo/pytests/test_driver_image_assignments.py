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
