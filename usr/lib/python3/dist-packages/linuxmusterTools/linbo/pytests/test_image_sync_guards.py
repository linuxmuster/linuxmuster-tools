"""
Tests for the path guards of the image serving helpers.

Each of these takes an image name straight from an API path parameter and
builds a filesystem path from it, so a name that escapes the images
directory has to be refused before any file operation happens. ".." alone is
enough: it is a valid single URL segment, and images_dir/.incoming/.. is the
images directory itself.
"""

import pytest

from linuxmusterTools.linbo.image_sync import (
    cancel_upload,
    finalize_upload,
    get_upload_status,
    resolve_image_file,
)


ESCAPING_NAMES = ["..", "../..", "../../etc", "a/b", "a\\b", "", None]


@pytest.fixture
def images_dir(tmp_path):
    """An images directory holding one staged upload and one neighbour."""

    (tmp_path / ".incoming" / "ubuntu22.qcow2").mkdir(parents=True)
    (tmp_path / "keep_me").mkdir()
    return tmp_path


@pytest.mark.parametrize("name", ESCAPING_NAMES)
def test_cancel_upload_refuses_an_escaping_name(images_dir, name):
    with pytest.raises(ValueError):
        cancel_upload(images_dir, name)
    assert images_dir.is_dir()
    assert (images_dir / "keep_me").is_dir()
    assert (images_dir / ".incoming" / "ubuntu22.qcow2").is_dir()


@pytest.mark.parametrize("name", ESCAPING_NAMES)
def test_finalize_upload_refuses_an_escaping_name(images_dir, name):
    with pytest.raises(ValueError):
        finalize_upload(images_dir, name)
    assert (images_dir / "keep_me").is_dir()


@pytest.mark.parametrize("name", ESCAPING_NAMES)
def test_get_upload_status_refuses_an_escaping_name(images_dir, name):
    with pytest.raises(ValueError):
        get_upload_status(images_dir, name, "ubuntu22.qcow2")


@pytest.mark.parametrize("name", ESCAPING_NAMES)
def test_resolve_image_file_refuses_an_escaping_name(images_dir, name):
    with pytest.raises(ValueError):
        resolve_image_file(images_dir, name, "ubuntu22.qcow2")


@pytest.mark.parametrize("name", ESCAPING_NAMES)
def test_resolve_image_file_refuses_an_escaping_filename(images_dir, name):
    with pytest.raises(ValueError):
        resolve_image_file(images_dir, "ubuntu22.qcow2", name)


def test_cancel_upload_still_cleans_a_valid_staged_upload(images_dir):
    assert cancel_upload(images_dir, "ubuntu22.qcow2") == {"cleaned": True}
    assert not (images_dir / ".incoming" / "ubuntu22.qcow2").exists()
    assert (images_dir / "keep_me").is_dir()


def test_cancel_upload_reports_nothing_to_clean(images_dir):
    result = cancel_upload(images_dir, "never-uploaded.qcow2")
    assert result["cleaned"] is False
