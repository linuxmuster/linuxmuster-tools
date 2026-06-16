import pytest

from linuxmusterTools.ldapconnector.urls.ldaprouter import router


class TestURLMatching:

    def test_users_collection_route(self):
        func, data = router._find_method('/users')
        assert func.type == 'collection'

    def test_single_user_route(self):
        func, data = router._find_method('/users/johndoe')
        assert func.type == 'single'
        assert 'johndoe' in data.values()

    def test_user_search_route(self):
        func, data = router._find_method('/users/search/student/mueller')
        assert func.type == 'collection'
        assert data.get('selection') == 'student'
        assert data.get('query') == 'mueller'

    def test_schoolclasses_collection_route(self):
        func, data = router._find_method('/schoolclasses')
        assert func.type == 'collection'

    def test_single_schoolclass_route(self):
        func, data = router._find_method('/schoolclasses/7a')
        assert func.type == 'single'
        assert data.get('schoolclass') == '7a'

    def test_schoolclass_students_route(self):
        func, data = router._find_method('/schoolclasses/7a/students')
        assert func.type == 'collection'

    def test_projects_collection_route(self):
        func, data = router._find_method('/projects')
        assert func.type == 'collection'

    def test_single_project_route(self):
        func, data = router._find_method('/projects/robotics')
        assert func.type == 'single'

    def test_groups_collection_route(self):
        func, data = router._find_method('/groups')
        assert func.type == 'collection'

    def test_devices_collection_route(self):
        func, data = router._find_method('/devices')
        assert func.type == 'collection'

    def test_schools_collection_route(self):
        func, data = router._find_method('/schools')
        assert func.type == 'collection'

    def test_dn_lookup_route(self):
        func, data = router._find_method('/dn/CN=test,DC=linuxmuster,DC=lan')
        assert func.type == 'single'

    def test_unknown_url_raises(self):
        with pytest.raises(Exception, match='unknown'):
            router._find_method('/this/does/not/exist')

    def test_unknown_url_includes_path_in_message(self):
        with pytest.raises(Exception, match='/bad/route'):
            router._find_method('/bad/route')

    def test_roles_route(self):
        func, data = router._find_method('/roles/student')
        assert func.type == 'collection'
        assert data.get('role') == 'student'


class TestGetval:

    def test_getval_single_object_returns_scalar(self, monkeypatch):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {'cn': 'johndoe', 'mail': 'j@test.com'})
        assert router.getval('/users/johndoe', 'cn') == 'johndoe'

    def test_getval_collection_returns_list(self, monkeypatch):
        monkeypatch.setattr(router, 'get', lambda url, **kw: [{'cn': 'johndoe'}, {'cn': 'janedoe'}])
        result = router.getval('/users', 'cn')
        assert result == ['johndoe', 'janedoe']

    def test_getval_missing_key_returns_none(self, monkeypatch):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {'cn': 'johndoe'})
        assert router.getval('/users/johndoe', 'mail') is None

    def test_getval_non_string_attribute_raises(self):
        with pytest.raises(Exception):
            router.getval('/users', ['cn'])


class TestGetvalues:

    def test_getvalues_single_returns_dict(self, monkeypatch):
        monkeypatch.setattr(router, 'get', lambda url, **kw: {'cn': 'johndoe', 'mail': 'j@test.com', 'dn': 'x'})
        result = router.getvalues('/users/johndoe', ['cn', 'mail'])
        assert result == {'cn': 'johndoe', 'mail': 'j@test.com'}

    def test_getvalues_collection_returns_list_of_dicts(self, monkeypatch):
        monkeypatch.setattr(router, 'get', lambda url, **kw: [
            {'cn': 'johndoe', 'mail': 'j@test.com'},
            {'cn': 'janedoe', 'mail': 'jane@test.com'},
        ])
        result = router.getvalues('/users', ['cn', 'mail'])
        assert len(result) == 2
        assert result[0] == {'cn': 'johndoe', 'mail': 'j@test.com'}

    def test_getvalues_non_list_attributes_raises(self):
        with pytest.raises(Exception):
            router.getvalues('/users', 'cn')
