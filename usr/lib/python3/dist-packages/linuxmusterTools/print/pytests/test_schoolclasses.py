"""
Tests for print_schoolclass_list orchestration logic. LatexTemplates and
LatexRenderer are mocked entirely; lr.getval/lr.get are mocked per test.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import linuxmusterTools.print.schoolclasses as schoolclasses_module
from linuxmusterTools.print.schoolclasses import print_schoolclass_list


class FakeTemplates:
    """Stand-in for LatexTemplates(), pre-loaded with a fixed templates dict."""

    def __init__(self, templates=None):
        self.templates = templates or {}


def make_fake_templates_factory(templates_dict):
    def factory():
        return FakeTemplates(templates_dict)
    return factory


def test_unknown_template_raises(monkeypatch):
    monkeypatch.setattr(schoolclasses_module, "LatexTemplates", make_fake_templates_factory({}))

    with pytest.raises(Exception, match="Can not find the template"):
        print_schoolclass_list("7a", "admin", template="does-not-exist.tex")


def test_empty_schoolclass_raises(monkeypatch):
    template_obj = SimpleNamespace(filename="schoolclass-DE-32-template.tex", count=32, type="schoolclass")
    monkeypatch.setattr(
        schoolclasses_module, "LatexTemplates",
        make_fake_templates_factory({"schoolclass-DE-32-template.tex": template_obj}),
    )
    monkeypatch.setattr(schoolclasses_module.lr, "getval", lambda url, attribute, **kwargs: [])

    with pytest.raises(Exception, match="not found or empty"):
        print_schoolclass_list("7a", "admin")


def test_not_found_schoolclass_raises_when_members_is_none(monkeypatch):
    template_obj = SimpleNamespace(filename="schoolclass-DE-32-template.tex", count=32, type="schoolclass")
    monkeypatch.setattr(
        schoolclasses_module, "LatexTemplates",
        make_fake_templates_factory({"schoolclass-DE-32-template.tex": template_obj}),
    )
    monkeypatch.setattr(schoolclasses_module.lr, "getval", lambda url, attribute, **kwargs: None)

    with pytest.raises(Exception, match="not found or empty"):
        print_schoolclass_list("unknown-class", "admin")


def test_happy_path_sorts_students_and_calls_renderer(monkeypatch):
    template_obj = SimpleNamespace(filename="schoolclass-DE-32-template.tex", count=32, type="schoolclass")
    monkeypatch.setattr(
        schoolclasses_module, "LatexTemplates",
        make_fake_templates_factory({"schoolclass-DE-32-template.tex": template_obj}),
    )

    students_db = {
        "/users/bob": SimpleNamespace(sn="Zorro", givenName="Bob"),
        "/users/alice": SimpleNamespace(sn="Anders", givenName="Alice"),
    }

    def fake_getval(url, attribute, **kwargs):
        assert url == "/schoolclasses/7a"
        assert attribute == "sophomorixMembers"
        return ["bob", "alice"]

    def fake_get(url, as_dict=False, **kwargs):
        assert as_dict is False
        return students_db[url]

    monkeypatch.setattr(schoolclasses_module.lr, "getval", fake_getval)
    monkeypatch.setattr(schoolclasses_module.lr, "get", fake_get)

    renderer_instance = MagicMock()
    renderer_instance.compile.return_value = "/var/lib/lmntools/print/admin-schoolclass-7a.pdf"
    renderer_ctor = MagicMock(return_value=renderer_instance)
    monkeypatch.setattr(schoolclasses_module, "LatexRenderer", renderer_ctor)

    result = print_schoolclass_list("7a", "admin", school="default-school")

    assert result == "/var/lib/lmntools/print/admin-schoolclass-7a.pdf"
    renderer_ctor.assert_called_once()
    args, kwargs = renderer_ctor.call_args
    passed_template_obj, passed_data, passed_caller = args[0], args[1], args[2]
    assert passed_template_obj is template_obj
    assert passed_caller == "admin"
    assert kwargs["vars"] == {"school": "default-school", "schoolclass": "7a"}

    # sorted by lastname+firstname: "Anders" < "Zorro"
    assert passed_data == [
        {"lastname": "Anders", "firstname": "Alice"},
        {"lastname": "Zorro", "firstname": "Bob"},
    ]
    renderer_instance.compile.assert_called_once()


def test_school_param_not_forwarded_to_ldap_calls(monkeypatch):
    """
    Documents a production gap: print_schoolclass_list() accepts a `school`
    argument (used only for the template's `vars`), but its lr.getval()/
    lr.get() calls never pass school=school (see schoolclasses.py:21,27),
    unlike the equivalent code in passwords.py which does forward it. In a
    multi-school setup this means classes are always looked up against the
    LDAP router's default school regardless of the `school` argument.
    """
    template_obj = SimpleNamespace(filename="schoolclass-DE-32-template.tex", count=32, type="schoolclass")
    monkeypatch.setattr(
        schoolclasses_module, "LatexTemplates",
        make_fake_templates_factory({"schoolclass-DE-32-template.tex": template_obj}),
    )

    seen_kwargs = {}

    def fake_getval(url, attribute, **kwargs):
        seen_kwargs["getval"] = kwargs
        return ["bob"]

    def fake_get(url, as_dict=False, **kwargs):
        seen_kwargs["get"] = kwargs
        return SimpleNamespace(sn="Zorro", givenName="Bob")

    monkeypatch.setattr(schoolclasses_module.lr, "getval", fake_getval)
    monkeypatch.setattr(schoolclasses_module.lr, "get", fake_get)
    monkeypatch.setattr(schoolclasses_module, "LatexRenderer", MagicMock())

    print_schoolclass_list("7a", "admin", school="other-school")

    assert "school" not in seen_kwargs["getval"]
    assert "school" not in seen_kwargs["get"]
