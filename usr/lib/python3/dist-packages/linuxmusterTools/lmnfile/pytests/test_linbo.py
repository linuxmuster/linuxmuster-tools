"""
Tests for LinboLoader: plain-text linbo metadata files.
LinboLoader.__enter__ returns the raw file object, not self.
"""

import pytest
from linuxmusterTools.lmnfile import LMNFile


@pytest.mark.parametrize('ext', ['.desc', '.reg', '.postsync', '.info', '.macct', '.prestart'])
def test_linbo_file_readable(tmp_path, ext):
    f = tmp_path / f'image{ext}'
    f.write_text(f'content for {ext}\n', encoding='utf-8')

    with LMNFile(str(f), 'r') as file_obj:
        text = file_obj.read()

    assert f'content for {ext}' in text


def test_linbo_returns_raw_file_object(tmp_path):
    f = tmp_path / 'image.desc'
    f.write_text('Ubuntu 20.04\n', encoding='utf-8')

    with LMNFile(str(f), 'r') as file_obj:
        # The context variable must be the file object, not a LMNFile instance
        assert hasattr(file_obj, 'read')
        assert callable(file_obj.read)


def test_linbo_multiline_content(tmp_path):
    content = 'line1\nline2\nline3\n'
    f = tmp_path / 'image.desc'
    f.write_text(content, encoding='utf-8')

    with LMNFile(str(f), 'r') as file_obj:
        text = file_obj.read()

    assert text == content


def test_linbo_write_mode(tmp_path):
    f = tmp_path / 'image.desc'
    f.write_text('old content\n', encoding='utf-8')

    with LMNFile(str(f), 'w') as file_obj:
        file_obj.write('new content\n')

    assert f.read_text() == 'new content\n'


def test_linbo_unicode_content(tmp_path):
    f = tmp_path / 'image.desc'
    f.write_text('système linux\n', encoding='utf-8')

    with LMNFile(str(f), 'r') as file_obj:
        text = file_obj.read()

    assert 'système' in text
