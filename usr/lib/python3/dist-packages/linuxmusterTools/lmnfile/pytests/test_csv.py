"""
Tests for CSVLoader: read, write, fieldnames, BOM, delimiter, comments,
empty lines and HEADER_MARKER.
"""

import os
import pytest
from linuxmusterTools.lmnfile import LMNFile
from linuxmusterTools.lmnfile.lmnfile import BOM_MARKER, EMPTY_LINE_MARKER

FIELDS = ['room', 'hostname', 'mac']


def make_csv(tmp_path, content, binary=False):
    f = tmp_path / 'data.csv'
    if binary:
        f.write_bytes(content)
    else:
        f.write_text(content, encoding='utf-8')
    return f


# ── Fieldnames ────────────────────────────────────────────────────────────────

def test_read_with_explicit_fieldnames(tmp_path):
    f = make_csv(tmp_path, 'room1;pc1;aa:bb:cc\nroom2;pc2;dd:ee:ff\n')
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
    assert len(rows) == 2
    assert rows[0]['room'] == 'room1'
    assert rows[1]['hostname'] == 'pc2'


def test_read_with_header_marker(tmp_path):
    content = '#HEADERS#room;hostname;mac\nroom1;pc1;aa:bb:cc\n'
    f = make_csv(tmp_path, content)
    with LMNFile(str(f), 'r') as lmn:
        rows = lmn.read()
    assert rows[0]['room'] == 'room1'
    assert rows[0]['hostname'] == 'pc1'


def test_header_marker_fieldnames_are_stripped(tmp_path):
    content = '#HEADERS# room ; hostname ; mac \nroom1;pc1;aa:bb:cc\n'
    f = make_csv(tmp_path, content)
    with LMNFile(str(f), 'r') as lmn:
        rows = lmn.read()
    # Keys must not have surrounding spaces
    assert 'room' in rows[0]
    assert ' room ' not in rows[0]
    assert rows[0]['room'] == 'room1'


def test_only_first_header_marker_used(tmp_path):
    content = '#HEADERS#room;hostname;mac\n#HEADERS#other;fields\nroom1;pc1;aa:bb:cc\n'
    f = make_csv(tmp_path, content)
    with LMNFile(str(f), 'r') as lmn:
        rows = lmn.read()
    assert 'room' in rows[0]


# ── Whitespace stripping ───────────────────────────────────────────────────────

def test_leading_trailing_spaces_stripped(tmp_path):
    f = make_csv(tmp_path, ' room1 ; pc1 ; aa:bb:cc \n')
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
    assert rows[0]['room'] == 'room1'
    assert rows[0]['hostname'] == 'pc1'
    assert rows[0]['mac'] == 'aa:bb:cc'


# ── Comments and empty lines ──────────────────────────────────────────────────

def test_comment_lines_preserved_on_write(tmp_path):
    content = '# comment line\nroom1;pc1;aa:bb:cc\n'
    f = make_csv(tmp_path, content)
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
        lmn.write(rows)
    assert '# comment line' in f.read_text()


def test_empty_lines_preserved_on_write(tmp_path):
    content = 'room1;pc1;aa:bb:cc\n\nroom2;pc2;dd:ee:ff\n'
    f = make_csv(tmp_path, content)
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
        lmn.write(rows)
    lines = f.read_text().splitlines()
    assert '' in lines


# ── BOM ───────────────────────────────────────────────────────────────────────

def test_bom_detected(tmp_path):
    f = make_csv(tmp_path, BOM_MARKER + b'room1;pc1;aa:bb:cc\n', binary=True)
    lmn = LMNFile(str(f), 'r', fieldnames=FIELDS)
    assert lmn.has_BOM is True


def test_no_bom_detected_when_absent(tmp_path):
    f = make_csv(tmp_path, 'room1;pc1;aa:bb:cc\n')
    lmn = LMNFile(str(f), 'r', fieldnames=FIELDS)
    assert lmn.has_BOM is False


def test_bom_removed_from_file_on_enter(tmp_path):
    f = make_csv(tmp_path, BOM_MARKER + b'room1;pc1;aa:bb:cc\n', binary=True)
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        lmn.read()
    assert not f.read_bytes().startswith(BOM_MARKER)


def test_bom_file_still_readable_after_fix(tmp_path):
    f = make_csv(tmp_path, BOM_MARKER + b'room1;pc1;aa:bb:cc\n', binary=True)
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
    assert rows[0]['room'] == 'room1'


# ── Write ─────────────────────────────────────────────────────────────────────

def test_write_modifies_field(tmp_path):
    f = make_csv(tmp_path, 'room1;pc1;aa:bb:cc\n')
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
        rows[0]['room'] = 'room2'
        lmn.write(rows)
    assert 'room2' in f.read_text()


def test_write_uses_self_delimiter(tmp_path):
    f = tmp_path / 'data.csv'
    f.write_text('room1,pc1,aa:bb:cc\n', encoding='utf-8')
    with LMNFile(str(f), 'r', delimiter=',', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
        rows[0]['room'] = 'room2'
        lmn.write(rows)
    content = f.read_text()
    # The written file must use comma, not semicolon
    assert ',' in content
    assert 'room2' in content


def test_write_creates_backup_on_change(tmp_path):
    f = make_csv(tmp_path, 'room1;pc1;aa:bb:cc\n')
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
        rows[0]['room'] = 'changed'
        lmn.write(rows)
    backups = [x for x in os.listdir(str(tmp_path)) if x.startswith('.data.csv.bak.')]
    assert len(backups) == 1


def test_write_no_backup_when_unchanged(tmp_path):
    f = make_csv(tmp_path, 'room1;pc1;aa:bb:cc\n')
    with LMNFile(str(f), 'r', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
        lmn.write(rows)
    backups = [x for x in os.listdir(str(tmp_path)) if x.startswith('.data.csv.bak.')]
    assert len(backups) == 0


# ── Delimiter ─────────────────────────────────────────────────────────────────

def test_read_with_custom_delimiter(tmp_path):
    f = tmp_path / 'data.csv'
    f.write_text('room1,pc1,aa:bb:cc\n', encoding='utf-8')
    with LMNFile(str(f), 'r', delimiter=',', fieldnames=FIELDS) as lmn:
        rows = lmn.read()
    assert rows[0]['room'] == 'room1'
    assert rows[0]['hostname'] == 'pc1'
