"""
Tests for print_passwords_list orchestration logic: unknown/empty-schoolclass
errors, the large=True template-name-swap logic, and the happy path.
LatexTemplates/LatexRenderer/SchoolConfig are mocked entirely; lr.getval/
lr.get are mocked per test.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import linuxmusterTools.print.passwords as passwords_module
from linuxmusterTools.print.passwords import print_passwords_list


class FakeTemplates:
    def __init__(self, templates=None):
        self.templates = templates or {}


def make_fake_templates_factory(templates_dict):
    def factory():
        return FakeTemplates(templates_dict)
    return factory


class FakeSchoolConfig:
    def __init__(self, school="default-school"):
        self.config = {"school": {"SCHOOL_LONGNAME": "Test School"}}


def test_unknown_template_raises(monkeypatch):
    monkeypatch.setattr(passwords_module, "LatexTemplates", make_fake_templates_factory({}))

    with pytest.raises(Exception, match="Can not find the template"):
        print_passwords_list("7a", "admin", template="does-not-exist.tex")


def test_empty_schoolclass_raises(monkeypatch):
    template_obj = SimpleNamespace(filename="passwords-DE-1-template.tex", count=1, type="passwords")
    monkeypatch.setattr(
        passwords_module, "LatexTemplates",
        make_fake_templates_factory({"passwords-DE-1-template.tex": template_obj}),
    )
    monkeypatch.setattr(passwords_module.lr, "getval", lambda url, attribute, **kwargs: [])

    with pytest.raises(Exception, match="not found or empty"):
        print_passwords_list("7a", "admin")


def test_large_true_swaps_passwords_prefix_to_passwordslarge(monkeypatch):
    """
    large=True with a template starting with "passwords-" should look up
    "passwordslarge-..." instead (passwords.py:15-16).
    """
    large_template_obj = SimpleNamespace(
        filename="passwordslarge-DE-1-template.tex", count=1, type="passwordslarge",
    )
    templates_dict = {"passwordslarge-DE-1-template.tex": large_template_obj}
    monkeypatch.setattr(passwords_module, "LatexTemplates", make_fake_templates_factory(templates_dict))
    monkeypatch.setattr(passwords_module.lr, "getval", lambda url, attribute, **kwargs: [])

    # Should NOT raise "Can not find the template" - it should resolve to the
    # swapped passwordslarge- name and only fail later on the empty schoolclass.
    with pytest.raises(Exception, match="not found or empty"):
        print_passwords_list("7a", "admin", large=True, template="passwords-DE-1-template.tex")


def test_large_true_leaves_non_passwords_prefixed_template_unchanged(monkeypatch):
    """
    The swap only applies when template.startswith("passwords-"); a custom
    template name should be looked up unchanged and thus fail with the
    "Can not find the template" error if absent.
    """
    monkeypatch.setattr(passwords_module, "LatexTemplates", make_fake_templates_factory({}))

    with pytest.raises(Exception, match=r"Can not find the template custom-template\.tex"):
        print_passwords_list("7a", "admin", large=True, template="custom-template.tex")


def test_large_false_keeps_original_template_name(monkeypatch):
    monkeypatch.setattr(passwords_module, "LatexTemplates", make_fake_templates_factory({}))

    with pytest.raises(Exception, match=r"Can not find the template passwords-DE-1-template\.tex"):
        print_passwords_list("7a", "admin", large=False, template="passwords-DE-1-template.tex")


def test_happy_path_builds_data_and_vars_and_calls_renderer(monkeypatch):
    template_obj = SimpleNamespace(filename="passwords-DE-1-template.tex", count=1, type="passwords")
    monkeypatch.setattr(
        passwords_module, "LatexTemplates",
        make_fake_templates_factory({"passwords-DE-1-template.tex": template_obj}),
    )

    users_db = {
        "/users/bob": SimpleNamespace(
            sn="Zorro", givenName="Bob", sAMAccountName="bob", sophomorixFirstPassword="pw-bob",
        ),
        "/users/alice": SimpleNamespace(
            sn="Anders", givenName="Alice", sAMAccountName="alice", sophomorixFirstPassword="pw-alice",
        ),
        "/users/teacher1": SimpleNamespace(givenName="Jane", sn="Doe"),
    }

    def fake_getval(url, attribute, **kwargs):
        assert kwargs.get("school") == "default-school"
        if attribute == "sophomorixMembers":
            assert url == "/schoolclasses/7a"
            return ["bob", "alice"]
        if attribute == "sophomorixAdmins":
            assert url == "/schoolclasses/7a"
            return ["teacher1"]
        raise AssertionError(f"unexpected getval attribute {attribute!r}")

    def fake_get(url, as_dict=False, **kwargs):
        assert as_dict is False
        assert kwargs.get("school") == "default-school"
        return users_db[url]

    monkeypatch.setattr(passwords_module.lr, "getval", fake_getval)
    monkeypatch.setattr(passwords_module.lr, "get", fake_get)
    monkeypatch.setattr(passwords_module, "SchoolConfig", FakeSchoolConfig)
    monkeypatch.setattr(passwords_module, "SAMBA_WORKGROUP", "TESTDOMAIN")

    renderer_instance = MagicMock()
    renderer_instance.compile.return_value = "/var/lib/lmntools/print/admin-passwords-7a.pdf"
    renderer_ctor = MagicMock(return_value=renderer_instance)
    monkeypatch.setattr(passwords_module, "LatexRenderer", renderer_ctor)

    result = print_passwords_list("7a", "admin", school="default-school")

    assert result == "/var/lib/lmntools/print/admin-passwords-7a.pdf"
    renderer_ctor.assert_called_once()
    args, kwargs = renderer_ctor.call_args
    passed_template_obj, passed_data, passed_caller = args[0], args[1], args[2]

    assert passed_template_obj is template_obj
    assert passed_caller == "admin"

    # sorted by lastname+firstname: "Anders" < "Zorro"
    assert passed_data == [
        {
            "lastname": "Anders", "firstname": "Alice", "login": "alice",
            "password": "pw-alice", "schoolclass": "7a",
        },
        {
            "lastname": "Zorro", "firstname": "Bob", "login": "bob",
            "password": "pw-bob", "schoolclass": "7a",
        },
    ]

    passed_vars = kwargs["vars"]
    assert passed_vars["schoolclass"] == "7a"
    assert passed_vars["school_longname"] == "Test School"
    assert passed_vars["filename"] == "admin-passwords-7a"
    assert passed_vars["domain"] == "TESTDOMAIN"
    assert passed_vars["teachermembers"] == "Jane Doe"

    renderer_instance.compile.assert_called_once()


def test_no_teachers_yields_empty_teachermembers_string(monkeypatch):
    template_obj = SimpleNamespace(filename="passwords-DE-1-template.tex", count=1, type="passwords")
    monkeypatch.setattr(
        passwords_module, "LatexTemplates",
        make_fake_templates_factory({"passwords-DE-1-template.tex": template_obj}),
    )

    def fake_getval(url, attribute, **kwargs):
        if attribute == "sophomorixMembers":
            return ["bob"]
        if attribute == "sophomorixAdmins":
            return None
        raise AssertionError(f"unexpected getval attribute {attribute!r}")

    monkeypatch.setattr(passwords_module.lr, "getval", fake_getval)
    monkeypatch.setattr(
        passwords_module.lr, "get",
        lambda url, as_dict=False, **kwargs: SimpleNamespace(
            sn="Zorro", givenName="Bob", sAMAccountName="bob", sophomorixFirstPassword="pw",
        ),
    )
    monkeypatch.setattr(passwords_module, "SchoolConfig", FakeSchoolConfig)
    monkeypatch.setattr(passwords_module, "SAMBA_WORKGROUP", "TESTDOMAIN")

    renderer_instance = MagicMock()
    renderer_ctor = MagicMock(return_value=renderer_instance)
    monkeypatch.setattr(passwords_module, "LatexRenderer", renderer_ctor)

    print_passwords_list("7a", "admin", school="default-school")

    _, kwargs = renderer_ctor.call_args
    assert kwargs["vars"]["teachermembers"] == ""
