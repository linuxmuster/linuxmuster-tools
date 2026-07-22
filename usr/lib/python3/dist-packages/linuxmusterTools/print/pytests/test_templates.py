"""
Tests for GLOBAL_FILENAME_REGEX matching, LatexTemplate.__post_init__ casting,
and LatexTemplates' glob-based template discovery (LDAP schools list mocked).
"""

import re

import pytest

from linuxmusterTools.print.templates import (
    GLOBAL_FILENAME_REGEX,
    LatexTemplate,
    LatexTemplates,
)


# ── GLOBAL_FILENAME_REGEX ────────────────────────────────────────────────────

@pytest.mark.parametrize("filename,expected", [
    ("passwords-DE-1-template.tex", {"type": "passwords", "lang": "DE", "count": "1"}),
    ("passwords-EN-36-template.tex", {"type": "passwords", "lang": "EN", "count": "36"}),
    ("schoolclass-DE-32-template.tex", {"type": "schoolclass", "lang": "DE", "count": "32"}),
    ("schoolclass-FR-32-template.tex", {"type": "schoolclass", "lang": "FR", "count": "32"}),
    ("datalist-DE-1-template.tex", {"type": "datalist", "lang": "DE", "count": "1"}),
])
def test_regex_matches_valid_filenames(filename, expected):
    match = re.match(GLOBAL_FILENAME_REGEX, filename)
    assert match is not None
    assert match.groupdict() == expected


@pytest.mark.parametrize("filename", [
    "passwords-de-1-template.tex",       # lowercase lang
    "passwords-DE-x-template.tex",        # non-digit count
    "randomfile.tex",                     # no structure at all
    "passwords-DE-1-templates.tex",       # misspelled suffix
    "schoolclass_DE_32_template.tex",     # underscores instead of hyphens
    "passwords-DE-1-template.txt",        # wrong extension
])
def test_regex_rejects_invalid_filenames(filename):
    assert re.match(GLOBAL_FILENAME_REGEX, filename) is None


# ── LatexTemplate.__post_init__ ──────────────────────────────────────────────

def make_template(**overrides):
    defaults = dict(
        count="5", filename="f.tex", fullpath="/tmp/f.tex",
        lang="DE", package="lmntools", school="global", type="passwords",
    )
    defaults.update(overrides)
    return LatexTemplate(**defaults)


def test_post_init_casts_count_string_to_int():
    t = make_template(count="12")
    assert t.count == 12
    assert isinstance(t.count, int)


def test_post_init_accepts_int_count_unchanged():
    t = make_template(count=7)
    assert t.count == 7


def test_post_init_datalist_type_becomes_passwords():
    t = make_template(type="datalist")
    assert t.type == "passwords"


def test_post_init_other_types_unchanged():
    t = make_template(type="schoolclass")
    assert t.type == "schoolclass"


# ── LatexTemplates.load() ────────────────────────────────────────────────────

def write_tex(directory, filename, content="dummy"):
    (directory / filename).write_text(content, encoding="utf-8")


def test_load_discovers_lmntools_templates(templates_dirs, monkeypatch):
    lmntools_dir, sophomorix_dir, config_dir = templates_dirs
    write_tex(lmntools_dir, "passwords-DE-1-template.tex")
    write_tex(lmntools_dir, "not-a-template.tex")  # should be ignored

    import linuxmusterTools.print.templates as templates_module
    monkeypatch.setattr(templates_module.lr, "getval", lambda url, attribute, **kwargs: [])

    templates = LatexTemplates().templates

    assert "passwords-DE-1-template.tex" in templates
    assert "not-a-template.tex" not in templates
    t = templates["passwords-DE-1-template.tex"]
    assert t.package == "lmntools"
    assert t.school == "global"
    assert t.lang == "DE"
    assert t.count == 1
    assert t.type == "passwords"


def test_load_discovers_sophomorix_templates(templates_dirs, monkeypatch):
    lmntools_dir, sophomorix_dir, config_dir = templates_dirs
    write_tex(sophomorix_dir, "schoolclass-FR-32-template.tex")

    import linuxmusterTools.print.templates as templates_module
    monkeypatch.setattr(templates_module.lr, "getval", lambda url, attribute, **kwargs: [])

    templates = LatexTemplates().templates

    assert "schoolclass-FR-32-template.tex" in templates
    t = templates["schoolclass-FR-32-template.tex"]
    assert t.package == "sophomorix"
    assert t.school == "global"
    assert t.count == 32


def test_load_ignores_non_matching_filenames(templates_dirs, monkeypatch):
    lmntools_dir, sophomorix_dir, config_dir = templates_dirs
    write_tex(lmntools_dir, "garbage.tex")
    write_tex(sophomorix_dir, "also-garbage.txt")

    import linuxmusterTools.print.templates as templates_module
    monkeypatch.setattr(templates_module.lr, "getval", lambda url, attribute, **kwargs: [])

    templates = LatexTemplates().templates
    assert templates == {}


def test_load_queries_schools_via_lr_getval(templates_dirs, monkeypatch):
    import linuxmusterTools.print.templates as templates_module
    calls = []

    def fake_getval(url, attribute, **kwargs):
        calls.append((url, attribute))
        return []

    monkeypatch.setattr(templates_module.lr, "getval", fake_getval)
    LatexTemplates()

    assert ("/schools", "ou") in calls


def test_load_discovers_school_specific_templates(templates_dirs, monkeypatch):
    lmntools_dir, sophomorix_dir, config_dir = templates_dirs
    import linuxmusterTools.print.templates as templates_module

    monkeypatch.setattr(
        templates_module.lr, "getval",
        lambda url, attribute, **kwargs: ["default-school"],
    )

    school_dir = config_dir / "default-school" / "latex-templates"
    school_dir.mkdir(parents=True)
    write_tex(school_dir, "default-school.passwords-DE-1-template.tex")
    write_tex(school_dir, "unrelated-file.tex")  # doesn't match school prefix regex

    templates = LatexTemplates().templates

    key = "default-school.passwords-DE-1-template.tex"
    assert key in templates
    t = templates[key]
    assert t.package == "school defined"
    assert t.school == "default-school"
    assert t.type == "passwords"
    assert t.lang == "DE"
    assert t.count == 1
    assert "unrelated-file.tex" not in templates


def test_load_school_templates_only_for_matching_school(templates_dirs, monkeypatch):
    """
    A school-specific templates directory for a school not returned by
    lr.getval('/schools', 'ou') should never be scanned/matched.
    """
    lmntools_dir, sophomorix_dir, config_dir = templates_dirs
    import linuxmusterTools.print.templates as templates_module

    monkeypatch.setattr(
        templates_module.lr, "getval",
        lambda url, attribute, **kwargs: ["school-a"],
    )

    other_dir = config_dir / "school-b" / "latex-templates"
    other_dir.mkdir(parents=True)
    write_tex(other_dir, "school-b.passwords-DE-1-template.tex")

    templates = LatexTemplates().templates
    assert templates == {}


def test_str_includes_header_and_template_rows(templates_dirs, monkeypatch):
    lmntools_dir, sophomorix_dir, config_dir = templates_dirs
    import linuxmusterTools.print.templates as templates_module

    write_tex(lmntools_dir, "passwords-DE-1-template.tex")
    monkeypatch.setattr(templates_module.lr, "getval", lambda url, attribute, **kwargs: [])

    output = str(LatexTemplates())
    assert "Filename" in output
    assert "passwords-DE-1-template.tex" in output
