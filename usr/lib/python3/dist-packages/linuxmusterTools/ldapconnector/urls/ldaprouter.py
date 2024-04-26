import re
import ldap
import logging

from linuxmusterTools.ldapconnector.connector import LdapConnector


# This marker will be replaced by the selected school, or default-school
SCHOOL_MARKER = "##SCHOOL_MARKER##"

class LMNLdapRouter:
    def __init__(self):
        self.lc = LdapConnector()
        self.urls = {}

    def _find_method(self, url):
       for url_model, func in self.urls.items():
            match = func.url_pattern.match(url)
            if match:
                data = match.groupdict()
                return func, data
       raise Exception(f'Requested search {url} unknown')

    def get(self, url, **kwargs):
        """
        Parse all urls and find the right method to handle the request.
        """

        func, data = self._find_method(url)
        ldap_filter = func(**data)

        # Replace selected school in the subdn where we are searching
        if 'school' in kwargs:
            school = kwargs['school']
        else:
            school = 'default-school'

        subdn = func.subdn.replace(SCHOOL_MARKER, school)

        if func.type == 'single':
            return self.lc.get_single(func.model, ldap_filter, scope=func.scope, subdn=subdn, **kwargs)

        if func.type == 'collection':
            return self.lc.get_collection(func.model, ldap_filter, scope=func.scope, subdn=subdn, **kwargs)

    def getval(self, url, attribute, **kwargs):

        if isinstance(attribute, str):
            attrs = [attribute]
        else:
            raise Exception(f"Attribute {attribute} should be a string.")

        results = self.get(url, attributes=attrs, dict=dict, **kwargs)

        return results.get(attribute, None)

    def getvalues(self, url, attributes, dict=True, **kwargs):

        if isinstance(attributes, list):
            attrs = attributes
        else:
            raise Exception(f"Attributes {attributes} should be a list of valid attributes.")

        results = self.get(url, attributes=attrs, dict=dict, **kwargs)

        if dict:
            return {attr: results.get(attr, None) for attr in attrs}
        else:
            return {attr: getattr(results, attr, None) for attr in attrs}

    def add_url(self, url, method):
        """
        Check collisions between URLs before adding to self.urls.

        :param url: Regexp to match
        :type url: re.pattern
        :param method: Method to run
        :type method: function
        """

        if url in self.urls:
            logging.warning(f"URL {url} already listed in the methods, not adding it!")
        else:
            self.urls[url] = method

    def single(self, pattern, model):
        """
        Search a single entry in the whole subtree of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'single'
            f.model = model
            f.scope = ldap.SCOPE_SUBTREE
            f.subdn = ''
            self.add_url(f.url_pattern, f)
            return f
        return decorator

    def single_l(self, pattern, model):
        """
        Search a single entry in the current level scope of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'single'
            f.model = model
            f.scope = ldap.SCOPE_ONELEVEL
            f.subdn = ''
            self.add_url(f.url_pattern, f)
            return f

        return decorator

    def single_s(self, pattern, model, subdn):
        """
        Search a single entry in the whole subtree of a subtree of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'single'
            f.model = model
            f.scope = ldap.SCOPE_SUBTREE
            f.subdn = subdn
            self.add_url(f.url_pattern, f)
            return f

        return decorator

    def single_ls(self, pattern, model, subdn):
        """
        Search a single entry in the current level scope of a subtree.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'single'
            f.model = model
            f.scope = ldap.SCOPE_ONELEVEL
            f.subdn = subdn
            self.add_url(f.url_pattern, f)
            return f

        return decorator

    def collection(self, pattern, model):
        """
        Search multiple entries in the whole subtree of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'collection'
            f.model = model
            f.scope = ldap.SCOPE_SUBTREE
            f.subdn = ''
            self.add_url(f.url_pattern, f)
            return f
        return decorator

    def collection_l(self, pattern, model):
        """
        Search multiple entries in the current level scope of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'collection'
            f.model = model
            f.scope = ldap.SCOPE_ONELEVEL
            f.subdn = ''
            self.add_url(f.url_pattern, f)
            return f

        return decorator

    def collection_s(self, pattern, model, subdn):
        """
        Search multiple entries in the whole subtree of a subtree of the base dn.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'collection'
            f.model = model
            f.scope = ldap.SCOPE_SUBTREE
            f.subdn = subdn
            self.add_url(f.url_pattern, f)
            return f

        return decorator

    def collection_ls(self, pattern, model, subdn):
        """
        Search multiple entries in the current level scope of a subtree.

        :param pattern: URL pattern
        :type pattern: basestring
        :param model: model obejct to return, can be e.g. LMNUser
        :type model: dataclass object
        """

        def decorator(f):
            f.url_pattern = re.compile(f'^{pattern}$')
            f.type = 'collection'
            f.model = model
            f.scope = ldap.SCOPE_ONELEVEL
            f.subdn = subdn
            self.add_url(f.url_pattern, f)
            return f

        return decorator

router = LMNLdapRouter()