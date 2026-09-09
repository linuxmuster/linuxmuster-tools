import pytest

from linuxmusterTools.ldapconnector.checks import is_valid_school, valid_schools
from linuxmusterTools.ldapconnector.urls.ldaprouter import router


SCHOOLS = ['default-school', 'school2']


class TestValidSchools:

    def test_returns_school_list(self, monkeypatch):
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: list(SCHOOLS))
        assert valid_schools() == SCHOOLS

    def test_queries_the_schools_route(self, monkeypatch):
        called = {}
        def mock_getval(url, attr, **kw):
            called['url'], called['attr'] = url, attr
            return list(SCHOOLS)

        monkeypatch.setattr(router, 'getval', mock_getval)
        valid_schools()
        assert called == {'url': '/schools', 'attr': 'ou'}


class TestIsValidSchool:

    @pytest.fixture(autouse=True)
    def _schools(self, monkeypatch):
        monkeypatch.setattr(router, 'getval', lambda url, attr, **kw: list(SCHOOLS))

    def test_existing_school(self):
        assert is_valid_school('default-school') is True

    def test_secondary_school(self):
        assert is_valid_school('school2') is True

    def test_unknown_school(self):
        assert is_valid_school('nonexistent') is False

    def test_global_is_not_a_school(self):
        # 'global' is the routing marker for global-administrators, it must
        # never be accepted as a school name.
        assert is_valid_school('global') is False

    def test_empty_school(self):
        assert is_valid_school('') is False
