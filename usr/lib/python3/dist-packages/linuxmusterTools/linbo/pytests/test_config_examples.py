"""
Tests for LinboConfigManager.list_examples() and .read_example(), which read
the ready-made configs shipped in /srv/linbo/examples.
"""

import pytest

from linuxmusterTools.linbo.config import LinboConfigManager


@pytest.fixture
def examples(tmp_path):
    """
    A directory holding the same kinds of files as a real
    /srv/linbo/examples, README included.
    """

    path = tmp_path / 'examples'
    path.mkdir()
    (path / 'start.conf.win10-efi').write_text('[LINBO]\nGroup = win10-efi\n')
    (path / 'start.conf.ubuntu').write_text('[LINBO]\nGroup = ubuntu\n')
    (path / 'win10.image.reg').write_text('Windows Registry Editor Version 5.00\n')
    (path / 'image.postsync').write_text('#!/bin/bash\n')
    (path / 'image.prestart').write_text('#!/bin/bash\n')
    (path / 'README.txt').write_text('Have a look at the examples.\n')
    return path


# ── list_examples ────────────────────────────────────────────────────────────


def test_list_reports_templates_and_sidecars(examples):
    names = [example['name'] for example in LinboConfigManager().list_examples()]

    assert names == [
        'image.postsync',
        'image.prestart',
        'start.conf.ubuntu',
        'start.conf.win10-efi',
        'win10.image.reg',
    ]


def test_list_skips_files_that_are_not_examples(examples):
    names = [example['name'] for example in LinboConfigManager().list_examples()]

    assert 'README.txt' not in names


def test_list_reports_the_kind_of_each_example(examples):
    kinds = {e['name']: e['type'] for e in LinboConfigManager().list_examples()}

    assert kinds['start.conf.ubuntu'] == 'config'
    assert kinds['win10.image.reg'] == 'reg'
    assert kinds['image.postsync'] == 'postsync'
    assert kinds['image.prestart'] == 'prestart'


def test_list_reports_size_and_mtime(examples):
    example = next(
        e for e in LinboConfigManager().list_examples() if e['name'] == 'start.conf.ubuntu'
    )

    assert example['size'] == len('[LINBO]\nGroup = ubuntu\n')
    assert example['updatedAt'] is not None


def test_list_skips_subdirectories(examples):
    (examples / 'start.conf.adirectory').mkdir()

    names = [example['name'] for example in LinboConfigManager().list_examples()]

    assert 'start.conf.adirectory' not in names


def test_list_returns_empty_without_examples_directory(tmp_path):
    """
    A server without that directory must not take the listing down with it.
    """

    assert LinboConfigManager().list_examples() == []


# ── read_example ─────────────────────────────────────────────────────────────


def test_read_returns_the_content(examples):
    assert LinboConfigManager().read_example('start.conf.ubuntu') == '[LINBO]\nGroup = ubuntu\n'


def test_read_rejects_an_unlisted_file(examples):
    """
    README.txt exists in the directory but is not an example: what is not
    listed is not readable either.
    """

    with pytest.raises(FileNotFoundError):
        LinboConfigManager().read_example('README.txt')


def test_read_rejects_a_path(examples, tmp_path):
    (tmp_path / 'start.conf.mygroup').write_text('[LINBO]\nGroup = mygroup\n')

    for name in ('../start.conf.mygroup', 'examples/start.conf.ubuntu', '/etc/passwd'):
        with pytest.raises(FileNotFoundError):
            LinboConfigManager().read_example(name)


def test_read_missing_example_raises_file_not_found(examples):
    with pytest.raises(FileNotFoundError):
        LinboConfigManager().read_example('start.conf.doesnotexist')
